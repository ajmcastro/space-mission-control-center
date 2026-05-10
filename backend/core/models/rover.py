from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4
from pydantic import BaseModel, Field, computed_field


class RoverState(str, Enum):
    IDLE = "idle"
    MOVING = "moving"
    SAMPLING = "sampling"
    CHARGING = "charging"
    STUCK = "stuck"
    COMM_LOST = "comm_lost"
    ERROR = "error"
    SAFE_MODE = "safe_mode"


class RoverSpec(BaseModel):
    max_battery: float = 1000.0
    move_cost_per_cell: float = 10.0
    sample_cost: float = 25.0
    comm_cost: float = 5.0
    max_speed_cells_per_step: int = 1


class Rover(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    mission_id: str | None = None
    state: RoverState = RoverState.IDLE
    x: int = 0
    y: int = 0
    battery: float = 1000.0
    spec: RoverSpec = Field(default_factory=RoverSpec)

    # Tracking
    path_history: list[tuple[int, int]] = Field(default_factory=list)
    samples_collected: int = 0
    steps_taken: int = 0
    total_distance: float = 0.0
    anomalies_encountered: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Fault Protection System (V4)
    anomaly_streak: int = 0           # consecutive anomaly hits without a clean step
    safe_mode_reason: str | None = None

    @property
    def position(self) -> tuple[int, int]:
        return (self.x, self.y)

    @computed_field
    @property
    def battery_pct(self) -> float:
        return round(self.battery / self.spec.max_battery * 100, 1)

    @property
    def is_operational(self) -> bool:
        return self.state not in (
            RoverState.STUCK, RoverState.ERROR,
            RoverState.COMM_LOST, RoverState.SAFE_MODE,
        )

    def move_to(self, x: int, y: int, cost: float) -> None:
        self.path_history.append((self.x, self.y))
        self.x = x
        self.y = y
        self.battery -= cost
        self.steps_taken += 1
        self.total_distance += 1
        self.state = RoverState.IDLE

    def collect_sample(self) -> None:
        self.battery -= self.spec.sample_cost
        self.samples_collected += 1
        self.state = RoverState.IDLE
