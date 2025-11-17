"""
Thread 管理工具

提供用户 Thread 的创建、获取和管理功能.
"""

import logging
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from auth.models import User
from external_services.nlu_client import get_nlu_client

logger = logging.getLogger(__name__)


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
    user = await session.get(User, UUID(user_id))
    return user.main_thread_id if user else None


async def create_new_thread_for_user(user: User, session: AsyncSession) -> str:
    """
    为用户创建新的 Thread (用于"新建对话"功能)

    当前实现为"单 Thread + 清空"模式:
    - 创建新 Thread ID
    - 更新为用户的主 Thread
    - 旧的对话历史仍然保留在旧 Thread 中 (可通过其他方式访问)
    - 通知 NLU 服务删除旧 Thread 对应的 session

    Args:
        user: 用户对象
        session: 数据库会话

    Returns:
        新的 Thread ID
    """
    # 保存旧的 thread_id, 用于清理 NLU session
    old_thread_id = user.main_thread_id

    # 创建新 Thread ID
    new_thread_id = str(uuid4())
    user.main_thread_id = new_thread_id

    # 更新数据库
    session.add(user)
    await session.commit()
    await session.refresh(user)

    # 通知 NLU 清理旧的 session (非阻塞, 失败不影响主流程)
    if old_thread_id:
        try:
            async with get_nlu_client() as nlu_client:
                success = await nlu_client.delete_session(old_thread_id)
                if success:
                    logger.info(f"Successfully deleted NLU session for old thread {old_thread_id}")
                else:
                    logger.warning(f"Failed to delete NLU session for old thread {old_thread_id}")
        except Exception as e:
            logger.warning(f"Error deleting NLU session for old thread {old_thread_id}: {e}")

    return new_thread_id


async def cleanup_thread(thread_id: str) -> bool:
    """
    清理指定的 Thread 及其关联的 NLU session

    用于以下场景:
    - 用户主动删除对话
    - 对话超时或用户离线
    - 任务完成且不需要后续追问

    Args:
        thread_id: 要清理的 Thread ID

    Returns:
        bool: True 表示清理成功, False 表示清理失败
    """
    try:
        async with get_nlu_client() as nlu_client:
            success = await nlu_client.delete_session(thread_id)
            if success:
                logger.info(f"Successfully cleaned up NLU session for thread {thread_id}")
            else:
                logger.warning(f"Failed to clean up NLU session for thread {thread_id}")
            return success
    except Exception as e:
        logger.error(f"Error cleaning up thread {thread_id}: {e}")
        return False
