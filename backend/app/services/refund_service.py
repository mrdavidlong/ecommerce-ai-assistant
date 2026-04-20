from sqlalchemy.orm import Session

from app.models.order import Order
from app.models.product import Product
from app.models.user import User


def apply_refund(db: Session, order: Order, user: User) -> None:
    """Atomically mark order refunded, restore balance, and restore stock for all items."""
    order.refunded = True
    user.balance += order.total

    product_ids = [item.product_id for item in order.items]
    products = {p.id: p for p in db.query(Product).filter(Product.id.in_(product_ids)).all()}
    for item in order.items:
        if item.product_id in products:
            products[item.product_id].stock_quantity += item.quantity

    db.commit()
