"""Fault Protection System — tiered autonomous fault response (V4)."""
import structlog
from dataclasses import dataclass, field
from enum import Enum

from core.models.rover import Rover, RoverState
from core.models.anomaly import Anomaly, AnomalyType, AnomalyResolution
from core.models.command import Command, CommandType
from core.models.environment import Grid
from core.config import settings

log = structlog.get_logger(__name__)


class FPSAction(str, Enum):
    CONTINUE  = "continue"   # no structural change — loop proceeds normally
    RETRY     = "retry"      # retry the same step; idx unchanged
    REVERSE   = "reverse"    # move back to the previous cell, then retry
    REPLAN    = "replan"     # compute a new path from current position via A*
    SAFE_MODE = "safe_mode"  # halt and wait for ground control intervention


@dataclass
class FPSResult:
    action: FPSAction
    reason: str = ""
    resolution: AnomalyResolution = AnomalyResolution.PENDING
    # Filled only for REPLAN — list of replacement MOVE commands.
    new_commands: list[Command] = field(default_factory=list)


class FaultProtectionEngine:
    """
    Evaluate each anomaly against the rover's fault history and decide the
    least-disruptive recovery action that keeps the mission alive.

    Decision table
    ──────────────
    WHEEL_STUCK      streak ≤ retry_limit          → RETRY
                     streak == retry_limit + 1      → REVERSE (back one cell)
                     streak > retry_limit + 1       → SAFE_MODE
    COMM_LOSS        streak ≤ comm_limit            → RETRY (with brief wait)
                     streak > comm_limit            → SAFE_MODE
    LOW_BATTERY      always                         → SAFE_MODE
    GEYSER_PROXIMITY always                         → REPLAN (or SAFE_MODE if no path)
    PATH_BLOCKED     always                         → REPLAN (or SAFE_MODE if no path)
    ENERGY_SPIKE     always                         → CONTINUE (drain already applied)
    SENSOR_FAULT     always                         → CONTINUE
    UNKNOWN          streak == 1                    → RETRY
                     streak > 1                     → SAFE_MODE
    """

    def handle(
        self,
        rover: Rover,
        anomaly: Anomaly,
        remaining_objectives: list,
        grid: Grid,
    ) -> FPSResult:
        rover.anomaly_streak += 1
        result = self._decide(rover, anomaly, remaining_objectives, grid)
        log.info(
            "fps_rule_triggered",
            rover=rover.name,
            anomaly_type=anomaly.type.value,
            streak=rover.anomaly_streak,
            action=result.action.value,
            reason=result.reason,
        )
        return result

    def reset_streak(self, rover: Rover) -> None:
        """Call after each successful step to clear the consecutive-fault counter."""
        if rover.anomaly_streak > 0:
            rover.anomaly_streak = 0

    # ─── Private helpers ──────────────────────────────────────────────────────

    def _decide(
        self,
        rover: Rover,
        anomaly: Anomaly,
        remaining_objectives: list,
        grid: Grid,
    ) -> FPSResult:
        t      = anomaly.type
        streak = rover.anomaly_streak

        if t == AnomalyType.WHEEL_STUCK:
            limit = settings.fps_wheel_stuck_retry_limit
            if streak <= limit:
                return FPSResult(
                    FPSAction.RETRY,
                    reason=f"Wheel stuck — retry {streak}/{limit}",
                )
            if streak == limit + 1:
                return FPSResult(
                    FPSAction.REVERSE,
                    reason="Persistent wheel-stuck — reversing to prior cell",
                    resolution=AnomalyResolution.AUTO_RECOVERED,
                )
            return FPSResult(
                FPSAction.SAFE_MODE,
                reason=f"Wheel stuck after {streak} attempts — entering safe mode",
            )

        if t == AnomalyType.COMM_LOSS:
            limit = settings.fps_comm_loss_retry_limit
            if streak <= limit:
                return FPSResult(
                    FPSAction.RETRY,
                    reason=f"Comm loss — waiting for signal recovery ({streak}/{limit})",
                )
            return FPSResult(
                FPSAction.SAFE_MODE,
                reason=f"Comm link unrecovered after {streak} attempts — safe mode",
            )

        if t == AnomalyType.LOW_BATTERY:
            return FPSResult(
                FPSAction.SAFE_MODE,
                reason=f"Critical battery ({rover.battery_pct:.1f}%) — entering safe mode",
            )

        if t == AnomalyType.GEYSER_PROXIMITY:
            cmds = self._replan_commands(rover, remaining_objectives, grid)
            if cmds is not None:
                return FPSResult(
                    FPSAction.REPLAN,
                    reason="Geyser hazard — replanning route around it",
                    resolution=AnomalyResolution.REPLANNED,
                    new_commands=cmds,
                )
            return FPSResult(
                FPSAction.SAFE_MODE,
                reason="Geyser hazard and no safe route found — safe mode",
            )

        if t == AnomalyType.PATH_BLOCKED:
            cmds = self._replan_commands(rover, remaining_objectives, grid)
            if cmds is not None:
                return FPSResult(
                    FPSAction.REPLAN,
                    reason="Path blocked — computing alternative route",
                    resolution=AnomalyResolution.REPLANNED,
                    new_commands=cmds,
                )
            return FPSResult(
                FPSAction.SAFE_MODE,
                reason="Path blocked and no alternative route — safe mode",
            )

        if t in (AnomalyType.ENERGY_SPIKE, AnomalyType.SENSOR_FAULT):
            return FPSResult(
                FPSAction.CONTINUE,
                reason=f"{t.value} logged — continuing execution",
                resolution=AnomalyResolution.AUTO_RECOVERED,
            )

        # UNKNOWN and any future types
        if streak <= 1:
            return FPSResult(FPSAction.RETRY, reason="Unknown anomaly — retrying once")
        return FPSResult(
            FPSAction.SAFE_MODE,
            reason=f"Repeated unknown anomaly ({streak} times) — safe mode",
        )

    def _replan_commands(
        self,
        rover: Rover,
        remaining_objectives: list,
        grid: Grid,
    ) -> list[Command] | None:
        """
        Run A* from the rover's current position through all incomplete objectives
        in priority order.  Returns a flat list of MOVE commands, or None if any
        objective is unreachable.
        """
        # Lazy import to avoid circular dependency.
        from services.planning_service.astar import astar

        commands: list[Command] = []
        cx, cy = rover.x, rover.y

        for obj in sorted(remaining_objectives, key=lambda o: o.priority):
            if obj.completed:
                continue
            path, _ = astar(grid, (cx, cy), (obj.target_x, obj.target_y))
            if path is None:
                log.warning(
                    "fps_replan_no_path",
                    rover=rover.name,
                    from_pos=(cx, cy),
                    to_obj=(obj.target_x, obj.target_y),
                )
                return None

            for wx, wy in path[1:]:
                commands.append(Command(
                    mission_id=rover.mission_id or "",
                    rover_id=rover.id,
                    type=CommandType.MOVE,
                    sequence=len(commands),
                    target_x=wx,
                    target_y=wy,
                ))
            cx, cy = obj.target_x, obj.target_y

        return commands if commands else None
