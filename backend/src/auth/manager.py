"""用户管理器配置"""

import logging
from collections.abc import AsyncGenerator
from typing import Optional
from uuid import UUID, uuid4

from fastapi import Depends, Request
from fastapi_users import BaseUserManager, UUIDIDMixin
from fastapi_users.db import SQLAlchemyUserDatabase

from auth.database import get_user_db
from auth.models import User
from core.settings import settings

logger = logging.getLogger(__name__)


class UserManager(UUIDIDMixin, BaseUserManager[User, UUID]):
    """
    用户管理器

    处理用户的创建、验证、密码重置等操作
    """

    reset_password_token_secret = settings.AUTH_JWT_SECRET.get_secret_value()
    verification_token_secret = settings.AUTH_JWT_SECRET.get_secret_value()

    async def on_after_register(self, user: User, request: Optional[Request] = None):
        """用户注册后的回调"""
        logger.info(f"用户 {user.id} 已注册，邮箱: {user.email}")

        # 为新用户创建主 Thread ID
        if not user.main_thread_id:
            new_thread_id = str(uuid4())
            await self.user_db.update(user, {"main_thread_id": new_thread_id})
            logger.info(f"为用户 {user.id} 创建主 Thread: {new_thread_id}")

    async def on_after_forgot_password(
        self, user: User, token: str, request: Optional[Request] = None
    ):
        """忘记密码请求后的回调"""
        logger.info(f"用户 {user.id} 请求重置密码。Token: {token}")
        # TODO: 在这里可以实现发送密码重置邮件的逻辑

    async def on_after_request_verify(
        self, user: User, token: str, request: Optional[Request] = None
    ):
        """请求验证后的回调"""
        logger.info(f"用户 {user.id} 请求验证邮箱。Token: {token}")
        # TODO: 在这里可以实现发送验证邮件的逻辑


async def get_user_manager(
    user_db: SQLAlchemyUserDatabase = Depends(get_user_db),
) -> AsyncGenerator[UserManager, None]:
    """
    获取用户管理器实例

    用作 FastAPI 依赖项
    """
    yield UserManager(user_db)
