from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4
from pydantic import BaseModel, Field


class AnomalyType(str, Enum):
    WHEEL_STUCK = "wheel_stuck"
    COMM_LOSS = "comm_loss"
    ENERGY_SPIKE = "energy_spike"
    SENSOR_FAULT = "sensor_fault"
    GEYSER_PROXIMITY = "geyser_proximity"
    LOW_BATTERY = "low_battery"
    PATH_BLOCKED = "path_blocked"
    UNKNOWN = "unknown"


class AnomalySeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AnomalyResolution(str, Enum):
    PENDING = "pending"
    AUTO_RECOVERED = "auto_recovered"
    REPLANNED = "replanned"
    ABORTED = "aborted"
    IGNORED = "ignored"


class Anomaly(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    type: AnomalyType
    severity: AnomalySeverity
    mission_id: str
    rover_id: str
    x: int
    y: int
    description: str = ""
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: datetime | None = None
    resolution: AnomalyResolution = AnomalyResolution.PENDING

    # Hook for replanning
    triggered_replan: bool = False
    replan_mission_id: str | None = None

    def resolve(self, resolution: AnomalyResolution) -> None:
        self.resolution = resolution
        self.resolved_at = datetime.now(timezone.utc)
