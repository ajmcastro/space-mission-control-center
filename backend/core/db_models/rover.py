from datetime import datetime
from sqlalchemy import DateTime, Float, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column
from core.database import Base


class RoverRow(Base):
    __tablename__ = "rovers"

    id:                   Mapped[str]            = mapped_column(String, primary_key=True)
    name:                 Mapped[str]            = mapped_column(String, nullable=False)
    mission_id:           Mapped[str | None]     = mapped_column(String, nullable=True, index=True)
    state:                Mapped[str]            = mapped_column(String, default="idle")
    x:                    Mapped[int]            = mapped_column(Integer, default=0)
    y:                    Mapped[int]            = mapped_column(Integer, default=0)
    battery:              Mapped[float]          = mapped_column(Float, default=1000.0)
    spec:                 Mapped[dict]           = mapped_column(JSON, nullable=False)
    path_history:         Mapped[list]           = mapped_column(JSON, default=list)
    samples_collected:    Mapped[int]            = mapped_column(Integer, default=0)
    steps_taken:          Mapped[int]            = mapped_column(Integer, default=0)
    total_distance:       Mapped[float]          = mapped_column(Float, default=0.0)
    anomalies_encountered: Mapped[int]           = mapped_column(Integer, default=0)
    created_at:           Mapped[datetime]       = mapped_column(DateTime(timezone=True), nullable=False)

    # V4 Fault Protection System
    anomaly_streak:       Mapped[int]            = mapped_column(Integer, default=0)
    safe_mode_reason:     Mapped[str | None]     = mapped_column(String, nullable=True)

    # V4 AEGIS Autonomous Target Selection
    autonomy_level:       Mapped[str]            = mapped_column(String, default="supervised")
    aegis_objectives_generated: Mapped[int]      = mapped_column(Integer, default=0)
