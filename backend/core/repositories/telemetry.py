from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db_models.telemetry import TelemetryEventRow
from core.models.telemetry import TelemetryEvent, TelemetryType


def _to_domain(row: TelemetryEventRow) -> TelemetryEvent:
    return TelemetryEvent(
        id=row.id,
        type=TelemetryType(row.type),
        mission_id=row.mission_id,
        rover_id=row.rover_id,
        timestamp=row.timestamp,
        x=row.x,
        y=row.y,
        battery=row.battery,
        battery_pct=row.battery_pct,
        payload=row.payload or {},
    )


def _to_row(event: TelemetryEvent) -> TelemetryEventRow:
    return TelemetryEventRow(
        id=event.id,
        type=event.type.value,
        mission_id=event.mission_id,
        rover_id=event.rover_id,
        timestamp=event.timestamp,
        x=event.x,
        y=event.y,
        battery=event.battery,
        battery_pct=event.battery_pct,
        payload=event.payload,
    )


class TelemetryRepository:
    async def append(self, session: AsyncSession, event: TelemetryEvent) -> None:
        session.add(_to_row(event))
        await session.flush()

    async def get_for_mission(
        self, session: AsyncSession, mission_id: str, limit: int = 500
    ) -> list[TelemetryEvent]:
        result = await session.execute(
            select(TelemetryEventRow)
            .where(TelemetryEventRow.mission_id == mission_id)
            .order_by(TelemetryEventRow.timestamp)
            .limit(limit)
        )
        return [_to_domain(r) for r in result.scalars().all()]

    async def delete_for_mission(self, session: AsyncSession, mission_id: str) -> None:
        await session.execute(
            delete(TelemetryEventRow).where(TelemetryEventRow.mission_id == mission_id)
        )

    async def get_for_rover(
        self, session: AsyncSession, rover_id: str, limit: int = 200
    ) -> list[TelemetryEvent]:
        result = await session.execute(
            select(TelemetryEventRow)
            .where(TelemetryEventRow.rover_id == rover_id)
            .order_by(TelemetryEventRow.timestamp)
            .limit(limit)
        )
        return [_to_domain(r) for r in result.scalars().all()]
