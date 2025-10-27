"""行程规划路由

提供前端行程规划功能的接口实现。
"""

import json
import logging
from collections.abc import AsyncGenerator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, AIMessageChunk, AnyMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from agents import DEFAULT_AGENT, AgentGraph, get_agent
from auth import User, current_active_user
from auth.database import get_async_session
from core import settings
from service.thread_manager import get_or_create_main_thread
from service.utils import convert_message_content_to_string, remove_tool_calls

logger = logging.getLogger(__name__)

# 创建路由器
planner_router = APIRouter(prefix="/planner", tags=["planner"])


# === 数据模型 ===


class FrontendMessage(BaseModel):
    """前端消息格式"""

    id: str
    role: str  # "user" | "assistant"
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    createdAt: str | None = None


class HistoryResponse(BaseModel):
    """历史记录响应"""

    messages: list[FrontendMessage]


class PlanContext(BaseModel):
    """行程规划上下文"""

    language: str | None = Field(default=None, description="UI 语言")
    history: list[FrontendMessage] = Field(default_factory=list, description="前端传递的历史")


class PlanRequest(BaseModel):
    """行程规划请求"""

    prompt: str = Field(description="用户输入")
    context: PlanContext = Field(default_factory=PlanContext, description="上下文")


# === 辅助函数 ===


def langchain_message_to_frontend(message: AnyMessage) -> FrontendMessage:
    """将 LangChain 消息转换为前端格式"""
    # 确定角色
    if isinstance(message, HumanMessage):
        role = "user"
    elif isinstance(message, AIMessage):
        role = "assistant"
    else:
        role = "assistant"  # 默认为 assistant

    # 提取消息 ID (使用 run_id 或生成新的)
    message_id = getattr(message, "id", None) or str(id(message))

    # 提取内容
    content = str(message.content) if message.content else ""

    # 提取元数据
    metadata = getattr(message, "response_metadata", {})

    # 提取创建时间 (如果有)
    created_at = None

    return FrontendMessage(
        id=message_id,
        role=role,
        content=content,
        metadata=metadata,
        createdAt=created_at,
    )


# === 路由实现 ===


@planner_router.get("/history", response_model=HistoryResponse)
async def get_history(
    current_user: Annotated[User, Depends(current_active_user)],
    session: AsyncSession = Depends(get_async_session),
) -> HistoryResponse:
    """
    获取用户的历史对话记录

    前端适配接口, 对应 GET /planner/history
    根据登录用户自动查询其主 Thread 的对话历史
    """
    try:
        # 获取用户的主 Thread ID
        thread_id = await get_or_create_main_thread(current_user, session)

        # 获取 agent (使用默认 agent 或专门的 travel planner)
        agent: AgentGraph = get_agent(DEFAULT_AGENT)

        # 获取 Thread 状态
        config = RunnableConfig(configurable={"thread_id": thread_id})
        state = await agent.aget_state(config=config)

        # 提取消息历史
        messages: list[AnyMessage] = state.values.get("messages", [])

        # 转换为前端格式
        frontend_messages = [langchain_message_to_frontend(msg) for msg in messages]

        return HistoryResponse(messages=frontend_messages)

    except Exception as e:
        logger.error(f"获取历史记录失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "API_ERROR", "message": "获取历史记录失败"},
        )


@planner_router.post("/plan/stream")
async def plan_stream(
    request: PlanRequest,
    current_user: Annotated[User, Depends(current_active_user)],
    session: AsyncSession = Depends(get_async_session),
) -> StreamingResponse:
    """
    流式行程规划接口

    前端适配接口, 对应 POST /planner/plan/stream
    使用 SSE 返回增量响应
    """

    async def generate_events() -> AsyncGenerator[str, None]:
        """生成 SSE 事件流"""
        try:
            # 获取用户的主 Thread ID
            thread_id = await get_or_create_main_thread(current_user, session)

            # 获取 agent
            agent: AgentGraph = get_agent(DEFAULT_AGENT)

            # 构建配置
            configurable: dict[str, Any] = {"thread_id": thread_id, "user_id": str(current_user.id)}
            if request.context.language:
                configurable["language"] = request.context.language
            if settings.DEFAULT_MODEL:
                configurable["model"] = settings.DEFAULT_MODEL

            config = RunnableConfig(configurable=configurable)

            # 构建输入
            input_message = HumanMessage(content=request.prompt)
            user_input = {"messages": [input_message]}

            # 生成消息 ID (用于最终返回)
            message_id = f"msg-{id(input_message)}"

            # 流式调用 agent
            async for stream_event in agent.astream(
                user_input, config=config, stream_mode=["updates", "messages"], subgraphs=True
            ):
                if not isinstance(stream_event, tuple):
                    continue

                # 解析事件
                if len(stream_event) == 3:
                    _, stream_mode, event = stream_event
                else:
                    stream_mode, event = stream_event

                # 处理 updates 事件
                if stream_mode == "updates":
                    for node, updates in event.items():
                        if node == "__interrupt__":
                            continue

                        updates = updates or {}
                        update_messages = updates.get("messages", [])

                        # 过滤掉工具消息
                        for msg in update_messages:
                            if isinstance(msg, AIMessage) and msg.content:
                                # 发送完整消息作为 token 事件
                                content = str(msg.content)
                                yield f"data: {json.dumps({'type': 'token', 'delta': content})}\n\n"

                # 处理 messages 事件 (token 流)
                if stream_mode == "messages":
                    msg, metadata = event
                    if isinstance(msg, AIMessageChunk):
                        content = remove_tool_calls(msg.content)
                        if content:
                            yield f"data: {json.dumps({'type': 'token', 'delta': convert_message_content_to_string(content)})}\n\n"

            # 发送结束事件
            empty_dict = {}
            yield f"data: {json.dumps({'type': 'end', 'messageId': message_id, 'metadata': empty_dict})}\n\n"

            # 发送 [DONE] 标记
            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error(f"流式规划失败: {e}")
            yield f"data: {json.dumps({'type': 'error', 'content': '服务器异常'})}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
        },
    )
