import asyncio
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Query, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.telemetry import TelemetryEvent
from core.models.anomaly import Anomaly, AnomalyResolution, AnomalyType
from core.models.rover import RoverState
from core.repositories import TelemetryRepository, AnomalyRepository, RoverRepository
from core.events import MissionEvent, EventType
from api.deps import get_session

router = APIRouter(prefix="/telemetry", tags=["telemetry"])

_telemetry_repo = TelemetryRepository()
_anomaly_repo = AnomalyRepository()
_rover_repo = RoverRepository()


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
    limit: int = Query(default=100, le=1000),
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


@router.post("/anomalies/{mission_id}/dismiss-all", response_model=list[Anomaly])
async def dismiss_all_anomalies(
    mission_id: str,
    session: AsyncSession = Depends(get_session),
) -> list[Anomaly]:
    """Resolve all pending anomalies for a mission as ignored."""
    anomalies = await _anomaly_repo.get_for_mission(session, mission_id)
    resolved = []
    for a in anomalies:
        if a.resolution == AnomalyResolution.PENDING:
            updated = await _anomaly_repo.resolve(session, a.id, AnomalyResolution.IGNORED.value)
            if updated:
                resolved.append(updated)
    await session.commit()
    return resolved


@router.patch("/anomalies/{anomaly_id}/resolve", response_model=Anomaly)
async def resolve_anomaly(
    anomaly_id: str,
    body: ResolveAnomalyRequest,
    session: AsyncSession = Depends(get_session),
) -> Anomaly:
    anomaly = await _anomaly_repo.resolve(session, anomaly_id, body.resolution.value)
    if not anomaly:
        raise HTTPException(404, f"Anomaly {anomaly_id} not found")

    # Dismissing a comm_loss restores the rover to IDLE so the operator can re-run the plan
    if anomaly.type == AnomalyType.COMM_LOSS:
        rover = await _rover_repo.get(session, anomaly.rover_id)
        if rover and rover.state == RoverState.COMM_LOST:
            rover.state = RoverState.IDLE
            await _rover_repo.save(session, rover)

    # Dismissing a low_battery triggers an emergency recharge to full capacity
    if anomaly.type == AnomalyType.LOW_BATTERY:
        rover = await _rover_repo.get(session, anomaly.rover_id)
        if rover:
            rover.battery = rover.spec.max_battery
            rover.state = RoverState.IDLE
            await _rover_repo.save(session, rover)

    await session.commit()
    return anomaly


async def push_telemetry_event(event: MissionEvent) -> None:
    """Called by the event bus listener in main.py to push telemetry to WebSocket clients."""
    payload = event.payload
    if payload:
        await manager.broadcast(event.mission_id or "", {
            "type": "telemetry",
            "data": payload,
        })
