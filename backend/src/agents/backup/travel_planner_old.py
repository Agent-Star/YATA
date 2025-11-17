"""Travel Planner Agent - 基于 NLU/RAG 的旅行规划 Agent"""

from __future__ import annotations

import logging
from typing import Literal, cast

from langchain_core.messages import AIMessageChunk, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, MessagesState, StateGraph

from agents.timestamp import add_timestamp_to_message
from external_services import (
    NLUResponse,
    NLUServiceError,
    ServiceUnavailableError,
    get_nlu_client,
)

logger = logging.getLogger(__name__)


# === 状态定义 ===


class TravelPlannerState(MessagesState, total=False):
    """Travel Planner Agent 状态"""

    nlu_response: NLUResponse | None  # NLU 服务响应 (可选)
    fallback_triggered: bool  # 是否触发兜底机制
    error_message: str | None  # 错误信息 (用于日志)


# === 节点实现 ===


async def call_nlu_service(
    state: TravelPlannerState,
    config: RunnableConfig,
) -> TravelPlannerState:
    """
    调用 NLU 服务节点 (流式)

    Args:
        state: 当前状态
        config: 运行配置

    Returns:
        更新后的状态
    """
    # 获取用户最后一条消息
    messages = state["messages"]
    if not messages:
        logger.error("TravelPlanner: No messages in state")
        return {
            "messages": [],
            "fallback_triggered": True,
            "error_message": "No input message",
        }

    last_message = messages[-1]
    if not isinstance(last_message, HumanMessage):
        logger.error(f"TravelPlanner: Last message is not HumanMessage: {type(last_message)}")
        return {
            "messages": [],
            "fallback_triggered": True,
            "error_message": "Invalid message type",
        }

    user_input = str(last_message.content)

    # 获取 session_id (使用 thread_id)
    session_id = config.get("configurable", {}).get("thread_id")

    logger.info(f"TravelPlanner: Calling NLU service (streaming) with session_id={session_id}")

    try:
        # 流式调用 NLU 服务
        full_content = ""
        chunks = []
        nlu_session_id = None
        nlu_status = None

        async with get_nlu_client() as nlu_client:
            async for event in nlu_client.call_nlu_stream(
                text=user_input,
                session_id=session_id,
            ):
                event_type = event.get("type")

                if event_type == "phase_start":
                    # 阶段开始 (可选: 记录日志)
                    phase = event.get("phase")
                    logger.debug(f"TravelPlanner: NLU phase started - {phase}")

                elif event_type == "phase_end":
                    # 阶段完成 (可选: 记录日志)
                    phase = event.get("phase")
                    logger.debug(f"TravelPlanner: NLU phase ended - {phase}")

                elif event_type == "token":
                    # 接收到一个 token
                    delta = event.get("delta", "")
                    full_content += delta

                    # 创建 AIMessageChunk 并添加时间戳
                    chunk = AIMessageChunk(content=delta)
                    chunk = cast(AIMessageChunk, add_timestamp_to_message(chunk))
                    chunks.append(chunk)

                elif event_type == "end":
                    # 流式结束
                    nlu_session_id = event.get("session_id")
                    nlu_status = event.get("status")
                    logger.info(
                        f"TravelPlanner: NLU streaming completed - "
                        f"session_id={nlu_session_id}, status={nlu_status}"
                    )
                    break

                elif event_type == "error":
                    # NLU 返回错误
                    error_message = event.get("message", "Unknown error")
                    logger.error(f"TravelPlanner: NLU returned error - {error_message}")
                    raise NLUServiceError(error_message)

        # 检查是否收到了完整的回复
        if not full_content:
            logger.warning("TravelPlanner: NLU returned empty content")
            return {
                "messages": [],
                "fallback_triggered": True,
                "error_message": "NLU returned empty content",
            }

        # 检查是否需要追问 (status=incomplete)
        if nlu_status == "incomplete":
            logger.warning(
                "TravelPlanner: NLU returned incomplete status, reply contains follow-up questions"
            )

        # 构造 NLUResponse 对象 (用于保持向后兼容)
        nlu_response = NLUResponse(
            session_id=nlu_session_id or session_id or "unknown",
            type="itinerary",  # 默认为 itinerary
            status=nlu_status or "complete",
            reply=full_content,
        )

        return {
            "messages": chunks,
            "nlu_response": nlu_response,
            "fallback_triggered": False,
        }

    except ServiceUnavailableError as e:
        logger.error(f"TravelPlanner: NLU service unavailable - {e}")
        return {
            "messages": [],
            "fallback_triggered": True,
            "error_message": str(e),
        }

    except NLUServiceError as e:
        logger.error(f"TravelPlanner: NLU service error - {e}")
        return {
            "messages": [],
            "fallback_triggered": True,
            "error_message": str(e),
        }

    except Exception as e:
        logger.error(f"TravelPlanner: Unexpected error - {e}", exc_info=True)
        return {
            "messages": [],
            "fallback_triggered": True,
            "error_message": str(e),
        }


async def fallback_to_research_assistant(
    state: TravelPlannerState,
    config: RunnableConfig,
) -> TravelPlannerState:
    """
    兜底节点: 降级到 Research-Assistant

    Args:
        state: 当前状态
        config: 运行配置

    Returns:
        更新后的状态
    """
    # 延迟导入以避免循环导入
    from agents.agents import get_agent

    logger.info("TravelPlanner: Fallback triggered, calling Research-Assistant")

    # 获取 Research-Assistant Agent
    research_agent = get_agent("research-assistant")

    # 调用 Research-Assistant (非流式)
    # 注意: 这里我们直接调用, 不使用 astream, 因为 StateGraph 会处理流式
    result = await research_agent.ainvoke(state, config)

    # 返回 Research-Assistant 的输出
    return {
        "messages": result.get("messages", []),
        "fallback_triggered": True,
    }


# === 条件边 ===


def should_fallback(state: TravelPlannerState) -> Literal["fallback", "done"]:
    """
    判断是否需要兜底

    Args:
        state: 当前状态

    Returns:
        "fallback" 表示需要兜底, "done" 表示正常结束
    """
    return "fallback" if state.get("fallback_triggered", False) else "done"


# === StateGraph 构建 ===


def build_travel_planner():
    """
    构建 Travel Planner Agent 状态图

    Returns:
        CompiledStateGraph: 编译后的状态图
    """
    agent = StateGraph(TravelPlannerState)

    # 添加节点
    agent.add_node("call_nlu_service", call_nlu_service)
    agent.add_node("fallback_to_research_assistant", fallback_to_research_assistant)

    # 设置入口
    agent.set_entry_point("call_nlu_service")

    # 添加条件边
    agent.add_conditional_edges(
        "call_nlu_service",
        should_fallback,
        {
            "fallback": "fallback_to_research_assistant",
            "done": END,
        },
    )

    # fallback 节点执行后结束
    agent.add_edge("fallback_to_research_assistant", END)

    return agent.compile()


# === 导出 ===

travel_planner = build_travel_planner()
