# 行程规划系统调用链路分析

## 核心问题

**阶段 3 实现的 `/planner/plan/stream` 接口是否可以在未对接 RAG/算法小组的情况下，仅依赖 AI API-key 完成基本应答？**

**答案：✅ 可以！**

当前系统**完全不依赖 RAG/算法小组的对接**，仅需配置有效的 AI API-key 即可正常工作。

---

## 完整调用链路分析

### 1. 前端发起请求

```
POST /planner/plan/stream
Body: {
  "prompt": "帮我规划一个三天的东京旅行",
  "context": {"language": "zh"}
}
Headers: Cookie (包含 JWT token)
```

### 2. 后端路由处理

**文件**: `backend/src/service/planner_routes.py`

```python
@planner_router.post("/plan/stream")
async def plan_stream(
    request: PlanRequest,
    current_user: Annotated[User, Depends(current_active_user)],
    session: AsyncSession = Depends(get_async_session),
) -> StreamingResponse:
```

**核心逻辑**:

1. ✅ 验证用户身份（通过 JWT cookie）
2. ✅ 获取或创建用户的主 Thread ID（用于会话持久化）
3. ✅ **获取默认 Agent** (`DEFAULT_AGENT = "research-assistant"`)
4. ✅ 构建配置（thread_id, user_id, language, model）
5. ✅ 流式调用 Agent 并返回 SSE 事件

### 3. Agent 层处理

**文件**: `backend/src/agents/research_assistant.py`

**Agent 类型**: `research-assistant` (默认 Agent)

**Agent 能力**:

```python
tools = [web_search, calculator]

# 可选: 如果配置了 OPENWEATHERMAP_API_KEY
tools.append(weather_tool)
```

**处理流程**:

```
用户输入 → guard_input (安全检查)
         ↓
      [安全?]
         ↓ (safe)
       model (调用 LLM)
         ↓
    [需要工具?]
         ↓ (yes)
       tools (执行工具调用)
         ↓
       model (再次调用 LLM 汇总结果)
         ↓
       END (返回最终响应)
```

**系统提示词**:

```python
instructions = f"""
You are a helpful research assistant with the ability to search the web and use other tools.
Today's date is {current_date}.

NOTE: THE USER CAN'T SEE THE TOOL RESPONSE.

A few things to remember:
- Please include markdown-formatted links to any citations used in your response.
- Use calculator tool with numexpr to answer math questions.
"""
```

### 4. LLM 模型调用

**文件**: `backend/src/core/llm.py`

```python
@cache
def get_model(model_name: AllModelEnum, /) -> ModelT:
    # 根据配置的模型名称返回对应的 LLM 客户端
    if model_name in OpenAIModelName:
        return ChatOpenAI(model=api_model_name, temperature=0.5, streaming=True)
    if model_name in DeepseekModelName:
        return ChatOpenAI(
            model=api_model_name,
            openai_api_base="https://api.deepseek.com",
            openai_api_key=settings.DEEPSEEK_API_KEY,
        )
    # ... 其他模型提供商
```

**支持的模型提供商**:

- OpenAI (GPT-3.5, GPT-4, GPT-4o, etc.)
- Deepseek
- Anthropic (Claude)
- Google (Gemini)
- Azure OpenAI
- Groq
- Ollama (本地)
- 其他 OpenAI 兼容接口

### 5. 流式响应返回

**SSE 事件格式**:

```javascript
// Token 事件 (增量内容)
data: {"type": "token", "delta": "东京是一个..."}

// 结束事件
data: {"type": "end", "messageId": "msg-123", "metadata": {}}

// 完成标记
data: [DONE]
```

---

## 关键发现

### ✅ 不依赖 RAG/算法小组

1. **默认 Agent 不需要 RAG**:
   - `research-assistant` 使用 **web search** 和 **calculator** 工具
   - 这些工具是 LangChain Community 提供的开箱即用工具
   - **无需任何自定义算法或知识库**

2. **完全独立运行**:
   - 只需配置 LLM API key（如 `OPENAI_API_KEY` 或 `DEEPSEEK_API_KEY`）
   - Agent 会根据用户问题自主决定是否需要调用工具
   - 所有逻辑都在后端完成，前端只负责展示

3. **会话持久化**:
   - 使用 LangGraph 的 Checkpointer（PostgreSQL 或 SQLite）
   - 每个用户有独立的 `main_thread_id`
   - 对话历史自动保存和恢复

### 🔍 与 RAG Assistant 的对比

项目中**也有** `rag-assistant` Agent，但**未被使用**:

```python
# backend/src/agents/agents.py
agents = {
    "research-assistant": Agent(...),  # ← 当前使用 (DEFAULT_AGENT)
    "rag-assistant": Agent(...),        # ← 需要 ChromaDB，未被使用
}
```

**RAG Assistant 需要**:

- ChromaDB 数据库
- 预先上传的知识库文档
- 额外的配置和初始化

**当前系统使用的 Research Assistant**:

- ❌ 不需要 RAG
- ❌ 不需要知识库
- ✅ 只需要 LLM API key
- ✅ 使用 web search 实时获取信息

---

## 实际工作示例

### 场景 1: 行程规划问题

**用户输入**: "帮我规划一个三天的东京旅行"

**系统响应流程**:

1. Research Assistant 接收问题
2. 分析问题，可能调用 `WebSearch` 工具搜索 "东京旅行攻略"
3. LLM 基于搜索结果生成行程规划
4. 流式返回给前端

### 场景 2: 数学问题

**用户输入**: "计算 123 * 456 + 789"

**系统响应流程**:

1. Research Assistant 识别为数学问题
2. 调用 `calculator` 工具执行计算
3. LLM 格式化结果返回

### 场景 3: 普通聊天

**用户输入**: "你好，今天天气不错"

**系统响应流程**:

1. Research Assistant 分析，判断不需要工具
2. 直接使用 LLM 生成回复
3. 流式返回

---

## 当前系统运行所需配置

### 必需配置

```bash
# 数据库配置 (用于用户认证和会话持久化)
DATABASE_TYPE=postgres  # 或 sqlite
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=yata
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your-password

# JWT 配置
AUTH_JWT_SECRET=your-jwt-secret

# LLM 配置 (至少配置一个)
OPENAI_API_KEY=sk-xxx          # 或
DEEPSEEK_API_KEY=sk-xxx        # 或
ANTHROPIC_API_KEY=sk-xxx       # 等
DEFAULT_MODEL=gpt-4o           # 或其他支持的模型
```

### 可选配置

```bash
# 天气查询功能 (可选)
OPENWEATHERMAP_API_KEY=xxx

# 超级管理员 (可选)
SUPER_ADMIN_USERNAME=admin
SUPER_ADMIN_PASSWORD=12345678
```

### ❌ 不需要的配置

```bash
# ChromaDB (RAG Assistant 才需要，当前不用)
# CHROMA_HOST=xxx
# CHROMA_PORT=xxx

# 自定义算法服务 (未对接，不需要)
# ALGORITHM_SERVICE_URL=xxx
```

---

## 总结

### ✅ 可以独立运行

你的**阶段 3 实现完全可以独立运行**，无需等待 RAG/算法小组对接：

1. **基础能力完备**: Web search + Calculator + LLM = 已经是一个功能完整的助手
2. **适合行程规划**: Web search 可以实时查询旅游信息、景点推荐等
3. **可扩展性好**: 未来对接 RAG 时，只需切换 Agent 或添加工具即可

### 🔧 建议测试步骤

1. **启动服务**:

   ```bash
   cd backend
   uv run fastapi dev src/run_service.py
   ```

2. **注册/登录用户**:

   ```bash
   curl -X POST http://localhost:8080/auth/register \
     -H "Content-Type: application/json" \
     -d '{"email": "test@example.com", "username": "test", "password": "12345678"}'
   ```

3. **测试行程规划**:

   ```bash
   curl -X POST http://localhost:8080/planner/plan/stream \
     -H "Cookie: yata_auth=<jwt-token>" \
     -H "Content-Type: application/json" \
     -d '{"prompt": "帮我规划一个三天的东京旅行", "context": {"language": "zh"}}'
   ```

4. **观察输出**: 应该能看到 SSE 流式响应

### 🚀 未来对接 RAG/算法时

如果未来需要对接自定义的 RAG 或算法服务，有两种方式：

**方式 1**: 切换到 `rag-assistant` Agent

```python
# planner_routes.py
agent: AgentGraph = get_agent("rag-assistant")  # 改为使用 RAG Assistant
```

**方式 2**: 为 `research-assistant` 添加自定义工具

```python
# research_assistant.py
from your_rag_service import custom_rag_tool

tools = [web_search, calculator, custom_rag_tool]  # 添加自定义工具
```

但**目前不需要**，系统已经可以正常工作！

---

## 技术亮点

1. **模块化设计**: Agent、LLM、Tools 解耦，易于替换和扩展
2. **多 Agent 架构**: 支持多种 Agent，通过配置切换
3. **流式响应**: SSE 实现实时反馈，用户体验好
4. **会话管理**: LangGraph Checkpointer 自动管理对话上下文
5. **安全防护**: Llama Guard 检查输入输出安全性

这个设计非常优秀，既保证了当前的可用性，又为未来的扩展预留了空间！
