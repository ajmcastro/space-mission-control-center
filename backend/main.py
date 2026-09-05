"""
Enceladus Mission Control — unified FastAPI entry point (V2).
All services run in a single process; state is persisted to SQLite (dev) or PostgreSQL (prod).
"""
import asyncio
import contextlib
import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.database import create_tables, AsyncSessionLocal
from core.events.bus import EventBus
from core.events.memory_bus import InMemoryEventBus
from core.events.redis_bus import RedisStreamBus

from services.mission_service.service import MissionService
from services.planning_service.service import PlanningService
from services.simulation_service.service import SimulationService
from services.explainability_service.service import ExplainabilityService
from services.comm_service.service import CommWindowService

from services.mission_service.router import router as mission_router
from services.planning_service.router import router as planning_router
from services.simulation_service.router import router as simulation_router
from services.telemetry_service.router import router as telemetry_router
from services.explainability_service.router import router as explain_router
from services.comm_service.router import router as comm_router

log = structlog.get_logger(__name__)


async def _telemetry_ws_listener(bus: EventBus) -> None:
    """Forward telemetry bus events to connected WebSocket clients."""
    from services.telemetry_service.router import manager as ws_manager
    async for event in bus.subscribe(settings.telemetry_stream):
        if event.payload:
            await ws_manager.broadcast(event.mission_id or "", {
                "type": "telemetry",
                "data": event.payload,
            })


async def _event_persist_listener(bus: EventBus) -> None:
    """
    Persist key bus events to the telemetry DB so they appear in the REST endpoint.

    The executor already persists POSITION/SAMPLE_COLLECTED/STATE_CHANGE rows for
    every executed command.  This listener covers everything else: anomalies, FPS
    decisions, terrain changes, mission lifecycle, and replanning.

    TELEMETRY_EMITTED and CELLS_REVEALED are intentionally skipped (already
    persisted by the executor and too noisy respectively).
    """
    from core.events.types import EventType
    from core.models.telemetry import TelemetryEvent, TelemetryType
    from core.repositories import TelemetryRepository

    _SKIP = {EventType.TELEMETRY_EMITTED, EventType.CELLS_REVEALED, EventType.ROVER_MOVED}

    _TYPE_MAP: dict[EventType, TelemetryType] = {
        # Anomalies
        EventType.ANOMALY_DETECTED:     TelemetryType.ANOMALY_DETECTED,
        EventType.ANOMALY_RESOLVED:     TelemetryType.ANOMALY_DETECTED,
        # Rover state
        EventType.ROVER_STATE_CHANGED:  TelemetryType.STATE_CHANGE,
        EventType.SAMPLE_COLLECTED:     TelemetryType.SAMPLE_COLLECTED,
        # Fault Protection System
        EventType.FPS_RULE_TRIGGERED:   TelemetryType.MISSION_EVENT,
        EventType.SAFE_MODE_ENTERED:    TelemetryType.STATE_CHANGE,
        EventType.SAFE_MODE_EXITED:     TelemetryType.STATE_CHANGE,
        # Planning
        EventType.REPLAN_TRIGGERED:     TelemetryType.MISSION_EVENT,
        EventType.PLAN_CREATED:         TelemetryType.MISSION_EVENT,
        # Dynamic terrain
        EventType.GEYSER_ERUPTION:      TelemetryType.MISSION_EVENT,
        EventType.GEYSER_DORMANCY:      TelemetryType.MISSION_EVENT,
        EventType.ICE_FRACTURE:         TelemetryType.MISSION_EVENT,
        EventType.FROST_CYCLE_START:    TelemetryType.MISSION_EVENT,
        EventType.FROST_CYCLE_END:      TelemetryType.MISSION_EVENT,
        # Mission lifecycle
        EventType.MISSION_STARTED:      TelemetryType.MISSION_EVENT,
        EventType.MISSION_COMPLETED:    TelemetryType.MISSION_EVENT,
        EventType.MISSION_FAILED:       TelemetryType.MISSION_EVENT,
        EventType.MISSION_ABORTED:      TelemetryType.MISSION_EVENT,
    }

    repo = TelemetryRepository()
    streams = [settings.telemetry_stream, settings.anomaly_stream, settings.mission_stream]

    async def _listen(stream: str) -> None:
        async for event in bus.subscribe(stream, group="persist", consumer="persist"):
            if event.type in _SKIP:
                continue
            telem_type = _TYPE_MAP.get(event.type, TelemetryType.MISSION_EVENT)
            telem = TelemetryEvent(
                type=telem_type,
                mission_id=event.mission_id or "",
                rover_id=event.rover_id or "",
                payload={"event_type": event.type.value, **event.payload},
            )
            try:
                async with AsyncSessionLocal() as session:
                    await repo.append(session, telem)
                    await session.commit()
            except Exception as exc:
                log.warning("event_persist_failed", event_type=event.type.value, error=str(exc))

    await asyncio.gather(*[_listen(s) for s in streams])


async def _comm_uplink_flusher(comm_service: CommWindowService) -> None:
    """Deliver queued uplink commands once a second whenever a comm window is open.

    Runs independently of any mission's plan-execution loop so a queued ground
    command is delivered even if the rover that triggered it later enters
    safe mode (which stops that mission's own tick loop).
    """
    while True:
        try:
            await comm_service.flush_ready()
        except Exception:
            log.exception("comm_uplink_flush_failed")
        await asyncio.sleep(1.0)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("startup", app=settings.app_name, version=settings.app_version)

    # Initialise database tables (idempotent; Alembic manages schema in prod)
    await create_tables()

    # Bootstrap the event bus — Redis when USE_REDIS=true, in-memory otherwise
    bus: EventBus
    if settings.use_redis:
        redis_bus = RedisStreamBus(settings.redis_url)
        try:
            await redis_bus.connect()
            bus = redis_bus
            log.info("event_bus", backend="redis", url=settings.redis_url)
        except Exception as exc:
            log.warning("redis_unavailable_falling_back", error=str(exc))
            bus = InMemoryEventBus()
            await bus.connect()
    else:
        bus = InMemoryEventBus()
        await bus.connect()
        log.info("event_bus", backend="in-memory")

    # Wire up singleton services — SimulationService gets the session factory
    # so its background execution tasks can create their own DB sessions
    app.state.event_bus = bus
    app.state.mission_service = MissionService(bus)
    app.state.planning_service = PlanningService(bus)
    app.state.simulation_service = SimulationService(bus, AsyncSessionLocal)
    app.state.explainability_service = ExplainabilityService()
    app.state.comm_service = CommWindowService(bus, AsyncSessionLocal)

    # Comm window service needs the simulation service (autonomy/AEGIS) and the
    # extracted anomaly-resolution logic to actually deliver a queued uplink.
    from services.telemetry_service.service import resolve_anomaly as _resolve_anomaly
    app.state.comm_service.wire(app.state.simulation_service, _resolve_anomaly)

    # Background listeners
    ws_task = asyncio.create_task(
        _telemetry_ws_listener(bus), name="telemetry-ws-listener"
    )
    persist_task = asyncio.create_task(
        _event_persist_listener(bus), name="event-persist-listener"
    )
    uplink_task = asyncio.create_task(
        _comm_uplink_flusher(app.state.comm_service), name="comm-uplink-flusher"
    )

    log.info("services_ready", bus=bus.__class__.__name__)
    yield

    ws_task.cancel()
    persist_task.cancel()
    uplink_task.cancel()
    await bus.disconnect()
    log.info("shutdown")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Digital twin mission control for Enceladus rover operations.",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(mission_router, prefix="/api/v1")
app.include_router(planning_router, prefix="/api/v1")
app.include_router(simulation_router, prefix="/api/v1")
app.include_router(telemetry_router, prefix="/api/v1")
app.include_router(explain_router, prefix="/api/v1")
app.include_router(comm_router, prefix="/api/v1")


@app.get("/", tags=["health"])
async def root() -> dict:
    return {"status": "nominal", "system": settings.app_name, "version": settings.app_version}


@app.get("/health", tags=["health"])
async def health() -> dict:
    return {"status": "ok"}
