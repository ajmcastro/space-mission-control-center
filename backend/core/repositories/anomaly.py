from datetime import datetime, timezone
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db_models.anomaly import AnomalyRow
from core.models.anomaly import Anomaly, AnomalyType, AnomalySeverity, AnomalyResolution


def _to_domain(row: AnomalyRow) -> Anomaly:
    return Anomaly(
        id=row.id,
        type=AnomalyType(row.type),
        severity=AnomalySeverity(row.severity),
        mission_id=row.mission_id,
        rover_id=row.rover_id,
        x=row.x,
        y=row.y,
        description=row.description,
        detected_at=row.detected_at,
        resolved_at=row.resolved_at,
        resolution=AnomalyResolution(row.resolution),
        triggered_replan=row.triggered_replan,
        replan_mission_id=row.replan_mission_id,
    )


def _to_row(anomaly: Anomaly) -> AnomalyRow:
    return AnomalyRow(
        id=anomaly.id,
        type=anomaly.type.value,
        severity=anomaly.severity.value,
        mission_id=anomaly.mission_id,
        rover_id=anomaly.rover_id,
        x=anomaly.x,
        y=anomaly.y,
        description=anomaly.description,
        detected_at=anomaly.detected_at,
        resolved_at=anomaly.resolved_at,
        resolution=anomaly.resolution.value,
        triggered_replan=anomaly.triggered_replan,
        replan_mission_id=anomaly.replan_mission_id,
    )


class AnomalyRepository:
    async def append(self, session: AsyncSession, anomaly: Anomaly) -> None:
        session.add(_to_row(anomaly))
        await session.flush()

    async def get(self, session: AsyncSession, anomaly_id: str) -> Anomaly | None:
        row = await session.get(AnomalyRow, anomaly_id)
        return _to_domain(row) if row else None

    async def get_for_mission(
        self, session: AsyncSession, mission_id: str
    ) -> list[Anomaly]:
        result = await session.execute(
            select(AnomalyRow)
            .where(AnomalyRow.mission_id == mission_id)
            .order_by(AnomalyRow.detected_at)
        )
        return [_to_domain(r) for r in result.scalars().all()]

    async def get_all(self, session: AsyncSession) -> list[Anomaly]:
        result = await session.execute(
            select(AnomalyRow).order_by(AnomalyRow.detected_at)
        )
        return [_to_domain(r) for r in result.scalars().all()]

    async def delete_for_mission(self, session: AsyncSession, mission_id: str) -> None:
        await session.execute(
            delete(AnomalyRow).where(AnomalyRow.mission_id == mission_id)
        )

    async def resolve(
        self, session: AsyncSession, anomaly_id: str, resolution: str
    ) -> Anomaly | None:
        row = await session.get(AnomalyRow, anomaly_id)
        if not row:
            return None
        row.resolution = resolution
        row.resolved_at = datetime.now(timezone.utc)
        await session.flush()
        return _to_domain(row)
