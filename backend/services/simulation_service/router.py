from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.rover import Rover
from core.models.comm import UplinkKind
from api.deps import get_simulation_service, get_session, get_comm_service
from services.comm_service.service import CommWindowService
from services.comm_service.schemas import UplinkResult
from .service import SimulationService
from .schemas import SpawnRoverRequest, RunPlanRequest, SetAutonomyRequest

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


@router.patch("/rovers/{rover_id}/autonomy", response_model=UplinkResult)
async def set_autonomy(
    rover_id: str,
    req: SetAutonomyRequest,
    svc: SimulationService = Depends(get_simulation_service),
    session: AsyncSession = Depends(get_session),
    comm: CommWindowService = Depends(get_comm_service),
) -> UplinkResult:
    rover = await svc.get_rover(session, rover_id)
    if not rover or not rover.mission_id:
        raise HTTPException(404, f"Rover {rover_id} not found")
    result = await comm.gate(
        session, rover.mission_id, rover_id, UplinkKind.SET_AUTONOMY, {"level": req.level.value}
    )
    await session.commit()
    return result


@router.get("/rovers/{rover_id}/aegis-proposal")
async def get_aegis_proposal(
    rover_id: str,
    svc: SimulationService = Depends(get_simulation_service),
) -> dict:
    proposal = svc.get_aegis_proposal(rover_id)
    if not proposal:
        return {"pending": False}
    return {
        "pending": True,
        "x": proposal.x,
        "y": proposal.y,
        "score": round(proposal.score, 3),
        "reason": proposal.reason,
    }


@router.post("/rovers/{rover_id}/aegis-proposal/approve", response_model=UplinkResult)
async def approve_aegis_proposal(
    rover_id: str,
    mission_id: str,
    svc: SimulationService = Depends(get_simulation_service),
    session: AsyncSession = Depends(get_session),
    comm: CommWindowService = Depends(get_comm_service),
) -> UplinkResult:
    if not svc.get_aegis_proposal(rover_id):
        raise HTTPException(404, "No pending AEGIS proposal for this rover")
    result = await comm.gate(session, mission_id, rover_id, UplinkKind.AEGIS_APPROVE, {})
    await session.commit()
    return result


@router.post("/rovers/{rover_id}/aegis-proposal/reject", response_model=UplinkResult)
async def reject_aegis_proposal(
    rover_id: str,
    svc: SimulationService = Depends(get_simulation_service),
    session: AsyncSession = Depends(get_session),
    comm: CommWindowService = Depends(get_comm_service),
) -> UplinkResult:
    if not svc.get_aegis_proposal(rover_id):
        raise HTTPException(404, "No pending AEGIS proposal for this rover")
    rover = await svc.get_rover(session, rover_id)
    if not rover or not rover.mission_id:
        raise HTTPException(404, f"Rover {rover_id} not found")
    result = await comm.gate(session, rover.mission_id, rover_id, UplinkKind.AEGIS_REJECT, {})
    await session.commit()
    return result
