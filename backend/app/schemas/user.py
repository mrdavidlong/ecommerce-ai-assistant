from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr


class UserBase(BaseModel):
    name: str
    email: EmailStr


class UserCreate(UserBase):
    pass


class UserRead(UserBase):
    id: UUID
    balance: float
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
