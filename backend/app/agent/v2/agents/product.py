from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from sqlalchemy.orm import Session

from app.agent.shared.steps import extract_latest_turn_steps
from app.agent.shared.tools import make_tools
from app.agent.v2.state import ShoppingState

_SYSTEM = (
    "You are a product specialist for an electronics store. "
    "Help customers find products, compare items, and discover what they can afford. "
    "Be concise and helpful. Only use the tools provided."
)


def make_product_node(llm: ChatOpenAI, db: Session, user_id: str, cart_actions: list):
    all_tools = make_tools(db, user_id, cart_actions)
    tool_names = {"search_products", "compare_products", "get_affordable_products"}
    tools = [t for t in all_tools if t.name in tool_names]
    agent = create_agent(llm, tools, system_prompt=_SYSTEM)

    def product_node(state: ShoppingState) -> dict:
        result = agent.invoke(state)  # type: ignore
        return {
            "messages": result["messages"],
            # Extract only this turn; result["messages"] also includes MemorySaver history.
            "steps": state["steps"] + extract_latest_turn_steps(result["messages"]),
        }

    return product_node
