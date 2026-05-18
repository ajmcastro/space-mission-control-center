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
- **Event bus** — `InMemoryEventBus` by default; `USE_REDIS=true` activates `RedisStreamBus`; broadcast pub-sub: each `subscribe()` call gets its own independent queue so multiple concurrent consumers (WebSocket forwarder, DB persist listener) all receive every event without stealing from each other
- **Planning** — A* (`astar.py`), greedy RL value-function (`rl_planner.py`), multi-agent objective distribution (`multi_agent_planner.py`)
- **Physics** — elevation map per environment, slope-adjusted movement cost, temperature-aware anomaly probability
- **Explainability** — structured logs + Claude API streaming SSE (`ANTHROPIC_API_KEY` optional)
- **Frontend tabs** — Map (2D SVG) · Telemetry (filter by rover/type, paginated 50/page, up to 2 000 events, colour-coded event badges) · Charts · Timeline · Explain (command-type filter, 30-step pagination, battery cost column, non-MOVE step highlighting, Claude SSE analysis) · 3D (React Three Fiber) · Anomalies (full history, sort + filter)

### V1 constraints still in force
- All 5 services run in **one FastAPI process**. Do not split into microservices without discussion.
- SQLite is the default `DATABASE_URL`. PostgreSQL is activated by env var.
- The event bus abstraction must be preserved — never call between services directly.

### V4 (in progress)
- **Fog of War** — `Cell.revealed` field; `Grid.reveal_around()` reveals cells in a Chebyshev radius; simulation service reveals cells on spawn and after every move; `CELLS_REVEALED` event published on the bus; frontend polls environment every 2s; 2D and 3D maps render fogged cells as uniform dark blocks; objectives visible as uncharted markers in fog; `FOG_OF_WAR=false` disables globally
- **Fault Protection System** — `FaultProtectionEngine` in `services/simulation_service/fault_protection.py`; called after every anomaly in `_run_plan_loop`; decision table maps anomaly type + streak to CONTINUE / RETRY / REVERSE / REPLAN / SAFE_MODE; `RoverState.SAFE_MODE` added (cyan in UI); safe-mode reason shown in rover panel; anomaly resolution endpoint exits safe mode and resets rover to IDLE; configurable via `FPS_*` env vars
- **Dynamic Terrain Events** — `TerrainEventEngine` in `services/simulation_service/terrain_events.py`; called every sim step; geyser eruption/dormancy cycles (`TERRAIN_GEYSER_*`); ice fracture propagation (`TERRAIN_FRACTURE_PROB_PER_TICK`); Enceladus day/night frost cycle (`TERRAIN_FROST_*`); `Cell.geyser_active` field; `Environment.sim_tick` and `Environment.is_night`; FPS auto-replans on path-blocking terrain changes; 2D/3D maps show dormant geyser colour, frost overlay, and day/night status bar
- **Telemetry richness** — executor emits correct `TelemetryType` per command type (POSITION / SAMPLE_COLLECTED / STATE_CHANGE / HEARTBEAT / COMMAND_ACK); `_event_persist_listener` in `main.py` subscribes to all three bus streams (telemetry, anomaly, mission) and persists anomaly, FPS, terrain, and lifecycle events to the DB so they appear in the Telemetry tab alongside position rows; skips noisy TELEMETRY_EMITTED / CELLS_REVEALED / ROVER_MOVED events
- **Explain tab & Claude context** — `_build_llm_context()` enriched: full step sequence (MOVE runs compressed, non-MOVE steps with target/cost/rationale), objectives with completion status, command-type breakdown, night-cycle state; system prompt updated for bullet-point analysis; Explain tab UI: command-type filter, 30-step pagination, battery cost column, non-MOVE step highlighting
- **Objective completion bug fix** — terrain-replan block in `_run_plan_loop` was missing `continue`, causing `idx += 1` to skip `pending[0]` after every terrain replan (manifested as `return_to_base` not being marked when the new plan had only one step); added `continue`; also added post-loop final objective check as a safety net
- **Science Value Map** — `Cell.science_value: float` field; `compute_science_scores(grid)` in `core/models/environment.py` computes per-cell scores from geyser proximity (Chebyshev decay, max 5.0), ice-water interface bonus (ICE adjacent to geyser, +3.0), and crater proximity (+2.0/+0.75); scores computed at environment generation time (`store.py`) and recomputed after every geyser eruption/dormancy event in `terrain_events.py`; `MultiAgentCoordinator.plan_all()` gains `optimize_science: bool` — when `True` uses science ROI (science_value / battery_cost) instead of travel cost for assignment; `MultiAgentPlanRequest` gains `optimize_science` field; metadata tag `"coordinator"` set to `"greedy_science_roi"` or `"greedy_distance"`; `GET /api/v1/planning/environments/{id}/science-heatmap` exposes raw scores; `GridMap` gains `showScienceOverlay` prop (teal→amber heat gradient); "Science overlay" toggle and "Maximize science" checkbox in MissionView

### Possible future work
- Trained neural policy for `RLPlanner` (swap `_value()` — no other changes needed).
- Per-mission environment editing (add/remove terrain features via the UI).
- Physics-based terrain simulation (momentum, wind, geyser pressure).
