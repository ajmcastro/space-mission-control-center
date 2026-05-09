from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db_models.rover import RoverRow
from core.models.rover import Rover, RoverState, RoverSpec


def _to_domain(row: RoverRow) -> Rover:
    return Rover(
        id=row.id,
        name=row.name,
        mission_id=row.mission_id,
        state=RoverState(row.state),
        x=row.x,
        y=row.y,
        battery=row.battery,
        spec=RoverSpec.model_validate(row.spec),
        path_history=[tuple(p) for p in row.path_history],
        samples_collected=row.samples_collected,
        steps_taken=row.steps_taken,
        total_distance=row.total_distance,
        anomalies_encountered=row.anomalies_encountered,
        created_at=row.created_at,
    )


def _to_row(rover: Rover) -> RoverRow:
    return RoverRow(
        id=rover.id,
        name=rover.name,
        mission_id=rover.mission_id,
        state=rover.state.value,
        x=rover.x,
        y=rover.y,
        battery=rover.battery,
        spec=rover.spec.model_dump(),
        path_history=[list(p) for p in rover.path_history],
        samples_collected=rover.samples_collected,
        steps_taken=rover.steps_taken,
        total_distance=rover.total_distance,
        anomalies_encountered=rover.anomalies_encountered,
        created_at=rover.created_at,
    )


class RoverRepository:
    async def get(self, session: AsyncSession, rover_id: str) -> Rover | None:
        row = await session.get(RoverRow, rover_id)
        return _to_domain(row) if row else None

    async def list_for_mission(self, session: AsyncSession, mission_id: str) -> list[Rover]:
        result = await session.execute(
            select(RoverRow).where(RoverRow.mission_id == mission_id)
        )
        return [_to_domain(r) for r in result.scalars().all()]

    async def list_all(self, session: AsyncSession) -> list[Rover]:
        result = await session.execute(select(RoverRow))
        return [_to_domain(r) for r in result.scalars().all()]

    async def delete_for_mission(self, session: AsyncSession, mission_id: str) -> None:
        await session.execute(
            delete(RoverRow).where(RoverRow.mission_id == mission_id)
        )

    async def save(self, session: AsyncSession, rover: Rover) -> Rover:
        existing = await session.get(RoverRow, rover.id)
        if existing:
            existing.state = rover.state.value
            existing.x = rover.x
            existing.y = rover.y
            existing.battery = rover.battery
            existing.spec = rover.spec.model_dump()
            existing.path_history = [list(p) for p in rover.path_history]
            existing.samples_collected = rover.samples_collected
            existing.steps_taken = rover.steps_taken
            existing.total_distance = rover.total_distance
            existing.anomalies_encountered = rover.anomalies_encountered
            existing.mission_id = rover.mission_id
        else:
            session.add(_to_row(rover))
        await session.flush()
        return rover
