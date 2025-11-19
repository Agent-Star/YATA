"""RAG 服务客户端 (可选实现)"""

from __future__ import annotations

import logging

import httpx
from pydantic import BaseModel, Field

from core.settings import settings
from external_services.exceptions import RAGServiceError, ServiceUnavailableError

logger = logging.getLogger(__name__)


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

            logger.debug(f"RAGClient: Received {len(rag_response.results)} results")

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
