"""
RL-inspired greedy value planner.

Uses a reward-function heuristic at inference time (epsilon=0 greedy policy).
The architecture matches PlannerInterface so a trained neural policy can be
hot-swapped by overriding _value() without changing any other code.
"""
import structlog
from core.models.plan import Plan, PlanStep, PlannerType
from core.models.command import Command, CommandType
from core.models.environment import Grid, Cell, TerrainType
from core.config import settings
from .schemas import PlanRequest

log = structlog.get_logger(__name__)


class RLPlanner:
    """Greedy value-function planner — V3 RL interface."""

    def __init__(
        self,
        episode_budget: int | None = None,
        w_target: float | None = None,
        w_terrain: float | None = None,
        w_geyser: float | None = None,
    ) -> None:
        self._budget = episode_budget or settings.rl_episode_budget
        self._w_target  = w_target  or settings.rl_weight_target
        self._w_terrain = w_terrain or settings.rl_weight_terrain
        self._w_geyser  = w_geyser  or settings.rl_weight_geyser

    async def plan(self, request: PlanRequest, grid: Grid, objectives: list) -> Plan:
        plan = Plan(
            mission_id=request.mission_id,
            rover_id=request.rover_id,
            planner=PlannerType.RL,
            metadata={
                "policy": "greedy_value",
                "weights": {
                    "target": self._w_target,
                    "terrain": self._w_terrain,
                    "geyser": self._w_geyser,
                },
            },
        )

        pending = [o for o in sorted(objectives, key=lambda o: o.priority) if not o.completed]
        pos = (request.start_x, request.start_y)
        visited: set[tuple[int, int]] = {pos}
        steps_taken = 0

        log.info(
            "rl_plan_start",
            mission_id=request.mission_id,
            rover_id=request.rover_id,
            objectives=len(pending),
        )

        while pending and steps_taken < self._budget:
            next_pos = self._greedy_step(pos, pending, grid, visited)
            if next_pos is None:
                # Trapped or budget reached — fall back: direct step toward nearest objective.
                next_pos = self._forced_step(pos, pending, grid)
                if next_pos is None:
                    break

            visited.add(next_pos)
            cell = grid.get_cell(*next_pos)
            cell_cost = settings.rover_move_cost * (cell.movement_cost if cell else 1.0)

            cmd = Command(
                mission_id=request.mission_id,
                rover_id=request.rover_id,
                type=CommandType.MOVE,
                sequence=len(plan.steps),
                target_x=next_pos[0],
                target_y=next_pos[1],
            )
            nearest_obj = self._nearest_objective(next_pos, pending)
            plan.add_step(
                cmd,
                cost=cell_cost,
                rationale=f"RL greedy step → obj {nearest_obj.id[:8] if nearest_obj else '?'}",
            )
            plan.waypoints.append(next_pos)
            pos = next_pos
            steps_taken += 1

            # Collect sample and mark objective reached.
            reached = [o for o in pending if (o.target_x, o.target_y) == pos]
            for obj in reached:
                target_cell = grid.get_cell(obj.target_x, obj.target_y)
                if target_cell and (target_cell.has_sample or obj.type.value == "collect_sample"):
                    sample_cmd = Command(
                        mission_id=request.mission_id,
                        rover_id=request.rover_id,
                        type=CommandType.COLLECT_SAMPLE,
                        sequence=len(plan.steps),
                        target_x=obj.target_x,
                        target_y=obj.target_y,
                    )
                    plan.add_step(sample_cmd, cost=settings.rover_sample_cost,
                                  rationale=f"Collect sample at obj {obj.id[:8]}")
                pending.remove(obj)
                # Allow revisiting positions once an objective is completed.
                visited.discard(pos)

        plan.metadata["episode_steps"] = steps_taken
        plan.estimated_steps = len(plan.steps)
        plan.estimated_duration_seconds = plan.estimated_steps * settings.sim_step_delay_seconds

        log.info(
            "rl_plan_done",
            mission_id=request.mission_id,
            steps=plan.estimated_steps,
            episode_steps=steps_taken,
            objectives_remaining=len(pending),
        )
        return plan

    # ── Value function ──────────────────────────────────────────────────────

    def _value(
        self,
        pos: tuple[int, int],
        objectives: list,
        grid: Grid,
    ) -> float:
        cell = grid.get_cell(*pos)
        if cell is None or not cell.passable:
            return float("-inf")

        # Proximity reward: 1 / (1 + dist_to_nearest_obj)
        nearest = self._nearest_objective(pos, objectives)
        dist = self._manhattan(pos, (nearest.target_x, nearest.target_y)) if nearest else 100
        target_reward = self._w_target / (1.0 + dist)

        # Terrain penalty
        terrain_penalty = self._w_terrain * cell.movement_cost

        # Geyser safety penalty
        geyser_penalty = self._w_geyser if cell.terrain == TerrainType.GEYSER else 0.0

        # Elevation penalty (high gradient = risky)
        elevation_penalty = abs(cell.elevation) * 0.5

        return target_reward - terrain_penalty - geyser_penalty - elevation_penalty

    def _greedy_step(
        self,
        pos: tuple[int, int],
        objectives: list,
        grid: Grid,
        visited: set[tuple[int, int]],
    ) -> tuple[int, int] | None:
        neighbors = grid.neighbors(*pos)
        candidates = [
            (n.x, n.y) for n in neighbors
            if (n.x, n.y) not in visited
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda p: self._value(p, objectives, grid))

    def _forced_step(
        self,
        pos: tuple[int, int],
        objectives: list,
        grid: Grid,
    ) -> tuple[int, int] | None:
        """Emergency step: pick any passable neighbor closest to nearest objective."""
        nearest = self._nearest_objective(pos, objectives)
        if not nearest:
            return None
        goal = (nearest.target_x, nearest.target_y)
        neighbors = grid.neighbors(*pos)
        if not neighbors:
            return None
        return min(
            ((n.x, n.y) for n in neighbors),
            key=lambda p: self._manhattan(p, goal),
        )

    # ── Helpers ─────────────────────────────────────────────────────────────

    @staticmethod
    def _manhattan(a: tuple[int, int], b: tuple[int, int]) -> int:
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    @staticmethod
    def _nearest_objective(pos: tuple[int, int], objectives: list):
        if not objectives:
            return None
        return min(objectives, key=lambda o: abs(o.target_x - pos[0]) + abs(o.target_y - pos[1]))
