# Enceladus Mission Control Center

A production-grade space mission control system simulating rover operations on Enceladus — Saturn's ocean moon. Features a physics-based digital twin simulation engine, A* and RL mission planning with multi-agent coordination, autonomous fault protection and AEGIS-style self-directed target selection, fog-of-war exploration of a geologically active terrain (geyser cycles, ice fractures, day/night frost), and light-delay-constrained communication windows — alongside real-time telemetry streaming, Claude-powered explanations, timeline playback, and a 3D terrain visualiser.

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
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │                        comm_service                              │ │
│  │      Comm window schedule · uplink queue for gated actions       │ │
│  └─────────────────────────────────────────────────────────────────┘ │
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
| `UplinkCommand` | Ground command queued while the comm window was closed, held for the next uplink |

### Service Responsibilities

| Service | Prefix | Responsibility |
|---|---|---|
| `mission_service` | `/api/v1/missions` | Mission CRUD, physics-based elevation terrain generation |
| `planning_service` | `/api/v1/planning` | A* pathfinding, RL value-function planner, multi-agent objective distribution |
| `simulation_service` | `/api/v1/simulation` | Rover spawn, physics-aware plan execution, anomaly injection |
| `telemetry_service` | `/api/v1/telemetry` | WebSocket push, event history, anomaly resolution |
| `explainability_service` | `/api/v1/explain` | Structured decision logs, Claude API streaming explanations (SSE) |
| `comm_service` | `/api/v1/comm` | Comm window schedule, uplink queue for gated ground-control actions |

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
| `make test` | Run all backend tests (53 total) |
| `make test-verbose` | Tests with full output |
| `make test-unit` | Unit tests only (A* + simulation + AEGIS + comm windows) |
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
make test           # all tests (53 total)
make test-verbose   # with full output
make test-unit      # A* + simulation + AEGIS + comm windows unit tests (fast)
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
│   │   │   ├── environment.py       # Environment, Grid, Cell, TerrainType
│   │   │   └── comm.py              # UplinkKind, UplinkCommand (V4 — in-memory only, no db_models/repository)
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
│   │   │   ├── anomaly_engine.py    # Probabilistic failure injection
│   │   │   ├── fault_protection.py  # FaultProtectionEngine — tiered anomaly recovery (V4)
│   │   │   ├── terrain_events.py    # TerrainEventEngine — geyser/fracture/frost cycles (V4)
│   │   │   └── aegis.py             # Autonomous target scoring + selection (V4)
│   │   ├── telemetry_service/
│   │   │   ├── router.py            # REST + WebSocket endpoints
│   │   │   ├── service.py           # Anomaly-resolution side effects, shared with comm_service (V4)
│   │   │   └── store.py             # V2 compatibility shim — logic now lives in core/repositories/
│   │   ├── explainability_service/
│   │   │   ├── router.py
│   │   │   └── service.py           # Decision log + LLM context builder
│   │   └── comm_service/            # Communication windows (V4)
│   │       ├── router.py            # GET /comm/status, GET /comm/{mission_id}/queue
│   │       ├── service.py           # CommWindowService — gate/enqueue/flush
│   │       ├── windows.py           # Pure wall-clock comm-window schedule
│   │       └── schemas.py           # CommStatusResponse, UplinkResult
│   └── tests/
│       ├── conftest.py              # In-memory SQLite fixture for tests
│       ├── test_astar.py            # A* pathfinding unit tests
│       ├── test_simulation.py       # Rover model + anomaly engine
│       ├── test_aegis.py            # AEGIS scoring + target selection (V4)
│       ├── test_comm_windows.py     # Comm window schedule + gate/queue/flush (V4)
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
│       │   ├── useComm.ts           # Comm window status + uplink queue polling (V4)
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
| POST | `/api/v1/missions/{id}/complete` | Mark mission complete |
| GET | `/api/v1/missions/{id}/environment` | Get terrain grid |
| POST | `/api/v1/planning/auto` | Generate A* or RL plan for a rover (`planner` field: `astar`\|`rl`) |
| POST | `/api/v1/planning/manual` | Create manual plan |
| GET | `/api/v1/planning/{plan_id}` | Get plan by id |
| GET | `/api/v1/planning/mission/{mission_id}` | Get the current plan for a mission |
| POST | `/api/v1/planning/multi-agent` | Coordinate all rovers — distribute objectives and generate one plan per rover |
| GET | `/api/v1/planning/mission/{id}/all` | List all plans for a mission (one per rover) |
| GET | `/api/v1/planning/environments/{id}/science-heatmap` | Per-cell science scores for an environment (V4) |
| POST | `/api/v1/simulation/rovers` | Spawn rover |
| GET | `/api/v1/simulation/rovers` | List rovers (filter by `?mission_id=`) |
| GET | `/api/v1/simulation/rovers/{rover_id}` | Get a single rover |
| POST | `/api/v1/simulation/run` | Execute plan (async, multiple concurrent plans allowed) |
| POST | `/api/v1/simulation/{id}/stop` | Stop all running plans for a mission |
| GET | `/api/v1/simulation/{id}/status` | Simulation status |
| GET | `/api/v1/simulation/rovers/{rover_id}/aegis-proposal` | Get the rover's pending AEGIS target proposal, if any |
| WS | `/api/v1/telemetry/ws/{mission_id}` | Real-time telemetry stream |
| GET | `/api/v1/telemetry/events/{mission_id}` | Telemetry history |
| GET | `/api/v1/telemetry/anomalies/{mission_id}` | Mission anomalies |
| PATCH | `/api/v1/telemetry/anomalies/{anomaly_id}/resolve` | Resolve / dismiss an anomaly — gated by the comm window (V4); returns `{delivered, uplink, result}` |
| POST | `/api/v1/telemetry/anomalies/{mission_id}/dismiss-all` | Dismiss all pending anomalies for a mission — each gated individually |
| GET | `/api/v1/explain/plan/{plan_id}` | Plan explanation |
| GET | `/api/v1/explain/mission/{mission_id}` | Mission summary |
| GET | `/api/v1/explain/anomaly/{anomaly_id}` | Anomaly analysis |
| GET | `/api/v1/explain/llm/{subject}/{id}` | Claude streaming explanation (SSE) — subject: `plan`\|`mission`\|`anomaly` |
| GET | `/api/v1/comm/status` | Current comm window state (open/closed, seconds until next transition) (V4) |
| GET | `/api/v1/comm/{mission_id}/queue` | Pending uplink commands awaiting the next comm window (V4) |

Also gated by the comm window (V4) — same `{delivered, uplink, result}` response shape as anomaly resolution:

| Method | Path | Description |
|---|---|---|
| PATCH | `/api/v1/simulation/rovers/{rover_id}/autonomy` | Set autonomy level |
| POST | `/api/v1/simulation/rovers/{rover_id}/aegis-proposal/approve` | Approve pending AEGIS target proposal |
| POST | `/api/v1/simulation/rovers/{rover_id}/aegis-proposal/reject` | Reject pending AEGIS target proposal |

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
| `CLAUDE_MAX_TOKENS` | `4096` | Max tokens per Claude response |
| `RL_EPISODE_BUDGET` | `500` | Max steps the RL planner may explore per plan |
| `RL_WEIGHT_TARGET` | `2.0` | RL value function: target proximity weight |
| `RL_WEIGHT_TERRAIN` | `1.0` | RL value function: terrain cost penalty |
| `RL_WEIGHT_GEYSER` | `3.0` | RL value function: geyser avoidance penalty |
| `PHYSICS_ELEVATION_COST_FACTOR` | `0.5` | Slope stress multiplier for wheel-stuck probability |
| `PHYSICS_THERMAL_ANOMALY_SCALE` | `1.0` | Temperature anomaly probability scale factor |
| `FOG_OF_WAR` | `true` | Enable fog of war — cells hidden until a rover enters sensor range |
| `SENSOR_RANGE` | `2` | Chebyshev radius of cells revealed around rover position each step |
| `FPS_WHEEL_STUCK_RETRY_LIMIT` | `2` | Consecutive wheel-stuck retries before FPS attempts a reverse manoeuvre |
| `FPS_COMM_LOSS_RETRY_LIMIT` | `2` | Comm-loss wait cycles before FPS declares safe mode |
| `FPS_SAFE_MODE_BATTERY_PCT` | `10.0` | Battery % below which FPS forces safe mode (CRITICAL low-battery anomaly) |
| `TERRAIN_GEYSER_CYCLE_TICKS` | `15` | Steps between geyser eruption/dormancy evaluations |
| `TERRAIN_GEYSER_FLIP_PROB` | `0.35` | Probability each geyser changes state per evaluation cycle |
| `TERRAIN_FRACTURE_PROB_PER_TICK` | `0.004` | Probability a crevasse cell spreads to an adjacent flat/ice cell per step |
| `TERRAIN_FROST_PERIOD_TICKS` | `20` | Full Enceladus day/night cycle length in simulation steps (night = half) |
| `TERRAIN_FROST_COST_FACTOR` | `1.4` | Movement cost multiplier applied to flat/ice cells during night frost |
| `AEGIS_MAX_AUTO_OBJECTIVES` | `10` | Cap on self-generated AEGIS objectives per mission run (`0` = unlimited) |
| `COMM_SLOT_SECONDS` | `60` | Seconds between successive uplink window openings |
| `COMM_WINDOW_DURATION_SECONDS` | `15` | How long each uplink window stays open |

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

`InMemoryEventBus` uses broadcast pub-sub semantics: every `subscribe()` call creates an independent queue, so multiple concurrent consumers (WebSocket telemetry forwarder, DB persistence listener) each receive the full event stream without stealing messages from one another. An `_event_persist_listener` background task in `main.py` subscribes to all three streams (`telemetry`, `anomaly`, `mission`) and persists key events — anomalies, FPS decisions, terrain changes, mission lifecycle — directly to the telemetry DB table.

---

## Anomaly System

The `AnomalyEngine` injects probabilistic failures during execution (probabilities are physics-informed in V3 — slope stress and ambient temperature affect failure rates). Recovery from an injected anomaly is governed by the `FaultProtectionEngine` (V4, `services/simulation_service/fault_protection.py`), which tracks a per-rover consecutive-anomaly streak and escalates through retry → reverse/replan → safe mode.

| Anomaly | Trigger | Immediate effect | FPS response (V4) |
|---|---|---|---|
| `wheel_stuck` | Rocky/crater terrain; probability scales with cell elevation (slope stress) | Rover enters `STUCK` state | Retry up to `FPS_WHEEL_STUCK_RETRY_LIMIT`, then reverse one cell, then safe mode |
| `comm_loss` | Random (1% per step) | Rover enters `COMM_LOST` state | Retry (brief wait) up to `FPS_COMM_LOSS_RETRY_LIMIT`, then safe mode |
| `energy_spike` | Random; probability doubles below 60 K (thermal contraction) | −10% battery | Continue — drain already applied, no further action |
| `geyser_proximity` | Active geyser terrain cell (25% per step) | Rover enters `STUCK` state | Replan around the hazard, or safe mode if no path exists |
| `low_battery` | Battery < 15% (always `CRITICAL` severity) | Alert only — no state change | Safe mode |
| `path_blocked` | Synthesised (not by `AnomalyEngine`) when a V4 terrain event — ice fracture or geyser eruption — blocks a cell on the rover's planned path | None | Replan, or safe mode if no path exists |
| `sensor_fault` | Not currently triggered by any engine — reserved for the Instrument Health Dashboard (V5 backlog #9) | — | Continue (rule already defined, unused until #9 ships) |
| `unknown` | Not currently raised — generic fallback type | — | Retry once, then safe mode |

Severity levels: `low`, `medium`, `high`, `critical`. All anomalies are persisted and dismissible via the UI or `PATCH /api/v1/telemetry/anomalies/{id}/resolve` — gated by the comm window (V4) when ground control dismisses one manually; FPS's own automatic responses above are not gated.

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

### V2 (complete)
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

### V3 (complete)
- [x] Reinforcement Learning planner — greedy value-function policy; select A* or RL per-rover in the UI; hot-swap ready for trained weights
- [x] Multi-agent planning — "Coordinate All Rovers" distributes objectives across rovers via greedy distance assignment, generates independent A* plans per rover
- [x] Claude API integration — streaming SSE explanation in the Explain tab; set `ANTHROPIC_API_KEY` to activate; falls back gracefully if unset; response rendered as Markdown (headings, lists, bold, code, blockquotes) via `react-markdown`
- [x] Physics-based terrain — elevation map (multi-octave noise), slope-adjusted movement cost, temperature-aware anomaly probability
- [x] 3D visualization — React Three Fiber terrain canvas, per-cell meshes with elevation extrusion, location-pin rover markers with bob animation and shadow ring, hover tooltips (lazy-loaded in "3D" tab)
- [x] Anomalies tab — full anomaly history with sort (newest / oldest / severity) and filter (status / type / severity) controls; sidebar shows only active anomalies newest-first with direct dismiss actions; Anomalies tab button shows live badge count

### V4 (complete)
- [x] **Fog of War / terrain discovery** — cells start unknown until a rover enters sensor range (Chebyshev radius, default 2); map fills in progressively in both 2D and 3D views; fogged cells hide terrain type, elevation, and samples; objectives remain visible as uncharted markers; set `FOG_OF_WAR=false` to disable
- [x] **Fault Protection System** — tiered autonomous fault response per anomaly type (retry → reverse → replan → safe mode); `FaultProtectionEngine` runs after every anomaly in the execution loop; rover enters `safe_mode` state on critical faults, exits when ground control resolves the anomaly; configurable retry/replan thresholds via env vars
- [x] **Dynamic terrain events** — geyser eruption cycles (active ↔ dormant per configurable probability); ice fracture propagation (crevasse spreads to adjacent flat/ice cells); surface frost (day/night cycle multiplies flat/ice movement costs); all changes published on event bus; FPS auto-replans when fracture/eruption blocks planned path; 2D and 3D maps reflect live terrain state; frost/night status shown in map status bar
- [x] **Telemetry enrichment** — executor emits the correct `TelemetryType` per command (POSITION / SAMPLE_COLLECTED / STATE_CHANGE / HEARTBEAT / COMMAND_ACK); `_event_persist_listener` in `main.py` persists anomaly, FPS, terrain, and mission-lifecycle bus events to the DB so all event types appear in the Telemetry tab; `InMemoryEventBus` upgraded to broadcast pub-sub (each subscriber gets its own queue, multiple concurrent listeners no longer steal events from each other); Telemetry tab updated with rover/type filters, 50-row pagination, up to 2 000 events, and colour-coded event-type badges
- [x] **Explain tab improvements** — `_build_llm_context()` now sends Claude the full step sequence (MOVE runs compressed, non-MOVE steps shown with target, battery cost, and rationale), the objectives list with completion status, command-type breakdown, and night-cycle state; system prompt updated to request bullet-point analysis; Explain tab UI gains a command-type filter dropdown, 30-step pagination with « ‹ / › » controls, battery cost column, and visual highlighting for non-MOVE steps
- [x] **Objective completion bug fix** — terrain-replan block in `_run_plan_loop` was missing a `continue` statement, causing `idx += 1` to run after resetting `idx = 0`, which skipped the first (sometimes only) step of the new plan; added `continue` to match the FPS-anomaly replan path; also added a final post-loop objective check as a safety net so the rover's ending position is always compared against remaining objectives before the mission-completion test runs
- [x] **Science Value Map + coverage optimiser** — per-cell science scores computed from geyser proximity (up to 5.0, Chebyshev-distance decay), ice-water interface bonus (ICE cells adjacent to geysers +3.0), and crater proximity (+2.0 at the crater, +0.75 in the ejecta ring), clamped to [0, 10]; scores are recomputed whenever geyser eruption/dormancy events fire; multi-agent coordinator gains an `optimize_science` mode that assigns objectives to maximise science ROI (science_value / battery_cost) rather than minimising travel; 2D map gains a "Science overlay" toggle rendering a teal→lime→amber heatmap; cell hover tooltips show the science score; `GET /api/v1/planning/environments/{id}/science-heatmap` exposes scores for external consumers; "Maximize science" checkbox in the rover control panel switches the coordinator into science-ROI mode
- [x] **AEGIS-style autonomous target selection** — when the assigned objective list is exhausted, rovers autonomously score every reachable cell (science value, unexplored bonus, sample presence, elevation gradient, distance) and self-generate the best target; three per-rover autonomy levels: `supervised` (propose target, pause for ground-control approval/rejection via UI), `semi_autonomous` (self-direct within already-revealed terrain), `fully_autonomous` (explore any reachable cell including uncharted fog); `AEGIS_MAX_AUTO_OBJECTIVES` env var caps the number of self-generated objectives per run; `PATCH /api/v1/simulation/rovers/{id}/autonomy` sets level; `GET /api/v1/simulation/rovers/{id}/aegis-proposal` + approve/reject endpoints for supervised workflow; `AEGIS_TARGET_SELECTED` and `AEGIS_TARGET_PROPOSED` events published on the mission stream; rover panel shows autonomy selector buttons and inline proposal approval card
- [x] **Communication windows** — configurable uplink windows (`COMM_SLOT_SECONDS` apart, `COMM_WINDOW_DURATION_SECONDS` long); ground-control interventions (anomaly resolution, autonomy level changes, AEGIS proposal approve/reject) are gated by the window and held in an in-memory uplink queue when closed, delivered automatically by a background flusher once the next window opens; the onboard plan execution loop itself is never gated — rovers keep executing their current plan autonomously regardless of window state; `GET /api/v1/comm/status` and `GET /api/v1/comm/{mission_id}/queue` expose the schedule and pending queue; Timeline tab renders comm window bands beneath the scrubber and an open/closed indicator for the current replay position; rover panel and mission header show a live "queued" notice / uplink badge

### V5 (to be implemented)

Remaining Features Backlog items, in priority order. See the Features Backlog section below for full descriptions and the V5 Priority Summary table for rationale.

- [ ] **Sample Chain of Custody** (#8) — sample ID, timestamp, location, terrain type, and `collected → analysed → archived` state; Sample Registry tab; Claude summarises scientific significance
- [ ] **Opportunistic Science** (#4) — configurable off-path deviation budget; rovers grab a sample or investigate a feature without a ground command; deviations logged as `opportunistic_science` telemetry events
- [ ] **Dynamic Replanning with Shared Hazard Maps** (#5) — shared hazard map accumulates a cost penalty at cells where anomalies occurred; persists across replans; multi-agent coordinator uses it so one rover avoids cells that stuck another
- [ ] **Instrument Health Dashboard** (#9) — per-instrument health % that degrades with use and anomaly events; low health raises `sensor_fault` probability; maintenance recommendations from Claude
- [ ] **Operations Metrics Dashboard** (#13) — science return rate, plan adherence, uptime, and terrain coverage KPIs on the Dashboard per mission
- [ ] **Resource-Aware Mission Scheduling** (#2) — per-rover resource budget model (battery, sample slots, max steps/sol); rovers defer/refuse budget-violating activities; sol grouping with rest/charge phases shown as Timeline bands
- [ ] **Multi-Mission Fleet View** (#14) — fleet overview map across all active missions, cross-mission resource summary, and a single alert roll-up with per-mission navigation
- [ ] **Mission Replay & What-If Analysis** (#12) — replay a completed mission from any checkpoint and branch off with a different plan to compare outcomes

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

The streamed response is rendered as Markdown using `react-markdown` with theme-matched component overrides (see `MissionView.tsx` → Claude Analysis section).

`_build_llm_context()` in `explainability_service/service.py` builds the user message sent to Claude. It now includes: mission name and planner type; objectives list with type, target, priority, and completion status; command-type breakdown (e.g. `move×47, collect_sample×3`); the full step sequence capped at 120 entries (MOVE runs compressed to `... N MOVE step(s) ...`, non-MOVE steps shown with target coordinates, battery cost, and rationale); and environment data (grid size, geyser count, temperature, night-cycle status). Extend it here to feed Claude additional context.

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

---

## Features Backlog

Candidate features grounded in real planetary rover operations software (MER, MSL Curiosity, Mars 2020 Perseverance, and proposed ocean-world mission concepts). V4 priorities are marked ★ — all six are now implemented (see Roadmap → V4 above). Everything else below is still backlog.

---

### 🤖 Rover Autonomy & Self-Directed Operations

#### ★ 1. AEGIS-style Onboard Target Selection — ✅ Implemented
Real precedent: Perseverance uses AEGIS (Autonomous Exploration for Gathering Increased Science) to autonomously identify and laser-fire on targets without an Earth uplink. For Enceladus this means:
- Rovers score adjacent cells each step for scientific value (geyser proximity, sample density, unexplored territory, elevation gradient).
- A configurable **autonomy level** per rover: `supervised` (propose targets, wait for approval), `semi-autonomous` (act within a pre-approved zone), `fully autonomous` (self-directed within resource budgets).
- Rovers **generate their own objectives** when the human-assigned list is exhausted, prioritising unexplored terrain and high-science cells.

#### 2. Resource-Aware Mission Scheduling (MEXEM / SEQGEN-style)
JPL's SEQGEN tool schedules activities around resource windows. Here:
- A **resource budget model** per rover: battery capacity, sample storage slots, max steps per sol.
- Rover refuses or defers activities that would violate budgets rather than failing mid-execution.
- **Sol planning** — groups commands into sols with a rest/charge phase between them; Timeline shows sol boundaries as coloured bands.

#### ★ 3. Fault Protection System (FPS) — ✅ Implemented
Every real rover has a tiered fault response system (modelled on Curiosity's FPS):
- **Fault rules** defined per anomaly type: e.g. `if wheel_stuck AND slope > 0.6 → attempt_reverse THEN replan`.
- **Safe mode** trigger — if battery drops below a critical threshold or 3+ anomalies occur in one sol, rover autonomously halts, stops non-essential systems, and waits for ground contact.
- **Watchdog** — if no telemetry for N steps, simulation marks rover as `contact_lost` and queues a recovery uplink for the next comm window.

#### 4. Opportunistic Science
Rovers deviate slightly from their planned path to collect a sample or investigate a newly detected feature — without waiting for a ground command:
- A **deviation budget** (e.g. max 3 cells off-path) configurable per rover.
- Deviations logged as `opportunistic_science` events in telemetry, visible in the Timeline tab.
- Claude can explain why a rover deviated from its original plan.

---

### 🗺️ Planning & Path Intelligence

#### 5. Dynamic Replanning with Shared Hazard Maps
- Rovers build a shared **hazard map** from their traversal history — cells where anomalies occurred accumulate a cost penalty for future planning.
- The hazard map persists across replans and is visible as an overlay on the 2D/3D map.
- The multi-agent coordinator uses the shared hazard map so Rover 2 avoids cells that caused Rover 1 to get stuck.

#### ★ 6. Communication Windows & Uplink Scheduling — ✅ Implemented
Enceladus is ~1.3 billion km from Earth — a fundamental operational constraint:
- Configurable **comm windows** (e.g. two uplink windows per sol, each 20 minutes).
- Commands queued outside a window are held in an **uplink queue** with estimated delivery timestamps.
- Rovers execute their onboard plan autonomously between windows; ground can only intervene during an open window.
- Timeline shows comm windows as coloured bands; anomalies detected between windows are surfaced at the next uplink.

#### ★ 7. Science Value Map & Coverage Optimisation — ✅ Implemented
- Each cell carries a **science value** score (higher near geysers, ice-water interfaces, craters, and unexplored regions).
- A **coverage optimiser** (greedy or RL-based) assigns objectives to maximise total science return per unit of battery spent — replacing the current distance-only multi-agent assignment.
- A **coverage heatmap** overlay in the 2D/3D map shows which areas have been scientifically characterised vs. unexplored.

---

### 🧪 Science Operations

#### 8. Sample Chain of Custody
Real missions track every sample from collection through analysis:
- Samples carry an ID, collection timestamp, location, terrain type, and analysis state (`collected → analysed → archived`).
- A **Sample Registry** tab — table of all collected samples with full metadata, sortable and filterable.
- Samples can be "analysed" (costs battery, takes time, generates a science event) or held for later.
- Claude can summarise the scientific significance of the sample set.

#### 9. Instrument Health Dashboard
Rovers carry science instruments that degrade with use and anomaly events:
- Each rover has instruments (spectrometer, camera, drill) with a **health percentage** that degrades per use and with fault events.
- Instruments below a health threshold become unreliable, increasing the probability of `sensor_fault` anomalies.
- Instrument health is visible per rover in the sidebar panel, with maintenance recommendations from Claude.

---

### 🌍 Environment & Simulation Fidelity

#### ★ 10. Dynamic Terrain Events — ✅ Implemented
Enceladus is one of the most geologically active bodies in the Solar System — the environment should change during a mission:
- **Geyser eruption cycles** — geyser cells activate and deactivate on a schedule or probabilistically; active geysers are impassable, dormant ones are high-science targets.
- **Ice fracture propagation** — crevasse cells can spread to adjacent flat or ice cells over time, closing off previously planned routes.
- **Surface frost** — terrain costs increase during the Enceladus "night" (~32-hour rotation period), reducing battery efficiency and movement speed.
- All events appear in the Timeline and trigger anomaly alerts.

#### ★ 11. Fog of War / Terrain Feature Discovery — ✅ Implemented
- Cells start as `unknown` until a rover enters sensor range (configurable radius).
- The 2D and 3D maps reveal terrain progressively as rovers explore — unknown cells are shown dark and featureless.
- Scientific value of a cell cannot be assessed until it is revealed, creating a meaningful exploration vs. exploitation trade-off.
- Directly incentivises coverage-optimising planners and the AEGIS target-selection feature.

---

### 📡 Ground Operations

#### 12. Mission Replay & What-If Analysis
- Load a completed mission and replay it from any point, then branch off with different planning decisions.
- "What if Rover 2 had gone left instead of right?" — re-runs the simulation from a saved checkpoint with a different plan.
- Useful for post-mission analysis, operator training, and comparing planner performance.

#### 13. Operations Metrics Dashboard
Real missions track engineering and science efficiency KPIs:
- **Science return rate** — samples collected per unit battery consumed.
- **Plan adherence** — percentage of planned steps executed without deviation or replan.
- **Uptime** — percentage of mission time rovers were active vs. stuck / in safe mode.
- **Terrain coverage** — percentage of grid cells visited at least once.
- Displayed on the Dashboard per mission, alongside existing mission status cards.

#### 14. Multi-Mission Fleet View
Extend the Dashboard to support simultaneous mission oversight:
- A **fleet overview map** showing all active missions on their respective grids simultaneously, with live rover positions.
- Cross-mission resource summary: total active rovers, total pending anomalies, total science events across the fleet.
- Alert roll-up: a single view for every critical anomaly across all running missions, with one-click navigation to the affected mission.

---

### V4 Priority Summary

| Priority | Feature | Rationale |
|---|---|---|
| ★ 1 | ~~Fog of War / terrain discovery (#11)~~ ✅ | Changes every session's exploration dynamic; minimal backend changes |
| ★ 2 | ~~Fault Protection System (#3)~~ ✅ | Closes the gap between current "dismiss anomaly" and real autonomous recovery |
| ★ 3 | ~~Dynamic terrain events (#10)~~ ✅ | Makes long missions feel alive; Enceladus's active geology is the core narrative |
| ★ 4 | ~~Science Value Map + coverage optimiser (#7)~~ ✅ | Replaces distance-only multi-agent assignment with scientifically motivated planning |
| ★ 5 | ~~AEGIS-style target selection (#1)~~ ✅ | The headline autonomy feature — rovers that pursue their own science goals |
| ★ 6 | ~~Communication windows (#6)~~ ✅ | The most authentic Enceladus-specific constraint; fundamentally changes the planning rhythm |

### V5 Priority Summary

All remaining Features Backlog items — none started. Ordered by a mix of implementation cost and payoff: small, self-contained additions to existing systems first; multi-mission and checkpoint/branching infrastructure last since both need new cross-cutting plumbing this codebase doesn't have yet.

| Priority | Feature | Rationale |
|---|---|---|
| 1 | Sample Chain of Custody (#8) | Small, self-contained extension of the existing sample-collection mechanic; immediate visible science-ops payoff |
| 2 | Opportunistic Science (#4) | Builds directly on the AEGIS autonomy work just shipped in V4; scoped to a deviation budget check in the executor |
| 3 | Dynamic Replanning with Shared Hazard Maps (#5) | Meaningfully improves multi-agent coordination already in place since V3; moderate complexity, no new subsystems |
| 4 | Instrument Health Dashboard (#9) | Adds depth to the existing anomaly/`sensor_fault` system; additive UI, no changes to core execution loop |
| 5 | Operations Metrics Dashboard (#13) | Pure aggregation over data already collected (telemetry, anomalies, objectives); low risk, high stakeholder visibility |
| 6 | Resource-Aware Mission Scheduling (#2) | Bigger structural change — touches the planner and adds sol-level scheduling; more invasive than the above |
| 7 | Multi-Mission Fleet View (#14) | Needs new cross-mission aggregation endpoints; valuable but orthogonal to the per-mission core loop |
| 8 | Mission Replay & What-If Analysis (#12) | Highest cost — needs a mission/rover/environment checkpoint system and branching re-simulation, well beyond today's simple Timeline replay |
