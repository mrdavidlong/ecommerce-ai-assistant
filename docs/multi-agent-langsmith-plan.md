# Capstone Upgrade Plan: Multi-Agent Ecommerce AI Assistant

## Context

The project is a working single-agent ecommerce chatbot (LangChain ReAct + GPT-4o + ChromaDB RAG + FastAPI + Next.js). The goal is to upgrade it to score maximum points on the BYOP capstone rubric by adding: LangGraph multi-agent architecture, LangSmith observability + evaluation, structured outputs, and minor UX/documentation polish.

The upgrade keeps v1 (single-agent) running alongside v2 (multi-agent) via separate `/v1/chat` and `/v2/chat` endpoints. All 8 tools and the RAG system are preserved and shared between both versions.

---

## Rubric Summary (100 pts)

| Category | Points | Key Requirement |
|---|---|---|
| Problem Definition & Use Case | 20 | Clear problem, user personas, measurable success metrics |
| Agentic Design & Architecture | 25 | Multi-agent decomposition, orchestration, modularity |
| Quality, Grounding & Reliability | 20 | RAG, structured outputs, guardrails/validation |
| Evaluation, Iteration & Improvement | 15 | Test dataset, metrics, before/after improvement evidence |
| Technical Implementation | 10 | Tool integration, error handling |
| UX & Decision Support | 5 | Intuitive interface, reasoning visible |
| Documentation & Delivery | 5 | Architecture docs, clear demo |

---

## Final Folder Structure

```
backend/
├── app/
│   ├── agent/
│   │   ├── shared/
│   │   │   ├── rag.py          ← ChromaDB (moved from agent/rag.py, shared by v1+v2)
│   │   │   └── tools.py        ← all 8 tools (moved from agent/tools.py, shared by v1+v2)
│   │   ├── v1/
│   │   │   └── agent.py        ← current single LangChain ReAct agent (run_agent_v1)
│   │   └── v2/
│   │       ├── state.py        ← ShoppingState TypedDict + SupervisorDecision Pydantic model
│   │       ├── graph.py        ← LangGraph StateGraph + build_graph()
│   │       ├── agent.py        ← run_agent_v2() thin wrapper
│   │       └── agents/
│   │           ├── __init__.py
│   │           ├── supervisor.py   ← routing node, structured output
│   │           ├── product.py      ← search, compare, affordable tools
│   │           ├── account.py      ← balance, order history, refund tools
│   │           ├── cart.py         ← add/remove_from_cart + search fallback
│   │           └── general.py      ← plain LLM, no tools
│   ├── routers/
│   │   ├── chat_v1.py          ← POST /v1/chat (replaces chat.py)
│   │   ├── chat_v2.py          ← POST /v2/chat
│   │   ├── users.py            ← unchanged
│   │   ├── products.py         ← unchanged
│   │   └── orders.py           ← unchanged
│   ├── schemas/
│   │   └── chat.py             ← add agent_name field to ChatResponse
│   ├── db/                     ← unchanged
│   ├── models/                 ← unchanged
│   ├── services/               ← unchanged
│   └── main.py                 ← register v1/v2 routers with prefixes
├── evals/
│   ├── __init__.py
│   ├── dataset.py              ← 25 test cases + LangSmith dataset push
│   ├── evaluators.py           ← routing_accuracy, tool_accuracy, faithfulness, helpfulness
│   └── run_eval.py             ← CLI: uv run python -m evals.run_eval --version v1|v2
└── pyproject.toml              ← add langgraph, langgraph-checkpoint, langsmith

frontend/
└── src/components/
    └── ChatWidget.tsx          ← add agentName display + AgentBadge component

docs/
├── multi-agent-langsmith-plan.md   ← this file
├── capstone_rubric.md              ← extracted rubric content
├── architecture.md                 ← system diagram, agent roles, data flow (to create)
└── evaluation_results.md           ← v1 vs v2 comparison table + LangSmith screenshots (to create)
```

---

## API Design

Only the chat endpoint is versioned — all other endpoints are shared and unversioned:

```
POST /v1/chat    ← single-agent (LangChain ReAct)
POST /v2/chat    ← multi-agent (LangGraph)

GET  /users/
GET  /users/{user_id}
GET  /products/
GET  /products/{product_id}
POST /orders/
GET  /orders/
POST /orders/{order_id}/refund
```

`main.py` registration:
```python
app.include_router(chat_v1_router, prefix="/v1")
app.include_router(chat_v2_router, prefix="/v2")
app.include_router(users_router)    # no prefix
app.include_router(products_router)
app.include_router(orders_router)
```

---

## Multi-Agent Architecture (v2): LangGraph Star Topology

```
User Message
     │
[Supervisor Node]  ← llm.with_structured_output(SupervisorDecision)
     │
     ├─ "product"  → [ProductAgent]  search_products, compare_products, get_affordable_products
     ├─ "account"  → [AccountAgent]  get_user_balance, get_order_history, process_refund
     ├─ "cart"     → [CartAgent]     add_to_cart, remove_from_cart, search_products (fallback)
     └─ "general"  → [GeneralAgent]  plain LLM, no tools — greetings, policy, chitchat
                            │
                           END
```

**Why star topology**: cleanest demonstration of routing/decomposition; each agent has single responsibility; easy to explain in an interview; straightforward to extend with a new specialist node.

**Why LangGraph over plain LangChain**: explicit state graph = clean traces in LangSmith, native MemorySaver checkpointing (replaces the in-memory `_history` dict in `chat.py`), conditional routing is first-class.

---

## Key Implementation Details

### `agent/v2/state.py`

```python
class ShoppingState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    agent_name: str          # "product" | "account" | "cart" | "general"
    cart_actions: list[dict]
    steps: list[dict]

class SupervisorDecision(BaseModel):
    route: Literal["product", "account", "cart", "general"]
    reasoning: str           # shown in frontend "Thinking" accordion
```

### `agent/v2/agents/supervisor.py`

- Uses `llm.with_structured_output(SupervisorDecision)` — guaranteed JSON, no parsing code, Pydantic validates the `route` literal
- Does NOT call any tools — pure classification node
- Appends routing step to `steps` list so reasoning is visible in frontend

### `agent/v2/graph.py`

```python
builder = StateGraph(ShoppingState)
builder.add_node("supervisor", supervisor_node)
builder.add_node("product",    product_node)
builder.add_node("account",    account_node)
builder.add_node("cart",       cart_node)
builder.add_node("general",    general_node)
builder.set_entry_point("supervisor")
builder.add_conditional_edges("supervisor", lambda s: s["agent_name"], {
    "product": "product", "account": "account",
    "cart": "cart", "general": "general",
})
for node in ("product", "account", "cart", "general"):
    builder.add_edge(node, END)
return builder.compile(checkpointer=MemorySaver())
```

### `agent/v2/agent.py` — Thin Wrapper

```python
def run_agent_v2(db, user_id, message, session_id) -> tuple[str, list, list, str]:
    # drops `history` param — MemorySaver owns conversation state
    cart_actions = []
    graph = build_graph(llm, db, user_id, cart_actions)
    config = {"configurable": {"thread_id": session_id}}
    final_state = graph.invoke(initial_state, config)
    return response, steps, cart_actions, agent_name
```

### `schemas/chat.py` — Updated Response

```python
class ChatResponse(BaseModel):
    response: str
    steps: list[AgentStep]
    cart_actions: list[CartAction] = []
    agent_name: str = "unknown"    # NEW — which specialist handled the query
```

### `routers/chat_v1.py`

Rename existing `chat.py` → `chat_v1.py`. Update import paths for tools/rag to use `agent/shared/`. No logic changes.

### `routers/chat_v2.py`

Same schema as v1. Calls `run_agent_v2()`. No `_history` dict — MemorySaver handles session state via `session_id`.

---

## LangSmith Integration

**Already configured** — user has added keys to `backend/.env`.

Use **one LangSmith project** (`ecommerce-ai-assistant`) with experiment tags to differentiate v1 vs v2. LangSmith's "Compare Experiments" view shows metric deltas side-by-side.

```python
# In run_eval.py, tag runs per version:
config = {
    "configurable": {"thread_id": session_id},
    "metadata": {"version": "v2"},
    "tags": ["multi-agent", "v2"],
}
```

Zero additional code needed for tracing — LangChain/LangGraph picks up `LANGCHAIN_TRACING_V2=true` automatically.

---

## Evaluation Framework (`backend/evals/`)

### 25-Query Dataset

| Category | Count | Expected Agent |
|---|---|---|
| Product Search | 7 | product |
| Product Compare | 3 | product |
| Account/Balance | 4 | account |
| Budget Shopping | 2 | product |
| Refunds | 2 | account |
| Cart Management | 4 | cart |
| General/Chitchat | 3 | general |
| **Total** | **25** | |

### 4 Evaluators

| Evaluator | Type | Measures |
|---|---|---|
| `routing_accuracy` | Custom (0/1) | Did supervisor route to the correct specialist? |
| `tool_accuracy` | Custom (0/1) | Did specialist call the correct tool first? |
| `faithfulness` | LangSmith LLM judge | Is answer grounded in tool outputs, not hallucinated? |
| `helpfulness` | LangSmith LLM judge | Is the response useful and relevant? |

### Running Evals

```bash
# Push dataset to LangSmith (one-time)
cd backend && uv run python -m evals.dataset

# Run v1 baseline
uv run python -m evals.run_eval --version v1

# Run v2 multi-agent
uv run python -m evals.run_eval --version v2
```

Compare results in LangSmith → Experiments → Compare. Document in `docs/evaluation_results.md`.

---

## Frontend Changes (`ChatWidget.tsx`)

1. Add `agentName: string` to `Message` type and fetch handler
2. Add `AgentBadge` component: `"Handled by: Product Specialist"` shown above steps accordion
3. Supervisor routing step visible as first entry in "Thinking" accordion (shows reasoning)
4. Update header subtitle: `"Powered by GPT-4o · Multi-Agent + RAG"` (for v2 endpoint)
5. Toggle between v1/v2 endpoint via an env var or simple UI toggle for demo purposes

---

## Dependencies to Add

```bash
cd backend
uv add langgraph langgraph-checkpoint langsmith
```

---

## Implementation Sequence

### Step 0 — Docs (immediate)
- Extract xlsx rubric → `docs/capstone_rubric.md`

### Step 1 — Restructure agent directory (no behavior change)
- Move `agent/rag.py` → `agent/shared/rag.py`
- Move `agent/tools.py` → `agent/shared/tools.py`
- Move `agent/agent.py` → `agent/v1/agent.py`, rename `run_agent` → `run_agent_v1`
- Update all imports
- Run `uv run pytest tests/ -v` — all pass

### Step 2 — Rename chat router, add agent_name to schema
- Rename `routers/chat.py` → `routers/chat_v1.py`
- Update import prefix in `chat_v1.py` to use `agent/shared/` paths
- Add `agent_name: str = "unknown"` to `ChatResponse` in `schemas/chat.py`
- Update `main.py`: `app.include_router(chat_v1_router, prefix="/v1")`
- Run tests — all pass

### Step 3 — Build v2 agent layer
- Create `agent/v2/state.py`
- Create `agent/v2/agents/__init__.py`
- Create `agent/v2/agents/supervisor.py`
- Create `agent/v2/agents/product.py`
- Create `agent/v2/agents/account.py`
- Create `agent/v2/agents/cart.py`
- Create `agent/v2/agents/general.py`
- Create `agent/v2/graph.py`
- Create `agent/v2/agent.py` (`run_agent_v2`)

### Step 4 — Wire up v2 router
- Create `routers/chat_v2.py` calling `run_agent_v2`
- Register in `main.py`: `app.include_router(chat_v2_router, prefix="/v2")`
- Manual smoke test: `POST /v2/chat` with "find a webcam" → response includes `agent_name: "product"`

### Step 5 — Add dependencies
- `uv add langgraph langgraph-checkpoint langsmith`

### Step 6 — Evaluation framework
- Create `evals/__init__.py`, `evals/dataset.py`, `evals/evaluators.py`, `evals/run_eval.py`
- Push dataset to LangSmith
- Run v1 baseline eval; run v2 eval; capture comparison

### Step 7 — Frontend polish
- Update `ChatWidget.tsx`: add `AgentBadge`, `agentName` field, updated subtitle

### Step 8 — Documentation
- `docs/architecture.md` — system diagram, agent role table, data flow
- `docs/evaluation_results.md` — v1 vs v2 table + LangSmith screenshots

---

## Verification Checklist

- [ ] `uv run pytest tests/ -v` — all existing tests pass
- [ ] `POST /v1/chat` — works exactly as before
- [ ] `POST /v2/chat` with "find a webcam" → `agent_name: "product"` in response
- [ ] `POST /v2/chat` with "what's my balance?" → `agent_name: "account"`
- [ ] `POST /v2/chat` with "add webcam to cart" → `agent_name: "cart"`
- [ ] `POST /v2/chat` with "hello" → `agent_name: "general"`
- [ ] LangSmith dashboard shows traces for v2 runs with supervisor routing step visible
- [ ] `uv run python -m evals.run_eval --version v2` completes without errors
- [ ] LangSmith Experiments shows routing_accuracy, tool_accuracy, faithfulness, helpfulness metrics
- [ ] Frontend shows "Handled by: Product Specialist" badge on v2 responses
- [ ] Frontend "Thinking" accordion shows supervisor routing as first step
