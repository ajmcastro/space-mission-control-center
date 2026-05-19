from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4
from pydantic import BaseModel, Field


class EventType(str, Enum):
    # Mission lifecycle
    MISSION_CREATED = "mission.created"
    MISSION_STARTED = "mission.started"
    MISSION_COMPLETED = "mission.completed"
    MISSION_FAILED = "mission.failed"
    MISSION_ABORTED = "mission.aborted"

    # Planning
    PLAN_CREATED = "plan.created"
    PLAN_UPDATED = "plan.updated"

    # Rover / Command
    COMMAND_QUEUED = "command.queued"
    COMMAND_EXECUTED = "command.executed"
    COMMAND_FAILED = "command.failed"
    ROVER_MOVED = "rover.moved"
    ROVER_STATE_CHANGED = "rover.state_changed"
    SAMPLE_COLLECTED = "rover.sample_collected"

    # Telemetry
    TELEMETRY_EMITTED = "telemetry.emitted"

    # Anomaly
    ANOMALY_DETECTED = "anomaly.detected"
    ANOMALY_RESOLVED = "anomaly.resolved"
    REPLAN_TRIGGERED = "replan.triggered"

    # Fog of War (V4)
    CELLS_REVEALED = "cells.revealed"

    # Fault Protection System (V4)
    FPS_RULE_TRIGGERED = "fps.rule_triggered"
    SAFE_MODE_ENTERED  = "fps.safe_mode_entered"
    SAFE_MODE_EXITED   = "fps.safe_mode_exited"

    # Dynamic Terrain Events (V4)
    GEYSER_ERUPTION   = "terrain.geyser_eruption"
    GEYSER_DORMANCY   = "terrain.geyser_dormancy"
    ICE_FRACTURE      = "terrain.ice_fracture"
    FROST_CYCLE_START = "terrain.frost_cycle_start"
    FROST_CYCLE_END   = "terrain.frost_cycle_end"

    # AEGIS Autonomous Target Selection (V4)
    AEGIS_TARGET_SELECTED = "aegis.target_selected"   # rover autonomously selected a new objective
    AEGIS_TARGET_PROPOSED = "aegis.target_proposed"   # supervised rover awaiting approval


class MissionEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    type: EventType
    stream: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    mission_id: str | None = None
    rover_id: str | None = None
    payload: dict = Field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type.value,
            "stream": self.stream,
            "timestamp": self.timestamp.isoformat(),
            "mission_id": self.mission_id or "",
            "rover_id": self.rover_id or "",
            **{f"payload_{k}": str(v) for k, v in self.payload.items()},
        }
