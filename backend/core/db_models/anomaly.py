from datetime import datetime
from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from core.database import Base


class AnomalyRow(Base):
    __tablename__ = "anomalies"

    id:                  Mapped[str]            = mapped_column(String, primary_key=True)
    type:                Mapped[str]            = mapped_column(String, nullable=False)
    severity:            Mapped[str]            = mapped_column(String, nullable=False)
    mission_id:          Mapped[str]            = mapped_column(String, nullable=False, index=True)
    rover_id:            Mapped[str]            = mapped_column(String, nullable=False)
    x:                   Mapped[int]            = mapped_column(Integer, nullable=False)
    y:                   Mapped[int]            = mapped_column(Integer, nullable=False)
    description:         Mapped[str]            = mapped_column(Text, default="")
    detected_at:         Mapped[datetime]       = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at:         Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution:          Mapped[str]            = mapped_column(String, default="pending")
    triggered_replan:    Mapped[bool]           = mapped_column(Boolean, default=False)
    replan_mission_id:   Mapped[str | None]     = mapped_column(String, nullable=True)
