import asyncio
import sys

import uvicorn
from dotenv import load_dotenv

from core import settings
from core.logging_config import get_uvicorn_log_config, setup_logging

load_dotenv()

if __name__ == "__main__":
    # 配置统一的彩色日志格式
    setup_logging(level=settings.LOG_LEVEL.to_logging_level())

    # Set Compatible event loop policy on Windows Systems.
    # On Windows systems, the default ProactorEventLoop can cause issues with
    # certain async database drivers like psycopg (PostgreSQL driver).
    # The WindowsSelectorEventLoopPolicy provides better compatibility and prevents
    # "RuntimeError: Event loop is closed" errors when working with database connections.
    # This needs to be set before running the application server.
    # Refer to the documentation for more information.
    # https://www.psycopg.org/psycopg3/docs/advanced/async.html#asynchronous-operations
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    # 启动 uvicorn 服务器，使用统一的日志配置
    uvicorn.run(
        "service:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.is_dev(),
        timeout_graceful_shutdown=settings.GRACEFUL_SHUTDOWN_TIMEOUT,
        log_config=get_uvicorn_log_config(level=settings.LOG_LEVEL.value.lower()),
    )
