from datetime import datetime
from sqlalchemy import DateTime, Float, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from core.database import Base


class TelemetryEventRow(Base):
    __tablename__ = "telemetry_events"

    id:          Mapped[str]           = mapped_column(String, primary_key=True)
    type:        Mapped[str]           = mapped_column(String, nullable=False)
    mission_id:  Mapped[str]           = mapped_column(String, nullable=False, index=True)
    rover_id:    Mapped[str]           = mapped_column(String, nullable=False, index=True)
    timestamp:   Mapped[datetime]      = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    x:           Mapped[int | None]    = mapped_column(Integer, nullable=True)
    y:           Mapped[int | None]    = mapped_column(Integer, nullable=True)
    battery:     Mapped[float | None]  = mapped_column(Float, nullable=True)
    battery_pct: Mapped[float | None]  = mapped_column(Float, nullable=True)
    payload:     Mapped[dict]          = mapped_column(JSON, default=dict)
