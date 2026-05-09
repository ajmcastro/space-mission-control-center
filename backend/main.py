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
from core.events.memory_bus import InMemoryEventBus

from services.mission_service.service import MissionService
from services.planning_service.service import PlanningService
from services.simulation_service.service import SimulationService
from services.explainability_service.service import ExplainabilityService

from services.mission_service.router import router as mission_router
from services.planning_service.router import router as planning_router
from services.simulation_service.router import router as simulation_router
from services.telemetry_service.router import router as telemetry_router
from services.explainability_service.router import router as explain_router

log = structlog.get_logger(__name__)


async def _telemetry_ws_listener(bus: InMemoryEventBus) -> None:
    """Forward telemetry bus events to connected WebSocket clients."""
    from services.telemetry_service.router import manager as ws_manager
    async for event in bus.subscribe(settings.telemetry_stream):
        if event.payload:
            await ws_manager.broadcast(event.mission_id or "", {
                "type": "telemetry",
                "data": event.payload,
            })


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("startup", app=settings.app_name, version=settings.app_version)

    # Initialise database tables (idempotent; Alembic manages schema in prod)
    await create_tables()

    # Bootstrap the event bus (in-memory for V1/V2; swap to RedisStreamBus for V2.1)
    bus = InMemoryEventBus()
    await bus.connect()

    # Wire up singleton services — SimulationService gets the session factory
    # so its background execution tasks can create their own DB sessions
    app.state.event_bus = bus
    app.state.mission_service = MissionService(bus)
    app.state.planning_service = PlanningService(bus)
    app.state.simulation_service = SimulationService(bus, AsyncSessionLocal)
    app.state.explainability_service = ExplainabilityService()

    # Start background listener that pushes telemetry events to WebSocket clients
    listener_task = asyncio.create_task(
        _telemetry_ws_listener(bus), name="telemetry-ws-listener"
    )

    log.info("services_ready", bus=bus.__class__.__name__)
    yield

    listener_task.cancel()
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


@app.get("/", tags=["health"])
async def root() -> dict:
    return {"status": "nominal", "system": settings.app_name, "version": settings.app_version}


@app.get("/health", tags=["health"])
async def health() -> dict:
    return {"status": "ok"}
