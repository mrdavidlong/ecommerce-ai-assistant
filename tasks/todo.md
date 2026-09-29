# Eval suite v2: component evals, harder golden set, robustness

Plan: `/Users/davidlong/.claude/plans/floating-coalescing-sparrow.md` (full autonomous run, no commits)

## Milestone 1 — skip v1 routing
- [x] `routing_accuracy` returns a None score when `agent_name` is None; v1 target returns None
- [x] Tests + README wording

## Milestone 2 — component evals
- [x] `evals/sync.py` (needed by dataset pushes) — built in milestone 4 but stubbed first
- [x] Supervisor suite: dataset (~60), target, `supervisor_route_accuracy`, confusion matrix
- [x] Retrieval suite: dataset (~20), target, `recall_at_k` / `hit_at_1` / `reciprocal_rank`
- [x] `--suite` flag in `run_eval.py`
- [x] Tests

## Milestone 3 — harder e2e golden set
- [x] `seed_eval_orders`, `reset_eval_db` raises on failure, per-example reset in target
- [x] `final_state` snapshot + `state_accuracy` evaluator
- [x] New cases: real refunds, adversarial, out-of-stock, multi-turn (`history`)
- [x] Tests

## Milestone 4 — robustness
- [x] `sync_dataset` upsert (experiments preserved) + `--dry-run`
- [x] `breakdown_by` per-agent report
- [x] Tests

## Wrap-up
- [x] pytest + ruff check + ruff format --check
- [x] Real runs: push datasets, supervisor, retrieval, e2e v1 + v2; sanity-check results
- [x] README, CLAUDE.md, `.env.example`, `tasks/lessons.md`
- [x] Diff review

## Follow-up: screenshot, README, test grouping
- [x] Refresh LangSmith screenshot (34-query v1 vs v2)
- [x] README: test cases with links, "How the evals are tested", numbers match screenshot
- [x] Comments on every golden case; eval tests regrouped into tests/evals (scoring, golden sets, infra)
