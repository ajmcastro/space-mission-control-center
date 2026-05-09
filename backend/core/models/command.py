from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4
from pydantic import BaseModel, Field


class CommandType(str, Enum):
    MOVE = "move"
    COLLECT_SAMPLE = "collect_sample"
    TRANSMIT = "transmit"
    WAIT = "wait"
    CHARGE = "charge"
    ABORT = "abort"


class CommandStatus(str, Enum):
    QUEUED = "queued"
    SENT = "sent"           # uplinked, in comm delay window
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Command(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    mission_id: str
    rover_id: str
    type: CommandType
    sequence: int = 0       # order within the mission plan

    # Command parameters (type-specific)
    target_x: int | None = None
    target_y: int | None = None
    payload: dict = Field(default_factory=dict)

    status: CommandStatus = CommandStatus.QUEUED
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    sent_at: datetime | None = None
    executed_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None

    def mark_sent(self) -> None:
        self.status = CommandStatus.SENT
        self.sent_at = datetime.now(timezone.utc)

    def mark_executing(self) -> None:
        self.status = CommandStatus.EXECUTING
        self.executed_at = datetime.now(timezone.utc)

    def mark_completed(self) -> None:
        self.status = CommandStatus.COMPLETED
        self.completed_at = datetime.now(timezone.utc)

    def mark_failed(self, reason: str) -> None:
        self.status = CommandStatus.FAILED
        self.error_message = reason
        self.completed_at = datetime.now(timezone.utc)
