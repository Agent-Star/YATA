"""
用户认证模块

提供基于 FastAPI-Users 的完整用户认证系统，包括：
- 用户注册
- JWT 登录/登出
- 密码重置
- 邮箱验证
- 用户管理
"""

from auth.auth import (
    bearer_auth_backend,
    cookie_auth_backend,
    current_active_user,
    current_superuser,
    current_verified_user,
    fastapi_users,
)
from auth.database import create_db_and_tables, get_async_session, get_user_db
from auth.manager import get_user_manager
from auth.models import User, UserCreate, UserRead, UserUpdate

__all__ = [
    # FastAPI Users 实例
    "fastapi_users",
    "cookie_auth_backend",
    "bearer_auth_backend",
    # 用户依赖
    "current_active_user",
    "current_verified_user",
    "current_superuser",
    # 数据库
    "create_db_and_tables",
    "get_async_session",
    "get_user_db",
    # 用户管理
    "get_user_manager",
    # 模型和 Schema
    "User",
    "UserRead",
    "UserCreate",
    "UserUpdate",
]
