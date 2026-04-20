from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.product import Product


def _seed_products(db: Session) -> list[Product]:
    products = [
        Product(
            name="Laptop",
            description="A laptop",
            image_url="http://example.com/laptop.jpg",
            price=999.99,
            stock_quantity=10,
        ),
        Product(
            name="Mouse",
            description="A mouse",
            image_url="http://example.com/mouse.jpg",
            price=29.99,
            stock_quantity=50,
        ),
    ]
    db.add_all(products)
    db.commit()
    for p in products:
        db.refresh(p)
    return products


def test_list_products_returns_all(client: TestClient, db: Session):
    _seed_products(db)
    resp = client.get("/products/")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    assert all("id" in p and "name" in p and "price" in p for p in body)


def test_get_product_by_id_returns_correct_product(client: TestClient, db: Session):
    products = _seed_products(db)
    target = products[0]
    resp = client.get(f"/products/{target.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == str(target.id)
    assert body["name"] == target.name
    assert body["price"] == target.price


def test_get_product_by_id_returns_404_for_unknown(client: TestClient, db: Session):
    resp = client.get("/products/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404
