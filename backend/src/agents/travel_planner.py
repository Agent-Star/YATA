"""Travel Planner Agent - 基于 NLU/RAG 的旅行规划 Agent"""

from __future__ import annotations

import logging
from typing import Literal, cast

from langchain_core.messages import AIMessage, HumanMessage
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
    调用 NLU 服务节点

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

    logger.info(f"TravelPlanner: Calling NLU service with session_id={session_id}")

    try:
        # 调用 NLU 服务
        async with get_nlu_client() as nlu_client:
            nlu_response = await nlu_client.call_nlu(
                text=user_input,
                session_id=session_id,
            )

        logger.info(
            f"TravelPlanner: NLU response received - "
            f"type={nlu_response.type}, status={nlu_response.status}"
        )

        # 将 NLU 的回复转换为 AIMessage
        ai_message = AIMessage(content=nlu_response.reply)
        ai_message = cast(AIMessage, add_timestamp_to_message(ai_message))

        # 检查是否需要追问 (status=incomplete)
        if nlu_response.status == "incomplete":
            logger.warning(
                "TravelPlanner: NLU returned incomplete status, reply contains follow-up questions"
            )
            # 目前 NLU 的追问功能有 BUG, 但仍然返回 incomplete 的回复
            # 这里我们直接返回 NLU 的回复, 让用户补充信息

        return {
            "messages": [ai_message],
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
