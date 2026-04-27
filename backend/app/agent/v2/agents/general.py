from langchain_core.messages import AIMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.agent.v2.state import ShoppingState

_SYSTEM = (
    "You are a friendly assistant for an electronics store. "
    "Answer greetings, general questions, and store policy questions. "
    "Keep responses brief and warm. You do not have access to product or account tools."
)


def make_general_node(llm: ChatOpenAI):
    def general_node(state: ShoppingState) -> dict:
        response = llm.invoke([SystemMessage(content=_SYSTEM)] + state["messages"])
        return {
            "messages": [response],
            "steps": state.get("steps", []),
        }

    return general_node
