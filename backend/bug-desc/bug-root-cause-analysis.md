# Bug 根因分析报告

## 问题描述

用户输入提示词并收到返回消息后，历史记录中不会包含用户之前输入的提示词，只显示 AI 的回复。

## Bug 根本原因

### 核心问题

**LangGraph Functional API 的 `aget_state()` 返回的是 `entrypoint.final` 中 `value` 的内容，而不是 `save` 的内容！**

### 详细分析

在 `travel_planner_functional.py:167-174` 中：

```python
return entrypoint.final(
    # value: 用于流式输出 - 返回所有 AIMessageChunk
    value={"messages": chunks},  # ❌ 只包含 AI 的响应 chunks

    # save: 用于持久化到 checkpoint - 保存完整消息历史
    save={"messages": all_messages + [final_message]},  # ✅ 包含用户消息 + AI 响应
)
```

**数据流分析：**

1. **保存阶段（✅ 正确）：**
   - `save` 参数包含完整的消息历史：`[HumanMessage, AIMessage, ...]`
   - LangGraph checkpointer 成功将 `save` 的内容持久化到 PostgreSQL

2. **下次调用时（✅ 正确）：**
   - `previous` 参数成功接收到 `save` 的完整内容
   - Agent 内部能看到所有历史消息（包括 HumanMessage）

3. **读取历史记录时（❌ 错误）：**
   - `planner_routes.py:get_history()` 调用 `agent.aget_state(config=config)`
   - **`aget_state()` 返回的是 `value` 的内容，而不是 `save` 的内容**
   - 因此只能看到 `chunks`（AI 的响应），看不到用户消息

### 实验验证

通过调试脚本验证：

```python
# 测试结果：
# - save 包含: [HumanMessage("用户消息1"), AIMessage("AI 回复")]
# - previous 包含: [HumanMessage("用户消息1"), AIMessage("AI 回复")]  ✅
# - aget_state 返回: [AIMessage("这是 value 中的响应")]  ❌ 只有 value
```

**结论：`aget_state()` 在 Functional API 中返回的是 `value`，不是 `save`！**

## 解决方案

### 方案 A：修改 entrypoint.final 的 value 参数（推荐）

**核心思路：**让 `value` 也包含完整的消息历史，而不仅仅是 chunks。

**实现方式：**

修改 `travel_planner_functional.py:167-174`：

```python
# 创建完整的 final_message（合并所有 chunks）
final_message = AIMessage(content=full_content)
final_message = add_timestamp_to_message(final_message)

# ✅ 新方案：value 和 save 都包含完整的消息历史
return entrypoint.final(
    # value: 返回完整的消息历史（用于 aget_state 读取）
    value={"messages": all_messages + [final_message]},

    # save: 保存完整的消息历史（用于 previous 参数）
    save={"messages": all_messages + [final_message]},
)
```

**优点：**

- ✅ 修改最小，只需改 1 行代码
- ✅ `aget_state()` 能正确读取完整历史
- ✅ 不影响 `previous` 参数的行为
- ✅ 与 LangGraph Functional API 的设计一致

**缺点：**

- ⚠️ **流式输出会输出整个历史记录！**（严重问题）
- 在 `plan_stream` 中，`stream_mode=["messages"]` 会 yield `value` 中的所有消息
- 每次请求都会重复输出之前的所有历史消息

**判断：❌ 此方案不可行**（会破坏流式输出功能）

---

### 方案 B：使用 stream 的 messages 而不是 value（推荐）⭐

**核心思路：**区分流式输出和历史记录读取，流式时只输出新消息 chunks，读取历史时获取完整消息。

**问题分析：**

- `stream_mode=["messages"]` 会实时 yield agent 产生的**新消息**
- 这些新消息来自于节点的输出（可能是 value 或 save，取决于 LangGraph 的实现）
- 当前实现中，`value` 只包含 chunks，因此流式输出正常工作

**解决方法：**修改 `value` 为完整历史，但调整流式读取逻辑，只输出新产生的消息。

```python
# travel_planner_functional.py

# 方案 B-1: 记录之前的消息数量
previous_message_count = len(all_messages)

return entrypoint.final(
    # value: 包含完整历史（用于 aget_state）
    value={"messages": all_messages + [final_message]},

    # save: 同样包含完整历史（用于 previous）
    save={"messages": all_messages + [final_message]},

    # metadata: 记录新消息的起始位置
    # （如果 LangGraph 支持的话）
)
```

然后修改 `planner_routes.py:plan_stream`，只输出新消息：

```python
# planner_routes.py

async for stream_event in agent.astream(user_input, config=config, stream_mode=["messages"], subgraphs=True):
    if stream_mode == "messages":
        msg, metadata = event
        # 只输出新产生的消息（通过某种标记区分）
        if isinstance(msg, AIMessageChunk):
            # 流式输出 chunk
            yield f"data: {json.dumps({'type': 'token', 'delta': ...})}\n\n"
```

**判断：⚠️ 此方案需要深入了解 LangGraph 的流式机制**

---

### 方案 C：分离流式输出和完整消息（最佳方案）⭐⭐⭐

**核心思路：**

- `value` 返回 chunks 用于流式输出（保持现状）
- 在完整消息保存后，额外调用一次 agent 或使用其他机制更新 checkpoint

**实现方式 C-1：使用两次 entrypoint.final**

```python
# 方案 C-1 不可行，entrypoint.final 只能 return 一次
```

**实现方式 C-2：修改 get_history 的读取逻辑**

问题在于 `aget_state` 返回 `value`，那我们能否直接从 checkpointer 读取 `save` 的数据？

```python
# planner_routes.py:get_history

# ❌ 旧实现：使用 aget_state（返回 value）
state = await agent.aget_state(config=config)
messages = state.values.get("messages", [])

# ✅ 新实现：直接从 checkpointer 读取
# 但问题是：checkpointer 只有一个 state，它保存的是 save 的数据
# 而 aget_state 应该返回 save 的数据才对...

# 让我们测试一下 checkpointer 实际保存的是什么
```

**方案 C-2 的关键：测试 checkpointer 实际保存的数据**

让我重新测试，直接访问 checkpointer 查看保存的数据。

---

### 方案 D：使用 StateGraph 代替 Functional API（备选方案）

**核心思路：**回退到 StateGraph 模式，使用传统的节点返回方式。

**缺点：**

- ❌ 放弃了 Functional API 解决历史记录分块问题的优势
- ❌ 需要大量重构代码

**判断：❌ 不推荐**

---

## 下一步行动

1. **测试 checkpointer 实际保存的数据**：验证 checkpointer 中保存的是 `save` 的内容
2. **查找 LangGraph 文档**：了解如何从 checkpointer 直接读取数据
3. **实施方案 C-2**：绕过 `aget_state`，直接从 checkpointer 读取完整历史

## 临时解决方案

在找到最佳方案之前，可以使用以下临时方案：

**临时方案：在 get_history 时调用一次 agent.ainvoke 获取 previous**

```python
# planner_routes.py:get_history

# 创建一个临时的 agent 调用，利用 previous 参数获取完整历史
# （这个方案比较 hacky，但可以快速验证）

# 但这需要修改 agent 代码，增加一个"只读取历史"的模式
```

**更好的临时方案：记录用户输入到数据库**

在 `plan_stream` 中，将用户输入单独保存到数据库或 store 中，然后在 `get_history` 时从数据库读取并合并。

但这不是根本解决方案。

---

## 总结

- **Bug 根因**：`aget_state()` 返回 `value` 而不是 `save`
- **最佳方案**：方案 C - 直接从 checkpointer 读取或修改读取逻辑
- **需要验证**：checkpointer 实际保存的数据内容
