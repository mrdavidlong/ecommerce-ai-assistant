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


def apply_item_refund(
    db: Session, item: OrderItem, order: Order, user: User, refund_qty: int = None
) -> float:
    """Refund one or more units of an order item. Returns the refund amount.

    Args:
        refund_qty: number of units to refund. If None, refunds all remaining units.
    """
    if refund_qty is None:
        refund_qty = item.quantity - item.refunded_quantity
    refund_amount = item.price * refund_qty
    item.refunded_quantity += refund_qty
    if item.refunded_quantity >= item.quantity:
        item.refunded = True
    user.balance += refund_amount

    product = db.query(Product).filter(Product.id == item.product_id).first()
    if product:
        product.stock_quantity += refund_qty

    if all(i.refunded for i in order.items):
        order.refunded = True

    db.commit()
    return refund_amount
