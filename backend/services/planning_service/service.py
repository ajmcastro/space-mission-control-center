import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.plan import Plan, PlanStep, PlannerType
from core.models.command import Command, CommandType
from core.models.environment import Grid
from core.events import EventBus, MissionEvent, EventType
from core.config import settings
from core.repositories import MissionRepository, EnvironmentRepository, PlanRepository
from .astar import astar, path_battery_cost
from .schemas import PlanRequest, WaypointRequest


class PlannerInterface:
    """Extension point — plug in RL or MAS planners here."""
    async def plan(self, request: PlanRequest, grid: Grid) -> Plan:
        raise NotImplementedError


class AStarPlanner(PlannerInterface):
    def __init__(self, move_cost_per_cell: float = 10.0) -> None:
        self._move_cost = move_cost_per_cell

    async def plan(self, request: PlanRequest, grid: Grid, objectives: list) -> Plan:
        plan = Plan(
            mission_id=request.mission_id,
            rover_id=request.rover_id,
            planner=PlannerType.ASTAR,
        )

        current_x, current_y = request.start_x, request.start_y

        for obj in sorted(objectives, key=lambda o: o.priority):
            if obj.completed:
                continue
            path, cost = astar(grid, (current_x, current_y), (obj.target_x, obj.target_y))
            if path is None:
                continue

            plan.waypoints.extend(path[1:])

            for wx, wy in path[1:]:
                cmd = Command(
                    mission_id=request.mission_id,
                    rover_id=request.rover_id,
                    type=CommandType.MOVE,
                    sequence=len(plan.steps),
                    target_x=wx,
                    target_y=wy,
                )
                cell = grid.get_cell(wx, wy)
                cell_cost = self._move_cost * (cell.movement_cost if cell else 1.0)
                plan.add_step(cmd, cost=cell_cost, rationale=f"A* path to objective {obj.id[:8]}")

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
                plan.add_step(sample_cmd, cost=settings.rover_sample_cost, rationale=f"Collect sample at objective {obj.id[:8]}")

            current_x, current_y = obj.target_x, obj.target_y

        plan.estimated_steps = len(plan.steps)
        plan.estimated_duration_seconds = plan.estimated_steps * settings.sim_step_delay_seconds
        return plan


class PlanningService:
    def __init__(self, event_bus: EventBus) -> None:
        self._bus = event_bus
        self._astar = AStarPlanner(move_cost_per_cell=settings.rover_move_cost)
        self._missions = MissionRepository()
        self._environments = EnvironmentRepository()
        self._plans = PlanRepository()

    async def create_plan(self, session: AsyncSession, request: PlanRequest) -> Plan | None:
        mission = await self._missions.get(session, request.mission_id)
        if not mission:
            return None
        env = await self._environments.get(session, mission.environment_id)
        if not env:
            return None

        plan = await self._astar.plan(request, env.grid, mission.objectives)
        await self._plans.save(session, plan)

        mission.plan_id = plan.id
        await self._missions.save(session, mission)
        await session.commit()

        await self._bus.publish(MissionEvent(
            type=EventType.PLAN_CREATED,
            stream=settings.mission_stream,
            mission_id=request.mission_id,
            rover_id=request.rover_id,
            payload={"plan_id": plan.id, "steps": str(plan.estimated_steps)},
        ))
        return plan

    async def create_manual_plan(self, session: AsyncSession, request: WaypointRequest) -> Plan | None:
        mission = await self._missions.get(session, request.mission_id)
        if not mission:
            return None
        env = await self._environments.get(session, mission.environment_id)
        if not env:
            return None

        plan = Plan(
            mission_id=request.mission_id,
            rover_id=request.rover_id,
            planner=PlannerType.MANUAL,
        )
        for i, (wx, wy) in enumerate(request.waypoints):
            cmd = Command(
                mission_id=request.mission_id,
                rover_id=request.rover_id,
                type=CommandType.MOVE,
                sequence=i,
                target_x=wx,
                target_y=wy,
            )
            cell = env.grid.get_cell(wx, wy)
            cost = settings.rover_move_cost * (cell.movement_cost if cell else 1.0)
            plan.add_step(cmd, cost=cost, rationale="Manual waypoint")

        plan.waypoints = list(request.waypoints)
        plan.estimated_steps = len(plan.steps)

        mission.plan_id = plan.id
        await self._plans.save(session, plan)
        await self._missions.save(session, mission)
        await session.commit()
        return plan

    async def get_plan(self, session: AsyncSession, plan_id: str) -> Plan | None:
        return await self._plans.get(session, plan_id)

    async def get_mission_plan(self, session: AsyncSession, mission_id: str) -> Plan | None:
        return await self._plans.get_for_mission(session, mission_id)
