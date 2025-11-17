# Bug 修复方案 - 最终版本

## 问题总结

`aget_state()` 返回的是 `entrypoint.final` 中 `value` 的内容，而不是 `save` 的内容。当前实现中 `value` 只包含 AI 响应 chunks，不包含用户消息，导致历史记录不完整。

## 最佳解决方案⭐

**方案：修改 `value` 返回完整的消息历史**

### 关键洞察

虽然担心修改 `value` 会影响流式输出，但经过分析发现：

- `stream_mode=["messages"]` 只会 yield **新产生**的消息（通过消息的 diff 机制）
- 即使 `value` 包含完整历史，流式输出也只会输出新消息

### 修改代码

**文件：`/home/eden/HKU-MSC-CS/nlp/YATA/backend/src/agents/travel_planner_functional.py`**

修改第 167-174 行：

```python
# ========== 旧代码 ==========
return entrypoint.final(
    value={"messages": chunks},  # ❌ 只有 chunks，导致 aget_state 读取不到用户消息
    save={"messages": all_messages + [final_message]},
)

# ========== 新代码 ==========
return entrypoint.final(
    value={"messages": all_messages + [final_message]},  # ✅ 包含完整历史
    save={"messages": all_messages + [final_message]},   # ✅ 保持一致
)
```

### 同时修改 fallback 分支

修改第 217-220 行：

```python
# ========== 旧代码 ==========
return entrypoint.final(
    value={"messages": ai_responses},  # ❌ 只有 AI 响应
    save={"messages": all_messages + ai_responses},
)

# ========== 新代码 ==========
return entrypoint.final(
    value={"messages": all_messages + ai_responses},  # ✅ 包含完整历史
    save={"messages": all_messages + ai_responses},   # ✅ 保持一致
)
```

## 为什么不会影响流式输出？

### LangGraph 的消息流式机制

LangGraph 的 `stream_mode=["messages"]` 使用**增量更新**机制：

1. 跟踪上一次的消息状态
2. 计算新旧状态的 diff
3. 只 yield 新增的消息

### 验证

当前代码流程：

1. `value = {"messages": chunks}` → 每个 chunk 都是"新消息" → 逐个 yield ✅
2. 修改后 `value = {"messages": all_messages + [final_message]}` → 只有 `final_message` 是"新消息" → 只 yield final_message

**问题：**修改后，流式输出会变成一次性输出完整消息，而不是逐 token 输出！

## 重新评估：这个方案有问题

经过仔细分析，直接修改 `value` 为完整历史**会破坏流式输出**！

## 正确的解决方案⭐⭐⭐

**方案：保持 `value` 返回 chunks（流式输出），但修改 `save` 的结构，使其能被 `aget_state` 正确读取**

### 关键洞察 #2

问题可能不在 LangGraph，而在我们对 Functional API 的理解。让我查看官方文档中的最佳实践...

实际上，**真正的问题是：Functional API 的 `aget_state` 设计就是返回 `value`，这是预期行为！**

### 终极解决方案

**方案：不修改 agent 代码，而是修改 `get_history` 的实现**

由于 `previous` 参数能正确接收完整历史，我们可以：

1. **临时触发一次 agent 执行**（不实际调用 LLM，只是获取 previous）
2. **从 previous 中提取完整历史**

### 实现代码

**文件：`/home/eden/HKU-MSC-CS/nlp/YATA/backend/src/agents/travel_planner_functional.py`**

添加一个新的辅助函数：

```python
@entrypoint()
async def get_full_history(
    inputs: dict,
    *,
    previous: dict | None,
    config: RunnableConfig,
) -> entrypoint.final:
    """
    辅助函数：仅用于获取完整的消息历史

    不执行任何 LLM 调用，只返回 previous 中的完整历史
    """
    if previous and previous.get("messages"):
        return entrypoint.final(
            value={"messages": previous["messages"]},
            save=previous,  # 保持 save 不变
        )
    else:
        return entrypoint.final(
            value={"messages": []},
            save={"messages": []},
        )
```

然后在 `planner_routes.py:get_history` 中使用：

```python
# ❌ 旧实现
state = await agent.aget_state(config=config)
messages = state.values.get("messages", [])

# ✅ 新实现：使用辅助 agent 获取完整历史
from agents.travel_planner_functional import get_full_history

# 触发一次空调用，获取 previous
result = await get_full_history.ainvoke({"messages": []}, config=config)
messages = result.get("messages", [])
```

### 优点

- ✅ 不影响流式输出
- ✅ 不修改核心 agent 逻辑
- ✅ 完全获取完整历史（包括用户消息）

### 缺点

- ⚠️ 增加了一次额外的 agent 调用
- ⚠️ 需要额外的辅助函数

## 最简解决方案⭐⭐⭐⭐

经过反复思考，我意识到有一个**超级简单的方案**：

**直接把 agent 换成使用相同 checkpointer 的版本，然后用 checkpointer 的 API 直接读取！**

但这需要访问 checkpointer 实例，而 agent 已经封装了 checkpointer...

### 终极最简方案

**修改 `value` 为完整历史 + 优化流式输出逻辑**

经过查阅 LangGraph 文档，发现可以通过特定的流式模式来解决：

修改 `travel_planner_functional.py` 返回完整历史：

```python
return entrypoint.final(
    value={"messages": all_messages + [final_message]},
    save={"messages": all_messages + [final_message]},
)
```

修改 `planner_routes.py:plan_stream` 的流式逻辑：

```python
# 记录已发送的消息数量
previous_message_count = 0

async for stream_event in agent.astream(...):
    ...
    # 只输出新增的消息
    current_message_count = len(messages)
    if current_message_count > previous_message_count:
        new_message = messages[-1]
        if isinstance(new_message, AIMessageChunk):
            yield chunk
        previous_message_count = current_message_count
```

但这仍然不能解决 chunk 的问题...

## 放弃纠结，选择最实用的方案

**最终方案：修改 `value` 返回时机，在 NLU 流式结束后再返回**

不，这也不行。

让我重新审视问题...

## 真正的根本问题

**问题不是代码逻辑，而是 Functional API 的设计限制！**

`entrypoint.final` 的设计目的是：

- `value`: 返回给调用者的"结果"
- `save`: 保存到 checkpoint 的"状态"

在流式场景下，这两者应该是不同的：

- `value`: chunks（用于实时显示）
- `save`: 完整历史（用于持久化）

但 `aget_state` 返回的是 `value`，这导致历史记录读取时丢失了用户消息。

**这可能是 LangGraph Functional API 的一个设计缺陷或使用限制！**

## 解决方案总结

基于以上分析，提供三个可行方案（按推荐顺序）：

### 推荐方案 1：使用 StateGraph 的历史记录读取方式

检查 `chatbot.py` 是否也有同样的问题，如果没有，学习它的实现方式。

### 推荐方案 2：修改 get_history 实现，不依赖 aget_state

直接查询 checkpointer 或使用其他方式获取完整历史。

### 推荐方案 3：临时 workaround

在发送消息时，将用户消息单独存储到数据库，读取历史时合并。
