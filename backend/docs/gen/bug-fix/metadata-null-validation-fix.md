# Metadata 字段 Null 值验证错误修复

**日期**: 2025-01-27  
**问题**: 422 Validation Error  
**原因**: `FrontendMessage.metadata` 不接受 `null` 值  
**影响**: 前端发送包含历史消息的请求时失败

---

## 🐛 问题描述

### 错误现象

用户在调用 `/planner/plan/stream` 接口时，传入包含历史消息的请求，服务器返回 **422 Validation Error**：

```json
{
  "detail": [
    {
      "type": "dict_type",
      "loc": ["body", "context", "history", 0, "metadata"],
      "msg": "Input should be a valid dictionary",
      "input": null
    },
    {
      "type": "dict_type", 
      "loc": ["body", "context", "history", 1, "metadata"],
      "msg": "Input should be a valid dictionary",
      "input": null
    }
  ]
}
```

### 请求体示例

```json
{
  "prompt": "帮我生成一个旅游规划",
  "context": {
    "language": "zh",
    "history": [
      {
        "id": "assistant-welcome",
        "role": "assistant",
        "content": "你好，我是你的AI旅行助手...",
        "metadata": null  // ❌ 这里是 null
      },
      {
        "id": "user-1761835929295",
        "role": "user",
        "content": "帮我生成一个旅游规划",
        "metadata": null  // ❌ 这里也是 null
      }
    ]
  }
}
```

---

## 🔍 根本原因

### 原始定义（有问题）

```python
class FrontendMessage(BaseModel):
    """前端消息格式"""
    
    id: str
    role: str | Literal["user", "assistant"]
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)  # ❌ 不接受 null
    createdAt: str | None = None
```

### Pydantic 验证行为

| 前端传入 | Pydantic 行为 | 结果 |
|---------|--------------|------|
| **不传** `metadata` | 使用 `default_factory=dict` → `{}` | ✅ 通过 |
| `"metadata": {}` | 直接使用 `{}` | ✅ 通过 |
| `"metadata": null` | 期望 `dict`，实际 `null` | ❌ **验证失败** |
| `"metadata": {"key": "value"}` | 直接使用 | ✅ 通过 |

**关键问题**：

- `default_factory=dict` 只在**字段缺失**时生效
- 当字段**存在但值为 `null`** 时，Pydantic 会验证失败
- 前端可能发送 `null` 值（如 JavaScript 的 `null`、JSON 的 `null`）

---

## ✅ 解决方案

### 修改后的定义

```python
class FrontendMessage(BaseModel):
    """前端消息格式"""
    
    id: str
    role: str | Literal["user", "assistant"]
    content: str
    metadata: dict[str, Any] | None = None  # ✅ 允许 null 值
    createdAt: str | None = None
```

### 新的验证行为

| 前端传入 | Pydantic 行为 | 结果 |
|---------|--------------|------|
| **不传** `metadata` | 使用默认值 `None` | ✅ 通过 |
| `"metadata": null` | 接受 `None` | ✅ 通过 |
| `"metadata": {}` | 接受空 dict | ✅ 通过 |
| `"metadata": {"key": "value"}` | 接受有效 dict | ✅ 通过 |

**优势**：

1. ✅ **兼容性**：同时支持 `null` 和 `{}`
2. ✅ **灵活性**：前端可以选择不传或传 `null`
3. ✅ **简洁性**：使用 `None` 作为默认值更符合 Python 习惯
4. ✅ **类型安全**：类型提示明确表示可以是 `None`

---

## 📋 修改的文件

### `backend/src/service/planner_routes.py`

**修改前**:

```python
metadata: dict[str, Any] = Field(default_factory=dict)
```

**修改后**:

```python
metadata: dict[str, Any] | None = None  # 允许 null 值
```

---

## 🧪 验证测试

### 测试用例 1: 不传 `metadata`

**请求**:

```json
{
  "prompt": "帮我规划旅行",
  "context": {
    "history": [
      {
        "id": "msg-1",
        "role": "user",
        "content": "你好"
        // 不传 metadata
      }
    ]
  }
}
```

**结果**: ✅ 通过（`metadata` 为 `None`）

---

### 测试用例 2: 传入 `null`

**请求**:

```json
{
  "prompt": "帮我规划旅行",
  "context": {
    "history": [
      {
        "id": "msg-1",
        "role": "user",
        "content": "你好",
        "metadata": null  // 显式传入 null
      }
    ]
  }
}
```

**结果**: ✅ 通过（`metadata` 为 `None`）

---

### 测试用例 3: 传入空 `{}`

**请求**:

```json
{
  "prompt": "帮我规划旅行",
  "context": {
    "history": [
      {
        "id": "msg-1",
        "role": "user",
        "content": "你好",
        "metadata": {}  // 空对象
      }
    ]
  }
}
```

**结果**: ✅ 通过（`metadata` 为 `{}`）

---

### 测试用例 4: 传入有效数据

**请求**:

```json
{
  "prompt": "帮我规划旅行",
  "context": {
    "history": [
      {
        "id": "msg-1",
        "role": "user",
        "content": "你好",
        "metadata": {
          "timestamp": "2025-01-27T10:00:00Z",
          "source": "frontend"
        }
      }
    ]
  }
}
```

**结果**: ✅ 通过（`metadata` 为有效 dict）

---

## 🔄 影响范围

### 受影响的端点

1. ✅ `POST /planner/plan/stream`
   - 接受 `PlanRequest` → 包含 `PlanContext` → 包含 `history: list[FrontendMessage]`

2. ✅ `GET /planner/history`
   - 返回 `HistoryResponse` → 包含 `messages: list[FrontendMessage]`

### 不受影响的部分

- ✅ 后端内部生成的消息（`langchain_message_to_frontend`）
  - 仍然传入 `metadata = getattr(message, "response_metadata", {})`
  - 始终是一个有效的 `dict`（不是 `None`）

---

## 📚 设计建议

### 为什么选择 `None` 而不是 `{}`？

#### 选项 1: 默认 `None` ✅ **推荐**

```python
metadata: dict[str, Any] | None = None
```

**优点**:

- 明确表示"没有元数据"和"有空元数据"的区别
- 节省内存（不需要为每条消息创建空 dict）
- 符合 Python 的 Optional 习惯
- 前端更灵活（可以传 `null`）

**缺点**:

- 使用时需要检查 `if metadata is not None`

---

#### 选项 2: 默认 `{}` ❌ 不推荐

```python
metadata: dict[str, Any] = Field(default_factory=dict)
```

**优点**:

- 使用时不需要检查 `None`
- 始终可以当作 dict 使用

**缺点**:

- ❌ **不接受前端的 `null` 值**（这是本次 bug 的根源）
- 无法区分"没有传"和"传了空对象"
- 每条消息都需要创建一个空 dict 实例

---

### 最佳实践

**在使用 `metadata` 时**:

```python
# ✅ 推荐：安全访问
metadata = message.metadata or {}
value = metadata.get("key", "default")

# ✅ 推荐：检查后使用
if message.metadata:
    do_something(message.metadata)

# ❌ 不推荐：直接访问（可能是 None）
value = message.metadata["key"]  # 如果 metadata 是 None 会报错
```

---

## 🎯 总结

### 问题根源

前端发送的历史消息中 `metadata` 字段为 `null`，而 Pydantic 验证要求必须是 `dict` 类型。

### 解决方案

将 `metadata` 字段改为 Optional：`dict[str, Any] | None = None`

### 影响

- ✅ 兼容前端发送的 `null` 值
- ✅ 兼容前端不传该字段
- ✅ 兼容前端传有效 dict
- ✅ 不影响后端现有逻辑

### Linting

- ✅ 无新增 linting 错误
- ✅ 类型提示明确

---

**修复状态**: ✅ 已完成  
**验证状态**: ✅ 已测试  
**文档状态**: ✅ 已记录
