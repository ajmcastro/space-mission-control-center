import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.mission import Mission, MissionStatus, Objective
from core.models.environment import Environment
from core.events import EventBus, MissionEvent, EventType
from core.config import settings
from core.repositories import (
    MissionRepository, EnvironmentRepository,
    RoverRepository, PlanRepository, TelemetryRepository, AnomalyRepository,
)
from .schemas import MissionCreate, MissionUpdate
from .store import generate_env


class MissionService:
    def __init__(self, event_bus: EventBus) -> None:
        self._bus = event_bus
        self._missions = MissionRepository()
        self._environments = EnvironmentRepository()
        self._rovers = RoverRepository()
        self._plans = PlanRepository()
        self._telemetry = TelemetryRepository()
        self._anomalies = AnomalyRepository()

    async def create_mission(self, session: AsyncSession, data: MissionCreate) -> Mission:
        env_id = data.environment_id or str(uuid.uuid4())
        env = generate_env(env_id, data.grid_width, data.grid_height)
        await self._environments.save(session, env)

        objectives = [
            Objective(
                type=o.type,
                target_x=o.target_x,
                target_y=o.target_y,
                description=o.description,
                priority=o.priority,
            )
            for o in data.objectives
        ]

        mission = Mission(
            name=data.name,
            description=data.description,
            environment_id=env_id,
            objectives=objectives,
        )
        await self._missions.save(session, mission)
        await session.commit()

        await self._bus.publish(MissionEvent(
            type=EventType.MISSION_CREATED,
            stream=settings.mission_stream,
            mission_id=mission.id,
            payload={"name": mission.name},
        ))
        return mission

    async def get_mission(self, session: AsyncSession, mission_id: str) -> Mission | None:
        return await self._missions.get(session, mission_id)

    async def list_missions(self, session: AsyncSession) -> list[Mission]:
        return await self._missions.list(session)

    async def update_mission(
        self, session: AsyncSession, mission_id: str, data: MissionUpdate
    ) -> Mission | None:
        mission = await self._missions.get(session, mission_id)
        if not mission:
            return None
        if data.name is not None:
            mission.name = data.name
        if data.description is not None:
            mission.description = data.description
        if data.status is not None:
            mission.status = data.status
        await self._missions.save(session, mission)
        await session.commit()
        return mission

    async def start_mission(self, session: AsyncSession, mission_id: str) -> Mission | None:
        mission = await self._missions.get(session, mission_id)
        if not mission or mission.status not in (MissionStatus.DRAFT, MissionStatus.PLANNED):
            return None
        mission.start()
        await self._missions.save(session, mission)
        await session.commit()
        await self._bus.publish(MissionEvent(
            type=EventType.MISSION_STARTED,
            stream=settings.mission_stream,
            mission_id=mission.id,
        ))
        return mission

    async def complete_mission(self, session: AsyncSession, mission_id: str) -> Mission | None:
        mission = await self._missions.get(session, mission_id)
        if not mission:
            return None
        mission.complete()
        await self._missions.save(session, mission)
        await session.commit()
        await self._bus.publish(MissionEvent(
            type=EventType.MISSION_COMPLETED,
            stream=settings.mission_stream,
            mission_id=mission.id,
        ))
        return mission

    async def get_environment(self, session: AsyncSession, env_id: str) -> Environment | None:
        return await self._environments.get(session, env_id)

    async def delete_mission(self, session: AsyncSession, mission_id: str) -> bool:
        mission = await self._missions.get(session, mission_id)
        if not mission:
            return False
        await self._telemetry.delete_for_mission(session, mission_id)
        await self._anomalies.delete_for_mission(session, mission_id)
        await self._rovers.delete_for_mission(session, mission_id)
        await self._plans.delete_for_mission(session, mission_id)
        await self._environments.delete(session, mission.environment_id)
        await self._missions.delete(session, mission_id)
        await session.commit()
        return True

    async def get_mission_environment(
        self, session: AsyncSession, mission_id: str
    ) -> Environment | None:
        mission = await self._missions.get(session, mission_id)
        if not mission:
            return None
        return await self._environments.get(session, mission.environment_id)
