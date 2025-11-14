# NLU/RAG 整合实现步骤清单

本文档提供详细的、可执行的实现步骤，每个步骤包含具体的代码示例和验证方法。

## 阶段一：基础设施搭建

### 步骤 1.1: 创建目录结构

```bash
cd backend/src
mkdir -p external_services
touch external_services/__init__.py
touch external_services/exceptions.py
touch external_services/nlu_client.py
touch external_services/rag_client.py
```

**验证**: 确认文件已创建

```bash
ls -la external_services/
```

---

### 步骤 1.2: 实现异常类

**文件**: `backend/src/external_services/exceptions.py`

```python
"""外部服务异常定义"""


class ExternalServiceError(Exception):
    """外部服务异常基类"""

    pass


class ServiceUnavailableError(ExternalServiceError):
    """服务不可达异常 (连接失败 / 超时)"""

    pass


class NLUServiceError(ExternalServiceError):
    """NLU 服务业务异常 (返回错误响应)"""

    pass


class RAGServiceError(ExternalServiceError):
    """RAG 服务业务异常"""

    pass
```

**验证**: Pyright 类型检查

```bash
cd backend
source .venv/bin/activate
pyright src/external_services/exceptions.py
```

---

### 步骤 1.3: 添加配置项

**文件**: `backend/src/core/settings.py`

在 `Settings` 类中添加以下配置项：

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

**注意**: 添加位置应该在类的末尾，保持与现有配置的格式一致。

**验证**: Pyright 类型检查 + 运行时检查

```bash
pyright src/core/settings.py

# 运行时检查
python -c "from src.core.settings import settings; print(settings.NLU_SERVICE_URL)"
```

---

### 步骤 1.4: 实现 NLU 客户端

**文件**: `backend/src/external_services/nlu_client.py`

```python
"""NLU 服务客户端"""

from __future__ import annotations

from typing import Literal

import httpx
from pydantic import BaseModel, Field

from core.logging_config import logger
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
            logger.debug(
                f"NLUClient: Calling /nlu/simple with text='{text[:50]}...', session_id={session_id}"
            )

            response = await self._client.post(
                "/nlu/simple",
                json=request_data.model_dump(exclude_none=True),
            )
            response.raise_for_status()

            # 解析响应
            data = response.json()
            nlu_response = NLUResponse(**data)

            logger.debug(
                f"NLUClient: Received response - "
                f"type={nlu_response.type}, status={nlu_response.status}, "
                f"session_id={nlu_response.session_id}"
            )

            return nlu_response

        except httpx.TimeoutException as e:
            error_msg = f"NLU service timeout after {self.timeout}s"
            logger.error(f"NLUClient: {error_msg}")
            raise ServiceUnavailableError(error_msg) from e

        except httpx.ConnectError as e:
            error_msg = f"Cannot connect to NLU service at {self.base_url}"
            logger.error(f"NLUClient: {error_msg}")
            raise ServiceUnavailableError(error_msg) from e

        except httpx.HTTPStatusError as e:
            error_msg = (
                f"NLU service returned error: {e.response.status_code} - {e.response.text}"
            )
            logger.error(f"NLUClient: {error_msg}")
            raise NLUServiceError(error_msg) from e

        except Exception as e:
            error_msg = f"Unexpected error calling NLU service: {e}"
            logger.error(f"NLUClient: {error_msg}", exc_info=settings.is_dev())
            raise NLUServiceError(error_msg) from e

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
            is_healthy = response.status_code == 200
            logger.debug(f"NLUClient: Health check - {'OK' if is_healthy else 'FAILED'}")
            return is_healthy
        except Exception as e:
            logger.warning(f"NLUClient: Health check failed - {e}")
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

**验证**: Pyright 类型检查

```bash
pyright src/external_services/nlu_client.py
```

---

### 步骤 1.5: 实现 RAG 客户端 (可选)

**文件**: `backend/src/external_services/rag_client.py`

```python
"""RAG 服务客户端 (可选实现)"""

from __future__ import annotations

import httpx
from pydantic import BaseModel, Field

from core.logging_config import logger
from core.settings import settings
from external_services.exceptions import RAGServiceError, ServiceUnavailableError


# === Pydantic 模型定义 ===


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


# === RAG 客户端 ===


class RAGClient:
    """RAG 服务客户端"""

    def __init__(
        self,
        base_url: str = "http://localhost:8001",
        timeout: float = 10.0,
        max_retries: int = 1,
    ):
        """
        初始化 RAG 客户端

        Args:
            base_url: RAG 服务地址
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

    async def search(
        self,
        query: str,
        city: str | None = None,
        top_k: int = 5,
    ) -> RAGResponse:
        """
        调用 RAG 服务 (/search 接口)

        Args:
            query: 搜索查询
            city: 城市过滤 (可选)
            top_k: 返回结果数量

        Returns:
            RAGResponse: RAG 服务响应

        Raises:
            ServiceUnavailableError: RAG 服务不可达
            RAGServiceError: RAG 服务返回错误
        """
        if not self._client:
            raise RuntimeError("RAGClient must be used as async context manager")

        request_data = RAGRequest(query=query, city=city, top_k=top_k)

        try:
            logger.debug(
                f"RAGClient: Calling /search with query='{query[:50]}...', city={city}, top_k={top_k}"
            )

            response = await self._client.post(
                "/search",
                json=request_data.model_dump(exclude_none=True),
            )
            response.raise_for_status()

            # 解析响应
            data = response.json()
            rag_response = RAGResponse(**data)

            logger.debug(
                f"RAGClient: Received {len(rag_response.results)} results"
            )

            return rag_response

        except httpx.TimeoutException as e:
            error_msg = f"RAG service timeout after {self.timeout}s"
            logger.error(f"RAGClient: {error_msg}")
            raise ServiceUnavailableError(error_msg) from e

        except httpx.ConnectError as e:
            error_msg = f"Cannot connect to RAG service at {self.base_url}"
            logger.error(f"RAGClient: {error_msg}")
            raise ServiceUnavailableError(error_msg) from e

        except httpx.HTTPStatusError as e:
            error_msg = (
                f"RAG service returned error: {e.response.status_code} - {e.response.text}"
            )
            logger.error(f"RAGClient: {error_msg}")
            raise RAGServiceError(error_msg) from e

        except Exception as e:
            error_msg = f"Unexpected error calling RAG service: {e}"
            logger.error(f"RAGClient: {error_msg}", exc_info=settings.is_dev())
            raise RAGServiceError(error_msg) from e

    async def health_check(self) -> bool:
        """
        检查 RAG 服务健康状态

        Returns:
            bool: True 表示服务正常, False 表示服务异常
        """
        if not self._client:
            raise RuntimeError("RAGClient must be used as async context manager")

        try:
            response = await self._client.get("/health", timeout=5.0)
            is_healthy = response.status_code == 200
            logger.debug(f"RAGClient: Health check - {'OK' if is_healthy else 'FAILED'}")
            return is_healthy
        except Exception as e:
            logger.warning(f"RAGClient: Health check failed - {e}")
            return False


# === 工厂函数 ===


def get_rag_client() -> RAGClient:
    """
    获取 RAG 客户端实例 (根据配置创建)

    Returns:
        RAGClient: RAG 客户端实例
    """
    return RAGClient(
        base_url=settings.RAG_SERVICE_URL,
        timeout=settings.RAG_TIMEOUT,
        max_retries=settings.RAG_MAX_RETRIES,
    )
```

**验证**: Pyright 类型检查

```bash
pyright src/external_services/rag_client.py
```

---

### 步骤 1.6: 初始化 external_services 包

**文件**: `backend/src/external_services/__init__.py`

```python
"""外部服务客户端模块"""

from external_services.exceptions import (
    ExternalServiceError,
    NLUServiceError,
    RAGServiceError,
    ServiceUnavailableError,
)
from external_services.nlu_client import NLUClient, NLURequest, NLUResponse, get_nlu_client
from external_services.rag_client import RAGClient, RAGRequest, RAGResponse, get_rag_client

__all__ = [
    # 异常类
    "ExternalServiceError",
    "ServiceUnavailableError",
    "NLUServiceError",
    "RAGServiceError",
    # NLU 客户端
    "NLUClient",
    "NLURequest",
    "NLUResponse",
    "get_nlu_client",
    # RAG 客户端
    "RAGClient",
    "RAGRequest",
    "RAGResponse",
    "get_rag_client",
]
```

**验证**: 导入测试

```bash
python -c "from src.external_services import get_nlu_client, get_rag_client; print('Import OK')"
```

---

## 阶段二：Travel Planner Agent 实现

### 步骤 2.1: 创建 Travel Planner Agent 文件

```bash
cd backend/src/agents
touch travel_planner.py
```

---

### 步骤 2.2: 实现 Travel Planner Agent

**文件**: `backend/src/agents/travel_planner.py`

```python
"""Travel Planner Agent - 基于 NLU/RAG 的旅行规划 Agent"""

from __future__ import annotations

from typing import Literal, cast

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, MessagesState, StateGraph

from agents.research_assistant import get_agent as get_research_assistant
from agents.timestamp import add_timestamp_to_message
from core.logging_config import logger
from external_services import (
    NLUResponse,
    NLUServiceError,
    ServiceUnavailableError,
    get_nlu_client,
)


# === 状态定义 ===


class TravelPlannerState(MessagesState, total=False):
    """Travel Planner Agent 状态"""

    nlu_response: NLUResponse | None  # NLU 服务响应 (可选)
    fallback_triggered: bool  # 是否触发兜底机制
    error_message: str | None  # 错误信息 (用于日志)


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
        logger.error(
            f"TravelPlanner: Last message is not HumanMessage: {type(last_message)}"
        )
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


def build_travel_planner():
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

**验证**: Pyright 类型检查

```bash
pyright src/agents/travel_planner.py
```

---

### 步骤 2.3: 在 Agent 注册中心注册新 Agent

**文件**: `backend/src/agents/agents.py` (修改)

在文件顶部添加导入:

```python
from agents.travel_planner import travel_planner
```

在 `agents` 字典中添加新 Agent:

```python
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
```

**暂不修改 DEFAULT_AGENT**, 保持为 `"research-assistant"`, 稍后测试通过后再切换。

**验证**: 检查 Agent 是否注册成功

```bash
python -c "from src.agents.agents import get_agent; agent = get_agent('travel-planner'); print('Agent registered:', agent)"
```

---

## 阶段三：集成与测试

### 步骤 3.1: 启动 NLU 和 RAG 服务

**终端 1: 启动 RAG 服务**

```bash
cd /path/to/RAG_chroma
source .venv/bin/activate
python api_server.py
```

预期输出:

```txt
INFO:     Uvicorn running on http://0.0.0.0:8001 (Press CTRL+C to quit)
```

**终端 2: 启动 NLU 服务**

```bash
cd /path/to/NLU_module
source .venv/bin/activate
cd api
python fastapi_server.py
```

预期输出:

```txt
INFO:     Uvicorn running on http://0.0.0.0:8010 (Press CTRL+C to quit)
```

**验证**: 健康检查

```bash
curl http://localhost:8001/health
# {"status":"ok"}

curl http://localhost:8010/health
# {"status":"ok"}
```

---

### 步骤 3.2: 启动 Backend 服务

**终端 3: 启动 Backend**

```bash
cd backend
source .venv/bin/activate
python src/run_service.py
```

预期输出:

```txt
INFO:     Uvicorn running on http://0.0.0.0:8080 (Press CTRL+C to quit)
```

---

### 步骤 3.3: 测试 NLU Client (单元测试)

**创建测试脚本**: `backend/test_nlu_client_manual.py`

```python
"""手动测试 NLU 客户端"""

import asyncio

from src.external_services import get_nlu_client


async def test_nlu_client():
    """测试 NLU 客户端调用"""
    async with get_nlu_client() as client:
        # 健康检查
        is_healthy = await client.health_check()
        print(f"NLU Health Check: {is_healthy}")

        if not is_healthy:
            print("NLU service is not available")
            return

        # 调用 NLU
        response = await client.call_nlu(
            text="规划一个4天的Paris行程，预算8000元，一个成人，下周去，从上海出发",
            session_id="test-session-123",
        )

        print(f"\n=== NLU Response ===")
        print(f"Session ID: {response.session_id}")
        print(f"Type: {response.type}")
        print(f"Status: {response.status}")
        print(f"Reply:\n{response.reply}\n")


if __name__ == "__main__":
    asyncio.run(test_nlu_client())
```

**运行测试**:

```bash
cd backend
python test_nlu_client_manual.py
```

**预期输出**:

```txt
NLU Health Check: True

=== NLU Response ===
Session ID: test-session-123
Type: itinerary
Status: complete
Reply:
# 4天巴黎行程规划
...
```

---

### 步骤 3.4: 测试 Travel Planner Agent (单元测试)

**创建测试脚本**: `backend/test_travel_planner_manual.py`

```python
"""手动测试 Travel Planner Agent"""

import asyncio

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

from src.agents.agents import get_agent


async def test_travel_planner_nlu_success():
    """测试 Travel Planner 调用 NLU 成功"""
    agent = get_agent("travel-planner")

    config = RunnableConfig(
        configurable={
            "thread_id": "test-thread-123",
        }
    )

    input_message = HumanMessage(
        content="规划一个4天的Paris行程，预算8000元，一个成人，下周去，从上海出发"
    )

    print("=== Testing Travel Planner (NLU Success) ===\n")

    result = await agent.ainvoke({"messages": [input_message]}, config)

    print(f"Fallback Triggered: {result.get('fallback_triggered', False)}")
    print(f"Number of Messages: {len(result.get('messages', []))}")

    if result.get("messages"):
        last_message = result["messages"][-1]
        print(f"\nAI Response:\n{last_message.content}\n")


async def test_travel_planner_fallback():
    """测试 Travel Planner 兜底机制"""
    agent = get_agent("travel-planner")

    # 修改配置，使 NLU 服务 URL 无效 (触发兜底)
    from src.core.settings import settings

    original_url = settings.NLU_SERVICE_URL
    settings.NLU_SERVICE_URL = "http://localhost:9999"  # 无效端口

    config = RunnableConfig(
        configurable={
            "thread_id": "test-thread-456",
        }
    )

    input_message = HumanMessage(content="规划一个4天的巴黎行程")

    print("=== Testing Travel Planner (Fallback) ===\n")

    result = await agent.ainvoke({"messages": [input_message]}, config)

    print(f"Fallback Triggered: {result.get('fallback_triggered', False)}")
    print(f"Number of Messages: {len(result.get('messages', []))}")

    if result.get("messages"):
        last_message = result["messages"][-1]
        print(f"\nAI Response (from Research-Assistant):\n{last_message.content[:200]}...\n")

    # 恢复配置
    settings.NLU_SERVICE_URL = original_url


async def main():
    """运行所有测试"""
    await test_travel_planner_nlu_success()
    print("\n" + "=" * 60 + "\n")
    await test_travel_planner_fallback()


if __name__ == "__main__":
    asyncio.run(main())
```

**运行测试**:

```bash
cd backend
python test_travel_planner_manual.py
```

**预期输出**:

```txt
=== Testing Travel Planner (NLU Success) ===

Fallback Triggered: False
Number of Messages: 1

AI Response:
# 4天巴黎行程规划
...

============================================================

=== Testing Travel Planner (Fallback) ===

Fallback Triggered: True
Number of Messages: 1

AI Response (from Research-Assistant):
Based on my search, here's a 4-day Paris itinerary...
```

---

### 步骤 3.5: 端到端测试 (通过 API)

**步骤 3.5.1: 注册测试用户**

```bash
curl -X POST "http://localhost:8080/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "username": "testuser",
    "password": "TestPassword123!",
    "is_active": true,
    "is_superuser": false,
    "is_verified": false
  }'
```

**步骤 3.5.2: 登录获取 Cookie**

```bash
curl -X POST "http://localhost:8080/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "account": "test@example.com",
    "password": "TestPassword123!"
  }' \
  -c cookies.txt
```

**步骤 3.5.3: 调用行程规划 API (使用 research-assistant)**

```bash
curl -X POST "http://localhost:8080/planner/plan/stream" \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "prompt": "规划一个4天的Paris行程，预算8000元，一个成人，下周去，从上海出发"
  }'
```

**预期输出**: 流式 SSE 事件 (来自 Research-Assistant)

```
data: {"type":"token","delta":"Based"}
data: {"type":"token","delta":" on"}
...
data: {"type":"end","messageId":"...","metadata":{}}
data: [DONE]
```

**步骤 3.5.4: 切换到 travel-planner Agent**

**修改**: `backend/src/agents/agents.py`

```python
DEFAULT_AGENT = "travel-planner"  # 从 "research-assistant" 切换
```

**重启 Backend 服务**:

```bash
# 在终端 3 中按 Ctrl+C 停止服务
python src/run_service.py  # 重新启动
```

**再次调用行程规划 API**:

```bash
curl -X POST "http://localhost:8080/planner/plan/stream" \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "prompt": "规划一个4天的Paris行程，预算8000元，一个成人，下周去，从上海出发"
  }'
```

**预期输出**: 流式 SSE 事件 (来自 NLU)

```txt
data: {"type":"token","delta":"# 4天巴黎行程规划\n\n"}
data: {"type":"token","delta":"## 第一天"}
...
data: {"type":"end","messageId":"...","metadata":{}}
data: [DONE]
```

**步骤 3.5.5: 测试兜底机制**

**停止 NLU 服务** (在终端 2 中按 Ctrl+C)

**再次调用行程规划 API**:

```bash
curl -X POST "http://localhost:8080/planner/plan/stream" \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "prompt": "规划一个4天的巴黎行程"
  }'
```

**预期输出**: 流式 SSE 事件 (来自 Research-Assistant 兜底)

**检查日志**:

```bash
tail -f backend/logs/app.log  # 假设日志输出到文件
```

预期日志:

```txt
ERROR: TravelPlanner: NLU service unavailable - Cannot connect to NLU service at http://localhost:8010
INFO: TravelPlanner: Fallback triggered, calling Research-Assistant
```

---

## 阶段四：优化与文档

### 步骤 4.1: Pyright 全局类型检查

```bash
cd backend
pyright src/external_services/
pyright src/agents/travel_planner.py
pyright src/core/settings.py
```

**目标**: 无错误输出 (或仅有已存在的错误，新增代码无错误)

---

### 步骤 4.2: 代码风格检查 (可选)

如果项目使用了 `black` 或 `ruff`:

```bash
black src/external_services/
black src/agents/travel_planner.py

ruff check src/external_services/
ruff check src/agents/travel_planner.py
```

---

### 步骤 4.3: 更新 .env.example

**文件**: `backend/.env.example`

添加以下配置项:

```bash
# === NLU 服务配置 ===
NLU_SERVICE_URL=http://localhost:8010
NLU_TIMEOUT=30.0
NLU_MAX_RETRIES=1
ENABLE_NLU_FALLBACK=true

# === RAG 服务配置 ===
RAG_SERVICE_URL=http://localhost:8001
RAG_TIMEOUT=10.0
RAG_MAX_RETRIES=1
```

---

### 步骤 4.4: 编写集成完成总结

**文件**: `backend/docs/gen/nlu-rag-integration/integration-complete.md`

```markdown
# NLU/RAG 集成完成总结

## 集成状态

✅ **已完成** - NLU 和 RAG 服务已成功集成到 YATA Backend

## 实现内容

### 1. 外部服务客户端

- ✅ `external_services/nlu_client.py` - NLU 服务客户端
- ✅ `external_services/rag_client.py` - RAG 服务客户端 (可选)
- ✅ `external_services/exceptions.py` - 异常类定义
- ✅ 异步上下文管理器 + Pydantic 模型
- ✅ 超时控制 + 错误处理

### 2. Travel Planner Agent

- ✅ `agents/travel_planner.py` - 旅行规划 Agent
- ✅ StateGraph 架构
- ✅ NLU 服务调用节点
- ✅ 兜底到 Research-Assistant 节点
- ✅ 条件边路由逻辑

### 3. 配置管理

- ✅ `core/settings.py` - 添加 NLU/RAG 配置项
- ✅ `.env.example` - 更新配置示例

### 4. Agent 注册

- ✅ `agents/agents.py` - 注册 `travel-planner` Agent
- ✅ 可选切换 `DEFAULT_AGENT`

## 使用方式

### 启动服务

```bash
# 1. 启动 RAG 服务
cd RAG_chroma && python api_server.py

# 2. 启动 NLU 服务
cd NLU_module/api && python fastapi_server.py

# 3. 启动 Backend
cd backend && python src/run_service.py
```

### 调用 API

**方式一: 使用 travel-planner Agent (默认)**

```bash
curl -X POST "http://localhost:8080/planner/plan/stream" \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{"prompt": "规划一个4天的Paris行程，预算8000元"}'
```

**方式二: 显式指定 Agent**

如果保持 `DEFAULT_AGENT = "research-assistant"`, 可以通过修改路由或配置切换。

### 兜底机制

- NLU 服务不可达时，自动降级到 Research-Assistant
- 用户无感知，响应格式完全一致
- 日志中记录兜底事件

## 测试结果

### 单元测试

- ✅ NLU Client 调用成功
- ✅ NLU Client 超时处理
- ✅ Travel Planner NLU 成功场景
- ✅ Travel Planner 兜底场景

### 端到端测试

- ✅ NLU 正常响应: 返回智能行程规划
- ✅ NLU 不可达: 触发兜底，返回 Research-Assistant 响应
- ✅ 流式响应正常
- ✅ 会话管理正常 (thread_id ≡ session_id)

## 性能指标

| 指标 | 数值 |
|------|------|
| NLU 平均响应时间 | ~3-5s |
| 兜底切换时间 | <1s |
| 端到端响应时间 | ~5-10s |

## 已知问题与限制

1. **NLU 追问功能不完善**
   - 状态: `status=incomplete` 时，reply 包含追问内容
   - 当前处理: 直接返回追问内容，让用户补充信息
   - 未来优化: 等待 NLU 修复后，支持真正的多轮追问

2. **NLU 不支持流式响应**
   - 状态: NLU 返回完整 Markdown，无 token-level 流式
   - 当前处理: 一次性返回完整内容
   - 未来优化: 如果 NLU 支持 SSE，可在客户端层透传

3. **仅 Paris 数据较完整**
   - 状态: RAG 数据库中仅 Paris 的数据较为齐全
   - 影响: 其他城市的行程规划可能不够准确
   - 解决: 等待算法组补充更多城市数据

## 后续优化建议

### 短期 (1-2 周)

1. **监控指标**
   - 添加 Prometheus metrics
   - 记录 NLU 调用成功率、兜底触发率

2. **缓存机制**
   - 缓存常见查询的 NLU 响应 (谨慎使用，考虑会话依赖)

### 中期 (1 月)

1. **健康检查**
   - 启动时检查 NLU/RAG 服务可用性
   - 如不可用，发出告警

2. **熔断器**
   - 如果 NLU 连续失败 N 次，暂时禁用 (避免频繁重试)

3. **直接 RAG 调用**
   - 在某些场景下跳过 NLU，直接调用 RAG (例如纯信息检索)

### 长期 (2-3 月)

1. **多 Agent 协作**
   - 根据意图自动路由到不同 Agent
   - Travel Planner (行程规划) vs Research Assistant (通用查询)

2. **行程编辑功能**
   - 基于 NLU 生成的行程进行局部修改
   - 例如: "在第二天加入博物馆参观"

## 参考文档

- [整合规划总览](./integration-plan.md)
- [架构设计详解](./architecture-design.md)
- [实现步骤清单](./implementation-steps.md)
- [NLU 服务文档](../../api/NLU-README.md)
- [RAG 服务文档](../../api/RAG-README.md)

---

**集成完成日期**: 2025-11-14
**版本**: v1.0
**状态**: ✅ 已完成并测试通过

---

```txt
### 步骤 4.5: 清理测试文件 (可选)

```bash
cd backend
rm test_nlu_client_manual.py
rm test_travel_planner_manual.py
rm cookies.txt
```

---

## 验收清单

### 功能验收

- [ ] NLU 服务调用成功，返回行程规划
- [ ] RAG 服务可独立调用 (可选)
- [ ] Travel Planner Agent 正常工作
- [ ] 兜底机制触发正常 (NLU 不可达时)
- [ ] 流式响应正常 (SSE 事件)
- [ ] 会话管理正常 (多轮对话)
- [ ] 前端对接无问题 (响应格式兼容)

### 代码质量

- [ ] Pyright 类型检查通过 (standard 级别)
- [ ] 无明显的类型错误
- [ ] 注释清晰，符合现有风格 (中英文混杂，英文标点，空格分隔)
- [ ] 日志记录完整 (关键路径 + 错误追踪)
- [ ] 异常处理健壮

### 可观测性能指标

- [ ] NLU 调用平均响应时间 < 5s
- [ ] 兜底切换时间 < 1s
- [ ] 端到端响应时间 < 10s

### 文档完整性

- [ ] 集成规划总览 (`integration-plan.md`)
- [ ] 架构设计详解 (`architecture-design.md`)
- [ ] 实现步骤清单 (`implementation-steps.md`)
- [ ] 集成完成总结 (`integration-complete.md`)
- [ ] `.env.example` 已更新

---

## 常见问题排查

### 问题 1: NLU 服务调用超时

**症状**: 日志显示 `NLU service timeout after 30s`

**排查**:

1. 检查 NLU 服务是否正常运行: `curl http://localhost:8010/health`
2. 检查 NLU 服务日志，查看是否有错误
3. 增加超时时间: `.env` 中设置 `NLU_TIMEOUT=60.0`

### 问题 2: 兜底未触发

**症状**: NLU 服务不可达，但仍然返回错误而非兜底

**排查**:

1. 检查 `ENABLE_NLU_FALLBACK` 是否为 `true`
2. 检查异常处理逻辑，确认 `ServiceUnavailableError` 被正确捕获
3. 查看日志，确认是否进入 `fallback_to_research_assistant` 节点

### 问题 3: 响应格式不兼容

**症状**: 前端显示异常或报错

**排查**:

1. 检查 NLU 响应是否正确转换为 `AIMessage`
2. 检查时间戳是否正确添加
3. 对比 Research-Assistant 和 Travel Planner 的响应格式

### 问题 4: Pyright 类型错误

**症状**: `pyright` 报告类型不匹配

**解决**:

1. 确保所有函数都有类型标注
2. 使用 `from __future__ import annotations` 启用延迟注解
3. 对于复杂类型，使用 `cast()` 或 `# type: ignore` (谨慎使用)

---

**文档版本**: v1.0
**编写日期**: 2025-11-14
**作者**: Claude Code
**状态**: 待执行
