import asyncio
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Query, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.telemetry import TelemetryEvent
from core.models.anomaly import Anomaly, AnomalyResolution
from core.models.comm import UplinkKind
from core.repositories import TelemetryRepository, AnomalyRepository
from core.events import MissionEvent, EventType
from api.deps import get_session, get_comm_service
from services.comm_service.service import CommWindowService
from services.comm_service.schemas import UplinkResult

router = APIRouter(prefix="/telemetry", tags=["telemetry"])

_telemetry_repo = TelemetryRepository()
_anomaly_repo = AnomalyRepository()


class ResolveAnomalyRequest(BaseModel):
    resolution: AnomalyResolution = AnomalyResolution.IGNORED


class ConnectionManager:
    """WebSocket connection manager for telemetry push."""

    def __init__(self) -> None:
        self._connections: dict[str, list[WebSocket]] = {}

    async def connect(self, ws: WebSocket, mission_id: str) -> None:
        await ws.accept()
        self._connections.setdefault(mission_id, []).append(ws)

    def disconnect(self, ws: WebSocket, mission_id: str) -> None:
        conns = self._connections.get(mission_id, [])
        if ws in conns:
            conns.remove(ws)

    async def broadcast(self, mission_id: str, data: dict) -> None:
        dead: list[WebSocket] = []
        for ws in self._connections.get(mission_id, []):
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws, mission_id)

    async def broadcast_all(self, data: dict) -> None:
        for mission_id in list(self._connections.keys()):
            await self.broadcast(mission_id, data)


manager = ConnectionManager()


@router.websocket("/ws/{mission_id}")
async def telemetry_ws(ws: WebSocket, mission_id: str) -> None:
    """Stream real-time telemetry for a mission via WebSocket."""
    from core.database import AsyncSessionLocal
    await manager.connect(ws, mission_id)
    try:
        async with AsyncSessionLocal() as session:
            history = await _telemetry_repo.get_for_mission(session, mission_id, limit=50)
        for event in history:
            await ws.send_json({"type": "history", "data": event.model_dump(mode="json")})

        while True:
            await asyncio.sleep(30)
            await ws.send_json({"type": "ping"})
    except WebSocketDisconnect:
        manager.disconnect(ws, mission_id)


@router.get("/events/{mission_id}", response_model=list[TelemetryEvent])
async def get_telemetry(
    mission_id: str,
    limit: int = Query(default=100, le=10000),
    session: AsyncSession = Depends(get_session),
) -> list[TelemetryEvent]:
    return await _telemetry_repo.get_for_mission(session, mission_id, limit=limit)


@router.get("/anomalies", response_model=list[Anomaly])
async def get_all_anomalies(session: AsyncSession = Depends(get_session)) -> list[Anomaly]:
    return await _anomaly_repo.get_all(session)


@router.get("/anomalies/{mission_id}", response_model=list[Anomaly])
async def get_mission_anomalies(
    mission_id: str,
    session: AsyncSession = Depends(get_session),
) -> list[Anomaly]:
    return await _anomaly_repo.get_for_mission(session, mission_id)


@router.post("/anomalies/{mission_id}/dismiss-all")
async def dismiss_all_anomalies(
    mission_id: str,
    session: AsyncSession = Depends(get_session),
    comm: CommWindowService = Depends(get_comm_service),
) -> dict:
    """Resolve all pending anomalies for a mission as ignored — each one individually
    gated by the comm window, same as a single dismiss (see resolve_anomaly)."""
    anomalies = await _anomaly_repo.get_for_mission(session, mission_id)
    results: list[UplinkResult] = []
    for a in anomalies:
        if a.resolution == AnomalyResolution.PENDING:
            results.append(await comm.gate(
                session, mission_id, a.rover_id, UplinkKind.RESOLVE_ANOMALY,
                {"anomaly_id": a.id, "resolution": AnomalyResolution.IGNORED.value},
            ))
    await session.commit()
    return {
        "delivered": [r.result for r in results if r.delivered],
        "queued": [r.uplink for r in results if not r.delivered],
    }


@router.patch("/anomalies/{anomaly_id}/resolve", response_model=UplinkResult)
async def resolve_anomaly(
    anomaly_id: str,
    body: ResolveAnomalyRequest,
    session: AsyncSession = Depends(get_session),
    comm: CommWindowService = Depends(get_comm_service),
) -> UplinkResult:
    anomaly = await _anomaly_repo.get(session, anomaly_id)
    if not anomaly:
        raise HTTPException(404, f"Anomaly {anomaly_id} not found")

    result = await comm.gate(
        session, anomaly.mission_id, anomaly.rover_id, UplinkKind.RESOLVE_ANOMALY,
        {"anomaly_id": anomaly_id, "resolution": body.resolution.value},
    )
    await session.commit()
    return result


async def push_telemetry_event(event: MissionEvent) -> None:
    """Called by the event bus listener in main.py to push telemetry to WebSocket clients."""
    payload = event.payload
    if payload:
        await manager.broadcast(event.mission_id or "", {
            "type": "telemetry",
            "data": payload,
        })
