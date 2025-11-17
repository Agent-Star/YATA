"""Travel Planner Agent - Functional API 实现

使用 LangGraph Functional API 重构，解决流式返回历史记录分块问题。

关键改进：
1. 使用 entrypoint.final(value=..., save=...) 区分流式输出和持久化保存
2. 流式输出：返回所有 AIMessageChunk，实现逐 token 显示
3. 持久化保存：只保存完整的 AIMessage，避免历史记录分块

参考：
- backend/src/agents/chatbot.py (现有 Functional API 实现)
- backend/docs/gen/travel-planner/streaming-chunks-history-fix.md
"""

from __future__ import annotations

import logging
from typing import cast

from langchain_core.messages import AIMessage, AIMessageChunk, AnyMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.func import entrypoint

from agents.timestamp import add_timestamp_to_message
from external_services import (
    NLUServiceError,
    ServiceUnavailableError,
    get_nlu_client,
)

logger = logging.getLogger(__name__)


@entrypoint()
async def travel_planner_functional(
    inputs: dict[str, list[AnyMessage]],
    *,
    previous: dict[str, list[AnyMessage]] | None,
    config: RunnableConfig,
) -> entrypoint.final:
    """
    Travel Planner Agent - 基于 NLU/RAG 的旅行规划 Agent

    流程：
    1. 尝试调用 NLU 流式接口
    2. 成功：收集 chunks 用于流式输出，创建完整消息用于保存
    3. 失败：fallback 到 research-assistant

    Args:
        inputs: 当前输入，格式 {"messages": [HumanMessage(...)]}
        previous: 历史状态，格式 {"messages": [...]}
        config: 运行配置，包含 thread_id 等

    Returns:
        entrypoint.final:
            - value: 用于流式输出的 chunks
            - save: 用于持久化的完整消息

    Raises:
        ValueError: 输入无效
    """

    # ========== 1. 输入验证和预处理 ==========

    input_messages = inputs.get("messages", [])
    if not input_messages:
        logger.error("TravelPlanner: No messages in input")
        raise ValueError("No input message")

    last_message = input_messages[-1]
    if not isinstance(last_message, HumanMessage):
        logger.error(f"TravelPlanner: Last message is not HumanMessage: {type(last_message)}")
        raise ValueError("Invalid message type")

    user_input = str(last_message.content)

    # 构建完整的消息历史 (previous + inputs)
    all_messages: list[AnyMessage] = []
    if previous and previous.get("messages"):
        all_messages = list(previous["messages"])
    all_messages.extend(input_messages)

    # 获取配置
    session_id = config.get("configurable", {}).get("thread_id")

    logger.info(
        f"TravelPlanner: Processing input='{user_input[:50]}...', session_id={session_id}"
    )

    # ========== 2. 尝试调用 NLU 服务（流式） ==========

    try:
        full_content = ""
        chunks: list[AIMessageChunk] = []
        nlu_session_id = None
        nlu_status = None

        logger.info(f"TravelPlanner: Calling NLU service (streaming) with session_id={session_id}")

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
                    result = event.get("result")
                    logger.debug(f"TravelPlanner: NLU phase ended - {phase}, result={result}")

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
                        f"session_id={nlu_session_id}, status={nlu_status}, "
                        f"total_chunks={len(chunks)}, content_length={len(full_content)}"
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
            raise NLUServiceError("NLU returned empty content")

        # 检查是否需要追问 (status=incomplete)
        if nlu_status == "incomplete":
            logger.warning(
                "TravelPlanner: NLU returned incomplete status, reply contains follow-up questions"
            )

        # 创建完整的 AIMessage 用于保存到 checkpoint
        final_message = AIMessage(content=full_content)
        final_message = cast(AIMessage, add_timestamp_to_message(final_message))

        logger.info(
            f"TravelPlanner: Returning {len(chunks)} chunks for streaming, "
            f"1 complete message for checkpoint"
        )

        # ========== 3. 返回结果（使用 entrypoint.final 区分流式和保存） ==========

        return entrypoint.final(
            # value: 用于流式输出
            # LangGraph 会在 stream_mode=["messages"] 时逐个 yield 这些 chunks
            value={"messages": chunks},
            # save: 用于持久化到 checkpoint
            # 历史记录读取时只会看到这个完整的 AIMessage，不会看到 chunks
            save={"messages": all_messages + [final_message]},
        )

    # ========== 4. 异常处理和 Fallback ==========

    except (ServiceUnavailableError, NLUServiceError) as e:
        # NLU 服务失败，fallback 到 research-assistant
        logger.warning(
            f"TravelPlanner: NLU failed ({type(e).__name__}: {e}), "
            f"falling back to research-assistant"
        )

        try:
            # 延迟导入以避免循环导入
            from agents.agents import get_agent

            # 获取 research-assistant agent
            research_agent = get_agent("research-assistant")

            # 构建输入 (只传递当前 input，不包括历史)
            research_input = {"messages": input_messages}

            logger.info("TravelPlanner: Calling research-assistant as fallback")

            # 调用 research-assistant
            # 注意：使用 ainvoke 而不是 astream，因为我们需要等待完整结果
            # LangGraph 会根据 research_agent 的类型（Pregel 或 CompiledStateGraph）
            # 自动处理流式输出
            result = await research_agent.ainvoke(research_input, config)

            # 提取 research-assistant 的响应
            research_messages = result.get("messages", [])

            logger.info(
                f"TravelPlanner: Research-assistant returned {len(research_messages)} messages"
            )

            # 过滤掉输入消息（research_assistant 会返回完整的 messages，包括输入）
            # 我们只需要新生成的消息
            new_messages = research_messages[len(input_messages) :]

            # 返回 research-assistant 的结果
            # 注意：research-assistant 可能也返回 chunks，这里我们直接传递
            # 如果 research-assistant 已经是完整消息，value 和 save 相同也没问题
            return entrypoint.final(
                value={"messages": new_messages},
                save={"messages": all_messages + new_messages},
            )

        except Exception as fallback_error:
            logger.error(
                f"TravelPlanner: Fallback to research-assistant also failed - {fallback_error}",
                exc_info=True,
            )
            raise

    except Exception as e:
        # 其他未预期的错误
        logger.error(f"TravelPlanner: Unexpected error - {e}", exc_info=True)
        raise


# ========== 导出 ==========

# 保持与旧实现相同的导出名称，方便迁移
travel_planner = travel_planner_functional
