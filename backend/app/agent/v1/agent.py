import os
from typing import Any

from langchain.agents import create_agent
from langchain_core.messages import BaseMessage, HumanMessage
from sqlalchemy.orm import Session

from app.agent.shared.response import extract_last_response
from app.agent.shared.steps import extract_steps
from app.agent.shared.tools import make_tools

SYSTEM_PROMPT = (
    "You are a helpful shopping assistant for an electronics store. "
    "You help customers find products, compare items, check their balance, "
    "and view order history. Be concise and friendly.\n\n"
    "Important rules:\n"
    "- When a user asks to add a product to the cart, call search_products first. "
    "If only one product matches, immediately call add_to_cart — "
    "do not ask for clarification.\n"
    "- If add_to_cart returns 'not found', then search_products to find the closest match "
    "and suggest it to the user.\n"
    "- Never ask 'which model or brand?' when the user has already named a product."
)

_LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o")


def run_agent_v1(
    db: Session,
    user_id: str,
    message: str,
    history: list[BaseMessage],
) -> tuple[str, list[dict], list[dict]]:
    """Run the single-agent and return (response_text, intermediate_steps, cart_actions)."""
    cart_actions: list[dict] = []
    tools = make_tools(db, user_id, cart_actions)
    agent = create_agent(_LLM_MODEL, tools, system_prompt=SYSTEM_PROMPT)

    all_messages = history + [HumanMessage(content=message)]
    result: dict[str, Any] = agent.invoke({"messages": all_messages})  # type: ignore[arg-type]

    messages: list[BaseMessage] = result.get("messages", [])
    steps = extract_steps(messages)

    response = extract_last_response(messages)
    return response or "I'm sorry, I couldn't process that request.", steps, cart_actions
