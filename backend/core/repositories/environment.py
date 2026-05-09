from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db_models.environment import EnvironmentRow
from core.models.environment import Environment, Grid


def _to_domain(row: EnvironmentRow) -> Environment:
    return Environment.model_validate({
        "id": row.id,
        "name": row.name,
        "grid": row.grid,
        "temperature_k": row.temperature_k,
        "pressure_pa": row.pressure_pa,
        "active_geysers": row.active_geysers,
        "hazard_zones": row.hazard_zones,
    })


def _to_row(env: Environment) -> EnvironmentRow:
    return EnvironmentRow(
        id=env.id,
        name=env.name,
        grid=env.grid.model_dump(mode="json"),
        temperature_k=env.temperature_k,
        pressure_pa=env.pressure_pa,
        active_geysers=[list(g) for g in env.active_geysers],
        hazard_zones=[list(h) for h in env.hazard_zones],
    )


class EnvironmentRepository:
    async def get(self, session: AsyncSession, env_id: str) -> Environment | None:
        row = await session.get(EnvironmentRow, env_id)
        return _to_domain(row) if row else None

    async def delete(self, session: AsyncSession, env_id: str) -> None:
        row = await session.get(EnvironmentRow, env_id)
        if row:
            await session.delete(row)

    async def save(self, session: AsyncSession, env: Environment) -> Environment:
        existing = await session.get(EnvironmentRow, env.id)
        if existing:
            existing.name = env.name
            existing.grid = env.grid.model_dump(mode="json")
            existing.temperature_k = env.temperature_k
            existing.pressure_pa = env.pressure_pa
            existing.active_geysers = [list(g) for g in env.active_geysers]
            existing.hazard_zones = [list(h) for h in env.hazard_zones]
        else:
            session.add(_to_row(env))
        await session.flush()
        return env
