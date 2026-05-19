"""Unit tests for the AEGIS autonomous target selection engine."""
import pytest

from core.models.rover import Rover, AutonomyLevel
from core.models.environment import Grid, Cell, TerrainType
from services.simulation_service.aegis import select_target, _score_cell


def _make_grid(width: int = 6, height: int = 6) -> Grid:
    cells = [
        [Cell(x=x, y=y, terrain=TerrainType.FLAT) for x in range(width)]
        for y in range(height)
    ]
    return Grid(width=width, height=height, cells=cells)


def _rover(x: int = 0, y: int = 0, level: AutonomyLevel = AutonomyLevel.FULLY_AUTONOMOUS) -> Rover:
    return Rover(name="TestRover", x=x, y=y, autonomy_level=level)


# ─── Scoring ─────────────────────────────────────────────────────────────────

def test_score_cell_unexplored_bonus():
    grid = _make_grid()
    rover = _rover()
    revealed_cell = grid.cells[1][1]
    revealed_cell.revealed = True
    uncharted_cell = grid.cells[2][2]

    score_revealed  = _score_cell(revealed_cell, rover, grid)
    score_uncharted = _score_cell(uncharted_cell, rover, grid)
    assert score_uncharted > score_revealed, "Uncharted cells should score higher"


def test_score_cell_sample_bonus():
    grid = _make_grid()
    rover = _rover()
    plain = grid.cells[1][1]
    plain.revealed = True
    sampled = grid.cells[2][2]
    sampled.revealed = True
    sampled.has_sample = True

    assert _score_cell(sampled, rover, grid) > _score_cell(plain, rover, grid)


def test_score_cell_science_value_bonus():
    grid = _make_grid()
    rover = _rover()
    low = grid.cells[1][1]
    low.revealed = True
    low.science_value = 1.0
    high = grid.cells[2][2]
    high.revealed = True
    high.science_value = 9.0

    assert _score_cell(high, rover, grid) > _score_cell(low, rover, grid)


# ─── Target selection ─────────────────────────────────────────────────────────

def test_fully_autonomous_picks_uncharted():
    grid = _make_grid(5, 5)
    # Reveal most cells but leave (4,4) uncharted with high science value
    for row in grid.cells:
        for cell in row:
            cell.revealed = True
    grid.cells[4][4].revealed = False
    grid.cells[4][4].science_value = 10.0

    rover = _rover(level=AutonomyLevel.FULLY_AUTONOMOUS)
    target = select_target(rover, grid, AutonomyLevel.FULLY_AUTONOMOUS)
    assert target is not None
    assert (target.x, target.y) == (4, 4)


def test_semi_autonomous_skips_uncharted():
    grid = _make_grid(5, 5)
    # Only (1,1) is revealed; everything else is uncharted
    grid.cells[1][1].revealed = True
    grid.cells[1][1].science_value = 5.0

    rover = _rover(level=AutonomyLevel.SEMI_AUTONOMOUS)
    target = select_target(rover, grid, AutonomyLevel.SEMI_AUTONOMOUS)
    # Should pick (1,1) (the only revealed non-origin cell)
    assert target is not None
    assert (target.x, target.y) == (1, 1)


def test_semi_autonomous_returns_none_if_no_revealed_cells():
    grid = _make_grid(3, 3)
    # Nothing revealed besides origin (not in candidate set)
    rover = _rover(level=AutonomyLevel.SEMI_AUTONOMOUS)
    target = select_target(rover, grid, AutonomyLevel.SEMI_AUTONOMOUS)
    assert target is None


def test_no_target_when_all_blocked():
    """Crevasse-only grid means no reachable target."""
    grid = _make_grid(3, 3)
    for row in grid.cells:
        for cell in row:
            if (cell.x, cell.y) != (0, 0):
                cell.terrain = TerrainType.CREVASSE

    rover = _rover(level=AutonomyLevel.FULLY_AUTONOMOUS)
    target = select_target(rover, grid, AutonomyLevel.FULLY_AUTONOMOUS)
    assert target is None


def test_skips_rovers_own_cell():
    grid = _make_grid(3, 3)
    for row in grid.cells:
        for c in row:
            c.revealed = True
    rover = _rover(x=1, y=1)
    target = select_target(rover, grid, AutonomyLevel.FULLY_AUTONOMOUS)
    assert target is not None
    assert (target.x, target.y) != (1, 1)
