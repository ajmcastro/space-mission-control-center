from pydantic import BaseModel

from core.models.comm import UplinkCommand


class CommStatusResponse(BaseModel):
    open: bool
    seconds_until_next_open: float
    seconds_until_close: float
    slot_seconds: float
    window_duration_seconds: float


class UplinkResult(BaseModel):
    """Response for a gated ground-control action: either it ran immediately
    (`delivered=True`, `result` populated) or it was queued for the next
    window (`delivered=False`, `uplink` populated)."""
    delivered: bool
    uplink: UplinkCommand | None = None
    result: dict | None = None
