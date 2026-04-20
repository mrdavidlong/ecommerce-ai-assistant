from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ProductRead(BaseModel):
    id: UUID
    name: str
    description: str
    image_url: str
    price: float
    stock_quantity: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
