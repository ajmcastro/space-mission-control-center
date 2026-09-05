"""Communication window gate + uplink queue (V4).

Ground-control actions that intervene on an already-running rover (resolving
an anomaly, changing autonomy level, approving/rejecting an AEGIS proposal)
are only delivered immediately if a comm window is open; otherwise they are
held in an in-memory uplink queue and delivered the next time `flush_ready`
finds a window open. The onboard plan execution loop is never gated — rovers
keep executing their current plan autonomously regardless of window state.
"""
from datetime import datetime, timezone
from typing import Awaitable, Callable

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.models.comm import UplinkCommand, UplinkKind
from core.models.anomaly import Anomaly, AnomalyResolution
from core.models.rover import AutonomyLevel, Rover
from core.events import EventBus, MissionEvent, EventType
from core.config import settings
from . import windows
from .schemas import CommStatusResponse, UplinkResult

log = structlog.get_logger(__name__)

ResolveAnomalyFn = Callable[[AsyncSession, str, str], Awaitable[Anomaly | None]]


class CommWindowService:
    def __init__(self, event_bus: EventBus, session_factory: async_sessionmaker) -> None:
        self._bus = event_bus
        self._session_factory = session_factory
        self._queue: dict[str, list[UplinkCommand]] = {}   # mission_id -> pending items
        self._simulation = None
        self._resolve_anomaly_fn: ResolveAnomalyFn | None = None

    def wire(self, simulation_service, resolve_anomaly_fn: ResolveAnomalyFn) -> None:
        """Late-bind the collaborators needed to actually deliver a queued command.
        Called once at startup after every singleton service has been constructed."""
        self._simulation = simulation_service
        self._resolve_anomaly_fn = resolve_anomaly_fn

    def status(self) -> CommStatusResponse:
        return CommStatusResponse(
            open=windows.is_window_open(),
            seconds_until_next_open=round(windows.seconds_until_next_open(), 1),
            seconds_until_close=round(windows.seconds_until_close(), 1),
            slot_seconds=settings.comm_slot_seconds,
            window_duration_seconds=settings.comm_window_duration_seconds,
        )

    def queue_for(self, mission_id: str) -> list[UplinkCommand]:
        return list(self._queue.get(mission_id, []))

    async def enqueue(
        self, mission_id: str, rover_id: str, kind: UplinkKind, payload: dict
    ) -> UplinkCommand:
        item = UplinkCommand(mission_id=mission_id, rover_id=rover_id, kind=kind, payload=payload)
        self._queue.setdefault(mission_id, []).append(item)
        await self._bus.publish(MissionEvent(
            type=EventType.UPLINK_QUEUED,
            stream=settings.mission_stream,
            mission_id=mission_id,
            rover_id=rover_id,
            payload={
                "uplink_id": item.id,
                "kind": kind.value,
                "eta_seconds": round(windows.seconds_until_next_open(), 1),
            },
        ))
        log.info("uplink_queued", mission_id=mission_id, rover_id=rover_id, kind=kind.value)
        return item

    async def gate(
        self,
        session: AsyncSession,
        mission_id: str,
        rover_id: str,
        kind: UplinkKind,
        payload: dict,
    ) -> UplinkResult:
        """Execute immediately if a comm window is currently open; otherwise queue it."""
        if windows.is_window_open():
            result = await self._deliver_one(session, kind, rover_id, mission_id, payload)
            return UplinkResult(delivered=True, result=result)
        item = await self.enqueue(mission_id, rover_id, kind, payload)
        return UplinkResult(delivered=False, uplink=item)

    async def flush_ready(self) -> None:
        """Deliver every queued uplink command, across all missions, while a window is open."""
        if not self._queue or not windows.is_window_open():
            return
        async with self._session_factory() as session:
            for mission_id, items in list(self._queue.items()):
                delivered_ids: set[str] = set()
                for item in items:
                    try:
                        result = await self._deliver_one(
                            session, item.kind, item.rover_id, item.mission_id, item.payload
                        )
                    except Exception:
                        log.exception(
                            "uplink_delivery_failed", uplink_id=item.id, kind=item.kind.value
                        )
                        await session.rollback()
                        continue
                    item.delivered = True
                    item.delivered_at = datetime.now(timezone.utc)
                    delivered_ids.add(item.id)
                    await self._bus.publish(MissionEvent(
                        type=EventType.UPLINK_DELIVERED,
                        stream=settings.mission_stream,
                        mission_id=mission_id,
                        rover_id=item.rover_id,
                        payload={"uplink_id": item.id, "kind": item.kind.value, "result": result},
                    ))
                    log.info(
                        "uplink_delivered", mission_id=mission_id,
                        uplink_id=item.id, kind=item.kind.value,
                    )
                if delivered_ids:
                    self._queue[mission_id] = [i for i in items if i.id not in delivered_ids]

    async def _deliver_one(
        self,
        session: AsyncSession,
        kind: UplinkKind,
        rover_id: str,
        mission_id: str,
        payload: dict,
    ) -> dict | None:
        if kind == UplinkKind.RESOLVE_ANOMALY:
            assert self._resolve_anomaly_fn is not None
            anomaly = await self._resolve_anomaly_fn(
                session, payload["anomaly_id"], payload.get("resolution", AnomalyResolution.IGNORED.value)
            )
            await session.commit()
            return anomaly.model_dump(mode="json") if anomaly else None

        assert self._simulation is not None
        if kind == UplinkKind.SET_AUTONOMY:
            rover: Rover | None = await self._simulation.set_autonomy_level(
                session, rover_id, AutonomyLevel(payload["level"])
            )
            return rover.model_dump(mode="json") if rover else None
        if kind == UplinkKind.AEGIS_APPROVE:
            ok = await self._simulation.approve_aegis_proposal(session, mission_id, rover_id)
            return {"approved": ok}
        if kind == UplinkKind.AEGIS_REJECT:
            ok = await self._simulation.reject_aegis_proposal(rover_id)
            return {"rejected": ok}
        raise ValueError(f"Unknown uplink kind: {kind}")
