"""
Run evaluation against v1 or v2 endpoints.

Usage:
    cd backend
    uv run python -m evals.run_eval --version v1
    uv run python -m evals.run_eval --version v2

Results appear in LangSmith → Datasets → ecommerce-assistant-eval → Experiments.
Compare v1 vs v2 using the "Compare" button.
"""

import argparse
import os
import uuid

from dotenv import load_dotenv

load_dotenv()

from langsmith import Client  # noqa: E402
from langsmith.evaluation import evaluate  # noqa: E402

from evals.dataset import DATASET_NAME, push_dataset  # noqa: E402
from evals.evaluators import routing_accuracy, tool_accuracy  # noqa: E402


def _make_target(version: str):
    """Return a target function that calls run_agent_v1 or run_agent_v2 directly."""
    from app.db.session import SessionLocal
    from app.models import order, order_item, product, user  # noqa: F401
    from app.models.user import User

    def _get_eval_user(db):
        return db.query(User).first()

    if version == "v1":
        from app.agent.v1.agent import run_agent_v1

        def target_v1(inputs: dict) -> dict:
            db = SessionLocal()
            try:
                user = _get_eval_user(db)
                if not user:
                    return {"response": "No user found", "steps": [], "agent_name": "unknown"}
                response, steps, _ = run_agent_v1(db, str(user.id), inputs["message"], [])
                return {"response": response, "steps": steps, "agent_name": "unknown"}
            finally:
                db.close()

        return target_v1

    else:
        from app.agent.v2.agent import run_agent_v2

        def target_v2(inputs: dict) -> dict:
            db = SessionLocal()
            try:
                user = _get_eval_user(db)
                if not user:
                    return {"response": "No user found", "steps": [], "agent_name": "unknown"}
                session_id = f"eval-{uuid.uuid4().hex[:8]}"
                response, steps, _, agent_name = run_agent_v2(
                    db, str(user.id), inputs["message"], session_id, []
                )
                return {"response": response, "steps": steps, "agent_name": agent_name}
            finally:
                db.close()

        return target_v2


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", choices=["v1", "v2"], default="v2")
    args = parser.parse_args()

    client = Client()

    existing = [d for d in client.list_datasets() if d.name == DATASET_NAME]
    if not existing:
        print(f"Dataset '{DATASET_NAME}' not found — creating it now...")
        push_dataset()

    print(f"Running eval for version: {args.version}")
    os.environ["LANGSMITH_PROJECT"] = "ecommerce-ai-assistant"

    results = evaluate(
        _make_target(args.version),
        data=DATASET_NAME,
        evaluators=[routing_accuracy, tool_accuracy],
        experiment_prefix=f"{args.version}-eval",
        metadata={"version": args.version},
    )

    print(f"\nEval complete. View results in LangSmith → Datasets → {DATASET_NAME} → Experiments")
    return results


if __name__ == "__main__":
    main()
