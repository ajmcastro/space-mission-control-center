"""Anomaly injection engine — hooks for noise, terrain effects, random failures."""
import random
from core.models.rover import Rover, RoverState
from core.models.anomaly import Anomaly, AnomalyType, AnomalySeverity
from core.models.command import Command
from core.models.environment import Environment, TerrainType


class AnomalyEngine:
    """
    Probabilistic anomaly injector. All probabilities are config-driven so
    tests can override them. A future V3 extension can replace this with
    physics-based failure modeling.
    """

    def __init__(
        self,
        wheel_stuck_prob: float = 0.02,
        energy_spike_prob: float = 0.03,
        comm_loss_prob: float = 0.01,
        geyser_hazard_prob: float = 0.25,
    ) -> None:
        self._wheel_stuck_prob = wheel_stuck_prob
        self._energy_spike_prob = energy_spike_prob
        self._comm_loss_prob = comm_loss_prob
        self._geyser_hazard_prob = geyser_hazard_prob

    def check(self, rover: Rover, command: Command, env: Environment) -> Anomaly | None:
        """
        Evaluate whether an anomaly occurs while executing `command`.
        Returns an Anomaly if one fires, otherwise None.
        """
        cell = env.grid.get_cell(rover.x, rover.y)

        # Geyser proximity check
        if cell and cell.terrain == TerrainType.GEYSER:
            if random.random() < self._geyser_hazard_prob:
                return self._make(
                    rover, AnomalyType.GEYSER_PROXIMITY, AnomalySeverity.HIGH,
                    "Active geyser eruption nearby — halting for safety",
                )

        # Wheel stuck on rocky/crater terrain
        if cell and cell.terrain in (TerrainType.ROCKY, TerrainType.CRATER):
            if random.random() < self._wheel_stuck_prob:
                return self._make(
                    rover, AnomalyType.WHEEL_STUCK, AnomalySeverity.MEDIUM,
                    "Wheel traction loss on rocky surface",
                )

        # Random energy spike
        if random.random() < self._energy_spike_prob:
            return self._make(
                rover, AnomalyType.ENERGY_SPIKE, AnomalySeverity.LOW,
                "Unexpected battery drain spike detected",
            )

        # Comm loss
        if random.random() < self._comm_loss_prob:
            return self._make(
                rover, AnomalyType.COMM_LOSS, AnomalySeverity.HIGH,
                "Communication link interrupted",
            )

        # Low battery warning (not a hard failure — just an alert)
        if rover.battery_pct < 15.0:
            return self._make(
                rover, AnomalyType.LOW_BATTERY, AnomalySeverity.CRITICAL,
                f"Battery critically low: {rover.battery_pct:.1f}%",
            )

        return None

    def apply(self, rover: Rover, anomaly: Anomaly) -> None:
        """Mutate rover state in response to anomaly."""
        if anomaly.type == AnomalyType.WHEEL_STUCK:
            rover.state = RoverState.STUCK
        elif anomaly.type == AnomalyType.COMM_LOSS:
            rover.state = RoverState.COMM_LOST
        elif anomaly.type == AnomalyType.ENERGY_SPIKE:
            rover.battery = max(0.0, rover.battery - rover.spec.max_battery * 0.1)
        elif anomaly.type == AnomalyType.GEYSER_PROXIMITY:
            rover.state = RoverState.STUCK
        # LOW_BATTERY and others are alerts, not state changes

    def _make(
        self,
        rover: Rover,
        anomaly_type: AnomalyType,
        severity: AnomalySeverity,
        description: str,
    ) -> Anomaly:
        return Anomaly(
            type=anomaly_type,
            severity=severity,
            mission_id=rover.mission_id or "",
            rover_id=rover.id,
            x=rover.x,
            y=rover.y,
            description=description,
        )
