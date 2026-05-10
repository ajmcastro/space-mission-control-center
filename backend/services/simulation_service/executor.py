"""Command executor — applies a single Command to a Rover, emitting telemetry."""
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.rover import Rover, RoverState
from core.models.command import Command, CommandType, CommandStatus
from core.models.telemetry import TelemetryEvent, TelemetryType
from core.models.anomaly import Anomaly, AnomalyResolution
from core.models.environment import Environment, TerrainType
from core.events import EventBus, MissionEvent, EventType
from core.config import settings
from core.repositories import TelemetryRepository, RoverRepository
from .anomaly_engine import AnomalyEngine


class CommandExecutor:
    def __init__(self, event_bus: EventBus) -> None:
        self._bus = event_bus
        self._anomaly_engine = AnomalyEngine()
        self._telemetry = TelemetryRepository()
        self._rovers = RoverRepository()

    async def execute(
        self,
        command: Command,
        rover: Rover,
        env: Environment,
        session: AsyncSession,
    ) -> tuple[Command, Anomaly | None]:
        command.mark_sent()
        await asyncio.sleep(min(settings.comm_delay_seconds, 0.1))
        command.mark_executing()

        anomaly = self._anomaly_engine.check(rover, command, env)
        if anomaly:
            self._anomaly_engine.apply(rover, anomaly)
            if rover.state in (RoverState.STUCK, RoverState.COMM_LOST, RoverState.ERROR):
                command.mark_failed(anomaly.description)
                await self._emit_anomaly(anomaly, rover)
                return command, anomaly

        try:
            if command.type == CommandType.MOVE:
                await self._execute_move(command, rover, env, session)
            elif command.type == CommandType.COLLECT_SAMPLE:
                await self._execute_sample(command, rover, env, session)
            elif command.type == CommandType.WAIT:
                await asyncio.sleep(settings.sim_step_delay_seconds)
            elif command.type == CommandType.CHARGE:
                rover.battery = min(rover.spec.max_battery, rover.battery + 50.0)
                rover.state = RoverState.IDLE
            elif command.type == CommandType.ABORT:
                rover.state = RoverState.IDLE
                command.mark_failed("Aborted by operator")
                return command, None

            command.mark_completed()

        except Exception as exc:
            command.mark_failed(str(exc))

        _CMD_TELEM_TYPE: dict[CommandType, TelemetryType] = {
            CommandType.MOVE:           TelemetryType.POSITION,
            CommandType.COLLECT_SAMPLE: TelemetryType.SAMPLE_COLLECTED,
            CommandType.CHARGE:         TelemetryType.STATE_CHANGE,
            CommandType.WAIT:           TelemetryType.HEARTBEAT,
            CommandType.TRANSMIT:       TelemetryType.COMMAND_ACK,
            CommandType.ABORT:          TelemetryType.STATE_CHANGE,
        }
        telem = TelemetryEvent(
            type=_CMD_TELEM_TYPE.get(command.type, TelemetryType.POSITION),
            mission_id=command.mission_id,
            rover_id=rover.id,
            x=rover.x,
            y=rover.y,
            battery=rover.battery,
            battery_pct=rover.battery_pct,
            payload={"command_id": command.id, "command_type": command.type.value},
        )
        await self._telemetry.append(session, telem)
        await self._bus.publish(MissionEvent(
            type=EventType.TELEMETRY_EMITTED,
            stream=settings.telemetry_stream,
            mission_id=command.mission_id,
            rover_id=rover.id,
            payload=telem.model_dump(mode="json"),
        ))

        return command, anomaly

    async def _execute_move(
        self, command: Command, rover: Rover, env: Environment, session: AsyncSession
    ) -> None:
        tx, ty = command.target_x, command.target_y
        cell = env.grid.get_cell(tx, ty)
        if not cell or not cell.passable:
            raise ValueError(f"Target ({tx},{ty}) is impassable")
        cost = rover.spec.move_cost_per_cell * cell.movement_cost
        # Surface frost (V4) — night increases battery drain on flat/ice terrain.
        if env.is_night and cell.terrain in (TerrainType.FLAT, TerrainType.ICE):
            cost *= settings.terrain_frost_cost_factor
        if rover.battery < cost:
            raise ValueError("Insufficient battery for move")
        rover.state = RoverState.MOVING
        # Commit MOVING state so HTTP polls (every 2 s) see the rover in motion.
        await self._rovers.save(session, rover)
        await session.commit()
        await asyncio.sleep(settings.sim_step_delay_seconds)
        rover.move_to(tx, ty, cost)
        await self._bus.publish(MissionEvent(
            type=EventType.ROVER_MOVED,
            stream=settings.telemetry_stream,
            mission_id=command.mission_id,
            rover_id=rover.id,
            payload={"x": tx, "y": ty, "battery": rover.battery},
        ))

    async def _execute_sample(
        self, command: Command, rover: Rover, env: Environment, session: AsyncSession
    ) -> None:
        if rover.battery < rover.spec.sample_cost:
            raise ValueError("Insufficient battery for sample collection")
        rover.state = RoverState.SAMPLING
        # Commit SAMPLING state so HTTP polls see it during the collection delay.
        await self._rovers.save(session, rover)
        await session.commit()
        await asyncio.sleep(settings.sim_step_delay_seconds * 2)
        rover.collect_sample()
        cell = env.grid.get_cell(rover.x, rover.y)
        if cell:
            cell.has_sample = False
        await self._bus.publish(MissionEvent(
            type=EventType.SAMPLE_COLLECTED,
            stream=settings.telemetry_stream,
            mission_id=command.mission_id,
            rover_id=rover.id,
            payload={"x": rover.x, "y": rover.y, "total": rover.samples_collected},
        ))

    async def _emit_anomaly(self, anomaly: Anomaly, rover: Rover) -> None:
        await self._bus.publish(MissionEvent(
            type=EventType.ANOMALY_DETECTED,
            stream=settings.anomaly_stream,
            mission_id=anomaly.mission_id,
            rover_id=rover.id,
            payload={
                "anomaly_id": anomaly.id,
                "type": anomaly.type.value,
                "severity": anomaly.severity.value,
                "description": anomaly.description,
                "x": anomaly.x,
                "y": anomaly.y,
            },
        ))
