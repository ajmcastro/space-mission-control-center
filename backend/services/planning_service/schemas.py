from pydantic import BaseModel
from core.models.plan import PlannerType


class PlanRequest(BaseModel):
    mission_id: str
    rover_id: str
    start_x: int = 0
    start_y: int = 0
    planner: PlannerType = PlannerType.ASTAR


class WaypointRequest(BaseModel):
    mission_id: str
    rover_id: str
    waypoints: list[tuple[int, int]]
    planner: PlannerType = PlannerType.MANUAL


class MultiAgentPlanRequest(BaseModel):
    mission_id: str
    rover_ids: list[str]
