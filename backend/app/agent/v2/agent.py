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

    # initial_state is applied as an update to the saved graph state for this thread_id.
    # messages has the add_messages reducer, so this HumanMessage is merged with prior turns.
    # The other fields have no reducer, so these values intentionally reset per request:
    # - agent_name is recalculated by the supervisor
    # - steps is rebuilt for this turn's Thinking trace
    # - cart_actions in graph state is shape-only; tools append to the request-scoped list above
    initial_state: dict = {
        "messages": [HumanMessage(content=message)],
        "agent_name": "",
        "cart_actions": [],
        "steps": [],  # Reset per request so the UI shows only this turn's trace.
    }

    final_state = graph.invoke(initial_state, config=config)

    messages: list[BaseMessage] = final_state.get("messages", [])
    steps: list[dict] = final_state.get("steps", [])
    agent_name: str = final_state.get("agent_name", "unknown")
    response = extract_last_response(messages)

    fallback = "I'm sorry, I couldn't process that request."
    return response or fallback, steps, cart_actions, agent_name
