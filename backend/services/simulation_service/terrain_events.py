"""Dynamic terrain event engine — geyser cycles, ice fracture, surface frost (V4)."""
import random
import structlog
from dataclasses import dataclass, field

from core.models.environment import Environment, Cell, TerrainType
from core.events import EventType
from core.config import settings

log = structlog.get_logger(__name__)


@dataclass
class TerrainChange:
    """A single terrain change produced by one tick."""
    event_type: EventType
    x: int
    y: int
    description: str
    payload: dict = field(default_factory=dict)


class TerrainEventEngine:
    """
    Advances the environment's geological state by one simulation tick.

    Three phenomena are modelled:

    Geyser eruption cycles
        Every `terrain_geyser_cycle_ticks` steps each geyser cell independently
        rolls against `terrain_geyser_flip_prob`.  A dormant geyser that erupts
        becomes hazardous again; an erupting geyser that goes dormant becomes a
        safe, rewarding traversal target.

    Ice fracture propagation
        Each step every CREVASSE cell has a small independent chance
        (`terrain_fracture_prob_per_tick`) to spread to one randomly chosen
        adjacent FLAT or ICE cell, closing off routes and adding geological drama.

    Surface frost
        Enceladus rotates every ~32.9 hours.  The simulation approximates this
        with a configurable tick period.  During the "night" half of the cycle
        flat and ice terrain costs are multiplied by `terrain_frost_cost_factor`,
        draining battery faster and slowing traversal.
    """

    def tick(
        self,
        env: Environment,
        mission_id: str,
        rover_id: str,
    ) -> list[TerrainChange]:
        """Advance one simulation step.  Returns a (possibly empty) list of terrain changes."""
        env.sim_tick += 1
        changes: list[TerrainChange] = []

        changes.extend(self._update_frost(env))
        changes.extend(self._update_geysers(env))
        changes.extend(self._propagate_fractures(env))

        if changes:
            log.info(
                "terrain_events_tick",
                tick=env.sim_tick,
                mission_id=mission_id,
                count=len(changes),
                types=[c.event_type.value for c in changes],
            )

        return changes

    # ─── Private ─────────────────────────────────────────────────────────────

    def _update_frost(self, env: Environment) -> list[TerrainChange]:
        """Toggle day/night frost at half the configured period."""
        changes: list[TerrainChange] = []
        half = settings.terrain_frost_period_ticks // 2
        if half < 1:
            return changes

        should_be_night = (env.sim_tick // half) % 2 == 1
        if should_be_night == env.is_night:
            return changes

        env.is_night = should_be_night
        etype = EventType.FROST_CYCLE_START if should_be_night else EventType.FROST_CYCLE_END
        description = (
            "Surface frost onset — ice and flat terrain movement costs increased"
            if should_be_night
            else "Surface frost cleared — normal traversal costs restored"
        )
        changes.append(TerrainChange(
            event_type=etype,
            x=-1, y=-1,
            description=description,
            payload={
                "is_night": should_be_night,
                "frost_cost_factor": settings.terrain_frost_cost_factor,
                "tick": env.sim_tick,
            },
        ))
        log.info("terrain_frost_cycle", is_night=should_be_night, tick=env.sim_tick)
        return changes

    def _update_geysers(self, env: Environment) -> list[TerrainChange]:
        """Probabilistically flip each geyser cell on the configured cycle."""
        if env.sim_tick % settings.terrain_geyser_cycle_ticks != 0:
            return []

        changes: list[TerrainChange] = []
        for row in env.grid.cells:
            for cell in row:
                if cell.terrain != TerrainType.GEYSER:
                    continue
                if random.random() >= settings.terrain_geyser_flip_prob:
                    continue

                cell.geyser_active = not cell.geyser_active
                if cell.geyser_active:
                    etype = EventType.GEYSER_ERUPTION
                    description = (
                        f"Geyser at ({cell.x},{cell.y}) resumed eruption — "
                        "hazardous, increased movement cost"
                    )
                else:
                    etype = EventType.GEYSER_DORMANCY
                    description = (
                        f"Geyser at ({cell.x},{cell.y}) entered dormancy — "
                        "safe to approach, high science value"
                    )

                changes.append(TerrainChange(
                    event_type=etype,
                    x=cell.x, y=cell.y,
                    description=description,
                    payload={
                        "geyser_active": cell.geyser_active,
                        "tick": env.sim_tick,
                    },
                ))

        return changes

    def _propagate_fractures(self, env: Environment) -> list[TerrainChange]:
        """Attempt to spread each CREVASSE cell to one adjacent FLAT or ICE cell."""
        changes: list[TerrainChange] = []
        grid = env.grid

        # Collect fracture sources first to avoid propagating newly created crevasses
        # in the same tick (would cause runaway spread).
        fracture_sources = [
            (cell.x, cell.y)
            for row in grid.cells
            for cell in row
            if cell.terrain == TerrainType.CREVASSE
        ]

        for cx, cy in fracture_sources:
            if random.random() >= settings.terrain_fracture_prob_per_tick:
                continue

            candidates = [
                (cx + dx, cy + dy)
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                if 0 <= cx + dx < grid.width and 0 <= cy + dy < grid.height
            ]
            spreadable = [
                (nx, ny) for nx, ny in candidates
                if grid.cells[ny][nx].terrain in (TerrainType.FLAT, TerrainType.ICE)
            ]
            if not spreadable:
                continue

            nx, ny = random.choice(spreadable)
            target = grid.cells[ny][nx]
            old_terrain = target.terrain
            target.terrain = TerrainType.CREVASSE
            target.geyser_active = True   # reset to default for non-geyser

            changes.append(TerrainChange(
                event_type=EventType.ICE_FRACTURE,
                x=nx, y=ny,
                description=(
                    f"Ice fracture at ({nx},{ny}) — {old_terrain.value} cell "
                    f"collapsed into crevasse (propagated from ({cx},{cy}))"
                ),
                payload={
                    "from_x": cx, "from_y": cy,
                    "to_x": nx, "to_y": ny,
                    "old_terrain": old_terrain.value,
                    "tick": env.sim_tick,
                },
            ))
            log.info(
                "terrain_ice_fracture",
                from_pos=(cx, cy), to_pos=(nx, ny),
                old_terrain=old_terrain.value,
                tick=env.sim_tick,
            )

        return changes
