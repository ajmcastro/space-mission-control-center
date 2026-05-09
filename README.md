# Enceladus Mission Control Center

A production-grade space mission control system simulating rover operations on Enceladus — Saturn's ocean moon. Features a physics-based digital twin simulation engine, A* and RL mission planning, multi-agent rover coordination, real-time telemetry streaming, anomaly detection, Claude-powered explanations, timeline playback, and a 3D terrain visualiser.

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                          Frontend (React + TS)                        │
│  Dashboard · Planner · Map (2D/3D) · Telemetry · Charts · Timeline  │
│  Explain (Claude SSE) · 3D · Anomalies · Multi-rover coordination    │
└───────────────────────────┬──────────────────────────────────────────┘
                            │ REST + WebSocket + SSE
┌───────────────────────────▼──────────────────────────────────────────┐
│                     FastAPI Backend (unified process)                 │
│                                                                       │
│  ┌─────────────────┐  ┌────────────────────────┐  ┌───────────────┐  │
│  │ mission_service │  │   planning_service      │  │ sim_service   │  │
│  │  CRUD + status  │  │  A* · RL · Multi-agent  │  │ physics-based │  │
│  │  elevation gen  │  │  Objective distribution  │  │ digital twin  │  │
│  └─────────────────┘  └────────────────────────┘  └───────────────┘  │
│                                                                       │
│  ┌─────────────────┐  ┌────────────────────────────────────────────┐ │
│  │telemetry_service│  │         explainability_service              │ │
│  │  WebSocket push │  │  Structured logs · Claude API streaming     │ │
│  │  Event history  │  │  Plan · Mission · Anomaly explain (SSE)     │ │
│  └─────────────────┘  └────────────────────────────────────────────┘ │
│                                                                       │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │                    Event Bus (abstract)                         │  │
│  │    InMemoryEventBus (default)  →  RedisStreamBus (USE_REDIS)   │  │
│  └────────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────────┘
                            │
            ┌───────────────┴───────────────┐
       ┌────▼────┐                     ┌────▼────┐
       │ Redis   │                     │Postgres │
       │ Streams │                     │  (opt.) │
       └─────────┘                     └─────────┘
```

### Domain Models

| Model | Description |
|---|---|
| `Mission` | Top-level mission container — status, objectives, rover list |
| `Objective` | Typed goal with target coordinates and priority |
| `Rover` | Digital twin — position, battery, state, path history |
| `Plan` | Ordered command sequence produced by a planner |
| `PlanStep` | Single command with battery cost estimate and rationale |
| `Command` | Typed action (MOVE, COLLECT_SAMPLE, WAIT, CHARGE, ABORT) |
| `TelemetryEvent` | Timestamped rover data snapshot |
| `Anomaly` | Detected failure with type, severity, and recovery hooks |
| `Environment` | Grid world — terrain, geysers, hazard zones, temperature, pressure |
| `Grid / Cell` | 2D terrain grid with per-cell movement cost and elevation |

### Service Responsibilities

| Service | Prefix | Responsibility |
|---|---|---|
| `mission_service` | `/api/v1/missions` | Mission CRUD, physics-based elevation terrain generation |
| `planning_service` | `/api/v1/planning` | A* pathfinding, RL value-function planner, multi-agent objective distribution |
| `simulation_service` | `/api/v1/simulation` | Rover spawn, physics-aware plan execution, anomaly injection |
| `telemetry_service` | `/api/v1/telemetry` | WebSocket push, event history, anomaly resolution |
| `explainability_service` | `/api/v1/explain` | Structured decision logs, Claude API streaming explanations (SSE) |

---

## Prerequisites

| Tool | Version | Install |
|---|---|---|
| Python | ≥ 3.12 | [python.org](https://python.org) |
| uv | ≥ 0.5 | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Node.js | ≥ 20 | [nodejs.org](https://nodejs.org) |
| Docker + Compose | any | [docker.com](https://docker.com) (optional) |

---

## Quick Start (Local Dev — No Docker)

### 1. Install prerequisites

| Tool | Version | Install |
|---|---|---|
| uv | ≥ 0.5 | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Node.js | ≥ 20 | [nodejs.org](https://nodejs.org) |

```bash
# Verify everything is available
make env-check
```

### 2. Install dependencies

```bash
make install
# Runs: uv sync (backend) + npm install (frontend)
# Also creates backend/.env from .env.example if missing
```

### 3. Start both servers

```bash
make dev
# Backend : http://localhost:8000  (API docs: /docs)
# Frontend: http://localhost:5173
```

Or start them separately in different terminals:

```bash
make dev-backend   # FastAPI with hot-reload
make dev-frontend  # Vite dev server
```

---

## Make Targets

All developer commands are available via `make`. Run `make help` for the full list.

| Target | Description |
|---|---|
| `make help` | Show all targets with descriptions |
| `make env-check` | Verify required tools are installed |
| `make install` | Install backend (uv) + frontend (npm) deps |
| `make dev` | Start backend + frontend in parallel |
| `make dev-backend` | FastAPI server with hot-reload |
| `make dev-frontend` | Vite dev server |
| `make test` | Run all backend tests (24 total) |
| `make test-verbose` | Tests with full output |
| `make test-unit` | Unit tests only (A* + simulation) |
| `make test-api` | API integration tests |
| `make lint` | Run ruff linter on backend |
| `make build` | Build frontend for production |
| `make docker-up` | Start full Docker stack (foreground) |
| `make docker-up-d` | Start full Docker stack (detached) |
| `make docker-down` | Stop containers |
| `make docker-down-v` | Stop containers + delete volumes |
| `make docker-logs` | Tail all container logs |
| `make docker-rebuild` | Rebuild images and restart |
| `make openapi-dump` | Dump OpenAPI spec to `openapi.json` |
| `make add-backend-dep PKG=x` | Add a backend package via uv |
| `make migrate` | Apply all pending Alembic migrations |
| `make migrate-create MSG="..."` | Generate a new migration from model changes |
| `make migrate-rollback` | Roll back one migration step |
| `make migrate-history` | Show full migration history |
| `make clean` | Remove build artefacts |
| `make clean-all` | Remove artefacts + venv + node_modules |

---

## Docker Compose (Full Stack)

```bash
make docker-up-d   # start detached

# Or directly:
docker compose -f infra/docker-compose.yml up -d
```

Services:
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- PostgreSQL: localhost:5432
- Redis: localhost:6379

```bash
make docker-down     # stop (keep volumes)
make docker-down-v   # stop + delete volumes
make docker-logs     # tail all logs
make docker-rebuild  # full rebuild
```

---

## Running Tests

```bash
make test           # all tests (24 total)
make test-verbose   # with full output
make test-unit      # A* + simulation unit tests (fast)
make test-api       # API integration tests

# Or directly from backend/:
cd backend && uv run pytest -v
```

---

## V1 Workflow (Manual)

The complete V1 workflow via the API (or use the UI):

```bash
BASE=http://localhost:8000/api/v1

# 1. Create a mission with objectives
MISSION=$(curl -s -X POST $BASE/missions/ -H "Content-Type: application/json" -d '{
  "name": "Alpha Geyser Survey",
  "description": "Investigate active geyser zone in grid sector Alpha",
  "grid_width": 20,
  "grid_height": 20,
  "objectives": [
    {"type": "reach_waypoint", "target_x": 8, "target_y": 6, "priority": 1},
    {"type": "collect_sample",  "target_x": 12, "target_y": 10, "priority": 2},
    {"type": "return_to_base",  "target_x": 0,  "target_y": 0,  "priority": 3}
  ]
}')
MISSION_ID=$(echo $MISSION | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# 2. Start the mission
curl -s -X POST $BASE/missions/$MISSION_ID/start | python3 -m json.tool

# 3. Spawn a rover
ROVER=$(curl -s -X POST $BASE/simulation/rovers -H "Content-Type: application/json" -d "{
  \"mission_id\": \"$MISSION_ID\",
  \"name\": \"Enc-Rover-Alpha\",
  \"start_x\": 0,
  \"start_y\": 0
}")
ROVER_ID=$(echo $ROVER | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# 4. Generate a plan (planner: "astar" or "rl")
PLAN=$(curl -s -X POST $BASE/planning/auto -H "Content-Type: application/json" -d "{
  \"mission_id\": \"$MISSION_ID\",
  \"rover_id\": \"$ROVER_ID\",
  \"planner\": \"astar\"
}")
PLAN_ID=$(echo $PLAN | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# 5. Execute the plan (async — runs in background)
curl -s -X POST $BASE/simulation/run -H "Content-Type: application/json" -d "{
  \"mission_id\": \"$MISSION_ID\",
  \"plan_id\": \"$PLAN_ID\"
}"

# 6. Check simulation status
curl -s $BASE/simulation/$MISSION_ID/status | python3 -m json.tool

# 7. Get telemetry events
curl -s "$BASE/telemetry/events/$MISSION_ID?limit=20" | python3 -m json.tool

# 8. Explain the plan decisions
curl -s $BASE/explain/plan/$PLAN_ID | python3 -m json.tool

# 9. Mission summary
curl -s $BASE/explain/mission/$MISSION_ID | python3 -m json.tool
```

---

## V3 Workflow (Multi-Rover + AI)

```bash
BASE=http://localhost:8000/api/v1

# 1–3: same as V1 workflow above (create mission, start, spawn rovers)
#      Spawn a second rover to enable multi-agent coordination:
curl -s -X POST $BASE/simulation/rovers -H "Content-Type: application/json" -d "{
  \"mission_id\": \"$MISSION_ID\",
  \"name\": \"Enc-Rover-Beta\",
  \"start_x\": 0, \"start_y\": 0
}"

# 4a. RL planner for a single rover
curl -s -X POST $BASE/planning/auto -H "Content-Type: application/json" -d "{
  \"mission_id\": \"$MISSION_ID\",
  \"rover_id\": \"$ROVER_ID\",
  \"planner\": \"rl\"
}" | python3 -m json.tool

# 4b. Multi-agent: distribute objectives across all rovers automatically
curl -s -X POST $BASE/planning/multi-agent -H "Content-Type: application/json" -d "{
  \"mission_id\": \"$MISSION_ID\",
  \"rover_ids\": [\"$ROVER_ID_1\", \"$ROVER_ID_2\"]
}" | python3 -m json.tool

# 5. Execute all rover plans (one POST per rover plan_id)
curl -s -X POST $BASE/simulation/run -H "Content-Type: application/json" -d "{
  \"mission_id\": \"$MISSION_ID\",
  \"plan_id\": \"$PLAN_ID\"
}"

# 6. Claude AI explanation (requires ANTHROPIC_API_KEY in .env)
#    Streams as Server-Sent Events — pipe through grep for a quick look:
curl -sN "$BASE/explain/llm/plan/$PLAN_ID" | grep '^data:' | head -5
```

---

## Contributing / Agent Instructions

See [CLAUDE.md](CLAUDE.md) for the full set of rules that govern how code and documentation changes are made in this repo — including mandatory doc-update rules, package management conventions, testing requirements, and feature-addition checklists.

---

## Project Structure

```
space-missions-control-center/
├── Makefile                         # All developer commands (single source of truth)
├── CLAUDE.md                        # Agent/contributor instructions + doc rules
├── README.md                        # This file
├── backend/                         # Python backend (uv-managed)
│   ├── pyproject.toml               # uv project config + dependencies
│   ├── uv.lock                      # Locked dependency graph
│   ├── .python-version              # Pinned Python version
│   ├── .env.example                 # Environment variable template
│   ├── Dockerfile                   # uv-based container image
│   ├── main.py                      # FastAPI app entry point
│   ├── alembic/                     # Database migration scripts
│   │   ├── env.py                   # Async Alembic environment
│   │   └── versions/                # Auto-generated migration files
│   ├── alembic.ini                  # Alembic configuration
│   ├── core/
│   │   ├── config.py                # Pydantic settings (env-driven)
│   │   ├── database.py              # SQLAlchemy async engine + session factory
│   │   ├── models/                  # Pydantic domain models (API-facing)
│   │   │   ├── mission.py           # Mission, Objective
│   │   │   ├── rover.py             # Rover, RoverState, RoverSpec
│   │   │   ├── command.py           # Command, CommandType, CommandStatus
│   │   │   ├── plan.py              # Plan, PlanStep
│   │   │   ├── telemetry.py         # TelemetryEvent
│   │   │   ├── anomaly.py           # Anomaly, AnomalyType, AnomalySeverity
│   │   │   └── environment.py       # Environment, Grid, Cell, TerrainType
│   │   ├── db_models/               # SQLAlchemy ORM table definitions (V2)
│   │   │   ├── mission.py           # MissionRow, ObjectiveRow
│   │   │   ├── rover.py             # RoverRow
│   │   │   ├── plan.py              # PlanRow, PlanStepRow
│   │   │   ├── telemetry.py         # TelemetryEventRow
│   │   │   ├── anomaly.py           # AnomalyRow
│   │   │   └── environment.py       # EnvironmentRow
│   │   ├── repositories/            # Data access layer (Pydantic ↔ ORM)
│   │   │   ├── mission.py
│   │   │   ├── rover.py
│   │   │   ├── plan.py
│   │   │   ├── telemetry.py
│   │   │   ├── anomaly.py
│   │   │   └── environment.py
│   │   └── events/
│   │       ├── bus.py               # Abstract EventBus interface
│   │       ├── memory_bus.py        # In-memory bus (default)
│   │       ├── redis_bus.py         # Redis Streams bus (swap in V2.1)
│   │       └── types.py             # MissionEvent, EventType
│   ├── api/
│   │   └── deps.py                  # FastAPI dependency injection
│   ├── services/
│   │   ├── mission_service/
│   │   │   ├── router.py            # REST endpoints
│   │   │   ├── service.py           # Business logic
│   │   │   ├── store.py             # Environment generator
│   │   │   └── schemas.py           # Request schemas
│   │   ├── planning_service/
│   │   │   ├── router.py
│   │   │   ├── service.py           # AStarPlanner + PlannerInterface + planner dispatch
│   │   │   ├── astar.py             # A* with terrain-weighted costs
│   │   │   ├── rl_planner.py        # Greedy value-function RL planner (V3)
│   │   │   ├── multi_agent_planner.py # Objective distribution coordinator (V3)
│   │   │   └── schemas.py
│   │   ├── simulation_service/
│   │   │   ├── router.py
│   │   │   ├── service.py           # Async execution loop
│   │   │   ├── executor.py          # Per-command executor
│   │   │   ├── rover_registry.py    # In-process rover registry
│   │   │   └── anomaly_engine.py    # Probabilistic failure injection
│   │   ├── telemetry_service/
│   │   │   └── router.py            # REST + WebSocket endpoints
│   │   └── explainability_service/
│   │       ├── router.py
│   │       └── service.py           # Decision log + LLM context builder
│   └── tests/
│       ├── conftest.py              # In-memory SQLite fixture for tests
│       ├── test_astar.py            # A* pathfinding unit tests
│       ├── test_simulation.py       # Rover model + anomaly engine
│       └── test_mission_api.py      # Full API integration tests
│
├── frontend/                        # React + TypeScript
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   └── src/
│       ├── main.tsx
│       ├── App.tsx                  # Router + QueryClient setup
│       ├── types/index.ts           # TypeScript domain types
│       ├── services/api.ts          # Axios API client
│       ├── store/missionStore.ts    # Zustand global state
│       ├── styles/
│       │   └── globals.css          # CSS custom property tokens (dark + light themes)
│       ├── hooks/
│       │   ├── useMissions.ts       # React Query hooks (includes useMultiAgentPlan V3)
│       │   ├── useTelemetry.ts      # WebSocket hook
│       │   ├── useExplain.ts        # Claude SSE streaming hook (V3)
│       │   └── useTheme.ts          # Theme toggle + localStorage persistence
│       ├── components/
│       │   ├── GridMap.tsx          # SVG 2D terrain grid (elevation tooltip V3)
│       │   ├── RoverStatus.tsx      # Rover health card
│       │   ├── AnomalyAlert.tsx     # Anomaly feed
│       │   ├── BatteryChart.tsx     # Battery % over time (Recharts)
│       │   ├── TimelinePlayer.tsx   # Step-by-step telemetry replay (V2)
│       │   ├── TerrainCanvas.tsx    # 3D terrain — React Three Fiber (V3)
│       │   └── MissionCard.tsx      # Mission list card
│       └── pages/
│           ├── Dashboard.tsx        # Fleet overview + stats
│           ├── MissionPlanner.tsx   # Create missions + objectives
│           └── MissionView.tsx      # Live mission ops center
│
├── infra/
│   └── docker-compose.yml           # Full local stack
├── Makefile                         # Developer commands
├── CLAUDE.md                        # Agent/contributor rules
└── README.md                        # This file
```

---

## API Reference (OpenAPI)

Full OpenAPI spec at http://localhost:8000/openapi.json when the server is running.

### Key Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/missions/` | List all missions |
| POST | `/api/v1/missions/` | Create mission |
| PATCH | `/api/v1/missions/{id}` | Update mission name / description |
| DELETE | `/api/v1/missions/{id}` | Delete mission and all related data |
| POST | `/api/v1/missions/{id}/start` | Start mission |
| GET | `/api/v1/missions/{id}/environment` | Get terrain grid |
| POST | `/api/v1/planning/auto` | Generate A* or RL plan for a rover (`planner` field: `astar`\|`rl`) |
| POST | `/api/v1/planning/manual` | Create manual plan |
| POST | `/api/v1/planning/multi-agent` | Coordinate all rovers — distribute objectives and generate one plan per rover |
| GET | `/api/v1/planning/mission/{id}/all` | List all plans for a mission (one per rover) |
| POST | `/api/v1/simulation/rovers` | Spawn rover |
| GET | `/api/v1/simulation/rovers` | List rovers (filter by `?mission_id=`) |
| POST | `/api/v1/simulation/run` | Execute plan (async, multiple concurrent plans allowed) |
| POST | `/api/v1/simulation/{id}/stop` | Stop all running plans for a mission |
| GET | `/api/v1/simulation/{id}/status` | Simulation status |
| WS | `/api/v1/telemetry/ws/{mission_id}` | Real-time telemetry stream |
| GET | `/api/v1/telemetry/events/{mission_id}` | Telemetry history |
| GET | `/api/v1/telemetry/anomalies/{mission_id}` | Mission anomalies |
| PATCH | `/api/v1/telemetry/anomalies/{anomaly_id}/resolve` | Resolve / dismiss an anomaly |
| POST | `/api/v1/telemetry/anomalies/{mission_id}/dismiss-all` | Dismiss all pending anomalies for a mission |
| GET | `/api/v1/explain/plan/{plan_id}` | Plan explanation |
| GET | `/api/v1/explain/mission/{mission_id}` | Mission summary |
| GET | `/api/v1/explain/anomaly/{anomaly_id}` | Anomaly analysis |
| GET | `/api/v1/explain/llm/{subject}/{id}` | Claude streaming explanation (SSE) — subject: `plan`\|`mission`\|`anomaly` |

---

## Configuration

All settings are in `backend/core/config.py` and driven by environment variables (`.env` file or shell):

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | SQLite local | `postgresql+asyncpg://...` for Postgres |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL |
| `USE_REDIS` | `false` | Set `true` to activate RedisStreamBus (falls back to in-memory if Redis is unreachable) |
| `SIM_STEP_DELAY_SECONDS` | `0.5` | Pause between simulation steps |
| `COMM_DELAY_SECONDS` | `2.5` | Simulated one-way comm delay |
| `DEBUG` | `false` | Enable SQLAlchemy query logging |
| `ROVER_BATTERY_CAPACITY` | `1000.0` | Max battery units |
| `ROVER_MOVE_COST` | `10.0` | Battery per cell × terrain multiplier |
| `ANTHROPIC_API_KEY` | _(unset)_ | Enables Claude streaming explanations in Explain tab |
| `CLAUDE_MODEL` | `claude-sonnet-4-6` | Claude model used for explanations |
| `CLAUDE_MAX_TOKENS` | `1024` | Max tokens per Claude response |
| `RL_EPISODE_BUDGET` | `500` | Max steps the RL planner may explore per plan |
| `RL_WEIGHT_TARGET` | `2.0` | RL value function: target proximity weight |
| `RL_WEIGHT_TERRAIN` | `1.0` | RL value function: terrain cost penalty |
| `RL_WEIGHT_GEYSER` | `3.0` | RL value function: geyser avoidance penalty |
| `PHYSICS_ELEVATION_COST_FACTOR` | `0.5` | Slope stress multiplier for wheel-stuck probability |
| `PHYSICS_THERMAL_ANOMALY_SCALE` | `1.0` | Temperature anomaly probability scale factor |

---

## Database Migrations (Alembic)

The backend uses SQLite by default for local development. Set `DATABASE_URL` to switch to PostgreSQL.

```bash
# Apply all pending migrations (run after pulling new schema changes)
make migrate

# Generate a new migration after changing ORM models in core/db_models/
make migrate-create MSG="add user preferences table"

# Roll back one step
make migrate-rollback

# View history
make migrate-history
```

On first `make dev`, `create_tables()` runs automatically at startup (idempotent). Alembic manages schema in production Docker deployments — run `make migrate` inside the container before starting the server.

---

## Switching the Event Bus (V1 → V2)

The event bus is abstracted behind `core/events/bus.py`. Switch from in-memory to Redis Streams with a single env var — no code changes required:

```bash
# .env or shell export
USE_REDIS=true
REDIS_URL=redis://localhost:6379/0   # default; override if needed
```

`main.py` reads `USE_REDIS` at startup and activates `RedisStreamBus` automatically. If Redis is unreachable, it falls back to `InMemoryEventBus` and logs a warning.

---

## Anomaly System

The `AnomalyEngine` injects probabilistic failures during execution. Probabilities are physics-informed in V3 — slope stress and ambient temperature affect failure rates.

| Anomaly | Trigger | Effect |
|---|---|---|
| `wheel_stuck` | Rocky/crater terrain; probability scales with cell elevation (slope stress) | Halts rover (STUCK state); auto-retried after 1 s hold |
| `comm_loss` | Random (1% per step) | COMM_LOST state — halts plan |
| `energy_spike` | Random; probability doubles below 60 K (thermal contraction) | −10% battery |
| `geyser_proximity` | Geyser terrain cell (25% per step) | Halts rover (STUCK state) |
| `low_battery` | Battery < 15% | Alert only — no state change |

Severity levels: `low`, `medium`, `high`, `critical`. All anomalies are persisted and dismissible via the UI or `PATCH /api/v1/telemetry/anomalies/{id}/resolve`.

---

## Roadmap

### V1 (complete)
- [x] Mission CRUD + environment generation
- [x] A* pathfinding with terrain costs
- [x] Rover digital twin (battery, position, path history)
- [x] Sequential command execution with comm delay
- [x] Anomaly injection and basic recovery
- [x] REST API with OpenAPI docs
- [x] WebSocket telemetry streaming
- [x] Explainability API
- [x] React UI: Dashboard, Planner, Mission View, SVG Grid Map
- [x] Light/dark theme switch with localStorage persistence
- [x] Auto-generate objectives in Mission Planner (quadrant-spread waypoints)
- [x] Map hover tooltips (terrain, rover state, battery, path/objective tags)
- [x] Anomaly resolution workflow (Dismiss button → PATCH endpoint)
- [x] Telemetry WebSocket push wired via event bus listener
- [x] Plan step expansion (Show all / Show fewer toggle)
- [x] 24 unit + integration tests

### V2
- [x] SQLAlchemy async persistence (SQLite dev / PostgreSQL prod via `DATABASE_URL`)
- [x] Repository pattern — `core/db_models/` ORM tables + `core/repositories/` data access layer
- [x] Alembic migrations (`make migrate`, `make migrate-create`)
- [x] Redis Streams event bus — set `USE_REDIS=true` to activate `RedisStreamBus` (auto-falls back to in-memory)
- [x] Telemetry charts — battery % over time per rover (Charts tab in Mission View, powered by Recharts)
- [x] Multi-rover coordination — spawn up to 4 rovers per mission, each with an independent A* plan running concurrently
- [x] Mission inline edit (name, description) and cascade delete from Mission View
- [x] Anomaly recovery side-effects — dismiss comm_loss restores rover to IDLE; dismiss low_battery recharges to 100%
- [x] Plan resume from rover's current position after comm loss / low battery recovery
- [x] Timeline playback (step-by-step replay of past telemetry with scrubber, play/pause, and speed control)

### V3
- [x] Reinforcement Learning planner — greedy value-function policy; select A* or RL per-rover in the UI; hot-swap ready for trained weights
- [x] Multi-agent planning — "Coordinate All Rovers" distributes objectives across rovers via greedy distance assignment, generates independent A* plans per rover
- [x] Claude API integration — streaming SSE explanation in the Explain tab; set `ANTHROPIC_API_KEY` to activate; falls back gracefully if unset
- [x] Physics-based terrain — elevation map (multi-octave noise), slope-adjusted movement cost, temperature-aware anomaly probability
- [x] 3D visualization — React Three Fiber terrain canvas, per-cell meshes with elevation extrusion, location-pin rover markers with bob animation and shadow ring, hover tooltips (lazy-loaded in "3D" tab)
- [x] Anomalies tab — full anomaly history with sort (newest / oldest / severity) and filter (status / type / severity) controls; sidebar shows only active anomalies newest-first with direct dismiss actions; Anomalies tab button shows live badge count

---

## Development

### Adding a new planner

1. Create `backend/services/planning_service/my_planner.py` and implement `PlannerInterface`:

```python
from .schemas import PlanRequest
from core.models.plan import Plan
from core.models.environment import Grid

class MyPlanner:
    async def plan(self, request: PlanRequest, grid: Grid, objectives: list) -> Plan:
        # Your planning logic here
        ...
```

2. Add a value to `PlannerType` in `core/models/plan.py` (e.g. `MY_PLANNER = "my_planner"`).
3. Instantiate and dispatch in `PlanningService.__init__` / `create_plan` in `planning_service/service.py`.
4. The existing A* and RL planners (`astar.py`, `rl_planner.py`) are good reference implementations.

### Adding a new anomaly type

1. Add to `AnomalyType` in `core/models/anomaly.py`
2. Add detection logic in `simulation_service/anomaly_engine.py`
3. Add impact/recommendation text in `explainability_service/service.py`

### Claude API integration

Claude is already wired in `explainability_service/service.py`. To activate it:

```bash
# backend/.env
ANTHROPIC_API_KEY=sk-ant-...
CLAUDE_MODEL=claude-sonnet-4-6   # default
```

The `GET /api/v1/explain/llm/{subject}/{id}` endpoint streams a Server-Sent Events response. In the UI, click **Ask Claude** in the Explain tab. If the key is absent, the endpoint returns a plain-text fallback message — no errors or crashes.

To extend the context Claude receives, edit `_build_llm_context()` in `explainability_service/service.py`. The method returns a plain string that is passed directly as the user message.

### Tuning the RL planner

The RL planner uses a greedy value function:

```
V(cell) = (w_target / (1 + dist_to_nearest_obj))
        - w_terrain × cell.movement_cost
        - w_geyser  × geyser_penalty
        - |elevation| × 0.5
```

Adjust weights in `.env` without redeploying:

```bash
RL_WEIGHT_TARGET=2.0    # increase to be more aggressive toward objectives
RL_WEIGHT_TERRAIN=1.0   # increase to prefer easier terrain
RL_WEIGHT_GEYSER=3.0    # increase for stronger geyser avoidance
RL_EPISODE_BUDGET=500   # max steps before fallback to A*
```

To swap in a trained neural policy, subclass or replace `_value()` in `rl_planner.py` — the rest of the planning loop stays unchanged.
