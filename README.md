# Enceladus Mission Control Center

A production-grade space mission control system simulating rover operations on Enceladus — Saturn's ocean moon. Features a digital twin simulation engine, A* mission planning, real-time telemetry streaming, anomaly detection, and an explainability layer.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (React)                          │
│  Dashboard · Mission Planner · Grid Map · Telemetry · Timeline  │
└──────────────────────┬──────────────────────────────────────────┘
                       │ REST + WebSocket
┌──────────────────────▼──────────────────────────────────────────┐
│                    FastAPI Backend (V1: unified)                  │
│                                                                   │
│  ┌─────────────────┐  ┌──────────────────┐  ┌────────────────┐  │
│  │ mission_service │  │ planning_service  │  │ sim_service    │  │
│  │  CRUD + status  │  │  A* pathfinding   │  │  rover digital │  │
│  │  environment gen│  │  Manual plans     │  │  twin executor │  │
│  └─────────────────┘  └──────────────────┘  └────────────────┘  │
│                                                                   │
│  ┌─────────────────┐  ┌──────────────────────────────────────┐  │
│  │telemetry_service│  │       explainability_service          │  │
│  │  WebSocket push │  │  Structured logs · LLM-ready context  │  │
│  │  Event history  │  │  Plan · Mission · Anomaly explain API │  │
│  └─────────────────┘  └──────────────────────────────────────┘  │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              Event Bus (abstract)                         │   │
│  │  V1: InMemoryEventBus  →  V2: RedisStreamBus             │   │
│  └──────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
                       │
         ┌─────────────┴────────────┐
    ┌────▼────┐               ┌────▼────┐
    │ Redis   │               │Postgres │
    │ Streams │               │  (V2)   │
    └─────────┘               └─────────┘
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
| `Environment` | Grid world — terrain, geysers, hazard zones |
| `Grid / Cell` | 2D terrain grid with per-cell movement cost |

### Service Responsibilities

| Service | Port (standalone) | Responsibility |
|---|---|---|
| `mission_service` | `/api/v1/missions` | Mission CRUD, environment generation |
| `planning_service` | `/api/v1/planning` | A* pathfinding, plan generation |
| `simulation_service` | `/api/v1/simulation` | Rover spawn, plan execution loop |
| `telemetry_service` | `/api/v1/telemetry` | WebSocket push, event history |
| `explainability_service` | `/api/v1/explain` | Decision rationale, LLM context |

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
| `make test` | Run all backend tests |
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
make test           # all tests (22 total)
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

# 4. Generate A* plan
PLAN=$(curl -s -X POST $BASE/planning/auto -H "Content-Type: application/json" -d "{
  \"mission_id\": \"$MISSION_ID\",
  \"rover_id\": \"$ROVER_ID\"
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
│   │   │   ├── service.py           # AStarPlanner + PlannerInterface
│   │   │   ├── astar.py             # A* with terrain-weighted costs
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
│       │   ├── useMissions.ts       # React Query hooks
│       │   ├── useTelemetry.ts      # WebSocket hook
│       │   └── useTheme.ts          # Theme toggle + localStorage persistence
│       ├── components/
│       │   ├── GridMap.tsx          # SVG 2D terrain grid
│       │   ├── RoverStatus.tsx      # Rover health card
│       │   ├── AnomalyAlert.tsx     # Anomaly feed
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
| POST | `/api/v1/planning/auto` | Generate A* plan |
| POST | `/api/v1/planning/manual` | Create manual plan |
| POST | `/api/v1/simulation/rovers` | Spawn rover |
| POST | `/api/v1/simulation/run` | Execute plan (async) |
| GET | `/api/v1/simulation/{id}/status` | Simulation status |
| WS | `/api/v1/telemetry/ws/{mission_id}` | Real-time telemetry stream |
| GET | `/api/v1/telemetry/events/{mission_id}` | Telemetry history |
| GET | `/api/v1/telemetry/anomalies/{mission_id}` | Mission anomalies |
| PATCH | `/api/v1/telemetry/anomalies/{anomaly_id}/resolve` | Resolve / dismiss an anomaly |
| POST | `/api/v1/telemetry/anomalies/{mission_id}/dismiss-all` | Dismiss all pending anomalies for a mission |
| GET | `/api/v1/explain/plan/{plan_id}` | Plan explanation |
| GET | `/api/v1/explain/mission/{mission_id}` | Mission summary |
| GET | `/api/v1/explain/anomaly/{anomaly_id}` | Anomaly analysis |

---

## Configuration

All settings are in `backend/core/config.py` and driven by environment variables (`.env` file or shell):

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | SQLite local | `postgresql+asyncpg://...` for Postgres |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection |
| `SIM_STEP_DELAY_SECONDS` | `0.5` | Pause between simulation steps |
| `COMM_DELAY_SECONDS` | `2.5` | Simulated one-way comm delay |
| `DEBUG` | `false` | Enable SQLAlchemy query logging |
| `ROVER_BATTERY_CAPACITY` | `1000.0` | Max battery units |
| `ROVER_MOVE_COST` | `10.0` | Battery per cell × terrain multiplier |

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

The event bus is abstracted behind `core/events/bus.py`. To switch from in-memory to Redis Streams:

```python
# In main.py, replace:
bus = InMemoryEventBus()

# With:
from core.events.redis_bus import RedisStreamBus
bus = RedisStreamBus(url=settings.redis_url)
```

No other code changes required.

---

## Anomaly System

The `AnomalyEngine` injects probabilistic failures during execution:

| Anomaly | Trigger | Effect |
|---|---|---|
| `wheel_stuck` | Rocky/crater terrain | Halts rover (STUCK state) |
| `comm_loss` | Random (1% per step) | COMM_LOST state |
| `energy_spike` | Random (3% per step) | −10% battery |
| `geyser_proximity` | Geyser terrain cell | Halts rover |
| `low_battery` | Battery < 15% | Alert (no state change) |

Auto-recovery: stuck rovers are auto-retried once after a 1-second hold.

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
- [x] 22 unit + integration tests

### V2
- [x] SQLAlchemy async persistence (SQLite dev / PostgreSQL prod via `DATABASE_URL`)
- [x] Repository pattern — `core/db_models/` ORM tables + `core/repositories/` data access layer
- [x] Alembic migrations (`make migrate`, `make migrate-create`)
- [ ] Redis Streams event bus (replace InMemoryEventBus)
- [ ] Timeline playback UI
- [ ] Telemetry charts (battery over time, path replay)
- [ ] Multi-rover coordination (single mission, multiple rovers)

### V3
- [ ] Reinforcement Learning planner interface
- [ ] Multi-agent planning (independent rover objectives)
- [ ] Claude API integration for natural-language explanations
- [ ] Physics-based terrain simulation
- [ ] 3D visualization

---

## Development

### Adding a new planner

Implement `PlannerInterface` in `backend/services/planning_service/service.py`:

```python
class MyRLPlanner(PlannerInterface):
    async def plan(self, request: PlanRequest, grid: Grid, objectives: list) -> Plan:
        # Your RL/MAS planning logic here
        ...
```

Register it under a new `PlannerType` enum value and add a route.

### Adding a new anomaly type

1. Add to `AnomalyType` in `core/models/anomaly.py`
2. Add detection logic in `simulation_service/anomaly_engine.py`
3. Add impact/recommendation text in `explainability_service/service.py`

### Extending the explainability layer for LLM

The `_build_llm_context()` method in `explainability_service/service.py` already builds a structured string context. To wire Claude:

```python
import anthropic

client = anthropic.Anthropic()
response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    messages=[{"role": "user", "content": context}],
)
```
