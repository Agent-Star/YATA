from langchain_core.messages import BaseMessage
from langchain_core.runnables import RunnableConfig
from langgraph.func import entrypoint

from agents.timestamp import add_timestamp_to_message
from core import get_model, settings


@entrypoint()
async def chatbot(
    inputs: dict[str, list[BaseMessage]],
    *,
    previous: dict[str, list[BaseMessage]],
    config: RunnableConfig,
):
    messages = inputs["messages"]
    if previous:
        messages = previous["messages"] + messages

    model = get_model(config.get("configurable", {}).get("model", settings.DEFAULT_MODEL))
    response = await model.ainvoke(messages)

    # 为响应添加时间戳
    response = add_timestamp_to_message(response)

    return entrypoint.final(
        value={"messages": [response]},
        save={"messages": messages + [response]}
    )
