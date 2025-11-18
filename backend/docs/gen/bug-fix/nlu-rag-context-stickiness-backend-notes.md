# Backend 层面对 NLU-RAG 上下文粘滞问题的改进建议

## 问题概述

本文档是针对 NLU-RAG 上下文粘滞 bug 在 Backend 层面的分析和改进建议。

**相关文档**:

- NLU 模块的主要分析和解决方案: `/algorithms/NLU/docs/gen/bug-fix/context-stickiness-analysis-and-fix.md`
- 问题复现数据: `/cross-issues/history-dump.json`

**结论**: 经过分析，该 bug 的**根本原因在 NLU 模块**，Backend 层面不是主要问题源。但 Backend 仍有一些可选的改进空间。

---

## Backend 当前实现分析

### 1. 历史消息管理

**位置**: `src/service/planner_routes.py` 第 234 行附近

**当前实现**:

```python
async for event in nlu_client.call_nlu_stream(
    text=request.prompt,
    session_id=thread_id,  # 只传递 session_id
):
```

**分析**:

- Backend 接收前端传来的完整历史消息（`request.messages`）
- 但在调用 NLU 时，只传递了 `session_id`（即 `thread_id`），没有传递历史消息
- NLU 模块内部通过 `session_id` 维护自己的历史记录（`SESSIONS` 字典中的 `NLU.history`）

### 2. 会话标识传递

**当前机制**:

- Frontend → Backend: 通过 `thread_id` 标识会话
- Backend → NLU: 将 `thread_id` 作为 `session_id` 传递
- NLU 内部: 基于 `session_id` 维护会话状态

**优点**:

- 简洁高效，避免重复传递大量历史数据
- NLU 模块负责自己的状态管理，职责清晰

**潜在问题**:

- 如果 NLU 服务重启，会话状态丢失（SESSIONS 是内存存储）
- Frontend 和 NLU 的历史记录可能不同步（如 NLU 服务重启后）

---

## 可选改进方案

### 方案 1: 传递完整历史消息（优先级：低）

#### 改进思路

在调用 NLU 时，将前端的完整历史消息传递给 NLU，由 NLU 决定如何使用。

#### 实施步骤

##### 步骤 1: 修改 NLU API 定义

在 `algorithms/NLU/fastapi_server.py` 中，扩展请求参数：

```python
class NLURequest(BaseModel):
    session_id: str
    text: str
    history: list[dict[str, Any]] | None = None  # 新增可选参数
```

##### 步骤 2: 修改 NLU 服务处理逻辑

在 `fastapi_server.py` 的流式端点中：

```python
@app.post("/nlu/stream")
async def nlu_stream(request: NLURequest):
    # 获取或创建 NLU 实例
    nlu = get_or_create_nlu_session(request.session_id)

    # 如果前端传递了 history，同步到 NLU 实例
    if request.history is not None:
        nlu.sync_history(request.history)  # 需要实现此方法

    # 正常处理
    async for event in nlu.run_stream(request.text):
        yield event
```

##### 步骤 3: 修改 Backend 调用处

在 `backend/src/service/planner_routes.py` 中：

```python
# 准备历史消息（转换格式）
history_for_nlu = [
    {
        "role": msg.role,
        "content": msg.content,
        # 其他必要字段...
    }
    for msg in thread.messages[-10:]  # 只传递最近 10 条
]

async for event in nlu_client.call_nlu_stream(
    text=request.prompt,
    session_id=thread_id,
    history=history_for_nlu,  # 传递历史
):
```

#### 优点

- 确保 Frontend 和 NLU 的历史消息完全同步
- 即使 NLU 服务重启，也能从前端恢复上下文

#### 缺点

- 增加网络传输开销（每次请求都传递历史）
- 需要定义和维护历史消息的同步格式
- 需要同时修改 NLU API 和 Backend 代码

#### 是否必要？

**不必要**。因为：

1. 当前的 bug 根本原因是 NLU 内部的合并逻辑问题，与历史消息是否同步无关
2. NLU 通过 `session_id` 维护的历史已经足够，且更高效
3. 增加的复杂度和开销大于收益

**建议**: 暂不实施，除非未来有明确的需求（如需要支持 NLU 服务的无状态部署）。

---

### 方案 2: 添加历史消息重置接口（优先级：中）

#### 改进思路

提供一个接口，允许前端或 Backend 在必要时重置 NLU 的会话状态。

#### 使用场景

- 用户明确表示要"开始新的规划"
- 用户说"清除之前的对话"
- 检测到上下文切换（如从 Kyoto 切换到 Tokyo）

#### 实施步骤

##### 步骤 1: 在 NLU API 中添加重置端点

在 `algorithms/NLU/fastapi_server.py` 中：

```python
@app.post("/nlu/session/{session_id}/reset")
async def reset_session(session_id: str):
    """重置指定会话的状态"""
    if session_id in SESSIONS:
        del SESSIONS[session_id]
        return {"status": "success", "message": f"Session {session_id} reset"}
    return {"status": "not_found", "message": f"Session {session_id} not found"}
```

##### 步骤 2: 在 Backend 中添加调用逻辑（可选）

在 `backend/src/service/planner_routes.py` 中添加新的端点：

```python
@router.post("/planner/reset/{thread_id}")
async def reset_planner_session(
    thread_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
):
    """重置规划会话（清除 NLU 状态）"""
    await nlu_client.reset_session(thread_id)
    return {"status": "success"}
```

##### 步骤 3: 前端集成（可选）

前端可以提供一个"重新开始"按钮，调用此接口清除上下文。

#### 优点

- 给用户提供明确的上下文控制能力
- 实现简单，侵入性小

#### 缺点

- 需要用户手动触发
- 不能自动解决上下文粘滞问题

#### 是否必要？

**部分必要**。作为辅助功能，可以让用户在遇到问题时有手动重置的选项。但不应该作为主要解决方案。

**建议**: 可以考虑实施，但优先级低于 NLU 模块的核心修复。

---

### 方案 3: 在 Backend 层面检测意图切换（优先级：低）

#### 改进思路

在 Backend 调用 NLU 之前，先分析用户输入是否存在明显的意图切换（如目的地变更），并在检测到时主动重置 NLU 会话。

#### 实施步骤

##### 步骤 1: 实现简单的意图切换检测

```python
def detect_intent_change(
    current_input: str,
    recent_messages: list[Message]
) -> bool:
    """
    检测用户输入是否存在明显的意图切换

    简单规则：
    - 包含"重新"、"换成"、"改为"等关键词
    - 提到不同的城市名称
    """
    change_keywords = ["重新", "换成", "改为", "不是", "改一下"]
    for keyword in change_keywords:
        if keyword in current_input:
            return True
    return False
```

##### 步骤 2: 在调用 NLU 前检测

```python
# 检测意图切换
if detect_intent_change(request.prompt, thread.messages):
    # 重置 NLU 会话
    await nlu_client.reset_session(thread_id)

# 正常调用 NLU
async for event in nlu_client.call_nlu_stream(...):
    ...
```

#### 优点

- 自动化处理，无需用户手动重置

#### 缺点

- Backend 需要理解 NLU 的业务逻辑，违反了职责分离原则
- 检测规则可能不准确
- 与 NLU 模块内部的 merge_partial 逻辑重复

#### 是否必要？

**不必要**。因为：

1. 意图理解应该由 NLU 模块负责，Backend 不应该介入
2. 这会导致逻辑重复和维护困难
3. NLU 模块本身应该有能力处理意图变更

**建议**: 不实施。应该在 NLU 模块内部彻底解决问题。

---

## 推荐方案

### 当前阶段：不修改 Backend

**理由**:

1. Bug 的根本原因在 NLU 模块的 `merge_partial` 函数
2. 当前 Backend 的实现是合理的，职责清晰
3. 修改 Backend 无法从根本上解决问题，反而增加复杂度

**建议行动**:

1. **优先实施 NLU 模块的修复**（参见 `/algorithms/NLU/docs/gen/bug-fix/context-stickiness-analysis-and-fix.md`）
2. 验证 NLU 修复后问题是否解决
3. 如果问题依然存在，再考虑 Backend 层面的辅助方案

### 未来可选改进（优先级低）

如果未来有需求，可以考虑：

1. **方案 2（会话重置接口）**: 作为用户的手动控制选项
2. **方案 1（传递完整历史）**: 仅在需要无状态部署 NLU 时考虑

---

## 总结

经过分析，Backend 模块在 NLU-RAG 上下文粘滞问题中**不是主要责任方**。当前的实现是合理和高效的。

**核心结论**:

- **主要问题**: NLU 模块的 `merge_partial` 函数在合并 `dest_pref` 时采用了不合适的累加策略
- **Backend 角色**: 仅作为前端和 NLU 之间的桥梁，正确传递了 `session_id`
- **修复重点**: 应集中在 NLU 模块，而非 Backend

**行动建议**:

1. 不修改 Backend 代码
2. 优先实施 NLU 模块的智能意图变更检测（方案 1）和智能城市选择（方案 3）
3. 验证修复效果后再评估是否需要 Backend 层面的辅助功能

---

## 参考文档

- **NLU 模块主分析**: `/algorithms/NLU/docs/gen/bug-fix/context-stickiness-analysis-and-fix.md`
- **问题复现数据**: `/cross-issues/history-dump.json`
- **Backend 代码**: `src/service/planner_routes.py`
- **NLU API**: `algorithms/NLU/fastapi_server.py`
