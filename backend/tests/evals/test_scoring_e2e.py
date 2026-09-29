"""
Scoring logic of the end-to-end evaluators, tested with fake LangSmith runs and examples.

Group 1 of 3 for the eval suite (see README "How the evals are tested"):
    scoring (this file and test_scoring_component.py) -> do the evaluators score correctly?
    golden sets (test_golden_sets.py)                 -> are the labels themselves correct?
    infrastructure (test_infra_*.py)                  -> do the DB, sync and report helpers work?

The end-to-end evaluators fall into three kinds, in the order below:
    process - did the agent route and call tools correctly?   routing_accuracy, tool_accuracy
    answer  - is the response right and useful?               factual_accuracy, helpfulness
    effect  - did the database and cart end up right?         state_accuracy

No real LLM or LangSmith call is made anywhere in this file.
"""

from types import SimpleNamespace

import pytest

from evals import evaluators
from evals.evaluators import (
    HelpfulnessVerdict,
    factual_accuracy,
    helpfulness,
    routing_accuracy,
    state_accuracy,
    tool_accuracy,
)


def _run(**outputs) -> SimpleNamespace:
    """Fake LangSmith Run whose outputs are the given keyword arguments."""
    return SimpleNamespace(outputs=outputs)


_RUN_WITHOUT_OUTPUTS = SimpleNamespace(outputs=None)  # a run whose target crashed


def _example(message: str = "hi", **outputs) -> SimpleNamespace:
    """Fake LangSmith Example: the message is its input, the keyword arguments its labels."""
    return SimpleNamespace(inputs={"message": message}, outputs=outputs)


# ---------------------------------------------------------------------------------------------
# PROCESS: routing_accuracy
# Did the supervisor send the query to an acceptable specialist? v1 has no supervisor.
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("agent_name", "expected_agent", "score"),
    [
        ("product", "product", 1),  # routed correctly
        ("cart", "product", 0),  # routed to the wrong specialist
        ("unknown", "product", 0),  # v2's failure fallback is a real miss, not "n/a"
        (None, "product", None),  # v1 has no supervisor: skipped, not scored 0
    ],
)
def test_routing_accuracy(agent_name, expected_agent, score):
    """A single expected_agent is compared exactly; a missing agent_name is skipped."""
    result = routing_accuracy(_run(agent_name=agent_name), _example(expected_agent=expected_agent))
    assert result == {"key": "routing_accuracy", "score": score}


def test_routing_accuracy_skips_when_run_has_no_outputs():
    """A crashed target gives no agent_name, which is skipped rather than counted as a miss."""
    assert (
        routing_accuracy(_RUN_WITHOUT_OUTPUTS, _example(expected_agent="product"))["score"] is None
    )


@pytest.mark.parametrize(
    ("labels", "route", "score"),
    [
        ({"expected_agents": ["product", "cart"]}, "cart", 1),  # ambiguous query: either accepted
        ({"expected_agents": ["product", "cart"]}, "account", 0),  # outside the acceptable set
        ({"expected_agents": ["product"], "expected_agent": "cart"}, "product", 1),  # list wins
        ({}, "product", None),  # no route labelled: nothing to check, skipped
    ],
)
def test_routing_accuracy_with_optional_labels(labels, route, score):
    """expected_agents (several acceptable routes) takes precedence over expected_agent."""
    assert routing_accuracy(_run(agent_name=route), _example(**labels))["score"] == score


# ---------------------------------------------------------------------------------------------
# PROCESS: tool_accuracy
# Did the specialist call the expected tool first? No tool is a valid expectation (chitchat).
# ---------------------------------------------------------------------------------------------


def _steps(*tools: str) -> list[dict]:
    """Agent trace: the supervisor's routing step followed by the given tool calls."""
    return [{"tool": "supervisor"}, *({"tool": t} for t in tools)]


@pytest.mark.parametrize(
    ("labels", "steps", "score"),
    [
        ({"expected_tool": "search_products"}, _steps("search_products", "add_to_cart"), 1),
        ({"expected_tool": "search_products"}, _steps("add_to_cart"), 0),  # wrong first tool
        ({"expected_tool": "search_products"}, _steps(), 0),  # no specialist tool at all
        ({"expected_tool": None}, _steps(), 1),  # chitchat, correctly no tool
        ({"expected_tool": None}, _steps("get_user_balance"), 0),  # unexpected tool call
        ({}, _steps("anything"), None),  # key omitted: several first steps legitimate, skipped
    ],
)
def test_tool_accuracy(labels, steps, score):
    """Only the first non-supervisor step counts; expected_tool=None means no tool call."""
    assert tool_accuracy(_run(steps=steps), _example(**labels))["score"] == score


# ---------------------------------------------------------------------------------------------
# ANSWER: factual_accuracy
# Deterministic check that the response contains the facts fixed by the seed data.
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("response", "facts", "expected"),
    [
        ("The Webcam costs $89.99", ["Webcam", "89.99"], 1.0),  # all facts present
        ("The Webcam is great", ["Webcam", "89.99"], 0.5),  # partial
        ("Nothing relevant", ["Webcam", "89.99"], 0.0),  # none present
        ("the WEBCAM costs $89.99", ["Webcam", "89.99"], 1.0),  # case-insensitive
        ("Your balance is $1,000.00", ["1000"], 1.0),  # thousands separator stripped
        ("Only 29.99 here", ["29.99", "24.99"], 0.5),  # single element missing
        ("$29.99", ["29.99", "29.99"], 1.0),  # duplicate facts, present
        ("$24.99", ["29.99", "29.99"], 0.0),  # duplicate facts, missing
        ("", ["Webcam"], 0.0),  # empty response
        (None, ["Webcam"], 0.0),  # None response
    ],
)
def test_factual_accuracy_scores_fraction_of_facts_found(response, facts, expected):
    """Score is the fraction of expected_facts found, ignoring case and thousands separators."""
    result = factual_accuracy(_run(response=response), _example(expected_facts=facts))
    assert result == {"key": "factual_accuracy", "score": expected}


def test_factual_accuracy_missing_run_outputs_scores_zero():
    """A crashed target has no response, so every fact is missing."""
    result = factual_accuracy(_RUN_WITHOUT_OUTPUTS, _example(expected_facts=["Webcam"]))
    assert result["score"] == 0.0


@pytest.mark.parametrize(
    "example",
    [
        _example(),  # example defines no facts
        _example(expected_facts=[]),  # empty fact list must not divide by zero
        _example(expected_facts=None),
    ],
)
def test_factual_accuracy_skips_examples_without_facts(example):
    """No facts to check means the example is skipped, not scored 0 or 1."""
    result = factual_accuracy(_run(response="anything"), example)
    assert result == {"key": "factual_accuracy", "score": None}


# ---------------------------------------------------------------------------------------------
# ANSWER: helpfulness (LLM judge, replaced here by a fake so no model is called)
# ---------------------------------------------------------------------------------------------


class _FakeJudge:
    """Stands in for the structured-output judge LLM; records the prompt it receives."""

    def __init__(self, verdict: HelpfulnessVerdict | Exception):
        self.verdict = verdict
        self.prompts: list[str] = []

    def invoke(self, prompt: str) -> HelpfulnessVerdict:
        self.prompts.append(prompt)
        if isinstance(self.verdict, Exception):
            raise self.verdict
        return self.verdict


def _patch_judge(monkeypatch, verdict) -> _FakeJudge:
    judge = _FakeJudge(verdict)
    monkeypatch.setattr(evaluators, "_get_judge", lambda: judge)
    return judge


@pytest.mark.parametrize(
    ("rating", "expected"),
    [(5, 1.0), (4, 0.75), (3, 0.5), (2, 0.25), (1, 0.0)],
)
def test_helpfulness_normalises_rating_to_unit_interval(monkeypatch, rating, expected):
    """The judge's 1-5 rating maps linearly to 0-1 and its reasoning becomes the comment."""
    _patch_judge(monkeypatch, HelpfulnessVerdict(reasoning="because", score=rating))
    result = helpfulness(_run(response="A webcam costs $89.99"), _example("find a webcam"))
    assert result == {"key": "helpfulness", "score": expected, "comment": "because"}


def test_helpfulness_prompt_contains_message_and_response(monkeypatch):
    """Braces in user text must reach the judge verbatim (no str.format surprises)."""
    judge = _patch_judge(monkeypatch, HelpfulnessVerdict(reasoning="ok", score=5))
    helpfulness(_run(response="resp {with braces}"), _example("msg {x}"))
    assert "msg {x}" in judge.prompts[0]
    assert "resp {with braces}" in judge.prompts[0]


@pytest.mark.parametrize("bad_rating", [0, 6, -1])
def test_helpfulness_rejects_out_of_range_rating(monkeypatch, bad_rating):
    """An out-of-scale rating fails loudly instead of skewing the average."""
    _patch_judge(monkeypatch, HelpfulnessVerdict(reasoning="x", score=bad_rating))
    with pytest.raises(ValueError, match="out-of-range"):
        helpfulness(_run(response="r"), _example())


def test_helpfulness_propagates_judge_errors(monkeypatch):
    """A judge outage is an error, never a silent zero."""
    _patch_judge(monkeypatch, RuntimeError("judge down"))
    with pytest.raises(RuntimeError, match="judge down"):
        helpfulness(_run(response="r"), _example())


# ---------------------------------------------------------------------------------------------
# EFFECT: state_accuracy
# Did the run leave the database and cart in the expected state? Catches an agent that says it
# refunded but did not, or acts when it should refuse.
# ---------------------------------------------------------------------------------------------

_FINAL_STATE = {
    "balance": 1089.99,
    "refunded": {"Webcam": 1},
    "stock": {"Webcam": 15, "Laptop": 10},
    "cart_actions": [],
}


@pytest.mark.parametrize(
    ("expected", "score"),
    [
        ({"balance": 1089.99}, 1),  # single key matches
        ({"balance": 1089.994}, 1),  # within half a cent
        ({"balance": 1000.0}, 0),  # wrong balance
        ({"refunded": {"Webcam": 1}}, 1),
        ({"refunded": {}}, 0),  # a refund happened but none was expected
        ({"refunded": {"Webcam": 2}}, 0),  # wrong quantity
        ({"cart_actions": []}, 1),  # nothing added, as expected
        ({"cart_actions": [{"action": "add", "product_name": "Webcam", "quantity": 1}]}, 0),
        ({"stock": {"Webcam": 15}}, 1),  # stock is a subset match
        ({"stock": {"Webcam": 14}}, 0),
        ({"stock": {"Ghost": 1}}, 0),  # unknown product never matches
        ({"balance": 1089.99, "refunded": {"Webcam": 1}}, 1),  # all keys must match
        ({"balance": 1089.99, "refunded": {}}, 0),  # one wrong key fails the example
    ],
)
def test_state_accuracy(expected, score):
    """Every key in expected_state must match the run's final_state."""
    result = state_accuracy(_run(final_state=_FINAL_STATE), _example(expected_state=expected))
    assert result["score"] == score


def test_state_accuracy_comment_names_the_mismatch():
    """The comment says which key failed, so a miss can be diagnosed from LangSmith alone."""
    result = state_accuracy(
        _run(final_state=_FINAL_STATE), _example(expected_state={"balance": 5.0})
    )
    assert "balance" in result["comment"]


@pytest.mark.parametrize(
    "example", [_example(), _example(expected_state=None), _example(expected_state={})]
)
def test_state_accuracy_skips_examples_without_expected_state(example):
    """Examples that assert no state (e.g. plain searches) are skipped."""
    result = state_accuracy(_run(final_state=_FINAL_STATE), example)
    assert result == {"key": "state_accuracy", "score": None}


@pytest.mark.parametrize("run", [_RUN_WITHOUT_OUTPUTS, _run(), _run(final_state=None)])
def test_state_accuracy_missing_final_state_fails(run):
    """If a state was expected but the run produced none, that is a failure."""
    assert state_accuracy(run, _example(expected_state={"balance": 1.0}))["score"] == 0
