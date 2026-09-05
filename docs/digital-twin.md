# Digital Twin and Environment Simulation

[← Back to README](../README.md)

## Rover Digital Twin

Each simulated rover has an operational state that evolves as commands execute.

Important state includes:

- position;
- battery;
- rover state;
- path history;
- mission association;
- current plan;
- autonomy level;
- anomaly/recovery state.

The digital twin provides the state on which planning, telemetry, fault protection, visualization, and explainability operate.

## Command Execution

Plans are executed asynchronously, step by step.

Commands include movement and mission actions such as:

```text
MOVE
COLLECT_SAMPLE
WAIT
CHARGE
ABORT
```

Execution updates rover state, consumes resources, produces telemetry, and may trigger environment or anomaly behavior.

The simulation step delay is configurable:

```bash
SIM_STEP_DELAY_SECONDS=0.5
```

## Physics-Aware Terrain

The environment is a grid containing per-cell information such as:

- terrain type;
- elevation;
- movement cost;
- reveal state;
- hazard/science information.

Elevation is generated procedurally and movement cost is influenced by terrain and slope.

Representative physics tuning:

```bash
PHYSICS_ELEVATION_COST_FACTOR=0.5
PHYSICS_THERMAL_ANOMALY_SCALE=1.0
```

Slope stress can affect wheel-stuck probability, while ambient temperature can influence anomaly probabilities.

## Battery Model

Movement consumes battery according to base rover movement cost and terrain-related multipliers.

Representative configuration:

```bash
ROVER_BATTERY_CAPACITY=1000.0
ROVER_MOVE_COST=10.0
```

Battery state is exposed through telemetry and charts and is also used by safety/autonomy behavior.

## Fog of War

The environment can start partially unknown.

```bash
FOG_OF_WAR=true
SENSOR_RANGE=2
```

`SENSOR_RANGE` is the Chebyshev radius revealed around the rover.

Fogged cells hide terrain details, elevation, and samples, while objectives can remain visible as uncharted targets.

Both the 2D and 3D views progressively reveal terrain as rovers explore.

## Dynamic Terrain Events

The simulation contains background terrain behavior.

### Geyser cycles

Geysers can transition between active and dormant states.

```bash
TERRAIN_GEYSER_CYCLE_TICKS=15
TERRAIN_GEYSER_FLIP_PROB=0.35
```

Geyser state affects hazards and science value.

### Ice fractures

Crevasses can spread into neighboring flat/ice cells.

```bash
TERRAIN_FRACTURE_PROB_PER_TICK=0.004
```

If a fracture blocks a planned route, the rover may need to replan.

### Frost / day-night cycle

A simulated day/night cycle changes movement cost.

```bash
TERRAIN_FROST_PERIOD_TICKS=20
TERRAIN_FROST_COST_FACTOR=1.4
```

During night frost, flat/ice movement can become more expensive.

## Science Value

Cells can carry a science score based on geological/contextual signals.

Implemented factors include:

- geyser proximity;
- ice/water-interface relevance;
- crater proximity.

The score is clamped to `[0, 10]` and can be recomputed as the environment changes.

The frontend can display a science heatmap and the planner can use science return when coordinating rover objectives.

## Anomaly Injection

The `AnomalyEngine` injects probabilistic failures during execution.

Some probabilities are physics-informed. For example:

- slope/elevation can affect wheel-stuck likelihood;
- extreme temperature can influence energy anomalies;
- active geyser proximity can create hazards.

Fault recovery is handled separately by the Fault Protection System.

See [Autonomy](autonomy.md).

## Telemetry

Execution emits typed telemetry such as:

```text
POSITION
SAMPLE_COLLECTED
STATE_CHANGE
HEARTBEAT
COMMAND_ACK
```

The event persistence listener also records important non-command events, including:

- anomalies;
- FPS decisions;
- terrain changes;
- mission lifecycle events.

The frontend provides:

- live telemetry;
- rover/type filters;
- paginated event history;
- battery charts;
- anomaly history;
- timeline playback.

## Timeline Playback

Past telemetry can be replayed step by step with:

- play/pause;
- scrubber;
- speed control;
- communication-window bands.

This allows post-mission analysis to use the same event history that supported live mission operations.
