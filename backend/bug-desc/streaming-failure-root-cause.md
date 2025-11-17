# Backend 流式输出失败根因分析

## 问题定位

**问题出在：backend 模块**
**模块分支：feat/backend**

## 根本原因

### 问题描述

Backend 的 `travel_planner_functional.py` 在接收 NLU 的流式事件时，**只是将 chunks 收集到列表中，并没有实时转发**。整个 `async for` 循环必须完全执行完毕后，才会返回结果，导致流式输出失效。

### 代码分析

**文件：`src/agents/travel_planner_functional.py:100-137`**

```python
async with get_nlu_client() as nlu_client:
    async for event in nlu_client.call_nlu_stream(
        text=user_input,
        session_id=session_id,
    ):
        event_type = event.get("type")

        if event_type == "token":
            delta = event.get("delta", "")
            full_content += delta

            # ❌ 问题：只是收集到列表中，没有立即 yield
            chunk = AIMessageChunk(content=delta)
            chunk = cast(AIMessageChunk, add_timestamp_to_message(chunk))
            chunks.append(chunk)  # 收集但不转发

        elif event_type == "end":
            # 只有接收完所有 chunks 后才 break
            break

# 只有在循环结束后才返回
return entrypoint.final(
    value={"messages": chunks},  # 此时才返回所有 chunks
    save={"messages": all_messages + [final_message]},
)
```

### 问题流程

```
1. NLU 服务开始流式生成 token
   ↓
2. Backend 接收第 1 个 token
   - 创建 AIMessageChunk
   - 添加到 chunks 列表 ❌ 不转发
   ↓
3. Backend 接收第 2 个 token
   - 创建 AIMessageChunk
   - 添加到 chunks 列表 ❌ 不转发
   ↓
   ... (重复 4147 次) ...
   ↓
4. NLU 发送 end 事件
   - Backend 跳出循环
   ↓
5. Backend 返回 entrypoint.final
   - LangGraph 开始处理 chunks
   - 此时才开始流式输出
   ↓
6. 前端一次性收到所有 chunks
   - 无法实时渲染
```

### 为什么 Fallback 时流式正常？

Fallback 调用的是 `research-assistant`，它使用 **StateGraph**：
- StateGraph 会捕获 LLM 调用过程中的**中间状态**
- LangGraph 自动拦截 LLM 的流式输出
- 不需要手动收集 chunks

**Functional API 的限制：**
- 函数必须**完全执行完毕**后才能返回
- 返回的 chunks 才会被 LangGraph 处理
- 无法实现真正的实时流式输出

## 解决方案

### 核心挑战

Functional API 的设计限制导致：
- **无法在函数执行过程中流式输出**
- 必须等待函数返回后，LangGraph 才开始处理 value
- 与 NLU 的流式接口不兼容

### 方案 A：绕过 agent.astream，直接流式转发 ⭐⭐⭐⭐⭐

**核心思路：**
- 不依赖 LangGraph 的流式机制
- 在 `planner_routes.py:plan_stream` 中直接调用 NLU
- 边接收边转发，实现真正的流式输出

**实现方式：**

修改 `planner_routes.py:plan_stream`，不再调用 `agent.astream`，而是直接调用 NLU：

```python
async def generate_events() -> AsyncGenerator[str, None]:
    try:
        # 获取用户的主 Thread ID
        thread_id = await get_or_create_main_thread(current_user, session)

        # 构建配置
        config = RunnableConfig(configurable={
            "thread_id": thread_id,
            "user_id": str(current_user.id)
        })

        # 创建带时间戳的 HumanMessage (用于后续保存)
        input_message = create_timestamped_message(request.prompt, HumanMessage)

        # ========== 直接调用 NLU，边接收边转发 ==========

        full_content = ""
        nlu_session_id = None
        nlu_status = None

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

                elif event_type == "end":
                    nlu_session_id = event.get("session_id")
                    nlu_status = event.get("status")
                    break

        # ========== 保存完整历史到 checkpoint ==========

        # 调用 agent 保存历史（不使用流式）
        agent = get_agent(DEFAULT_AGENT)

        # 创建完整的 AIMessage
        final_message = AIMessage(content=full_content)
        final_message = add_timestamp_to_message(final_message)

        # 使用 ainvoke 保存（不使用 astream）
        await agent.ainvoke(
            {"messages": [input_message]},  # 用户输入
            config=config
        )
        # 注意：agent.ainvoke 只会调用 NLU（已经有结果了），
        # 我们需要手动保存 final_message

        # 发送结束事件
        message_id = f"msg-{id(input_message)}"
        yield f"data: {json.dumps({'type': 'end', 'messageId': message_id, 'metadata': {}})}\n\n"
        yield "data: [DONE]\n\n"

    except Exception as e:
        logger.error(f"流式规划失败: {e}")
        yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
        yield "data: [DONE]\n\n"
```

**问题：** 这个方案绕过了 agent，需要手动保存历史记录。

---

### 方案 B：修改 travel_planner 为无状态转发 ⭐⭐⭐⭐

**核心思路：**
- 将 `travel_planner_functional` 改为简单的转发函数
- 在 `planner_routes.py` 中处理流式输出和历史保存

**实现步骤：**

1. **简化 `travel_planner_functional`**：只负责调用 NLU，不收集 chunks
2. **在 `planner_routes.py` 中直接调用 NLU**：实现真正的流式转发
3. **手动保存历史记录**：使用单独的逻辑保存到 checkpoint

---

### 方案 C：使用 StateGraph 替代 Functional API ⭐⭐

**核心思路：**
- 将 `travel_planner` 改回 StateGraph
- 但使用特殊的消息合并逻辑避免历史记录分块

**缺点：**
- 需要大量重构
- 可能回到之前的分块问题

---

## 推荐方案

**方案 B（修改为无状态转发）是最佳选择：**

1. **流式输出正常**：直接转发 NLU 的 token
2. **历史记录完整**：手动保存到 checkpoint
3. **代码清晰**：职责分离，易于维护
4. **兼容性好**：不影响其他 agent

### 实施步骤

1. 在 `planner_routes.py` 中直接调用 NLU 并流式转发
2. 流式完成后，手动保存历史记录到 checkpoint
3. 移除 `travel_planner_functional` 对流式的依赖

---

## 实际实施方案

**已实施：方案 B 的优化版本**

### 实施详情

#### 1. 创建历史保存辅助函数

**文件：`src/agents/travel_planner_functional.py`**

添加了 `save_history_helper` 函数（第 273-308 行）：

```python
@entrypoint()
async def save_history_helper(
    inputs: dict[str, list[AnyMessage]],
    *,
    previous: dict[str, list[AnyMessage]] | None,
    config: RunnableConfig,
) -> entrypoint.final:
    """
    辅助函数：用于保存消息到历史记录

    用于在流式输出完成后，将完整的消息历史保存到 checkpoint。
    不进行任何 NLU 调用，只负责持久化。
    """
    new_messages = inputs.get("messages", [])

    if previous and previous.get("messages"):
        all_messages = previous["messages"] + new_messages
    else:
        all_messages = new_messages

    logger.info(f"SaveHistoryHelper: Saved {len(new_messages)} new messages, total {len(all_messages)} messages")

    return entrypoint.final(
        value={"messages": all_messages},
        save={"messages": all_messages},
    )
```

**关键特性：**
- 不调用 NLU（避免重复请求）
- 接收已生成的消息并直接保存
- 使用 `previous` 参数合并历史
- 确保流式输出与保存内容一致

#### 2. 注册辅助 Agent

**文件：`src/agents/agents.py`**

- 导入 `save_history_helper`（第 16 行）
- 注册为可用 agent（第 53-56 行）：

```python
"save-history-helper": Agent(
    description="Helper to save messages to checkpoint without processing.",
    graph=save_history_helper,
),
```

**重要性：** 注册后才能获得 checkpointer 注入，才能正确保存到数据库。

#### 3. 修改流式输出逻辑

**文件：`src/service/planner_routes.py`**

**修改 1：添加导入（第 23、25 行）**
```python
from agents.timestamp import add_timestamp_to_message, create_timestamped_message
from external_services.nlu_client import get_nlu_client
```

**修改 2：重写 `generate_events()` 函数（第 202-279 行）**

核心流程：

```python
# 1. 直接调用 NLU，边接收边转发
full_content = ""
async with get_nlu_client() as nlu_client:
    async for event in nlu_client.call_nlu_stream(
        text=request.prompt,
        session_id=thread_id,
    ):
        if event.get("type") == "token":
            delta = event.get("delta", "")
            full_content += delta
            # ✅ 立即转发给前端
            yield f"data: {json.dumps({'type': 'token', 'delta': delta})}\n\n"
        elif event.get("type") == "end":
            break

# 2. 创建完整的 AIMessage
final_message = AIMessage(content=full_content)
final_message = add_timestamp_to_message(final_message)

# 3. 使用 save-history-helper 保存（不会再次调用 NLU）
save_helper = get_agent("save-history-helper")
await save_helper.ainvoke(
    {"messages": [input_message, final_message]},
    config=config
)
```

**优势：**
1. ✅ **真正的流式输出**：直接从 NLU 转发，无需等待函数返回
2. ✅ **避免重复调用**：只调用 NLU 一次
3. ✅ **内容一致性**：流式输出和保存的内容完全一致
4. ✅ **历史完整性**：正确保存用户输入和 AI 响应

---

## NLU 模块分析

NLU 模块的实现是**正确的**：

### 验证结果

1. **`fastapi_server.py`**：正确实现 SSE 流式输出
2. **`generate_itinerary_stream`**：正确逐 token yield
3. **`ask_text_stream`**：正确调用 LLM 流式 API

**NLU 模块无需修改。**

---

## 总结

- **问题模块**：backend
- **问题文件**：`src/agents/travel_planner_functional.py`
- **根本原因**：Functional API 无法实现真正的流式输出
- **解决方案**：绕过 LangGraph，直接在 `planner_routes.py` 中流式转发
- **NLU 模块**：实现正确，无需修改

---

**修复日期**：2025-11-18
**问题定位**：Backend Functional API 的设计限制
**影响范围**：只影响 NLU 流式输出，Fallback 正常
**实施状态**：✅ 已完成实施

---

## 修改文件清单

### 修改的文件

1. **`src/agents/travel_planner_functional.py`**
   - 添加 `save_history_helper` 函数（第 273-308 行）
   - 提供无副作用的历史保存功能

2. **`src/agents/agents.py`**
   - 导入 `save_history_helper`（第 16 行）
   - 注册 `save-history-helper` agent（第 53-56 行）

3. **`src/service/planner_routes.py`**
   - 添加必要导入：`add_timestamp_to_message`, `get_nlu_client`（第 23、25 行）
   - 重写 `generate_events()` 函数以直接调用 NLU（第 202-279 行）
   - 使用 `save-history-helper` 保存历史（第 256-260 行）

### 未修改的文件

- **`travel_planner_functional.py` 主逻辑**：保持不变，作为 fallback 路径
- **NLU 模块**：无需任何修改
- **其他 agent**：不受影响

---

## 预期效果

### ✅ 应该正常工作

1. **流式输出**
   - 用户输入后立即开始逐 token 渲染
   - 响应速度与 NLU 生成速度同步
   - 前端实时显示内容

2. **历史记录**
   - 用户消息正确显示
   - AI 响应完整保存
   - 多轮对话上下文正确

3. **功能完整性**
   - Fallback 机制仍然正常
   - 收藏功能可用
   - 历史记录查询正确

### 🔍 需要验证

1. **性能表现**
   - 延迟是否降低
   - 内存占用是否正常
   - 数据库写入是否成功

2. **边界情况**
   - NLU 服务异常时的处理
   - 超长对话的性能
   - 并发请求的稳定性

---

## 后续优化建议

1. **添加错误重试机制**：当 NLU 调用失败时自动重试或 fallback
2. **添加缓存层**：对相同问题的响应进行缓存，减少 NLU 调用
3. **监控和日志**：添加详细的性能监控和调用链追踪
4. **单元测试**：为新的 `save_history_helper` 添加测试用例

