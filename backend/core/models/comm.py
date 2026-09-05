from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4
from pydantic import BaseModel, Field


class UplinkKind(str, Enum):
    """The ground-control actions gated by communication windows."""
    RESOLVE_ANOMALY = "resolve_anomaly"
    SET_AUTONOMY = "set_autonomy"
    AEGIS_APPROVE = "aegis_approve"
    AEGIS_REJECT = "aegis_reject"


class UplinkCommand(BaseModel):
    """A ground command submitted while the comm window was closed, held in the
    uplink queue until the next window opens."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    mission_id: str
    rover_id: str
    kind: UplinkKind
    payload: dict = Field(default_factory=dict)
    queued_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    delivered: bool = False
    delivered_at: datetime | None = None
