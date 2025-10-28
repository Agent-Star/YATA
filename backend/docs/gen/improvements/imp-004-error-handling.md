# IMP-004: 错误处理标准化

## 元数据

- **ID**: IMP-004
- **分类**: 代码质量
- **优先级**: 🟡 中
- **状态**: 待处理
- **创建日期**: 2025-01-27
- **预计工作量**: 中
- **相关文档**: `phase1-implementation-summary.md`, `phase3-implementation-summary.md`

---

## 问题描述

### 当前实现

#### 1. 错误响应格式不统一

**frontend_routes.py**:

```python
raise HTTPException(
    status_code=status.HTTP_409_CONFLICT,
    detail={"code": "ACCOUNT_EXISTS", "message": "账号已存在"},  # ✅ 结构化
)
```

**planner_routes.py**:

```python
raise HTTPException(
    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    detail={"code": "API_ERROR", "message": "获取历史记录失败"},  # ✅ 结构化
)
```

**service.py** (其他端点):

```python
raise HTTPException(
    status_code=404,
    detail="Agent not found",  # ❌ 字符串格式
)
```

#### 2. 错误码未集中管理

错误码散落在各个文件中：

- `"ACCOUNT_EXISTS"` - frontend_routes.py
- `"INVALID_CREDENTIALS"` - frontend_routes.py
- `"API_ERROR"` - planner_routes.py
- 其他端点没有错误码

#### 3. 异常处理不完整

某些函数缺少异常处理：

```python
async def get_history(...):
    try:
        # ... 业务逻辑 ...
    except Exception as e:
        logger.error(f"获取历史记录失败: {e}")  # ✅ 有日志
        raise HTTPException(...)  # ✅ 有异常转换
```

但其他地方可能没有：

```python
async def some_endpoint(...):
    # ... 业务逻辑 ...
    # ❌ 没有 try-except，异常直接暴露给用户
```

### 不足之处

1. **前端处理困难**：错误响应格式不统一，前端需要处理多种情况
2. **可维护性差**：错误码和消息分散，难以维护
3. **用户体验差**：某些错误信息对用户不友好（如直接暴露异常堆栈）
4. **调试困难**：错误日志不完整，难以定位问题

---

## 影响分析

### 功能影响

- ⚠️ **前端错误处理复杂**：需要同时处理字符串和对象格式
- ⚠️ **国际化困难**：错误消息硬编码，难以翻译

### 用户体验影响

- ⚠️ **错误提示不友好**：技术性错误信息直接展示给用户
- ⚠️ **缺少错误追踪**：用户无法提供有效的错误信息给客服

### 开发维护影响

- ⚠️ **代码重复**：错误处理逻辑重复
- ⚠️ **难以统一修改**：修改错误消息需要查找所有文件

---

## 改进方案

### 方案: 统一错误处理系统（推荐）

**目标**：

1. 统一错误响应格式
2. 集中管理错误码和消息
3. 提供全局异常处理器
4. 改善错误日志

**实施步骤**：

#### 1. 定义错误码枚举

**文件**: `backend/src/schema/errors.py` (新建)

```python
"""统一错误处理"""

from enum import Enum
from typing import Any


class ErrorCode(str, Enum):
    """错误码枚举"""
    
    # === 通用错误 ===
    INTERNAL_ERROR = "INTERNAL_ERROR"
    INVALID_PAYLOAD = "INVALID_PAYLOAD"
    NOT_FOUND = "NOT_FOUND"
    FORBIDDEN = "FORBIDDEN"
    UNAUTHORIZED = "UNAUTHORIZED"
    
    # === 认证错误 ===
    ACCOUNT_EXISTS = "ACCOUNT_EXISTS"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    ACCOUNT_LOCKED = "ACCOUNT_LOCKED"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    INVALID_TOKEN = "INVALID_TOKEN"
    
    # === 业务错误 ===
    API_ERROR = "API_ERROR"
    AGENT_NOT_FOUND = "AGENT_NOT_FOUND"
    THREAD_NOT_FOUND = "THREAD_NOT_FOUND"
    HISTORY_ERROR = "HISTORY_ERROR"
    STREAM_ERROR = "STREAM_ERROR"
    
    # === LLM 相关错误 ===
    LLM_ERROR = "LLM_ERROR"
    MODEL_NOT_AVAILABLE = "MODEL_NOT_AVAILABLE"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    CONTEXT_LENGTH_EXCEEDED = "CONTEXT_LENGTH_EXCEEDED"


# 错误消息映射（支持国际化）
ERROR_MESSAGES = {
    ErrorCode.INTERNAL_ERROR: "服务器内部错误",
    ErrorCode.INVALID_PAYLOAD: "请求参数不正确",
    ErrorCode.NOT_FOUND: "资源不存在",
    ErrorCode.FORBIDDEN: "没有权限访问该资源",
    ErrorCode.UNAUTHORIZED: "未登录或登录已过期",
    
    ErrorCode.ACCOUNT_EXISTS: "账号已存在",
    ErrorCode.INVALID_CREDENTIALS: "账号或密码错误",
    ErrorCode.ACCOUNT_LOCKED: "账号已被锁定",
    ErrorCode.TOKEN_EXPIRED: "登录已过期，请重新登录",
    ErrorCode.INVALID_TOKEN: "登录凭证无效",
    
    ErrorCode.API_ERROR: "API 调用失败",
    ErrorCode.AGENT_NOT_FOUND: "Agent 不存在",
    ErrorCode.THREAD_NOT_FOUND: "对话不存在",
    ErrorCode.HISTORY_ERROR: "获取历史记录失败",
    ErrorCode.STREAM_ERROR: "流式响应失败",
    
    ErrorCode.LLM_ERROR: "AI 模型调用失败",
    ErrorCode.MODEL_NOT_AVAILABLE: "AI 模型不可用",
    ErrorCode.RATE_LIMIT_EXCEEDED: "请求过于频繁，请稍后再试",
    ErrorCode.CONTEXT_LENGTH_EXCEEDED: "对话内容过长",
}


class ErrorResponse(BaseModel):
    """统一错误响应格式"""
    
    code: ErrorCode = Field(description="错误码")
    message: str = Field(description="错误描述")
    detail: dict[str, Any] | None = Field(default=None, description="额外错误详情")
    request_id: str | None = Field(default=None, description="请求追踪 ID")


class AppException(Exception):
    """应用异常基类"""
    
    def __init__(
        self,
        code: ErrorCode,
        message: str | None = None,
        status_code: int = 500,
        detail: dict[str, Any] | None = None,
    ):
        self.code = code
        self.message = message or ERROR_MESSAGES.get(code, str(code))
        self.status_code = status_code
        self.detail = detail
        super().__init__(self.message)


# === 特定异常类 ===

class AuthenticationError(AppException):
    """认证错误"""
    def __init__(self, code: ErrorCode = ErrorCode.UNAUTHORIZED, message: str | None = None):
        super().__init__(code, message, status_code=401)


class AuthorizationError(AppException):
    """授权错误"""
    def __init__(self, code: ErrorCode = ErrorCode.FORBIDDEN, message: str | None = None):
        super().__init__(code, message, status_code=403)


class ValidationError(AppException):
    """验证错误"""
    def __init__(self, message: str | None = None, detail: dict | None = None):
        super().__init__(
            ErrorCode.INVALID_PAYLOAD,
            message,
            status_code=400,
            detail=detail
        )


class NotFoundError(AppException):
    """资源不存在错误"""
    def __init__(self, resource: str, message: str | None = None):
        super().__init__(
            ErrorCode.NOT_FOUND,
            message or f"{resource} 不存在",
            status_code=404
        )


class BusinessError(AppException):
    """业务逻辑错误"""
    def __init__(self, code: ErrorCode, message: str | None = None):
        super().__init__(code, message, status_code=400)
```

#### 2. 实现全局异常处理器

**文件**: `backend/src/service/service.py`

```python
from schema.errors import AppException, ErrorCode, ErrorResponse
import traceback
import uuid

# 添加全局异常处理器
@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    """处理自定义应用异常"""
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    
    logger.error(
        f"AppException: {exc.code} - {exc.message}",
        extra={
            "request_id": request_id,
            "code": exc.code,
            "detail": exc.detail,
            "path": request.url.path,
        }
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            code=exc.code,
            message=exc.message,
            detail=exc.detail,
            request_id=request_id,
        ).model_dump()
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """处理 FastAPI HTTPException"""
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    
    # 如果 detail 已经是字典格式，直接使用
    if isinstance(exc.detail, dict):
        content = {**exc.detail, "request_id": request_id}
    else:
        # 否则转换为统一格式
        content = ErrorResponse(
            code=ErrorCode.INTERNAL_ERROR,
            message=str(exc.detail),
            request_id=request_id,
        ).model_dump()
    
    logger.error(
        f"HTTPException: {exc.status_code} - {exc.detail}",
        extra={"request_id": request_id, "path": request.url.path}
    )
    
    return JSONResponse(status_code=exc.status_code, content=content)


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """处理未捕获的异常"""
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    
    logger.error(
        f"Unhandled exception: {type(exc).__name__} - {str(exc)}",
        extra={
            "request_id": request_id,
            "path": request.url.path,
            "traceback": traceback.format_exc(),
        }
    )
    
    # 生产环境不暴露详细错误信息
    if settings.is_dev():
        message = f"{type(exc).__name__}: {str(exc)}"
    else:
        message = "服务器内部错误"
    
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            code=ErrorCode.INTERNAL_ERROR,
            message=message,
            request_id=request_id,
        ).model_dump()
    )
```

#### 3. 更新现有代码使用新的异常系统

**frontend_routes.py**:

```python
from schema.errors import AppException, ErrorCode, BusinessError

@frontend_router.post("/register", response_model=FrontendAuthResponse)
async def register(...):
    try:
        # ... 创建用户 ...
        user = await user_manager.create(user_create)
        return FrontendAuthResponse(...)
        
    except Exception as e:
        error_msg = str(e)
        if "already exists" in error_msg.lower() or "unique" in error_msg.lower():
            raise BusinessError(ErrorCode.ACCOUNT_EXISTS)  # ✅ 使用统一异常
        elif "invalid" in error_msg.lower():
            raise BusinessError(ErrorCode.INVALID_PAYLOAD)
        else:
            raise AppException(ErrorCode.INTERNAL_ERROR, str(e))
```

**planner_routes.py**:

```python
from schema.errors import AppException, ErrorCode, NotFoundError

@planner_router.get("/history", response_model=HistoryResponse)
async def get_history(...):
    try:
        thread_id = await get_or_create_main_thread(current_user, session)
        agent: AgentGraph = get_agent(DEFAULT_AGENT)
        # ...
        return HistoryResponse(messages=frontend_messages)
        
    except KeyError as e:
        raise NotFoundError("Thread", f"Thread {thread_id} not found")
    except Exception as e:
        logger.error(f"获取历史记录失败: {e}", exc_info=True)
        raise AppException(
            ErrorCode.HISTORY_ERROR,
            "获取历史记录失败",
            detail={"error": str(e)} if settings.is_dev() else None
        )
```

#### 4. 添加请求追踪中间件

```python
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """为每个请求添加唯一 ID"""
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = request_id
    
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response
```

---

## 实施建议

### 实施步骤

1. **创建错误处理模块** (`schema/errors.py`)
   - 预计工作量：2 小时

2. **添加全局异常处理器** (`service/service.py`)
   - 预计工作量：1 小时

3. **迁移现有代码**
   - `frontend_routes.py`: 30分钟
   - `planner_routes.py`: 30分钟
   - 其他端点: 1 小时

4. **测试和文档更新**
   - 预计工作量：2 小时

**总计**：约 7 小时

### 迁移策略

**渐进式迁移**：

1. 先添加错误处理基础设施
2. 新代码直接使用新系统
3. 逐步迁移旧代码（不紧急）

### 注意事项

1. **向后兼容**：保持响应格式兼容
2. **生产环境**：不暴露敏感信息（如堆栈追踪）
3. **日志记录**：确保所有错误都被记录

---

## 测试计划

```python
def test_app_exception_handler():
    """测试自定义异常处理"""
    @app.get("/test-error")
    async def test_endpoint():
        raise AppException(
            ErrorCode.API_ERROR,
            "测试错误",
            detail={"extra": "info"}
        )
    
    response = client.get("/test-error")
    assert response.status_code == 500
    data = response.json()
    assert data["code"] == "API_ERROR"
    assert data["message"] == "测试错误"
    assert "request_id" in data


def test_error_response_format():
    """测试错误响应格式"""
    response = client.post("/auth/login", json={
        "account": "nonexistent",
        "password": "wrong"
    })
    
    assert response.status_code == 401
    data = response.json()
    assert "code" in data
    assert "message" in data
    assert isinstance(data["code"], str)
```

---

## 相关资源

- [FastAPI Exception Handling](https://fastapi.tiangolo.com/tutorial/handling-errors/)
- [RFC 7807: Problem Details for HTTP APIs](https://datatracker.ietf.org/doc/html/rfc7807)
- [Error Handling Best Practices](https://www.bugsnag.com/blog/error-handling-best-practices)

---

## 更新日志

- 2025-01-27: 创建文档，提供统一错误处理方案
