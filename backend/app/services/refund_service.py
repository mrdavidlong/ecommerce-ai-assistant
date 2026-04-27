from sqlalchemy.orm import Session

from app.models.order import Order
from app.models.order_item import OrderItem
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


def apply_item_refund(db: Session, item: OrderItem, order: Order, user: User) -> float:
    """Refund a single order item. Returns the refund amount."""
    refund_amount = item.price * item.quantity
    item.refunded = True
    user.balance += refund_amount

    product = db.query(Product).filter(Product.id == item.product_id).first()
    if product:
        product.stock_quantity += item.quantity

    if all(i.refunded for i in order.items):
        order.refunded = True

    db.commit()
    return refund_amount
