# NLU/RAG 整合架构设计详解

## 一、整体架构图

```txt
┌─────────────────────────────────────────────────────────────────────┐
│                           Frontend (React)                          │
│                   POST /planner/plan/stream                         │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ↓
┌─────────────────────────────────────────────────────────────────────┐
│                     Backend API Layer (FastAPI)                     │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  planner_routes.py: plan_stream()                            │  │
│  │  - 认证: current_active_user                                 │  │
│  │  - 获取: thread_id (作为 NLU session_id)                     │  │
│  │  - 调用: Agent.astream()                                     │  │
│  │  - 返回: StreamingResponse (SSE)                            │  │
│  └──────────────────────────────────────────────────────────────┘  │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ↓
┌─────────────────────────────────────────────────────────────────────┐
│                   Agent Layer (LangGraph)                           │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Travel Planner Agent (新增)                                │   │
│  │                                                             │   │
│  │  StateGraph:                                                │   │
│  │                                                             │   │
│  │    ┌──────────────┐                                        │   │
│  │    │  call_nlu    │  调用 NLU Service                      │   │
│  │    │  _service    │                                        │   │
│  │    └──────┬───────┘                                        │   │
│  │           │                                                │   │
│  │           ↓                                                │   │
│  │    ┌──────────────┐   No (成功)                           │   │
│  │    │   should_    ├───────────→ END                       │   │
│  │    │  fallback?   │                                       │   │
│  │    └──────┬───────┘                                       │   │
│  │           │ Yes (失败/超时)                               │   │
│  │           ↓                                                │   │
│  │    ┌──────────────┐                                       │   │
│  │    │  fallback_to │  降级到 Research-Assistant            │   │
│  │    │  _research   │                                       │   │
│  │    └──────┬───────┘                                       │   │
│  │           │                                                │   │
│  │           ↓                                                │   │
│  │         END                                                │   │
│  │                                                             │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Research-Assistant Agent (现有，作为兜底)                  │   │
│  │  - DuckDuckGo Web Search                                    │   │
│  │  - LLM 推理 (GPT-4o / Claude 3.5 Sonnet)                   │   │
│  └─────────────────────────────────────────────────────────────┘   │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ↓
┌─────────────────────────────────────────────────────────────────────┐
│                External Services Layer (新增)                       │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  NLU Client (nlu_client.py)                                 │   │
│  │  - POST http://localhost:8010/nlu/simple                    │   │
│  │  - 超时控制: 30s                                            │   │
│  │  - 重试策略: 1 次                                           │   │
│  │  - 异常处理: NLUServiceError                               │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  RAG Client (rag_client.py) [可选]                         │   │
│  │  - POST http://localhost:8001/search                        │   │
│  │  - 用于未来直接调用 RAG                                     │   │
│  └─────────────────────────────────────────────────────────────┘   │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                   ┌─────────┴─────────┐
                   │                   │
                   ↓                   ↓
        ┌──────────────────┐  ┌──────────────────┐
        │  NLU Service     │  │  RAG Service     │
        │  (Port 8010)     │  │  (Port 8001)     │
        │                  │  │                  │
        │  - 意图识别      │  │  - 向量检索      │
        │  - 行程生成      │  │  - ChromaDB      │
        │  - 推荐生成      │  │  - BGE-M3        │
        │  - 内部调用 RAG  │◄─┤                  │
        └──────────────────┘  └──────────────────┘
```

## 二、核心模块设计

### 2.1 External Services 层

#### 2.1.1 NLU Client

**文件位置**: `backend/src/external_services/nlu_client.py`

**职责**:

- 封装 NLU 服务的 HTTP 调用
- 处理请求/响应的序列化/反序列化
- 实现超时、重试、错误处理
- 提供健康检查接口

**核心类定义**:

```python
from pydantic import BaseModel, Field
from typing import Literal
import httpx
from core.settings import settings
from external_services.exceptions import NLUServiceError, ServiceUnavailableError

# === Pydantic 模型定义 ===

class NLURequest(BaseModel):
    """NLU 服务请求模型"""
    text: str = Field(..., description="用户输入的自然语言文本")
    session_id: str | None = Field(None, description="会话 ID, 用于维持对话上下文")


class NLUResponse(BaseModel):
    """NLU 服务响应模型"""
    session_id: str = Field(..., description="会话 ID")
    type: Literal["itinerary", "recommendation"] = Field(..., description="任务类型")
    status: Literal["complete", "incomplete"] = Field(..., description="完成状态")
    reply: str = Field(..., description="格式化的自然语言回复 (Markdown)")


# === NLU 客户端 ===

class NLUClient:
    """NLU 服务客户端"""

    def __init__(
        self,
        base_url: str = "http://localhost:8010",
        timeout: float = 30.0,
        max_retries: int = 1,
    ):
        """
        初始化 NLU 客户端

        Args:
            base_url: NLU 服务地址
            timeout: 请求超时时间 (秒)
            max_retries: 最大重试次数
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self):
        """异步上下文管理器入口"""
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(self.timeout),
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self._client:
            await self._client.aclose()

    async def call_nlu(
        self,
        text: str,
        session_id: str | None = None,
    ) -> NLUResponse:
        """
        调用 NLU 服务 (/nlu/simple 接口)

        Args:
            text: 用户输入的自然语言文本
            session_id: 会话 ID (可选)

        Returns:
            NLUResponse: NLU 服务响应

        Raises:
            ServiceUnavailableError: NLU 服务不可达
            NLUServiceError: NLU 服务返回错误
        """
        if not self._client:
            raise RuntimeError("NLUClient must be used as async context manager")

        request_data = NLURequest(text=text, session_id=session_id)

        try:
            response = await self._client.post(
                "/nlu/simple",
                json=request_data.model_dump(exclude_none=True),
            )
            response.raise_for_status()

            # 解析响应
            data = response.json()
            return NLUResponse(**data)

        except httpx.TimeoutException as e:
            raise ServiceUnavailableError(
                f"NLU service timeout after {self.timeout}s"
            ) from e

        except httpx.ConnectError as e:
            raise ServiceUnavailableError(
                f"Cannot connect to NLU service at {self.base_url}"
            ) from e

        except httpx.HTTPStatusError as e:
            raise NLUServiceError(
                f"NLU service returned error: {e.response.status_code} - {e.response.text}"
            ) from e

        except Exception as e:
            raise NLUServiceError(f"Unexpected error calling NLU service: {e}") from e

    async def health_check(self) -> bool:
        """
        检查 NLU 服务健康状态

        Returns:
            bool: True 表示服务正常, False 表示服务异常
        """
        if not self._client:
            raise RuntimeError("NLUClient must be used as async context manager")

        try:
            response = await self._client.get("/health", timeout=5.0)
            return response.status_code == 200
        except Exception:
            return False


# === 工厂函数 ===

def get_nlu_client() -> NLUClient:
    """
    获取 NLU 客户端实例 (根据配置创建)

    Returns:
        NLUClient: NLU 客户端实例
    """
    return NLUClient(
        base_url=settings.NLU_SERVICE_URL,
        timeout=settings.NLU_TIMEOUT,
        max_retries=settings.NLU_MAX_RETRIES,
    )
```

**设计要点**:

1. **异步上下文管理器**: 使用 `async with` 模式管理 HTTP 连接池生命周期
2. **Pydantic 模型**: 强类型保证，自动验证和序列化
3. **异常分类**: 区分服务不可达 (`ServiceUnavailableError`) 和业务错误 (`NLUServiceError`)
4. **健康检查**: 提供独立的健康检查方法，用于启动时验证
5. **可配置性**: 通过全局配置 (`settings`) 管理参数

#### 2.1.2 RAG Client

**文件位置**: `backend/src/external_services/rag_client.py`

**设计**: 与 NLU Client 类似，暂时可选实现 (因为 NLU 内部已集成 RAG)

```python
class RAGRequest(BaseModel):
    """RAG 服务请求模型"""
    query: str = Field(..., description="搜索查询")
    city: str | None = Field(None, description="城市过滤 (可选)")
    top_k: int = Field(5, description="返回结果数量")


class RAGResult(BaseModel):
    """单个检索结果"""
    id: str
    city: str
    title: str
    content: str
    score: float
    url: str | None = None
    source_file: str | None = None
    chunk_index: int | None = None


class RAGResponse(BaseModel):
    """RAG 服务响应模型"""
    contexts: str = Field(..., description="拼接的上下文")
    results: list[RAGResult] = Field(..., description="检索结果列表")


class RAGClient:
    """RAG 服务客户端"""
    # 实现与 NLUClient 类似
    pass
```

#### 2.1.3 异常定义

**文件位置**: `backend/src/external_services/exceptions.py`

```python
class ExternalServiceError(Exception):
    """外部服务异常基类"""
    pass


class ServiceUnavailableError(ExternalServiceError):
    """服务不可达异常 (连接失败/超时)"""
    pass


class NLUServiceError(ExternalServiceError):
    """NLU 服务业务异常 (返回错误响应)"""
    pass


class RAGServiceError(ExternalServiceError):
    """RAG 服务业务异常"""
    pass
```

### 2.2 Agent 层

#### 2.2.1 Travel Planner Agent

**文件位置**: `backend/src/agents/travel_planner.py`

**职责**:

- 接收用户的旅行规划请求
- 优先调用 NLU 服务获取智能响应
- 在 NLU 失败时降级到 Research-Assistant
- 管理会话状态和对话历史

**核心架构**:

```python
from __future__ import annotations

from typing import Literal, cast
from langgraph.graph import StateGraph, END, MessagesState
from langgraph.types import Command
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from agents.research_assistant import AgentState, get_agent as get_research_assistant
from external_services.nlu_client import get_nlu_client, NLUResponse
from external_services.exceptions import ServiceUnavailableError, NLUServiceError
from agents.timestamp import add_timestamp_to_message
from core.logging_config import logger

# === 状态定义 ===

class TravelPlannerState(MessagesState, total=False):
    """Travel Planner Agent 状态"""
    nlu_response: NLUResponse | None  # NLU 服务响应 (可选)
    fallback_triggered: bool          # 是否触发兜底机制
    error_message: str | None         # 错误信息 (用于日志)


# === 节点实现 ===

async def call_nlu_service(
    state: TravelPlannerState,
    config: RunnableConfig,
) -> TravelPlannerState:
    """
    调用 NLU 服务节点

    Args:
        state: 当前状态
        config: 运行配置

    Returns:
        更新后的状态
    """
    # 获取用户最后一条消息
    messages = state["messages"]
    if not messages:
        logger.error("TravelPlanner: No messages in state")
        return {
            "fallback_triggered": True,
            "error_message": "No input message",
        }

    last_message = messages[-1]
    if not isinstance(last_message, HumanMessage):
        logger.error(f"TravelPlanner: Last message is not HumanMessage: {type(last_message)}")
        return {
            "fallback_triggered": True,
            "error_message": "Invalid message type",
        }

    user_input = str(last_message.content)

    # 获取 session_id (使用 thread_id)
    session_id = config.get("configurable", {}).get("thread_id")

    logger.info(f"TravelPlanner: Calling NLU service with session_id={session_id}")

    try:
        # 调用 NLU 服务
        async with get_nlu_client() as nlu_client:
            nlu_response = await nlu_client.call_nlu(
                text=user_input,
                session_id=session_id,
            )

        logger.info(
            f"TravelPlanner: NLU response received - "
            f"type={nlu_response.type}, status={nlu_response.status}"
        )

        # 将 NLU 的回复转换为 AIMessage
        ai_message = AIMessage(content=nlu_response.reply)
        ai_message = add_timestamp_to_message(ai_message)

        # 检查是否需要追问 (status=incomplete)
        if nlu_response.status == "incomplete":
            logger.warning(
                f"TravelPlanner: NLU returned incomplete status, "
                f"reply contains follow-up questions"
            )
            # 目前 NLU 的追问功能有 BUG, 但仍然返回 incomplete 的回复
            # 这里我们直接返回 NLU 的回复, 让用户补充信息

        return {
            "messages": [ai_message],
            "nlu_response": nlu_response,
            "fallback_triggered": False,
        }

    except ServiceUnavailableError as e:
        logger.error(f"TravelPlanner: NLU service unavailable - {e}")
        return {
            "fallback_triggered": True,
            "error_message": str(e),
        }

    except NLUServiceError as e:
        logger.error(f"TravelPlanner: NLU service error - {e}")
        return {
            "fallback_triggered": True,
            "error_message": str(e),
        }

    except Exception as e:
        logger.error(f"TravelPlanner: Unexpected error - {e}", exc_info=True)
        return {
            "fallback_triggered": True,
            "error_message": str(e),
        }


async def fallback_to_research_assistant(
    state: TravelPlannerState,
    config: RunnableConfig,
) -> TravelPlannerState:
    """
    兜底节点: 降级到 Research-Assistant

    Args:
        state: 当前状态
        config: 运行配置

    Returns:
        更新后的状态
    """
    logger.info("TravelPlanner: Fallback triggered, calling Research-Assistant")

    # 获取 Research-Assistant Agent
    research_agent = get_research_assistant("research-assistant")

    # 调用 Research-Assistant (非流式)
    # 注意: 这里我们直接调用, 不使用 astream, 因为 StateGraph 会处理流式
    result = await research_agent.ainvoke(state, config)

    # 返回 Research-Assistant 的输出
    return {
        "messages": result.get("messages", []),
        "fallback_triggered": True,
    }


# === 条件边 ===

def should_fallback(state: TravelPlannerState) -> Literal["fallback", "done"]:
    """
    判断是否需要兜底

    Args:
        state: 当前状态

    Returns:
        "fallback" 表示需要兜底, "done" 表示正常结束
    """
    return "fallback" if state.get("fallback_triggered", False) else "done"


# === StateGraph 构建 ===

def build_travel_planner() -> StateGraph:
    """
    构建 Travel Planner Agent 状态图

    Returns:
        CompiledStateGraph: 编译后的状态图
    """
    agent = StateGraph(TravelPlannerState)

    # 添加节点
    agent.add_node("call_nlu_service", call_nlu_service)
    agent.add_node("fallback_to_research_assistant", fallback_to_research_assistant)

    # 设置入口
    agent.set_entry_point("call_nlu_service")

    # 添加条件边
    agent.add_conditional_edges(
        "call_nlu_service",
        should_fallback,
        {
            "fallback": "fallback_to_research_assistant",
            "done": END,
        },
    )

    # fallback 节点执行后结束
    agent.add_edge("fallback_to_research_assistant", END)

    return agent.compile()


# === 导出 ===

travel_planner = build_travel_planner()
```

**设计要点**:

1. **清晰的状态定义**: `TravelPlannerState` 继承 `MessagesState`, 添加 NLU 特有字段
2. **异常驱动的兜底**: 捕获 `ServiceUnavailableError` 和 `NLUServiceError` 触发兜底
3. **会话 ID 映射**: 直接使用 LangGraph 的 `thread_id` 作为 NLU 的 `session_id`
4. **格式转换**: 将 NLU 的 Markdown 回复包装为 `AIMessage`
5. **日志记录**: 记录关键路径和错误信息
6. **兜底调用**: 直接调用 `research_assistant.ainvoke()`, 不重新构建状态图

#### 2.2.2 Agent 注册

**文件位置**: `backend/src/agents/agents.py` (修改)

```python
from agents.travel_planner import travel_planner

# 在 agents 字典中添加
agents: dict[str, Agent] = {
    "chatbot": Agent(description="A simple chatbot.", graph=chatbot),
    "research-assistant": Agent(
        description="A research assistant with web search and calculator.",
        graph=research_assistant
    ),
    "rag-assistant": Agent(
        description="A RAG assistant with access to information in a database.",
        graph=rag_assistant
    ),
    "travel-planner": Agent(  # 新增
        description="A travel planner powered by NLU/RAG, with fallback to research assistant.",
        graph=travel_planner
    ),
    # ... 其他 Agent
}

# 可选: 更新默认 Agent
# DEFAULT_AGENT = "travel-planner"  # 测试通过后可切换
```

### 2.3 配置层

**文件位置**: `backend/src/core/settings.py` (修改)

```python
class Settings(BaseSettings):
    # ... 现有配置 ...

    # === NLU 服务配置 ===
    NLU_SERVICE_URL: str = "http://localhost:8010"
    NLU_TIMEOUT: float = 30.0
    NLU_MAX_RETRIES: int = 1
    ENABLE_NLU_FALLBACK: bool = True  # 是否启用兜底机制

    # === RAG 服务配置 ===
    RAG_SERVICE_URL: str = "http://localhost:8001"
    RAG_TIMEOUT: float = 10.0
    RAG_MAX_RETRIES: int = 1
```

### 2.4 路由层

**文件位置**: `backend/src/service/planner_routes.py` (可能需要微调)

**选项一**: 保持现有路由不变, 只切换默认 Agent

```python
# 在 agents.py 中修改
DEFAULT_AGENT = "travel-planner"
```

**选项二**: 添加新路由用于测试

```python
@planner_router.post("/plan/nlu/stream")
async def plan_nlu_stream(
    request: PlanRequest,
    current_user: Annotated[User, Depends(current_active_user)],
    session: AsyncSession = Depends(get_async_session),
) -> StreamingResponse:
    """
    NLU 驱动的行程规划 (流式响应)

    使用 travel-planner Agent
    """
    async def generate_events() -> AsyncGenerator[str, None]:
        thread_id = await get_or_create_main_thread(current_user, session)
        agent = get_agent("travel-planner")  # 强制使用 travel-planner

        # ... 其余逻辑与 plan_stream() 相同 ...

    return StreamingResponse(
        generate_events(),
        media_type="text/event-stream",
    )
```

**推荐**: 先使用选项二测试, 验证通过后切换到选项一。

## 三、数据流详解

### 3.1 正常流程 (NLU 成功)

```md
1. 用户输入
   "规划一个4天的Paris行程，预算8000元，一个成人，下周去，从上海出发"

2. Frontend → Backend API
   POST /planner/plan/stream
   {
       "prompt": "...",
   }

3. planner_routes.py
   - 认证: current_active_user
   - 获取: thread_id = user.main_thread_id
   - 调用: agent.astream({"messages": [HumanMessage(...)]}, config)

4. Travel Planner Agent
   a. 节点: call_nlu_service
      - 提取: user_input, session_id=thread_id
      - 调用: NLUClient.call_nlu(user_input, session_id)

5. NLU Service
   - 接收: {"text": "...", "session_id": "..."}
   - 内部: 意图识别 → RAG 检索 → 行程生成 → Verifier 审查
   - 返回: {
       "session_id": "...",
       "type": "itinerary",
       "status": "complete",
       "reply": "# 4天巴黎行程规划\n\n## 第一天\n..."
     }

6. call_nlu_service 节点
   - 转换: NLUResponse → AIMessage(content=reply)
   - 添加: 时间戳
   - 返回: {"messages": [AIMessage], "nlu_response": ..., "fallback_triggered": False}

7. 条件边: should_fallback
   - 判断: fallback_triggered == False
   - 路由: → END

8. StateGraph
   - stream_mode=["updates", "messages"]
   - 生成: AIMessageChunk (如果支持流式)

9. planner_routes.py
   - 解析: stream_event
   - 生成: SSE 事件
     data: {"type": "token", "delta": "# 4天巴黎行程规划\n"}
     data: {"type": "token", "delta": "## 第一天\n"}
     ...
     data: {"type": "end", "messageId": "...", "metadata": {...}}
     data: [DONE]

10. Frontend
    - 接收: SSE 事件
    - 渲染: Markdown 内容
```

### 3.2 兜底流程 (NLU 失败)

```md
1. 用户输入 (同上)

2-4. 同正常流程

5. NLU Service
   - 情况 A: 服务不可达 (连接失败/超时)
   - 情况 B: 服务返回错误 (500 Internal Server Error)
   - 情况 C: 响应格式异常

6. call_nlu_service 节点
   - 捕获: ServiceUnavailableError / NLUServiceError
   - 日志: logger.error(...)
   - 返回: {"fallback_triggered": True, "error_message": "..."}

7. 条件边: should_fallback
   - 判断: fallback_triggered == True
   - 路由: → fallback_to_research_assistant

8. fallback_to_research_assistant 节点
   - 获取: research_agent = get_agent("research-assistant")
   - 调用: research_agent.ainvoke(state, config)
   - 执行: Research-Assistant 的完整流程
     - guard_input (安全检测)
     - model (LLM 推理)
     - tools (DuckDuckGo 搜索)
     - model (处理搜索结果)
   - 返回: {"messages": [AIMessage], "fallback_triggered": True}

9. StateGraph
   - 继续流式输出 Research-Assistant 的响应

10. planner_routes.py
    - 生成: SSE 事件 (与正常流程相同)

11. Frontend
    - 用户感知: 响应内容来自 Web Search (而非 NLU)
    - 无需特殊处理: 响应格式完全一致
```

### 3.3 会话管理

```txt
┌──────────────────────────────────────────────────────────────┐
│  User Table (PostgreSQL)                                     │
├──────────────────────────────────────────────────────────────┤
│  id: UUID                                                    │
│  email: str                                                  │
│  main_thread_id: str  ◄──┐ (LangGraph Thread ID)            │
└───────────────────────────┼──────────────────────────────────┘
                            │
                            │ 映射关系:
                            │ LangGraph thread_id ≡ NLU session_id
                            │
┌───────────────────────────┼──────────────────────────────────┐
│  LangGraph Checkpointer   │                                  │
├───────────────────────────┼──────────────────────────────────┤
│  thread_id: str  ◄────────┘                                  │
│  checkpoint_id: UUID                                         │
│  state: JSON (包含 messages)                                 │
└──────────────────────────────────────────────────────────────┘
                            │
                            │ 传递给 NLU
                            ↓
┌──────────────────────────────────────────────────────────────┐
│  NLU Service                                                 │
├──────────────────────────────────────────────────────────────┤
│  session_id: str  (from thread_id)                           │
│  conversation_history: list[Message]                         │
└──────────────────────────────────────────────────────────────┘
```

**设计优势**:

1. **无需额外映射表**: 直接使用 `thread_id` 作为 `session_id`
2. **自动隔离**: LangGraph 的 Checkpointer 已实现多用户隔离
3. **一致性保证**: 同一个 `thread_id` 在 Backend 和 NLU 中表示同一会话

### 3.4 错误处理流程

```txt
┌─────────────────────────────────────────────────────────────┐
│  错误类型分类                                               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. ServiceUnavailableError (服务不可达)                   │
│     - httpx.ConnectError (连接失败)                        │
│     - httpx.TimeoutException (超时)                        │
│     → 触发兜底                                             │
│                                                             │
│  2. NLUServiceError (NLU 业务错误)                         │
│     - httpx.HTTPStatusError (4xx/5xx)                      │
│     - Pydantic ValidationError (响应格式错误)              │
│     → 触发兜底                                             │
│                                                             │
│  3. NLU incomplete 状态                                    │
│     - status="incomplete"                                  │
│     - reply 包含追问问题                                   │
│     → 暂不触发兜底, 返回追问内容                           │
│     → 可选: 如果追问次数过多, 触发兜底                     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**日志记录策略**:

```python
# 正常调用
logger.info(
    f"TravelPlanner: NLU response - "
    f"type={nlu_response.type}, status={nlu_response.status}, "
    f"session_id={nlu_response.session_id}"
)

# 服务不可达
logger.error(
    f"TravelPlanner: NLU service unavailable, fallback triggered - {error}",
    extra={"session_id": session_id, "user_id": user_id}
)

# 兜底触发
logger.warning(
    f"TravelPlanner: Fallback to Research-Assistant, "
    f"reason={error_message}, session_id={session_id}"
)

# 兜底完成
logger.info(
    f"TravelPlanner: Fallback completed, "
    f"session_id={session_id}"
)
```

## 四、关键技术决策

### 4.1 为什么不使用 LangGraph 的 @entrypoint?

**决策**: 使用 `StateGraph` 而非 `@entrypoint`

**理由**:

1. **更清晰的兜底逻辑**: 通过条件边实现兜底路由, 逻辑直观
2. **状态管理**: 需要记录 `fallback_triggered` 等状态, `StateGraph` 更适合
3. **与现有 Agent 一致**: `research_assistant` 使用 `StateGraph`, 保持一致性
4. **可扩展性**: 未来可能添加更多节点 (如重试逻辑、缓存查询等)

### 4.2 为什么不使用 ToolNode 调用 NLU?

**决策**: 直接在节点中调用 NLU Client, 而非将 NLU 封装为 Tool

**理由**:

1. **NLU 不是 Tool**: NLU 是核心逻辑, 不是 LLM 的辅助工具
2. **避免额外 LLM 调用**: 使用 Tool 需要先调用 LLM 生成 `tool_calls`, 增加延迟和成本
3. **更直接的控制**: 直接调用 NLU, 便于错误处理和兜底
4. **流式响应**: NLU 返回完整 Markdown, 无法实现 token-level 的流式 (除非 NLU 支持 SSE)

### 4.3 为什么直接使用 thread_id 作为 session_id?

**决策**: `thread_id` ≡ `session_id`, 不做额外映射

**理由**:

1. **简化设计**: 避免维护额外的映射表
2. **一致性**: 同一个标识符在 Backend 和 NLU 中表示同一会话
3. **无冲突**: `thread_id` 是 UUID, 全局唯一, 不会冲突
4. **自动隔离**: LangGraph Checkpointer 已实现基于 `thread_id` 的隔离

### 4.4 为什么不实现 NLU 的流式响应?

**决策**: 暂不实现 token-level 的流式响应

**理由**:

1. **NLU 不支持**: NLU 服务返回完整的 Markdown, 不支持 SSE 流式
2. **后端模拟困难**: 在 Backend 模拟流式需要解析 Markdown 并逐字发送, 复杂且不自然
3. **用户体验可接受**: 完整响应的延迟在 5s 以内, 可接受
4. **未来可优化**: 如果 NLU 支持 SSE, 可在客户端层面直接透传

**可选的优化方案** (后续实现):

- 在 Frontend 显示 Loading 动画
- 或在 Backend 模拟流式: 按行或按段落发送 Markdown

## 五、性能与可靠性

### 5.1 超时配置

| 服务 | 默认超时 | 说明 |
|------|----------|------|
| NLU Service | 30s | 行程生成较慢, 需要较长超时 |
| RAG Service | 10s | 向量检索较快 |
| Research-Assistant | 无限制 | LangGraph 自行控制 |

**超时触发兜底**:

```python
try:
    response = await nlu_client.call_nlu(text, session_id)
except httpx.TimeoutException:
    # 触发兜底
    logger.error("NLU timeout, fallback to Research-Assistant")
    return {"fallback_triggered": True}
```

### 5.2 重试策略

**当前设计**: 不重试 NLU 调用, 直接兜底

**理由**:

1. **用户体验**: 重试会增加延迟, 不如直接兜底
2. **服务稳定性**: 如果 NLU 不可达, 重试多次仍会失败
3. **简化逻辑**: 避免复杂的重试状态管理

**可选优化** (后续实现):

- 健康检查: 启动时检查 NLU 是否可用, 如不可用则直接跳过 NLU
- 熔断器: 如果 NLU 连续失败 N 次, 暂时禁用 NLU (一段时间后重试)

### 5.3 缓存策略

**短期不实现**, 理由:

1. **会话依赖**: NLU 响应依赖会话历史, 不适合缓存
2. **动态内容**: 行程规划可能每次都不同 (时间、价格等)
3. **复杂度**: 缓存失效策略复杂

**长期可考虑**:

- 缓存常见查询 (如 "推荐巴黎景点")
- 缓存 RAG 检索结果 (城市 + 关键词)

### 5.4 监控指标

**关键指标**:

1. **NLU 调用成功率**: `nlu_call_success / nlu_call_total`
2. **兜底触发率**: `fallback_triggered / total_requests`
3. **NLU 平均响应时间**: `avg(nlu_response_time)`
4. **端到端响应时间**: `avg(total_response_time)`

**日志聚合**:

```python
# 在每次调用后记录
logger.info(
    "TravelPlanner metrics",
    extra={
        "nlu_success": not fallback_triggered,
        "nlu_response_time": response_time,
        "session_id": session_id,
        "user_id": user_id,
    }
)
```

## 六、测试策略

### 6.1 单元测试

**测试文件**: `backend/tests/test_nlu_client.py`

```python
import pytest
from external_services.nlu_client import NLUClient, NLURequest, NLUResponse
from external_services.exceptions import ServiceUnavailableError

@pytest.mark.asyncio
async def test_nlu_client_success(httpx_mock):
    """测试 NLU 客户端成功调用"""
    httpx_mock.add_response(
        method="POST",
        url="http://localhost:8010/nlu/simple",
        json={
            "session_id": "test-session",
            "type": "itinerary",
            "status": "complete",
            "reply": "# 巴黎行程规划\n...",
        },
    )

    async with NLUClient() as client:
        response = await client.call_nlu("规划巴黎行程")
        assert response.type == "itinerary"
        assert response.status == "complete"

@pytest.mark.asyncio
async def test_nlu_client_timeout(httpx_mock):
    """测试 NLU 客户端超时"""
    httpx_mock.add_exception(httpx.TimeoutException("Timeout"))

    async with NLUClient(timeout=1.0) as client:
        with pytest.raises(ServiceUnavailableError):
            await client.call_nlu("规划巴黎行程")
```

### 6.2 集成测试

**测试文件**: `backend/tests/test_travel_planner.py`

```python
import pytest
from agents.travel_planner import travel_planner
from langchain_core.messages import HumanMessage

@pytest.mark.asyncio
async def test_travel_planner_nlu_success(monkeypatch):
    """测试 Travel Planner 调用 NLU 成功"""
    # Mock NLU 客户端
    # ...

    result = await travel_planner.ainvoke({
        "messages": [HumanMessage(content="规划巴黎行程")]
    })

    assert len(result["messages"]) > 0
    assert not result.get("fallback_triggered", False)

@pytest.mark.asyncio
async def test_travel_planner_fallback(monkeypatch):
    """测试 Travel Planner 兜底机制"""
    # Mock NLU 客户端抛出异常
    # ...

    result = await travel_planner.ainvoke({
        "messages": [HumanMessage(content="规划巴黎行程")]
    })

    assert result.get("fallback_triggered", False) == True
```

### 6.3 端到端测试

**测试流程**:

1. **启动服务**:

   ```bash
   # 启动 NLU 服务
   cd NLU_module && python api/fastapi_server.py

   # 启动 RAG 服务
   cd RAG_chroma && python api_server.py

   # 启动 Backend
   cd backend && python src/run_service.py
   ```

2. **正常场景测试**:

   ```bash
   curl -X POST "http://localhost:8080/planner/plan/stream" \
     -H "Cookie: yata_auth=..." \
     -H "Content-Type: application/json" \
     -d '{"prompt": "规划一个4天的Paris行程，预算8000元，一个成人，下周去，从上海出发"}'
   ```

3. **兜底场景测试**:

   ```bash
   # 先停止 NLU 服务
   # 然后发送同样的请求, 观察是否触发兜底
   ```

4. **验证点**:
   - [ ] 正常场景: 返回 NLU 生成的行程规划
   - [ ] 兜底场景: 返回 Research-Assistant 的响应
   - [ ] 流式响应: SSE 事件正常推送
   - [ ] 会话管理: 多轮对话上下文正确

---

**文档版本**: v1.0
**编写日期**: 2025-11-14
**作者**: Claude Code
**状态**: 待审核
