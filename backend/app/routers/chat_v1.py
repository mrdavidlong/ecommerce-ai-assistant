from fastapi import APIRouter, Depends, HTTPException
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from sqlalchemy.orm import Session

from app.agent.v1.agent import run_agent_v1
from app.db.session import get_db
from app.schemas.chat import AgentStep, CartAction, ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["chat-v1"])

# In-memory conversation history keyed by session_id
_history: dict[str, list[BaseMessage]] = {}


@router.post("/", response_model=ChatResponse)
def chat(payload: ChatRequest, db: Session = Depends(get_db)):
    history = _history.setdefault(payload.session_id, [])

    try:
        response_text, raw_steps, raw_cart = run_agent_v1(
            db, payload.user_id, payload.message, history
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {e}")

    steps = [AgentStep(tool=s["tool"], input=s["input"], output=s["output"]) for s in raw_steps]
    cart_actions = [
        CartAction(
            action=a["action"],
            product_id=a["product_id"],
            product_name=a["product_name"],
            quantity=a["quantity"],
            price=a["price"],
        )
        for a in raw_cart
    ]

    history.append(HumanMessage(content=payload.message))
    history.append(AIMessage(content=response_text))
    _history[payload.session_id] = history[-20:]

    return ChatResponse(response=response_text, steps=steps, cart_actions=cart_actions)
