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

## Adding an Anomaly Type

1. Add to `AnomalyType` in `core/models/anomaly.py`
2. Add detection logic in `simulation_service/anomaly_engine.py`
3. Add FPS behavior when needed.
4. Add impact/recommendation text in `explainability_service/service.py`
5. Add tests.
6. Update documentation.

## Claude Integration

Claude is already wired in `explainability_service/service.py`. To activate it:

```bash
# backend/.env
ANTHROPIC_API_KEY=sk-ant-...
CLAUDE_MODEL=claude-sonnet-4-6   # default
```

The `GET /api/v1/explain/llm/{subject}/{id}` endpoint streams a Server-Sent Events response. In the UI, click **Ask Claude** in the Explain tab. If the key is absent, the endpoint returns a plain-text fallback message — no errors or crashes.

The streamed response is rendered as Markdown using `react-markdown` with theme-matched component overrides (see `MissionView.tsx` → Claude Analysis section).

`_build_llm_context()` in `explainability_service/service.py` builds the user message sent to Claude. It now includes: mission name and planner type; objectives list with type, target, priority, and completion status; command-type breakdown (e.g. `move×47, collect_sample×3`); the full step sequence capped at 120 entries (MOVE runs compressed to `... N MOVE step(s) ...`, non-MOVE steps shown with target coordinates, battery cost, and rationale); and environment data (grid size, geyser count, temperature, night-cycle status). Extend it here to feed Claude additional context.

The LLM context contains structured mission information such as:

- mission and planner;
- objectives and completion state;
- command-type breakdown;
- compressed plan-step sequence;
- battery cost and rationale;
- environment information.

The LLM is an explanation layer rather than the source of operational state.

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


## Contributor / Agent Instructions

See [`../CLAUDE.md`](../CLAUDE.md) for repository-specific contribution and AI-agent instructions, including package-management, testing, and documentation-update conventions.
