"""Terrain generation helper — pure function, no in-memory state in V2."""
import random
from core.models.environment import Environment, Grid, Cell, TerrainType


def generate_env(env_id: str, width: int = 20, height: int = 20) -> Environment:
    """Generate a deterministic Enceladus-like terrain grid seeded by env_id."""
    rng = random.Random(env_id)
    cells: list[list[Cell]] = []
    geysers: list[tuple[int, int]] = []
    hazards: list[tuple[int, int]] = []

    terrain_weights = [
        (TerrainType.FLAT, 50),
        (TerrainType.ICE, 25),
        (TerrainType.ROCKY, 15),
        (TerrainType.CRATER, 5),
        (TerrainType.GEYSER, 3),
        (TerrainType.CREVASSE, 2),
    ]
    terrain_choices = [t for t, w in terrain_weights for _ in range(w)]

    for y in range(height):
        row: list[Cell] = []
        for x in range(width):
            terrain = rng.choice(terrain_choices)
            has_sample = terrain in (TerrainType.ROCKY, TerrainType.CRATER) and rng.random() < 0.3
            cell = Cell(x=x, y=y, terrain=terrain, has_sample=has_sample)
            row.append(cell)
            if terrain == TerrainType.GEYSER:
                geysers.append((x, y))
                hazards.append((x, y))
        cells.append(row)

    # Ensure start position (0,0) is always passable flat
    cells[0][0] = Cell(x=0, y=0, terrain=TerrainType.FLAT)

    grid = Grid(width=width, height=height, cells=cells)
    return Environment(
        id=env_id,
        grid=grid,
        active_geysers=geysers,
        hazard_zones=hazards,
    )
