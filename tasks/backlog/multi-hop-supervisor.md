# Backlog: multi-hop supervisor (specialists report back before the reply)

**Status:** not started

## Problem

The v2 graph is single-hop. The supervisor routes once, the chosen specialist runs, and its answer
goes straight to the user:

```python
# backend/app/agent/v2/graph.py
for node in ("product_agent", "account_agent", "cart_agent", "general_agent"):
    builder.add_edge(node, END)
```

The supervisor never sees what the specialist did, so it cannot:

- serve messages with more than one intent ("add the webcam and check my balance" only gets one half answered)
- notice a weak or failed specialist answer and route to a different specialist
- chain specialists, e.g. account (check the balance) then product (find what the user can afford)

## Goal

After a specialist finishes, control goes back to the supervisor. The supervisor reviews the
specialist's result, then either routes to another specialist or finishes and sends the response
to the user.

```
supervisor ──► specialist ──► supervisor ──► specialist ──► supervisor ──► END
```

## Proposed design

1. **Edges:** replace `add_edge(node, END)` with `add_edge(node, "supervisor_agent")` for every
   specialist.
2. **Finish route:** add `"finish"` to `SupervisorDecision.route` in `agent/v2/state.py` and map it
   to `END` in `add_conditional_edges`.
3. **Supervisor prompt:** tell it to review the latest specialist output, list which intents in the
   user's message are still unserved, and pick `finish` only when all are served. On the first hop
   it behaves as it does today.
4. **Loop guard:** add a hop counter to `ShoppingState` that is reset per request. Force `finish`
   past a named limit (e.g. `MAX_SPECIALIST_HOPS = 3`) and also set LangGraph's `recursion_limit`
   in the invoke config as a backstop.
5. **Final response:** today `extract_last_response` takes the last AI message. With several hops
   the reply has to cover every specialist's work. Decide between:
   - a supervisor "finish" step that writes a combined answer (one more LLM call, best UX), or
   - joining the specialist answers (cheaper, but reads poorly).
6. **`agent_name`:** it is a single string today and powers the "Handled by" badge. It becomes a
   list (or the last specialist), which affects `ChatResponse`, the frontend `AgentBadge`, and the
   `routing_accuracy` evaluator.
7. **Steps / Thinking UI:** each supervisor hop appends a routing step; check the accordion still
   reads clearly with several hops.

## Tradeoffs

- At least one extra supervisor LLM call on every turn, even single-intent ones, because the
  supervisor must confirm `finish`. That adds roughly the supervisor's latency (~0.9s p50 today)
  and its token cost. Mitigation: let a specialist mark its answer final for clearly single-intent
  routes, or skip the review hop when the first decision had one intent.
- A risk of routing loops (supervisor ping-pongs between specialists), handled by the hop guard.
- Side effects run once per hop: a refund or cart change must not repeat if the supervisor
  re-routes to the same specialist.

## Acceptance criteria

- Multi-intent cases in the supervisor golden set (`backend/evals/component_datasets.py`) and
  e2e set are fully served: both intents appear in the reply and in `final_state`.
- Single-intent e2e scores stay at or above the current v2 baseline (see README "v1 vs v2 results").
- Latency and cost increase measured with `uv run python -m evals.run_eval --version v2` and
  recorded in the README.
- Unit tests: hop limit forces `finish`; `finish` on the first hop ends the graph; a two-intent
  message visits two specialists in order.
- README section "One specialist per turn: control never returns to the supervisor" rewritten to
  describe the new flow.
