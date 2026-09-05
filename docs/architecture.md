# Architecture

[← Back to README](../README.md)

## Overview

Enceladus Mission Control Center is a full-stack autonomous mission-control simulation. A React/TypeScript frontend communicates with a unified FastAPI backend using REST, WebSockets, and Server-Sent Events (SSE). The backend separates mission lifecycle, planning, simulation, telemetry, explainability, and communication-window responsibilities while sharing domain models, repositories, persistence, and an abstract event bus.

```text
┌──────────────────────────────────────────────────────────────────────┐
│                          Frontend (React + TS)                        │
│ Dashboard · Planner · Map (2D/3D) · Telemetry · Charts · Timeline   │
│ Explain · Anomalies · Multi-rover coordination                      │
└───────────────────────────┬──────────────────────────────────────────┘
                            │ REST + WebSocket + SSE
┌───────────────────────────▼──────────────────────────────────────────┐
│                         FastAPI Backend                              │
│                                                                      │
│ mission_service   planning_service   simulation_service              │
│ telemetry_service   explainability_service   comm_service            │
│                                                                      │
│                  Abstract Event Bus                                  │
│          InMemoryEventBus ↔ RedisStreamBus                           │
└──────────────────────┬──────────────────────────┬────────────────────┘
                       │                          │
                       ▼                          ▼
                  Redis Streams              PostgreSQL
```

## Domain Models

| Model | Description |
|---|---|
| `Mission` | Top-level mission container: status, objectives, rover list |
| `Objective` | Typed goal with target coordinates and priority |
| `Rover` | Digital twin: position, battery, state, path history |
| `Plan` | Ordered command sequence produced by a planner |
| `PlanStep` | Command plus battery estimate and rationale |
| `Command` | Typed action such as MOVE, COLLECT_SAMPLE, WAIT, CHARGE, ABORT |
| `TelemetryEvent` | Timestamped rover/mission event |
| `Anomaly` | Detected failure with type, severity, and recovery information |
| `Environment` | Grid world containing terrain, hazards, geysers, temperature, and pressure |
| `Grid` / `Cell` | Terrain representation with movement cost, elevation, reveal state, and science value |
| `UplinkCommand` | Ground command queued until an uplink window opens |

## Service Responsibilities

| Service | API prefix | Responsibility |
|---|---|---|
| Mission | `/api/v1/missions` | Mission CRUD, lifecycle, objectives, environment/elevation generation |
| Planning | `/api/v1/planning` | A*, RL, multi-agent planning, science-value optimization |
| Simulation | `/api/v1/simulation` | Rover spawn, plan execution, anomalies, FPS, AEGIS, terrain events |
| Telemetry | `/api/v1/telemetry` | Event history, WebSocket streaming, anomaly resolution |
| Explainability | `/api/v1/explain` | Structured decision context and Claude streaming explanations |
| Communications | `/api/v1/comm` | Communication-window schedule and queued uplinks |

## Backend Layers

The backend follows a layered structure:

```text
FastAPI routers
      │
      ▼
Service / domain logic
      │
      ├──────── Planning / simulation engines
      │
      ▼
Repositories
      │
      ▼
SQLAlchemy ORM
      │
      ▼
SQLite (development) / PostgreSQL
```

Pydantic domain models remain API-facing while SQLAlchemy models represent persistence. Repository classes perform the translation between those layers.

## Event-Driven Architecture

The event bus is abstracted behind `core/events/bus.py`.

Two implementations are available:

- `InMemoryEventBus` — default lightweight development implementation.
- `RedisStreamBus` — Redis Streams implementation enabled with `USE_REDIS=true`.

The in-memory implementation uses broadcast pub/sub semantics: each subscriber receives an independent copy of the event stream. This prevents concurrent consumers such as WebSocket forwarding and persistence listeners from stealing messages from one another.

A background event-persistence listener subscribes to telemetry, anomaly, and mission streams and persists important operational events, including:

- anomalies;
- FPS decisions;
- terrain changes;
- mission lifecycle events.

If Redis is configured but unavailable, the application falls back to the in-memory bus and logs a warning.

## Persistence

Local development uses SQLite by default. PostgreSQL can be selected through `DATABASE_URL`.

SQLAlchemy asynchronous sessions provide persistence and Alembic manages schema migrations.

```bash
make migrate
make migrate-create MSG="describe schema change"
make migrate-rollback
make migrate-history
```

## Frontend Architecture

The frontend is built with React and TypeScript and uses:

- Vite for development/build tooling;
- TanStack Query for server-state queries and mutations;
- Zustand for global mission state;
- Axios for REST access;
- WebSockets for telemetry;
- SSE for streamed Claude explanations;
- Recharts for telemetry visualization;
- Three.js / React Three Fiber / Drei for 3D terrain.

Major UI surfaces include the Dashboard, Mission Planner, Mission View, 2D map, 3D terrain, telemetry, charts, anomaly history, timeline playback, and explainability/debriefing.

## Real-Time Interfaces

The system deliberately uses different interfaces for different traffic patterns:

- **REST** for mission-control operations and queries.
- **WebSockets** for real-time telemetry.
- **SSE** for progressively streamed AI explanations.

## API Reference

The full OpenAPI specification is available while the backend is running:

```text
http://localhost:8000/openapi.json
```

Interactive Swagger documentation:

```text
http://localhost:8000/docs
```

Key API groups are:

```text
/api/v1/missions
/api/v1/planning
/api/v1/simulation
/api/v1/telemetry
/api/v1/explain
/api/v1/comm
```

See [API Workflows](api-workflows.md) for complete runnable examples.
