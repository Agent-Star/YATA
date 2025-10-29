# IMP-001: 消息时间戳持久化

## 元数据

- **ID**: IMP-001
- **分类**: 数据一致性
- **优先级**: 🟡 中
- **状态**: ✅ 已完成
- **创建日期**: 2025-01-27
- **完成日期**: 2025-01-27
- **预计工作量**: 中
- **实际工作量**: 中
- **相关文档**:
  - `impl-summary/sorting-timestamp-improvement.md`
  - `improvements/timestamp-implementation-guide.md` (实施指南)

---

## 问题描述

### 当前实现

在 `backend/src/service/planner_routes.py` 的 `langchain_message_to_frontend()` 函数中，时间戳提取逻辑如下：

```python
# 1. 尝试从 additional_kwargs 获取
if hasattr(message, "additional_kwargs"):
    additional_kwargs = getattr(message, "additional_kwargs", {})
    created_at = additional_kwargs.get("created_at") or additional_kwargs.get("timestamp")

# 2. 尝试从 response_metadata 获取
if not created_at and metadata:
    created_at = metadata.get("created_at") or metadata.get("timestamp")

# 3. 如果仍未找到时间戳, 使用当前 UTC 时间
if not created_at:
    created_at = datetime.now(timezone.utc).isoformat()
```

### 不足之处

1. **数据不一致**：LangChain 消息对象通常不包含时间戳，导致回退到"当前时间"
2. **时间漂移**：每次查询历史记录时，没有时间戳的消息会得到不同的时间值
3. **依赖框架**：时间戳的存在完全依赖 LangChain 或 Agent 实现，不可控

**示例场景**：

```
第一次查询 GET /planner/history:
- Message 1: createdAt = "2025-01-27T10:00:00Z" (查询时的当前时间)

第二次查询 GET /planner/history (5分钟后):
- Message 1: createdAt = "2025-01-27T10:05:00Z" (又变了！)
```

---

## 影响分析

### 功能影响

- ❌ **时间显示不准确**：前端无法正确显示消息的真实创建时间
- ⚠️ **排序可能不稳定**：虽然当前依赖消息列表顺序，但时间戳不稳定会影响基于时间的其他功能

### 性能影响

- ✅ 无显著性能影响（时间戳提取开销极小）

### 用户体验影响

- ⚠️ **信任度下降**：用户可能注意到历史记录的时间显示不一致
- ⚠️ **功能受限**：无法基于准确时间实现高级功能（如时间筛选、统计等）

### 开发维护影响

- ⚠️ **调试困难**：无法准确追踪消息创建时间，影响问题排查

---

## 改进方案

### 方案 1: Agent 层添加时间戳（推荐）

**优势**：

- ✅ 数据在源头就准确
- ✅ 不需要额外存储
- ✅ 与 LangChain 生态集成良好

**实施步骤**：

#### 1. 修改 Research Assistant

**文件**: `backend/src/agents/research_assistant.py`

```python
async def acall_model(state: AgentState, config: RunnableConfig) -> AgentState:
    from datetime import datetime, timezone
    
    m = get_model(config["configurable"].get("model", settings.DEFAULT_MODEL))
    model_runnable = wrap_model(m)
    response = await model_runnable.ainvoke(state, config)

    # ✅ 添加时间戳
    if isinstance(response, AIMessage):
        if not hasattr(response, "additional_kwargs") or response.additional_kwargs is None:
            response.additional_kwargs = {}
        response.additional_kwargs["created_at"] = datetime.now(timezone.utc).isoformat()

    # Run llama guard check...
    # ...
    
    return {"messages": [response]}
```

#### 2. 修改输入消息处理

在 `planner_routes.py` 创建 HumanMessage 时添加时间戳：

```python
async def generate_events() -> AsyncGenerator[str, None]:
    try:
        # 获取用户的主 Thread ID
        thread_id = await get_or_create_main_thread(current_user, session)

        # 获取 agent
        agent: AgentGraph = get_agent(DEFAULT_AGENT)

        # ...

        # 构建输入 (✅ 添加时间戳)
        from datetime import datetime, timezone
        input_message = HumanMessage(
            content=request.prompt,
            additional_kwargs={"created_at": datetime.now(timezone.utc).isoformat()}
        )
        user_input = {"messages": [input_message]}
```

#### 3. 更新其他 Agent

对所有使用的 Agent（`chatbot`, `rag_assistant` 等）应用同样的改动。

---

### 方案 2: 使用 Checkpointer 时间戳

**优势**：

- ✅ 利用 LangGraph Checkpointer 的内置时间戳
- ✅ 无需修改 Agent 代码

**劣势**：

- ❌ 需要从 Checkpointer metadata 中提取，可能不够直观
- ⚠️ 依赖 Checkpointer 实现

**实施步骤**：

修改 `langchain_message_to_frontend()` 函数：

```python
def langchain_message_to_frontend(
    message: AnyMessage, 
    checkpoint_metadata: dict | None = None
) -> FrontendMessage:
    """将 LangChain 消息转换为前端格式"""
    # ...
    
    # 提取创建时间
    created_at = None
    
    # 1. 尝试从消息本身获取
    if hasattr(message, "additional_kwargs"):
        additional_kwargs = getattr(message, "additional_kwargs", {})
        created_at = additional_kwargs.get("created_at") or additional_kwargs.get("timestamp")
    
    # 2. 尝试从 checkpoint metadata 获取
    if not created_at and checkpoint_metadata:
        created_at = checkpoint_metadata.get("created_at")
    
    # 3. 回退方案保持不变
    if not created_at:
        created_at = datetime.now(timezone.utc).isoformat()
    
    return FrontendMessage(...)
```

---

### 方案 3: 数据库层持久化（最稳健）

**优势**：

- ✅ 完全可控，不依赖框架
- ✅ 可以存储额外的元数据（编辑时间、IP 地址等）
- ✅ 支持复杂查询和统计

**劣势**：

- ❌ 需要设计新的数据库表
- ❌ 增加系统复杂度
- ❌ 可能与 LangGraph Checkpointer 数据重复

**数据库设计**：

```sql
CREATE TABLE message_metadata (
    id UUID PRIMARY KEY,
    message_id VARCHAR(255) UNIQUE NOT NULL,
    thread_id VARCHAR(100) NOT NULL,
    user_id UUID NOT NULL,
    role VARCHAR(20) NOT NULL,
    content TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE,
    metadata JSONB,
    FOREIGN KEY (user_id) REFERENCES user(id)
);

CREATE INDEX idx_message_thread ON message_metadata(thread_id, created_at);
CREATE INDEX idx_message_user ON message_metadata(user_id, created_at);
```

---

## 实施建议

### 推荐方案

**方案 1 (Agent 层添加时间戳)** - 最佳平衡

**理由**：

1. 实现简单，工作量适中
2. 数据在源头就准确
3. 不增加系统复杂度
4. 与现有架构兼容

### 实施步骤

1. **阶段 1**：修改 `research_assistant.py` 和 `planner_routes.py`
   - 预计工作量：2-3 小时
   - 测试覆盖：单元测试 + 集成测试

2. **阶段 2**：修改其他 Agent（如需要）
   - 预计工作量：1-2 小时

3. **阶段 3**：验证和部署
   - 清空现有历史记录（或接受旧消息时间不准确）
   - 监控新消息的时间戳是否正确

### 注意事项

1. **向后兼容**：旧消息没有时间戳，保持现有回退逻辑
2. **时区处理**：统一使用 UTC，前端根据用户时区显示
3. **时间格式**：使用 ISO 8601 格式 (`YYYY-MM-DDTHH:MM:SS+00:00`)

### 回滚方案

如果出现问题，直接移除 `additional_kwargs["created_at"]` 的设置代码，系统会回退到当前的实现（使用当前时间）。

---

## 测试计划

### 单元测试

```python
def test_message_with_agent_timestamp():
    """测试 Agent 创建的消息包含时间戳"""
    from agents.research_assistant import acall_model
    
    state = AgentState(messages=[HumanMessage(content="测试")])
    config = RunnableConfig(configurable={"model": "gpt-4o"})
    
    result = await acall_model(state, config)
    
    ai_message = result["messages"][0]
    assert "created_at" in ai_message.additional_kwargs
    # 验证时间戳格式
    datetime.fromisoformat(ai_message.additional_kwargs["created_at"])
```

### 集成测试

```bash
# 1. 发送消息
curl -X POST http://localhost:8080/planner/plan/stream \
  -H "Cookie: yata_auth=<token>" \
  -d '{"prompt": "测试消息", "context": {}}'

# 2. 获取历史记录
curl -X GET http://localhost:8080/planner/history \
  -H "Cookie: yata_auth=<token>"

# 3. 验证
# - 每条消息都有 createdAt
# - createdAt 格式正确 (ISO 8601)
# - createdAt 时间合理（接近实际发送时间）

# 4. 再次获取历史记录（5分钟后）
curl -X GET http://localhost:8080/planner/history \
  -H "Cookie: yata_auth=<token>"

# 5. 验证
# - createdAt 时间没有变化（与第一次查询相同）
```

---

## 相关资源

- [sorting-timestamp-improvement.md](../frontend-integration/impl-summary/sorting-timestamp-improvement.md) - 当前时间戳提取实现
- [LangChain Message Documentation](https://python.langchain.com/docs/modules/model_io/messages/)
- [ISO 8601 Date Format](https://en.wikipedia.org/wiki/ISO_8601)

---

## 实施总结

**实施日期**: 2025-01-27

### 采用方案

✅ **方案 1: Agent 层添加时间戳** - 已完成实施

### 实施内容

1. **创建通用工具模块** (`agents/timestamp.py`)
   - `@with_message_timestamps` 装饰器（StateGraph 模式）
   - `add_timestamp_to_message()` 函数（@entrypoint 模式手动添加）
   - `create_timestamped_message()` 函数（创建带时间戳的消息）
   - `add_timestamps_to_messages()` 批量处理函数
   - `get_utc_timestamp()` 时间戳生成工具
   - **设计决策**: 未实现 `@entrypoint` 装饰器，因为 `entrypoint.final()` 对象不透明，无法在外部拦截修改

2. **应用到现有 Agent**
   - `research_assistant.py`: 使用 `@with_message_timestamps` 装饰器
   - `rag_assistant.py`: 使用 `@with_message_timestamps` 装饰器
   - `chatbot.py`: 使用 `add_timestamp_to_message()` 手动添加

3. **API 层集成**
   - `planner_routes.py`: 使用 `create_timestamped_message()` 为用户输入添加时间戳

4. **模块导出**
   - 在 `agents/__init__.py` 中导出所有时间戳工具，方便全局使用

### 技术亮点

1. **通用性强**: 支持 StateGraph 和 @entrypoint 两种 Agent 模式
2. **零侵入性**: 装饰器模式，现有 Agent 只需添加一行代码
3. **类型安全**: 所有 linting 错误已修复，类型注解完整
4. **向后兼容**: 保留了原有的回退逻辑，旧消息不受影响
5. **可扩展性**: 新 Agent 可以轻松集成时间戳功能

### 测试验证

- ✅ 所有修改文件通过 linting 检查
- ✅ 装饰器类型定义正确
- ✅ 导入导出无循环依赖

### 后续建议

1. 添加单元测试验证时间戳功能
2. 添加集成测试验证端到端流程
3. 监控生产环境中消息时间戳的准确性
4. 考虑为其他 Agent（command_agent, interrupt_agent 等）添加时间戳支持

## 更新日志

- 2025-01-27: 创建文档，提出三种改进方案
- 2025-01-27: 完成方案 1 实施，创建通用时间戳管理工具
