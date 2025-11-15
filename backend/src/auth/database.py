"""数据库适配器配置"""

from collections.abc import AsyncGenerator

from fastapi import Depends
from fastapi_users.db import SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from auth.models import Base, User
from core.settings import DatabaseType, settings

# === 数据库引擎和会话管理 ===


def get_database_url(async_mode: bool = True) -> str:
    """获取数据库连接 URL

    Args:
        async_mode: 是否返回异步数据库 URL

    Returns:
        数据库连接字符串
    """
    if settings.DATABASE_TYPE == DatabaseType.POSTGRES:
        if not all(
            [
                settings.POSTGRES_USER,
                settings.POSTGRES_PASSWORD,
                settings.POSTGRES_HOST,
                settings.POSTGRES_PORT,
                settings.POSTGRES_DB,
            ]
        ):
            raise ValueError("PostgreSQL 配置不完整")

        driver = "postgresql+asyncpg" if async_mode else "postgresql+psycopg"
        password = (
            settings.POSTGRES_PASSWORD.get_secret_value() if settings.POSTGRES_PASSWORD else ""
        )

        return (
            f"{driver}://{settings.POSTGRES_USER}:{password}@"
            f"{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/"
            f"{settings.POSTGRES_DB}"
        )
    else:  # SQLite
        driver = "sqlite+aiosqlite" if async_mode else "sqlite"
        return f"{driver}:///{settings.SQLITE_DB_PATH}"


# 创建异步数据库引擎
async_engine = create_async_engine(get_database_url(async_mode=True), echo=False)

# 创建异步会话工厂
async_session_maker = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def create_db_and_tables():
    """
    创建数据库表

    仅在应用启动时调用一次
    """
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    获取异步数据库会话

    用作 FastAPI 依赖项
    """
    async with async_session_maker() as session:
        yield session


async def get_user_db(
    session: AsyncSession = Depends(get_async_session),
) -> AsyncGenerator[SQLAlchemyUserDatabase, None]:
    """
    获取用户数据库访问器

    用作 FastAPI 依赖项，提供对用户表的访问
    """
    yield SQLAlchemyUserDatabase(session, User)
