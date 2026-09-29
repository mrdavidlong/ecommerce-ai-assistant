"""
Scoring logic of the component-level evaluators (supervisor routing and product retrieval).

Group 1 of 3 for the eval suite (see README "How the evals are tested"): scoring. These
evaluators score one part of the system in isolation, unlike the end-to-end ones in
test_scoring_e2e.py. No real LLM, embedding or LangSmith call is made.
"""

from types import SimpleNamespace

import pytest

from evals.evaluators import hit_at_1, recall_at_k, reciprocal_rank, supervisor_route_accuracy


def _run(**outputs) -> SimpleNamespace:
    """Fake LangSmith Run whose outputs are the given keyword arguments."""
    return SimpleNamespace(outputs=outputs)


_RUN_WITHOUT_OUTPUTS = SimpleNamespace(outputs=None)  # a run whose target crashed


def _example(**outputs) -> SimpleNamespace:
    """Fake LangSmith Example whose labels are the given keyword arguments."""
    return SimpleNamespace(inputs={"message": "q"}, outputs=outputs)


# ---------------------------------------------------------------------------------------------
# supervisor_route_accuracy
# Is the supervisor's route one of the example's acceptable routes?
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("route", "expected", "score"),
    [
        ("product", ["product"], 1),  # exact match
        ("cart", ["product"], 0),  # wrong route
        ("cart", ["product", "cart"], 1),  # ambiguous query, either route accepted
        ("account", ["product", "cart"], 0),  # outside the acceptable set
        (None, ["product"], 0),  # supervisor produced nothing
        ("product", [], 0),  # no labels: can never match
    ],
)
def test_supervisor_route_accuracy(route, expected, score):
    """The route must be in expected_agents; several entries mark a genuinely ambiguous query."""
    result = supervisor_route_accuracy(_run(agent_name=route), _example(expected_agents=expected))
    assert result == {"key": "supervisor_route_accuracy", "score": score}


def test_supervisor_route_accuracy_missing_outputs():
    """A crashed target is a miss."""
    result = supervisor_route_accuracy(_RUN_WITHOUT_OUTPUTS, _example(expected_agents=["a"]))
    assert result["score"] == 0


# ---------------------------------------------------------------------------------------------
# Retrieval metrics: recall_at_k, hit_at_1, reciprocal_rank
# Does the vector search surface the relevant products, and how high does it rank them?
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("products", "relevant", "recall", "hit", "rr"),
    [
        (["Webcam", "Laptop"], ["Webcam"], 1.0, 1, 1.0),  # relevant at rank 1
        (["Laptop", "Webcam"], ["Webcam"], 1.0, 0, 0.5),  # relevant at rank 2
        (["A", "B", "Webcam"], ["Webcam"], 1.0, 0, 1 / 3),  # relevant at rank 3
        (["Laptop", "Mouse"], ["Webcam"], 0.0, 0, 0.0),  # relevant absent
        (["AirTag", "Laptop"], ["AirTag", "Tile Mate"], 0.5, 1, 1.0),  # partial recall
        (["AirTag", "Tile Mate"], ["AirTag", "Tile Mate"], 1.0, 1, 1.0),  # all found
        ([], ["Webcam"], 0.0, 0, 0.0),  # nothing retrieved
        (["Webcam", "Webcam"], ["Webcam"], 1.0, 1, 1.0),  # duplicate retrieved name
    ],
)
def test_retrieval_metrics(products, relevant, recall, hit, rr):
    """recall = share of relevant items found; hit = top result relevant; rr = 1 / first rank."""
    run, example = _run(products=products), _example(relevant_products=relevant)
    assert recall_at_k(run, example)["score"] == pytest.approx(recall)
    assert hit_at_1(run, example)["score"] == hit
    assert reciprocal_rank(run, example)["score"] == pytest.approx(rr)


@pytest.mark.parametrize("evaluator", [recall_at_k, hit_at_1, reciprocal_rank])
@pytest.mark.parametrize("example", [_example(), _example(relevant_products=[])])
def test_retrieval_metrics_skip_examples_without_labels(evaluator, example):
    """No relevant products labelled means nothing to measure: skipped, not scored."""
    assert evaluator(_run(products=["Webcam"]), example)["score"] is None


@pytest.mark.parametrize("evaluator", [recall_at_k, hit_at_1, reciprocal_rank])
def test_retrieval_metrics_handle_missing_outputs(evaluator):
    """A crashed target retrieved nothing, so every metric is 0."""
    result = evaluator(_RUN_WITHOUT_OUTPUTS, _example(relevant_products=["Webcam"]))
    assert result["score"] == 0
