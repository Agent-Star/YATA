"""
行程规划路由

提供前端行程规划功能的接口实现.
"""

import json
import logging
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Annotated, Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, AIMessageChunk, AnyMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from agents import DEFAULT_AGENT, AgentGraph, get_agent
from agents.timestamp import add_timestamp_to_message, create_timestamped_message
from auth import User, current_active_user
from external_services.exceptions import NLUServiceError, ServiceUnavailableError
from external_services.nlu_client import get_nlu_client
from auth.database import get_async_session
from auth.models import Favorite
from core import settings
from schema.schema import FavoriteCreate, FavoriteRead, FavoriteResponse
from service.thread_manager import create_new_thread_for_user, get_or_create_main_thread

logger = logging.getLogger(__name__)

# 创建路由器
planner_router = APIRouter(prefix="/planner", tags=["planner"])

# 是否在 history 中过滤 ToolMessage
logger.info(f"Filter `ToolMessage` in History: {settings.FILTER_TOOL_MESSAGE_IN_HISTORY}")

# === 数据模型 ===


class FrontendMessage(BaseModel):
    """前端消息格式"""

    id: str
    role: str | Literal["user", "assistant"]
    content: str
    metadata: dict[str, Any] | None = None  # nullable
    createdAt: str | None = None
    isFavorited: bool = Field(default=False, description="是否已被当前用户收藏")


class HistoryResponse(BaseModel):
    """历史记录响应"""

    messages: list[FrontendMessage]


class PlanContext(BaseModel):
    """行程规划上下文"""

    language: str | None = Field(default=None, description="UI 语言")
    history: list[FrontendMessage] | None = Field(default=None, description="前端传递的历史")


class PlanRequest(BaseModel):
    """行程规划请求"""

    prompt: str = Field(description="用户输入")
    context: PlanContext | None = Field(default=None, description="上下文")


# === 辅助函数 ===


def langchain_message_to_frontend(message: AnyMessage) -> FrontendMessage:
    """将 LangChain 消息转换为前端格式"""
    from datetime import datetime, timezone

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

    # 提取创建时间 (尝试从多个来源获取)
    created_at = None

    # 1. 尝试从 additional_kwargs 获取
    if hasattr(message, "additional_kwargs"):
        additional_kwargs = getattr(message, "additional_kwargs", {})
        created_at = additional_kwargs.get("created_at") or additional_kwargs.get("timestamp")

    # 2. 尝试从 response_metadata 获取
    if not created_at and metadata:
        created_at = metadata.get("created_at") or metadata.get("timestamp")

    # 3. 如果仍未找到时间戳, 使用当前 UTC 时间
    # 注意: 这不是理想方案, 但确保字段有值
    if not created_at:
        created_at = datetime.now(timezone.utc).isoformat()

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
    filter_tool_message: bool = settings.FILTER_TOOL_MESSAGE_IN_HISTORY,
) -> HistoryResponse:
    """
    获取用户的历史对话记录

    前端适配接口, 对应 GET /planner/history
    根据登录用户自动查询其主 Thread 的对话历史
    """
    try:
        # 获取用户的主 Thread ID
        thread_id = await get_or_create_main_thread(current_user, session)

        # 获取 Thread 状态
        # 注意：不使用 agent.aget_state()，因为它返回 value（只有 chunks）
        # 而是使用 get_history_helper 通过 previous 参数获取完整历史（来自 save）
        history_helper = get_agent("get-history-helper")

        config = RunnableConfig(configurable={"thread_id": thread_id})
        result = await history_helper.ainvoke({"messages": []}, config=config)

        # 提取消息历史（从 save 中保存的完整历史）
        messages: list[AnyMessage] = result.get("messages", [])

        # TODO: 权宜之计, 彻底解决还需后端进行 message 分类 + 前端提供支持
        # filter_tool_message 为 True 时, 过滤掉 ToolMessage (不展示 snippet)
        filtered_messages = (
            [msg for msg in messages if not isinstance(msg, ToolMessage)]
            if filter_tool_message
            else messages
        )

        # 转换为前端格式
        frontend_messages = [langchain_message_to_frontend(msg) for msg in filtered_messages]

        # 查询用户的所有收藏记录
        stmt = select(Favorite.message_id).where(Favorite.user_id == current_user.id)
        result = await session.execute(stmt)
        favorited_message_ids = {row[0] for row in result.fetchall()}

        # 标记 isFavorited
        for msg in frontend_messages:
            msg.isFavorited = msg.id in favorited_message_ids

        # 显式按时间升序排列 (确保前端按正确顺序渲染)
        # 虽然 LangGraph 通常已按时间顺序存储, 但显式排序使代码意图更清晰
        frontend_messages.sort(key=lambda m: m.createdAt if m.createdAt else "")

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
        """
        生成 SSE 事件流

        直接调用 NLU 服务实现真正的逐 token 流式输出,
        如果 NLU 失败则 fallback 到 research-assistant.
        """
        # 获取用户的主 Thread ID
        thread_id = await get_or_create_main_thread(current_user, session)

        # 构建配置
        configurable: dict[str, Any] = {"thread_id": thread_id, "user_id": str(current_user.id)}
        if request.context and request.context.language:
            configurable["language"] = request.context.language
        if settings.DEFAULT_MODEL:
            configurable["model"] = settings.DEFAULT_MODEL

        config = RunnableConfig(configurable=configurable)

        # 构建输入消息 (带时间戳)
        input_message = create_timestamped_message(request.prompt, HumanMessage)
        message_id = f"msg-{id(input_message)}"

        try:
            # ========== 尝试调用 NLU 流式 ==========
            full_content = ""

            async with get_nlu_client() as nlu_client:
                async for event in nlu_client.call_nlu_stream(
                    text=request.prompt,
                    session_id=thread_id,
                ):
                    event_type = event.get("type")

                    if event_type == "token":
                        # ✅ 立即转发给前端
                        delta = event.get("delta", "")
                        full_content += delta
                        yield f"data: {json.dumps({'type': 'token', 'delta': delta})}\n\n"

                    elif event_type == "error":
                        # NLU 返回错误
                        error_message = event.get("message", "Unknown error")
                        logger.error(f"PlanStream: NLU returned error - {error_message}")
                        raise NLUServiceError(error_message)

                    elif event_type == "end":
                        # NLU 成功完成
                        break

            # 检查是否收到了完整的回复
            if not full_content:
                logger.warning("PlanStream: NLU returned empty content")
                raise NLUServiceError("NLU returned empty content")

            # ========== NLU 成功，保存历史 ==========

            # 创建完整的 AIMessage
            final_message = AIMessage(content=full_content)
            final_message = add_timestamp_to_message(final_message)

            # 使用 save-history-helper 保存历史（不会调用 NLU）
            save_helper = get_agent("save-history-helper")
            await save_helper.ainvoke(
                {"messages": [input_message, final_message]},
                config=config
            )

            # 发送结束事件
            empty_dict = {}
            yield f"data: {json.dumps({'type': 'end', 'messageId': message_id, 'metadata': empty_dict})}\n\n"
            yield "data: [DONE]\n\n"

        except (ServiceUnavailableError, NLUServiceError) as e:
            # ========== NLU 失败，Fallback 到 research-assistant ==========
            logger.warning(
                f"PlanStream: NLU failed ({type(e).__name__}: {e}), "
                f"falling back to research-assistant"
            )

            try:
                # 获取 research-assistant agent
                research_agent = get_agent("research-assistant")

                # 调用 research-assistant（使用流式）
                logger.info("PlanStream: Calling research-assistant as fallback")

                async for stream_event in research_agent.astream(
                    {"messages": [input_message]},
                    config=config,
                    stream_mode=["messages"],
                    subgraphs=True
                ):
                    if not isinstance(stream_event, tuple):
                        continue

                    # 解析事件
                    if len(stream_event) == 3:
                        _, stream_mode, event = stream_event
                    else:
                        stream_mode, event = stream_event

                    # 处理 messages 事件 (token 流)
                    if stream_mode == "messages":
                        msg, _ = event
                        if isinstance(msg, AIMessageChunk):
                            content = msg.content
                            if content:
                                # 转换为字符串（处理可能的复杂内容类型）
                                if isinstance(content, str):
                                    delta = content
                                else:
                                    delta = str(content)
                                yield f"data: {json.dumps({'type': 'token', 'delta': delta})}\n\n"

                # 发送结束事件
                empty_dict = {}
                yield f"data: {json.dumps({'type': 'end', 'messageId': message_id, 'metadata': empty_dict})}\n\n"
                yield "data: [DONE]\n\n"

            except Exception as fallback_error:
                logger.error(f"PlanStream: Fallback to research-assistant also failed: {fallback_error}")
                yield f"data: {json.dumps({'type': 'error', 'content': '服务暂时不可用，请稍后重试'})}\n\n"
                yield "data: [DONE]\n\n"

        except Exception as e:
            # ========== 其他未预期的错误 ==========
            logger.error(f"PlanStream: Unexpected error: {e}", exc_info=True)
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


@planner_router.delete("/history", status_code=status.HTTP_204_NO_CONTENT)
async def delete_history(
    current_user: Annotated[User, Depends(current_active_user)],
    session: AsyncSession = Depends(get_async_session),
) -> None:
    """
    删除用户的历史对话记录

    前端适配接口, 对应 DELETE /planner/history

    实现方式: 为用户创建新的主 Thread ID, 旧的历史记录将无法访问.
    幂等操作: 重复调用不会报错.
    """
    try:
        # 删除用户的所有收藏记录 (保持数据一致性)
        stmt = delete(Favorite).where(Favorite.user_id == current_user.id)
        await session.execute(stmt)
        await session.commit()

        # 调用 thread_manager 创建新 Thread
        new_thread_id = await create_new_thread_for_user(current_user, session)

        logger.info(f"用户 {current_user.id} 的历史记录已清空, 新 Thread ID: {new_thread_id}")

        # 返回 204 无内容

    except Exception as e:
        logger.error(f"删除历史记录失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "API_ERROR", "message": "删除历史记录失败"},
        )


@planner_router.post("/favorites", response_model=FavoriteResponse, status_code=status.HTTP_200_OK)
async def create_favorite(
    request: FavoriteCreate,
    current_user: Annotated[User, Depends(current_active_user)],
    session: AsyncSession = Depends(get_async_session),
) -> FavoriteResponse:
    """
    收藏指定消息

    前端适配接口, 对应 POST /planner/favorites

    从用户的历史记录中查找消息并创建收藏记录.
    若消息不存在或已收藏, 返回相应错误.
    """
    try:
        # 1. 获取用户的主 Thread ID
        thread_id = await get_or_create_main_thread(current_user, session)

        # 2. 从 Thread 历史中查找消息
        agent: AgentGraph = get_agent(DEFAULT_AGENT)
        config = RunnableConfig(configurable={"thread_id": thread_id})
        state = await agent.aget_state(config=config)
        messages: list[AnyMessage] = state.values.get("messages", [])

        # 3. 查找目标消息
        target_message: AnyMessage | None = None
        for msg in messages:
            msg_id = getattr(msg, "id", None) or str(id(msg))
            if msg_id == request.messageId:
                target_message = msg
                break

        if not target_message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "MESSAGE_NOT_FOUND", "message": "消息不存在"},
            )

        # 4. 检查是否已收藏
        stmt = select(Favorite).where(
            Favorite.user_id == current_user.id,
            Favorite.message_id == request.messageId,
        )
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "ALREADY_FAVORITED", "message": "该消息已收藏"},
            )

        # 5. 提取消息内容和元数据
        role = "user" if isinstance(target_message, HumanMessage) else "assistant"
        content = str(target_message.content) if target_message.content else ""
        msg_metadata = getattr(target_message, "response_metadata", None)

        # 6. 创建收藏记录
        favorite = Favorite(
            id=uuid4(),
            user_id=current_user.id,
            message_id=request.messageId,
            role=role,
            content=content,
            message_metadata=msg_metadata,
            saved_at=datetime.now(timezone.utc),
        )

        session.add(favorite)
        await session.commit()
        await session.refresh(favorite)

        # 7. 返回响应
        return FavoriteResponse(
            favorite=FavoriteRead(
                id=str(favorite.id),
                messageId=favorite.message_id,
                role=favorite.role,
                content=favorite.content,
                metadata=favorite.message_metadata,
                savedAt=favorite.saved_at.isoformat(),
            )
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建收藏失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "API_ERROR", "message": "创建收藏失败"},
        )


@planner_router.delete("/favorites/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_favorite(
    message_id: str,
    current_user: Annotated[User, Depends(current_active_user)],
    session: AsyncSession = Depends(get_async_session),
) -> None:
    """
    取消收藏指定消息

    前端适配接口, 对应 DELETE /planner/favorites/{message_id}

    幂等操作: 若消息未收藏, 也返回 204.
    """
    try:
        # 删除收藏记录 (基于 user_id + message_id)
        stmt = delete(Favorite).where(
            Favorite.user_id == current_user.id,
            Favorite.message_id == message_id,
        )

        await session.execute(stmt)
        await session.commit()

        logger.info(f"用户 {current_user.id} 取消收藏消息 {message_id}")

        # 无论是否删除了记录, 都返回 204 (幂等)

    except Exception as e:
        logger.error(f"取消收藏失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "API_ERROR", "message": "取消收藏失败"},
        )
