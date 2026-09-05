"""Tests for the V4 Communication Windows feature — schedule math + gate/queue/flush."""
import pytest
from httpx import AsyncClient, ASGITransport

from core.config import settings
from core.database import AsyncSessionLocal
from core.models.anomaly import Anomaly, AnomalyType, AnomalySeverity
from core.repositories import AnomalyRepository
from services.comm_service import windows
from main import app


@pytest.fixture
async def client():
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac


# ─── Pure schedule math ────────────────────────────────────────────────────────

class TestWindowSchedule:
    def test_window_open_at_phase_zero(self, monkeypatch):
        monkeypatch.setattr(settings, "comm_slot_seconds", 10.0)
        monkeypatch.setattr(settings, "comm_window_duration_seconds", 4.0)
        assert windows.is_window_open(now=0.0) is True
        assert windows.is_window_open(now=3.9) is True

    def test_window_closed_after_duration(self, monkeypatch):
        monkeypatch.setattr(settings, "comm_slot_seconds", 10.0)
        monkeypatch.setattr(settings, "comm_window_duration_seconds", 4.0)
        assert windows.is_window_open(now=4.0) is False
        assert windows.is_window_open(now=9.9) is False

    def test_window_reopens_on_next_slot(self, monkeypatch):
        monkeypatch.setattr(settings, "comm_slot_seconds", 10.0)
        monkeypatch.setattr(settings, "comm_window_duration_seconds", 4.0)
        assert windows.is_window_open(now=10.0) is True
        assert windows.is_window_open(now=23.5) is True
        assert windows.is_window_open(now=24.0) is False

    def test_seconds_until_next_open_when_closed(self, monkeypatch):
        monkeypatch.setattr(settings, "comm_slot_seconds", 10.0)
        monkeypatch.setattr(settings, "comm_window_duration_seconds", 4.0)
        assert windows.seconds_until_next_open(now=6.0) == pytest.approx(4.0)

    def test_seconds_until_next_open_when_open(self, monkeypatch):
        monkeypatch.setattr(settings, "comm_slot_seconds", 10.0)
        monkeypatch.setattr(settings, "comm_window_duration_seconds", 4.0)
        assert windows.seconds_until_next_open(now=2.0) == pytest.approx(0.0)

    def test_seconds_until_close_when_open(self, monkeypatch):
        monkeypatch.setattr(settings, "comm_slot_seconds", 10.0)
        monkeypatch.setattr(settings, "comm_window_duration_seconds", 4.0)
        assert windows.seconds_until_close(now=1.0) == pytest.approx(3.0)

    def test_seconds_until_close_when_closed(self, monkeypatch):
        monkeypatch.setattr(settings, "comm_slot_seconds", 10.0)
        monkeypatch.setattr(settings, "comm_window_duration_seconds", 4.0)
        assert windows.seconds_until_close(now=7.0) == pytest.approx(0.0)


# ─── Gate / queue / flush, end-to-end through the API ─────────────────────────

class TestCommGate:
    async def _make_mission_rover_anomaly(self, client: AsyncClient) -> tuple[str, str, str]:
        r = await client.post("/api/v1/missions/", json={"name": "Comm Window Test"})
        mission_id = r.json()["id"]

        r = await client.post(
            "/api/v1/simulation/rovers",
            json={"mission_id": mission_id, "name": "Sojourner", "start_x": 0, "start_y": 0},
        )
        rover_id = r.json()["id"]

        anomaly = Anomaly(
            type=AnomalyType.SENSOR_FAULT,
            severity=AnomalySeverity.LOW,
            mission_id=mission_id,
            rover_id=rover_id,
            x=0, y=0,
            description="test anomaly",
        )
        async with AsyncSessionLocal() as session:
            await AnomalyRepository().append(session, anomaly)
            await session.commit()

        return mission_id, rover_id, anomaly.id

    async def test_resolve_delivered_immediately_when_window_open(self, client: AsyncClient, monkeypatch):
        monkeypatch.setattr(settings, "comm_window_duration_seconds", settings.comm_slot_seconds)
        mission_id, rover_id, anomaly_id = await self._make_mission_rover_anomaly(client)

        r = await client.patch(f"/api/v1/telemetry/anomalies/{anomaly_id}/resolve", json={"resolution": "ignored"})
        assert r.status_code == 200
        data = r.json()
        assert data["delivered"] is True
        assert data["result"]["resolution"] == "ignored"

        r = await client.get(f"/api/v1/comm/{mission_id}/queue")
        assert r.json() == []

    async def test_resolve_queued_when_window_closed_then_delivered_on_flush(
        self, client: AsyncClient, monkeypatch
    ):
        monkeypatch.setattr(settings, "comm_window_duration_seconds", 0.0)
        mission_id, rover_id, anomaly_id = await self._make_mission_rover_anomaly(client)

        r = await client.patch(f"/api/v1/telemetry/anomalies/{anomaly_id}/resolve", json={"resolution": "ignored"})
        assert r.status_code == 200
        data = r.json()
        assert data["delivered"] is False
        assert data["uplink"]["kind"] == "resolve_anomaly"

        r = await client.get(f"/api/v1/comm/status")
        assert r.json()["open"] is False

        r = await client.get(f"/api/v1/comm/{mission_id}/queue")
        queue = r.json()
        assert len(queue) == 1
        assert queue[0]["rover_id"] == rover_id

        # Anomaly must still be pending — it was queued, not resolved.
        r = await client.get(f"/api/v1/telemetry/anomalies/{mission_id}")
        assert r.json()[0]["resolution"] == "pending"

        # Open the window and let the background-style flush deliver the queued command.
        monkeypatch.setattr(settings, "comm_window_duration_seconds", settings.comm_slot_seconds)
        await app.state.comm_service.flush_ready()

        r = await client.get(f"/api/v1/telemetry/anomalies/{mission_id}")
        assert r.json()[0]["resolution"] == "ignored"

        r = await client.get(f"/api/v1/comm/{mission_id}/queue")
        assert r.json() == []
