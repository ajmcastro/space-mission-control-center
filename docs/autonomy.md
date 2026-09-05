# Autonomy

[← Back to README](../README.md)

## Overview

Autonomy in Enceladus Mission Control Center is built around a simple principle: the rover should continue making bounded local decisions even when ground control cannot immediately intervene.

The main autonomy mechanisms are:

- Fault Protection System (FPS);
- AEGIS-style autonomous science targeting;
- dynamic replanning;
- configurable autonomy levels;
- communication-window-independent onboard execution.

## Fault Protection System

The `FaultProtectionEngine` evaluates anomalies during execution and applies anomaly-specific recovery rules.

The general escalation pattern is:

```text
Detect anomaly
      │
      ▼
Apply rule
      │
      ├── Retry
      ├── Reverse
      ├── Replan
      └── Safe mode
```

Recovery state is tracked per rover so repeated failures can escalate rather than retrying forever.

### Anomaly Behavior

| Anomaly | Trigger / source | Immediate effect | FPS response |
|---|---|---|---|
| `wheel_stuck` | Rocky/crater terrain; probability influenced by elevation/slope stress | Rover becomes `STUCK` | Retry, then reverse, then safe mode |
| `comm_loss` | Probabilistic | Rover becomes `COMM_LOST` | Wait/retry, then safe mode |
| `energy_spike` | Probabilistic; more likely under very low temperature | Battery drain | Continue after drain |
| `geyser_proximity` | Active geyser cell | Rover becomes `STUCK` | Replan around hazard or enter safe mode |
| `low_battery` | Battery below threshold | Critical alert | Safe mode |
| `path_blocked` | Terrain event blocks planned path | Route invalidated | Replan or safe mode |
| `sensor_fault` | Reserved for future instrument-health work | — | Rule exists for future use |
| `unknown` | Generic fallback | — | Retry, then safe mode |

Anomalies have severity levels:

```text
low
medium
high
critical
```

## Safe Mode

Safe mode is the final protective response for conditions where continuing normal execution would be unsafe.

Examples include:

- critically low battery;
- repeated unrecoverable anomalies;
- no feasible path around a hazard.

The rover can remain protected until a suitable recovery or ground-control action occurs.

## Configurable FPS Parameters

Representative environment variables include:

```bash
FPS_WHEEL_STUCK_RETRY_LIMIT=2
FPS_COMM_LOSS_RETRY_LIMIT=2
FPS_SAFE_MODE_BATTERY_PCT=10.0
```

These allow experiments with different fault-tolerance policies without changing code.

## AEGIS-Style Target Selection

The project models autonomous science targeting inspired by AEGIS-style rover autonomy.

When the assigned objective list is exhausted, the rover can score reachable cells using signals such as:

- science value;
- unexplored-terrain bonus;
- sample presence;
- elevation gradient;
- distance.

The best candidate can become a new rover-generated objective.

## Autonomy Levels

Each rover supports three conceptual autonomy levels.

### `supervised`

The rover proposes a science target and pauses for ground-control approval or rejection.

This provides human-in-the-loop autonomy.

### `semi_autonomous`

The rover may self-direct within already revealed terrain.

This allows local autonomy while limiting action to known areas.

### `fully_autonomous`

The rover may select reachable targets including unexplored/fogged terrain.

This models the strongest onboard autonomy mode.

## AEGIS Events and Control

The system publishes autonomy events such as:

```text
AEGIS_TARGET_SELECTED
AEGIS_TARGET_PROPOSED
```

The API supports:

```text
PATCH /api/v1/simulation/rovers/{rover_id}/autonomy
GET   /api/v1/simulation/rovers/{rover_id}/aegis-proposal
POST  /api/v1/simulation/rovers/{rover_id}/aegis-proposal/approve
POST  /api/v1/simulation/rovers/{rover_id}/aegis-proposal/reject
```

Ground-control autonomy changes and proposal decisions are subject to communication-window gating. Onboard execution itself is not.

## Autonomous Objective Limit

The number of self-generated objectives can be capped:

```bash
AEGIS_MAX_AUTO_OBJECTIVES=10
```

A value of `0` represents an unlimited configuration.

## Dynamic Terrain and Autonomous Replanning

The environment can change while a plan is running.

Examples:

- geyser activation/dormancy;
- ice-fracture propagation;
- night frost increasing movement cost.

When a terrain change invalidates the current route, the rover can autonomously replan.

This creates a closed-loop autonomy pattern:

```text
Sense / receive event
        │
        ▼
Evaluate current plan
        │
        ▼
Plan still valid?
   │          │
  yes         no
   │          │
Continue    Replan
```

## Ground Control vs Onboard Autonomy

Communication windows constrain **ground intervention**, not onboard rover execution.

That distinction is important:

- a rover keeps executing its onboard plan while Earth is out of contact;
- FPS continues protecting the rover;
- autonomous target selection can continue according to the configured autonomy level;
- ground actions are queued until an uplink window becomes available.

See [Communications](communications.md) for the communication model.
