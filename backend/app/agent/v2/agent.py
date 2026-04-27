from langchain_core.messages import BaseMessage, HumanMessage
from sqlalchemy.orm import Session

from app.agent.shared.response import extract_last_response
from app.agent.v2.graph import build_graph


def run_agent_v2(
    db: Session,
    user_id: str,
    message: str,
    session_id: str,
) -> tuple[str, list[dict], list[dict], str]:
    """Run the multi-agent graph and return (response, steps, cart_actions, agent_name)."""
    cart_actions: list[dict] = []
    graph = build_graph(db, user_id, cart_actions)

    config = {"configurable": {"thread_id": session_id}}

    # Only pass the current message — MemorySaver restores prior turns via thread_id
    initial_state: dict = {
        "messages": [HumanMessage(content=message)],
        "agent_name": "",
        "cart_actions": [],
        "steps": [],
    }

    final_state = graph.invoke(initial_state, config=config)

    messages: list[BaseMessage] = final_state.get("messages", [])
    steps: list[dict] = final_state.get("steps", [])
    agent_name: str = final_state.get("agent_name", "unknown")
    response = extract_last_response(messages)

    fallback = "I'm sorry, I couldn't process that request."
    return response or fallback, steps, cart_actions, agent_name
