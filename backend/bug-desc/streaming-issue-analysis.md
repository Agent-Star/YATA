# 流式输出失败问题分析报告

## 问题描述

修复历史记录bug后，NLU服务的流式输出失败：

- 日志显示收到 4147 个 chunks
- 但前端无法实时渲染，只能在最后一次性显示
- Apifox 测试显示没有任何 `token` 事件，只有最后的 `end` 事件

## 根本原因

### 修改前后对比

**修改前（有历史记录bug，但流式正常）：**

```python
# travel_planner_functional.py:170
return entrypoint.final(
    value={"messages": chunks},  # ✅ 返回 4147 个 AIMessageChunk
    save={"messages": all_messages + [final_message]},
)
```

**修改后（历史记录正常，但流式失败）：**

```python
# travel_planner_functional.py:170
return entrypoint.final(
    value={"messages": all_messages + [final_message]},  # ❌ 只返回完整的 AIMessage
    save={"messages": all_messages + [final_message]},
)
```

### 流式输出机制

在 `planner_routes.py:231-249`，流式输出的处理逻辑：

```python
async for stream_event in agent.astream(
    user_input, config=config, stream_mode=["messages"], subgraphs=True
):
    ...
    if stream_mode == "messages":
        msg, _ = event
        if isinstance(msg, AIMessageChunk):  # ⚠️ 只处理 AIMessageChunk
            content = remove_tool_calls(msg.content)
            if content:
                yield f"data: {json.dumps({'type': 'token', 'delta': ...})}\n\n"
```

**关键点：**

1. `planner_routes.py:246` 只处理 `isinstance(msg, AIMessageChunk)`
2. 修改后，`value` 包含的是 `AIMessage`（完整消息），不是 `AIMessageChunk`
3. 因此所有消息都被跳过，没有任何 token 输出

### 为什么 fallback 时流式正常？

**Fallback 调用的是 `research_assistant`：**

- `research_assistant` 使用 **StateGraph**（不是 Functional API）
- StateGraph 的流式机制不同，LLM 在生成过程中会自动产生 AIMessageChunk
- LangGraph 会捕获这些中间状态并流式输出

**关键区别：**

- **Functional API**: 开发者需要显式控制 `value` 返回什么
- **StateGraph**: LangGraph 自动捕获节点执行过程中的中间状态

## 数据流分析

### 修改后的完整流程

```
1. 用户发送消息
   ↓
2. travel_planner_functional 执行
   - 调用 NLU 流式接口
   - 逐个接收 4147 个 token
   - 收集到 chunks 列表（4147 个 AIMessageChunk）
   ↓
3. 创建 final_message
   - AIMessage(content=full_content)  # 完整内容 6372 字符
   ↓
4. 返回 entrypoint.final
   - value={"messages": all_messages + [final_message]}
   - 注意：chunks 被丢弃了！没有在 value 中返回
   ↓
5. LangGraph 流式处理
   - stream_mode=["messages"] 只会 yield value 中的消息
   - value 中只有完整的 AIMessage，没有 chunks
   ↓
6. planner_routes.py 处理流式事件
   - 检查 isinstance(msg, AIMessageChunk) → False
   - 跳过所有消息，不输出任何 token
   ↓
7. 最后发送 end 事件
   - 用户只能看到 end 事件，看不到任何 token
```

### 为什么之前没测出来？

在我的测试环境中：

- 可能测试的是 fallback 场景（调用 research_assistant）
- 或者测试的是简单的 chatbot（没有 chunks 的场景）
- 没有真实调用 NLU 服务进行端到端测试

## 解决方案

### 核心挑战

我们面临一个两难问题：

1. **流式输出需要**：`value` 返回 `chunks`（多个 AIMessageChunk）
2. **历史记录需要**：`value` 返回完整历史（包括 HumanMessage）

**这两个需求是冲突的！**

### 可行方案

#### 方案 A：在 value 中同时返回历史和 chunks ⭐⭐⭐

```python
return entrypoint.final(
    value={"messages": all_messages + chunks},  # 历史 + chunks
    save={"messages": all_messages + [final_message]},  # 历史 + 完整消息
)
```

**优点：**

- ✅ 流式输出正常（包含 chunks）
- ✅ 历史记录完整（包含 all_messages）
- ✅ 修改最小

**缺点：**

- ⚠️ `aget_state` 会读取到 chunks，而不是完整消息
- ⚠️ 历史记录可能显示为多个小块（回到了之前的分块问题！）

**判断：❌ 此方案会回到原始的分块问题**

---

#### 方案 B：修改 get_history，不使用 aget_state ⭐⭐⭐⭐

**核心思路：**

- 保持 `value={"messages": chunks}`（流式输出正常）
- 修改 `get_history` 的实现，通过其他方式获取完整历史（从 `save` 中读取）

**实现方式 B-1：添加辅助 entrypoint**

创建一个专门用于读取历史的 entrypoint：

```python
# travel_planner_functional.py

@entrypoint()
async def get_history_helper(
    inputs: dict,
    *,
    previous: dict | None,
    config: RunnableConfig,
) -> entrypoint.final:
    """
    辅助函数：用于获取完整的历史记录
    利用 previous 参数能正确获取 save 内容的特性
    """
    if previous and previous.get("messages"):
        messages = previous["messages"]
    else:
        messages = []

    # 直接返回 previous 中的消息（来自 save）
    return entrypoint.final(
        value={"messages": messages},
        save=previous if previous else {"messages": []},
    )
```

然后在 `planner_routes.py:get_history` 中使用：

```python
# planner_routes.py

from agents.travel_planner_functional import get_history_helper

@planner_router.get("/history", response_model=HistoryResponse)
async def get_history(...):
    # ❌ 旧实现
    # state = await agent.aget_state(config=config)
    # messages = state.values.get("messages", [])

    # ✅ 新实现：通过辅助函数获取完整历史
    result = await get_history_helper.ainvoke(
        {"messages": []},  # 空输入
        config=config
    )
    messages = result.get("messages", [])

    # 后续处理保持不变
    ...
```

**优点：**

- ✅ 流式输出正常（value 仍然返回 chunks）
- ✅ 历史记录完整（通过 previous 参数获取）
- ✅ 不会回到分块问题
- ✅ 利用了 LangGraph 的设计（previous 返回 save 的内容）

**缺点：**

- ⚠️ 需要额外调用一次 agent（性能开销小）
- ⚠️ 增加了一个辅助函数

---

#### 方案 C：修改 planner_routes.py 的流式逻辑

**核心思路：**

- 同时处理 AIMessageChunk 和 AIMessage
- 当收到完整的 AIMessage 时，手动分块输出

```python
# planner_routes.py:243-249

if stream_mode == "messages":
    msg, _ = event
    if isinstance(msg, AIMessageChunk):
        # 处理 chunk
        content = remove_tool_calls(msg.content)
        if content:
            yield f"data: {json.dumps({'type': 'token', 'delta': ...})}\n\n"
    elif isinstance(msg, AIMessage):
        # ⚠️ 收到完整消息，手动分块输出
        content = str(msg.content)
        # 但这样无法实现真正的流式输出！
        yield f"data: {json.dumps({'type': 'token', 'delta': content})}\n\n"
```

**判断：❌ 此方案无法实现真正的流式输出**

---

## 推荐方案

**方案 B（添加辅助 entrypoint）是最佳选择：**

1. **流式输出正常**：`value` 返回 chunks
2. **历史记录完整**：通过 `previous` 参数获取完整历史
3. **不破坏现有逻辑**：最小化修改
4. **利用 LangGraph 设计**：previous 正确返回 save 的内容

### 实施步骤

1. 在 `travel_planner_functional.py` 中添加 `get_history_helper` 函数
2. 恢复 `travel_planner_functional` 的 `value` 为返回 `chunks`
3. 修改 `planner_routes.py:get_history` 使用 `get_history_helper`
4. 测试验证

---

## 总结

- **问题根因**：修改 `value` 为完整历史后，chunks 被丢弃，流式输出失败
- **核心挑战**：流式输出需要 chunks，历史记录需要完整消息，两者冲突
- **最佳方案**：保持 value 返回 chunks，通过辅助函数获取完整历史
- **关键洞察**：`aget_state` 返回 value，`previous` 返回 save，利用这个差异解决问题
