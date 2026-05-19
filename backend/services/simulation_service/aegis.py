"""AEGIS-style autonomous target selection (V4).

Mirrors JPL's Autonomous Exploration for Gathering Increased Science system
used on Perseverance. Rovers score every reachable cell and pick the highest-
value unexplored target when their ground-assigned objective list runs out.

Scoring (all components normalised to [0, 1] then weighted):
  science_value   — pre-computed composite score (geyser proximity, ice-water
                    interface, crater adjacency); already in [0, 10], divided by 10
  unexplored      — 1.0 if not yet revealed, 0.0 if already visited
  sample_bonus    — 1.0 if cell carries a collectable sample
  geology         — abs(elevation) capped at 1.0 for steep terrain interest
  distance_bonus  — slight penalty for very close cells to encourage exploration

Each autonomy level restricts the candidate pool:
  FULLY_AUTONOMOUS  — all passable cells
  SEMI_AUTONOMOUS   — passable AND already revealed cells
  SUPERVISED        — does not call select_target; handled by the service loop
"""
import math
import structlog
from dataclasses import dataclass

from core.models.rover import Rover, AutonomyLevel
from core.models.environment import Grid, Cell
from core.config import settings

log = structlog.get_logger(__name__)

# Scoring weights
_W_SCIENCE    = 0.40
_W_UNEXPLORED = 0.30
_W_SAMPLE     = 0.15
_W_GEOLOGY    = 0.10
_W_DISTANCE   = 0.05   # negative weight — farther cells score slightly higher


@dataclass
class AegisTarget:
    x: int
    y: int
    score: float
    reason: str   # human-readable justification logged in telemetry


def _chebyshev(ax: int, ay: int, bx: int, by: int) -> int:
    return max(abs(ax - bx), abs(ay - by))


def _score_cell(cell: Cell, rover: Rover, grid: Grid) -> float:
    science   = cell.science_value / 10.0
    unexplored = 0.0 if cell.revealed else 1.0
    sample    = 1.0 if cell.has_sample else 0.0
    geology   = min(abs(cell.elevation), 1.0)
    dist      = _chebyshev(rover.x, rover.y, cell.x, cell.y)
    # Normalise distance: max possible is max(width, height). Reward distance
    # up to ~60% of the grid diagonal, then plateau.
    max_dist  = math.sqrt(grid.width ** 2 + grid.height ** 2)
    dist_norm = min(dist / max(max_dist * 0.6, 1.0), 1.0)

    return (
        _W_SCIENCE    * science
        + _W_UNEXPLORED * unexplored
        + _W_SAMPLE     * sample
        + _W_GEOLOGY    * geology
        + _W_DISTANCE   * dist_norm
    )


def _reason(cell: Cell, rover: Rover) -> str:
    parts: list[str] = []
    if cell.science_value >= 5.0:
        parts.append(f"high science ({cell.science_value:.1f})")
    if not cell.revealed:
        parts.append("uncharted territory")
    if cell.has_sample:
        parts.append("collectable sample")
    if abs(cell.elevation) > 0.5:
        parts.append(f"elevation gradient ({cell.elevation:+.2f})")
    dist = _chebyshev(rover.x, rover.y, cell.x, cell.y)
    parts.append(f"dist {dist}")
    return ", ".join(parts) if parts else "best available cell"


def select_target(
    rover: Rover,
    grid: Grid,
    autonomy_level: AutonomyLevel,
) -> AegisTarget | None:
    """Return the highest-scoring candidate cell, or None if none are reachable.

    Uses A* reachability check to guarantee the chosen cell is actually
    accessible from the rover's current position.
    """
    from services.planning_service.astar import astar

    best: AegisTarget | None = None

    for row in grid.cells:
        for cell in row:
            if not cell.passable:
                continue
            if (cell.x, cell.y) == (rover.x, rover.y):
                continue
            # Autonomy gate: semi-autonomous rovers only explore known terrain.
            if autonomy_level == AutonomyLevel.SEMI_AUTONOMOUS and not cell.revealed:
                continue

            score = _score_cell(cell, rover, grid)
            if best and score <= best.score:
                continue

            # Reachability — avoid scoring a cell we cannot actually path to.
            path, _ = astar(grid, (rover.x, rover.y), (cell.x, cell.y))
            if path is None:
                continue

            best = AegisTarget(
                x=cell.x,
                y=cell.y,
                score=score,
                reason=_reason(cell, rover),
            )

    if best:
        log.info(
            "aegis_target_selected",
            rover=rover.name,
            target=(best.x, best.y),
            score=round(best.score, 3),
            reason=best.reason,
        )
    else:
        log.info("aegis_no_target", rover=rover.name, autonomy=autonomy_level.value)

    return best
