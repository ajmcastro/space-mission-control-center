# API Workflows

[← Back to README](../README.md)

This document preserves the complete manual API workflows for exercising the mission-control backend. For interactive endpoint discovery, run the backend and open `http://localhost:8000/docs`.

## V1 — Single-Rover Mission

```bash
BASE=http://localhost:8000/api/v1

# 1. Create a mission with objectives
MISSION=$(curl -s -X POST $BASE/missions/ -H "Content-Type: application/json" -d '{
  "name": "Alpha Geyser Survey",
  "description": "Investigate active geyser zone in grid sector Alpha",
  "grid_width": 20,
  "grid_height": 20,
  "objectives": [
    {"type": "reach_waypoint", "target_x": 8, "target_y": 6, "priority": 1},
    {"type": "collect_sample",  "target_x": 12, "target_y": 10, "priority": 2},
    {"type": "return_to_base",  "target_x": 0,  "target_y": 0,  "priority": 3}
  ]
}')
MISSION_ID=$(echo $MISSION | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# 2. Start the mission
curl -s -X POST $BASE/missions/$MISSION_ID/start | python3 -m json.tool

# 3. Spawn a rover
ROVER=$(curl -s -X POST $BASE/simulation/rovers -H "Content-Type: application/json" -d "{
  \"mission_id\": \"$MISSION_ID\",
  \"name\": \"Enc-Rover-Alpha\",
  \"start_x\": 0,
  \"start_y\": 0
}")
ROVER_ID=$(echo $ROVER | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# 4. Generate a plan: planner may be "astar" or "rl"
PLAN=$(curl -s -X POST $BASE/planning/auto -H "Content-Type: application/json" -d "{
  \"mission_id\": \"$MISSION_ID\",
  \"rover_id\": \"$ROVER_ID\",
  \"planner\": \"astar\"
}")
PLAN_ID=$(echo $PLAN | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# 5. Execute asynchronously
curl -s -X POST $BASE/simulation/run -H "Content-Type: application/json" -d "{
  \"mission_id\": \"$MISSION_ID\",
  \"plan_id\": \"$PLAN_ID\"
}"

# 6. Simulation status
curl -s $BASE/simulation/$MISSION_ID/status | python3 -m json.tool

# 7. Recent telemetry
curl -s "$BASE/telemetry/events/$MISSION_ID?limit=20" | python3 -m json.tool

# 8. Structured plan explanation
curl -s $BASE/explain/plan/$PLAN_ID | python3 -m json.tool

# 9. Mission summary
curl -s $BASE/explain/mission/$MISSION_ID | python3 -m json.tool
```

## V3 — Multi-Rover + RL + Claude

Create and start a mission as above, then spawn at least two rovers.

```bash
BASE=http://localhost:8000/api/v1

curl -s -X POST $BASE/simulation/rovers -H "Content-Type: application/json" -d "{
  \"mission_id\": \"$MISSION_ID\",
  \"name\": \"Enc-Rover-Beta\",
  \"start_x\": 0,
  \"start_y\": 0
}"
```

### RL planning for one rover

```bash
curl -s -X POST $BASE/planning/auto -H "Content-Type: application/json" -d "{
  \"mission_id\": \"$MISSION_ID\",
  \"rover_id\": \"$ROVER_ID\",
  \"planner\": \"rl\"
}" | python3 -m json.tool
```

### Multi-agent coordination

```bash
curl -s -X POST $BASE/planning/multi-agent -H "Content-Type: application/json" -d "{
  \"mission_id\": \"$MISSION_ID\",
  \"rover_ids\": [\"$ROVER_ID_1\", \"$ROVER_ID_2\"]
}" | python3 -m json.tool
```

Execute each returned rover plan separately:

```bash
curl -s -X POST $BASE/simulation/run -H "Content-Type: application/json" -d "{
  \"mission_id\": \"$MISSION_ID\",
  \"plan_id\": \"$PLAN_ID\"
}"
```

### Claude explanation

Requires `ANTHROPIC_API_KEY`.

```bash
curl -sN "$BASE/explain/llm/plan/$PLAN_ID" | grep '^data:' | head -5
```

## V4 — Autonomy, Dynamic Environment, and Communications

V4 adds fog of war, Fault Protection, dynamic terrain, science-value maps, AEGIS-style target selection, and communication-window gating.

### Inspect fog-of-war progress

```bash
ENV_ID=$(curl -s $BASE/missions/$MISSION_ID | \
  python3 -c "import sys,json; print(json.load(sys.stdin)['environment_id'])")

curl -s $BASE/missions/$MISSION_ID/environment | python3 -c "
import sys, json
env = json.load(sys.stdin)
cells = [c for row in env['grid']['cells'] for c in row]
revealed = sum(c['revealed'] for c in cells)
print(f\"{revealed}/{len(cells)} cells revealed | sim_tick={env['sim_tick']} | night={env['is_night']}\")
"
```

### Observe anomalies, FPS, and terrain events

Fault Protection and terrain events are background/probabilistic behaviors rather than direct request/response actions.

```bash
watch -n 2 "curl -s $BASE/telemetry/anomalies/$MISSION_ID | python3 -m json.tool"
```

The telemetry UI/event stream may contain events such as:

```text
FPS_RULE_TRIGGERED
GEYSER_ERUPTION
ICE_FRACTURE
FROST_CYCLE_START
```

### Science-value heatmap

```bash
curl -s $BASE/planning/environments/$ENV_ID/science-heatmap | python3 -m json.tool
```

### Change rover autonomy

Ground-control autonomy changes are communication-window gated.

```bash
curl -s -X PATCH $BASE/simulation/rovers/$ROVER_ID/autonomy \
  -H "Content-Type: application/json" \
  -d '{"level": "fully_autonomous"}' | python3 -m json.tool
```

Supported conceptual levels are:

- `supervised`
- `semi_autonomous`
- `fully_autonomous`

### Inspect communication status and queued uplinks

```bash
curl -s $BASE/comm/status | python3 -m json.tool
curl -s $BASE/comm/$MISSION_ID/queue | python3 -m json.tool
```

## Important API Groups

| Method / group | Purpose |
|---|---|
| `/api/v1/missions` | Mission CRUD and lifecycle |
| `/api/v1/planning/auto` | A* or RL plan generation |
| `/api/v1/planning/manual` | Manual plan creation |
| `/api/v1/planning/multi-agent` | Multi-rover objective distribution and planning |
| `/api/v1/planning/environments/{id}/science-heatmap` | Science-value map |
| `/api/v1/simulation/rovers` | Rover creation and state |
| `/api/v1/simulation/run` | Plan execution |
| `/api/v1/telemetry` | Events and anomalies |
| `/api/v1/explain` | Structured and Claude-powered explanations |
| `/api/v1/comm/status` | Current uplink-window state |
| `/api/v1/comm/{mission_id}/queue` | Pending uplinks |

Ground-control operations such as anomaly resolution, autonomy-level changes, and AEGIS proposal approval/rejection can be gated by the communication window. When closed, the action is queued and delivered when the next window opens.

For the authoritative endpoint schemas and current request/response models, use the generated OpenAPI documentation.
