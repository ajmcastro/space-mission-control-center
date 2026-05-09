from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.plan import Plan
from api.deps import get_planning_service, get_session
from .service import PlanningService
from .schemas import PlanRequest, WaypointRequest

router = APIRouter(prefix="/planning", tags=["planning"])


@router.post("/auto", response_model=Plan, status_code=201)
async def auto_plan(
    request: PlanRequest,
    svc: PlanningService = Depends(get_planning_service),
    session: AsyncSession = Depends(get_session),
) -> Plan:
    plan = await svc.create_plan(session, request)
    if not plan:
        raise HTTPException(404, "Mission or environment not found")
    return plan


@router.post("/manual", response_model=Plan, status_code=201)
async def manual_plan(
    request: WaypointRequest,
    svc: PlanningService = Depends(get_planning_service),
    session: AsyncSession = Depends(get_session),
) -> Plan:
    plan = await svc.create_manual_plan(session, request)
    if not plan:
        raise HTTPException(404, "Mission or environment not found")
    return plan


@router.get("/{plan_id}", response_model=Plan)
async def get_plan(
    plan_id: str,
    svc: PlanningService = Depends(get_planning_service),
    session: AsyncSession = Depends(get_session),
) -> Plan:
    plan = await svc.get_plan(session, plan_id)
    if not plan:
        raise HTTPException(404, f"Plan {plan_id} not found")
    return plan


@router.get("/mission/{mission_id}", response_model=Plan)
async def get_mission_plan(
    mission_id: str,
    svc: PlanningService = Depends(get_planning_service),
    session: AsyncSession = Depends(get_session),
) -> Plan:
    plan = await svc.get_mission_plan(session, mission_id)
    if not plan:
        raise HTTPException(404, f"No plan for mission {mission_id}")
    return plan


@router.get("/mission/{mission_id}/all", response_model=list[Plan])
async def list_mission_plans(
    mission_id: str,
    svc: PlanningService = Depends(get_planning_service),
    session: AsyncSession = Depends(get_session),
) -> list[Plan]:
    return await svc.list_plans_for_mission(session, mission_id)
