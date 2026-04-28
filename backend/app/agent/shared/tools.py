from datetime import datetime, timezone
from uuid import UUID as _UUID

from langchain_core.tools import tool
from sqlalchemy import String, cast
from sqlalchemy.orm import Session, selectinload

from app.agent.shared.rag import search_products_rag
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.product import Product
from app.services.refund_service import apply_item_refund
from app.services.user_service import get_user_by_id

_REFUND_WINDOW_DAYS = 30


def _stock_status(qty: int) -> str:
    return f"{qty} in stock" if qty > 0 else "out of stock"


def _short_id(id: object) -> str:
    return str(id)[:8]


def _trunc(s: str, max_len: int = 60) -> str:
    return s[:max_len] + "..." if len(s) > max_len else s


def make_tools(db: Session, user_id: str, cart_actions: list) -> list:
    uid = _UUID(user_id)

    @tool
    def search_products(query: str) -> str:
        """Search for products using natural language. Use this when the user asks for product
        recommendations, wants to find items matching a use-case, or asks what's available."""
        results = search_products_rag(query, n=4)
        if not results:
            return "No products found matching that query."
        # Fetch live stock from DB — ChromaDB metadata is stale after orders/refunds
        product_ids = [r["product_id"] for r in results]
        product_uuids = [_UUID(pid) for pid in product_ids]
        live_stock = {
            str(p.id): p.stock_quantity
            for p in db.query(Product).filter(Product.id.in_(product_uuids)).all()
        }
        lines = ["Here are the most relevant products:"]
        for r in results:
            qty = live_stock.get(r["product_id"], 0)
            lines.append(f"- {r['name']}: ${r['price']:.2f} ({_stock_status(qty)})")
        return "\n".join(lines)

    @tool
    def compare_products(product_a: str, product_b: str) -> str:
        """Compare two products side by side. Takes two product names.
        Use this when the user asks to compare two specific products."""
        a = db.query(Product).filter(Product.name.ilike(f"%{product_a}%")).first()
        b = db.query(Product).filter(Product.name.ilike(f"%{product_b}%")).first()
        if not a and not b:
            return f"Could not find products matching '{product_a}' or '{product_b}'."
        if not a:
            return f"Could not find a product matching '{product_a}'."
        if not b:
            return f"Could not find a product matching '{product_b}'."

        return (
            f"Comparison: {a.name} vs {b.name}\n"
            f"Price:        ${a.price:.2f}  vs  ${b.price:.2f}\n"
            f"Availability: {_stock_status(a.stock_quantity)}"
            f"  vs  {_stock_status(b.stock_quantity)}\n"
            f"{a.name} — {_trunc(a.description)}\n"
            f"{b.name} — {_trunc(b.description)}"
        )

    @tool
    def get_order_history(_: str = "") -> str:
        """Get the current user's recent order history including individual items.
        Use this when the user asks about their past orders or purchase history. No input needed."""
        orders = (
            db.query(Order)
            .options(selectinload(Order.items).selectinload(OrderItem.product))
            .filter(Order.user_id == uid)
            .order_by(Order.created_at.desc())
            .limit(5)
            .all()
        )
        if not orders:
            return "You have no orders yet."
        lines = [f"Your last {len(orders)} order(s), newest first:"]
        for o in orders:
            order_status = " [Fully refunded]" if o.refunded else ""
            lines.append(
                f"\nOrder #{_short_id(o.id)} on {o.created_at.strftime('%Y-%m-%d')}: "
                f"${o.total:.2f}{order_status}"
            )
            for item in o.items:
                name = item.product.name if item.product else "Unknown product"
                if item.refunded:
                    item_status = " [Fully refunded]"
                elif item.refunded_quantity > 0:
                    remaining = item.quantity - item.refunded_quantity
                    refunded = item.refunded_quantity
                    item_status = (
                        f" [{refunded} of {item.quantity} refunded, {remaining} remaining]"
                    )
                else:
                    item_status = ""
                lines.append(f"  - {name} × {item.quantity}: ${item.price:.2f} each{item_status}")
        return "\n".join(lines)

    @tool
    def get_user_balance(_: str = "") -> str:
        """Get the current user's account balance. Use this when the user asks about
        their balance, how much they can spend, or what they can afford. No input needed."""
        user = get_user_by_id(db, uid)
        if not user:
            return "User not found."
        return f"Your current balance is ${user.balance:.2f}."

    @tool
    def get_affordable_products(_: str = "") -> str:
        """List all products the user can currently afford based on their balance.
        Use this when the user asks 'what can I afford?', 'what's in my budget?',
        or 'what can I buy right now?'. No input needed."""
        user = get_user_by_id(db, uid)
        if not user:
            return "User not found."
        products = (
            db.query(Product)
            .filter(Product.price <= user.balance, Product.stock_quantity > 0)
            .order_by(Product.price.desc())
            .all()
        )
        if not products:
            return (
                f"With your current balance of ${user.balance:.2f}, "
                "you cannot afford any available products."
            )
        count = len(products)
        lines = [f"With your balance of ${user.balance:.2f}, you can afford {count} product(s):"]
        for p in products:
            lines.append(f"- {p.name}: ${p.price:.2f} ({_stock_status(p.stock_quantity)})")
        return "\n".join(lines)

    @tool
    def process_item_refund(order_id: str, product_name: str, quantity: int = 1) -> str:
        """Refund one or more units of a specific item from an order. Takes an order ID prefix
        (first 8 characters shown in order history), the product name, and an optional quantity
        to refund (default 1). Use this when the user wants to refund part or all of an item."""
        matched_orders = (
            db.query(Order)
            .options(selectinload(Order.items).selectinload(OrderItem.product))
            .filter(
                Order.user_id == uid,
                cast(Order.id, String).like(f"{order_id.strip()}%"),
            )
            .all()
        )
        if not matched_orders:
            return (
                f"No order found with ID starting with '{order_id}'. "
                "Use get_order_history to see your orders."
            )
        if len(matched_orders) > 1:
            return "Multiple orders match that ID prefix. Please provide more characters."
        order = matched_orders[0]

        needle = product_name.lower()
        item = next(
            (i for i in order.items if i.product and needle in i.product.name.lower()),
            None,
        )
        if not item:
            return (
                f"No item matching '{product_name}' found in Order #{_short_id(order.id)}. "
                "Use get_order_history to see the items in your order."
            )
        remaining = item.quantity - item.refunded_quantity
        if remaining == 0:
            name = item.product.name if item.product else product_name
            return f"{name} in Order #{_short_id(order.id)} has already been fully refunded."
        if quantity > remaining:
            return (
                f"Can only refund {remaining} more unit(s) of {product_name} "
                f"(requested {quantity})."
            )
        if quantity < 1:
            return "Quantity must be at least 1."

        age_days = (datetime.now(timezone.utc) - order.created_at.replace(tzinfo=timezone.utc)).days
        if age_days > _REFUND_WINDOW_DAYS:
            return (
                f"Order #{_short_id(order.id)} is {age_days} days old and outside the "
                f"{_REFUND_WINDOW_DAYS}-day refund window."
            )

        user = get_user_by_id(db, uid)
        if not user:
            return "User not found."
        try:
            refund_amount = apply_item_refund(db, item, order, user, quantity)
        except Exception as exc:
            db.rollback()
            return f"Refund failed due to an internal error: {exc}"

        name = item.product.name if item.product else product_name
        return (
            f"Refunded {quantity} × {name} from Order #{_short_id(order.id)}. "
            f"${refund_amount:.2f} returned to your balance. "
            f"New balance: ${user.balance:.2f}."
        )

    @tool
    def add_to_cart(product_name: str, quantity: int = 1) -> str:
        """Add a product to the user's cart. Takes a product name and optional quantity (default 1).
        Use this when the user asks to add something to their cart or says 'I want to buy X'."""
        product = db.query(Product).filter(Product.name.ilike(f"%{product_name}%")).first()
        if not product:
            return f"Could not find a product matching '{product_name}'."
        if quantity < 1:
            return "Quantity must be at least 1."
        if product.stock_quantity < quantity:
            return f"Only {product.stock_quantity} {product.name}(s) in stock."
        cart_actions.append(
            {
                "action": "add",
                "product_id": str(product.id),
                "product_name": product.name,
                "quantity": quantity,
                "price": product.price,
            }
        )
        return (
            f"Added {quantity} × {product.name} (${product.price:.2f} each) to your cart. "
            f"Cart total for this item: ${product.price * quantity:.2f}."
        )

    @tool
    def remove_from_cart(product_name: str) -> str:
        """Remove a product from the user's cart. Takes a product name.
        Use this when the user asks to remove something from their cart."""
        product = db.query(Product).filter(Product.name.ilike(f"%{product_name}%")).first()
        if not product:
            return f"Could not find a product matching '{product_name}'."
        cart_actions.append(
            {
                "action": "remove",
                "product_id": str(product.id),
                "product_name": product.name,
                "quantity": 0,
                "price": product.price,
            }
        )
        return f"Removed {product.name} from your cart."

    return [
        search_products,
        compare_products,
        get_order_history,
        get_user_balance,
        get_affordable_products,
        process_item_refund,
        add_to_cart,
        remove_from_cart,
    ]
