from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.rover import Rover
from api.deps import get_simulation_service, get_session
from .service import SimulationService
from .schemas import SpawnRoverRequest, RunPlanRequest

router = APIRouter(prefix="/simulation", tags=["simulation"])


@router.post("/rovers", response_model=Rover, status_code=201)
async def spawn_rover(
    req: SpawnRoverRequest,
    svc: SimulationService = Depends(get_simulation_service),
    session: AsyncSession = Depends(get_session),
) -> Rover:
    return await svc.spawn_rover(session, req.mission_id, req.name, req.start_x, req.start_y)


@router.get("/rovers", response_model=list[Rover])
async def list_rovers(
    mission_id: str | None = None,
    svc: SimulationService = Depends(get_simulation_service),
    session: AsyncSession = Depends(get_session),
) -> list[Rover]:
    return await svc.list_rovers(session, mission_id)


@router.get("/rovers/{rover_id}", response_model=Rover)
async def get_rover(
    rover_id: str,
    svc: SimulationService = Depends(get_simulation_service),
    session: AsyncSession = Depends(get_session),
) -> Rover:
    rover = await svc.get_rover(session, rover_id)
    if not rover:
        raise HTTPException(404, f"Rover {rover_id} not found")
    return rover


@router.post("/run", status_code=202)
async def run_plan(
    req: RunPlanRequest,
    svc: SimulationService = Depends(get_simulation_service),
) -> dict:
    try:
        await svc.run_plan(req.mission_id, req.plan_id)
        return {"status": "started", "mission_id": req.mission_id, "plan_id": req.plan_id}
    except RuntimeError as e:
        raise HTTPException(409, str(e))


@router.post("/{mission_id}/stop")
async def stop_simulation(
    mission_id: str,
    svc: SimulationService = Depends(get_simulation_service),
) -> dict:
    stopped = await svc.stop_simulation(mission_id)
    return {"stopped": stopped, "mission_id": mission_id}


@router.get("/{mission_id}/status")
async def simulation_status(
    mission_id: str,
    svc: SimulationService = Depends(get_simulation_service),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await svc.get_simulation_status(session, mission_id)
