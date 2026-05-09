from datetime import datetime
from sqlalchemy import DateTime, Float, Integer, JSON, String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from core.database import Base


class PlanRow(Base):
    __tablename__ = "plans"

    id:                       Mapped[str]     = mapped_column(String, primary_key=True)
    mission_id:               Mapped[str]     = mapped_column(String, nullable=False, index=True)
    rover_id:                 Mapped[str]     = mapped_column(String, nullable=False)
    planner:                  Mapped[str]     = mapped_column(String, nullable=False)
    waypoints:                Mapped[list]    = mapped_column(JSON, default=list)
    estimated_total_battery:  Mapped[float]   = mapped_column(Float, default=0.0)
    estimated_steps:          Mapped[int]     = mapped_column(Integer, default=0)
    estimated_duration_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    created_at:               Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    steps: Mapped[list["PlanStepRow"]] = relationship(
        "PlanStepRow", back_populates="plan",
        cascade="all, delete-orphan", order_by="PlanStepRow.sequence",
    )


class PlanStepRow(Base):
    __tablename__ = "plan_steps"

    id:                    Mapped[str]   = mapped_column(String, primary_key=True)
    plan_id:               Mapped[str]   = mapped_column(String, ForeignKey("plans.id", ondelete="CASCADE"), nullable=False)
    sequence:              Mapped[int]   = mapped_column(Integer, nullable=False)
    command:               Mapped[dict]  = mapped_column(JSON, nullable=False)
    estimated_battery_cost: Mapped[float] = mapped_column(Float, default=0.0)
    rationale:             Mapped[str]   = mapped_column(Text, default="")

    plan: Mapped["PlanRow"] = relationship("PlanRow", back_populates="steps")
