"""
Explainability service — structured decision logs and LLM-ready summaries.

V1: rule-based structured explanations from plan steps and telemetry.
V3: swap explain() to call Claude API with the structured context.
"""
from sqlalchemy.ext.asyncio import AsyncSession

from core.repositories import (
    MissionRepository,
    PlanRepository,
    TelemetryRepository,
    AnomalyRepository,
    EnvironmentRepository,
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

    def _build_llm_context(self, plan, mission, env) -> str:
        lines = [
            f"Mission: {mission.name if mission else 'unknown'}",
            f"Planner: {plan.planner.value}",
            f"Total commands: {plan.total_commands}",
            f"Estimated battery: {plan.estimated_total_battery:.1f} units",
        ]
        if mission:
            lines.append(f"Objectives: {len(mission.objectives)}")
        if env:
            lines.append(f"Grid: {env.grid.width}x{env.grid.height}")
            lines.append(f"Active geysers: {len(env.active_geysers)}")
        return "\n".join(lines)

    async def _build_decision_log(self, session: AsyncSession, mission_id: str) -> list[dict]:
        events = await self._telemetry.get_for_mission(session, mission_id, limit=500)
        log = []
        for e in events:
            if e.payload.get("command_type") in ("move", "collect_sample"):
                log.append({
                    "timestamp": e.timestamp.isoformat(),
                    "action": e.payload.get("command_type"),
                    "position": {"x": e.x, "y": e.y},
                    "battery_pct": e.battery_pct,
                })
        return log[-50:]

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
