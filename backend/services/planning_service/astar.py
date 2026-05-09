"""A* pathfinding on a weighted terrain grid."""
import heapq
from core.models.environment import Grid, TerrainType, TERRAIN_COST


def heuristic(ax: int, ay: int, bx: int, by: int) -> float:
    """Manhattan distance — admissible for 4-connected grid."""
    return abs(ax - bx) + abs(ay - by)


def astar(
    grid: Grid,
    start: tuple[int, int],
    goal: tuple[int, int],
) -> tuple[list[tuple[int, int]], float] | tuple[None, float]:
    """
    Returns (path, total_cost) or (None, 0) if no path exists.
    Path includes both start and goal positions.
    Cost uses terrain-specific movement weights from TERRAIN_COST.
    """
    if start == goal:
        return [start], 0.0

    sx, sy = start
    gx, gy = goal

    start_cell = grid.get_cell(sx, sy)
    goal_cell = grid.get_cell(gx, gy)
    if not start_cell or not goal_cell or not goal_cell.passable:
        return None, 0.0

    # (f, g, x, y)
    open_heap: list[tuple[float, float, int, int]] = []
    heapq.heappush(open_heap, (heuristic(sx, sy, gx, gy), 0.0, sx, sy))

    g_score: dict[tuple[int, int], float] = {(sx, sy): 0.0}
    came_from: dict[tuple[int, int], tuple[int, int]] = {}

    while open_heap:
        f, g, cx, cy = heapq.heappop(open_heap)
        current = (cx, cy)

        if current == (gx, gy):
            return _reconstruct(came_from, current), g

        if g > g_score.get(current, float("inf")):
            continue  # stale entry

        for neighbor in grid.neighbors(cx, cy):
            nx, ny = neighbor.x, neighbor.y
            step_cost = neighbor.movement_cost
            tentative_g = g + step_cost

            if tentative_g < g_score.get((nx, ny), float("inf")):
                g_score[(nx, ny)] = tentative_g
                came_from[(nx, ny)] = current
                f_new = tentative_g + heuristic(nx, ny, gx, gy)
                heapq.heappush(open_heap, (f_new, tentative_g, nx, ny))

    return None, 0.0  # no path found


def _reconstruct(
    came_from: dict[tuple[int, int], tuple[int, int]],
    current: tuple[int, int],
) -> list[tuple[int, int]]:
    path = [current]
    while current in came_from:
        current = came_from[current]
        path.append(current)
    path.reverse()
    return path


def path_battery_cost(path: list[tuple[int, int]], grid: Grid, move_cost_per_cell: float = 10.0) -> float:
    """Estimate total battery cost for traversing a path."""
    total = 0.0
    for x, y in path[1:]:  # skip start position
        cell = grid.get_cell(x, y)
        if cell:
            total += move_cost_per_cell * cell.movement_cost
    return total
