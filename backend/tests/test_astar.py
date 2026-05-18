"""Tests for the A* pathfinding engine and science value scoring."""
import pytest
from core.models.environment import Grid, Cell, TerrainType, compute_science_scores
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


class TestScienceScores:
    def _make_typed_grid(self, width: int, height: int, terrain_map: dict[tuple[int, int], TerrainType]) -> Grid:
        cells = [
            [
                Cell(x=x, y=y, terrain=terrain_map.get((x, y), TerrainType.FLAT))
                for x in range(width)
            ]
            for y in range(height)
        ]
        return Grid(width=width, height=height, cells=cells)

    def test_no_special_terrain_all_zero(self):
        grid = make_grid([".....", "....."])
        compute_science_scores(grid)
        for row in grid.cells:
            for cell in row:
                assert cell.science_value == 0.0

    def test_geyser_cell_has_highest_score(self):
        grid = self._make_typed_grid(5, 5, {(2, 2): TerrainType.GEYSER})
        compute_science_scores(grid)
        geyser_cell = grid.get_cell(2, 2)
        # Geyser cell itself is at dist=0 → score = 5.0
        assert geyser_cell.science_value == pytest.approx(5.0)

    def test_proximity_decays_with_distance(self):
        grid = self._make_typed_grid(10, 1, {(0, 0): TerrainType.GEYSER})
        compute_science_scores(grid)
        scores = [grid.get_cell(x, 0).science_value for x in range(6)]
        # Each cell one step further should have a lower or equal score
        assert all(scores[i] >= scores[i + 1] for i in range(len(scores) - 1))
        # Beyond range 5 the score is zero
        assert grid.get_cell(6, 0).science_value == 0.0

    def test_ice_water_interface_bonus(self):
        # ICE cell adjacent to GEYSER gets +3.0 on top of proximity
        grid = self._make_typed_grid(3, 1, {
            (0, 0): TerrainType.GEYSER,
            (1, 0): TerrainType.ICE,
        })
        compute_science_scores(grid)
        ice_cell = grid.get_cell(1, 0)
        # proximity(dist=1) = 4.0 + ice-water bonus 3.0 = 7.0
        assert ice_cell.science_value == pytest.approx(7.0)

    def test_crater_bonus(self):
        grid = self._make_typed_grid(5, 1, {(2, 0): TerrainType.CRATER})
        compute_science_scores(grid)
        crater_cell = grid.get_cell(2, 0)
        adjacent_cell = grid.get_cell(1, 0)
        assert crater_cell.science_value == pytest.approx(2.0)
        assert adjacent_cell.science_value == pytest.approx(0.75)

    def test_scores_clamped_to_ten(self):
        # Place geyser, crater, and ice all adjacent — should not exceed 10.0
        grid = self._make_typed_grid(3, 3, {
            (1, 1): TerrainType.GEYSER,
            (0, 0): TerrainType.CRATER,
            (2, 0): TerrainType.ICE,
        })
        compute_science_scores(grid)
        for row in grid.cells:
            for cell in row:
                assert cell.science_value <= 10.0

    def test_recompute_after_geyser_dormancy(self):
        # Simulate a geyser cell going dormant — score should stay stable (proximity is geometry-based).
        grid = self._make_typed_grid(5, 1, {(0, 0): TerrainType.GEYSER})
        compute_science_scores(grid)
        score_before = grid.get_cell(1, 0).science_value
        # Flip geyser to dormant and recompute
        grid.get_cell(0, 0).geyser_active = False
        compute_science_scores(grid)
        score_after = grid.get_cell(1, 0).science_value
        # Score is geometry-based, not dependent on active state — should be identical
        assert score_before == score_after
