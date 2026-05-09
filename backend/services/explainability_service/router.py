import json
from typing import Literal, AsyncIterator
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
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


@router.get("/llm/{subject}/{subject_id}")
async def explain_llm_stream(
    subject: Literal["plan", "mission", "anomaly"],
    subject_id: str,
    svc: ExplainabilityService = Depends(get_explainability_service),
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    """Stream a Claude-generated explanation as Server-Sent Events."""
    async def event_generator() -> AsyncIterator[str]:
        async for chunk in svc.explain_with_claude(session, subject, subject_id):
            yield f"data: {json.dumps({'text': chunk})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
