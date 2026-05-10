"""Terrain generation helper — pure function, no in-memory state in V2."""
import math
import random
from core.models.environment import Environment, Grid, Cell, TerrainType
from core.config import settings

# Elevation bias per terrain type — ensures physical consistency.
_TERRAIN_ELEVATION_BIAS: dict[TerrainType, float] = {
    TerrainType.FLAT:     0.0,
    TerrainType.ROCKY:    0.3,
    TerrainType.ICE:      0.1,
    TerrainType.CRATER:  -0.5,
    TerrainType.GEYSER:   0.2,
    TerrainType.CREVASSE:-0.7,
}


def _generate_elevation_map(width: int, height: int, rng: random.Random) -> list[list[float]]:
    """
    Multi-octave sinusoidal noise field seeded from `rng`.
    Returns values in [-1, 1] that are fully deterministic for a given rng state.
    """
    # Pre-draw all phase offsets so the map is reproducible.
    phases = [(rng.uniform(0, 2 * math.pi), rng.uniform(0, 2 * math.pi)) for _ in range(3)]
    freqs = [0.15, 0.30, 0.60]
    amps  = [1.00, 0.50, 0.25]

    elevations: list[list[float]] = []
    for y in range(height):
        row: list[float] = []
        for x in range(width):
            val = sum(
                amps[i] * math.sin(x * freqs[i] + phases[i][0]) * math.cos(y * freqs[i] + phases[i][1])
                for i in range(3)
            )
            # Normalise to [-1, 1] (theoretical max amplitude is sum of amps = 1.75)
            row.append(max(-1.0, min(1.0, val / 1.75)))
        elevations.append(row)
    return elevations


def generate_env(env_id: str, width: int = 20, height: int = 20) -> Environment:
    """Generate a deterministic Enceladus-like terrain grid seeded by env_id."""
    rng = random.Random(env_id)

    # Build elevation map first so terrain biases can be applied consistently.
    elevation_map = _generate_elevation_map(width, height, rng)

    cells: list[list[Cell]] = []
    geysers: list[tuple[int, int]] = []
    hazards: list[tuple[int, int]] = []

    terrain_weights = [
        (TerrainType.FLAT,     50),
        (TerrainType.ICE,      25),
        (TerrainType.ROCKY,    15),
        (TerrainType.CRATER,    5),
        (TerrainType.GEYSER,    3),
        (TerrainType.CREVASSE,  2),
    ]
    terrain_choices = [t for t, w in terrain_weights for _ in range(w)]

    for y in range(height):
        row: list[Cell] = []
        for x in range(width):
            terrain = rng.choice(terrain_choices)
            has_sample = terrain in (TerrainType.ROCKY, TerrainType.CRATER) and rng.random() < 0.3

            base_elev = elevation_map[y][x]
            bias = _TERRAIN_ELEVATION_BIAS[terrain]
            elevation = max(-1.0, min(1.0, base_elev + bias * 0.5))

            # Cells are hidden until a rover enters sensor range (fog of war).
            # When fog_of_war is disabled every cell starts revealed.
            revealed = not settings.fog_of_war
            cell = Cell(x=x, y=y, terrain=terrain, elevation=elevation,
                        has_sample=has_sample, revealed=revealed)
            row.append(cell)
            if terrain == TerrainType.GEYSER:
                geysers.append((x, y))
                hazards.append((x, y))
        cells.append(row)

    # Ensure start position (0, 0) is always passable flat at ground level.
    cells[0][0] = Cell(x=0, y=0, terrain=TerrainType.FLAT, elevation=0.0,
                       revealed=not settings.fog_of_war)

    grid = Grid(width=width, height=height, cells=cells)
    return Environment(
        id=env_id,
        grid=grid,
        active_geysers=geysers,
        hazard_zones=hazards,
    )
