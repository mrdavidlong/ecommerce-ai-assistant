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

### Backend — Layered FastAPI + SQLAlchemy

```
backend/app/
├── db/base.py       ← TimestampMixin + Base (all models inherit from Base)
├── db/session.py    ← engine, SessionLocal, get_db dependency
├── db/seed.py       ← idempotent startup seed (3 users)
├── models/          ← SQLAlchemy ORM models
├── schemas/         ← Pydantic v2 request/response models
├── services/        ← business logic (no FastAPI dependencies)
├── routers/         ← FastAPI route handlers (thin, delegate to services)
└── main.py          ← app factory, lifespan, CORS, router registration
```

**Base model**: Every ORM model inherits `Base` from `app/db/base.py`, which provides `id` (UUID, auto-generated), `created_at` (UTC), and `updated_at` (UTC, auto-updated on change). Never define these manually on a model.

**Startup lifecycle**: `main.py` uses a `lifespan` async context manager. On startup it calls `Base.metadata.create_all` (no drop — safe to restart) then `seed_database()`. The seed is idempotent: it checks `db.query(User).count() > 0` and returns immediately if data exists.

**Testing**: Tests use a separate `test.db`. The `conftest.py` overrides `get_db` via `app.dependency_overrides` so all HTTP requests in tests hit the test database. The lifespan seed runs against the real engine (not the override), so tests must seed data directly using the `db` fixture.

### Frontend — Next.js App Router

```
frontend/src/
├── app/             ← Next.js pages (all "use client" — no server components in auth flow)
├── components/      ← presentational components (no auth logic)
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
