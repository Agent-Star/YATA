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
