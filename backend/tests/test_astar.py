"""Tests for the A* pathfinding engine."""
import pytest
from core.models.environment import Grid, Cell, TerrainType
from services.planning_service.astar import astar, path_battery_cost


def make_grid(layout: list[str]) -> Grid:
    """
    Build a Grid from a list of strings.
    '.' = flat, '#' = crevasse (impassable), 'R' = rocky
    """
    height = len(layout)
    width = len(layout[0])
    terrain_map = {".": TerrainType.FLAT, "#": TerrainType.CREVASSE, "R": TerrainType.ROCKY}
    cells = [
        [Cell(x=x, y=y, terrain=terrain_map.get(layout[y][x], TerrainType.FLAT)) for x in range(width)]
        for y in range(height)
    ]
    return Grid(width=width, height=height, cells=cells)


class TestAstar:
    def test_direct_path(self):
        grid = make_grid([
            ".....",
            ".....",
            ".....",
        ])
        path, cost = astar(grid, (0, 0), (4, 2))
        assert path is not None
        assert path[0] == (0, 0)
        assert path[-1] == (4, 2)
        assert len(path) == 7  # Manhattan distance 6 + start

    def test_same_start_goal(self):
        grid = make_grid(["..."])
        path, cost = astar(grid, (1, 0), (1, 0))
        assert path == [(1, 0)]
        assert cost == 0.0

    def test_impassable_goal(self):
        grid = make_grid(["..#"])
        path, cost = astar(grid, (0, 0), (2, 0))
        assert path is None

    def test_path_around_wall(self):
        grid = make_grid([
            ".#.",
            ".#.",
            "...",
        ])
        path, cost = astar(grid, (0, 0), (2, 0))
        assert path is not None
        assert path[-1] == (2, 0)
        # Must go around the wall through row y=2
        xs = [p[0] for p in path]
        assert 0 in xs and 2 in xs

    def test_no_path_fully_blocked(self):
        grid = make_grid([
            ".#.",
            "###",
            "...",
        ])
        path, cost = astar(grid, (0, 0), (2, 0))
        assert path is None

    def test_cost_increases_with_rocky_terrain(self):
        flat_grid = make_grid(["...."])
        rocky_grid = make_grid(["RRRR"])
        _, flat_cost = astar(flat_grid, (0, 0), (3, 0))
        _, rocky_cost = astar(rocky_grid, (0, 0), (3, 0))
        assert rocky_cost > flat_cost

    def test_battery_cost_calculation(self):
        grid = make_grid(["...."])
        path, _ = astar(grid, (0, 0), (3, 0))
        cost = path_battery_cost(path, grid, move_cost_per_cell=10.0)
        assert cost == pytest.approx(30.0)
