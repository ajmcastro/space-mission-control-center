from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4
from pydantic import BaseModel, Field, computed_field


class MissionStatus(str, Enum):
    DRAFT = "draft"
    PLANNED = "planned"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"


class ObjectiveType(str, Enum):
    REACH_WAYPOINT = "reach_waypoint"
    COLLECT_SAMPLE = "collect_sample"
    SURVEY_AREA = "survey_area"
    INVESTIGATE_ANOMALY = "investigate_anomaly"
    RETURN_TO_BASE = "return_to_base"


class Objective(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    type: ObjectiveType
    target_x: int
    target_y: int
    description: str = ""
    priority: int = 1               # 1 = highest
    completed: bool = False
    completed_at: datetime | None = None

    def complete(self) -> None:
        self.completed = True
        self.completed_at = datetime.now(timezone.utc)


class Mission(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    description: str = ""
    status: MissionStatus = MissionStatus.DRAFT
    environment_id: str
    rover_ids: list[str] = Field(default_factory=list)
    objectives: list[Objective] = Field(default_factory=list)
    plan_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    metadata: dict = Field(default_factory=dict)

    @computed_field
    @property
    def progress_pct(self) -> float:
        if not self.objectives:
            return 0.0
        done = sum(1 for o in self.objectives if o.completed)
        return round(done / len(self.objectives) * 100, 1)

    def start(self) -> None:
        self.status = MissionStatus.ACTIVE
        self.started_at = datetime.now(timezone.utc)

    def complete(self) -> None:
        self.status = MissionStatus.COMPLETED
        self.completed_at = datetime.now(timezone.utc)

    def fail(self) -> None:
        self.status = MissionStatus.FAILED
        self.completed_at = datetime.now(timezone.utc)
