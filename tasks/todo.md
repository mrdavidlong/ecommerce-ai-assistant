# Eval: doc fixes + response-quality evaluators

## Milestone 1 — doc drift
- [x] Fix false "built-in evaluators wired" docstring in `backend/evals/evaluators.py`
- [x] Fix "25-query" -> "21-query" in `CLAUDE.md`

## Milestone 2 — evaluators
- [x] List test cases (see plan) then write `backend/tests/test_evaluators.py`
- [x] Add `expected_facts` to golden set in `backend/evals/dataset.py`
- [x] Add `factual_accuracy` evaluator
- [x] Add `helpfulness` LLM-judge evaluator (`JUDGE_MODEL` env, defaults to `LLM_MODEL`)
- [x] Wire both into `backend/evals/run_eval.py`
- [x] Document `JUDGE_MODEL` in `CLAUDE.md`
- [x] pytest + ruff check + ruff format --check
- [x] Real eval run sanity check (needs API keys) and diff review
