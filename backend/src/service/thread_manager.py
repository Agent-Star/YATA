"""Thread 管理工具

提供用户 Thread 的创建、获取和管理功能.
"""

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.models import User


async def get_or_create_main_thread(user: User, session: AsyncSession) -> str:
    """
    获取或创建用户的主 Thread ID

    Args:
        user: 用户对象
        session: 数据库会话

    Returns:
        用户的主 Thread ID
    """
    # 如果用户已有主 Thread, 直接返回
    if user.main_thread_id:
        return user.main_thread_id

    # 创建新的主 Thread ID
    new_thread_id = str(uuid4())
    user.main_thread_id = new_thread_id

    # 保存到数据库
    session.add(user)
    await session.commit()
    await session.refresh(user)

    return new_thread_id


async def get_main_thread_id(user_id: str, session: AsyncSession) -> str | None:
    """
    根据用户 ID 获取主 Thread ID

    Args:
        user_id: 用户 ID
        session: 数据库会话

    Returns:
        主 Thread ID, 如果用户不存在或没有主 Thread 则返回 None
    """
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        return None

    return user.main_thread_id


async def create_new_thread_for_user(user: User, session: AsyncSession) -> str:
    """
    为用户创建新的 Thread (用于"新建对话"功能)

    当前实现为"单 Thread + 清空"模式:
    - 创建新 Thread ID
    - 更新为用户的主 Thread
    - 旧的对话历史仍然保留在旧 Thread 中 (可通过其他方式访问)

    Args:
        user: 用户对象
        session: 数据库会话

    Returns:
        新的 Thread ID
    """
    new_thread_id = str(uuid4())
    user.main_thread_id = new_thread_id

    # 更新数据库
    session.add(user)
    await session.commit()
    await session.refresh(user)

    return new_thread_id
