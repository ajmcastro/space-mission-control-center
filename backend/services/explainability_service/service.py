"""
Explainability service — structured decision logs and LLM-ready summaries.

V1: rule-based structured explanations from plan steps and telemetry.
V3: Claude API streaming explanations via explain_with_claude().
"""
import json
from typing import AsyncIterator, Literal
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.repositories import (
    MissionRepository,
    PlanRepository,
    TelemetryRepository,
    AnomalyRepository,
    EnvironmentRepository,
)

log = structlog.get_logger(__name__)

_SYSTEM_PROMPT = (
    "You are an expert mission controller for the Enceladus rover program on Saturn's moon. "
    "Explain the following mission data in clear, concise language for ground operators. "
    "Cover: planner strategy, key non-MOVE operations (sample collection, charging, waits), "
    "battery budget risks, terrain or geyser hazards, objective completion status, and "
    "recommended next actions. Use bullet points for clarity. Be technically precise."
)


class ExplainabilityService:

    def __init__(self) -> None:
        self._missions = MissionRepository()
        self._plans = PlanRepository()
        self._telemetry = TelemetryRepository()
        self._anomalies = AnomalyRepository()
        self._environments = EnvironmentRepository()

    async def explain_plan(self, session: AsyncSession, plan_id: str) -> dict:
        plan = await self._plans.get(session, plan_id)
        if not plan:
            return {"error": "Plan not found"}

        mission = await self._missions.get(session, plan.mission_id)
        env = None
        if mission:
            env = await self._environments.get(session, mission.environment_id)

        explanations = []
        for step in plan.steps:
            cmd = step.command
            explanations.append({
                "sequence": step.sequence,
                "command": cmd.type.value,
                "target": {"x": cmd.target_x, "y": cmd.target_y},
                "estimated_battery_cost": step.estimated_battery_cost,
                "rationale": step.rationale,
            })

        return {
            "plan_id": plan_id,
            "mission_id": plan.mission_id,
            "planner": plan.planner.value,
            "total_steps": plan.total_commands,
            "estimated_battery_usage": plan.estimated_total_battery,
            "objectives_count": len(mission.objectives) if mission else 0,
            "steps": explanations,
            "llm_context": self._build_llm_context(plan, mission, env),
        }

    async def explain_mission(self, session: AsyncSession, mission_id: str) -> dict:
        mission = await self._missions.get(session, mission_id)
        if not mission:
            return {"error": "Mission not found"}

        anomalies = await self._anomalies.get_for_mission(session, mission_id)
        telemetry = await self._telemetry.get_for_mission(session, mission_id, limit=200)

        completed_objs = [o for o in mission.objectives if o.completed]
        pending_objs = [o for o in mission.objectives if not o.completed]

        return {
            "mission_id": mission_id,
            "name": mission.name,
            "status": mission.status.value,
            "progress_pct": mission.progress_pct,
            "objectives": {
                "total": len(mission.objectives),
                "completed": len(completed_objs),
                "pending": len(pending_objs),
            },
            "anomalies": {
                "total": len(anomalies),
                "by_severity": self._count_by(anomalies, "severity"),
                "by_type": self._count_by(anomalies, "type"),
            },
            "telemetry_events": len(telemetry),
            "rover_count": len(mission.rover_ids),
            "decision_log": await self._build_decision_log(session, mission_id),
        }

    async def explain_anomaly(self, session: AsyncSession, anomaly_id: str) -> dict:
        anomalies = await self._anomalies.get_all(session)
        for a in anomalies:
            if a.id == anomaly_id:
                return {
                    "anomaly_id": anomaly_id,
                    "type": a.type.value,
                    "severity": a.severity.value,
                    "description": a.description,
                    "location": {"x": a.x, "y": a.y},
                    "detected_at": a.detected_at.isoformat(),
                    "resolution": a.resolution.value,
                    "impact_analysis": self._anomaly_impact(a),
                    "recommended_actions": self._anomaly_recommendations(a),
                }
        return {"error": "Anomaly not found"}

    async def explain_with_claude(
        self,
        session: AsyncSession,
        subject: Literal["plan", "mission", "anomaly"],
        subject_id: str,
    ) -> AsyncIterator[str]:
        """Stream a natural-language explanation from Claude. Yields text chunks."""
        if not settings.anthropic_api_key:
            yield "Claude API key not configured. Set ANTHROPIC_API_KEY in your .env file."
            return

        # Build structured context for Claude.
        if subject == "plan":
            data = await self.explain_plan(session, subject_id)
            context = data.get("llm_context", json.dumps(data, default=str))
        elif subject == "mission":
            data = await self.explain_mission(session, subject_id)
            context = json.dumps({k: v for k, v in data.items() if k != "decision_log"}, default=str)
        else:
            data = await self.explain_anomaly(session, subject_id)
            context = json.dumps(data, default=str)

        if "error" in data:
            yield data["error"]
            return

        log.info("claude_explain_start", subject=subject, subject_id=subject_id)

        try:
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
            async with client.messages.stream(
                model=settings.claude_model,
                max_tokens=settings.claude_max_tokens,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": context}],
            ) as stream:
                async for chunk in stream.text_stream:
                    yield chunk
        except Exception as exc:
            log.error("claude_explain_error", subject=subject, subject_id=subject_id, exc_info=exc)
            yield f"Claude API error: {exc}"

    # ── Internal helpers ────────────────────────────────────────────────────

    def _build_llm_context(self, plan, mission, env) -> str:
        lines = [
            f"Mission: {mission.name if mission else 'unknown'}",
            f"Planner: {plan.planner.value}",
            f"Total commands: {plan.total_commands}",
            f"Estimated battery: {plan.estimated_total_battery:.1f} units",
        ]
        if mission:
            completed = sum(1 for o in mission.objectives if o.completed)
            lines.append(f"Objectives: {len(mission.objectives)} ({completed} completed)")
            for o in mission.objectives:
                status = "✓" if o.completed else "○"
                lines.append(
                    f"  {status} [{o.type.value}] target=({o.target_x},{o.target_y})"
                    f" priority={o.priority}"
                )
        if env:
            lines.append(f"Grid: {env.grid.width}x{env.grid.height}")
            lines.append(f"Active geysers: {len(env.active_geysers)}")
            lines.append(f"Temperature: {env.temperature_k:.0f} K")
            lines.append(f"Night cycle active: {env.is_night}")

        # Step-type breakdown
        from collections import Counter
        type_counts = Counter(s.command.type.value for s in plan.steps)
        lines.append("Command breakdown: " + ", ".join(
            f"{t}×{n}" for t, n in sorted(type_counts.items())
        ))

        # Full step list (capped at 120 to stay within token budget).
        # Non-MOVE steps are always included; MOVE steps are summarised in runs.
        MAX_STEPS = 120
        step_lines: list[str] = []
        move_run = 0  # consecutive MOVE steps being compressed

        def _flush_run() -> None:
            nonlocal move_run
            if move_run:
                step_lines.append(f"    ... {move_run} MOVE step(s) ...")
                move_run = 0

        for step in plan.steps[:MAX_STEPS]:
            cmd = step.command
            t = cmd.type.value
            if t == "move":
                move_run += 1
            else:
                _flush_run()
                target = (
                    f"({cmd.target_x},{cmd.target_y})"
                    if cmd.target_x is not None else "—"
                )
                cost = f"{step.estimated_battery_cost:.1f}W"
                note = f" [{step.rationale}]" if step.rationale else ""
                step_lines.append(
                    f"  #{step.sequence:>3} {t:<16} target={target:<12} cost={cost}{note}"
                )
        _flush_run()

        if plan.total_commands > MAX_STEPS:
            step_lines.append(f"  ... ({plan.total_commands - MAX_STEPS} more steps truncated)")

        if step_lines:
            lines.append("Step sequence:")
            lines.extend(step_lines)

        if hasattr(plan, "metadata") and plan.metadata:
            lines.append(f"Planner metadata: {json.dumps(plan.metadata)}")
        return "\n".join(lines)

    async def _build_decision_log(self, session: AsyncSession, mission_id: str) -> list[dict]:
        events = await self._telemetry.get_for_mission(session, mission_id, limit=500)
        decision_log = []
        for e in events:
            if e.payload.get("command_type") in ("move", "collect_sample"):
                decision_log.append({
                    "timestamp": e.timestamp.isoformat(),
                    "action": e.payload.get("command_type"),
                    "position": {"x": e.x, "y": e.y},
                    "battery_pct": e.battery_pct,
                })
        return decision_log[-50:]

    def _count_by(self, items: list, field: str) -> dict:
        counts: dict = {}
        for item in items:
            val = getattr(item, field)
            key = val.value if hasattr(val, "value") else str(val)
            counts[key] = counts.get(key, 0) + 1
        return counts

    def _anomaly_impact(self, anomaly) -> str:
        from core.models.anomaly import AnomalyType
        impact_map = {
            AnomalyType.WHEEL_STUCK: "Rover halted. Mission progress paused until recovery.",
            AnomalyType.COMM_LOSS: "Command uplink interrupted. Rover operating on last known state.",
            AnomalyType.ENERGY_SPIKE: "Battery reduced by ~10%. Remaining range decreased.",
            AnomalyType.LOW_BATTERY: "Risk of power-down. Immediate charging or abort recommended.",
            AnomalyType.GEYSER_PROXIMITY: "Thermal and pressure hazard. Rover halted for safety.",
            AnomalyType.SENSOR_FAULT: "Science data may be unreliable.",
            AnomalyType.PATH_BLOCKED: "Current route is impassable. Replanning required.",
            AnomalyType.UNKNOWN: "Unknown impact. Manual review required.",
        }
        return impact_map.get(anomaly.type, "Unknown impact")

    def _anomaly_recommendations(self, anomaly) -> list[str]:
        from core.models.anomaly import AnomalyType
        recs_map = {
            AnomalyType.WHEEL_STUCK: ["Wait for auto-recovery", "Command WAIT then retry MOVE", "Replan route avoiding terrain"],
            AnomalyType.COMM_LOSS: ["Wait for link recovery", "Rover will enter safe mode autonomously"],
            AnomalyType.ENERGY_SPIKE: ["Continue with reduced range estimate", "Consider CHARGE command"],
            AnomalyType.LOW_BATTERY: ["Issue CHARGE command immediately", "Abort non-critical objectives"],
            AnomalyType.GEYSER_PROXIMITY: ["Replan route away from geyser zone", "Wait for geyser dormancy window"],
            AnomalyType.PATH_BLOCKED: ["Replan with updated terrain map"],
            AnomalyType.SENSOR_FAULT: ["Mark samples as provisional", "Run sensor self-test sequence"],
            AnomalyType.UNKNOWN: ["Manual operator review required"],
        }
        return recs_map.get(anomaly.type, ["Manual review required"])
