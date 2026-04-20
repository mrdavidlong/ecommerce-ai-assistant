from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User


def _seed_test_users(db: Session) -> list[User]:
    users = [
        User(name="Test User 1", email="test1@example.com"),
        User(name="Test User 2", email="test2@example.com"),
        User(name="Test User 3", email="test3@example.com"),
    ]
    db.add_all(users)
    db.commit()
    for u in users:
        db.refresh(u)
    return users


def test_get_users_returns_3_after_seeding(client: TestClient, db: Session):
    _seed_test_users(db)
    resp = client.get("/users/")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 3
    assert all("id" in u and "name" in u and "email" in u for u in body)


def test_get_user_by_id_returns_correct_user(client: TestClient, db: Session):
    users = _seed_test_users(db)
    target = users[0]
    resp = client.get(f"/users/{target.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == str(target.id)
    assert body["name"] == target.name
    assert body["email"] == target.email
