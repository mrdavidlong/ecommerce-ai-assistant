"""
Local reports printed after an eval run: per-group metric breakdowns and confusion matrices.

LangSmith shows only experiment-wide averages, so these tables show where a score comes from
(e.g. which specialist's queries dragged a metric down, or which routes get confused).
"""

from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping
from typing import Any


def score_rows(
    results: Iterable[Mapping[str, Any]], group_of: Callable[[Mapping[str, Any]], str]
) -> list[dict]:
    """Flatten LangSmith experiment results into one row per example.

    Args:
        results: Iterable of result dicts from `evaluate()`, each with "example" and
            "evaluation_results" (whose "results" hold objects with `key` and `score`).
        group_of: Maps a result dict to the group label the row belongs to.

    Returns:
        Rows of {"group": str, "scores": {metric key: score, or None when skipped}}.
    """
    rows = []
    for result in results:
        evaluations = result["evaluation_results"]["results"]
        rows.append(
            {
                "group": group_of(result),
                "scores": {e.key: e.score for e in evaluations},
            }
        )
    return rows


def breakdown_by(rows: list[dict]) -> str:
    """Render the mean of each metric per group as a text table.

    Args:
        rows: Rows from `score_rows`. A metric's None scores (skipped) are excluded from its mean;
            a group with no scored example for a metric shows "-".

    Returns:
        A fixed-width table with one line per group (sorted) and one column per metric, plus the
        number of examples in the group. Empty string when there are no rows.
    """
    if not rows:
        return ""
    metrics = sorted({key for row in rows for key in row["scores"]})
    by_group: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_group[row["group"]].append(row["scores"])

    header = ["group", "n", *metrics]
    lines = []
    for group in sorted(by_group):
        cells = [group, str(len(by_group[group]))]
        for metric in metrics:
            values = [s[metric] for s in by_group[group] if s.get(metric) is not None]
            cells.append(f"{sum(values) / len(values):.2f}" if values else "-")
        lines.append(cells)
    return _format_table(header, lines)


def confusion_matrix(pairs: list[tuple[str, str]]) -> str:
    """Render expected-vs-actual label counts as a text table.

    Args:
        pairs: (expected label, actual label) for each example. For examples with several
            acceptable labels, pass the acceptable label the run matched, or the first if none.

    Returns:
        A table with expected labels as rows and actual labels as columns. Empty string when
        there are no pairs.
    """
    if not pairs:
        return ""
    counts: dict[tuple[str, str], int] = defaultdict(int)
    for expected, actual in pairs:
        counts[(expected, actual)] += 1
    expected_labels = sorted({e for e, _ in pairs})
    actual_labels = sorted({a for _, a in pairs})
    header = ["expected \\ actual", *actual_labels]
    lines = [
        [expected, *[str(counts[(expected, actual)]) for actual in actual_labels]]
        for expected in expected_labels
    ]
    return _format_table(header, lines)


def _format_table(header: list[str], lines: list[list[str]]) -> str:
    """Left-align cells into columns as wide as their longest entry."""
    widths = [max(len(row[i]) for row in [header, *lines]) for i in range(len(header))]
    rendered = [
        " | ".join(cell.ljust(w) for cell, w in zip(row, widths)) for row in [header, *lines]
    ]
    rendered.insert(1, "-+-".join("-" * w for w in widths))
    return "\n".join(rendered)


def list_misses(
    results: Iterable[Mapping[str, Any]], ignore_metrics: Iterable[str] = ()
) -> list[str]:
    """Describe every example that scored below 1 on a deterministic metric.

    Args:
        results: Result dicts from `evaluate()` (with "run", "example" and "evaluation_results").
        ignore_metrics: Metric keys to leave out (e.g. the LLM-judged helpfulness, which is
            rarely exactly 1).

    Returns:
        One line per miss: the example inputs, the metric, its score and the evaluator comment.
    """
    ignored = set(ignore_metrics)
    lines = []
    for result in results:
        for evaluation in result["evaluation_results"]["results"]:
            if evaluation.key in ignored or evaluation.score is None or evaluation.score >= 1:
                continue
            comment = f" ({evaluation.comment})" if getattr(evaluation, "comment", None) else ""
            inputs = result["example"].inputs
            lines.append(f"{inputs} -> {evaluation.key}={evaluation.score:.2f}{comment}")
    return lines
