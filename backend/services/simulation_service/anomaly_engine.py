"""Anomaly injection engine — physics-informed failure model (V3)."""
import random
from core.models.rover import Rover, RoverState
from core.models.anomaly import Anomaly, AnomalyType, AnomalySeverity
from core.models.command import Command
from core.models.environment import Environment, TerrainType
from core.config import settings


class AnomalyEngine:
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
        cell = env.grid.get_cell(rover.x, rover.y)

        # Geyser proximity check
        if cell and cell.terrain == TerrainType.GEYSER:
            if random.random() < self._geyser_hazard_prob:
                return self._make(
                    rover, AnomalyType.GEYSER_PROXIMITY, AnomalySeverity.HIGH,
                    "Active geyser eruption nearby — halting for safety",
                )

        # Wheel stuck — elevated on steep terrain (physics: higher |elevation| = more slope stress)
        slope_stress = abs(cell.elevation) if cell else 0.0
        adjusted_wheel_stuck = self._wheel_stuck_prob * (
            1.0 + slope_stress * 2.0 * settings.physics_elevation_cost_factor
        )
        if cell and cell.terrain in (TerrainType.ROCKY, TerrainType.CRATER):
            if random.random() < adjusted_wheel_stuck:
                return self._make(
                    rover, AnomalyType.WHEEL_STUCK, AnomalySeverity.MEDIUM,
                    f"Wheel traction loss on {cell.terrain.value} surface "
                    f"(slope stress {slope_stress:.2f})",
                )

        # Thermal stress: extreme cold contracts battery cells and causes power spikes.
        # Enceladus surface is ~75 K; any deviation downward is hazardous.
        thermal_scale = settings.physics_thermal_anomaly_scale
        thermal_spike_prob = self._energy_spike_prob
        if env.temperature_k < 60.0:
            thermal_spike_prob *= 2.0 * thermal_scale
        if random.random() < thermal_spike_prob:
            return self._make(
                rover, AnomalyType.ENERGY_SPIKE, AnomalySeverity.LOW,
                f"Unexpected battery drain spike "
                f"(T={env.temperature_k:.0f} K, elev={slope_stress:.2f})",
            )

        # Comm loss
        if random.random() < self._comm_loss_prob:
            return self._make(
                rover, AnomalyType.COMM_LOSS, AnomalySeverity.HIGH,
                "Communication link interrupted",
            )

        # Low battery warning
        if rover.battery_pct < 15.0:
            return self._make(
                rover, AnomalyType.LOW_BATTERY, AnomalySeverity.CRITICAL,
                f"Battery critically low: {rover.battery_pct:.1f}%",
            )

        return None

    def apply(self, rover: Rover, anomaly: Anomaly) -> None:
        if anomaly.type == AnomalyType.WHEEL_STUCK:
            rover.state = RoverState.STUCK
        elif anomaly.type == AnomalyType.COMM_LOSS:
            rover.state = RoverState.COMM_LOST
        elif anomaly.type == AnomalyType.ENERGY_SPIKE:
            rover.battery = max(0.0, rover.battery - rover.spec.max_battery * 0.1)
        elif anomaly.type == AnomalyType.GEYSER_PROXIMITY:
            rover.state = RoverState.STUCK

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
