# Skill: 后端代码风格与质量标准

## 使用场景

在 YATA 后端项目中编写或审查代码时, 确保代码符合项目的风格和质量标准.

## 项目技术栈

- **Python**: 3.13+
- **Web 框架**: FastAPI 0.115
- **ORM**: SQLAlchemy 2.0 (异步)
- **类型检查**: Pyright (standard level)
- **AI 框架**: LangGraph 0.5
- **认证**: FastAPI-Users 14.0
- **数据库**: PostgreSQL (主) / SQLite (开发)

## 类型标注规范

### 基本原则

- ✅ 所有函数参数必须有类型标注
- ✅ 所有函数返回值必须有类型标注
- ✅ 避免使用 `Any`, 尽量使用具体类型
- ✅ 使用 Python 3.10+ 语法 (`Type | None` 而非 `Optional[Type]`)
- ✅ 通过 Pyright standard level 检查

### 依赖注入

```python
from typing import Annotated
from fastapi import Depends

# ✅ 正确: 使用 Annotated
async def route_handler(
    current_user: Annotated[User, Depends(current_active_user)],
    session: AsyncSession = Depends(get_async_session),
) -> ResponseModel:
    pass

# ❌ 错误: 缺少类型标注
async def route_handler(current_user, session):
    pass
```

### 可选类型

```python
from typing import Optional

# ✅ 正确: Python 3.10+ 语法
def process(data: str | None = None) -> dict[str, Any] | None:
    pass

# ⚠️ 可接受但不推荐: 旧语法
def process(data: Optional[str] = None) -> Optional[dict[str, Any]]:
    pass
```

### SQLAlchemy 类型标注

```python
from sqlalchemy.orm import Mapped, mapped_column
from uuid import UUID

# ✅ 正确: 使用 Mapped
class User(Base):
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)

# ❌ 错误: 缺少类型标注
class User(Base):
    id = Column(UUID, primary_key=True)
    name = Column(String(100))
```

## 注释规范

### Docstring (函数和类)

```python
# ✅ 正确: 完整的 docstring
def create_user(name: str, email: str) -> User:
    """
    创建新用户

    根据提供的用户名和邮箱创建新用户记录.
    若邮箱已存在, 抛出 HTTPException.

    Args:
        name: 用户名
        email: 用户邮箱

    Returns:
        创建的用户对象

    Raises:
        HTTPException: 邮箱已存在时抛出 409 错误
    """
    pass

# ❌ 错误: 缺少 docstring
def create_user(name: str, email: str) -> User:
    pass
```

### 行内注释

```python
# ✅ 正确: 中英混合, 英文标点, 空格分隔
def process_data(data: dict[str, Any]) -> None:
    # 1. 验证数据格式 (validate data format)
    if not data:
        raise ValueError("数据不能为空")

    # 2. 提取关键字段
    user_id = data.get("userId")

# ❌ 错误: 中文标点
def process_data(data):
    # 1、验证数据格式（validate data format）
    pass

# ❌ 错误: 无空格分隔
def process_data(data):
    # 1.验证数据格式validate data format
    pass
```

### 注释风格总结

- ✅ 使用英文标点 (`.`, `,`, `:` 等)
- ✅ 中文和英文之间用**一个空格**分隔
- ✅ 可以混用中英文, 但标点必须统一为英文
- ✅ 关键业务逻辑添加注释
- ✅ 复杂算法添加分步注释

## 数据库模型规范

### 字段定义

```python
from datetime import datetime, timezone
from uuid import UUID, uuid4
from sqlalchemy import DateTime, ForeignKey, Index, String, Text, JSON
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

class Example(Base):
    """示例数据模型"""

    __tablename__ = "examples"

    # ✅ 正确: UUID 主键 (兼容 PostgreSQL 和 SQLite)
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)

    # ✅ 正确: UUID 外键 (类型必须匹配)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # ✅ 正确: 必填字符串
    name: Mapped[str] = mapped_column(String(length=100), nullable=False)

    # ✅ 正确: 可选字符串
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ✅ 正确: JSON 字段 (避免使用 metadata 作为字段名)
    extra_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # ✅ 正确: 时间戳 (使用 timezone-aware datetime)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # ✅ 正确: 复合索引
    __table_args__ = (
        Index("ix_examples_user_name", "user_id", "name", unique=True),
    )
```

### 常见错误

```python
# ❌ 错误 1: 使用 String 而非 UUID
user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))

# ❌ 错误 2: 使用保留字段名
metadata: Mapped[dict | None] = mapped_column(JSON)

# ❌ 错误 3: 使用已废弃的 datetime.utcnow
created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

# ❌ 错误 4: 缺少类型标注
name = Column(String(100))
```

## API 路由规范

### 路由函数结构

```python
@router.post("/resource", response_model=ResourceResponse, status_code=status.HTTP_201_CREATED)
async def create_resource(
    request: ResourceCreate,
    current_user: Annotated[User, Depends(current_active_user)],
    session: AsyncSession = Depends(get_async_session),
) -> ResourceResponse:
    """
    创建资源

    详细描述接口功能和使用方式.
    """
    try:
        # 1. 业务逻辑验证
        # ...

        # 2. 数据库操作
        # ...

        # 3. 日志记录
        logger.info(f"用户 {current_user.id} 创建了资源: {resource.id}")

        # 4. 返回响应
        return ResourceResponse(...)

    except HTTPException:
        # 重新抛出业务异常
        raise
    except Exception as e:
        # 捕获系统异常
        logger.error(f"创建资源失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "API_ERROR", "message": "创建失败"},
        )
```

### 错误处理

```python
# ✅ 正确: 区分业务异常和系统异常
try:
    # 业务逻辑
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_INPUT", "message": "输入无效"},
        )

    # 数据库操作
    result = await session.execute(stmt)

except HTTPException:
    # 重新抛出业务异常
    raise
except Exception as e:
    # 记录并转换系统异常
    logger.error(f"操作失败: {e}")
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={"code": "API_ERROR", "message": "操作失败"},
    )
```

### 错误码规范

| HTTP 状态码 | 错误码 | 使用场景 |
|------------|--------|---------|
| 400 | INVALID_PAYLOAD | 请求参数校验失败 |
| 401 | UNAUTHENTICATED | 未登录或登录已失效 |
| 403 | FORBIDDEN | 无权限访问 |
| 404 | NOT_FOUND / MESSAGE_NOT_FOUND | 资源不存在 |
| 409 | ALREADY_EXISTS / ALREADY_FAVORITED | 资源已存在或冲突 |
| 500 | API_ERROR | 服务器内部错误 |
| 503 | SERVICE_UNAVAILABLE | 服务不可用 |

## 数据库操作规范

### 异步操作

```python
# ✅ 正确: 所有数据库操作使用 await
async def get_user(user_id: UUID, session: AsyncSession) -> User | None:
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()

# ❌ 错误: 缺少 await
async def get_user(user_id: UUID, session: AsyncSession) -> User | None:
    stmt = select(User).where(User.id == user_id)
    result = session.execute(stmt)  # 缺少 await
    return result.scalar_one_or_none()
```

### SQLAlchemy 2.0 风格

```python
from sqlalchemy import select, delete, update

# ✅ 正确: 使用 select()
stmt = select(User).where(User.email == email)
result = await session.execute(stmt)
user = result.scalar_one_or_none()

# ✅ 正确: 使用 delete()
stmt = delete(User).where(User.id == user_id)
await session.execute(stmt)

# ✅ 正确: 使用 update()
stmt = update(User).where(User.id == user_id).values(name=new_name)
await session.execute(stmt)

# ❌ 错误: 使用旧式 query API
user = session.query(User).filter(User.email == email).first()
```

### 事务处理

```python
# ✅ 正确: 完整的事务流程
async def create_user(data: UserCreate, session: AsyncSession) -> User:
    user = User(**data.dict())
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user

# ⚠️ 注意: 默认已在事务中, 无需手动 begin
# FastAPI 的 Depends(get_async_session) 已处理事务
```

## 日志记录规范

```python
import logging

logger = logging.getLogger(__name__)

# ✅ 正确: 使用适当的日志级别
logger.debug(f"处理请求: {request_id}")
logger.info(f"用户 {user_id} 创建了资源: {resource_id}")
logger.warning(f"用户 {user_id} 尝试访问无权限资源: {resource_id}")
logger.error(f"数据库操作失败: {e}", exc_info=True)

# ❌ 错误: 使用 print
print(f"User {user_id} created resource")

# ❌ 错误: 日志级别不当
logger.error(f"用户创建了资源")  # 应使用 info
logger.info(f"数据库连接失败")  # 应使用 error
```

## Pydantic Schema 规范

```python
from pydantic import BaseModel, Field

# ✅ 正确: 完整的 Schema 定义
class UserCreate(BaseModel):
    """用户创建请求"""

    username: str = Field(description="用户名", min_length=3, max_length=50)
    email: str = Field(description="邮箱地址")
    password: str = Field(description="密码", min_length=8)


class UserRead(BaseModel):
    """用户响应数据"""

    id: str = Field(description="用户 ID")
    username: str = Field(description="用户名")
    email: str = Field(description="邮箱地址")
    createdAt: str = Field(description="创建时间 (ISO 8601)")

    # ✅ 正确: 使用 camelCase (前端约定)
    # ❌ 错误: created_at (snake_case)
```

## 代码组织规范

### 文件内部组织

```python
"""
模块文档字符串

简要描述该模块的功能.
"""

# 1. 标准库导入
import logging
from datetime import datetime, timezone
from typing import Annotated

# 2. 第三方库导入
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

# 3. 本地模块导入
from auth import User, current_active_user
from auth.database import get_async_session
from auth.models import Resource
from schema.schema import ResourceCreate, ResourceRead

# 4. 模块级变量
logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["api"])

# 5. 数据模型定义
class RequestModel(BaseModel):
    pass

# 6. 辅助函数
def helper_function():
    pass

# 7. 路由实现
@router.get("/")
async def route_handler():
    pass
```

## 质量检查清单

### 代码风格

- [ ] 所有函数有完整类型标注
- [ ] 所有类和函数有 docstring
- [ ] 注释使用英文标点
- [ ] 中英文间有空格
- [ ] 无 `print()` 语句 (使用 `logger`)

### 类型安全

- [ ] 通过 `pyright` 检查 (0 errors)
- [ ] 避免使用 `Any`
- [ ] 避免使用 `# type: ignore`
- [ ] UUID 类型一致 (不混用 str)

### 数据库

- [ ] 所有操作使用 `await`
- [ ] 使用 SQLAlchemy 2.0 风格
- [ ] 外键类型匹配
- [ ] 避免使用保留字段名
- [ ] 添加必要的索引

### 错误处理

- [ ] 使用 `try-except` 捕获异常
- [ ] 区分业务异常和系统异常
- [ ] 错误码明确且一致
- [ ] 记录错误日志

### 性能

- [ ] 避免 N+1 查询
- [ ] 使用批量查询
- [ ] 添加必要的索引
- [ ] 避免在循环中查询数据库

## Pyright 检查命令

```bash
# 检查单个文件
pyright src/auth/models.py

# 检查多个文件
pyright src/auth/models.py src/service/planner_routes.py

# 检查整个项目
pyright src/

# 期望结果
# 0 errors, 0 warnings, 0 informations
```

## 参考资源

- **FastAPI 文档**: <https://fastapi.tiangolo.com/>
- **SQLAlchemy 2.0 文档**: <https://docs.sqlalchemy.org/en/20/>
- **Pydantic 文档**: <https://docs.pydantic.dev/>
- **Python 类型标注**: <https://docs.python.org/3/library/typing.html>
- **Pyright 文档**: <https://github.com/microsoft/pyright>

---

**版本**: v1.0
**创建时间**: 2025-11-11
**适用项目**: YATA Backend (FastAPI + SQLAlchemy)
