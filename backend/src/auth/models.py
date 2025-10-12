"""用户认证数据模型"""

from datetime import datetime
from typing import Optional

from fastapi_users import schemas
from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from sqlalchemy import DateTime, Integer, MetaData, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# 定义 SQLAlchemy 元数据，用于表命名约定
metadata = MetaData(
    naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }
)


class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类"""

    metadata = metadata


class User(SQLAlchemyBaseUserTableUUID, Base):
    """
    用户数据库模型

    继承自 SQLAlchemyBaseUserTableUUID，提供以下字段：
    - id: UUID (主键)
    - email: str (唯一，索引)
    - hashed_password: str
    - is_active: bool (默认 True)
    - is_superuser: bool (默认 False)
    - is_verified: bool (默认 False)
    """

    __tablename__ = "users"

    # 扩展字段
    username: Mapped[Optional[str]] = mapped_column(
        String(length=50), unique=True, index=True, nullable=True
    )
    full_name: Mapped[Optional[str]] = mapped_column(String(length=100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    # 用于跟踪用户对话使用情况
    total_conversations: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


# === Pydantic Schemas for API ===


class UserRead(schemas.BaseUser[str]):
    """
    用户读取响应 Schema

    继承自 BaseUser，提供基础字段：
    - id: UUID
    - email: str
    - is_active: bool
    - is_superuser: bool
    - is_verified: bool
    """

    username: Optional[str] = None
    full_name: Optional[str] = None
    created_at: datetime
    total_conversations: int


class UserCreate(schemas.BaseUserCreate):
    """
    用户注册请求 Schema

    继承自 BaseUserCreate，提供：
    - email: str
    - password: str
    - is_active: bool (可选)
    - is_superuser: bool (可选)
    - is_verified: bool (可选)
    """

    username: Optional[str] = None
    full_name: Optional[str] = None


class UserUpdate(schemas.BaseUserUpdate):
    """
    用户更新请求 Schema

    继承自 BaseUserUpdate，所有字段可选：
    - email: str (可选)
    - password: str (可选)
    - is_active: bool (可选)
    - is_superuser: bool (可选)
    - is_verified: bool (可选)
    """

    username: Optional[str] = None
    full_name: Optional[str] = None
