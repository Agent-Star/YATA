"""
自定义日志配置模块

提供与 uvicorn 一致的彩色日志格式，包括：
- 彩色的日志级别
- Tab 分隔的格式
- 模块名称标识
"""

import logging
import sys
from typing import Any, Dict


class ColoredFormatter(logging.Formatter):
    """
    彩色日志格式化器，模仿 uvicorn 的日志风格

    格式: INFO:		[module.name] Message content
          ^级别 ^tab   ^模块标识    ^内容
    """

    # ANSI 颜色代码
    COLORS: Dict[str, str] = {
        "DEBUG": "\033[36m",  # 青色
        "INFO": "\033[32m",  # 绿色
        "WARNING": "\033[33m",  # 黄色
        "ERROR": "\033[31m",  # 红色
        "CRITICAL": "\033[35m",  # 紫色
    }
    RESET = "\033[0m"
    GRAY = "\033[90m"  # 灰色，用于模块名

    def __init__(
        self,
        fmt: str | None = None,
        datefmt: str | None = None,
        use_colors: bool = True,
        show_module: bool = True,
        strict_module_align: bool = False,
    ):
        """
        Args:
            fmt: 日志格式（如果为 None，使用默认格式）
            datefmt: 日期格式
            use_colors: 是否使用颜色（在非 TTY 环境下可能需要禁用）
            show_module: 是否显示模块名称
            strict_module_align: 是否严格对齐模块名称
        """
        super().__init__(fmt, datefmt)
        self.use_colors = use_colors and self._supports_color()
        self.show_module = show_module
        self.strict_module_align = strict_module_align

    def _supports_color(self) -> bool:
        """
        检查终端是否支持颜色输出
        """
        # Windows 10+ 和类 Unix 系统都支持 ANSI 颜色
        if sys.platform == "win32":
            # Windows 10 1607+ 支持 ANSI 转义码
            try:
                import ctypes

                kernel32 = ctypes.windll.kernel32
                # 启用虚拟终端处理
                kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
                return True
            except Exception:
                return False
        # 类 Unix 系统（Linux, macOS）通常都支持
        return hasattr(sys.stderr, "isatty") and sys.stderr.isatty()

    def format(self, record: logging.LogRecord) -> str:
        """
        格式化日志记录

        格式示例:
        INFO:		[service.service] 初始化用户认证数据库表...
        ERROR:		[auth.init] 超级管理员创建失败: admin
        """
        # 获取日志级别
        levelname = record.levelname

        # 添加颜色
        if self.use_colors and levelname in self.COLORS:
            colored_levelname = f"{self.COLORS[levelname]}{levelname}{self.RESET}"
        else:
            colored_levelname = levelname

        # 构建模块标识
        if self.show_module:
            # 使用 record.name 而不是 record.module，因为 name 包含完整路径
            # 例如: "service.service" 而不是 "service"
            if self.use_colors:
                module_part = f"{self.GRAY}[{record.name}]{self.RESET} "
            else:
                module_part = f"[{record.name}] "
        else:
            module_part = ""

        # 格式化消息内容
        message = record.getMessage()

        # 如果有异常信息，添加到消息末尾
        if record.exc_info:
            if not message.endswith("\n"):
                message += "\n"
            message += self.formatException(record.exc_info)

        if self.strict_module_align:
            # 最终格式: LEVEL:\t\t[module] message
            # 使用两个 tab 来确保对齐（因为 INFO 是 4 字符，WARNING 是 7 字符）
            tab_count = 2 if len(levelname) <= 5 else 1
            tabs = "\t" * tab_count
        else:
            tabs = "  "

        return f"{colored_levelname}:{tabs}{module_part}{message}"


def setup_logging(
    level: int = logging.INFO,
    use_colors: bool = True,
    show_module: bool = True,
    strict_module_align: bool = False,
) -> None:
    """
    配置应用日志系统

    Args:
        level: 日志级别（默认 INFO）
        use_colors: 是否启用彩色输出
        show_module: 是否显示模块名称
        strict_module_align: 是否严格对齐模块名称

    Example:
        >>> from core.logging_config import setup_logging
        >>> import logging
        >>> setup_logging(level=logging.INFO)
        >>> logger = logging.getLogger(__name__)
        >>> logger.info("应用启动成功")
        INFO: [__main__] 应用启动成功
    """
    # 创建格式化器
    formatter = ColoredFormatter(use_colors=use_colors, show_module=show_module)

    # 配置根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # 移除现有的处理器（避免重复日志）
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # 创建控制台处理器
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)

    # 添加到根日志记录器
    root_logger.addHandler(console_handler)

    # 调整第三方库的日志级别（避免过多噪音）
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)


def get_uvicorn_log_config(
    level: str = "info",
    use_colors: bool = True,
) -> Dict[str, Any]:
    """
    获取 uvicorn 的日志配置字典

    用于在 uvicorn.run() 中传入 log_config 参数，
    使 uvicorn 的日志也使用统一的格式。

    Args:
        level: 日志级别字符串 ("debug", "info", "warning", "error")
        use_colors: 是否启用颜色

    Returns:
        uvicorn 兼容的日志配置字典

    Example:
        >>> uvicorn.run(
        ...     "service:app",
        ...     log_config=get_uvicorn_log_config(level="info"),
        ... )
    """
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "()": "core.logging_config.ColoredFormatter",
                "use_colors": use_colors,
                "show_module": True,
            },
            "access": {
                "()": "core.logging_config.ColoredFormatter",
                "use_colors": use_colors,
                "show_module": False,  # access 日志不显示模块名
            },
        },
        "handlers": {
            "default": {
                "formatter": "default",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stderr",
            },
            "access": {
                "formatter": "access",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
            },
        },
        "loggers": {
            "uvicorn": {
                "handlers": ["default"],
                "level": level.upper(),
                "propagate": False,
            },
            "uvicorn.error": {
                "handlers": ["default"],
                "level": level.upper(),
                "propagate": False,
            },
            "uvicorn.access": {
                "handlers": ["access"],
                "level": "INFO",
                "propagate": False,
            },
        },
        "root": {
            "handlers": ["default"],
            "level": level.upper(),
        },
    }
