from fastapi import APIRouter, Depends

from core.models.comm import UplinkCommand
from api.deps import get_comm_service
from .service import CommWindowService
from .schemas import CommStatusResponse

router = APIRouter(prefix="/comm", tags=["comm"])


@router.get("/status", response_model=CommStatusResponse)
async def comm_status(
    svc: CommWindowService = Depends(get_comm_service),
) -> CommStatusResponse:
    return svc.status()


@router.get("/{mission_id}/queue", response_model=list[UplinkCommand])
async def comm_queue(
    mission_id: str,
    svc: CommWindowService = Depends(get_comm_service),
) -> list[UplinkCommand]:
    return svc.queue_for(mission_id)
