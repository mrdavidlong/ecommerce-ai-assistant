from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.product import Product
from app.models.user import User


def _seed(db: Session):
    user = User(name="Alice", email="alice@example.com", balance=500.0)
    product = Product(
        name="Laptop",
        description="A laptop",
        image_url="http://example.com/laptop.jpg",
        price=100.0,
        stock_quantity=5,
    )
    db.add_all([user, product])
    db.commit()
    db.refresh(user)
    db.refresh(product)
    return user, product


def test_create_order_success(client: TestClient, db: Session):
    user, product = _seed(db)
    resp = client.post(
        "/orders/",
        json={
            "user_id": str(user.id),
            "items": [{"product_id": str(product.id), "quantity": 2}],
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["user_id"] == str(user.id)
    assert body["total"] == 200.0
    assert len(body["items"]) == 1
    assert body["items"][0]["product_name"] == "Laptop"
    assert body["items"][0]["quantity"] == 2


def test_create_order_deducts_balance(client: TestClient, db: Session):
    user, product = _seed(db)
    client.post(
        "/orders/",
        json={
            "user_id": str(user.id),
            "items": [{"product_id": str(product.id), "quantity": 1}],
        },
    )
    db.refresh(user)
    assert user.balance == 400.0


def test_create_order_deducts_stock(client: TestClient, db: Session):
    user, product = _seed(db)
    client.post(
        "/orders/",
        json={
            "user_id": str(user.id),
            "items": [{"product_id": str(product.id), "quantity": 3}],
        },
    )
    db.refresh(product)
    assert product.stock_quantity == 2


def test_create_order_fails_insufficient_balance(client: TestClient, db: Session):
    user, product = _seed(db)
    resp = client.post(
        "/orders/",
        json={
            "user_id": str(user.id),
            "items": [{"product_id": str(product.id), "quantity": 6}],
        },
    )
    assert resp.status_code == 400
    assert "balance" in resp.json()["detail"].lower()


def test_create_order_fails_insufficient_stock(client: TestClient, db: Session):
    user = User(name="Rich", email="rich@example.com", balance=99999.0)
    product = Product(
        name="Rare",
        description="Rare item",
        image_url="http://example.com/rare.jpg",
        price=1.0,
        stock_quantity=2,
    )
    db.add_all([user, product])
    db.commit()
    db.refresh(user)
    db.refresh(product)
    resp = client.post(
        "/orders/",
        json={
            "user_id": str(user.id),
            "items": [{"product_id": str(product.id), "quantity": 10}],
        },
    )
    assert resp.status_code == 400
    assert "stock" in resp.json()["detail"].lower()


def test_create_order_fails_empty_items(client: TestClient, db: Session):
    user, _ = _seed(db)
    resp = client.post("/orders/", json={"user_id": str(user.id), "items": []})
    assert resp.status_code == 400


def test_create_order_fails_unknown_user(client: TestClient, db: Session):
    _, product = _seed(db)
    resp = client.post(
        "/orders/",
        json={
            "user_id": "00000000-0000-0000-0000-000000000000",
            "items": [{"product_id": str(product.id), "quantity": 1}],
        },
    )
    assert resp.status_code == 404


def test_create_order_fails_unknown_product(client: TestClient, db: Session):
    user, _ = _seed(db)
    resp = client.post(
        "/orders/",
        json={
            "user_id": str(user.id),
            "items": [{"product_id": "00000000-0000-0000-0000-000000000000", "quantity": 1}],
        },
    )
    assert resp.status_code == 404


def test_list_orders_returns_user_orders(client: TestClient, db: Session):
    user, product = _seed(db)
    client.post(
        "/orders/",
        json={
            "user_id": str(user.id),
            "items": [{"product_id": str(product.id), "quantity": 1}],
        },
    )
    resp = client.get(f"/orders/?user_id={user.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["user_id"] == str(user.id)


def test_list_orders_returns_empty_for_new_user(client: TestClient, db: Session):
    user, _ = _seed(db)
    resp = client.get(f"/orders/?user_id={user.id}")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_orders_fails_unknown_user(client: TestClient, db: Session):
    resp = client.get("/orders/?user_id=00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


def _place_order(client: TestClient, user, product) -> str:
    resp = client.post(
        "/orders/",
        json={
            "user_id": str(user.id),
            "items": [{"product_id": str(product.id), "quantity": 1}],
        },
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def test_refund_restores_balance_and_stock(client: TestClient, db: Session):
    user, product = _seed(db)
    initial_balance = user.balance
    order_id = _place_order(client, user, product)
    resp = client.post(f"/orders/{order_id}/refund?user_id={user.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["refunded_amount"] == 100.0
    assert body["new_balance"] == initial_balance  # balance fully restored
    db.refresh(user)
    db.refresh(product)
    assert user.balance == initial_balance
    assert product.stock_quantity == 5  # stock restored


def test_refund_marks_order_refunded(client: TestClient, db: Session):
    user, product = _seed(db)
    order_id = _place_order(client, user, product)
    client.post(f"/orders/{order_id}/refund?user_id={user.id}")
    resp = client.get(f"/orders/?user_id={user.id}")
    assert resp.json()[0]["refunded"] is True


def test_refund_cannot_refund_twice(client: TestClient, db: Session):
    user, product = _seed(db)
    order_id = _place_order(client, user, product)
    client.post(f"/orders/{order_id}/refund?user_id={user.id}")
    resp = client.post(f"/orders/{order_id}/refund?user_id={user.id}")
    assert resp.status_code == 400
    assert "already been refunded" in resp.json()["detail"]


def test_refund_rejects_wrong_user(client: TestClient, db: Session):
    user, product = _seed(db)
    other = User(name="Bob", email="bob@example.com", balance=500.0)
    db.add(other)
    db.commit()
    db.refresh(other)
    order_id = _place_order(client, user, product)
    resp = client.post(f"/orders/{order_id}/refund?user_id={other.id}")
    assert resp.status_code == 403


def test_refund_unknown_order_returns_404(client: TestClient, db: Session):
    user, _ = _seed(db)
    resp = client.post(f"/orders/00000000-0000-0000-0000-000000000000/refund?user_id={user.id}")
    assert resp.status_code == 404
