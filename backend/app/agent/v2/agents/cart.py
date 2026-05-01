from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from sqlalchemy.orm import Session

from app.agent.shared.steps import extract_latest_turn_steps
from app.agent.shared.tools import make_tools
from app.agent.v2.state import ShoppingState

_SYSTEM = (
    "You are a cart specialist for an electronics store. "
    "Help customers add or remove items from their cart. "
    "When adding an item, call search_products first to find the exact product name, "
    "then call add_to_cart immediately if there is exactly one match. "
    "Be concise. Only use the tools provided."
)


def make_cart_node(llm: ChatOpenAI, db: Session, user_id: str, cart_actions: list):
    all_tools = make_tools(db, user_id, cart_actions)
    tool_names = {"add_to_cart", "remove_from_cart", "search_products"}
    tools = [t for t in all_tools if t.name in tool_names]
    agent = create_agent(llm, tools, system_prompt=_SYSTEM)

    def cart_node(state: ShoppingState) -> dict:
        result = agent.invoke(state)  # type: ignore
        tool_steps = extract_latest_turn_steps(result["messages"])
        # Tag each tool step so the Thinking UI can show which specialist acted.
        for step in tool_steps:
            step["agent"] = "cart"
        return {
            "messages": result["messages"],
            # Extract only this turn; result["messages"] also includes MemorySaver history.
            "steps": state["steps"] + tool_steps,
        }

    return cart_node
