from sqlalchemy import Float, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from core.database import Base


class EnvironmentRow(Base):
    __tablename__ = "environments"

    id:             Mapped[str]   = mapped_column(String, primary_key=True)
    name:           Mapped[str]   = mapped_column(Text, default="")
    grid:           Mapped[dict]  = mapped_column(JSON, nullable=False)  # serialised Grid
    temperature_k:  Mapped[float] = mapped_column(Float, default=75.0)
    pressure_pa:    Mapped[float] = mapped_column(Float, default=0.0)
    active_geysers: Mapped[list]  = mapped_column(JSON, default=list)
    hazard_zones:   Mapped[list]  = mapped_column(JSON, default=list)
