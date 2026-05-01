from typing import Annotated, Literal

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel
from typing_extensions import TypedDict


class ShoppingState(TypedDict):
    # Conversation context for the graph. add_messages merges each new turn into the
    # saved MemorySaver thread instead of replacing prior messages.
    messages: Annotated[list[BaseMessage], add_messages]
    # Current supervisor route label: "product", "account", "cart", or "general".
    # graph.py maps this label to the destination agent node ID.
    agent_name: str
    # State shape for cart side effects. In practice, tools append frontend cart actions
    # to the request-scoped list captured by make_tools(), then run_agent_v2 returns it.
    cart_actions: list[dict]
    # Per-request UI trace for the Thinking accordion. No reducer: nodes must return
    # state["steps"] + new steps, and run_agent_v2 resets it at the start of each request.
    steps: list[dict]


class SupervisorDecision(BaseModel):
    # Structured LLM output from supervisor_agent.
    # route must match one of the route labels handled by graph.py.
    route: Literal["product", "account", "cart", "general"]
    # Short explanation captured for the UI-visible supervisor step.
    reasoning: str
