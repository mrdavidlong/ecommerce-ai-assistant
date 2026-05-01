from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.agent.shared.steps import extract_latest_turn_steps, extract_steps


def test_extract_latest_turn_steps_ignores_previous_tool_calls():
    messages = [
        HumanMessage(content="refund my webcam"),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "id": "old_call",
                    "name": "process_item_refund",
                    "args": {"order_id": "abc123", "product_name": "Webcam"},
                }
            ],
        ),
        ToolMessage(content="Refunded Webcam.", tool_call_id="old_call"),
        AIMessage(content="Done."),
        HumanMessage(content="what's good for video conference?"),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "id": "new_call",
                    "name": "search_products",
                    "args": {"query": "video conference"},
                }
            ],
        ),
        ToolMessage(content="Found: Webcam.", tool_call_id="new_call"),
        AIMessage(content="A webcam is best."),
    ]

    all_steps = extract_steps(messages)
    latest_steps = extract_latest_turn_steps(messages)

    assert [step["tool"] for step in all_steps] == ["process_item_refund", "search_products"]
    assert latest_steps == [
        {
            "tool": "search_products",
            "input": "{'query': 'video conference'}",
            "output": "Found: Webcam.",
        }
    ]
