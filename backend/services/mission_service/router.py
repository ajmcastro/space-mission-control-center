from fastapi import APIRouter, HTTPException, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.mission import Mission
from core.models.environment import Environment
from api.deps import get_mission_service, get_session, get_simulation_service
from .service import MissionService
from .schemas import MissionCreate, MissionUpdate

router = APIRouter(prefix="/missions", tags=["missions"])


@router.post("/", response_model=Mission, status_code=201)
async def create_mission(
    data: MissionCreate,
    svc: MissionService = Depends(get_mission_service),
    session: AsyncSession = Depends(get_session),
) -> Mission:
    return await svc.create_mission(session, data)


@router.get("/", response_model=list[Mission])
async def list_missions(
    svc: MissionService = Depends(get_mission_service),
    session: AsyncSession = Depends(get_session),
) -> list[Mission]:
    return await svc.list_missions(session)


@router.get("/{mission_id}", response_model=Mission)
async def get_mission(
    mission_id: str,
    svc: MissionService = Depends(get_mission_service),
    session: AsyncSession = Depends(get_session),
) -> Mission:
    mission = await svc.get_mission(session, mission_id)
    if not mission:
        raise HTTPException(404, f"Mission {mission_id} not found")
    return mission


@router.patch("/{mission_id}", response_model=Mission)
async def update_mission(
    mission_id: str,
    data: MissionUpdate,
    svc: MissionService = Depends(get_mission_service),
    session: AsyncSession = Depends(get_session),
) -> Mission:
    mission = await svc.update_mission(session, mission_id, data)
    if not mission:
        raise HTTPException(404, f"Mission {mission_id} not found")
    return mission


@router.post("/{mission_id}/start", response_model=Mission)
async def start_mission(
    mission_id: str,
    svc: MissionService = Depends(get_mission_service),
    session: AsyncSession = Depends(get_session),
) -> Mission:
    mission = await svc.start_mission(session, mission_id)
    if not mission:
        raise HTTPException(400, "Cannot start mission — check status and existence")
    return mission


@router.post("/{mission_id}/complete", response_model=Mission)
async def complete_mission(
    mission_id: str,
    svc: MissionService = Depends(get_mission_service),
    session: AsyncSession = Depends(get_session),
) -> Mission:
    mission = await svc.complete_mission(session, mission_id)
    if not mission:
        raise HTTPException(404, f"Mission {mission_id} not found")
    return mission


@router.delete("/{mission_id}", status_code=204)
async def delete_mission(
    mission_id: str,
    svc: MissionService = Depends(get_mission_service),
    sim_svc=Depends(get_simulation_service),
    session: AsyncSession = Depends(get_session),
) -> Response:
    await sim_svc.stop_simulation(mission_id)
    deleted = await svc.delete_mission(session, mission_id)
    if not deleted:
        raise HTTPException(404, f"Mission {mission_id} not found")
    return Response(status_code=204)


@router.get("/{mission_id}/environment", response_model=Environment)
async def get_mission_environment(
    mission_id: str,
    svc: MissionService = Depends(get_mission_service),
    session: AsyncSession = Depends(get_session),
) -> Environment:
    env = await svc.get_mission_environment(session, mission_id)
    if not env:
        raise HTTPException(404, "Environment not found")
    return env
