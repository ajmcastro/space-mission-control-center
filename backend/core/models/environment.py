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
    revealed: bool = False          # False until a rover enters sensor range (Fog of War)

    # Dynamic terrain (V4) — only meaningful for GEYSER cells
    geyser_active: bool = True      # False = dormant (safe to traverse), True = erupting (hazardous)

    # Science Value Map (V4) — composite score in [0, 10]
    science_value: float = 0.0

    @property
    def passable(self) -> bool:
        return self.terrain != TerrainType.CREVASSE

    @property
    def movement_cost(self) -> float:
        # Dormant geysers are safe traversal targets; active ones carry full hazard cost.
        if self.terrain == TerrainType.GEYSER and not self.geyser_active:
            base = TERRAIN_COST[TerrainType.ICE]   # rewarded for science potential
        else:
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

    def reveal_around(self, cx: int, cy: int, sensor_range: int) -> list[tuple[int, int]]:
        """Mark all cells within sensor_range of (cx, cy) as revealed.

        Returns the coordinates of cells that were newly revealed this call.
        Uses Chebyshev distance (square neighbourhood) matching orbital sensor footprint.
        """
        newly_revealed: list[tuple[int, int]] = []
        for dy in range(-sensor_range, sensor_range + 1):
            for dx in range(-sensor_range, sensor_range + 1):
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < self.width and 0 <= ny < self.height:
                    cell = self.cells[ny][nx]
                    if not cell.revealed:
                        cell.revealed = True
                        newly_revealed.append((nx, ny))
        return newly_revealed

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

    # Dynamic terrain state (V4)
    sim_tick: int = 0                   # simulation steps elapsed since mission start
    is_night: bool = False              # surface frost active during Enceladus night


def compute_science_scores(grid: "Grid") -> None:
    """
    Compute per-cell science values in-place from three terrain signals:

    Geyser proximity
        Cells near geyser cells score up to 5.0 on a Chebyshev-distance decay
        (max at dist=0, zero beyond dist=5).  Geyser cells themselves are the
        highest-value science targets on Enceladus — potential ocean-surface vents.

    Ice-water interface
        ICE cells immediately adjacent (Chebyshev dist ≤ 1) to any geyser cell
        receive a +3.0 bonus — the contact zone between subsurface water and
        surface ice is an analogue of deep-sea hydrothermal vent biomes.

    Crater proximity
        CRATER cells score +2.0 (impact-excavated material); cells one step away
        score +0.75 (ejecta blanket).  Secondary craters concentrate volatiles
        and expose sub-surface stratigraphy.

    The three components are summed and clamped to [0, 10].
    """
    geyser_coords: list[tuple[int, int]] = [
        (cell.x, cell.y)
        for row in grid.cells
        for cell in row
        if cell.terrain == TerrainType.GEYSER
    ]
    crater_coords: list[tuple[int, int]] = [
        (cell.x, cell.y)
        for row in grid.cells
        for cell in row
        if cell.terrain == TerrainType.CRATER
    ]

    for row in grid.cells:
        for cell in row:
            score = 0.0

            if geyser_coords:
                min_geyser_dist = min(
                    max(abs(cell.x - gx), abs(cell.y - gy))
                    for gx, gy in geyser_coords
                )
                score += max(0.0, 5.0 - min_geyser_dist)
                if cell.terrain == TerrainType.ICE and min_geyser_dist <= 1:
                    score += 3.0

            if crater_coords:
                min_crater_dist = min(
                    max(abs(cell.x - cx), abs(cell.y - cy))
                    for cx, cy in crater_coords
                )
                if min_crater_dist == 0:
                    score += 2.0
                elif min_crater_dist == 1:
                    score += 0.75

            cell.science_value = min(10.0, round(score, 2))
