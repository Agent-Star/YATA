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
