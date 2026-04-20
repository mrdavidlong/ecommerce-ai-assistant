from typing import Literal

from pydantic import BaseModel


class ChatRequest(BaseModel):
    user_id: str
    message: str
    session_id: str


class AgentStep(BaseModel):
    tool: str
    input: str
    output: str


class CartAction(BaseModel):
    action: Literal["add", "remove"]
    product_id: str
    product_name: str
    quantity: int
    price: float


class ChatResponse(BaseModel):
    response: str
    steps: list[AgentStep]
    cart_actions: list[CartAction] = []
