"""NLU 服务客户端"""

from __future__ import annotations

import logging
from typing import Literal

import httpx
from pydantic import BaseModel, Field

from core.settings import settings
from external_services.exceptions import NLUServiceError, ServiceUnavailableError

logger = logging.getLogger(__name__)


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
