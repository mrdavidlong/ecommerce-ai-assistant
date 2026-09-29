"""Tests for the dataset upsert helper. A fake client stands in for LangSmith.

Group 3 of 3 for the eval suite (see README "How the evals are tested"):
infrastructure. Syncing must never recreate a dataset, because
LangSmith deletes a dataset's experiments with it.
"""

from types import SimpleNamespace

import pytest

from evals.sync import plan_sync, sync_dataset


def _row(id_: str, message: str, outputs: dict) -> SimpleNamespace:
    """Fake LangSmith dataset example."""
    return SimpleNamespace(id=id_, inputs={"message": message}, outputs=outputs)


def _spec(message: str, outputs: dict) -> dict:
    return {"inputs": {"message": message}, "outputs": outputs}


class _FakeClient:
    """Records the writes sync_dataset makes."""

    def __init__(self, rows: list | None = None, has_dataset: bool = True):
        self.rows = rows or []
        self._has_dataset = has_dataset
        self.calls: list[tuple[str, dict]] = []

    def has_dataset(self, dataset_name):
        return self._has_dataset

    def read_dataset(self, dataset_name):
        return SimpleNamespace(id="ds-1")

    def create_dataset(self, name, description):
        self.calls.append(("create_dataset", {"name": name}))
        return SimpleNamespace(id="ds-new")

    def list_examples(self, dataset_id):
        return iter(self.rows)

    def create_examples(self, **kwargs):
        self.calls.append(("create_examples", kwargs))

    def update_examples(self, **kwargs):
        self.calls.append(("update_examples", kwargs))

    def delete_examples(self, ids):
        self.calls.append(("delete_examples", {"ids": ids}))


def test_plan_all_new():
    """Every desired example is created when the dataset is empty."""
    plan = plan_sync([], [_spec("a", {"x": 1}), _spec("b", {"x": 2})])
    assert [e["inputs"]["message"] for e in plan.created] == ["a", "b"]
    assert (plan.updated, plan.deleted, plan.unchanged) == ([], [], 0)


def test_plan_no_changes():
    """An identical example is left alone and counted as unchanged."""
    plan = plan_sync([_row("1", "a", {"x": 1})], [_spec("a", {"x": 1})])
    assert plan.unchanged == 1
    assert not (plan.created or plan.updated or plan.deleted)


def test_plan_changed_outputs_keep_example_id():
    """Changed labels update the existing example in place, keeping its id (and experiments)."""
    plan = plan_sync([_row("1", "a", {"x": 1})], [_spec("a", {"x": 2})])
    assert plan.updated == [{"id": "1", "inputs": {"message": "a"}, "outputs": {"x": 2}}]
    assert not (plan.created or plan.deleted)


def test_plan_removed_example_is_deleted():
    """Examples no longer in the golden set are deleted from the dataset."""
    plan = plan_sync([_row("1", "a", {}), _row("2", "gone", {})], [_spec("a", {})])
    assert plan.deleted == ["2"]
    assert plan.unchanged == 1


def test_plan_stray_duplicate_row_is_deleted():
    """A duplicate row in the dataset is deleted, keeping one copy."""
    plan = plan_sync([_row("1", "a", {}), _row("2", "a", {})], [_spec("a", {})])
    assert plan.deleted == ["2"]
    assert plan.unchanged == 1


def test_plan_history_distinguishes_examples_with_same_message():
    """Multi-turn examples are matched on message plus history, not message alone."""
    with_history = {"inputs": {"message": "add it", "history": ["show laptop"]}, "outputs": {}}
    plain = {"inputs": {"message": "add it"}, "outputs": {}}
    plan = plan_sync([], [with_history, plain])
    assert len(plan.created) == 2


def test_plan_rejects_duplicate_desired_inputs():
    """Two golden examples with identical inputs are rejected as ambiguous."""
    with pytest.raises(ValueError, match="Duplicate"):
        plan_sync([], [_spec("a", {}), _spec("a", {"x": 1})])


def test_sync_applies_only_the_differences():
    """Only the create, update and delete that are needed are sent to LangSmith."""
    client = _FakeClient(
        rows=[_row("1", "keep", {"x": 1}), _row("2", "old", {}), _row("3", "chg", {})]
    )
    plan = sync_dataset(
        client,
        "ds",
        "desc",
        [_spec("keep", {"x": 1}), _spec("chg", {"x": 9}), _spec("new", {"x": 3})],
    )
    assert plan.summary() == "1 to create, 1 to update, 1 to delete, 1 unchanged"
    assert [name for name, _ in client.calls] == [
        "create_examples",
        "update_examples",
        "delete_examples",
    ]
    assert client.calls[1][1]["updates"] == [{"id": "3", "outputs": {"x": 9}}]
    assert client.calls[2][1]["ids"] == ["2"]


def test_sync_no_changes_writes_nothing():
    """An up-to-date dataset triggers no writes at all."""
    client = _FakeClient(rows=[_row("1", "a", {})])
    sync_dataset(client, "ds", "desc", [_spec("a", {})])
    assert client.calls == []


def test_sync_creates_missing_dataset():
    """A missing dataset is created first, then filled."""
    client = _FakeClient(has_dataset=False)
    plan = sync_dataset(client, "ds", "desc", [_spec("a", {})])
    assert [name for name, _ in client.calls] == ["create_dataset", "create_examples"]
    assert client.calls[1][1]["dataset_id"] == "ds-new"
    assert len(plan.created) == 1


@pytest.mark.parametrize("has_dataset", [True, False])
def test_sync_dry_run_writes_nothing(has_dataset):
    """A dry run reports the plan but writes nothing, whether or not the dataset exists."""
    client = _FakeClient(
        rows=[_row("1", "old", {})] if has_dataset else [], has_dataset=has_dataset
    )
    plan = sync_dataset(client, "ds", "desc", [_spec("a", {})], dry_run=True)
    assert client.calls == []
    assert len(plan.created) == 1
