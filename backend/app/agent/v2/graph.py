import os

from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from app.agent.v2.agents.account import make_account_node
from app.agent.v2.agents.cart import make_cart_node
from app.agent.v2.agents.general import make_general_node
from app.agent.v2.agents.product import make_product_node
from app.agent.v2.agents.supervisor import make_supervisor_node
from app.agent.v2.state import ShoppingState

_LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o")

# Module-level singletons — shared across all requests
_llm = ChatOpenAI(model=_LLM_MODEL, temperature=0)
# In-memory LangGraph checkpointer keyed by config["configurable"]["thread_id"].
_checkpointer = MemorySaver()


def build_graph(db: Session, user_id: str, cart_actions: list):
    builder = StateGraph(ShoppingState)

    builder.add_node("supervisor_agent", make_supervisor_node(_llm))
    builder.add_node("product_agent", make_product_node(_llm, db, user_id, cart_actions))
    builder.add_node("account_agent", make_account_node(_llm, db, user_id, cart_actions))
    builder.add_node("cart_agent", make_cart_node(_llm, db, user_id, cart_actions))
    builder.add_node("general_agent", make_general_node(_llm))

    builder.set_entry_point("supervisor_agent")

    # Map supervisor route labels to graph node IDs.
    builder.add_conditional_edges(
        "supervisor_agent",
        lambda state: state["agent_name"],
        {
            "product": "product_agent",
            "account": "account_agent",
            "cart": "cart_agent",
            "general": "general_agent",
        },
    )

    for node in ("product_agent", "account_agent", "cart_agent", "general_agent"):
        builder.add_edge(node, END)

    return builder.compile(checkpointer=_checkpointer)
