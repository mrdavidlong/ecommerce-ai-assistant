"""
Custom evaluators for the ecommerce assistant eval suite.

- routing_accuracy: Did the supervisor send to the right specialist?
- tool_accuracy:    Did the specialist call the right tool first?
- factual_accuracy: Does the response contain the facts fixed by the seed data? (deterministic)
- helpfulness:      Does the response address the user's message? (LLM judge, no reference answer)

The judge model is set with JUDGE_MODEL (falls back to LLM_MODEL). Keep it pinned across runs so
v1 vs v2 score differences come from the agents, not the judge.
"""

import os
from functools import lru_cache

from langchain_openai import ChatOpenAI
from langsmith.schemas import Example, Run
from pydantic import BaseModel, Field

JUDGE_MODEL = os.getenv("JUDGE_MODEL", os.getenv("LLM_MODEL", "gpt-4o"))

# Bounds of the judge's rating scale; the score is normalised to 0-1 from these.
_MIN_RATING = 1
_MAX_RATING = 5

_HELPFULNESS_PROMPT = f"""You are grading an ecommerce shopping assistant.
Rate how helpful the assistant's response is to the user's message on a scale of \
{_MIN_RATING} to {_MAX_RATING}:
{_MAX_RATING} = directly and completely addresses the request
3 = partially addresses it, or is vague/incomplete
{_MIN_RATING} = ignores, misunderstands, or fails to address the request (including errors)
Judge only how well the response serves the request, not its style or length.

User message: {{message}}

Assistant response: {{response}}"""


class HelpfulnessVerdict(BaseModel):
    """Structured output of the helpfulness LLM judge."""

    reasoning: str = Field(description="Brief justification, written before scoring")
    score: int = Field(description=f"Integer rating from {_MIN_RATING} to {_MAX_RATING}")


@lru_cache(maxsize=1)
def _get_judge():
    """Return the cached judge LLM. Built lazily so importing this module needs no API key."""
    return ChatOpenAI(model=JUDGE_MODEL, temperature=0).with_structured_output(HelpfulnessVerdict)


def routing_accuracy(run: Run, example: Example) -> dict:
    """Score 1 if agent_name matches expected_agent, 0 otherwise."""
    agent_used = (run.outputs or {}).get("agent_name", "")
    expected = (example.outputs or {}).get("expected_agent", "")
    return {"key": "routing_accuracy", "score": int(agent_used == expected)}


def tool_accuracy(run: Run, example: Example) -> dict:
    """Score 1 if the first non-supervisor step used the expected tool."""
    expected_tool = (example.outputs or {}).get("expected_tool")
    steps = (run.outputs or {}).get("steps", [])

    if expected_tool is None:
        # General queries — no tool call expected; penalise if a specialist tool was called
        specialist_steps = [s for s in steps if s.get("tool") != "supervisor"]
        return {"key": "tool_accuracy", "score": int(len(specialist_steps) == 0)}

    specialist_steps = [s for s in steps if s.get("tool") != "supervisor"]
    if not specialist_steps:
        return {"key": "tool_accuracy", "score": 0}

    first_tool = specialist_steps[0].get("tool", "")
    return {"key": "tool_accuracy", "score": int(first_tool == expected_tool)}


def factual_accuracy(run: Run, example: Example) -> dict:
    """Score the fraction of expected_facts found in the response.

    Matching is a case-insensitive substring test. Thousands separators are stripped from the
    response first so "$1,000.00" satisfies the fact "1000".

    Args:
        run: The agent run; reads outputs["response"].
        example: The golden example; reads outputs["expected_facts"] (list of substrings).

    Returns:
        A score between 0 and 1, or a None score (skipped by LangSmith) when the example
        defines no facts to check.
    """
    expected_facts = (example.outputs or {}).get("expected_facts") or []
    if not expected_facts:
        return {"key": "factual_accuracy", "score": None}

    response = ((run.outputs or {}).get("response") or "").replace(",", "").lower()
    found = sum(fact.lower() in response for fact in expected_facts)
    return {"key": "factual_accuracy", "score": found / len(expected_facts)}


def helpfulness(run: Run, example: Example) -> dict:
    """LLM-judge how well the response addresses the user's message (reference-free).

    Args:
        run: The agent run; reads outputs["response"].
        example: The golden example; reads inputs["message"].

    Returns:
        The judge's 1-5 rating normalised to 0-1, with its reasoning as the comment.

    Raises:
        TypeError: If the judge output cannot be parsed into a HelpfulnessVerdict.
        ValueError: If the judge returns a rating outside the 1-5 scale.
    """
    message = (example.inputs or {}).get("message", "")
    response = (run.outputs or {}).get("response", "")

    verdict = _get_judge().invoke(_HELPFULNESS_PROMPT.format(message=message, response=response))
    if not isinstance(verdict, HelpfulnessVerdict):
        raise TypeError(f"Judge returned {type(verdict).__name__}, expected HelpfulnessVerdict")
    if not _MIN_RATING <= verdict.score <= _MAX_RATING:
        raise ValueError(f"Judge returned out-of-range helpfulness rating: {verdict.score}")

    normalised = (verdict.score - _MIN_RATING) / (_MAX_RATING - _MIN_RATING)
    return {"key": "helpfulness", "score": normalised, "comment": verdict.reasoning}
