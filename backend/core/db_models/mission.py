from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from core.database import Base


class MissionRow(Base):
    __tablename__ = "missions"

    id:             Mapped[str]            = mapped_column(String, primary_key=True)
    name:           Mapped[str]            = mapped_column(String, nullable=False)
    description:    Mapped[str]            = mapped_column(Text, default="")
    status:         Mapped[str]            = mapped_column(String, nullable=False, default="draft")
    environment_id: Mapped[str]            = mapped_column(String, nullable=False)
    plan_id:        Mapped[str | None]     = mapped_column(String, nullable=True)
    rover_ids:      Mapped[list]           = mapped_column(JSON, default=list)
    created_at:     Mapped[datetime]       = mapped_column(DateTime(timezone=True), nullable=False)
    started_at:     Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at:   Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    objectives: Mapped[list["ObjectiveRow"]] = relationship(
        "ObjectiveRow", back_populates="mission",
        cascade="all, delete-orphan", order_by="ObjectiveRow.priority",
    )


class ObjectiveRow(Base):
    __tablename__ = "objectives"

    id:           Mapped[str]            = mapped_column(String, primary_key=True)
    mission_id:   Mapped[str]            = mapped_column(String, ForeignKey("missions.id", ondelete="CASCADE"), nullable=False)
    type:         Mapped[str]            = mapped_column(String, nullable=False)
    target_x:     Mapped[int]            = mapped_column(Integer, nullable=False)
    target_y:     Mapped[int]            = mapped_column(Integer, nullable=False)
    description:  Mapped[str]            = mapped_column(Text, default="")
    priority:     Mapped[int]            = mapped_column(Integer, default=1)
    completed:    Mapped[bool]           = mapped_column(Boolean, default=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    mission: Mapped["MissionRow"] = relationship("MissionRow", back_populates="objectives")
