"""
Custom evaluators for the ecommerce assistant eval suite.

- routing_accuracy: Did the supervisor send to the right specialist?
- tool_accuracy:    Did the specialist call the right tool first?
- factual_accuracy: Does the response contain the facts fixed by the seed data? (deterministic)
- helpfulness:      Does the response address the user's message? (LLM judge, no reference answer)
- state_accuracy:   Did the run leave the DB/cart in the expected state? (deterministic)

Component-level evaluators (one part of the system, not the whole agent):
- supervisor_route_accuracy:               Is the supervisor's route an acceptable one?
- recall_at_k / hit_at_1 / reciprocal_rank: Does product retrieval surface the relevant items?

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
    """Score 1 if agent_name matches the expected specialist, 0 otherwise.

    The expected specialist is `expected_agents` (any of several, for ambiguous queries) or
    `expected_agent`. Returns a None score (skipped by LangSmith) when the run reports no
    agent_name, as v1 does (a single agent, no supervisor, so routing does not apply), or when
    the example labels no expected route.
    """
    agent_used = (run.outputs or {}).get("agent_name")
    outputs = example.outputs or {}
    acceptable = outputs.get("expected_agents") or (
        [outputs["expected_agent"]] if "expected_agent" in outputs else []
    )
    if agent_used is None or not acceptable:
        return {"key": "routing_accuracy", "score": None}
    return {"key": "routing_accuracy", "score": int(agent_used in acceptable)}


def tool_accuracy(run: Run, example: Example) -> dict:
    """Score 1 if the first non-supervisor step used the expected tool.

    An expected_tool of None means no tool call is expected. When the example omits the key
    entirely (several first steps are legitimate), the score is None and LangSmith skips it.
    """
    outputs = example.outputs or {}
    if "expected_tool" not in outputs:
        return {"key": "tool_accuracy", "score": None}
    expected_tool = outputs["expected_tool"]
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


def supervisor_route_accuracy(run: Run, example: Example) -> dict:
    """Score 1 if the supervisor's route is one of the example's acceptable routes.

    Args:
        run: The supervisor run; reads outputs["agent_name"].
        example: The golden example; reads outputs["expected_agents"] (list of route labels).
            More than one label marks a genuinely ambiguous query.
    """
    route = (run.outputs or {}).get("agent_name")
    expected = (example.outputs or {}).get("expected_agents") or []
    return {"key": "supervisor_route_accuracy", "score": int(route in expected)}


def _ranked_products(run: Run) -> list[str]:
    """Product names returned by a retrieval run, best match first."""
    return (run.outputs or {}).get("products") or []


def _relevant_products(example: Example) -> list[str]:
    return (example.outputs or {}).get("relevant_products") or []


def recall_at_k(run: Run, example: Example) -> dict:
    """Fraction of the relevant products present in the retrieved list (k = its length).

    Args:
        run: The retrieval run; reads outputs["products"] (names, best match first, already
            cut to k by the target).
        example: The golden example; reads outputs["relevant_products"] (product names).
    """
    relevant = set(_relevant_products(example))
    if not relevant:
        return {"key": "recall_at_k", "score": None}
    found = relevant & set(_ranked_products(run))
    return {"key": "recall_at_k", "score": len(found) / len(relevant)}


def hit_at_1(run: Run, example: Example) -> dict:
    """Score 1 if the top-ranked product is one of the relevant products."""
    relevant = set(_relevant_products(example))
    if not relevant:
        return {"key": "hit_at_1", "score": None}
    ranked = _ranked_products(run)
    return {"key": "hit_at_1", "score": int(bool(ranked) and ranked[0] in relevant)}


def reciprocal_rank(run: Run, example: Example) -> dict:
    """1 / rank of the first relevant product (0 if none was retrieved).

    Averaged over examples this is the mean reciprocal rank (MRR).
    """
    relevant = set(_relevant_products(example))
    if not relevant:
        return {"key": "reciprocal_rank", "score": None}
    for rank, name in enumerate(_ranked_products(run), start=1):
        if name in relevant:
            return {"key": "reciprocal_rank", "score": 1 / rank}
    return {"key": "reciprocal_rank", "score": 0.0}


# Balances are stored as floats; treat differences below half a cent as equal.
_BALANCE_TOLERANCE = 0.005


def state_accuracy(run: Run, example: Example) -> dict:
    """Score 1 if the run's final state satisfies every key of the example's expected_state.

    Only keys present in expected_state are checked: balance (within half a cent), refunded
    (exact dict of product -> units refunded), cart_actions (exact list) and stock (each listed
    product must match). The comment names the keys that did not match.

    Returns:
        A 0/1 score, or a None score (skipped) when the example has no expected_state.
    """
    expected = (example.outputs or {}).get("expected_state")
    if not expected:
        return {"key": "state_accuracy", "score": None}

    actual = (run.outputs or {}).get("final_state") or {}
    mismatched = []
    for key, want in expected.items():
        got = actual.get(key)
        if key == "balance":
            ok = got is not None and abs(got - want) < _BALANCE_TOLERANCE
        elif key == "stock":
            ok = got is not None and all(got.get(name) == qty for name, qty in want.items())
        else:
            ok = got == want
        if not ok:
            mismatched.append(f"{key}: expected {want}, got {got}")
    return {
        "key": "state_accuracy",
        "score": int(not mismatched),
        "comment": "; ".join(mismatched) or "state matches",
    }


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
