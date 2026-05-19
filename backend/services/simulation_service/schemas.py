from pydantic import BaseModel
from core.models.rover import AutonomyLevel


class SpawnRoverRequest(BaseModel):
    mission_id: str
    name: str
    start_x: int = 0
    start_y: int = 0


class RunPlanRequest(BaseModel):
    mission_id: str
    plan_id: str


class SetAutonomyRequest(BaseModel):
    level: AutonomyLevel
