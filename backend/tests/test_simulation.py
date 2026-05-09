"""Unit tests for rover simulation and anomaly engine."""
import pytest
from core.models.rover import Rover, RoverState
from core.models.environment import Grid, Cell, TerrainType, Environment
from core.models.command import Command, CommandType
from services.simulation_service.anomaly_engine import AnomalyEngine
from core.models.anomaly import AnomalyType


def flat_env(width: int = 5, height: int = 5) -> Environment:
    cells = [[Cell(x=x, y=y, terrain=TerrainType.FLAT) for x in range(width)] for y in range(height)]
    grid = Grid(width=width, height=height, cells=cells)
    return Environment(id="test-env", grid=grid)


def make_rover(mission_id: str = "m1") -> Rover:
    return Rover(name="Test", mission_id=mission_id, x=0, y=0)


class TestRoverModel:
    def test_initial_state(self):
        rover = make_rover()
        assert rover.state == RoverState.IDLE
        assert rover.battery_pct == 100.0
        assert rover.is_operational

    def test_move_reduces_battery(self):
        rover = make_rover()
        initial_battery = rover.battery
        rover.move_to(1, 0, cost=10.0)
        assert rover.battery == initial_battery - 10.0
        assert rover.x == 1
        assert rover.y == 0
        assert rover.total_distance == 1

    def test_path_history_tracks_moves(self):
        rover = make_rover()
        rover.move_to(1, 0, cost=10.0)
        rover.move_to(2, 0, cost=10.0)
        assert (0, 0) in rover.path_history
        assert (1, 0) in rover.path_history

    def test_collect_sample_reduces_battery(self):
        rover = make_rover()
        rover.collect_sample()
        assert rover.battery < rover.spec.max_battery
        assert rover.samples_collected == 1

    def test_stuck_state_not_operational(self):
        rover = make_rover()
        rover.state = RoverState.STUCK
        assert not rover.is_operational


class TestAnomalyEngine:
    def test_no_anomaly_on_flat_safe_terrain(self):
        """With all probabilities at 0, no anomaly should fire."""
        engine = AnomalyEngine(
            wheel_stuck_prob=0.0,
            energy_spike_prob=0.0,
            comm_loss_prob=0.0,
            geyser_hazard_prob=0.0,
        )
        rover = make_rover()
        env = flat_env()
        cmd = Command(mission_id="m1", rover_id=rover.id, type=CommandType.MOVE, target_x=1, target_y=0)
        anomaly = engine.check(rover, cmd, env)
        assert anomaly is None

    def test_low_battery_always_triggers(self):
        engine = AnomalyEngine(
            wheel_stuck_prob=0.0,
            energy_spike_prob=0.0,
            comm_loss_prob=0.0,
            geyser_hazard_prob=0.0,
        )
        rover = make_rover()
        rover.battery = 100.0  # battery_pct = 10% → triggers LOW_BATTERY
        env = flat_env()
        cmd = Command(mission_id="m1", rover_id=rover.id, type=CommandType.MOVE, target_x=1, target_y=0)
        anomaly = engine.check(rover, cmd, env)
        assert anomaly is not None
        assert anomaly.type == AnomalyType.LOW_BATTERY

    def test_wheel_stuck_applies_state(self):
        engine = AnomalyEngine(wheel_stuck_prob=1.0, energy_spike_prob=0.0, comm_loss_prob=0.0)
        rover = make_rover()

        # Put rover on rocky terrain
        cells = [[Cell(x=0, y=0, terrain=TerrainType.ROCKY)]]
        grid = Grid(width=1, height=1, cells=cells)
        env = Environment(id="rocky", grid=grid)
        cmd = Command(mission_id="m1", rover_id=rover.id, type=CommandType.MOVE, target_x=0, target_y=0)

        anomaly = engine.check(rover, cmd, env)
        assert anomaly is not None
        assert anomaly.type == AnomalyType.WHEEL_STUCK
        engine.apply(rover, anomaly)
        assert rover.state == RoverState.STUCK
