from langchain_core.messages import AIMessage, ToolMessage


def extract_steps(messages: list) -> list[dict]:
    """Extract tool call/result pairs from a message list into step dicts."""
    steps: list[dict] = []
    tool_call_map: dict[str, dict] = {}
    for msg in messages:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                if tc["id"] is None:
                    continue
                tool_call_map[tc["id"]] = {"tool": tc["name"], "input": str(tc["args"])}
        elif isinstance(msg, ToolMessage):
            entry = tool_call_map.get(msg.tool_call_id, {})
            steps.append(
                {
                    "tool": entry.get("tool", "unknown"),
                    "input": entry.get("input", ""),
                    "output": str(msg.content),
                }
            )
    return steps
