# Mission Planning

[← Back to README](../README.md)

## Overview

The planning subsystem supports several complementary approaches:

1. A* terrain-aware path planning.
2. A greedy reinforcement-learning-style value-function planner.
3. Multi-agent objective distribution.
4. Science-value-aware coordination.

The goal is to make different planning strategies observable and comparable inside the same mission-control simulation.

## Planner Interface

Planning implementations share a common planner interface. This keeps planner selection separate from mission and simulation logic and makes it possible to add new planners without rewriting the execution system.

A plan consists of ordered `PlanStep` objects containing commands, expected battery cost, and rationale.

Typical commands include:

- `MOVE`
- `COLLECT_SAMPLE`
- `WAIT`
- `CHARGE`
- `ABORT`

## A* Planner

A* provides the deterministic baseline.

It searches the terrain grid while accounting for movement costs rather than treating every cell as equivalent. Environment state therefore affects the selected path.

A* is useful for:

- deterministic route generation;
- validating environment constraints;
- comparison with learned policies;
- replanning after hazards or terrain changes.

## RL Value-Function Planner

The RL planner uses a greedy value function rather than a trained neural network.

Conceptually:

```text
V(cell) =
    target attraction
  - terrain cost
  - geyser penalty
  - elevation penalty
```

The current value function is:

```text
V(cell) = (w_target / (1 + dist_to_nearest_obj))
        - w_terrain × cell.movement_cost
        - w_geyser  × geyser_penalty
        - |elevation| × 0.5
```

Weights are configurable:

```bash
RL_WEIGHT_TARGET=2.0
RL_WEIGHT_TERRAIN=1.0
RL_WEIGHT_GEYSER=3.0
RL_EPISODE_BUDGET=500
```

Interpretation:

- increase `RL_WEIGHT_TARGET` to make the policy more aggressive toward objectives;
- increase `RL_WEIGHT_TERRAIN` to favor easier terrain;
- increase `RL_WEIGHT_GEYSER` to strengthen geyser avoidance;
- `RL_EPISODE_BUDGET` limits exploration before fallback behavior.

The implementation is intentionally structured so that `_value()` can later be replaced by a trained policy while keeping the surrounding planning/execution interfaces.

## Multi-Agent Coordination

For missions with multiple rovers, the coordinator distributes objectives before generating rover-specific plans.

The baseline strategy uses greedy distance assignment:

```text
Mission objectives
       │
       ▼
Objective coordinator
   ┌───┼───┐
   ▼   ▼   ▼
  R1  R2   R3
   │   │    │
   ▼   ▼    ▼
 Plan Plan  Plan
```

Each rover can then execute its plan independently and concurrently.

This models a practical multi-agent pattern: centralized task allocation followed by decentralized execution.

## Science-Value Optimization

The coordinator also supports a science-oriented mode.

Each terrain cell can carry a science-value score derived from factors including:

- geyser proximity;
- ice/water-interface relevance;
- crater proximity;
- exploration state.

Scores are clamped to `[0, 10]` and can change as geyser state changes.

Instead of assigning objectives only by shortest travel distance, science optimization can use a return-on-investment concept:

```text
science ROI = science value / estimated battery cost
```

This changes the planning question from:

> Which rover can reach the objective most cheaply?

to:

> Which allocation is likely to maximize scientific return for the available energy?

The heatmap is available through:

```text
GET /api/v1/planning/environments/{id}/science-heatmap
```

## Dynamic Replanning

Planning is not assumed to be final once execution starts.

Replanning may be triggered when:

- a geyser eruption blocks a planned route;
- an ice fracture changes terrain;
- Fault Protection decides that the current path is unsafe;
- an anomaly requires recovery;
- AEGIS selects a new science target.

The rover therefore participates in a loop:

```text
Plan → Execute → Observe → Detect change → Replan → Continue
```

## AEGIS and Planning

AEGIS-style autonomy extends planning beyond human-assigned objectives.

When assigned objectives are exhausted, autonomous rovers can evaluate candidate cells and select scientifically valuable targets based on factors such as:

- science value;
- unexplored bonus;
- sample presence;
- elevation gradient;
- travel distance.

See [Autonomy](autonomy.md) for autonomy levels and approval behavior.

## Adding a Planner

Create a planner implementation under:

```text
backend/services/planning_service/
```

Implement the shared planner interface, add the new planner type, and register dispatch in `PlanningService`.

The existing A* and RL planners are the reference implementations.

Conceptually:

```python
class MyPlanner:
    async def plan(self, request, grid, objectives):
        ...
```

After adding a planner, include unit tests and expose the selection through the API/UI if it is intended for interactive use.
