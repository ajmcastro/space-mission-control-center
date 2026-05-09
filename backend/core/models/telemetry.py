from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4
from pydantic import BaseModel, Field


class TelemetryType(str, Enum):
    POSITION = "position"
    BATTERY = "battery"
    STATE_CHANGE = "state_change"
    SAMPLE_COLLECTED = "sample_collected"
    COMMAND_ACK = "command_ack"
    HEARTBEAT = "heartbeat"
    ANOMALY_DETECTED = "anomaly_detected"
    MISSION_EVENT = "mission_event"


class TelemetryEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    type: TelemetryType
    mission_id: str
    rover_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Position snapshot
    x: int | None = None
    y: int | None = None
    battery: float | None = None
    battery_pct: float | None = None

    # Generic payload for type-specific data
    payload: dict = Field(default_factory=dict)

    def to_stream_dict(self) -> dict[str, str]:
        """Serialize for Redis Stream (all values must be strings)."""
        return {
            "id": self.id,
            "type": self.type.value,
            "mission_id": self.mission_id,
            "rover_id": self.rover_id,
            "timestamp": self.timestamp.isoformat(),
            "x": str(self.x) if self.x is not None else "",
            "y": str(self.y) if self.y is not None else "",
            "battery": str(self.battery) if self.battery is not None else "",
            "battery_pct": str(self.battery_pct) if self.battery_pct is not None else "",
        }
