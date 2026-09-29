# Lessons

Patterns to avoid, added after corrections. Review at session start.

## Check before claiming state, and before destructive calls
- I said "no experiments are attached" without checking, then re-pushed a LangSmith dataset. Deleting a
  dataset deletes its experiments, so the user's v1-vs-v2 comparison was lost.
- Rule: before any delete/recreate of a remote resource, list what depends on it and confirm. Prefer
  upsert (`evals/sync.py`) over delete/recreate.

## Don't label things "stale" from a partial read
- I called "21-query" stale when only CLAUDE.md's "25" was wrong. Verify each claim against the source
  (the dataset itself) before editing docs.

## Labels are hypotheses, not ground truth
- Two refund examples expected `process_item_refund` first; both agents legitimately looked up the order
  history first. Read the trace before deciding whether a miss is an agent bug or a label mistake, and
  prefer outcome checks (`state_accuracy`) over prescribing the path.
- Exact-substring facts break on inflection ("Wireless Mice" vs "Wireless Mouse"); use the shortest
  stable token.

## Report evidence, not assumptions
- README claims must match the runs: a miss seen in one run must not be described as repeated, and
  causes (e.g. "longer answers") need a trace behind them.
- LangSmith aggregate stats lag or stick; compute overall numbers from per-run feedback instead.
