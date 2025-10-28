# 阶段 3 实施总结: 行程规划接口实现

## 实施内容

### 1. 核心路由文件

**文件**: `backend/src/service/planner_routes.py` (新建)

创建了专门的行程规划路由模块，实现了前端所需的所有接口。

---

### 2. 实现的接口

#### 2.1 GET `/planner/history` - 获取历史记录

**功能**: 根据登录用户自动查询其主 Thread 的对话历史

**实现要点**:

```python
@planner_router.get("/history", response_model=HistoryResponse)
async def get_history(
    current_user: Annotated[User, Depends(current_active_user)],
    session: AsyncSession = Depends(get_async_session),
) -> HistoryResponse:
```

**核心逻辑**:

1. ✅ 获取用户的主 Thread ID (`get_or_create_main_thread`)
2. ✅ 从 LangGraph agent 获取 Thread 状态
3. ✅ 提取消息历史 (`state.values.get("messages")`)
4. ✅ 转换为前端期望的格式 (`FrontendMessage`)
5. ✅ 按时间升序返回

**响应格式**:

```json
{
  "messages": [
    {
      "id": "msg-xxx",
      "role": "user",
      "content": "计划一次东京之旅",
      "metadata": {},
      "createdAt": null
    },
    {
      "id": "msg-yyy",
      "role": "assistant",
      "content": "为你准备了以下行程...",
      "metadata": {},
      "createdAt": null
    }
  ]
}
```

**特性**:

- 🔒 需要用户登录 (Cookie 认证)
- 🔄 自动关联用户的主 Thread
- 📦 统一的错误处理

---

#### 2.2 POST `/planner/plan/stream` - 流式行程规划

**功能**: 接收用户输入，通过 SSE 流式返回 AI 生成的行程规划

**实现要点**:

```python
@planner_router.post("/plan/stream")
async def plan_stream(
    request: PlanRequest,
    current_user: Annotated[User, Depends(current_active_user)],
    session: AsyncSession = Depends(get_async_session),
) -> StreamingResponse:
```

**请求格式**:

```json
{
  "prompt": "安排一个 3 天的东京美食之旅",
  "context": {
    "language": "zh",
    "history": [...]
  }
}
```

**SSE 事件格式** (完全符合前端约定):

| 事件类型 | 格式 | 说明 |
|---------|------|------|
| `token` | `{"type": "token", "delta": "..."}` | 增量文本片段 |
| `metadata` | `{"type": "metadata", "metadata": {...}}` | 结构化数据 (待扩展) |
| `end` | `{"type": "end", "messageId": "...", "metadata": {...}}` | 流结束标记 |
| `[DONE]` | `data: [DONE]` | 兼容 OpenAI 格式 |

**核心逻辑**:

1. ✅ 获取用户主 Thread ID
2. ✅ 配置 agent (thread_id, user_id, language, model)
3. ✅ 构建输入消息 (`HumanMessage`)
4. ✅ 流式调用 agent (`agent.astream`)
5. ✅ 实时转换并发送 SSE 事件
6. ✅ 自动持久化对话到 Thread

**响应示例**:

```
data: {"type":"token","delta":"第一天："}
data: {"type":"token","delta":"早上参观"}
data: {"type":"token","delta":"浅草寺"}
...
data: {"type":"end","messageId":"msg-123","metadata":{}}
data: [DONE]
```

**特性**:

- 🔒 需要用户登录
- 🌊 Server-Sent Events (SSE) 流式传输
- 🌐 支持多语言 (通过 `context.language`)
- 💾 自动保存对话历史
- 🚫 禁用 Nginx 缓冲 (`X-Accel-Buffering: no`)

---

### 3. 数据模型定义

#### 3.1 前端消息格式

```python
class FrontendMessage(BaseModel):
    """前端消息格式"""
    id: str
    role: str  # "user" | "assistant"
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    createdAt: str | None = None
```

**字段映射**:

- LangChain `HumanMessage` → `role: "user"`
- LangChain `AIMessage` → `role: "assistant"`
- `message.id` → `id`
- `message.content` → `content`
- `message.response_metadata` → `metadata`

#### 3.2 请求/响应模型

```python
class PlanContext(BaseModel):
    """行程规划上下文"""
    language: str | None = None
    history: list[FrontendMessage] = Field(default_factory=list)

class PlanRequest(BaseModel):
    """行程规划请求"""
    prompt: str
    context: PlanContext = Field(default_factory=PlanContext)

class HistoryResponse(BaseModel):
    """历史记录响应"""
    messages: list[FrontendMessage]
```

---

### 4. 辅助函数

#### 4.1 `langchain_message_to_frontend()`

将 LangChain 消息转换为前端期望的格式:

```python
def langchain_message_to_frontend(message: AnyMessage) -> FrontendMessage:
    """将 LangChain 消息转换为前端格式"""
    # 角色映射
    if isinstance(message, HumanMessage):
        role = "user"
    elif isinstance(message, AIMessage):
        role = "assistant"
    else:
        role = "assistant"
    
    # 提取 ID、内容、元数据
    ...
```

**转换逻辑**:

- ✅ 正确识别消息类型
- ✅ 提取消息内容
- ✅ 保留元数据
- ✅ 生成消息 ID

---

## 技术实现亮点

### 1. 用户隔离

```python
# 每个用户只能访问自己的历史
thread_id = await get_or_create_main_thread(current_user, session)
```

- 通过 `current_active_user` 依赖自动获取登录用户
- 使用用户的 `main_thread_id` 隔离对话
- 确保数据安全

### 2. 流式处理优化

```python
async for stream_event in agent.astream(
    user_input, 
    config=config, 
    stream_mode=["updates", "messages"],  # 多模式
    subgraphs=True  # 支持子图
):
```

- ✅ 同时监听 `updates` 和 `messages` 事件
- ✅ 支持 LangGraph 子图
- ✅ 实时发送增量内容

### 3. SSE 格式标准化

```python
# Token 事件
yield f'data: {json.dumps({"type": "token", "delta": content})}\n\n'

# End 事件
yield f'data: {json.dumps({"type": "end", "messageId": message_id})}\n\n'

# [DONE] 标记
yield "data: [DONE]\n\n"
```

- ✅ 完全符合前端约定
- ✅ 兼容 OpenAI SSE 格式
- ✅ 支持 `token`/`metadata`/`end` 事件类型

### 4. 错误处理

```python
try:
    # 核心逻辑
except Exception as e:
    logger.error(f"流式规划失败: {e}")
    yield f'data: {json.dumps({"type": "error", "content": "服务器异常"})}\n\n'
    yield "data: [DONE]\n\n"
```

- ✅ 异常捕获并记录
- ✅ 错误信息通过 SSE 返回
- ✅ 确保流正确关闭

---

## 集成到主应用

**文件**: `backend/src/service/service.py`

```python
from service.planner_routes import planner_router

# 注册路由
app.include_router(planner_router)
```

**路由前缀**: `/planner`

**完整端点**:

- `GET /planner/history`
- `POST /planner/plan/stream`

---

## 与前端接口约定的对照

### ✅ 历史记录接口

| 前端约定 | 后端实现 | 状态 |
|---------|---------|------|
| `GET /planner/history` | ✅ 完全一致 | ✅ |
| 无需传 thread_id | ✅ 自动从用户获取 | ✅ |
| 返回 `messages` 数组 | ✅ 统一格式 | ✅ |
| 按时间升序 | ✅ LangGraph 自动保证 | ✅ |

### ✅ 流式规划接口

| 前端约定 | 后端实现 | 状态 |
|---------|---------|------|
| `POST /planner/plan/stream` | ✅ 完全一致 | ✅ |
| SSE `text/event-stream` | ✅ StreamingResponse | ✅ |
| `{"type":"token","delta":"..."}` | ✅ 完全符合 | ✅ |
| `{"type":"metadata",...}` | ✅ 预留支持 | ✅ |
| `{"type":"end","messageId":"..."}` | ✅ 完全符合 | ✅ |
| `data: [DONE]` | ✅ 完全符合 | ✅ |
| 自动持久化 | ✅ LangGraph 自动保存 | ✅ |

---

## 测试要点

### 1. 历史记录接口

```bash
# 获取历史 (需要先登录并获取 Cookie)
curl -X GET http://localhost:8080/planner/history \
  -H "Cookie: yata_auth=<token>"
```

**预期**:

- ✅ 返回空数组 (新用户) 或历史消息
- ✅ 401 如果未登录

### 2. 流式规划接口

```bash
# 流式规划
curl -X POST http://localhost:8080/planner/plan/stream \
  -H "Cookie: yata_auth=<token>" \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{
    "prompt": "计划一次 3 天的东京之旅",
    "context": {"language": "zh"}
  }'
```

**预期**:

- ✅ SSE 流式响应
- ✅ 实时接收 token 事件
- ✅ 最终收到 end 和 [DONE]
- ✅ 对话自动保存到历史

### 3. 用户隔离测试

1. 用户 A 登录，发送对话
2. 用户 B 登录，查看历史
3. **预期**: 用户 B 看不到用户 A 的对话 ✅

---

## 性能考虑

### 1. 流式传输优化

- ✅ 使用异步生成器 (`AsyncGenerator`)
- ✅ 禁用 Nginx 缓冲
- ✅ 设置正确的 HTTP headers

### 2. 数据库访问

- ✅ 使用异步 SQLAlchemy session
- ✅ Thread 查询带索引 (`main_thread_id`)
- ✅ 最小化数据库调用

### 3. Agent 调用

- ✅ 流式处理，不等待完整响应
- ✅ 支持中断和恢复
- ✅ 自动 checkpoint 管理

---

## 扩展性设计

### 1. 结构化元数据支持

当前实现已预留 `metadata` 事件类型，可以轻松扩展：

```python
# 未来扩展: 发送结构化行程数据
itinerary_data = {"days": [...], "budget": {...}}
yield f'data: {json.dumps({"type": "metadata", "metadata": itinerary_data})}\n\n'
```

### 2. 多 Agent 支持

可以根据请求类型选择不同的 agent：

```python
# 扩展示例
if request.context.get("agent_type") == "budget-planner":
    agent = get_agent("budget-planner")
else:
    agent = get_agent("research-assistant")
```

### 3. 多 Thread 管理

当前实现基于单 Thread 模式，未来可扩展：

```python
# 扩展: 支持创建新对话
if request.context.get("new_conversation"):
    thread_id = await create_new_thread_for_user(current_user, session)
```

---

## 文件清单

### 新建文件

- `backend/src/service/planner_routes.py` - 行程规划路由 (约 220 行)

### 修改文件

- `backend/src/service/service.py` - 集成路由 (+2 行)

### 总代码量

- 新增: ~220 行
- 修改: ~2 行

---

## 已知限制与未来改进

### 当前限制

1. **时间戳**: 当前 `createdAt` 字段为 `None`
   - **改进**: 可在消息中添加时间戳字段

2. **元数据事件**: 当前未生成结构化行程元数据
   - **改进**: 添加 Agent 后处理，提取结构化数据

3. **Agent 选择**: 当前使用 `DEFAULT_AGENT`
   - **改进**: 创建专门的 `travel-planner` agent

### 未来改进方向

1. **创建 Travel Planner Agent**

   ```python
   # 专门的旅游规划 agent
   - 集成天气 API
   - 集成地点搜索
   - 生成结构化行程
   ```

2. **增强历史管理**

   ```python
   # 支持分页、搜索、筛选
   - 分页参数 (offset, limit)
   - 时间范围筛选
   - 关键词搜索
   ```

3. **性能监控**

   ```python
   # 添加指标收集
   - 响应时间
   - Token 生成速度
   - 用户活跃度
   ```

---

## 阶段状态

✅ **阶段 3 完成**

**完成时间**: 2025-10-27  
**Linting 状态**: ✅ 无错误

---

**文档版本**: v1.0  
**作者**: AI Assistant
