from langchain_core.messages import AIMessage, BaseMessage


def extract_last_response(messages: list[BaseMessage]) -> str:
    """Return the content of the last AIMessage that has no tool calls."""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and not msg.tool_calls:
            return str(msg.content)
    return ""
