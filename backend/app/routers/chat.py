from fastapi import APIRouter, Depends
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from sqlalchemy.orm import Session

from app.agent.agent import run_agent
from app.db.session import get_db
from app.routers.chat_errors import agent_error_response
from app.schemas.chat import AgentStep, CartAction, ChatRequest, ChatResponse

# Legacy unversioned chat route kept for compatibility; frontend uses /v2/chat/.
router = APIRouter(prefix="/chat", tags=["chat"])

# In-memory conversation history keyed by session_id
_history: dict[str, list[BaseMessage]] = {}


@router.post("/", response_model=ChatResponse)
def chat(payload: ChatRequest, db: Session = Depends(get_db)):
    history = _history.setdefault(payload.session_id, [])

    try:
        response_text, raw_steps, raw_cart = run_agent(
            db, payload.user_id, payload.message, history
        )
    except Exception as e:
        raise agent_error_response(e)

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
