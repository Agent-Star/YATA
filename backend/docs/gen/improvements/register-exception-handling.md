# 注册接口异常处理改进

**日期**: 2025-01-27  
**类型**: 代码健壮性改进  
**文件**: `backend/src/service/frontend_routes.py`

---

## 🎯 改进目标

1. ✅ 确保 `email` 和 `username` 都有 unique 约束
2. ✅ 精确区分 email 和 username 的重复错误
3. ✅ 使用类型化异常处理，替代不健壮的字符串匹配
4. ✅ 提供清晰的错误码和错误消息

---

## 📋 数据库约束

### User 模型（`backend/src/auth/models.py`）

```python
class User(SQLAlchemyBaseUserTableUUID, Base):
    # 继承的字段：
    # - email: str (unique=True, index=True)  # 从基类继承
    
    # 扩展字段：
    username: Mapped[Optional[str]] = mapped_column(
        String(length=50), 
        unique=True,      # ✅ username 唯一约束
        index=True,       # ✅ 索引优化查询
        nullable=True
    )
```

**约束**:

- ✅ `email` unique（从 `SQLAlchemyBaseUserTableUUID` 继承）
- ✅ `username` unique（手动设置）

---

## 🔧 改进前的问题

### 原始代码（不健壮）

```python
try:
    user = await user_manager.create(user_create)
    return FrontendAuthResponse(...)
except Exception as e:
    error_msg = str(e)  # ❌ 转换为字符串
    
    # ❌ 使用字符串匹配判断错误类型（不可靠）
    if "already exists" in error_msg.lower() or "unique" in error_msg.lower():
        raise HTTPException(
            status_code=409,
            detail={"code": "ACCOUNT_EXISTS", "message": "账号已存在"}
        )  # ❌ 无法区分是 email 还是 username 重复
```

**问题**:

1. ❌ 字符串匹配不可靠（不同数据库、不同语言的错误消息不同）
2. ❌ 无法区分是 email 还是 username 重复
3. ❌ 捕获所有异常（`Exception`）太宽泛
4. ❌ 错误消息不够明确

---

## ✅ 改进后的实现

### 精确的异常处理

```python
from fastapi_users import exceptions as fastapi_users_exceptions
from sqlalchemy.exc import IntegrityError
from pydantic import ValidationError

@frontend_router.post("/register", response_model=FrontendAuthResponse)
async def register(
    user_create: UserCreate,
    user_manager: UserManager = Depends(get_user_manager),
) -> FrontendAuthResponse:
    try:
        user = await user_manager.create(user_create)
        return FrontendAuthResponse(...)
    
    # ✅ 1. FastAPI-Users 内置异常：email 已存在
    except fastapi_users_exceptions.UserAlreadyExists as e:
        logger.warning(f"注册失败：用户已存在 - {e}")
        raise HTTPException(
            status_code=409,
            detail={"code": "EMAIL_EXISTS", "message": "该邮箱已被注册"}
        )
    
    # ✅ 2. SQLAlchemy 约束违反：username 或其他字段重复
    except IntegrityError as e:
        error_info = str(e.orig) if hasattr(e, "orig") else str(e)
        logger.warning(f"注册失败：数据库约束违反 - {error_info}")
        
        # 检查是否是 username 重复
        if "username" in error_info.lower() or "uq_users_username" in error_info.lower():
            raise HTTPException(
                status_code=409,
                detail={"code": "USERNAME_EXISTS", "message": "该用户名已被使用"}
            )
        # 检查是否是 email 重复
        elif "email" in error_info.lower():
            raise HTTPException(
                status_code=409,
                detail={"code": "EMAIL_EXISTS", "message": "该邮箱已被注册"}
            )
        else:
            raise HTTPException(
                status_code=409,
                detail={"code": "CONSTRAINT_VIOLATION", "message": "数据重复或约束违反"}
            )
    
    # ✅ 3. Pydantic 验证错误
    except ValidationError as e:
        logger.warning(f"注册失败：参数验证失败 - {e}")
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_PAYLOAD", "message": f"参数校验失败: {str(e)}"}
        )
    
    # ✅ 4. 密码强度不符合要求
    except fastapi_users_exceptions.InvalidPasswordException as e:
        logger.warning(f"注册失败：密码不符合要求 - {e}")
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_PASSWORD", "message": f"密码不符合要求: {e.reason}"}
        )
    
    # ✅ 5. 未预期的错误（兜底）
    except Exception as e:
        logger.error(f"注册失败：服务器异常 - {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"code": "API_ERROR", "message": "服务器异常，请稍后重试"}
        )
```

---

## 📊 异常处理对比

### 改进前 ❌

| 场景 | 捕获异常 | 错误码 | 错误消息 | 可区分性 |
|------|---------|--------|---------|---------|
| Email 重复 | `Exception` | `ACCOUNT_EXISTS` | "账号已存在" | ❌ 不可区分 |
| Username 重复 | `Exception` | `ACCOUNT_EXISTS` | "账号已存在" | ❌ 不可区分 |
| 密码太弱 | `Exception` | `INVALID_PAYLOAD` | "参数校验失败" | ❌ 不明确 |
| 其他错误 | `Exception` | `API_ERROR` | "服务器异常" | ❌ 笼统 |

---

### 改进后 ✅

| 场景 | 捕获异常 | 错误码 | 错误消息 | 可区分性 |
|------|---------|--------|---------|---------|
| Email 重复 | `UserAlreadyExists` | `EMAIL_EXISTS` | "该邮箱已被注册" | ✅ 明确 |
| Username 重复 | `IntegrityError` | `USERNAME_EXISTS` | "该用户名已被使用" | ✅ 明确 |
| 密码太弱 | `InvalidPasswordException` | `INVALID_PASSWORD` | "密码不符合要求: ..." | ✅ 详细 |
| 参数验证失败 | `ValidationError` | `INVALID_PAYLOAD` | "参数校验失败: ..." | ✅ 详细 |
| 其他约束违反 | `IntegrityError` | `CONSTRAINT_VIOLATION` | "数据重复或约束违反" | ✅ 有提示 |
| 未知错误 | `Exception` | `API_ERROR` | "服务器异常" | ✅ 兜底 |

---

## 🎯 错误码规范

### 409 Conflict（资源冲突）

| 错误码 | 含义 | 触发场景 |
|--------|------|---------|
| `EMAIL_EXISTS` | 邮箱已被注册 | email 字段违反 unique 约束 |
| `USERNAME_EXISTS` | 用户名已被使用 | username 字段违反 unique 约束 |
| `CONSTRAINT_VIOLATION` | 其他约束违反 | 未知的数据库约束错误 |

### 400 Bad Request（请求参数错误）

| 错误码 | 含义 | 触发场景 |
|--------|------|---------|
| `INVALID_PAYLOAD` | 参数校验失败 | Pydantic 验证错误 |
| `INVALID_PASSWORD` | 密码不符合要求 | 密码太短/太弱 |

### 500 Internal Server Error（服务器错误）

| 错误码 | 含义 | 触发场景 |
|--------|------|---------|
| `API_ERROR` | 服务器异常 | 未预期的错误 |

---

## 🧪 测试用例

### 测试 1: Email 重复

**请求**:

```json
POST /auth/register
{
  "email": "admin@example.com",  // 已存在
  "username": "newuser",
  "password": "12345678"
}
```

**响应**:

```json
{
  "detail": {
    "code": "EMAIL_EXISTS",
    "message": "该邮箱已被注册"
  }
}
```

**状态码**: 409 Conflict

---

### 测试 2: Username 重复

**请求**:

```json
POST /auth/register
{
  "email": "newuser@example.com",
  "username": "admin",  // 已存在
  "password": "12345678"
}
```

**响应**:

```json
{
  "detail": {
    "code": "USERNAME_EXISTS",
    "message": "该用户名已被使用"
  }
}
```

**状态码**: 409 Conflict

---

### 测试 3: 密码太弱

**请求**:

```json
POST /auth/register
{
  "email": "newuser@example.com",
  "username": "newuser",
  "password": "123"  // 太短
}
```

**响应**:

```json
{
  "detail": {
    "code": "INVALID_PASSWORD",
    "message": "密码不符合要求: Password should be at least 8 characters"
  }
}
```

**状态码**: 400 Bad Request

---

### 测试 4: 参数验证失败

**请求**:

```json
POST /auth/register
{
  "email": "invalid-email",  // 格式错误
  "username": "newuser",
  "password": "12345678"
}
```

**响应**:

```json
{
  "detail": {
    "code": "INVALID_PAYLOAD",
    "message": "参数校验失败: ..."
  }
}
```

**状态码**: 400 Bad Request

---

### 测试 5: 成功注册

**请求**:

```json
POST /auth/register
{
  "email": "newuser@example.com",
  "username": "newuser",
  "password": "12345678"
}
```

**响应**:

```json
{
  "user": {
    "id": "uuid",
    "account": "newuser",
    "displayName": "newuser"
  },
  "accessToken": null
}
```

**状态码**: 200 OK

---

## 🎓 技术要点

### 1. 异常捕获顺序

**原则**: 从最具体到最通用

```python
try:
    ...
except SpecificException:      # ✅ 最具体
    ...
except MoreGeneralException:   # ✅ 较通用
    ...
except Exception:              # ✅ 最通用（兜底）
    ...
```

**原因**: Python 按顺序匹配异常，先匹配到的会被捕获。

---

### 2. IntegrityError 处理

**为什么需要字符串检查？**

`IntegrityError` 是通用的数据库约束违反异常，需要检查错误消息来确定具体违反了哪个约束。

**PostgreSQL 示例**:

```
duplicate key value violates unique constraint "uq_users_username"
```

**SQLite 示例**:

```
UNIQUE constraint failed: users.username
```

**检查方法**:

```python
error_info = str(e.orig) if hasattr(e, "orig") else str(e)

# 检查约束名称
if "uq_users_username" in error_info.lower():
    # PostgreSQL
    ...
# 或检查字段名
elif "username" in error_info.lower():
    # SQLite 或其他
    ...
```

---

### 3. 日志记录

**原则**: 不同级别的日志

```python
# ✅ 警告：用户操作导致的预期错误
logger.warning(f"注册失败：用户已存在 - {e}")

# ✅ 错误：未预期的系统错误
logger.error(f"注册失败：服务器异常 - {e}", exc_info=True)
```

**`exc_info=True`**: 记录完整的堆栈跟踪，方便调试。

---

## 🔄 相关改进

### UserManager 扩展

**`backend/src/auth/manager.py`** 已实现：

```python
class UserManager:
    async def get_by_username(self, username: str) -> Optional[User]:
        """通过 username 查找用户"""
        ...
    
    async def authenticate(self, credentials) -> Optional[User]:
        """支持 email 或 username 登录"""
        # 先尝试 email，再尝试 username
        ...
```

---

## 📚 参考资源

- [FastAPI-Users Exceptions](https://fastapi-users.github.io/fastapi-users/exceptions/)
- [SQLAlchemy IntegrityError](https://docs.sqlalchemy.org/en/20/core/exceptions.html#sqlalchemy.exc.IntegrityError)
- [Pydantic ValidationError](https://docs.pydantic.dev/latest/errors/validation_errors/)

---

## 🎉 总结

### 改进成果

1. ✅ **类型化异常处理**：使用具体的异常类型而不是字符串匹配
2. ✅ **精确的错误码**：区分 `EMAIL_EXISTS` 和 `USERNAME_EXISTS`
3. ✅ **清晰的错误消息**：提供用户友好的中文提示
4. ✅ **完整的日志记录**：方便问题排查和监控
5. ✅ **健壮的实现**：覆盖所有可能的异常场景

### 代码质量提升

- 🟢 **可维护性**: 清晰的异常分类和处理
- 🟢 **可测试性**: 每种异常都可以独立测试
- 🟢 **用户体验**: 明确的错误提示
- 🟢 **可调试性**: 详细的日志记录

---

**改进状态**: ✅ 已完成  
**测试状态**: ⏳ 待测试  
**文档状态**: ✅ 已记录
