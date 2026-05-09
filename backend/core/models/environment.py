from enum import Enum
from pydantic import BaseModel, Field


class TerrainType(str, Enum):
    FLAT = "flat"
    ROCKY = "rocky"
    ICE = "ice"
    CRATER = "crater"
    GEYSER = "geyser"       # Enceladus-specific: active water geysers
    CREVASSE = "crevasse"   # impassable


TERRAIN_COST: dict[TerrainType, float] = {
    TerrainType.FLAT: 1.0,
    TerrainType.ROCKY: 2.5,
    TerrainType.ICE: 1.5,
    TerrainType.CRATER: 3.0,
    TerrainType.GEYSER: 4.0,
    TerrainType.CREVASSE: float("inf"),  # impassable
}


class Cell(BaseModel):
    x: int
    y: int
    terrain: TerrainType = TerrainType.FLAT
    elevation: float = 0.0
    has_sample: bool = False
    is_visited: bool = False

    @property
    def passable(self) -> bool:
        return self.terrain != TerrainType.CREVASSE

    @property
    def movement_cost(self) -> float:
        base = TERRAIN_COST[self.terrain]
        # Elevation relief adds up to 50% extra cost at maximum grade (|elev| = 1.0).
        slope_factor = 1.0 + abs(self.elevation) * 0.5
        return base * slope_factor


class Grid(BaseModel):
    width: int
    height: int
    cells: list[list[Cell]]

    @classmethod
    def create_empty(cls, width: int, height: int) -> "Grid":
        cells = [
            [Cell(x=x, y=y) for x in range(width)]
            for y in range(height)
        ]
        return cls(width=width, height=height, cells=cells)

    def get_cell(self, x: int, y: int) -> Cell | None:
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.cells[y][x]
        return None

    def neighbors(self, x: int, y: int) -> list[Cell]:
        candidates = [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
        return [
            self.cells[ny][nx]
            for nx, ny in candidates
            if 0 <= nx < self.width and 0 <= ny < self.height
            and self.cells[ny][nx].passable
        ]


class Environment(BaseModel):
    id: str
    name: str = "Enceladus Surface Zone Alpha"
    grid: Grid
    temperature_k: float = 75.0         # Surface temp ~75 K
    pressure_pa: float = 0.5            # Near-vacuum
    magnetic_field_ut: float = 325.0    # μT (similar to Saturn's field)
    active_geysers: list[tuple[int, int]] = Field(default_factory=list)
    hazard_zones: list[tuple[int, int]] = Field(default_factory=list)
