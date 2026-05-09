# CLAUDE.md — Agent Instructions for Enceladus Mission Control

This file tells Claude Code how to work in this repository. Read it before making any changes.

---

## Project Layout

```
space-missions-control-center/
├── backend/          Python / FastAPI (uv-managed)
├── frontend/         React + TypeScript (npm / Vite)
├── infra/            Docker Compose stack
├── Makefile          All developer commands (single source of truth)
├── README.md         Human-facing documentation
└── CLAUDE.md         This file
```

---

## Mandatory Documentation Rule

**After every change that affects developer workflow, update the relevant docs before considering the task done.**

| What changed | What to update |
|---|---|
| New `make` target or modified command | `Makefile` + the "Make Targets" table in `README.md` |
| New backend dependency (`uv add`) | `backend/pyproject.toml` (automatic) + Prerequisites table in `README.md` if it's a new tool |
| New frontend dependency (`npm install`) | `frontend/package.json` (automatic) + Prerequisites if it adds a new tool |
| New API endpoint | `README.md` → Key Endpoints table |
| New environment variable / config key | `backend/.env.example` + Configuration table in `README.md` |
| New service or major module | `README.md` → Project Structure tree + Service Responsibilities table |
| New domain model | `README.md` → Domain Models table |
| New anomaly type | `README.md` → Anomaly System table |
| New planner type | `README.md` → Development → Adding a new planner |
| Roadmap item completed | `README.md` → Roadmap (move `[ ]` to `[x]`) + update CLAUDE.md current state |
| New future work planned | `README.md` → Roadmap + CLAUDE.md → Possible future work |
| New Make target added | `README.md` → Make Targets section |
| Dev workflow changes | `README.md` → Quick Start or Development sections |

Docs-only fixes (typos, clarifications) do not require code changes.

---

## Package Management

### Backend — always use `uv`, never `pip`

```bash
# Add a dependency
cd backend && uv add <package>

# Add a dev-only dependency
cd backend && uv add --dev <package>

# Sync environment from lock file (after git pull)
cd backend && uv sync

# Run anything in the managed venv
cd backend && uv run <command>
```

Do NOT use `pip install`, `pip freeze`, `pipenv`, or `poetry`.

### Frontend — use `npm`

```bash
cd frontend && npm install <package>
cd frontend && npm run dev | build | lint
```

---

## Running the Project

Always use `make` targets from the project root — they encode the correct paths and flags.

```bash
make env-check      # verify tools are installed
make install        # uv sync + npm install
make dev            # start backend + frontend
make test           # run all backend tests
make docker-up      # start full Docker stack
make help           # full target list
```

Never run backend commands outside the `backend/` directory — `uv` resolves the venv from `pyproject.toml` location.

---

## Code Conventions

### Python (backend)

- **Strong typing everywhere** — all function signatures must have type annotations.
- **Pydantic v2** for all domain models (`model_dump`, `model_validate`, `@computed_field`).
- **Async-first** — all service methods and FastAPI handlers must be `async def`.
- **No comments unless the WHY is non-obvious** — well-named identifiers are documentation.
- **No print() statements** — use `structlog` (`log = structlog.get_logger(__name__)`).
- All new services get a `router.py` (FastAPI), `service.py` (business logic), and optionally `schemas.py` (request models) and `store.py` (persistence).
- New routers must be registered in `main.py` under `app.include_router(...)` with `prefix="/api/v1"`.

### TypeScript (frontend)

- **Strict mode** — `tsconfig.json` has `"strict": true`, honour it.
- All API types live in `src/types/index.ts` — mirror backend Pydantic models.
- Data fetching uses **React Query** hooks in `src/hooks/`.
- Global state uses **Zustand** in `src/store/missionStore.ts`.
- Direct API calls belong in `src/services/api.ts`, not in components.

---

## Testing

```bash
make test           # all tests
make test-unit      # unit only (fast, no server)
make test-api       # API integration (starts app lifespan)
make test-verbose   # with full output
```

- Every new service method needs at least one test.
- Every new API endpoint needs at least one integration test in `tests/test_mission_api.py`.
- New pathfinding or simulation logic goes in `tests/test_astar.py` or `tests/test_simulation.py`.
- Tests use `pytest-asyncio` in `asyncio_mode = "auto"`.
- API tests trigger the FastAPI lifespan via `app.router.lifespan_context(app)`.

---

## Event Bus

All rover actions, telemetry, and mission lifecycle events must go through the `EventBus`, never via direct function calls between services.

```python
await self._bus.publish(MissionEvent(
    type=EventType.SOME_EVENT,
    stream=settings.some_stream,
    mission_id=mission.id,
    payload={...},
))
```

The bus is `InMemoryEventBus` in V1. Do **not** hard-code Redis anywhere — use `settings.redis_url` and the abstraction in `core/events/`.

---

## Adding a New Feature — Checklist

1. **Domain model** — add/extend in `core/models/`, re-export from `core/models/__init__.py`, mirror type in `frontend/src/types/index.ts`.
2. **Service logic** — `services/<name>_service/service.py`.
3. **API endpoint** — `services/<name>_service/router.py`, register in `main.py`.
4. **Dependency** — add to `api/deps.py` if a new service singleton is needed.
5. **Test** — at minimum one unit test + one API test.
6. **Makefile** — add a target if the feature introduces a new dev command.
7. **README** — update every table that applies (see Mandatory Documentation Rule above).
8. **`.env.example`** — add any new config keys with sensible defaults.

---

## V1 Constraints (do not violate without discussion)

- State lives **in-memory** (dicts, registries, ring buffers). No DB writes in V1.
- The event bus is `InMemoryEventBus`. Swapping to Redis is a one-line change in `main.py`.
- All 5 services run in **one FastAPI process**. Do not split into microservices yet.
- SQLite is the default `DATABASE_URL`. PostgreSQL is activated by env var.

---

## Current Architecture State (V3 complete)

All V1, V2, and V3 features are shipped. The system runs as a single FastAPI process with SQLite (dev) or PostgreSQL (prod).

### What is in production
- **Persistence** — SQLAlchemy async ORM + Alembic migrations (`core/db_models/`, `core/repositories/`)
- **Event bus** — `InMemoryEventBus` by default; `USE_REDIS=true` activates `RedisStreamBus`
- **Planning** — A* (`astar.py`), greedy RL value-function (`rl_planner.py`), multi-agent objective distribution (`multi_agent_planner.py`)
- **Physics** — elevation map per environment, slope-adjusted movement cost, temperature-aware anomaly probability
- **Explainability** — structured logs + Claude API streaming SSE (`ANTHROPIC_API_KEY` optional)
- **Frontend tabs** — Map (2D SVG) · Telemetry · Charts · Timeline · Explain (Claude) · 3D (React Three Fiber) · Anomalies (full history, sort + filter)

### V1 constraints still in force
- All 5 services run in **one FastAPI process**. Do not split into microservices without discussion.
- SQLite is the default `DATABASE_URL`. PostgreSQL is activated by env var.
- The event bus abstraction must be preserved — never call between services directly.

### Possible future work
- Trained neural policy for `RLPlanner` (swap `_value()` — no other changes needed).
- Per-mission environment editing (add/remove terrain features via the UI).
- Physics-based terrain simulation (momentum, wind, geyser pressure).
