"""Simulation service — owns the step-by-step execution loop."""
import asyncio
import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.models.rover import Rover, RoverState
from core.models.command import Command, CommandType
from core.models.anomaly import Anomaly, AnomalyResolution
from core.models.plan import PlanStep
from core.events import EventBus, MissionEvent, EventType
from core.config import settings
from core.repositories import (
    MissionRepository, RoverRepository, PlanRepository,
    AnomalyRepository, EnvironmentRepository,
)
from core.models.environment import Environment
from .executor import CommandExecutor
from .fault_protection import FaultProtectionEngine, FPSAction
from .terrain_events import TerrainEventEngine

log = structlog.get_logger(__name__)


class SimulationService:
    def __init__(self, event_bus: EventBus, session_factory: async_sessionmaker) -> None:
        self._bus = event_bus
        self._session_factory = session_factory
        self._executor = CommandExecutor(event_bus)
        self._fps = FaultProtectionEngine()
        self._terrain = TerrainEventEngine()
        self._running: dict[str, asyncio.Task] = {}       # plan_id → task
        self._mission_plans: dict[str, list[str]] = {}    # mission_id → [plan_id, ...]
        self._missions = MissionRepository()
        self._rovers = RoverRepository()
        self._plans = PlanRepository()
        self._anomalies = AnomalyRepository()

    async def _reveal(
        self,
        session: AsyncSession,
        env: Environment,
        mission_id: str,
        rover_id: str,
        cx: int,
        cy: int,
    ) -> None:
        """Reveal cells around (cx, cy) and persist + broadcast if any were newly uncovered."""
        if not settings.fog_of_war:
            return
        env_repo = EnvironmentRepository()
        newly = env.grid.reveal_around(cx, cy, settings.sensor_range)
        if newly:
            await env_repo.save(session, env)
            await session.commit()
            await self._bus.publish(MissionEvent(
                type=EventType.CELLS_REVEALED,
                stream=settings.telemetry_stream,
                mission_id=mission_id,
                rover_id=rover_id,
                payload={"cells": newly, "count": len(newly)},
            ))

    async def spawn_rover(self, session: AsyncSession, mission_id: str, name: str, x: int = 0, y: int = 0) -> Rover:
        rover = Rover(name=name, mission_id=mission_id, x=x, y=y)
        await self._rovers.save(session, rover)

        mission = await self._missions.get(session, mission_id)
        if mission and rover.id not in mission.rover_ids:
            mission.rover_ids.append(rover.id)
            await self._missions.save(session, mission)

        # Reveal terrain around spawn position.
        env_repo = EnvironmentRepository()
        env = await env_repo.get(session, mission.environment_id) if mission else None
        if env:
            await self._reveal(session, env, mission_id, rover.id, x, y)

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
        existing = self._running.get(plan_id)
        if existing and not existing.done():
            raise RuntimeError(f"Plan {plan_id} is already executing")

        task = asyncio.create_task(
            self._execute_plan(mission_id, plan_id),
            name=f"sim-{plan_id[:8]}",
        )

        def _on_done(t: asyncio.Task) -> None:
            exc = t.exception() if not t.cancelled() else None
            if exc:
                log.error("execute_plan_task_failed", plan_id=plan_id, mission_id=mission_id, exc_info=exc)

        task.add_done_callback(_on_done)
        self._running[plan_id] = task
        self._mission_plans.setdefault(mission_id, [])
        if plan_id not in self._mission_plans[mission_id]:
            self._mission_plans[mission_id].append(plan_id)

    async def stop_simulation(self, mission_id: str) -> bool:
        """Cancel all running plan tasks for a mission."""
        plan_ids = self._mission_plans.get(mission_id, [])
        stopped = False
        for plan_id in plan_ids:
            task = self._running.get(plan_id)
            if task and not task.done():
                task.cancel()
                stopped = True
        return stopped

    async def get_simulation_status(self, session: AsyncSession, mission_id: str) -> dict:
        plan_ids = self._mission_plans.get(mission_id, [])
        running = any(
            (t := self._running.get(pid)) is not None and not t.done()
            for pid in plan_ids
        )
        rovers = await self._rovers.list_for_mission(session, mission_id)
        return {
            "mission_id": mission_id,
            "running": running,
            "rovers": [r.model_dump() for r in rovers],
        }

    async def _execute_plan(self, mission_id: str, plan_id: str) -> None:
        """Background task — owns its own DB session for the full execution lifetime."""
        log.info("execute_plan_start", plan_id=plan_id, mission_id=mission_id)
        try:
            await self._run_plan_loop(mission_id, plan_id)
        except Exception:
            log.exception("execute_plan_error", plan_id=plan_id, mission_id=mission_id)
            raise

    async def _run_plan_loop(self, mission_id: str, plan_id: str) -> None:
        async with self._session_factory() as session:
            plan = await self._plans.get(session, plan_id)
            if not plan:
                log.warning("execute_plan_no_plan", plan_id=plan_id)
                return

            mission = await self._missions.get(session, mission_id)
            if not mission:
                log.warning("execute_plan_no_mission", mission_id=mission_id)
                return

            env_repo = EnvironmentRepository()
            env = await env_repo.get(session, mission.environment_id)
            if not env:
                log.warning("execute_plan_no_env", env_id=mission.environment_id)
                return

            rover = await self._rovers.get(session, plan.rover_id)
            if not rover:
                log.warning("execute_plan_no_rover", rover_id=plan.rover_id)
                return

            log.info(
                "execute_plan_ready",
                plan_id=plan_id, rover=rover.name,
                steps=len(plan.steps), rover_pos=(rover.x, rover.y),
            )

            anomalies: list[Anomaly] = []

            # Resume from the rover's current position only when it has already moved
            # (steps_taken > 0). A fresh rover always starts from step 0, even if its
            # spawn point happens to match a later waypoint in the plan (e.g. return_to_base).
            resume_idx = 0
            if rover.steps_taken > 0:
                for i, step in enumerate(plan.steps):
                    if (step.command.type == CommandType.MOVE
                            and step.command.target_x == rover.x
                            and step.command.target_y == rover.y):
                        resume_idx = i + 1

            log.info("execute_plan_resume", resume_idx=resume_idx, total_steps=len(plan.steps))

            pending = list(plan.steps[resume_idx:])
            idx = 0
            while idx < len(pending):
                step = pending[idx]

                # Non-operational state: FPS already decided last iteration; honour it.
                if not rover.is_operational:
                    log.info(
                        "execute_plan_halted",
                        rover_state=rover.state.value, step=step.sequence,
                    )
                    break

                cmd, anomaly = await self._executor.execute(step.command, rover, env, session)
                await self._rovers.save(session, rover)

                # Reveal terrain around the rover's new position after every move.
                await self._reveal(session, env, mission_id, rover.id, rover.x, rover.y)

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

                    # ── Fault Protection System ──────────────────────────────
                    fps_result = self._fps.handle(
                        rover, anomaly, mission.objectives, env.grid
                    )

                    await self._bus.publish(MissionEvent(
                        type=EventType.FPS_RULE_TRIGGERED,
                        stream=settings.telemetry_stream,
                        mission_id=mission_id,
                        rover_id=rover.id,
                        payload={
                            "anomaly_type": anomaly.type.value,
                            "action": fps_result.action.value,
                            "reason": fps_result.reason,
                            "streak": rover.anomaly_streak,
                        },
                    ))

                    if fps_result.action == FPSAction.SAFE_MODE:
                        rover.state = RoverState.SAFE_MODE
                        rover.safe_mode_reason = fps_result.reason
                        await self._rovers.save(session, rover)
                        await session.commit()
                        await self._bus.publish(MissionEvent(
                            type=EventType.SAFE_MODE_ENTERED,
                            stream=settings.telemetry_stream,
                            mission_id=mission_id,
                            rover_id=rover.id,
                            payload={"reason": fps_result.reason},
                        ))
                        log.warning(
                            "fps_safe_mode_entered",
                            rover=rover.name, reason=fps_result.reason,
                        )
                        break

                    if fps_result.action == FPSAction.CONTINUE:
                        anomaly.resolve(fps_result.resolution)
                        await self._anomalies.resolve(
                            session, anomaly.id, fps_result.resolution.value
                        )
                        await session.commit()
                        # Fall through: advance idx normally below.

                    elif fps_result.action == FPSAction.RETRY:
                        # Restore IDLE so the executor can run the step again.
                        rover.state = RoverState.IDLE
                        await self._rovers.save(session, rover)
                        await session.commit()
                        await asyncio.sleep(1.0)
                        # Do NOT advance idx — same step will be retried.
                        continue

                    elif fps_result.action == FPSAction.REVERSE:
                        if rover.path_history:
                            px, py = rover.path_history[-1]
                            reverse_cmd = Command(
                                mission_id=mission_id,
                                rover_id=rover.id,
                                type=CommandType.MOVE,
                                sequence=-1,
                                target_x=px,
                                target_y=py,
                            )
                            rover.state = RoverState.IDLE
                            await self._rovers.save(session, rover)
                            await session.commit()
                            await self._executor.execute(reverse_cmd, rover, env, session)
                            await self._rovers.save(session, rover)
                            await self._reveal(session, env, mission_id, rover.id, rover.x, rover.y)
                        anomaly.resolve(fps_result.resolution)
                        await self._anomalies.resolve(
                            session, anomaly.id, fps_result.resolution.value
                        )
                        rover.state = RoverState.IDLE
                        await self._rovers.save(session, rover)
                        await session.commit()
                        # Retry the original step (do NOT advance idx).
                        continue

                    elif fps_result.action == FPSAction.REPLAN:
                        # Swap remaining steps for the freshly computed commands.
                        new_steps = [
                            PlanStep(
                                sequence=i,
                                command=c,
                                rationale="FPS replan",
                            )
                            for i, c in enumerate(fps_result.new_commands)
                        ]
                        pending = new_steps
                        idx = 0
                        anomaly.resolve(fps_result.resolution)
                        await self._anomalies.resolve(
                            session, anomaly.id, fps_result.resolution.value
                        )
                        rover.state = RoverState.IDLE
                        await self._rovers.save(session, rover)
                        await session.commit()
                        await self._bus.publish(MissionEvent(
                            type=EventType.REPLAN_TRIGGERED,
                            stream=settings.mission_stream,
                            mission_id=mission_id,
                            rover_id=rover.id,
                            payload={"reason": fps_result.reason, "new_steps": len(new_steps)},
                        ))
                        log.info(
                            "fps_replanned",
                            rover=rover.name,
                            reason=fps_result.reason,
                            new_steps=len(new_steps),
                        )
                        continue
                else:
                    # Clean step — reset the anomaly streak.
                    self._fps.reset_streak(rover)

                # ── Dynamic terrain tick (V4) ────────────────────────────────
                terrain_changes = self._terrain.tick(env, mission_id, rover.id)
                if terrain_changes:
                    await env_repo.save(session, env)
                    for change in terrain_changes:
                        await self._bus.publish(MissionEvent(
                            type=change.event_type,
                            stream=settings.telemetry_stream,
                            mission_id=mission_id,
                            rover_id=rover.id,
                            payload=change.payload | {"description": change.description,
                                                       "x": change.x, "y": change.y},
                        ))
                        # If an ice fracture or geyser eruption blocks the planned path,
                        # synthesise a PATH_BLOCKED anomaly so the FPS can replan.
                        affected = (change.x, change.y)
                        path_coords = {
                            (s.command.target_x, s.command.target_y)
                            for s in pending[idx:]
                            if s.command.target_x is not None
                        }
                        if affected in path_coords and change.event_type in (
                            EventType.ICE_FRACTURE, EventType.GEYSER_ERUPTION
                        ):
                            from core.models.anomaly import Anomaly, AnomalyType, AnomalySeverity
                            path_anomaly = Anomaly(
                                type=AnomalyType.PATH_BLOCKED,
                                severity=AnomalySeverity.HIGH,
                                mission_id=mission_id,
                                rover_id=rover.id,
                                x=change.x, y=change.y,
                                description=change.description,
                            )
                            await self._anomalies.append(session, path_anomaly)
                            await self._bus.publish(MissionEvent(
                                type=EventType.ANOMALY_DETECTED,
                                stream=settings.anomaly_stream,
                                mission_id=mission_id,
                                rover_id=rover.id,
                                payload={"type": path_anomaly.type.value,
                                         "severity": path_anomaly.severity.value},
                            ))
                            fps_result = self._fps.handle(
                                rover, path_anomaly, mission.objectives, env.grid
                            )
                            if fps_result.action == FPSAction.REPLAN and fps_result.new_commands:
                                new_steps = [
                                    PlanStep(sequence=i, command=c, rationale="terrain replan")
                                    for i, c in enumerate(fps_result.new_commands)
                                ]
                                pending = new_steps
                                idx = 0
                                path_anomaly.resolve(fps_result.resolution)
                                await self._anomalies.resolve(
                                    session, path_anomaly.id, fps_result.resolution.value
                                )
                                await self._bus.publish(MissionEvent(
                                    type=EventType.REPLAN_TRIGGERED,
                                    stream=settings.mission_stream,
                                    mission_id=mission_id,
                                    rover_id=rover.id,
                                    payload={"reason": fps_result.reason,
                                             "new_steps": len(new_steps)},
                                ))
                                # Restart the loop from step 0 of the new plan so that
                                # pending[0] is not skipped by the idx += 1 below.
                                continue

                # Mark objectives completed when rover reaches a target position.
                for obj in mission.objectives:
                    if not obj.completed and (rover.x, rover.y) == (obj.target_x, obj.target_y):
                        obj.complete()
                await self._missions.save(session, mission)
                await session.commit()

                idx += 1

            log.info("execute_plan_done", plan_id=plan_id, rover_pos=(rover.x, rover.y))

            # Final objective check — guards against objectives whose matching step was
            # skipped by a terrain-replan or whose loop iteration exited early.
            final_obj_changed = False
            for obj in mission.objectives:
                if not obj.completed and (rover.x, rover.y) == (obj.target_x, obj.target_y):
                    obj.complete()
                    final_obj_changed = True
            if final_obj_changed:
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
