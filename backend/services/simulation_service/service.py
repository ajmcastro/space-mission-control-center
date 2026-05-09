"""Simulation service — owns the step-by-step execution loop."""
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.models.rover import Rover, RoverState, RoverSpec
from core.models.plan import Plan
from core.models.command import CommandType
from core.models.anomaly import Anomaly, AnomalyResolution
from core.events import EventBus, MissionEvent, EventType
from core.config import settings
from core.repositories import MissionRepository, RoverRepository, PlanRepository, AnomalyRepository
from .executor import CommandExecutor


class SimulationService:
    def __init__(self, event_bus: EventBus, session_factory: async_sessionmaker) -> None:
        self._bus = event_bus
        self._session_factory = session_factory
        self._executor = CommandExecutor(event_bus)
        self._running: dict[str, asyncio.Task] = {}
        self._missions = MissionRepository()
        self._rovers = RoverRepository()
        self._plans = PlanRepository()
        self._anomalies = AnomalyRepository()

    async def spawn_rover(self, session: AsyncSession, mission_id: str, name: str, x: int = 0, y: int = 0) -> Rover:
        rover = Rover(name=name, mission_id=mission_id, x=x, y=y)
        await self._rovers.save(session, rover)

        mission = await self._missions.get(session, mission_id)
        if mission and rover.id not in mission.rover_ids:
            mission.rover_ids.append(rover.id)
            await self._missions.save(session, mission)

        await session.commit()
        return rover

    async def get_rover(self, session: AsyncSession, rover_id: str) -> Rover | None:
        return await self._rovers.get(session, rover_id)

    async def list_rovers(self, session: AsyncSession, mission_id: str | None = None) -> list[Rover]:
        if mission_id:
            return await self._rovers.list_for_mission(session, mission_id)
        return await self._rovers.list_all(session)

    async def run_plan(self, mission_id: str, plan_id: str) -> None:
        """Start executing a plan in a background asyncio task with its own DB session."""
        if mission_id in self._running:
            existing = self._running[mission_id]
            if not existing.done():
                raise RuntimeError(f"Simulation already running for mission {mission_id}")

        task = asyncio.create_task(
            self._execute_plan(mission_id, plan_id),
            name=f"sim-{mission_id[:8]}",
        )
        self._running[mission_id] = task

    async def stop_simulation(self, mission_id: str) -> bool:
        task = self._running.get(mission_id)
        if task and not task.done():
            task.cancel()
            return True
        return False

    async def get_simulation_status(self, session: AsyncSession, mission_id: str) -> dict:
        task = self._running.get(mission_id)
        rovers = await self._rovers.list_for_mission(session, mission_id)
        return {
            "mission_id": mission_id,
            "running": bool(task and not task.done()),
            "rovers": [r.model_dump() for r in rovers],
        }

    async def _execute_plan(self, mission_id: str, plan_id: str) -> None:
        """Background task — owns its own DB session for the full execution lifetime."""
        async with self._session_factory() as session:
            plan = await self._plans.get(session, plan_id)
            if not plan:
                return

            mission = await self._missions.get(session, mission_id)
            if not mission:
                return

            env_repo = __import__("core.repositories", fromlist=["EnvironmentRepository"]).EnvironmentRepository()
            env = await env_repo.get(session, mission.environment_id)
            if not env:
                return

            rover = await self._rovers.get(session, plan.rover_id)
            if not rover:
                return

            anomalies: list[Anomaly] = []

            # Resume from the rover's current position instead of replaying from step 0.
            # Find the last MOVE step whose target matches the rover's position and start
            # from the step after it — this handles re-runs after comm_loss / low_battery recovery.
            resume_idx = 0
            for i, step in enumerate(plan.steps):
                if (step.command.type == CommandType.MOVE
                        and step.command.target_x == rover.x
                        and step.command.target_y == rover.y):
                    resume_idx = i + 1

            for step in plan.steps[resume_idx:]:
                if not rover.is_operational:
                    if rover.state == RoverState.STUCK:
                        await asyncio.sleep(1.0)
                        rover.state = RoverState.IDLE
                        if anomalies:
                            last = anomalies[-1]
                            last.resolve(AnomalyResolution.AUTO_RECOVERED)
                            await self._anomalies.resolve(
                                session, last.id, AnomalyResolution.AUTO_RECOVERED.value
                            )
                            await session.commit()
                    else:
                        break

                cmd, anomaly = await self._executor.execute(step.command, rover, env, session)
                await self._rovers.save(session, rover)

                if anomaly:
                    anomalies.append(anomaly)
                    await self._anomalies.append(session, anomaly)
                    await self._bus.publish(MissionEvent(
                        type=EventType.ANOMALY_DETECTED,
                        stream=settings.anomaly_stream,
                        mission_id=mission_id,
                        rover_id=rover.id,
                        payload={"type": anomaly.type.value, "severity": anomaly.severity.value},
                    ))

                # Mark objectives completed when rover reaches target
                for obj in mission.objectives:
                    if not obj.completed and (rover.x, rover.y) == (obj.target_x, obj.target_y):
                        obj.complete()
                await self._missions.save(session, mission)
                await session.commit()

            # Final mission completion check
            if all(o.completed for o in mission.objectives):
                mission.complete()
                await self._missions.save(session, mission)
                await session.commit()
                await self._bus.publish(MissionEvent(
                    type=EventType.MISSION_COMPLETED,
                    stream=settings.mission_stream,
                    mission_id=mission_id,
                ))
