from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.db_models.plan import PlanRow, PlanStepRow
from core.models.plan import Plan, PlanStep, PlannerType
from core.models.command import Command


def _step_to_domain(row: PlanStepRow) -> PlanStep:
    return PlanStep(
        sequence=row.sequence,
        command=Command.model_validate(row.command),
        estimated_battery_cost=row.estimated_battery_cost,
        rationale=row.rationale,
    )


def _plan_to_domain(row: PlanRow) -> Plan:
    return Plan(
        id=row.id,
        mission_id=row.mission_id,
        rover_id=row.rover_id,
        planner=PlannerType(row.planner),
        steps=[_step_to_domain(s) for s in row.steps],
        waypoints=[tuple(w) for w in row.waypoints],
        estimated_total_battery=row.estimated_total_battery,
        estimated_steps=row.estimated_steps,
        estimated_duration_seconds=row.estimated_duration_seconds,
        created_at=row.created_at,
    )


def _plan_to_row(plan: Plan) -> PlanRow:
    row = PlanRow(
        id=plan.id,
        mission_id=plan.mission_id,
        rover_id=plan.rover_id,
        planner=plan.planner.value,
        waypoints=[list(w) for w in plan.waypoints],
        estimated_total_battery=plan.estimated_total_battery,
        estimated_steps=plan.estimated_steps,
        estimated_duration_seconds=plan.estimated_duration_seconds,
        created_at=plan.created_at,
        steps=[
            PlanStepRow(
                id=f"{plan.id}-step-{s.sequence}",
                plan_id=plan.id,
                sequence=s.sequence,
                command=s.command.model_dump(mode="json"),
                estimated_battery_cost=s.estimated_battery_cost,
                rationale=s.rationale,
            )
            for s in plan.steps
        ],
    )
    return row


class PlanRepository:
    async def get(self, session: AsyncSession, plan_id: str) -> Plan | None:
        result = await session.execute(
            select(PlanRow)
            .options(selectinload(PlanRow.steps))
            .where(PlanRow.id == plan_id)
        )
        row = result.scalar_one_or_none()
        return _plan_to_domain(row) if row else None

    async def get_for_mission(self, session: AsyncSession, mission_id: str) -> Plan | None:
        result = await session.execute(
            select(PlanRow)
            .options(selectinload(PlanRow.steps))
            .where(PlanRow.mission_id == mission_id)
            .order_by(PlanRow.created_at.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        return _plan_to_domain(row) if row else None

    async def list_for_mission(self, session: AsyncSession, mission_id: str) -> list[Plan]:
        result = await session.execute(
            select(PlanRow)
            .options(selectinload(PlanRow.steps))
            .where(PlanRow.mission_id == mission_id)
            .order_by(PlanRow.created_at.asc())
        )
        return [_plan_to_domain(row) for row in result.scalars().all()]

    async def delete_for_mission(self, session: AsyncSession, mission_id: str) -> None:
        """Delete all plans (and their steps via cascade) for a mission."""
        result = await session.execute(
            select(PlanRow.id).where(PlanRow.mission_id == mission_id)
        )
        plan_ids = result.scalars().all()
        if plan_ids:
            await session.execute(delete(PlanRow).where(PlanRow.id.in_(plan_ids)))

    async def save(self, session: AsyncSession, plan: Plan) -> Plan:
        existing = await session.get(PlanRow, plan.id)
        if existing:
            existing.estimated_total_battery = plan.estimated_total_battery
            existing.estimated_steps = plan.estimated_steps
            existing.waypoints = [list(w) for w in plan.waypoints]
        else:
            session.add(_plan_to_row(plan))
        await session.flush()
        return plan
