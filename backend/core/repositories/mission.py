from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.db_models.mission import MissionRow, ObjectiveRow
from core.models.mission import Mission, Objective, MissionStatus, ObjectiveType


def _obj_to_domain(row: ObjectiveRow) -> Objective:
    return Objective(
        id=row.id,
        type=ObjectiveType(row.type),
        target_x=row.target_x,
        target_y=row.target_y,
        description=row.description,
        priority=row.priority,
        completed=row.completed,
        completed_at=row.completed_at,
    )


def _mission_to_domain(row: MissionRow) -> Mission:
    return Mission(
        id=row.id,
        name=row.name,
        description=row.description,
        status=MissionStatus(row.status),
        environment_id=row.environment_id,
        rover_ids=list(row.rover_ids or []),
        objectives=[_obj_to_domain(o) for o in row.objectives],
        plan_id=row.plan_id,
        created_at=row.created_at,
        started_at=row.started_at,
        completed_at=row.completed_at,
    )


def _mission_to_row(mission: Mission) -> MissionRow:
    return MissionRow(
        id=mission.id,
        name=mission.name,
        description=mission.description,
        status=mission.status.value,
        environment_id=mission.environment_id,
        plan_id=mission.plan_id,
        rover_ids=list(mission.rover_ids),
        created_at=mission.created_at,
        started_at=mission.started_at,
        completed_at=mission.completed_at,
        objectives=[_obj_to_row(o, mission.id) for o in mission.objectives],
    )


def _obj_to_row(obj: Objective, mission_id: str) -> ObjectiveRow:
    return ObjectiveRow(
        id=obj.id,
        mission_id=mission_id,
        type=obj.type.value,
        target_x=obj.target_x,
        target_y=obj.target_y,
        description=obj.description,
        priority=obj.priority,
        completed=obj.completed,
        completed_at=obj.completed_at,
    )


class MissionRepository:
    async def get(self, session: AsyncSession, mission_id: str) -> Mission | None:
        result = await session.execute(
            select(MissionRow)
            .options(selectinload(MissionRow.objectives))
            .where(MissionRow.id == mission_id)
        )
        row = result.scalar_one_or_none()
        return _mission_to_domain(row) if row else None

    async def list(self, session: AsyncSession) -> list[Mission]:
        result = await session.execute(
            select(MissionRow).options(selectinload(MissionRow.objectives))
        )
        return [_mission_to_domain(r) for r in result.scalars().all()]

    async def save(self, session: AsyncSession, mission: Mission) -> Mission:
        result = await session.execute(
            select(MissionRow)
            .options(selectinload(MissionRow.objectives))
            .where(MissionRow.id == mission.id)
        )
        existing = result.scalar_one_or_none()
        if existing:
            # Update scalar fields
            existing.name = mission.name
            existing.description = mission.description
            existing.status = mission.status.value
            existing.plan_id = mission.plan_id
            existing.rover_ids = list(mission.rover_ids)
            existing.started_at = mission.started_at
            existing.completed_at = mission.completed_at
            # Sync objectives: delete removed, upsert remaining
            existing_ids = {o.id for o in existing.objectives}
            new_ids = {o.id for o in mission.objectives}
            for obj_row in list(existing.objectives):
                if obj_row.id not in new_ids:
                    await session.delete(obj_row)
            for obj in mission.objectives:
                if obj.id in existing_ids:
                    obj_row = next(o for o in existing.objectives if o.id == obj.id)
                    obj_row.completed = obj.completed
                    obj_row.completed_at = obj.completed_at
                    obj_row.priority = obj.priority
                else:
                    session.add(_obj_to_row(obj, mission.id))
        else:
            session.add(_mission_to_row(mission))
        await session.flush()
        return mission

    async def delete(self, session: AsyncSession, mission_id: str) -> None:
        row = await session.get(MissionRow, mission_id)
        if row:
            await session.delete(row)
            await session.flush()
