"""
Integrity of the golden sets: are the labels themselves consistent with the seed data?

Group 2 of 3 for the eval suite (see README "How the evals are tested"): golden sets. An eval
is only as good as its labels, and labels rot silently when the seed data changes or a
number is mistyped. These tests need no LLM and guard the labels in evals/dataset.py and
evals/component_datasets.py:
    - route labels are valid and unambiguous
    - product names, prices, order ids and stock numbers exist in the seed data
    - expected balances equal the starting balance plus the refunded items' prices
    - no duplicate inputs (they could not be told apart when syncing to LangSmith)
    - the multi-turn and adversarial cases we promise actually exist
"""

import re
from collections import Counter

import pytest

from app.agent.shared.tools import _REFUND_WINDOW_DAYS
from app.db.seed import _PRODUCTS
from evals.component_datasets import RETRIEVAL_EXAMPLES, SUPERVISOR_EXAMPLES
from evals.dataset import (
    EXAMPLES,
    e2e_specs,
    example_inputs,
    reference_outputs,
    retrieval_specs,
    supervisor_specs,
)
from evals.eval_db import _SEED_BALANCE, OLD_ORDER_ID, OTHER_USER_ORDER_ID, RECENT_ORDER_ID
from evals.sync import plan_sync

_ROUTES = {"product", "account", "cart", "general"}
_PRICES = {p.name: p.price for p in _PRODUCTS}
_NAMES = [p.name.lower() for p in _PRODUCTS]
_STATE_KEYS = {"balance", "refunded", "stock", "cart_actions"}
_ORDER_PREFIXES = {str(i)[:8] for i in (RECENT_ORDER_ID, OLD_ORDER_ID, OTHER_USER_ORDER_ID)}
# Whole-number facts the golden set may expect: the starting balance, the refund window in days
# (the keyboard order is refused for being older) and the Laptop's stock (over-quantity request).
_NUMERIC_FACTS = {
    str(int(_SEED_BALANCE)),
    str(_REFUND_WINDOW_DAYS),
    str(next(p.stock_quantity for p in _PRODUCTS if p.name == "Laptop")),
}


def _id(example: dict) -> str:
    return example["input"]


# ---------------------------------------------------------------------------------------------
# End-to-end set (EXAMPLES): routes, history, order ids
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("example", EXAMPLES, ids=_id)
def test_e2e_example_has_valid_route_labels(example):
    """Each example labels exactly one of expected_agent / expected_agents, all valid routes."""
    has_single, has_multi = "expected_agent" in example, "expected_agents" in example
    assert has_single != has_multi, "label exactly one of expected_agent / expected_agents"
    routes = [example["expected_agent"]] if has_single else example["expected_agents"]
    assert routes and set(routes) <= _ROUTES


@pytest.mark.parametrize("example", EXAMPLES, ids=_id)
def test_e2e_example_history_is_a_list_of_messages(example):
    """Multi-turn history is a list of non-empty user messages (or absent)."""
    history = example.get("history", [])
    assert isinstance(history, list) and all(isinstance(m, str) and m for m in history)


def test_e2e_examples_are_unique_by_message_and_history():
    """Two examples with the same message and history could not be told apart when syncing."""
    keys = [(e["input"], tuple(e.get("history", []))) for e in EXAMPLES]
    assert not [k for k, n in Counter(keys).items() if n > 1]


@pytest.mark.parametrize("example", EXAMPLES, ids=_id)
def test_e2e_order_ids_in_messages_are_seeded_orders(example):
    """A query that names an order must name one that eval_db actually seeds."""
    texts = [example["input"], *example.get("history", [])]
    for prefix in re.findall(r"\b5eed[0-9a-f]{4}\b", " ".join(texts)):
        assert prefix in _ORDER_PREFIXES


def test_e2e_covers_multi_turn_and_adversarial_cases():
    """The set keeps the hard cases it exists for: follow-up turns and a prompt injection."""
    assert sum("history" in e for e in EXAMPLES) >= 3
    assert any("Ignore all previous instructions" in e["input"] for e in EXAMPLES)


# ---------------------------------------------------------------------------------------------
# End-to-end set: expected_facts (answer labels) must be derivable from the seed data
# ---------------------------------------------------------------------------------------------

_FACT_EXAMPLES = [ex for ex in EXAMPLES if "expected_facts" in ex]


def test_golden_set_has_fact_labelled_examples():
    assert _FACT_EXAMPLES


@pytest.mark.parametrize("example", _FACT_EXAMPLES, ids=_id)
def test_expected_facts_match_seed_data(example):
    """Guards against the seed data changing without the golden set following."""
    facts = example["expected_facts"]
    assert facts
    assert all(isinstance(fact, str) and fact for fact in facts)
    for fact in facts:
        if re.fullmatch(r"\d+\.\d{2}", fact):
            assert fact in {f"{p:.2f}" for p in _PRICES.values()}, f"{fact} is not a seed price"
        elif fact.isdigit():
            assert fact in _NUMERIC_FACTS, f"{fact} is not a known seed-derived number"
        else:
            assert any(fact.lower() in name for name in _NAMES), f"{fact} is not a product name"


# ---------------------------------------------------------------------------------------------
# End-to-end set: expected_state (effect labels) must be arithmetically consistent
# ---------------------------------------------------------------------------------------------

_STATE_EXAMPLES = [e for e in EXAMPLES if "expected_state" in e]


def test_e2e_has_state_labelled_examples():
    assert len(_STATE_EXAMPLES) >= 10


@pytest.mark.parametrize("example", _STATE_EXAMPLES, ids=_id)
def test_expected_state_uses_known_keys_and_products(example):
    """expected_state only uses keys the snapshot provides, and only real product names."""
    state = example["expected_state"]
    assert state and set(state) <= _STATE_KEYS
    named = [*state.get("refunded", {}), *state.get("stock", {})]
    named += [a["product_name"] for a in state.get("cart_actions", [])]
    assert set(named) <= set(_PRICES)


@pytest.mark.parametrize("example", _STATE_EXAMPLES, ids=_id)
def test_expected_balance_matches_the_refunded_items(example):
    """Domain check on the label arithmetic: balance = starting balance + refunded item prices."""
    state = example["expected_state"]
    if "balance" not in state or "refunded" not in state:
        pytest.skip("balance or refunded not asserted")
    refunded_value = sum(_PRICES[name] * qty for name, qty in state["refunded"].items())
    assert state["balance"] == pytest.approx(_SEED_BALANCE + refunded_value)


# ---------------------------------------------------------------------------------------------
# Supervisor set (component level)
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("example", SUPERVISOR_EXAMPLES, ids=_id)
def test_supervisor_example_has_valid_routes(example):
    """Acceptable routes are non-empty, valid and free of repeats."""
    routes = example["expected_agents"]
    assert routes and set(routes) <= _ROUTES and len(set(routes)) == len(routes)


def test_supervisor_inputs_are_unique():
    inputs = [e["input"] for e in SUPERVISOR_EXAMPLES]
    assert len(inputs) == len(set(inputs))


@pytest.mark.parametrize("route", sorted(_ROUTES))
def test_supervisor_set_has_clear_examples_for_every_route(route):
    """Every route has at least 5 unambiguous examples, so a per-route miss is meaningful."""
    clear = [e for e in SUPERVISOR_EXAMPLES if e["expected_agents"] == [route]]
    assert len(clear) >= 5


def test_supervisor_set_includes_ambiguous_examples():
    """The set keeps its ambiguous cases, where more than one route is acceptable."""
    assert any(len(e["expected_agents"]) > 1 for e in SUPERVISOR_EXAMPLES)


# ---------------------------------------------------------------------------------------------
# Retrieval set (component level)
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("example", RETRIEVAL_EXAMPLES, ids=_id)
def test_retrieval_example_labels_are_seed_products(example):
    """Relevant products are real, distinct seed products."""
    relevant = example["relevant_products"]
    assert relevant and len(set(relevant)) == len(relevant)
    assert set(relevant) <= set(_PRICES)


def test_retrieval_queries_are_unique():
    queries = [e["input"] for e in RETRIEVAL_EXAMPLES]
    assert len(queries) == len(set(queries))


# ---------------------------------------------------------------------------------------------
# Conversion to LangSmith examples
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("specs", [e2e_specs, supervisor_specs, retrieval_specs])
def test_specs_can_be_synced_without_duplicate_inputs(specs):
    """Every dataset converts to specs that plan_sync accepts (no duplicate inputs)."""
    built = specs()
    assert built
    assert len(plan_sync([], built).created) == len(built)


def test_specs_carry_inputs_and_outputs():
    """Component specs map the golden entries onto LangSmith inputs and outputs."""
    assert supervisor_specs()[0] == {
        "inputs": {"message": SUPERVISOR_EXAMPLES[0]["input"]},
        "outputs": {"expected_agents": SUPERVISOR_EXAMPLES[0]["expected_agents"]},
    }
    assert retrieval_specs()[0]["inputs"] == {"query": RETRIEVAL_EXAMPLES[0]["input"]}


def test_example_inputs_include_history_only_when_present():
    assert example_inputs({"input": "hi"}) == {"message": "hi"}
    assert example_inputs({"input": "hi", "history": ["a"]}) == {"message": "hi", "history": ["a"]}


def test_reference_outputs_include_only_defined_keys():
    """Optional labels are copied only when defined, so 'no label' differs from 'empty label'."""
    example = {"input": "x", "expected_agents": ["cart"], "expected_state": {"cart_actions": []}}
    assert reference_outputs(example) == {
        "expected_agents": ["cart"],
        "expected_state": {"cart_actions": []},
    }
    assert reference_outputs({"input": "x", "expected_tool": None}) == {"expected_tool": None}
    base = {"input": "hi", "expected_tool": None, "expected_agent": "general"}
    assert reference_outputs(base) == {"expected_tool": None, "expected_agent": "general"}
