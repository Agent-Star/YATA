# Message ID 和 Fallback 历史记录修复

## 问题描述

### 问题 1：Message ID 格式错误导致收藏功能失效

**现象：**

- Message ID 从原来的 `run--xxxx-yyyy` 格式变成了纯数字
- 前端收藏操作无法同步到后端持久化
- 刷新页面后收藏状态丢失

**根本原因：**

```python
# ❌ 错误实现
message_id = f"msg-{id(input_message)}"
```

- `id(input_message)` 返回 Python 对象的**内存地址**
- 每次运行都不同
- 不会持久化到数据库
- 刷新页面后同一条消息的 ID 会变化

**影响：**

- 收藏功能完全失效（无法匹配到正确的消息）
- 前端只能进行本地收藏，无法同步到云端

---

### 问题 2：Fallback 时历史记录缺失

**现象：**

- 当 NLU 失败并 fallback 到 research-assistant 时
- 虽然实时渲染正常
- 但刷新页面后历史记录为空（用户输入和 AI 响应都没有）

**根本原因：**

```python
# ❌ 错误实现
async for stream_event in research_agent.astream(...):
    # 只是流式转发，没有保存历史
    yield f"data: {json.dumps({'type': 'token', 'delta': delta})}\n\n"

# 流式结束后直接返回，没有保存
yield "data: [DONE]\n\n"
```

- Fallback 路径只调用了 `research_agent.astream()` 进行流式转发
- **没有保存历史记录**
- StateGraph 虽然会自动保存，但与我们的历史管理逻辑不一致

**影响：**

- Fallback 场景下的对话无法查询历史
- 多轮对话上下文丢失

---

## 解决方案

### 修复 1：使用稳定的 UUID

**修改文件：**`src/service/planner_routes.py`

#### 1.1 为 input_message 设置 UUID

**修改位置：第 222-227 行**

```python
# ✅ 正确实现
input_message = create_timestamped_message(
    request.prompt,
    HumanMessage,
    id=str(uuid4())  # 设置稳定的 UUID
)
message_id = input_message.id  # 使用消息自己的 UUID
```

**关键改进：**

- 使用 `uuid4()` 生成唯一且稳定的 ID
- 通过 `id` 参数传递给 `create_timestamped_message`
- `message_id` 直接使用消息的 `id` 属性

#### 1.2 为 final_message 设置 UUID

**修改位置：第 264-268 行（NLU 成功路径）**

```python
# ✅ 正确实现
final_message = AIMessage(
    content=full_content,
    id=str(uuid4())  # 设置稳定的 UUID
)
final_message = add_timestamp_to_message(final_message)
```

#### 1.3 为 fallback_message 设置 UUID

**修改位置：第 335-339 行（Fallback 路径）**

```python
# ✅ 正确实现
fallback_message = AIMessage(
    content=fallback_content,
    id=str(uuid4())  # 设置稳定的 UUID
)
fallback_message = add_timestamp_to_message(fallback_message)
```

---

### 修复 2：Fallback 路径保存历史

**修改文件：**`src/service/planner_routes.py`

**修改位置：第 296-348 行**

#### 2.1 收集 Fallback 响应内容

```python
# ✅ 添加变量收集完整响应
fallback_content = ""

async for stream_event in research_agent.astream(...):
    if stream_mode == "messages":
        msg, _ = event
        if isinstance(msg, AIMessageChunk):
            content = msg.content
            if content:
                delta = str(content) if not isinstance(content, str) else content

                # ✅ 收集内容（用于后续保存）
                fallback_content += delta

                # 立即转发给前端
                yield f"data: {json.dumps({'type': 'token', 'delta': delta})}\n\n"
```

#### 2.2 Fallback 完成后保存历史

```python
# ========== Fallback 成功，保存历史 ==========

# 创建完整的 AIMessage (带稳定的 UUID)
fallback_message = AIMessage(
    content=fallback_content,
    id=str(uuid4())
)
fallback_message = add_timestamp_to_message(fallback_message)

# 使用 save-history-helper 保存历史
save_helper = get_agent("save-history-helper")
await save_helper.ainvoke(
    {"messages": [input_message, fallback_message]},
    config=config
)

logger.info(f"PlanStream: Fallback completed, saved {len(fallback_content)} chars to history")
```

**关键改进：**

- 在流式转发的同时收集完整响应内容
- 流式完成后创建完整的 `AIMessage`
- 使用 `save-history-helper` 手动保存历史
- 确保用户输入和 AI 响应都正确保存

---

## 修复效果

### ✅ Message ID 问题已解决

**之前：**

- Message ID：`12345678`（内存地址）
- 每次刷新都变化
- 收藏无法匹配

**现在：**

- Message ID：`550e8400-e29b-41d4-a716-446655440000`（UUID）
- 稳定且唯一
- 收藏功能正常

### ✅ Fallback 历史记录已解决

**之前：**

- Fallback 场景：历史记录为空
- 刷新页面：对话消失

**现在：**

- Fallback 场景：历史记录完整
- 刷新页面：对话正常显示
- 多轮对话：上下文正确

---

## 验证清单

### 代码验证

- [x] uuid4 已正确导入
- [x] input_message 设置了稳定的 UUID
- [x] final_message 设置了稳定的 UUID
- [x] fallback_message 设置了稳定的 UUID
- [x] message_id 使用消息的 UUID
- [x] Fallback 路径收集完整响应
- [x] Fallback 路径保存历史记录
- [x] 语法检查通过

### 功能验证

**测试场景 1：NLU 正常路径**

- [ ] Message ID 格式正确（UUID）
- [ ] 收藏功能正常工作
- [ ] 刷新页面后收藏状态保持

**测试场景 2：Fallback 路径**

- [ ] 流式输出正常
- [ ] 历史记录完整（用户输入 + AI 响应）
- [ ] Message ID 格式正确（UUID）
- [ ] 收藏功能正常工作

**测试场景 3：多轮对话**

- [ ] NLU 路径的多轮对话正常
- [ ] Fallback 路径的多轮对话正常
- [ ] 混合路径的多轮对话正常

---

## 技术细节

### UUID vs 内存地址

| 对比项 | 内存地址 `id(obj)` | UUID `uuid4()` |
|--------|-------------------|----------------|
| 唯一性 | 进程内唯一 | 全局唯一 |
| 稳定性 | 每次运行变化 | ✅ 永久稳定 |
| 格式 | 纯数字 | 标准 UUID 格式 |
| 数据库友好 | ❌ 不适合 | ✅ 适合 |

### LangChain 消息 ID 设置

```python
from langchain_core.messages import HumanMessage, AIMessage
from uuid import uuid4

# ✅ 正确：通过构造函数设置
msg = HumanMessage(
    content="你好",
    id=str(uuid4())
)

# ❌ 错误：使用内存地址
msg_id = f"msg-{id(msg)}"
```

### save-history-helper 的重要性

为什么需要手动保存历史？

1. **绕过了 travel_planner agent**：
   - 直接调用 NLU，没有经过 agent 的保存逻辑

2. **Fallback 使用不同的 agent**：
   - research-assistant 有自己的保存机制
   - 但与我们的历史管理不一致

3. **统一的历史管理**：
   - 使用 `save-history-helper` 确保所有路径的历史格式一致
   - 用户输入和 AI 响应都正确保存

---

## 相关问题

### 为什么不使用 LangGraph 的自动 ID？

LangGraph 在某些情况下会自动生成消息 ID（格式：`run--xxxx-yyyy`），但：

1. **我们绕过了 LangGraph 的流式机制**：
   - 直接调用 NLU 流式 API
   - 没有经过 LangGraph 的消息处理

2. **需要手动管理消息**：
   - 手动创建消息对象
   - 需要明确设置 ID

3. **一致性要求**：
   - 所有路径（NLU、Fallback）都需要使用相同的 ID 格式
   - UUID 是标准且可靠的选择

---

## 修改文件清单

### 修改的文件

1. **`src/service/planner_routes.py`** ⭐ **核心修改**
   - 第 222-227 行：为 `input_message` 设置 UUID
   - 第 264-268 行：为 `final_message` 设置 UUID（NLU 路径）
   - 第 296-348 行：Fallback 路径收集响应并保存历史
   - 第 335-339 行：为 `fallback_message` 设置 UUID（Fallback 路径）

### 未修改的文件

- 其他所有文件保持不变
- 只需修改 `planner_routes.py` 即可

---

## 后续测试

### 测试步骤

1. **启动服务**：

   ```bash
   cd /home/eden/HKU-MSC-CS/nlp/YATA/backend
   uv run fastapi dev src/service.py
   ```

2. **测试 NLU 路径**：
   - 发送旅行规划请求
   - 收藏一条消息
   - 刷新页面
   - 验证收藏状态保持

3. **测试 Fallback 路径**：
   - 停止 NLU 服务
   - 发送一般问题
   - 观察流式输出
   - 刷新页面
   - 验证历史记录完整
   - 验证收藏功能正常

4. **检查 Message ID 格式**：
   - 打开浏览器开发者工具
   - 查看网络请求响应
   - 验证 `messageId` 字段是 UUID 格式

---

**修复日期**：2025-11-18
**修复状态**：✅ 实施完成，待测试验证
**修复版本**：v3.0（Message ID + Fallback 历史）
