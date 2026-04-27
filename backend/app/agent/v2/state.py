from typing import Annotated, Literal

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel
from typing_extensions import TypedDict


class ShoppingState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    agent_name: str
    cart_actions: list[dict]
    steps: list[dict]


class SupervisorDecision(BaseModel):
    route: Literal["product", "account", "cart", "general"]
    reasoning: str
