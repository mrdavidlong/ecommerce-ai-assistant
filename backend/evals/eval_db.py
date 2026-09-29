"""
Database state for eval runs: reset to a known baseline, seed orders, and snapshot the outcome.

Every eval example starts from the same state, so refunds or cart changes made while answering
one example cannot leak into the next, and state assertions have a fixed starting point.
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.seed import _PRODUCTS

_SEED_BALANCE = 1000.0

# Fixed order ids so golden queries can reference an order by its 8-character prefix.
RECENT_ORDER_ID = UUID("5eed0001-0000-4000-8000-000000000001")
OLD_ORDER_ID = UUID("5eed0002-0000-4000-8000-000000000002")
OTHER_USER_ORDER_ID = UUID("5eed0003-0000-4000-8000-000000000003")

# Age of each seeded order in days; the refund window is 30 days (see agent/shared/tools.py).
_RECENT_ORDER_AGE_DAYS = 1
_OLD_ORDER_AGE_DAYS = 45
_OTHER_ORDER_AGE_DAYS = 2

# Seeded orders as (order id, owner index, age in days, [(product name, quantity)]).
# Owner index 0 is the eval user, 1 is another user. Order totals are derived from live prices.
_SEED_ORDERS = [
    (RECENT_ORDER_ID, 0, _RECENT_ORDER_AGE_DAYS, [("Wireless Mouse", 2), ("Webcam", 1)]),
    (OLD_ORDER_ID, 0, _OLD_ORDER_AGE_DAYS, [("Mechanical Keyboard", 1)]),
    (OTHER_USER_ORDER_ID, 1, _OTHER_ORDER_AGE_DAYS, [("Laptop", 1)]),
]


def get_eval_users(db: Session) -> list:
    """Return users in a stable order (by email); index 0 is the user the evals act as."""
    from app.models.user import User

    return db.query(User).order_by(User.email).all()


def reset_eval_db(db: Session) -> None:
    """Reset the database to the eval baseline and seed the eval orders.

    Clears all orders, restores every user's balance and every product's stock to the seed
    values, then creates the orders in _SEED_ORDERS. Commits on success.

    Args:
        db: SQLAlchemy session on the application database.

    Raises:
        RuntimeError: If there are fewer than two users or a seeded product is missing
            (the app has never been started to seed the database).
    """
    from app.models.order import Order
    from app.models.order_item import OrderItem
    from app.models.product import Product
    from app.models.user import User

    try:
        db.query(OrderItem).delete()
        db.query(Order).delete()
        db.query(User).update({"balance": _SEED_BALANCE})
        for product in _PRODUCTS:
            db.query(Product).filter(Product.name == product.name).update(
                {"stock_quantity": product.stock_quantity}
            )
        _seed_eval_orders(db)
        db.commit()
    except Exception:
        db.rollback()
        raise


def _seed_eval_orders(db: Session) -> None:
    """Add the _SEED_ORDERS rows to the session (the caller commits)."""
    from app.models.order import Order
    from app.models.order_item import OrderItem
    from app.models.product import Product

    users = get_eval_users(db)
    if len(users) < 2:
        raise RuntimeError("Need at least two users — start the app once to seed the database.")
    products = {p.name: p for p in db.query(Product).all()}
    now = datetime.now(timezone.utc)

    for order_id, owner_index, age_days, lines in _SEED_ORDERS:
        missing = [name for name, _ in lines if name not in products]
        if missing:
            raise RuntimeError(f"Seed products missing from the database: {missing}")
        items = [
            OrderItem(product_id=products[name].id, quantity=qty, price=products[name].price)
            for name, qty in lines
        ]
        created = now - timedelta(days=age_days)
        db.add(
            Order(
                id=order_id,
                user_id=users[owner_index].id,
                total=sum(i.price * i.quantity for i in items),
                items=items,
                created_at=created,
                updated_at=created,
            )
        )


def embed_eval_products(db: Session) -> int:
    """Build the in-memory ChromaDB product index for this eval process.

    The index is only populated by the FastAPI startup hook, so a standalone eval process starts
    with an empty index and every search_products call returns "No products found".

    Args:
        db: SQLAlchemy session to read products from.

    Returns:
        Number of products embedded.

    Raises:
        RuntimeError: If the database has no products (the app has never been started to seed it).
    """
    from app.agent.shared import rag
    from app.models.product import Product

    products = db.query(Product).all()
    if not products:
        raise RuntimeError("No products in the database — start the app once to seed it.")
    rag.embed_products(products)
    return len(products)


def snapshot_state(db: Session, user_id: str, cart_actions: list[dict]) -> dict:
    """Capture the outcome of an agent run for state assertions.

    Args:
        db: SQLAlchemy session (expired first so writes made by the agent's session are visible).
        user_id: Id of the user the agent acted as.
        cart_actions: The cart actions the agent's tools appended during the run.

    Returns:
        Dict with: balance (user balance rounded to cents), refunded (product name -> units
        refunded, only non-zero, across the user's orders), stock (product name -> stock
        quantity), cart_actions (list of {action, product_name, quantity}).
    """
    from app.models.order import Order
    from app.models.order_item import OrderItem
    from app.models.product import Product
    from app.models.user import User

    db.expire_all()
    user = db.get(User, UUID(user_id))
    refunded: dict[str, int] = {}
    items = (
        db.query(OrderItem)
        .join(Order, OrderItem.order_id == Order.id)
        .filter(Order.user_id == UUID(user_id), OrderItem.refunded_quantity > 0)
        .all()
    )
    for item in items:
        refunded[item.product.name] = refunded.get(item.product.name, 0) + item.refunded_quantity
    return {
        "balance": round(user.balance, 2),
        "refunded": refunded,
        "stock": {p.name: p.stock_quantity for p in db.query(Product).all()},
        "cart_actions": [
            {k: a[k] for k in ("action", "product_name", "quantity")} for a in cart_actions
        ],
    }
