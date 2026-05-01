from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agent.v2.agent import run_agent_v2
from app.db.session import get_db
from app.schemas.chat import AgentStep, CartAction, ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["chat-v2"])


@router.post("/", response_model=ChatResponse)
def chat(payload: ChatRequest, db: Session = Depends(get_db)):
    try:
        response_text, raw_steps, raw_cart, agent_name = run_agent_v2(
            db, payload.user_id, payload.message, payload.session_id
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {e}")

    steps = [
        AgentStep(
            tool=s["tool"],
            input=s["input"],
            output=s["output"],
            # Older/legacy steps may not include an agent tag.
            agent=s.get("agent", "unknown"),
        )
        for s in raw_steps
    ]
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

    return ChatResponse(
        response=response_text,
        steps=steps,
        cart_actions=cart_actions,
        agent_name=agent_name,
    )
