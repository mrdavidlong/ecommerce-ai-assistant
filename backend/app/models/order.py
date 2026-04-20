from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.order_item import OrderItem


class Order(Base):
    __tablename__ = "orders"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    total: Mapped[float] = mapped_column(Float, nullable=False)
    refunded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    items: Mapped[list["OrderItem"]] = relationship(
        "OrderItem", back_populates="order", cascade="all, delete-orphan"
    )
