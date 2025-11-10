"""
时间戳管理工具

为 Agent 消息自动添加时间戳，确保所有消息都有准确的创建时间。

使用方式：
1. 对于 StateGraph 模式的 Agent：在 acall_model 函数上使用 @with_message_timestamps 装饰器
2. 对于 @entrypoint 模式的 Agent：在返回前调用 add_timestamps_to_messages()
3. 对于用户输入消息：使用 create_timestamped_message() 创建 HumanMessage
"""

from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from functools import wraps
from typing import Any, TypeVar

from langchain_core.messages import BaseMessage, HumanMessage

# Type variable for generic decorators
T = TypeVar("T")


def get_utc_timestamp() -> str:
    """
    获取当前 UTC 时间戳 (ISO 8601 格式)

    Returns:
        ISO 8601 格式的时间戳字符串，例如: "2025-01-27T10:30:45.123456+00:00"
    """
    return datetime.now(timezone.utc).isoformat()


def add_timestamp_to_message(message: BaseMessage) -> BaseMessage:
    """
    为单个消息添加时间戳（如果尚未存在）

    Args:
        message: LangChain 消息对象

    Returns:
        添加了时间戳的消息对象（原地修改）
    """
    # 检查是否已有时间戳
    if hasattr(message, "additional_kwargs"):
        additional_kwargs = getattr(message, "additional_kwargs", {})
        if additional_kwargs and (
            "created_at" in additional_kwargs or "timestamp" in additional_kwargs
        ):
            # 已有时间戳，不覆盖
            return message

    # 添加时间戳
    if not hasattr(message, "additional_kwargs") or message.additional_kwargs is None:
        message.additional_kwargs = {}

    message.additional_kwargs["created_at"] = get_utc_timestamp()
    return message


def add_timestamps_to_messages(messages: list[BaseMessage]) -> list[BaseMessage]:
    """
    批量为消息列表添加时间戳

    Args:
        messages: 消息列表

    Returns:
        添加了时间戳的消息列表
    """
    return [add_timestamp_to_message(msg) for msg in messages]


def create_timestamped_message(
    content: str,
    message_type: type[BaseMessage] = HumanMessage,
    **kwargs: Any,
) -> BaseMessage:
    """
    创建带时间戳的消息

    Args:
        content: 消息内容
        message_type: 消息类型（HumanMessage, AIMessage 等）
        **kwargs: 传递给消息构造函数的其他参数

    Returns:
        带时间戳的消息对象

    Example:
        >>> msg = create_timestamped_message("你好", HumanMessage)
        >>> msg.additional_kwargs["created_at"]
        "2025-01-27T10:30:45.123456+00:00"
    """
    # 确保 additional_kwargs 包含时间戳
    additional_kwargs = kwargs.pop("additional_kwargs", {})
    if "created_at" not in additional_kwargs and "timestamp" not in additional_kwargs:
        additional_kwargs["created_at"] = get_utc_timestamp()

    return message_type(content=content, additional_kwargs=additional_kwargs, **kwargs)


def with_message_timestamps(
    func: Callable[..., Awaitable[Any]],
) -> Callable[..., Awaitable[Any]]:
    """
    装饰器：自动为 Agent 函数返回的消息添加时间戳

    适用于 StateGraph 模式的 Agent 节点函数，例如 acall_model()

    Args:
        func: 异步函数，返回包含 "messages" 键的字典

    Returns:
        包装后的函数，会自动为返回的消息添加时间戳

    Example:
        >>> @with_message_timestamps
        >>> async def acall_model(state: AgentState, config: RunnableConfig) -> AgentState:
        >>>     response = await model.ainvoke(state["messages"])
        >>>     return {"messages": [response]}  # 自动添加时间戳
    """

    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        result = await func(*args, **kwargs)

        # 检查返回值是否包含 messages
        if isinstance(result, dict) and "messages" in result:
            messages = result["messages"]
            if isinstance(messages, list):
                # 为所有消息添加时间戳
                result["messages"] = add_timestamps_to_messages(messages)

        return result

    return wrapper


# 便捷的别名
timestamped = with_message_timestamps  # 简短别名
