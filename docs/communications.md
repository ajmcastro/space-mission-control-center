# Communications

[← Back to README](../README.md)

## Why Communication Windows Matter

A distant planetary rover cannot assume continuous low-latency communication with Earth.

The project models this by separating:

1. **onboard execution**, which continues autonomously; and
2. **ground-control interventions**, which may only be delivered during communication windows.

This distinction is central to the autonomy model.

## Window Schedule

Communication windows are configurable:

```bash
COMM_SLOT_SECONDS=60
COMM_WINDOW_DURATION_SECONDS=15
```

- `COMM_SLOT_SECONDS` controls the interval between uplink openings.
- `COMM_WINDOW_DURATION_SECONDS` controls how long each window remains open.

The current state can be queried through:

```text
GET /api/v1/comm/status
```

The response exposes whether the window is open and timing information for the next transition.

## Uplink Queue

When ground control issues a gated action while the window is closed, the command is placed in an in-memory uplink queue.

```text
Ground-control action
         │
         ▼
 Communication open?
      │        │
     yes       no
      │        │
      ▼        ▼
   Deliver    Queue
                │
                ▼
        Next open window
                │
                ▼
             Deliver
```

Pending commands can be inspected through:

```text
GET /api/v1/comm/{mission_id}/queue
```

A background flusher delivers queued actions when a communication window opens.

## Gated Ground-Control Actions

Examples of gated actions include:

- manual anomaly resolution;
- changing rover autonomy level;
- approving an AEGIS proposal;
- rejecting an AEGIS proposal.

These actions use a consistent delivered/queued response concept.

## What Is Not Gated

The rover's onboard execution loop is deliberately **not** blocked by communication windows.

While Earth is out of contact, the rover can continue:

- executing the current plan;
- emitting telemetry locally/system-side;
- responding to anomalies through FPS;
- replanning when required;
- performing AEGIS-style autonomous behavior according to its autonomy level.

This models the operational reason autonomy is important in deep-space systems.

## Simulated Communication Delay

The project also exposes:

```bash
COMM_DELAY_SECONDS=2.5
```

This represents a configurable simulated one-way delay within the educational simulation.

The window model and delay model are abstractions designed to make delayed supervision visible in the software architecture; they are not intended as a precise orbital communications simulator.

## Timeline Integration

Communication windows are visualized in the timeline UI.

The replay view can show:

- open/closed periods;
- queued interventions;
- mission events occurring while ground control is unavailable.

This makes it possible to correlate autonomy decisions with communication availability.

## API Example

```bash
BASE=http://localhost:8000/api/v1

# Current communication state
curl -s $BASE/comm/status | python3 -m json.tool

# Pending uplinks for a mission
curl -s $BASE/comm/$MISSION_ID/queue | python3 -m json.tool
```

See [API Workflows](api-workflows.md) for a complete V4 example.
