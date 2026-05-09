from pydantic import BaseModel, Field
from core.models.mission import MissionStatus, ObjectiveType


class ObjectiveCreate(BaseModel):
    type: ObjectiveType
    target_x: int
    target_y: int
    description: str = ""
    priority: int = 1


class MissionCreate(BaseModel):
    name: str
    description: str = ""
    environment_id: str | None = None  # auto-generated if omitted
    objectives: list[ObjectiveCreate] = Field(default_factory=list)
    grid_width: int = 20
    grid_height: int = 20


class MissionUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    status: MissionStatus | None = None
