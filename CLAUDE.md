# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Backend (`cd backend` first)
```bash
uv sync --extra dev          # install dependencies
uv run uvicorn app.main:app --reload  # start dev server (http://localhost:8000)
uv run pytest tests/ -v      # run all tests
uv run pytest tests/test_users.py::test_get_user_by_id_returns_correct_user -v  # run single test
uv run ruff check .          # lint
uv run ruff check . --fix    # auto-fix lint issues
uv run ruff format .         # format

# Evaluation (requires LANGSMITH_API_KEY in .env)
uv run python -m evals.dataset          # push 25-query dataset to LangSmith (one-time)
uv run python -m evals.run_eval --version v1   # baseline single-agent eval
uv run python -m evals.run_eval --version v2   # multi-agent eval
```

### Frontend (`cd frontend` first)
```bash
npm install                  # install dependencies
npm run dev                  # start dev server (http://localhost:3000)
npm run build                # production build
npm run check                # TypeScript type check + ESLint
npm run lint                 # ESLint only
```

## Architecture

### API Versioning

Only the chat endpoint is versioned. All other endpoints are shared:

```
POST /v1/chat    ← single-agent (LangChain ReAct, run_agent_v1)
POST /v2/chat    ← multi-agent  (LangGraph star topology, run_agent_v2)  ← frontend uses this

GET  /users/, /users/{id}
GET  /products/, /products/{id}
POST /orders/, GET /orders/, POST /orders/{id}/refund
```

### Backend — Layered FastAPI + SQLAlchemy

```
backend/app/
├── agent/
│   ├── shared/
│   │   ├── rag.py       ← ChromaDB singleton + embed_products/search_products_rag (shared)
│   │   └── tools.py     ← make_tools(): 8 LangChain @tool closures (shared by v1 + v2)
│   ├── v1/
│   │   └── agent.py     ← run_agent_v1(): single LangChain ReAct agent
│   └── v2/
│       ├── state.py     ← ShoppingState TypedDict + SupervisorDecision Pydantic model
│       ├── graph.py     ← LangGraph StateGraph + build_graph() with MemorySaver
│       ├── agent.py     ← run_agent_v2(): thin wrapper over graph
│       └── agents/
│           ├── supervisor.py  ← routing node using llm.with_structured_output()
│           ├── product.py     ← search_products, compare_products, get_affordable_products
│           ├── account.py     ← get_user_balance, get_order_history, process_refund
│           ├── cart.py        ← add_to_cart, remove_from_cart, search_products (fallback)
│           ├── general.py     ← plain LLM, no tools — greetings, policy, chitchat
│           └── _steps.py      ← extract_steps() shared utility
├── db/base.py       ← TimestampMixin + Base (all models inherit from Base)
├── db/session.py    ← engine, SessionLocal, get_db dependency
├── db/seed.py       ← idempotent startup seed (3 users, 8 products)
├── models/          ← SQLAlchemy ORM models
├── schemas/         ← Pydantic v2 request/response models (ChatResponse has agent_name field)
├── services/        ← business logic (no FastAPI dependencies)
├── routers/
│   ├── chat_v1.py   ← POST /v1/chat — calls run_agent_v1, maintains _history dict
│   ├── chat_v2.py   ← POST /v2/chat — calls run_agent_v2, returns agent_name
│   ├── users.py, products.py, orders.py
└── main.py          ← app factory, lifespan, CORS, router registration

backend/evals/
├── dataset.py       ← 25-query LangSmith dataset (push once)
├── evaluators.py    ← routing_accuracy + tool_accuracy custom evaluators
└── run_eval.py      ← CLI runner: --version v1|v2
```

**Base model**: Every ORM model inherits `Base` from `app/db/base.py`, which provides `id` (UUID, auto-generated), `created_at` (UTC), and `updated_at` (UTC, auto-updated on change). Never define these manually on a model.

**Startup lifecycle**: `main.py` uses a `lifespan` async context manager. On startup it calls `Base.metadata.create_all` (no drop — safe to restart) then `seed_database()`. The seed is idempotent: it checks `db.query(User).count() > 0` and returns immediately if data exists. Then embeds products into ChromaDB via `embed_products()`.

**Testing**: Tests use a separate `test.db`. The `conftest.py` overrides `get_db` via `app.dependency_overrides` so all HTTP requests in tests hit the test database. Tests mock `run_agent_v1` at the router boundary — no real LLM calls. All tests POST to `/v1/chat/`.

**LangSmith**: Set `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`, and `LANGCHAIN_TRACING_V2=true` in `.env` to enable automatic tracing of every graph invocation.

### Multi-Agent Architecture (v2) — LangGraph Star Topology

```
User Message → [Supervisor] → routes to → [Product | Account | Cart | General] → END
```

- **Supervisor**: `llm.with_structured_output(SupervisorDecision)` — classifies intent, no tool calls
- **Product**: search_products, compare_products, get_affordable_products
- **Account**: get_user_balance, get_order_history, process_refund
- **Cart**: add_to_cart, remove_from_cart, search_products (for name resolution)
- **General**: plain LLM, no tools — handles greetings and store policy

The supervisor routing step is returned in the `steps` list so the frontend "Thinking" accordion shows which specialist handled the query. The `agent_name` field in `ChatResponse` powers the "Handled by: Product Specialist" badge.

### Frontend — Next.js App Router

```
frontend/src/
├── app/             ← Next.js pages (all "use client" — no server components in auth flow)
├── components/      ← presentational components (no auth logic)
│   └── ChatWidget.tsx  ← posts to /v2/chat/, shows AgentBadge + StepsAccordion
├── lib/auth.ts      ← all localStorage session logic (getCurrentUser, setCurrentUser, clearCurrentUser)
└── styles/          ← globals.css (Tailwind import only)
```

**Auth flow**: Session stored in `localStorage["current_user"]` as `{ id, name }`. `getCurrentUser()` includes an SSR guard (`typeof window === "undefined"`) — always use this function, never access localStorage directly. The dashboard returns `null` before the auth check resolves to prevent a flash of unauthenticated content. Redirects use `router.replace("/")` (not `push`) so the back button doesn't re-enter the dashboard.

**Path alias**: Use `~/` for imports from `src/` (e.g. `~/lib/auth`, `~/components/UserLoginCard`).

**API base URL**: Hardcoded as `http://localhost:8000` in page components. Change in one place per page for now; extract to an env var when needed.

## Adding a New Model

1. Create `backend/app/models/your_model.py` — inherit from `Base`, do not define `id`/`created_at`/`updated_at`
2. Create `backend/app/schemas/your_model.py` — `YourModelBase`, `YourModelCreate`, `YourModelRead` (with `ConfigDict(from_attributes=True)`)
3. Create `backend/app/services/your_model_service.py` — pure functions taking `db: Session`
4. Create `backend/app/routers/your_model.py` — thin handlers delegating to service
5. Register the router in `app/main.py` with `app.include_router(...)`

## Adding a New Specialist Agent (v2)

1. Create `backend/app/agent/v2/agents/your_agent.py` — follow the pattern in `product.py`
2. Pick the tools it needs from `agent/shared/tools.py`; filter by name in `make_your_node()`
3. Add a new node in `agent/v2/graph.py` and wire it with `add_node` + `add_edge`
4. Add the new route literal to `SupervisorDecision` in `agent/v2/state.py`
5. Update the supervisor system prompt in `agent/v2/agents/supervisor.py`
