from langchain_core.messages import AIMessage, HumanMessage, ToolMessage


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


def extract_latest_turn_steps(messages: list) -> list[dict]:
    """Extract tool steps that occurred after the latest user message only."""
    latest_human_idx = -1
    for idx, msg in enumerate(messages):
        if isinstance(msg, HumanMessage):
            latest_human_idx = idx
    return extract_steps(messages[latest_human_idx + 1 :])
