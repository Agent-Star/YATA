# 时间戳管理实施指南

## 概述

本文档说明如何在 YATA 项目中为 Agent 消息添加时间戳，确保所有消息都有准确的创建时间。

## 核心工具

所有时间戳管理工具位于 `backend/src/agents/timestamp.py`，提供以下功能：

### 1. 装饰器方式（推荐用于 StateGraph 模式）

```python
from agents.timestamp import with_message_timestamps

@with_message_timestamps
async def acall_model(state: AgentState, config: RunnableConfig) -> AgentState:
    response = await model.ainvoke(state["messages"])
    return {"messages": [response]}  # 自动添加时间戳
```

**适用场景**：

- StateGraph 模式的 Agent（如 `research_assistant`, `rag_assistant`）
- 任何返回 `{"messages": [...]}" 的节点函数

**优势**：

- ✅ 零侵入性，只需添加一行装饰器
- ✅ 自动处理所有返回的消息
- ✅ 不影响原有逻辑

### 2. 手动添加方式（用于 @entrypoint 模式）

```python
from agents.timestamp import add_timestamp_to_message

@entrypoint()
async def chatbot(inputs, *, previous, config):
    messages = inputs["messages"]
    response = await model.ainvoke(messages)
    
    # 手动添加时间戳
    response = add_timestamp_to_message(response)
    
    return entrypoint.final(value={"messages": [response]}, ...)
```

**适用场景**：

- 使用 `@entrypoint()` 装饰器的 Agent（如 `chatbot`）
- 需要精确控制时间戳添加位置的场景

**为什么不用装饰器？**

`@entrypoint()` 函数返回 `entrypoint.final()` 对象，其内部结构不透明，装饰器无法在外部拦截和修改消息。因此必须在函数内部手动调用 `add_timestamp_to_message()`。

### 3. 创建带时间戳的消息（用于用户输入）

```python
from agents.timestamp import create_timestamped_message
from langchain_core.messages import HumanMessage

# 创建用户消息
input_message = create_timestamped_message("你好", HumanMessage)

# 等价于：
input_message = HumanMessage(
    content="你好",
    additional_kwargs={"created_at": "2025-01-27T10:30:45.123456+00:00"}
)
```

**适用场景**：

- API 路由中接收用户输入时（如 `planner_routes.py`）
- 需要创建新消息的任何场景

## 已实施的 Agent

| Agent | 模式 | 实施方式 | 文件 |
|-------|------|----------|------|
| research_assistant | StateGraph | `@with_message_timestamps` | `agents/research_assistant.py` |
| rag_assistant | StateGraph | `@with_message_timestamps` | `agents/rag_assistant.py` |
| chatbot | @entrypoint | `add_timestamp_to_message()` | `agents/chatbot.py` |

## 新 Agent 开发指南

### 方案 A: StateGraph 模式（推荐）

```python
from typing import Literal
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, MessagesState, StateGraph

from agents.timestamp import with_message_timestamps  # 导入装饰器
from core import get_model, settings


class AgentState(MessagesState, total=False):
    # 自定义状态字段
    pass


@with_message_timestamps  # ✅ 添加装饰器
async def acall_model(state: AgentState, config: RunnableConfig) -> AgentState:
    model = get_model(config["configurable"].get("model", settings.DEFAULT_MODEL))
    response = await model.ainvoke(state["messages"])
    return {"messages": [response]}  # 自动添加时间戳


# 构建图
agent = StateGraph(AgentState)
agent.add_node("model", acall_model)
agent.set_entry_point("model")
agent.add_edge("model", END)

my_custom_agent = agent.compile()
```

### 方案 B: @entrypoint 模式

```python
from langchain_core.messages import BaseMessage
from langchain_core.runnables import RunnableConfig
from langgraph.func import entrypoint

from agents.timestamp import add_timestamp_to_message  # 导入工具函数
from core import get_model, settings


@entrypoint()
async def my_custom_agent(
    inputs: dict[str, list[BaseMessage]],
    *,
    previous: dict[str, list[BaseMessage]],
    config: RunnableConfig,
):
    messages = inputs["messages"]
    if previous:
        messages = previous["messages"] + messages

    model = get_model(config["configurable"].get("model", settings.DEFAULT_MODEL))
    response = await model.ainvoke(messages)
    
    # ✅ 手动添加时间戳
    response = add_timestamp_to_message(response)
    
    return entrypoint.final(
        value={"messages": [response]},
        save={"messages": messages + [response]}
    )
```

## API 层集成

在接收用户输入的路由中使用 `create_timestamped_message`：

```python
from agents.timestamp import create_timestamped_message
from langchain_core.messages import HumanMessage

@router.post("/chat")
async def chat(request: ChatRequest):
    # ✅ 创建带时间戳的用户消息
    input_message = create_timestamped_message(request.prompt, HumanMessage)
    
    # 调用 agent
    result = await agent.ainvoke({"messages": [input_message]}, config=config)
    
    return result
```

## 工具函数参考

### `get_utc_timestamp()`

获取当前 UTC 时间戳（ISO 8601 格式）。

```python
from agents.timestamp import get_utc_timestamp

timestamp = get_utc_timestamp()
# "2025-01-27T10:30:45.123456+00:00"
```

### `add_timestamp_to_message(message)`

为单个消息添加时间戳（如果尚未存在）。

```python
from agents.timestamp import add_timestamp_to_message
from langchain_core.messages import AIMessage

message = AIMessage(content="你好")
message = add_timestamp_to_message(message)

print(message.additional_kwargs["created_at"])
# "2025-01-27T10:30:45.123456+00:00"
```

**特性**：

- 如果消息已有 `created_at` 或 `timestamp`，不会覆盖
- 原地修改消息对象
- 返回修改后的消息（方便链式调用）

### `add_timestamps_to_messages(messages)`

批量为消息列表添加时间戳。

```python
from agents.timestamp import add_timestamps_to_messages

messages = [message1, message2, message3]
messages = add_timestamps_to_messages(messages)
```

### `create_timestamped_message(content, message_type, **kwargs)`

创建带时间戳的新消息。

```python
from agents.timestamp import create_timestamped_message
from langchain_core.messages import HumanMessage, AIMessage

# 创建用户消息
user_msg = create_timestamped_message("你好", HumanMessage)

# 创建 AI 消息
ai_msg = create_timestamped_message("你好！", AIMessage)

# 传递额外参数
msg = create_timestamped_message(
    "你好",
    HumanMessage,
    id="custom-id",
    name="用户A"
)
```

### `@with_message_timestamps`

装饰器，自动为函数返回的消息添加时间戳。

```python
from agents.timestamp import with_message_timestamps

@with_message_timestamps
async def my_node(state, config):
    return {"messages": [response]}  # 自动添加时间戳
```

**工作原理**：

1. 拦截函数返回值
2. 检查是否包含 `"messages"` 键
3. 为列表中的所有消息添加时间戳
4. 返回修改后的结果

## 时间戳格式

所有时间戳使用 **ISO 8601** 格式，UTC 时区：

```
2025-01-27T10:30:45.123456+00:00
```

**特点**：

- ✅ 国际标准格式
- ✅ 包含微秒精度
- ✅ 明确时区（UTC）
- ✅ 前端可直接解析

## 前端集成

前端接收到的消息格式：

```typescript
interface FrontendMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  metadata: Record<string, any>;
  createdAt: string; // ISO 8601 格式
}
```

前端可以直接使用 `createdAt` 字段：

```typescript
// 解析时间戳
const date = new Date(message.createdAt);

// 格式化显示
const displayTime = date.toLocaleString("zh-CN", {
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
});
```

## 验证方法

### 1. 单元测试

```python
import pytest
from agents.timestamp import create_timestamped_message
from langchain_core.messages import HumanMessage
from datetime import datetime

def test_message_has_timestamp():
    msg = create_timestamped_message("测试", HumanMessage)
    
    # 验证时间戳存在
    assert "created_at" in msg.additional_kwargs
    
    # 验证时间戳格式
    timestamp = msg.additional_kwargs["created_at"]
    dt = datetime.fromisoformat(timestamp)
    assert dt is not None
```

### 2. 集成测试

```bash
# 发送消息
curl -X POST http://localhost:8080/planner/plan/stream \
  -H "Cookie: yata_auth=<token>" \
  -d '{"prompt": "测试消息", "context": {}}'

# 获取历史记录
curl -X GET http://localhost:8080/planner/history \
  -H "Cookie: yata_auth=<token>"

# 验证每条消息都有 createdAt 字段
```

## 注意事项

### 1. 向后兼容

旧消息可能没有时间戳，`langchain_message_to_frontend()` 会自动处理：

```python
# 如果消息没有时间戳，使用当前时间作为回退
if not created_at:
    created_at = datetime.now(timezone.utc).isoformat()
```

### 2. 时间戳不可变

一旦消息创建并保存到 Checkpointer，时间戳不应被修改，这保证了历史记录的准确性。

### 3. 时区统一

**所有时间戳均使用 UTC**，前端根据用户时区显示：

```typescript
// 前端转换为本地时间
const localTime = new Date(message.createdAt).toLocaleString();
```

## 故障排查

### 问题：消息没有时间戳

**检查清单**：

1. Agent 的 `acall_model` 是否使用了 `@with_message_timestamps`
2. 用户输入是否使用了 `create_timestamped_message()`
3. 检查 `additional_kwargs` 是否为 `None`

### 问题：时间戳不稳定

**原因**：可能使用了回退逻辑（`datetime.now()`）

**解决方案**：确保所有消息创建时就添加时间戳，而不是在转换时添加。

## 相关文档

- [IMP-001: 消息时间戳持久化](./imp-001-message-timestamp.md) - 改进方案设计
- [timestamp.py 源码](../../src/agents/timestamp.py) - 工具实现

---

**最后更新**: 2025-01-27  
**维护者**: Backend Team
