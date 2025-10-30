"""用户管理器配置"""

import logging
from collections.abc import AsyncGenerator
from typing import Optional
from uuid import UUID, uuid4

from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordRequestForm
from fastapi_users import BaseUserManager, UUIDIDMixin, exceptions
from fastapi_users.db import SQLAlchemyUserDatabase
from sqlalchemy import select

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

    async def get_by_username(self, username: str) -> Optional[User]:
        """
        通过 username 查找用户

        Args:
            username: 用户名

        Returns:
            User 对象或 None
        """
        try:
            stmt = select(User).where(User.username == username)
            # SQLAlchemyUserDatabase 的 session 属性
            # 类型: SQLAlchemyUserDatabase 继承自 SQLAlchemyBaseUserDatabase，有 session 属性
            session = self.user_db.session  # type: ignore[attr-defined]
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()
            logger.debug(f"通过 username 查找用户 '{username}': {'找到' if user else '未找到'}")
            return user
        except Exception as e:
            logger.error(f"通过 username 查找用户失败 '{username}': {e}", exc_info=True)
            return None

    async def authenticate(self, credentials: OAuth2PasswordRequestForm) -> Optional[User]:
        """
        验证用户凭据（支持 email 或 username）

        Args:
            credentials: OAuth2 密码表单，包含 username 和 password

        Returns:
            验证成功返回 User 对象，否则返回 None
        """
        try:
            logger.debug(f"尝试认证用户: {credentials.username}")

            user = None

            # 尝试通过 email 查找用户
            try:
                user = await self.get_by_email(credentials.username)
                logger.debug("通过 email 找到用户")
            except exceptions.UserNotExists:
                logger.debug("通过 email 未找到用户")
                # 如果通过 email 未找到，尝试通过 username 查找
                logger.debug("尝试通过 username 查找...")
                user = await self.get_by_username(credentials.username)

            # 如果用户不存在，返回 None
            if user is None:
                logger.warning(f"用户不存在: {credentials.username}")
                # 运行密码哈希以防止时序攻击
                self.password_helper.hash(credentials.password)
                return None

            logger.debug("找到用户，开始验证密码...")
            # 验证密码（verify_and_update 是同步方法）
            verified, updated_password_hash = self.password_helper.verify_and_update(
                credentials.password, user.hashed_password
            )

            if not verified:
                logger.warning(f"密码验证失败: {credentials.username}")
                return None

            logger.info(f"用户认证成功: {credentials.username} (ID: {user.id})")

            # 如果密码哈希需要更新（例如算法升级）
            if updated_password_hash is not None:
                await self.user_db.update(user, {"hashed_password": updated_password_hash})
                logger.debug("密码哈希已更新")

            return user
        except Exception as e:
            logger.error(f"用户认证失败: {e}", exc_info=True)
            return None

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
        logger.info(f"用户 {user.id} 请求重置密码. Token: {token}")
        # TODO: 在这里可以实现发送密码重置邮件的逻辑

    async def on_after_request_verify(
        self, user: User, token: str, request: Optional[Request] = None
    ):
        """请求验证后的回调"""
        logger.info(f"用户 {user.id} 请求验证邮箱. Token: {token}")
        # TODO: 在这里可以实现发送验证邮件的逻辑


async def get_user_manager(
    user_db: SQLAlchemyUserDatabase = Depends(get_user_db),
) -> AsyncGenerator[UserManager, None]:
    """
    获取用户管理器实例

    用作 FastAPI 依赖项
    """
    yield UserManager(user_db)
