from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI

from app.agent.v2.state import ShoppingState, SupervisorDecision

_SYSTEM = """You are a routing supervisor for an electronics store AI assistant.
Your ONLY job is to classify the customer's intent and route to the correct specialist.

Routes:
- "product"  → searching products, comparing items, finding affordable products, product questions
- "account"  → balance enquiries, order history, refund requests
- "cart"     → adding or removing items from the cart
- "general"  → greetings, store policy, thank-you messages, anything else

Respond with JSON matching the required schema. Be decisive — pick the single best route."""


def make_supervisor_node(llm: ChatOpenAI):
    router_llm = llm.with_structured_output(SupervisorDecision)

    def supervisor(state: ShoppingState) -> dict:
        decision: SupervisorDecision = router_llm.invoke(
            [SystemMessage(content=_SYSTEM)] + state["messages"]
        )  # type: ignore
        return {
            # Route label; graph.py maps this to the destination node ID.
            "agent_name": decision.route,
            # Record routing as the first UI-visible thinking step for this turn.
            "steps": state["steps"]
            + [
                {
                    "tool": "supervisor",
                    "input": state["messages"][-1].content,
                    "output": f"Routed to {decision.route}: {decision.reasoning}",
                }
            ],
        }

    return supervisor
