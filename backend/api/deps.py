"""
Dependency injection for FastAPI routes.
All services are singletons stored on app.state at startup.
"""
from collections.abc import AsyncGenerator
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import AsyncSessionLocal
from services.mission_service.service import MissionService
from services.planning_service.service import PlanningService
from services.simulation_service.service import SimulationService
from services.explainability_service.service import ExplainabilityService
from services.comm_service.service import CommWindowService


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


def get_mission_service(request: Request) -> MissionService:
    return request.app.state.mission_service


def get_planning_service(request: Request) -> PlanningService:
    return request.app.state.planning_service


def get_simulation_service(request: Request) -> SimulationService:
    return request.app.state.simulation_service


def get_explainability_service(request: Request) -> ExplainabilityService:
    return request.app.state.explainability_service


def get_comm_service(request: Request) -> CommWindowService:
    return request.app.state.comm_service
