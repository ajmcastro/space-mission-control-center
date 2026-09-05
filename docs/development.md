# Development Guide

[← Back to README](../README.md)

## Prerequisites

| Tool | Version |
|---|---|
| Python | >= 3.12 |
| uv | >= 0.5 |
| Node.js | >= 20 |
| Docker + Compose | Optional |

Verify the environment:

```bash
make env-check
```

## Install

```bash
make install
```

This runs the backend `uv` installation and frontend `npm` installation and creates `backend/.env` from the example when needed.

## Run Locally

```bash
make dev
```

Or:

```bash
make dev-backend
make dev-frontend
```

Default endpoints:

```text
Frontend: http://localhost:5173
Backend:  http://localhost:8000
Swagger:  http://localhost:8000/docs
```

## Make Targets

| Target | Description |
|---|---|
| `make help` | Show all targets |
| `make env-check` | Verify required tools |
| `make install` | Install backend and frontend dependencies |
| `make dev` | Start backend and frontend |
| `make dev-backend` | FastAPI with hot reload |
| `make dev-frontend` | Vite dev server |
| `make test` | Run backend tests |
| `make test-verbose` | Run tests with full output |
| `make test-unit` | Unit tests |
| `make test-api` | API integration tests |
| `make lint` | Run Ruff |
| `make build` | Build frontend |
| `make docker-up` | Start Docker stack in foreground |
| `make docker-up-d` | Start Docker stack detached |
| `make docker-down` | Stop containers |
| `make docker-down-v` | Stop and delete volumes |
| `make docker-logs` | Tail container logs |
| `make docker-rebuild` | Rebuild and restart |
| `make openapi-dump` | Dump OpenAPI spec |
| `make add-backend-dep PKG=x` | Add backend package through uv |
| `make migrate` | Apply migrations |
| `make migrate-create MSG="..."` | Generate migration |
| `make migrate-rollback` | Roll back one migration |
| `make migrate-history` | Show migration history |
| `make clean` | Remove build artifacts |
| `make clean-all` | Also remove virtual environment and node_modules |

`make help` is the authoritative complete command reference.

## Docker Stack

```bash
make docker-up-d
```

The Docker Compose stack contains:

- frontend;
- FastAPI backend;
- PostgreSQL;
- Redis.

Useful operations:

```bash
make docker-logs
make docker-down
make docker-down-v
make docker-rebuild
```

## Testing

```bash
make test
make test-verbose
make test-unit
make test-api
```

Direct pytest execution:

```bash
cd backend
uv run pytest -v
```

Lint:

```bash
make lint
```

## Configuration

Settings are environment-driven through `backend/core/config.py`.

### Core infrastructure

```bash
DATABASE_URL=...
REDIS_URL=redis://localhost:6379/0
USE_REDIS=false
DEBUG=false
```

### Simulation

```bash
SIM_STEP_DELAY_SECONDS=0.5
COMM_DELAY_SECONDS=2.5
ROVER_BATTERY_CAPACITY=1000.0
ROVER_MOVE_COST=10.0
PHYSICS_ELEVATION_COST_FACTOR=0.5
PHYSICS_THERMAL_ANOMALY_SCALE=1.0
```

### RL planner

```bash
RL_EPISODE_BUDGET=500
RL_WEIGHT_TARGET=2.0
RL_WEIGHT_TERRAIN=1.0
RL_WEIGHT_GEYSER=3.0
```

### Fog of war and autonomy

```bash
FOG_OF_WAR=true
SENSOR_RANGE=2
FPS_WHEEL_STUCK_RETRY_LIMIT=2
FPS_COMM_LOSS_RETRY_LIMIT=2
FPS_SAFE_MODE_BATTERY_PCT=10.0
AEGIS_MAX_AUTO_OBJECTIVES=10
```

### Dynamic terrain

```bash
TERRAIN_GEYSER_CYCLE_TICKS=15
TERRAIN_GEYSER_FLIP_PROB=0.35
TERRAIN_FRACTURE_PROB_PER_TICK=0.004
TERRAIN_FROST_PERIOD_TICKS=20
TERRAIN_FROST_COST_FACTOR=1.4
```

### Communications

```bash
COMM_SLOT_SECONDS=60
COMM_WINDOW_DURATION_SECONDS=15
```

### Claude

```bash
ANTHROPIC_API_KEY=...
CLAUDE_MODEL=claude-sonnet-4-6
CLAUDE_MAX_TOKENS=4096
```

If the API key is absent, the explainability integration falls back gracefully rather than preventing mission execution.

## Database Migrations

```bash
make migrate
make migrate-create MSG="add user preferences table"
make migrate-rollback
make migrate-history
```

Local development uses SQLite by default; PostgreSQL is selected with `DATABASE_URL`.

## Redis Event Bus

Enable Redis Streams without code changes:

```bash
USE_REDIS=true
REDIS_URL=redis://localhost:6379/0
```

If Redis is unreachable, the application falls back to `InMemoryEventBus`.

## Adding a Planner

1. Add a planner under `backend/services/planning_service/`.
2. Implement the shared planner interface.
3. Add a value to `PlannerType`.
4. Register planner construction/dispatch in `PlanningService`.
5. Add tests.
6. Expose the option through API/UI when appropriate.

The A* and RL implementations are useful references.

## Adding an Anomaly Type

1. Add the type to `AnomalyType`.
2. Add detection/injection logic to the anomaly engine.
3. Add FPS behavior when needed.
4. Add explainability text/context.
5. Add tests.
6. Update documentation.

## Claude Integration

Claude integration lives in the explainability service.

The LLM context contains structured mission information such as:

- mission and planner;
- objectives and completion state;
- command-type breakdown;
- compressed plan-step sequence;
- battery cost and rationale;
- environment information.

The LLM is an explanation layer rather than the source of operational state.

## Roadmap

### V1 — Complete

- Mission CRUD and environment generation
- A* terrain-aware planning
- Rover digital twin
- Command execution and simulated delay
- Anomaly injection/basic recovery
- REST/OpenAPI
- WebSocket telemetry
- Explainability API
- React mission-control UI
- theme switching
- objective generation
- anomaly resolution
- plan-step inspection
- unit/integration testing

### V2 — Complete

- async SQLAlchemy persistence
- SQLite/PostgreSQL support
- repository pattern
- Alembic
- Redis Streams
- telemetry charts
- multiple concurrent rovers
- mission editing/deletion
- recovery side effects
- plan resume
- timeline playback

### V3 — Complete

- RL value-function planner
- multi-agent objective distribution
- Claude SSE explanations
- physics-aware elevation/terrain
- 3D visualization
- full anomaly-history UI

### V4 — Complete

- fog of war
- tiered Fault Protection System
- dynamic terrain events
- enriched telemetry
- improved explainability context/UI
- science-value heatmap
- science-ROI coordination
- AEGIS-style target selection
- supervised/semi/fully autonomous rover modes
- communication windows and queued uplinks

### V5 — Planned / Backlog

Candidate future work includes:

- sample chain of custody;
- opportunistic science;
- shared hazard maps and dynamic replanning;
- instrument-health dashboard;
- operations metrics;
- resource-aware mission scheduling;
- multi-mission fleet view;
- mission replay and what-if analysis.

## Contributor / Agent Instructions

See [`../CLAUDE.md`](../CLAUDE.md) for repository-specific contribution and AI-agent instructions, including package-management, testing, and documentation-update conventions.
