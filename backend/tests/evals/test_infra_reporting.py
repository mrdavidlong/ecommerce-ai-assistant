"""Tests for the local eval reports (breakdown, confusion matrix, misses).

Group 3 of 3 for the eval suite (see README "How the evals are tested"):
infrastructure. These tables are how a run is read
after it finishes, so wrong arithmetic here would mislead every conclusion.
"""

from types import SimpleNamespace

from evals.reporting import breakdown_by, confusion_matrix, list_misses, score_rows


def _result(agent: str, **scores) -> dict:
    """Fake result dict shaped like an item yielded by langsmith evaluate()."""
    evaluations = [SimpleNamespace(key=k, score=v) for k, v in scores.items()]
    return {
        "example": SimpleNamespace(outputs={"expected_agent": agent}),
        "evaluation_results": {"results": evaluations},
    }


def _group(result: dict) -> str:
    return result["example"].outputs["expected_agent"]


def test_score_rows_flattens_results():
    """LangSmith result dicts become one plain row per example, keeping None (skipped) scores."""
    rows = score_rows([_result("cart", tool_accuracy=1, helpfulness=None)], _group)
    assert rows == [{"group": "cart", "scores": {"tool_accuracy": 1, "helpfulness": None}}]


def test_breakdown_means_per_group_and_skips_none():
    """Group means ignore skipped (None) scores, and an all-skipped group shows '-'."""
    rows = score_rows(
        [
            _result("product", tool_accuracy=1, factual_accuracy=1.0),
            _result("product", tool_accuracy=0, factual_accuracy=None),  # skipped, not a zero
            _result("cart", tool_accuracy=1, factual_accuracy=None),
        ],
        _group,
    )
    lines = breakdown_by(rows).splitlines()
    header, _, cart, product = lines
    assert header.split(" | ")[0].strip() == "group"
    assert cart.replace(" ", "") == "cart|1|-|1.00"  # no factual scores in this group -> "-"
    assert product.replace(" ", "") == "product|2|1.00|0.50"


def test_breakdown_single_group():
    """A single group still renders as a table."""
    rows = score_rows([_result("general", tool_accuracy=1)], _group)
    assert "general" in breakdown_by(rows)


def test_breakdown_empty():
    """No rows gives an empty report rather than an error."""
    assert breakdown_by([]) == ""


def test_confusion_matrix_counts():
    """Rows are expected labels, columns actual labels, cells the counts."""
    table = confusion_matrix(
        [("product", "product"), ("product", "cart"), ("cart", "cart"), ("cart", "cart")]
    )
    lines = table.splitlines()
    assert [c.strip() for c in lines[0].split("|")] == ["expected \\ actual", "cart", "product"]
    assert [c.strip() for c in lines[2].split("|")] == ["cart", "2", "0"]
    assert [c.strip() for c in lines[3].split("|")] == ["product", "1", "1"]


def test_confusion_matrix_empty():
    """No pairs gives an empty report rather than an error."""
    assert confusion_matrix([]) == ""


def _scored(message: str, **scores) -> dict:
    """Fake result with example inputs and evaluator objects that carry comments."""
    evaluations = [SimpleNamespace(key=k, score=v, comment=f"why {k}") for k, v in scores.items()]
    return {
        "example": SimpleNamespace(inputs={"message": message}),
        "evaluation_results": {"results": evaluations},
    }


def test_list_misses_reports_only_scores_below_one():
    """Only real scores below 1 are listed; perfect and skipped ones are not."""
    results = [
        _scored("good", tool_accuracy=1, state_accuracy=None),
        _scored("bad", tool_accuracy=0, state_accuracy=1),
        _scored("half", factual_accuracy=0.5),
    ]
    assert list_misses(results) == [
        "{'message': 'bad'} -> tool_accuracy=0.00 (why tool_accuracy)",
        "{'message': 'half'} -> factual_accuracy=0.50 (why factual_accuracy)",
    ]


def test_list_misses_ignores_named_metrics():
    """Noisy metrics such as the LLM-judged helpfulness can be excluded."""
    results = [_scored("x", helpfulness=0.5, tool_accuracy=0)]
    assert len(list_misses(results, ignore_metrics=["helpfulness"])) == 1


def test_list_misses_empty():
    """No results gives no misses."""
    assert list_misses([]) == []
