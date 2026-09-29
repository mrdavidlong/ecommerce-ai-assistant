"""Tests for the eval evaluators and golden dataset. No real LLM or LangSmith calls are made."""

import re
from types import SimpleNamespace

import pytest

from app.db.seed import _PRODUCTS
from evals import evaluators
from evals.dataset import EXAMPLES, reference_outputs
from evals.evaluators import HelpfulnessVerdict, factual_accuracy, helpfulness
from evals.run_eval import _SEED_BALANCE


def _run(response: str | None = "", outputs_missing: bool = False) -> SimpleNamespace:
    """Fake LangSmith Run carrying only what the evaluators read."""
    return SimpleNamespace(outputs=None if outputs_missing else {"response": response})


def _example(facts=None, message: str = "hi", with_facts_key: bool = True) -> SimpleNamespace:
    """Fake LangSmith Example with optional expected_facts reference output."""
    outputs = {"expected_facts": facts} if with_facts_key else {}
    return SimpleNamespace(inputs={"message": message}, outputs=outputs)


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
    result = factual_accuracy(_run(response), _example(facts))
    assert result == {"key": "factual_accuracy", "score": expected}


def test_factual_accuracy_missing_run_outputs_scores_zero():
    result = factual_accuracy(_run(outputs_missing=True), _example(["Webcam"]))
    assert result["score"] == 0.0


@pytest.mark.parametrize(
    "example",
    [
        _example(with_facts_key=False),  # example defines no facts
        _example(facts=[]),  # empty fact list must not divide by zero
        _example(facts=None),
    ],
)
def test_factual_accuracy_skips_examples_without_facts(example):
    result = factual_accuracy(_run("anything"), example)
    assert result == {"key": "factual_accuracy", "score": None}


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
    _patch_judge(monkeypatch, HelpfulnessVerdict(reasoning="because", score=rating))
    result = helpfulness(_run("A webcam costs $89.99"), _example(message="find a webcam"))
    assert result == {"key": "helpfulness", "score": expected, "comment": "because"}


def test_helpfulness_prompt_contains_message_and_response(monkeypatch):
    judge = _patch_judge(monkeypatch, HelpfulnessVerdict(reasoning="ok", score=5))
    helpfulness(_run("resp {with braces}"), _example(message="msg {x}"))
    assert "msg {x}" in judge.prompts[0]
    assert "resp {with braces}" in judge.prompts[0]


@pytest.mark.parametrize("bad_rating", [0, 6, -1])
def test_helpfulness_rejects_out_of_range_rating(monkeypatch, bad_rating):
    _patch_judge(monkeypatch, HelpfulnessVerdict(reasoning="x", score=bad_rating))
    with pytest.raises(ValueError, match="out-of-range"):
        helpfulness(_run("r"), _example())


def test_helpfulness_propagates_judge_errors(monkeypatch):
    _patch_judge(monkeypatch, RuntimeError("judge down"))
    with pytest.raises(RuntimeError, match="judge down"):
        helpfulness(_run("r"), _example())


def test_reference_outputs_includes_facts_only_when_defined():
    base = {"input": "hi", "expected_tool": None, "expected_agent": "general"}
    assert reference_outputs(base) == {"expected_tool": None, "expected_agent": "general"}
    with_facts = {**base, "expected_facts": ["a"]}
    assert reference_outputs(with_facts)["expected_facts"] == ["a"]


_SEED_PRICES = {f"{p.price:.2f}" for p in _PRODUCTS}
_SEED_NAMES = [p.name.lower() for p in _PRODUCTS]
_FACT_EXAMPLES = [ex for ex in EXAMPLES if "expected_facts" in ex]


def test_golden_set_has_fact_labelled_examples():
    assert _FACT_EXAMPLES


@pytest.mark.parametrize("example", _FACT_EXAMPLES, ids=lambda ex: ex["input"])
def test_expected_facts_match_seed_data(example):
    """Guards against the seed data changing without the golden set following."""
    facts = example["expected_facts"]
    assert facts
    assert all(isinstance(fact, str) and fact for fact in facts)
    for fact in facts:
        if re.fullmatch(r"\d+\.\d{2}", fact):
            assert fact in _SEED_PRICES, f"{fact} is not a seed product price"
        elif fact.isdigit():
            assert float(fact) == _SEED_BALANCE, f"{fact} is not the seeded balance"
        else:
            assert any(fact.lower() in name for name in _SEED_NAMES), (
                f"{fact} is not a seed product name"
            )


def test_embed_eval_products_embeds_every_product(db, monkeypatch):
    """Regression: the eval process must build the RAG index itself, or all searches are empty."""
    from app.agent.shared import rag
    from app.models.product import Product
    from evals.run_eval import embed_eval_products

    db.add_all(
        [
            Product(name="A", description="d", image_url="/a.jpg", price=1.0, stock_quantity=1),
            Product(name="B", description="d", image_url="/b.jpg", price=2.0, stock_quantity=1),
        ]
    )
    db.commit()
    embedded: list = []
    monkeypatch.setattr(rag, "embed_products", embedded.extend)

    assert embed_eval_products(db) == 2
    assert {p.name for p in embedded} == {"A", "B"}


def test_embed_eval_products_fails_loudly_when_no_products(db, monkeypatch):
    from app.agent.shared import rag
    from evals.run_eval import embed_eval_products

    monkeypatch.setattr(rag, "embed_products", lambda products: pytest.fail("should not embed"))
    with pytest.raises(RuntimeError, match="No products"):
        embed_eval_products(db)
