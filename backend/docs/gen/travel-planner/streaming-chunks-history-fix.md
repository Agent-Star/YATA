# 流式返回历史记录分块问题 - 长期解决方案

## 问题背景

详见 `backend/bug-desc/流式返回历史记录分块问题分析.md`

**核心问题**：Backend 的 travel_planner 在流式调用 NLU 时，将每个 AIMessageChunk 都保存到 checkpoint，导致历史记录被分成大量小块（每块 1-2 字符）。

**根本原因**：LangGraph 的 MessagesState 使用 `add_messages` reducer，会将节点返回的所有消息添加到状态中并保存到 checkpoint。

## 技术调研

### 1. LangGraph Functional API

**核心特性**：`entrypoint.final(value=..., save=...)`

- **value**: 返回给调用者的值，用于流式输出
- **save**: 保存到 checkpoint 的值，用于下次调用的 previous 参数

**适用场景**：需要区分"流式输出的值"和"持久化保存的值"

**现有案例**：`backend/src/agents/chatbot.py` 已使用 Functional API

```python
@entrypoint()
async def chatbot(inputs, *, previous, config):
    response = await model.ainvoke(messages)
    response = add_timestamp_to_message(response)

    return entrypoint.final(
        value={"messages": [response]},           # 返回给调用者
        save={"messages": messages + [response]}  # 保存到 checkpoint
    )
```

### 2. LangGraph 流式机制

**stream_mode=["messages"]**：

- LangGraph 会流式输出 `value` 中的 AIMessageChunk
- 当 LLM 生成 token 时，每个 token 作为 AIMessageChunk 被流式输出
- StateGraph 会在流式输出完成后，将所有消息保存到 checkpoint

**关键发现**：

- Functional API 的 `value` 参数支持返回 AIMessageChunk 列表
- LangGraph 会自动流式输出这些 chunks
- `save` 参数可以保存完整的 AIMessage，与 `value` 解耦

### 3. 系统架构分析

**AgentGraph 类型定义**（`agents/agents.py:28`）：

```python
AgentGraph = CompiledStateGraph | Pregel
```

- **Pregel**：Functional API 返回的类型（如 chatbot）
- **CompiledStateGraph**：StateGraph().compile() 返回的类型（如 travel_planner）

**travel_planner 当前架构**：

```
StateGraph (TravelPlannerState)
  ├─ call_nlu_service (节点)
  │   └─ 调用 NLU 流式接口，返回 {"messages": [chunk1, chunk2, ...]}  ❌
  ├─ fallback_to_research_assistant (节点)
  │   └─ 降级到 research-assistant
  └─ should_fallback (条件边)
```

**挑战**：travel_planner 是一个包含多个节点和条件边的复杂图，如何迁移到 Functional API？

## 解决方案

### 方案 A: 完全重构为 Functional API（推荐长期方案）

**核心思路**：将整个 travel_planner 改为单个 entrypoint 函数，内部处理 NLU 调用和 fallback 逻辑。

#### 实现步骤

##### Step 1: 创建新的 Functional API 实现

在 `backend/src/agents/travel_planner_functional.py` 创建新文件：

```python
from __future__ import annotations

import logging
from typing import cast

from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.func import entrypoint

from agents.agents import get_agent
from agents.timestamp import add_timestamp_to_message
from external_services import (
    NLUServiceError,
    ServiceUnavailableError,
    get_nlu_client,
)

logger = logging.getLogger(__name__)


@entrypoint()
async def travel_planner_functional(
    inputs: dict,
    *,
    previous: dict | None,
    config: RunnableConfig,
) -> entrypoint.final:
    """
    Travel Planner Agent (Functional API 实现)

    实现策略:
    1. 流式调用 NLU 服务，收集所有 chunks
    2. 如果成功，返回 chunks 用于流式输出，保存完整消息到 checkpoint
    3. 如果失败，fallback 到 research-assistant
    """

    # 获取用户输入
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
    all_messages = []
    if previous and previous.get("messages"):
        all_messages = previous["messages"]
    all_messages = all_messages + input_messages

    # 获取配置
    session_id = config.get("configurable", {}).get("thread_id")

    logger.info(f"TravelPlanner: Calling NLU service (streaming) with session_id={session_id}")

    # 尝试调用 NLU 服务
    try:
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
                    phase = event.get("phase")
                    logger.debug(f"TravelPlanner: NLU phase started - {phase}")

                elif event_type == "phase_end":
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
                    nlu_session_id = event.get("session_id")
                    nlu_status = event.get("status")
                    logger.info(
                        f"TravelPlanner: NLU streaming completed - "
                        f"session_id={nlu_session_id}, status={nlu_status}"
                    )
                    break

                elif event_type == "error":
                    error_message = event.get("message", "Unknown error")
                    logger.error(f"TravelPlanner: NLU returned error - {error_message}")
                    raise NLUServiceError(error_message)

        # 检查是否收到了完整的回复
        if not full_content:
            logger.warning("TravelPlanner: NLU returned empty content")
            raise NLUServiceError("NLU returned empty content")

        # 创建完整的 AIMessage 用于保存
        final_message = AIMessage(content=full_content)
        final_message = cast(AIMessage, add_timestamp_to_message(final_message))

        # 使用 entrypoint.final 区分流式输出和保存的值
        return entrypoint.final(
            # 流式输出：返回所有 chunks，LangGraph 会逐个流式输出
            value={"messages": chunks},

            # 保存到 checkpoint：只保存完整消息
            save={"messages": all_messages + [final_message]}
        )

    except (ServiceUnavailableError, NLUServiceError) as e:
        # NLU 失败，fallback 到 research-assistant
        logger.warning(f"TravelPlanner: NLU failed ({e}), falling back to research-assistant")

        # 获取 research-assistant agent
        research_agent = get_agent("research-assistant")

        # 构建输入
        research_input = {"messages": input_messages}

        # 调用 research-assistant (使用 ainvoke，让 LangGraph 自动处理流式)
        # 注意：research_agent 也可能是 Pregel 或 CompiledStateGraph
        result = await research_agent.ainvoke(research_input, config)

        # 提取 research-assistant 的响应
        research_messages = result.get("messages", [])

        # 返回 research-assistant 的结果
        # 注意：这里可能需要根据 research_agent 的返回值调整
        return entrypoint.final(
            value={"messages": research_messages},
            save={"messages": all_messages + research_messages}
        )

    except Exception as e:
        logger.error(f"TravelPlanner: Unexpected error - {e}", exc_info=True)
        raise
```

##### Step 2: 更新 agents 注册

在 `backend/src/agents/agents.py` 中：

```python
from agents.travel_planner_functional import travel_planner_functional

agents: dict[str, Agent] = {
    # ... 其他 agents ...

    "travel-planner": Agent(
        description="A travel planner powered by NLU/RAG, with fallback to research assistant.",
        graph=travel_planner_functional,  # 使用新的 Functional API 实现
    ),
}
```

##### Step 3: 测试和验证

1. **流式输出测试**：

   ```bash
   # 调用 /planner/plan/stream 端点
   # 验证：用户能实时看到逐 token 生成
   ```

2. **历史记录测试**：

   ```bash
   # 刷新页面，调用 /planner/history 端点
   # 验证：历史记录显示为单条完整消息，不再分块
   ```

3. **Fallback 测试**：

   ```bash
   # 停止 NLU 服务，触发 fallback
   # 验证：自动降级到 research-assistant，流式输出正常
   ```

##### Step 4: 清理旧代码

备份并移除 `backend/src/agents/travel_planner.py`（原 StateGraph 实现）。

#### 优点

- ✅ 完美解决问题 - 流式输出 chunks，只保存完整消息
- ✅ 符合 LangGraph 最佳实践
- ✅ 代码更简洁 - 单个函数，无需复杂的 StateGraph 结构
- ✅ 易于维护和扩展

#### 缺点

- ⚠️  需要重构整个 travel_planner - 工作量较大
- ⚠️  需要仔细处理 fallback 逻辑 - research_agent 的调用和流式输出
- ⚠️  可能影响其他依赖 travel_planner 的功能（需全面测试）

#### 风险评估

**中等风险**：

- Functional API 与 StateGraph 行为可能存在细微差异
- Fallback 到 research-assistant 的流式处理需要额外关注

**缓解措施**：

- 充分的单元测试和集成测试
- 保留旧代码作为备份，逐步迁移
- 先在开发环境验证，再部署到生产环境

---

### 方案 B: 自定义 Reducer（替代方案）

**核心思路**：保持 StateGraph 结构，但自定义 messages 的 reducer，自动合并连续的 AIMessageChunk。

#### 实现概要

在 `TravelPlannerState` 中使用自定义 reducer：

```python
from typing import Annotated
from langgraph.graph import add_messages

def merge_chunks_reducer(left: list[AnyMessage], right: list[AnyMessage]) -> list[AnyMessage]:
    """
    自定义 reducer：合并连续的 AIMessageChunk

    策略：
    - 如果 right 中有多个连续的 AIMessageChunk，合并为一个 AIMessage
    - 其他情况使用默认的 add_messages 行为
    """
    # 检测 right 是否全部是 AIMessageChunk
    all_chunks = all(isinstance(msg, AIMessageChunk) for msg in right)

    if all_chunks and len(right) > 1:
        # 合并所有 chunks
        merged_content = "".join(str(chunk.content) for chunk in right)
        first_chunk = right[0]

        merged_message = AIMessage(
            content=merged_content,
            additional_kwargs=getattr(first_chunk, "additional_kwargs", {}),
            response_metadata=getattr(first_chunk, "response_metadata", {}),
        )

        # 使用默认 add_messages 逻辑添加合并后的消息
        return add_messages(left, [merged_message])
    else:
        # 使用默认 add_messages 逻辑
        return add_messages(left, right)


class TravelPlannerState(TypedDict, total=False):
    # 使用自定义 reducer
    messages: Annotated[list[AnyMessage], merge_chunks_reducer]

    nlu_response: NLUResponse | None
    fallback_triggered: bool
    error_message: str | None
```

#### 优点

- ✅ 保持现有 StateGraph 结构 - 改动较小
- ✅ 不影响其他功能 - 只修改 state 定义

#### 缺点

- ⚠️  流式输出可能受影响 - reducer 在保存时执行，可能影响流式行为
- ⚠️  不是最优雅的方案 - 仍然在流式时创建大量 chunks
- ⚠️  可能与 LangGraph 的内部机制冲突

#### 评估

**不推荐**：自定义 reducer 可能与 LangGraph 的流式机制产生不可预期的交互。

---

### 方案 C: 后处理合并（临时方案）

见 `backend/bug-desc/流式返回历史记录分块问题分析.md` 中的方案 C。

**评估**：适合快速修复，但治标不治本，不作为长期方案。

---

## 推荐实施方案

### 阶段 1: 快速修复（方案 C）

**时间**：1-2 小时

**实施**：在 `planner_routes.py` 的 `get_history` 中添加 `merge_consecutive_chunks` 逻辑。

**目标**：立即解决用户痛点，保证历史记录可读。

### 阶段 2: 长期重构（方案 A）

**时间**：1-2 天

**实施**：

1. 创建 `travel_planner_functional.py`，实现 Functional API 版本
2. 充分测试流式输出、历史记录、fallback 功能
3. 更新 `agents.py` 注册
4. 部署到开发环境验证
5. 部署到生产环境，监控

**目标**：彻底解决问题，符合 LangGraph 最佳实践。

---

## 技术细节

### Functional API 关键点

#### 1. 流式输出机制

在 Functional API 中，`entrypoint.final` 的 `value` 参数返回的消息会被 LangGraph 流式输出：

```python
return entrypoint.final(
    value={"messages": [chunk1, chunk2, chunk3, ...]},  # 流式输出
    save={"messages": [complete_message]}               # 保存
)
```

**LangGraph 行为**：

- 在 `stream_mode=["messages"]` 时，逐个 yield `chunk1`, `chunk2`, `chunk3`, ...
- 流式输出完成后，将 `save` 中的值保存到 checkpoint

#### 2. 与其他 Agent 集成

Functional API 的 entrypoint 可以调用其他 agent（无论是 Pregel 还是 CompiledStateGraph）：

```python
@entrypoint()
async def my_agent(inputs, *, previous, config):
    try:
        # 主逻辑
        result = await primary_service()
        return entrypoint.final(value=result, save=result)
    except Exception:
        # Fallback
        other_agent = get_agent("other-agent")
        result = await other_agent.ainvoke(inputs, config)
        return entrypoint.final(
            value=result.get("messages"),
            save={"messages": all_messages + result.get("messages")}
        )
```

#### 3. 消息历史管理

Functional API 通过 `previous` 参数访问历史：

```python
@entrypoint()
async def my_agent(inputs, *, previous, config):
    # 构建完整历史
    all_messages = []
    if previous and previous.get("messages"):
        all_messages = previous["messages"]
    all_messages = all_messages + inputs.get("messages", [])

    # ... 处理 ...

    return entrypoint.final(
        value={"messages": new_messages},
        save={"messages": all_messages + new_messages}
    )
```

---

## 测试计划

### 单元测试

在 `backend/tests/agents/test_travel_planner_functional.py`：

```python
import pytest
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

from agents.travel_planner_functional import travel_planner_functional


@pytest.mark.asyncio
async def test_streaming_output():
    """测试流式输出"""
    config = {
        "configurable": {
            "thread_id": "test-thread-1",
        }
    }

    inputs = {"messages": [HumanMessage(content="我想去北京旅游3天")]}

    chunks = []
    async for mode, chunk in travel_planner_functional.astream(
        inputs, config=config, stream_mode=["messages"]
    ):
        if mode == "messages":
            chunks.append(chunk)

    # 验证：收到多个 AIMessageChunk
    assert len(chunks) > 1
    assert all(chunk.__class__.__name__ == "AIMessageChunk" for chunk in chunks)


@pytest.mark.asyncio
async def test_saved_complete_message():
    """测试保存的是完整消息"""
    checkpointer = InMemorySaver()
    config = {
        "configurable": {
            "thread_id": "test-thread-2",
        }
    }

    inputs = {"messages": [HumanMessage(content="我想去上海旅游")]}

    # 执行
    result = await travel_planner_functional.ainvoke(inputs, config=config)

    # 获取保存的状态
    state = await travel_planner_functional.aget_state(config=config)
    messages = state.values.get("messages", [])

    # 验证：最后一条是 AIMessage，不是 AIMessageChunk
    assert len(messages) == 2  # HumanMessage + AIMessage
    assert messages[-1].__class__.__name__ == "AIMessage"
    assert len(messages[-1].content) > 0


@pytest.mark.asyncio
async def test_fallback_to_research_assistant():
    """测试 fallback 到 research-assistant"""
    # 模拟 NLU 服务不可用
    # ...

    # 验证：调用了 research-assistant
    # 验证：流式输出正常
    pass
```

### 集成测试

在 `backend/tests/integration/test_planner_routes.py`：

```python
@pytest.mark.asyncio
async def test_streaming_endpoint():
    """测试 /planner/plan/stream 端点"""
    # 调用流式端点
    # 验证：收到 SSE 事件流
    # 验证：事件包含 token delta
    pass


@pytest.mark.asyncio
async def test_history_endpoint():
    """测试 /planner/history 端点"""
    # 先调用流式端点
    # 再调用历史记录端点
    # 验证：历史记录中只有一条完整消息，不是多个 chunks
    pass
```

---

## 部署计划

### 1. 开发环境验证（1 天）

- 部署新代码到开发环境
- 运行所有测试
- 手动测试流式输出和历史记录
- 性能监控

### 2. 生产环境灰度发布（3 天）

- 部署到生产环境
- 使用 feature flag 控制，仅对部分用户启用
- 监控错误率、响应时间、用户反馈
- 逐步扩大用户范围

### 3. 全量发布（1 天）

- 对所有用户启用新实现
- 移除旧代码
- 更新文档

---

## 风险和缓解措施

### 风险 1: Functional API 与 StateGraph 行为差异

**缓解**：

- 充分的单元测试和集成测试
- 在开发环境充分验证
- 灰度发布，逐步扩大用户范围

### 风险 2: Fallback 逻辑可能影响流式输出

**缓解**：

- 单独测试 fallback 场景
- 确保 research-assistant 的流式输出正常工作

### 风险 3: 性能影响

**缓解**：

- 性能监控和基准测试
- 对比新旧实现的响应时间

---

## 后续优化

### 1. 统一所有 Agent 的流式实现

将其他使用 StateGraph 的 agent（如 research-assistant）也迁移到 Functional API，统一代码风格。

### 2. 改进 NLU 流式协议

考虑在 NLU 的流式事件中添加更多元信息，如：

- 当前阶段进度
- 预估完成时间
- 中间结果（如 intent 识别结果）

### 3. Frontend 优化

根据流式事件的 phase 信息，在 Frontend 显示不同的加载状态和进度提示。

---

## 参考资料

- [LangGraph Functional API 官方文档](https://docs.langchain.com/oss/python/langgraph/use-functional-api)
- [LangGraph entrypoint.final 参考](https://reference.langchain.com/python/langgraph/func/)
- [Backend chatbot.py 实现](backend/src/agents/chatbot.py)
- [问题分析文档](backend/bug-desc/流式返回历史记录分块问题分析.md)

---

## 总结

**推荐方案**：方案 A - 完全重构为 Functional API

**实施策略**：

1. 短期：使用方案 C 快速修复（1-2 小时）
2. 长期：实施方案 A 彻底解决（1-2 天）

**预期效果**：

- ✅ 流式输出正常 - 用户实时看到逐 token 生成
- ✅ 历史记录正确 - 显示为单条完整消息
- ✅ 代码更优雅 - 符合 LangGraph 最佳实践
- ✅ 易于维护 - 单个函数，逻辑清晰

**下一步行动**：

1. 复审本方案，确认技术细节
2. 实施方案 C（快速修复）
3. 开始实施方案 A（长期重构）
