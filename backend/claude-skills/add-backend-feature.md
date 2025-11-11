# Skill: 添加新后端功能

## 使用场景

当需要为 FastAPI + SQLAlchemy + LangGraph 后端添加新功能时, 使用此 Skill 确保完整且高质量的实现.

## 触发条件

- 用户要求添加新的 API 接口
- 需要新增数据库表或模型
- 需要扩展现有功能

## 执行流程

### 阶段 1: 深入理解现有架构 (15-30 分钟)

1. **使用 Explore Agent 分析代码库**

   ```
   使用 Task tool, subagent_type=Explore
   提示词: "请深入探索 backend 目录的代码架构, 重点关注:
   - 数据库模型定义方式
   - API 路由实现模式
   - 错误处理机制
   - 类型标注习惯
   - 代码风格特点"
   ```

2. **阅读关键文件**
   - `src/auth/models.py` - 数据模型示例
   - `src/service/planner_routes.py` - 路由实现示例
   - `src/schema/schema.py` - Pydantic Schema 示例
   - `docs/api/` - 接口文档

3. **理解现有模式**
   - 数据库 ORM 使用方式
   - 依赖注入模式
   - 异步操作规范
   - 日志记录方式

### 阶段 2: 规划新功能 (30-60 分钟)

1. **创建规划文档** (在 `docs/gen/<feature-name>/` 目录)

   **implementation-plan.md** 应包含:
   - 功能概述
   - 数据库设计 (表结构、字段、索引、外键)
   - API 设计 (接口定义、请求/响应格式、错误码)
   - 实现步骤和时间估算
   - 代码示例
   - 测试方案

   **implementation-checklist.md** 应包含:
   - 分步骤的检查清单
   - 代码质量检查项
   - 测试检查项

2. **确认技术细节**
   - 字段类型是否匹配 (特别注意 UUID vs String)
   - 外键关联是否正确
   - 索引设计是否合理
   - 是否有保留字段名冲突 (如 `metadata`)

### 阶段 3: 实现功能 (1-3 小时)

#### 步骤 1: 数据库模型 (src/auth/models.py 或新文件)

**模板**:

```python
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, JSON
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

class NewFeature(Base):
    """
    功能描述

    详细说明该表的用途和设计思路.
    """

    __tablename__ = "new_feature"

    # 主键 (使用 UUID, 兼容 PostgreSQL 和 SQLite)
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)

    # 外键 (类型必须与引用表一致)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # 业务字段
    name: Mapped[str] = mapped_column(String(length=100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 元数据字段 (注意: metadata 是保留字段, 使用其他名称)
    extra_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # 索引 (根据查询需求添加)
    __table_args__ = (
        Index("ix_new_feature_user_name", "user_id", "name", unique=True),
    )
```

**注意事项**:

- ✅ 使用 `UUID` 类型而非 `String` (与 users 表一致)
- ✅ 避免使用 `metadata` 作为字段名 (SQLAlchemy 保留字段)
- ✅ 使用 `datetime.now(timezone.utc)` 而非 `datetime.utcnow`
- ✅ 添加适当的索引提高查询性能
- ✅ 外键添加 `ondelete="CASCADE"` 实现级联删除

#### 步骤 2: Pydantic Schema (src/schema/schema.py)

**模板**:

```python
from typing import Any
from pydantic import BaseModel, Field


class NewFeatureCreate(BaseModel):
    """创建请求"""
    name: str = Field(description="名称")
    description: str | None = Field(default=None, description="描述")


class NewFeatureRead(BaseModel):
    """响应数据"""
    id: str = Field(description="ID")
    userId: str = Field(description="用户 ID")
    name: str = Field(description="名称")
    description: str | None = Field(default=None, description="描述")
    createdAt: str = Field(description="创建时间 (ISO 8601)")


class NewFeatureResponse(BaseModel):
    """API 响应"""
    data: NewFeatureRead
```

**注意事项**:

- ✅ 使用 camelCase 命名 (前端约定)
- ✅ 所有字段添加 `description`
- ✅ 时间字段使用 ISO 8601 字符串格式

#### 步骤 3: API 路由 (src/service/xxx_routes.py)

**模板**:

```python
from datetime import datetime, timezone
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from auth import User, current_active_user
from auth.database import get_async_session
from auth.models import NewFeature
from schema.schema import NewFeatureCreate, NewFeatureRead, NewFeatureResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["api"])


@router.post("/new-feature", response_model=NewFeatureResponse, status_code=status.HTTP_201_CREATED)
async def create_new_feature(
    request: NewFeatureCreate,
    current_user: Annotated[User, Depends(current_active_user)],
    session: AsyncSession = Depends(get_async_session),
) -> NewFeatureResponse:
    """
    创建新功能

    详细描述该接口的功能和使用方式.
    """
    try:
        # 1. 业务逻辑验证
        # 例如: 检查是否已存在
        stmt = select(NewFeature).where(
            NewFeature.user_id == current_user.id,
            NewFeature.name == request.name,
        )
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "ALREADY_EXISTS", "message": "记录已存在"},
            )

        # 2. 创建数据库记录
        new_feature = NewFeature(
            id=uuid4(),
            user_id=current_user.id,
            name=request.name,
            description=request.description,
            created_at=datetime.now(timezone.utc),
        )

        session.add(new_feature)
        await session.commit()
        await session.refresh(new_feature)

        # 3. 返回响应
        logger.info(f"用户 {current_user.id} 创建了新功能记录: {new_feature.id}")

        return NewFeatureResponse(
            data=NewFeatureRead(
                id=str(new_feature.id),
                userId=str(new_feature.user_id),
                name=new_feature.name,
                description=new_feature.description,
                createdAt=new_feature.created_at.isoformat(),
            )
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建新功能记录失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "API_ERROR", "message": "创建失败"},
        )


@router.delete("/new-feature/{feature_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_new_feature(
    feature_id: str,
    current_user: Annotated[User, Depends(current_active_user)],
    session: AsyncSession = Depends(get_async_session),
) -> None:
    """
    删除功能记录

    幂等操作: 重复删除不报错.
    """
    try:
        stmt = delete(NewFeature).where(
            NewFeature.user_id == current_user.id,
            NewFeature.id == feature_id,
        )

        await session.execute(stmt)
        await session.commit()

        logger.info(f"用户 {current_user.id} 删除了功能记录: {feature_id}")

    except Exception as e:
        logger.error(f"删除功能记录失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "API_ERROR", "message": "删除失败"},
        )
```

**注意事项**:

- ✅ 所有函数添加完整的类型标注
- ✅ 使用 `Annotated[User, Depends(...)]` 进行依赖注入
- ✅ 异常处理: 区分业务异常和系统异常
- ✅ 日志记录: 关键操作和错误
- ✅ 幂等性: DELETE 操作可重复调用

### 阶段 4: 类型检查与测试 (30 分钟)

1. **运行 Pyright 类型检查**

   ```bash
   pyright src/auth/models.py src/service/xxx_routes.py src/schema/schema.py
   ```

   **目标**: `0 errors, 0 warnings`

2. **手动测试接口**
   - 使用 curl 或 Postman 测试
   - 验证正常流程
   - 验证错误处理
   - 验证幂等性

3. **数据库验证**

   ```sql
   -- PostgreSQL
   \d table_name

   -- 验证索引
   \di

   -- 验证外键
   SELECT * FROM information_schema.table_constraints
   WHERE table_name = 'table_name';
   ```

## 常见问题与解决方案

### 问题 1: SQLAlchemy 字段名冲突

**错误**: `Attribute name 'metadata' is reserved when using the Declarative API.`

**解决**: 使用其他字段名, 如 `message_metadata`, `extra_data` 等.

### 问题 2: UUID 类型不匹配

**错误**: `incompatible types: character varying and uuid`

**解决**:

```python
# ❌ 错误
user_id: Mapped[str] = mapped_column(String(length=36), ForeignKey(...))

# ✅ 正确
user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey(...))
```

### 问题 3: datetime deprecation 警告

**错误**: `The method "utcnow" in class "datetime" is deprecated`

**解决**:

```python
# ❌ 错误
default=datetime.utcnow

# ✅ 正确
default=lambda: datetime.now(timezone.utc)
```

### 问题 4: 旧表结构冲突

**错误**: 表已存在但字段类型不匹配

**解决**:

```bash
# 方式 1: 删除旧表
psql -U user -d db -c "DROP TABLE IF EXISTS table_name CASCADE;"

# 方式 2: 使用 Alembic 迁移
alembic revision --autogenerate -m "Update table schema"
alembic upgrade head
```

## 代码质量检查清单

- [ ] 所有函数有完整类型标注
- [ ] 所有类和函数有 docstring
- [ ] 注释使用英文标点, 中英文间有空格
- [ ] 使用 `try-except` 捕获异常
- [ ] 业务异常使用明确的错误码
- [ ] 关键操作有日志记录
- [ ] 数据库操作使用 `await`
- [ ] 使用 SQLAlchemy 2.0 风格查询
- [ ] 通过 Pyright 类型检查
- [ ] 手动测试所有接口

## 输出文档位置

- **规划文档**: `docs/gen/<feature-name>/implementation-plan.md`
- **检查清单**: `docs/gen/<feature-name>/implementation-checklist.md`
- **实现总结**: `docs/gen/<feature-name>/implementation-summary.md` (完成后)

## 预计时间

- 小型功能 (1-2 个接口): 2-3 小时
- 中型功能 (3-5 个接口): 4-6 小时
- 大型功能 (多模块集成): 1-2 天

---

**版本**: v1.0
**创建时间**: 2025-11-11
**适用项目**: FastAPI + SQLAlchemy + LangGraph 后端
