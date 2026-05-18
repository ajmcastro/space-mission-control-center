"""
Multi-agent coordinator — distributes mission objectives across rovers then
generates an independent A* plan per rover.
"""
import asyncio
import structlog
from core.models.plan import Plan, PlannerType
from core.models.environment import Grid
from core.config import settings
from .astar import astar
from .schemas import PlanRequest

_SCIENCE_ROI_EPSILON = 1.0  # prevents division by zero in science ROI metric

log = structlog.get_logger(__name__)


class MultiAgentCoordinator:
    """
    Greedy objective assignment — two modes:

    Default (optimize_science=False)
        Assigns each objective to the rover with the lowest accumulated travel
        cost so far.  Minimises total battery spent across the fleet.

    Science-optimised (optimize_science=True)
        Assigns each objective to the rover that maximises expected science ROI:
        ``science_value_at_target / (cumulative_cost + cost_to_objective)``.
        Rovers converge on high-value targets (geyser vents, ice-water interfaces,
        craters) rather than nearby ones.
    """

    def __init__(self, astar_planner) -> None:  # type: ignore[annotation-unchecked]
        self._planner = astar_planner

    async def plan_all(
        self,
        mission_id: str,
        rover_ids: list[str],
        rover_positions: dict[str, tuple[int, int]],
        objectives: list,
        grid: Grid,
        optimize_science: bool = False,
    ) -> list[Plan]:
        if not rover_ids or not objectives:
            return []

        pending_objs = [o for o in objectives if not o.completed]
        if not pending_objs:
            return []

        log.info(
            "multi_agent_plan_start",
            mission_id=mission_id,
            rovers=len(rover_ids),
            objectives=len(pending_objs),
        )

        # Build cost matrix: rover → objective → A* cost (parallelised).
        cost_matrix = await self._build_cost_matrix(rover_ids, rover_positions, pending_objs, grid)

        # Greedy assignment: each objective (sorted by priority) goes to the rover
        # that minimises travel cost (default) or maximises science ROI (optimize_science).
        assignments: dict[str, list] = {rid: [] for rid in rover_ids}
        cumulative: dict[str, float] = {rid: 0.0 for rid in rover_ids}

        for obj in sorted(pending_objs, key=lambda o: o.priority):
            target_cell = grid.get_cell(obj.target_x, obj.target_y)
            sci_value = target_cell.science_value if target_cell else 0.0

            if optimize_science:
                best_rover = max(
                    rover_ids,
                    key=lambda rid: sci_value / max(
                        cumulative[rid] + cost_matrix.get((rid, obj.id), 1e9),
                        _SCIENCE_ROI_EPSILON,
                    ),
                )
            else:
                best_rover = min(
                    rover_ids,
                    key=lambda rid: cumulative[rid] + cost_matrix.get((rid, obj.id), 1e9),
                )
            assignments[best_rover].append(obj)
            cumulative[best_rover] += cost_matrix.get((best_rover, obj.id), 0.0)

        log.info("multi_agent_assignments", assignments={
            rid: [o.id[:8] for o in objs] for rid, objs in assignments.items()
        })

        # Generate one A* plan per rover (parallelised).
        tasks = [
            self._plan_rover(mission_id, rover_id, rover_positions[rover_id], assignments[rover_id], grid)
            for rover_id in rover_ids
        ]
        plans: list[Plan] = await asyncio.gather(*tasks)

        # Tag each plan with multi-agent metadata.
        coordinator_label = "greedy_science_roi" if optimize_science else "greedy_distance"
        for plan, rover_id in zip(plans, rover_ids):
            plan.planner = PlannerType.MULTI_AGENT
            plan.metadata["assigned_objectives"] = [o.id for o in assignments[rover_id]]
            plan.metadata["coordinator"] = coordinator_label
            if optimize_science:
                sci_total = sum(
                    (grid.get_cell(o.target_x, o.target_y).science_value
                     if grid.get_cell(o.target_x, o.target_y) else 0.0)
                    for o in assignments[rover_id]
                )
                plan.metadata["total_science_value"] = round(sci_total, 2)

        return plans

    async def _build_cost_matrix(
        self,
        rover_ids: list[str],
        positions: dict[str, tuple[int, int]],
        objectives: list,
        grid: Grid,
    ) -> dict[tuple[str, str], float]:
        """Run A* for every (rover, objective) pair, return cost dict."""
        pairs = [
            (rid, obj)
            for rid in rover_ids
            for obj in objectives
        ]

        async def _cost(rid: str, obj) -> tuple[tuple[str, str], float]:
            _, cost = astar(grid, positions[rid], (obj.target_x, obj.target_y))
            return (rid, obj.id), cost * settings.rover_move_cost

        results = await asyncio.gather(*[_cost(rid, obj) for rid, obj in pairs])
        return dict(results)

    async def _plan_rover(
        self,
        mission_id: str,
        rover_id: str,
        start: tuple[int, int],
        assigned: list,
        grid: Grid,
    ) -> Plan:
        request = PlanRequest(
            mission_id=mission_id,
            rover_id=rover_id,
            start_x=start[0],
            start_y=start[1],
        )
        return await self._planner.plan(request, grid, assigned)
