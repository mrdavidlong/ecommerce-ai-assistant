from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User
from app.routers.chat_v1 import _history


def _seed_user(db: Session) -> User:
    user = User(name="Alice", email="alice@example.com", balance=500.0)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


MOCK_STEPS = [{"tool": "search_products", "input": "webcam", "output": "Found: Webcam $89.99"}]
MOCK_RESPONSE = "I found a Webcam for $89.99."
MOCK_CART: list = []


@pytest.fixture(autouse=True)
def clear_chat_history():
    _history.clear()
    yield
    _history.clear()


def test_chat_returns_response(client: TestClient, db: Session):
    user = _seed_user(db)
    with patch("app.routers.chat_v1.run_agent_v1", return_value=(MOCK_RESPONSE, MOCK_STEPS, MOCK_CART)):
        resp = client.post(
            "/v1/chat/",
            json={"user_id": str(user.id), "message": "find a webcam", "session_id": "s1"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["response"] == MOCK_RESPONSE
    assert len(data["steps"]) == 1
    assert data["steps"][0]["tool"] == "search_products"


def test_chat_includes_steps(client: TestClient, db: Session):
    user = _seed_user(db)
    steps = [
        {"tool": "get_user_balance", "input": "", "output": "Your balance is $500.00."},
    ]
    with patch("app.routers.chat_v1.run_agent_v1", return_value=("You have $500.", steps, [])):
        resp = client.post(
            "/v1/chat/",
            json={"user_id": str(user.id), "message": "what is my balance", "session_id": "s2"},
        )
    data = resp.json()
    assert data["steps"][0]["tool"] == "get_user_balance"
    assert data["steps"][0]["output"] == "Your balance is $500.00."


def test_chat_no_steps_when_agent_answers_directly(client: TestClient, db: Session):
    user = _seed_user(db)
    with patch("app.routers.chat_v1.run_agent_v1", return_value=("Hello! How can I help?", [], [])):
        resp = client.post(
            "/v1/chat/",
            json={"user_id": str(user.id), "message": "hi", "session_id": "s3"},
        )
    assert resp.status_code == 200
    assert resp.json()["steps"] == []


def test_chat_maintains_session_history(client: TestClient, db: Session):
    user = _seed_user(db)
    session_id = "session-memory-test"

    with patch("app.routers.chat_v1.run_agent_v1", return_value=("First response.", [], [])):
        client.post(
            "/v1/chat/",
            json={"user_id": str(user.id), "message": "hello", "session_id": session_id},
        )

    assert session_id in _history
    assert len(_history[session_id]) == 2  # HumanMessage + AIMessage

    captured: list[int] = []

    def capture_history(db, user_id, message, history):
        captured.append(len(history))
        return "Second response.", [], []

    with patch("app.routers.chat_v1.run_agent_v1", side_effect=capture_history):
        client.post(
            "/v1/chat/",
            json={"user_id": str(user.id), "message": "follow up", "session_id": session_id},
        )

    assert captured == [2]


def test_chat_different_sessions_are_isolated(client: TestClient, db: Session):
    user = _seed_user(db)
    with patch("app.routers.chat_v1.run_agent_v1", return_value=("Response A.", [], [])):
        client.post(
            "/v1/chat/",
            json={"user_id": str(user.id), "message": "msg A", "session_id": "sess-A"},
        )
    with patch("app.routers.chat_v1.run_agent_v1", return_value=("Response B.", [], [])):
        client.post(
            "/v1/chat/",
            json={"user_id": str(user.id), "message": "msg B", "session_id": "sess-B"},
        )
    assert "sess-A" in _history
    assert "sess-B" in _history
    assert _history["sess-A"] != _history["sess-B"]


def test_chat_agent_error_returns_500(client: TestClient, db: Session):
    user = _seed_user(db)
    with patch("app.routers.chat_v1.run_agent_v1", side_effect=RuntimeError("LLM unavailable")):
        resp = client.post(
            "/v1/chat/",
            json={"user_id": str(user.id), "message": "anything", "session_id": "s-err"},
        )
    assert resp.status_code == 500
    assert "LLM unavailable" in resp.json()["detail"]


def test_chat_returns_cart_actions(client: TestClient, db: Session):
    user = _seed_user(db)
    cart = [
        {
            "action": "add",
            "product_id": "abc-123",
            "product_name": "Webcam",
            "quantity": 2,
            "price": 89.99,
        }
    ]
    mock_return = ("Added 2 webcams to your cart.", [], cart)
    with patch("app.routers.chat_v1.run_agent_v1", return_value=mock_return):
        resp = client.post(
            "/v1/chat/",
            json={"user_id": str(user.id), "message": "add 2 webcams", "session_id": "s-cart"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["cart_actions"]) == 1
    assert data["cart_actions"][0]["product_name"] == "Webcam"
    assert data["cart_actions"][0]["quantity"] == 2


def test_chat_returns_remove_cart_action(client: TestClient, db: Session):
    user = _seed_user(db)
    cart = [
        {
            "action": "remove",
            "product_id": "abc-123",
            "product_name": "Webcam",
            "quantity": 0,
            "price": 89.99,
        }
    ]
    mock_return = ("Removed Webcam from your cart.", [], cart)
    with patch("app.routers.chat_v1.run_agent_v1", return_value=mock_return):
        resp = client.post(
            "/v1/chat/",
            json={
                "user_id": str(user.id),
                "message": "remove the webcam",
                "session_id": "s-remove",
            },
        )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["cart_actions"]) == 1
    assert data["cart_actions"][0]["action"] == "remove"
    assert data["cart_actions"][0]["product_name"] == "Webcam"


def test_chat_empty_cart_actions_by_default(client: TestClient, db: Session):
    user = _seed_user(db)
    with patch("app.routers.chat_v1.run_agent_v1", return_value=("Hello!", [], [])):
        resp = client.post(
            "/v1/chat/",
            json={"user_id": str(user.id), "message": "hi", "session_id": "s-no-cart"},
        )
    assert resp.json()["cart_actions"] == []


def test_chat_response_includes_agent_name(client: TestClient, db: Session):
    user = _seed_user(db)
    with patch("app.routers.chat_v1.run_agent_v1", return_value=("Hello!", [], [])):
        resp = client.post(
            "/v1/chat/",
            json={"user_id": str(user.id), "message": "hi", "session_id": "s-agent-name"},
        )
    assert resp.status_code == 200
    assert "agent_name" in resp.json()
