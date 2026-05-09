from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_explainability_service, get_session
from .service import ExplainabilityService

router = APIRouter(prefix="/explain", tags=["explainability"])


@router.get("/plan/{plan_id}")
async def explain_plan(
    plan_id: str,
    svc: ExplainabilityService = Depends(get_explainability_service),
    session: AsyncSession = Depends(get_session),
) -> dict:
    result = await svc.explain_plan(session, plan_id)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result


@router.get("/mission/{mission_id}")
async def explain_mission(
    mission_id: str,
    svc: ExplainabilityService = Depends(get_explainability_service),
    session: AsyncSession = Depends(get_session),
) -> dict:
    result = await svc.explain_mission(session, mission_id)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result


@router.get("/anomaly/{anomaly_id}")
async def explain_anomaly(
    anomaly_id: str,
    svc: ExplainabilityService = Depends(get_explainability_service),
    session: AsyncSession = Depends(get_session),
) -> dict:
    result = await svc.explain_anomaly(session, anomaly_id)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result
