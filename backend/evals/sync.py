"""
Upsert golden examples into a LangSmith dataset without recreating it.

Deleting and recreating a dataset also deletes its experiments, so datasets are synced instead:
examples are matched on their inputs, and only the differences are written.
"""

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SyncPlan:
    """What a sync creates, updates and deletes; returned for both real and dry runs."""

    # {"inputs", "outputs"} specs not yet in the dataset.
    created: list[dict] = field(default_factory=list)
    # {"id", "inputs", "outputs"} for examples whose outputs changed; the id is preserved.
    updated: list[dict] = field(default_factory=list)
    # Ids of dataset examples no longer in the golden set.
    deleted: list[Any] = field(default_factory=list)
    # Number of examples already up to date.
    unchanged: int = 0

    def summary(self) -> str:
        return (
            f"{len(self.created)} to create, {len(self.updated)} to update, "
            f"{len(self.deleted)} to delete, {self.unchanged} unchanged"
        )


def _input_key(inputs: dict) -> str:
    """Stable identity of an example: its inputs serialised with sorted keys."""
    return json.dumps(inputs, sort_keys=True)


def plan_sync(existing: list, examples: list[dict]) -> SyncPlan:
    """Diff the desired examples against what the dataset holds.

    Args:
        existing: Current dataset examples (objects with id, inputs and outputs).
        examples: Desired examples, each {"inputs": dict, "outputs": dict}.

    Returns:
        The SyncPlan needed to make the dataset match `examples`.

    Raises:
        ValueError: If two desired examples share the same inputs (they could not be told apart).
    """
    desired: dict[str, dict] = {}
    for example in examples:
        key = _input_key(example["inputs"])
        if key in desired:
            raise ValueError(f"Duplicate example inputs: {example['inputs']}")
        desired[key] = example

    plan = SyncPlan()
    seen: set[str] = set()
    for row in existing:
        key = _input_key(row.inputs or {})
        if key not in desired or key in seen:
            # Removed from the golden set, or a stray duplicate row in the dataset.
            plan.deleted.append(row.id)
            continue
        seen.add(key)
        wanted = desired[key]
        if (row.outputs or {}) == wanted["outputs"]:
            plan.unchanged += 1
        else:
            plan.updated.append({"id": row.id, **wanted})

    plan.created = [example for key, example in desired.items() if key not in seen]
    return plan


def sync_dataset(
    client, name: str, description: str, examples: list[dict], dry_run: bool = False
) -> SyncPlan:
    """Make the LangSmith dataset `name` match `examples`, preserving example ids and experiments.

    Args:
        client: A langsmith.Client.
        name: Dataset name; created if it does not exist (unless dry_run).
        description: Description used when the dataset is created.
        examples: Desired examples, each {"inputs": dict, "outputs": dict}.
        dry_run: If True, compute and return the plan without writing anything.

    Returns:
        The SyncPlan that was (or, for a dry run, would be) applied.
    """
    exists = client.has_dataset(dataset_name=name)
    dataset = client.read_dataset(dataset_name=name) if exists else None
    existing = list(client.list_examples(dataset_id=dataset.id)) if dataset else []
    plan = plan_sync(existing, examples)
    if dry_run:
        return plan

    if dataset is None:
        dataset = client.create_dataset(name, description=description)
    if plan.created:
        client.create_examples(
            inputs=[e["inputs"] for e in plan.created],
            outputs=[e["outputs"] for e in plan.created],
            dataset_id=dataset.id,
        )
    if plan.updated:
        client.update_examples(
            dataset_id=dataset.id,
            updates=[{"id": u["id"], "outputs": u["outputs"]} for u in plan.updated],
        )
    if plan.deleted:
        client.delete_examples(plan.deleted)
    return plan
