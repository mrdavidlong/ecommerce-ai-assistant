# Backlog: scope and bound the context each v2 agent receives

**Status:** not started

## Problem

Every v2 agent gets the whole session's `state["messages"]`, unfiltered and untrimmed. That
includes raw tool calls and `ToolMessage` output from every earlier turn
(see README "How context is passed from the supervisor to a specialist"):

```python
# supervisor.py
router_llm.invoke([SystemMessage(content=_SYSTEM)] + state["messages"])
# product.py / account.py / cart.py
agent.invoke(state)
# general.py
llm.invoke([SystemMessage(content=_SYSTEM)] + state["messages"])
```

As a result:

- prompt tokens grow every turn, and every LLM call in the turn resends them (the supervisor call
  plus each specialist tool-loop iteration), so cost and latency rise with session length
- a long session would eventually hit the model's context limit, and nothing handles that
- the supervisor reads raw tool JSON it doesn't need for routing
- the supervisor's `reasoning` never reaches the specialist

## Phase 1: cheap, deterministic wins

1. **Supervisor view.** Pass the supervisor only `HumanMessage`s and final assistant replies
   (an `AIMessage` with no `tool_calls`), not tool traffic. Put the filter in a small shared helper.
2. **Token budget.** Apply `trim_messages` (langchain-core, already installed) to the messages each
   agent sends to the model, with a named budget constant (e.g. `MAX_CONTEXT_TOKENS`). Cut only on
   turn boundaries so a `ToolMessage` is never separated from the `AIMessage` that requested it,
   or OpenAI rejects the request. For `create_agent` specialists this needs middleware or a
   pre-trimmed copy of the state, not a change to the stored thread.
3. **Measure.** Add a long multi-turn e2e case (8+ turns that refer back to early facts) and compare
   prompt tokens, latency, and scores before and after.

## Phase 2: richer handoff (pairs with `multi-hop-supervisor.md`)

4. **Handoff brief.** Today the supervisor passes only a route label (`SupervisorDecision.route` →
   `state["agent_name"]`), and its `reasoning` goes only to the Thinking UI. Add a `task` field to
   `SupervisorDecision`, store it in `ShoppingState`, and inject it into the specialist's prompt
   (e.g. as a `SystemMessage` after the specialist's own prompt). The specialist gets the brief
   plus the latest N turns instead of the full thread. Keep `route` as a `Literal` so the graph
   mapping and the "Handled by" badge don't change. Add an eval that checks the brief keeps the
   entities the specialist needs (order ID, product name).
5. **Structured memory (only if needed).** Keep referenced entities such as `referenced_order_ids`
   and `last_viewed_products` in `ShoppingState` so follow-ups still resolve after old tool output is
   trimmed.
6. **Summarization (only if real sessions run long).** `SummarizationMiddleware` on `create_agent`,
   behind a token threshold.

## Tradeoffs to watch

- Trimming and filtering can break references to earlier turns ("refund the second one"). The
  multi-turn evals must cover this before shipping.
- A brief or summary adds LLM work and can lose or change facts. Prefer the deterministic options
  (filtering, trimming, structured state) first.

## Acceptance criteria

- Supervisor route accuracy is unchanged or better on the supervisor suite (currently 50/51).
- e2e v2 scores stay at or above the current baseline, including multi-turn and refund cases.
- Prompt tokens per request stop growing past the budget in the long-session case; report the
  before/after numbers in the README.
- Unit tests: the supervisor filter drops tool messages and keeps human/final replies; trimming
  never leaves an orphaned `ToolMessage`; the budget boundary is respected for empty, single-turn
  and over-budget histories.
