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

log = structlog.get_logger(__name__)


class MultiAgentCoordinator:
    """
    Greedy distance-based objective assignment.

    For each objective (sorted by priority), assigns it to the rover
    with the lowest accumulated travel cost so far.  After assignment,
    runs A* per rover to build the final plans.
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

        # Greedy assignment: each objective goes to the rover with lowest
        # cumulative cost, weighted by priority (lower priority number = higher urgency).
        assignments: dict[str, list] = {rid: [] for rid in rover_ids}
        cumulative: dict[str, float] = {rid: 0.0 for rid in rover_ids}

        for obj in sorted(pending_objs, key=lambda o: o.priority):
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
        for plan, rover_id in zip(plans, rover_ids):
            plan.planner = PlannerType.MULTI_AGENT
            plan.metadata["assigned_objectives"] = [o.id for o in assignments[rover_id]]
            plan.metadata["coordinator"] = "greedy_distance"

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
