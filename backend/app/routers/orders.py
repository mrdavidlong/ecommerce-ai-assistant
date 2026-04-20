from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.product import Product
from app.models.user import User
from app.schemas.order import OrderCreate, OrderItemRead, OrderRead, RefundResponse
from app.services.refund_service import apply_refund
from app.services.user_service import get_user_by_id

router = APIRouter(prefix="/orders", tags=["orders"])


def _serialize_order(order: Order) -> dict:
    return {
        "id": order.id,
        "user_id": order.user_id,
        "total": order.total,
        "refunded": order.refunded,
        "created_at": order.created_at,
        "items": [
            OrderItemRead(
                id=item.id,
                order_id=item.order_id,
                product_id=item.product_id,
                product_name=item.product.name,
                quantity=item.quantity,
                price=item.price,
            )
            for item in order.items
        ],
    }


@router.post("/", response_model=OrderRead, status_code=201)
def create_order(payload: OrderCreate, db: Session = Depends(get_db)):
    if not payload.items:
        raise HTTPException(status_code=400, detail="Order must contain at least one item")

    user = db.query(User).filter(User.id == payload.user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    product_map: dict = {}
    for item in payload.items:
        if item.quantity < 1:
            raise HTTPException(status_code=400, detail="Quantity must be at least 1")
        product = db.query(Product).filter(Product.id == item.product_id).first()
        if product is None:
            raise HTTPException(status_code=404, detail=f"Product {item.product_id} not found")
        product_map[item.product_id] = product

    total = sum(product_map[item.product_id].price * item.quantity for item in payload.items)

    if user.balance < total:
        raise HTTPException(status_code=400, detail="Insufficient balance")

    for item in payload.items:
        product = product_map[item.product_id]
        if product.stock_quantity < item.quantity:
            raise HTTPException(status_code=400, detail=f"Insufficient stock for {product.name}")

    try:
        user.balance -= total

        order = Order(user_id=user.id, total=total)
        db.add(order)
        db.flush()

        for item in payload.items:
            product = product_map[item.product_id]
            product.stock_quantity -= item.quantity
            db.add(
                OrderItem(
                    order_id=order.id,
                    product_id=product.id,
                    quantity=item.quantity,
                    price=product.price,
                )
            )

        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to create order")

    order = (
        db.query(Order)
        .options(selectinload(Order.items).joinedload(OrderItem.product))
        .filter(Order.id == order.id)
        .one()
    )
    return _serialize_order(order)


@router.get("/", response_model=list[OrderRead])
def list_orders(user_id: UUID, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    orders = (
        db.query(Order)
        .options(selectinload(Order.items).joinedload(OrderItem.product))
        .filter(Order.user_id == user_id)
        .order_by(Order.created_at.desc())
        .all()
    )
    return [_serialize_order(o) for o in orders]


@router.post("/{order_id}/refund", response_model=RefundResponse)
def refund_order(order_id: UUID, user_id: UUID, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.user_id != user_id:
        raise HTTPException(status_code=403, detail="Order does not belong to this user")
    if order.refunded:
        raise HTTPException(status_code=400, detail="Order has already been refunded")

    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        apply_refund(db, order, user)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to process refund")

    return RefundResponse(
        order_id=order.id,
        refunded_amount=order.total,
        new_balance=user.balance,
    )
