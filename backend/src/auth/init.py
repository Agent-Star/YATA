"""用户初始化相关功能"""

import logging

from sqlalchemy import select

from auth.database import get_async_session, get_user_db
from auth.manager import get_user_manager
from auth.models import User, UserCreate
from core.settings import settings

logger = logging.getLogger(__name__)


async def initialize_super_admin() -> None:
    """
    初始化超级管理员账户

    如果配置了 SUPER_ADMIN_USERNAME 和 SUPER_ADMIN_PASSWORD,
    并且数据库中不存在该用户名的账户, 则自动创建超级管理员.

    密码会通过 UserManager 自动哈希加密.
    """
    try:
        admin_username = settings.SUPER_ADMIN_USERNAME
        admin_password = settings.SUPER_ADMIN_PASSWORD

        if not admin_username or not admin_password:
            return

        logger.info(f"检查超级管理员账户: {admin_username}")

        # 获取数据库 session -> user_db -> user_manager
        async for session in get_async_session():
            async for user_db in get_user_db(session):
                async for user_manager in get_user_manager(user_db):
                    # 检查用户是否已存在 (通过 email 或 username)
                    # FastAPI-Users 通过 email 查找用户
                    try:
                        # 尝试通过 email 查找
                        existing_user = await user_manager.get_by_email(admin_username)
                        if existing_user:
                            logger.info(f"超级管理员已存在 (email): {admin_username}")
                            return
                    except Exception:
                        pass

                    # 检查是否已有 username 匹配的用户
                    stmt = select(User).where(User.username == admin_username)
                    result = await session.execute(stmt)
                    existing_user_by_username = result.scalar_one_or_none()

                    if existing_user_by_username:
                        logger.info(f"超级管理员已存在 (username): {admin_username}")
                        return

                    # 创建超级管理员
                    logger.info(f"创建超级管理员: {admin_username}")

                    # 使用 admin_username 作为 email 和 username
                    # UserManager.create() 会自动哈希密码
                    admin_user = await user_manager.create(
                        UserCreate(
                            email="edenwangtempemail@163.com",  # 生成一个管理员邮箱
                            username=admin_username,
                            password=admin_password.get_secret_value(),  # 明文密码, UserManager 会自动哈希
                            is_superuser=True,
                            is_verified=True,
                            is_active=True,
                        )
                    )

                    logger.info(f"超级管理员创建成功: {admin_user.username} (ID: {admin_user.id})")
                    return

    except Exception as e:
        logger.error(f"初始化超级管理员失败: {e}")
        # 不抛出异常, 避免阻止服务启动
        return
