from datetime import datetime
from typing import List
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class OrderItemCreate(BaseModel):
    product_id: UUID
    quantity: int


class OrderCreate(BaseModel):
    user_id: UUID
    items: List[OrderItemCreate]


class OrderItemRead(BaseModel):
    id: UUID
    order_id: UUID
    product_id: UUID
    product_name: str
    quantity: int
    price: float

    model_config = ConfigDict(from_attributes=True)


class OrderRead(BaseModel):
    id: UUID
    user_id: UUID
    total: float
    refunded: bool
    created_at: datetime
    items: List[OrderItemRead]

    model_config = ConfigDict(from_attributes=True)


class RefundResponse(BaseModel):
    order_id: UUID
    refunded_amount: float
    new_balance: float
