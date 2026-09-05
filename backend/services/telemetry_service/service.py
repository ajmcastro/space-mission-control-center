"""Anomaly-resolution business logic, extracted so it can be called both from
the direct HTTP endpoint and from the comm-window uplink dispatcher (V4)."""
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.anomaly import Anomaly, AnomalyType
from core.models.rover import RoverState
from core.repositories import AnomalyRepository, RoverRepository

_anomaly_repo = AnomalyRepository()
_rover_repo = RoverRepository()


async def resolve_anomaly(session: AsyncSession, anomaly_id: str, resolution: str) -> Anomaly | None:
    anomaly = await _anomaly_repo.resolve(session, anomaly_id, resolution)
    if not anomaly:
        return None

    rover = await _rover_repo.get(session, anomaly.rover_id)
    if rover:
        # Dismissing a comm_loss restores the rover to IDLE so the operator can re-run the plan.
        if anomaly.type == AnomalyType.COMM_LOSS and rover.state == RoverState.COMM_LOST:
            rover.state = RoverState.IDLE
            rover.anomaly_streak = 0
            await _rover_repo.save(session, rover)

        # Dismissing a low_battery triggers an emergency recharge to full capacity.
        elif anomaly.type == AnomalyType.LOW_BATTERY:
            rover.battery = rover.spec.max_battery
            rover.state = RoverState.IDLE
            rover.anomaly_streak = 0
            await _rover_repo.save(session, rover)

        # Exiting safe mode — reset FPS state so the operator can re-run the plan.
        elif rover.state == RoverState.SAFE_MODE:
            rover.state = RoverState.IDLE
            rover.anomaly_streak = 0
            rover.safe_mode_reason = None
            await _rover_repo.save(session, rover)

        # Ground-control override: dismiss any anomaly when rover is stuck.
        # Restores IDLE so the operator can re-run the plan from the rover's current position.
        elif rover.state == RoverState.STUCK:
            rover.state = RoverState.IDLE
            rover.anomaly_streak = 0
            await _rover_repo.save(session, rover)

    return anomaly
