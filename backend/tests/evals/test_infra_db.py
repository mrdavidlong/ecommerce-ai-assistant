"""Tests for the eval database helpers (reset, order seeding, state snapshot, index build).

Group 3 of 3 for the eval suite (see README "How the evals are tested"):
infrastructure. Every eval example starts from a reset,
order-seeded database; if this breaks, state checks are meaningless.
"""

from datetime import datetime, timezone

import pytest

from app.db.seed import _PRODUCTS
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.product import Product
from app.models.user import User
from app.services.refund_service import apply_item_refund
from evals.eval_db import (
    _SEED_BALANCE,
    OLD_ORDER_ID,
    OTHER_USER_ORDER_ID,
    RECENT_ORDER_ID,
    embed_eval_products,
    get_eval_users,
    reset_eval_db,
    snapshot_state,
)

_REFUND_WINDOW_DAYS = 30


def _seed_users_and_products(db, emails=("alice@x.com", "bob@x.com", "carol@x.com")) -> None:
    """Insert users and fresh copies of the seed products (never the module-level instances)."""
    db.add_all([User(name=e.split("@")[0], email=e, balance=5.0) for e in emails])
    db.add_all(
        Product(
            name=p.name,
            description=p.description,
            image_url=p.image_url,
            price=p.price,
            stock_quantity=1,
        )
        for p in _PRODUCTS
    )
    db.commit()


@pytest.fixture
def seeded(db):
    _seed_users_and_products(db)
    reset_eval_db(db)
    return db


def _order(db, order_id) -> Order:
    return db.get(Order, order_id)


def test_eval_users_are_ordered_by_email(db):
    """Users come back sorted by email, so index 0 is always the same eval user."""
    _seed_users_and_products(db, emails=("zed@x.com", "amy@x.com", "kim@x.com"))
    assert [u.email for u in get_eval_users(db)] == ["amy@x.com", "kim@x.com", "zed@x.com"]


def test_reset_seeds_the_three_orders_for_the_right_users(seeded):
    """The eval user owns the recent and old orders; another user owns the cross-user one."""
    alice, bob, _ = get_eval_users(seeded)
    assert _order(seeded, RECENT_ORDER_ID).user_id == alice.id
    assert _order(seeded, OLD_ORDER_ID).user_id == alice.id
    assert _order(seeded, OTHER_USER_ORDER_ID).user_id == bob.id
    assert seeded.query(Order).count() == 3


def test_recent_order_contents_and_total(seeded):
    """The recent order holds 2 mice and a webcam, with a total derived from live prices."""
    order = _order(seeded, RECENT_ORDER_ID)
    lines = {i.product.name: i.quantity for i in order.items}
    assert lines == {"Wireless Mouse": 2, "Webcam": 1}
    assert order.total == pytest.approx(2 * 29.99 + 89.99)


def _age_days(order: Order) -> int:
    created = order.created_at.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - created).days


def test_old_order_is_outside_the_refund_window_and_recent_is_inside(seeded):
    """Refund-window cases rely on the old order being past 30 days and the recent one inside."""
    assert _age_days(_order(seeded, OLD_ORDER_ID)) > _REFUND_WINDOW_DAYS
    assert _age_days(_order(seeded, RECENT_ORDER_ID)) <= _REFUND_WINDOW_DAYS


def test_reset_is_idempotent(seeded):
    """Resetting twice leaves exactly the seeded rows, with no leftover orders or items."""
    reset_eval_db(seeded)
    assert seeded.query(Order).count() == 3
    assert seeded.query(OrderItem).count() == 4  # 2 + 1 + 1 lines, no leftovers


def test_reset_restores_balance_and_stock_and_drops_extra_orders(seeded):
    """Balance, stock and extra orders left by a previous example are all undone."""
    alice = get_eval_users(seeded)[0]
    alice.balance = 1.0
    seeded.query(Product).filter(Product.name == "Laptop").update({"stock_quantity": 0})
    seeded.add(Order(user_id=alice.id, total=1.0))
    seeded.commit()

    reset_eval_db(seeded)

    assert seeded.query(Order).count() == 3
    assert {u.balance for u in get_eval_users(seeded)} == {_SEED_BALANCE}
    laptop = seeded.query(Product).filter(Product.name == "Laptop").one()
    assert laptop.stock_quantity == next(p.stock_quantity for p in _PRODUCTS if p.name == "Laptop")


def test_reset_fails_loudly_with_fewer_than_two_users(db):
    """Without a second user the cross-user order cannot be seeded: fail and roll back."""
    _seed_users_and_products(db, emails=("only@x.com",))
    with pytest.raises(RuntimeError, match="two users"):
        reset_eval_db(db)
    assert db.query(Order).count() == 0  # rolled back, nothing half-seeded


def test_reset_fails_loudly_when_a_seed_product_is_missing(db):
    """A missing seed product aborts the reset instead of seeding a partial order."""
    _seed_users_and_products(db)
    db.query(Product).filter(Product.name == "Webcam").delete()
    db.commit()
    with pytest.raises(RuntimeError, match="Webcam"):
        reset_eval_db(db)
    assert db.query(Order).count() == 0


def test_reset_rolls_back_and_reraises_on_database_errors(db, monkeypatch):
    """Regression: the old reset printed and swallowed DB errors, so evals ran on dirty state."""
    _seed_users_and_products(db)

    def boom():
        raise RuntimeError("disk full")

    monkeypatch.setattr(db, "commit", boom)
    with pytest.raises(RuntimeError, match="disk full"):
        reset_eval_db(db)


def test_snapshot_of_untouched_state(seeded):
    """A fresh snapshot shows the seed balance and stock, no refunds and no cart actions."""
    alice = get_eval_users(seeded)[0]
    snap = snapshot_state(seeded, str(alice.id), [])
    assert snap["balance"] == _SEED_BALANCE
    assert snap["refunded"] == {}
    assert snap["cart_actions"] == []
    assert snap["stock"]["Webcam"] == next(
        p.stock_quantity for p in _PRODUCTS if p.name == "Webcam"
    )


def test_snapshot_after_partial_refund_and_cart_actions(seeded):
    """Refunded units, balance and cart actions show up; extra cart keys are dropped."""
    alice = get_eval_users(seeded)[0]
    order = _order(seeded, RECENT_ORDER_ID)
    mouse = next(i for i in order.items if i.product.name == "Wireless Mouse")
    apply_item_refund(seeded, mouse, order, alice, 1)

    cart = [
        {"action": "add", "product_name": "Webcam", "quantity": 1, "product_id": "x", "price": 1}
    ]
    snap = snapshot_state(seeded, str(alice.id), cart)

    assert snap["balance"] == pytest.approx(_SEED_BALANCE + 29.99)
    assert snap["refunded"] == {"Wireless Mouse": 1}
    assert snap["cart_actions"] == [{"action": "add", "product_name": "Webcam", "quantity": 1}]


def test_snapshot_ignores_other_users_refunds(seeded):
    """Only the eval user's refunds are reported, so another user's activity cannot mask a bug."""
    alice, bob, _ = get_eval_users(seeded)
    order = _order(seeded, OTHER_USER_ORDER_ID)
    apply_item_refund(seeded, order.items[0], order, bob, 1)
    assert snapshot_state(seeded, str(alice.id), [])["refunded"] == {}


def test_embed_eval_products_embeds_every_product(db, monkeypatch):
    """Regression: the eval process must build the RAG index itself, or all searches are empty."""
    from app.agent.shared import rag

    db.add_all(
        [
            Product(name="A", description="d", image_url="/a.jpg", price=1.0, stock_quantity=1),
            Product(name="B", description="d", image_url="/b.jpg", price=2.0, stock_quantity=1),
        ]
    )
    db.commit()
    embedded: list = []
    monkeypatch.setattr(rag, "embed_products", embedded.extend)

    assert embed_eval_products(db) == 2
    assert {p.name for p in embedded} == {"A", "B"}


def test_embed_eval_products_fails_loudly_when_no_products(db, monkeypatch):
    """With no products in the database there is nothing to index: fail, do not embed nothing."""
    from app.agent.shared import rag

    monkeypatch.setattr(rag, "embed_products", lambda products: pytest.fail("should not embed"))
    with pytest.raises(RuntimeError, match="No products"):
        embed_eval_products(db)
