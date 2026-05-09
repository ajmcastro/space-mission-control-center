from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4
from pydantic import BaseModel, Field, computed_field
from .command import Command, CommandType


class PlannerType(str, Enum):
    MANUAL = "manual"
    ASTAR = "astar"
    RL = "rl"               # V3 placeholder
    MULTI_AGENT = "multi_agent"  # V3 placeholder


class PlanStep(BaseModel):
    sequence: int
    command: Command
    estimated_battery_cost: float = 0.0
    estimated_duration_seconds: float = 0.0
    rationale: str = ""     # for explainability


class Plan(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    mission_id: str
    rover_id: str
    planner: PlannerType = PlannerType.ASTAR
    steps: list[PlanStep] = Field(default_factory=list)

    # Path computed by planner
    waypoints: list[tuple[int, int]] = Field(default_factory=list)

    # Metrics
    estimated_total_battery: float = 0.0
    estimated_steps: int = 0
    estimated_duration_seconds: float = 0.0

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict = Field(default_factory=dict)

    @computed_field
    @property
    def total_commands(self) -> int:
        return len(self.steps)

    def add_step(self, command: Command, cost: float = 0.0, rationale: str = "") -> PlanStep:
        step = PlanStep(
            sequence=len(self.steps),
            command=command,
            estimated_battery_cost=cost,
            rationale=rationale,
        )
        self.steps.append(step)
        self.estimated_total_battery += cost
        return step
