"""
Run an eval suite against LangSmith.

Usage:
    cd backend
    uv run python -m evals.run_eval --version v1              # end-to-end, single agent
    uv run python -m evals.run_eval --version v2              # end-to-end, multi-agent
    uv run python -m evals.run_eval --suite supervisor        # supervisor routing only
    uv run python -m evals.run_eval --suite retrieval         # product vector search only
    uv run python -m evals.run_eval --suite e2e --dry-run     # show the plan, call nothing

Push/refresh the datasets first with `uv run python -m evals.dataset`.
Results appear in LangSmith → Datasets → <dataset> → Experiments.
Compare v1 vs v2 using the "Compare" button.
"""

import argparse
import os
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv

load_dotenv()

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage  # noqa: E402
from langsmith import Client  # noqa: E402
from langsmith.evaluation import evaluate  # noqa: E402

from evals.dataset import (  # noqa: E402
    DATASET_NAME,
    RETRIEVAL_DATASET_NAME,
    SUPERVISOR_DATASET_NAME,
    e2e_specs,
    retrieval_specs,
    supervisor_specs,
)
from evals.eval_db import (  # noqa: E402
    embed_eval_products,
    get_eval_users,
    reset_eval_db,
    snapshot_state,
)
from evals.evaluators import (  # noqa: E402
    JUDGE_MODEL,
    factual_accuracy,
    helpfulness,
    hit_at_1,
    recall_at_k,
    reciprocal_rank,
    routing_accuracy,
    state_accuracy,
    supervisor_route_accuracy,
    tool_accuracy,
)
from evals.reporting import breakdown_by, confusion_matrix, list_misses, score_rows  # noqa: E402

_NO_USER_RESPONSE = "No user found"


def _conversation_history(turns: list[tuple[str, str]]) -> list[BaseMessage]:
    """Turn (user message, assistant reply) pairs into the message list v1 takes as history."""
    messages: list[BaseMessage] = []
    for user_text, reply in turns:
        messages += [HumanMessage(content=user_text), AIMessage(content=reply)]
    return messages


def _make_e2e_target(version: str) -> Callable[[dict], dict]:
    """Return a target that runs one golden example through the v1 or v2 agent.

    Each call starts from a freshly reset, order-seeded database (refunds mutate state), replays
    any earlier turns in `inputs["history"]`, then sends `inputs["message"]` and snapshots the
    resulting DB/cart state. Only the final turn's response, steps and cart actions are scored.
    """
    from app.db.session import SessionLocal

    def target(inputs: dict) -> dict:
        with SessionLocal() as db:
            reset_eval_db(db)
            users = get_eval_users(db)
            if not users:
                return {"response": _NO_USER_RESPONSE, "steps": [], "agent_name": None}
            user_id = str(users[0].id)
            earlier_messages = inputs.get("history", [])

            if version == "v1":
                from app.agent.v1.agent import run_agent_v1

                turns: list[tuple[str, str]] = []
                for text in earlier_messages:
                    reply, _, _ = run_agent_v1(db, user_id, text, _conversation_history(turns))
                    turns.append((text, reply))
                response, steps, cart_actions = run_agent_v1(
                    db, user_id, inputs["message"], _conversation_history(turns)
                )
                # v1 has a single agent and no supervisor, so there is no agent_name to score.
                agent_name = None
            else:
                from app.agent.v2.agent import run_agent_v2

                session_id = f"eval-{uuid.uuid4().hex[:8]}"
                for text in earlier_messages:
                    run_agent_v2(db, user_id, text, session_id)
                response, steps, cart_actions, agent_name = run_agent_v2(
                    db, user_id, inputs["message"], session_id
                )

            return {
                "response": response,
                "steps": steps,
                "agent_name": agent_name,
                "final_state": snapshot_state(db, user_id, cart_actions),
            }

    return target


def _make_supervisor_target(_: argparse.Namespace) -> Callable[[dict], dict]:
    """Return a target that runs only the v2 supervisor node and reports its route."""
    from langchain_openai import ChatOpenAI

    from app.agent.v2.agents.supervisor import make_supervisor_node

    llm = ChatOpenAI(model=os.getenv("LLM_MODEL", "gpt-4o"), temperature=0)
    supervisor = make_supervisor_node(llm)

    def target(inputs: dict) -> dict:
        state = {"messages": [HumanMessage(content=inputs["message"])], "steps": []}
        return {"agent_name": supervisor(state)["agent_name"]}  # type: ignore[arg-type]

    return target


def _make_retrieval_target(_: argparse.Namespace) -> Callable[[dict], dict]:
    """Return a target that runs only the product vector search, at the tool's result cutoff."""
    from app.agent.shared.rag import search_products_rag
    from app.agent.shared.tools import SEARCH_RESULT_COUNT

    def target(inputs: dict) -> dict:
        results = search_products_rag(inputs["query"], n=SEARCH_RESULT_COUNT)
        return {"products": [r["name"] for r in results]}

    return target


def _e2e_group(result: Mapping[str, Any]) -> str:
    """Group end-to-end results by the specialist that should handle the query."""
    outputs = result["example"].outputs or {}
    if "expected_agents" in outputs:
        return "ambiguous"
    return outputs.get("expected_agent", "unlabelled")


def _print_misses(results: Sequence[Mapping[str, Any]], ignore_metrics=("helpfulness",)) -> None:
    misses = list_misses(results, ignore_metrics)
    print(f"\nMisses on deterministic metrics: {len(misses)}")
    for line in misses:
        print(f"  - {line}")


def _report_retrieval(results: Sequence[Mapping[str, Any]]) -> None:
    print("\nRetrieval scores (mean over all queries):")
    print(breakdown_by(score_rows(results, lambda _: "all")))
    _print_misses(results, ignore_metrics=("reciprocal_rank",))


def _report_e2e(results: Sequence[Mapping[str, Any]]) -> None:
    print("\nScores by expected specialist (mean; '-' = metric skipped for the group):")
    print(breakdown_by(score_rows(results, _e2e_group)))
    _print_misses(results)


def _report_supervisor(results: Sequence[Mapping[str, Any]]) -> None:
    pairs = []
    for result in results:
        acceptable = (result["example"].outputs or {}).get("expected_agents") or ["?"]
        actual = ((result["run"].outputs or {}).get("agent_name")) or "error"
        # For an ambiguous query the matched acceptable route counts as the expected one.
        pairs.append((actual if actual in acceptable else acceptable[0], actual))
    print("\nRouting confusion matrix (rows: expected, columns: actual):")
    print(confusion_matrix(pairs))
    _print_misses(results)


@dataclass
class Suite:
    """One runnable eval suite: which dataset, what runs, how it is scored and reported."""

    dataset: str  # LangSmith dataset name
    evaluators: list  # evaluator functions applied to every run
    specs: Callable[[], list[dict]]  # local golden examples, used for --dry-run
    make_target: Callable[[argparse.Namespace], Callable[[dict], dict]]
    report: (
        Callable[[Sequence[Mapping[str, Any]]], None] | None
    )  # local report printed after the run
    needs_search_index: bool  # whether the run needs the in-memory product index
    needs_seeded_db: bool  # whether examples reset and seed the database themselves


SUITES = {
    "e2e": Suite(
        dataset=DATASET_NAME,
        evaluators=[
            routing_accuracy,
            tool_accuracy,
            factual_accuracy,
            state_accuracy,
            helpfulness,
        ],
        specs=e2e_specs,
        make_target=lambda args: _make_e2e_target(args.version),
        report=_report_e2e,
        needs_search_index=True,
        needs_seeded_db=True,
    ),
    "supervisor": Suite(
        dataset=SUPERVISOR_DATASET_NAME,
        evaluators=[supervisor_route_accuracy],
        specs=supervisor_specs,
        make_target=_make_supervisor_target,
        report=_report_supervisor,
        needs_search_index=False,
        needs_seeded_db=False,
    ),
    "retrieval": Suite(
        dataset=RETRIEVAL_DATASET_NAME,
        evaluators=[recall_at_k, hit_at_1, reciprocal_rank],
        specs=retrieval_specs,
        make_target=_make_retrieval_target,
        report=_report_retrieval,
        needs_search_index=True,
        needs_seeded_db=False,
    ),
}


def _print_plan(name: str, suite: Suite, args: argparse.Namespace) -> None:
    """Print what a real run would do, without calling any LLM or LangSmith."""
    print(f"[dry run] suite: {name}" + (f" ({args.version})" if name == "e2e" else ""))
    print(f"  dataset:    {suite.dataset} ({len(suite.specs())} local examples)")
    print(f"  evaluators: {', '.join(e.__name__ for e in suite.evaluators)}")
    if helpfulness in suite.evaluators:
        print(f"  judge:      {JUDGE_MODEL}")
    if suite.needs_seeded_db:
        print("  database:   reset + seeded orders before every example")
    if suite.needs_search_index:
        print("  index:      product embeddings built once before the run")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", choices=sorted(SUITES), default="e2e")
    parser.add_argument(
        "--version", choices=["v1", "v2"], default="v2", help="agent version (e2e suite only)"
    )
    parser.add_argument("--dry-run", action="store_true", help="show the plan, call nothing")
    args = parser.parse_args()
    suite = SUITES[args.suite]

    if args.dry_run:
        _print_plan(args.suite, suite, args)
        return None

    client = Client()
    if not client.has_dataset(dataset_name=suite.dataset):
        raise RuntimeError(
            f"Dataset '{suite.dataset}' not found — run `uv run python -m evals.dataset` first."
        )

    if suite.needs_search_index:
        from app.db.session import SessionLocal

        with SessionLocal() as db:
            print(f"Embedded {embed_eval_products(db)} products into ChromaDB.")

    label = args.version if args.suite == "e2e" else args.suite
    print(f"Running eval suite '{args.suite}' ({label}) on {suite.dataset}")
    os.environ["LANGSMITH_PROJECT"] = "ecommerce-ai-assistant"

    results = evaluate(
        suite.make_target(args),
        data=suite.dataset,
        evaluators=suite.evaluators,
        experiment_prefix=f"{label}-eval",
        metadata={"suite": args.suite, "version": args.version},
    )

    print(f"\nEval complete. View results in LangSmith → Datasets → {suite.dataset} → Experiments")
    if suite.report:
        suite.report(list(results))
    return results


if __name__ == "__main__":
    main()
