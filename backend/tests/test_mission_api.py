"""Integration tests for the mission and planning APIs."""
import pytest
from httpx import AsyncClient, ASGITransport
from main import app


@pytest.fixture
async def client():
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac


class TestHealth:
    async def test_root(self, client: AsyncClient):
        r = await client.get("/")
        assert r.status_code == 200
        assert r.json()["status"] == "nominal"

    async def test_health(self, client: AsyncClient):
        r = await client.get("/health")
        assert r.status_code == 200


class TestMissions:
    async def test_create_mission(self, client: AsyncClient):
        payload = {
            "name": "Alpha Survey",
            "description": "First survey of Zone Alpha",
            "objectives": [
                {"type": "reach_waypoint", "target_x": 5, "target_y": 5, "priority": 1},
                {"type": "collect_sample", "target_x": 8, "target_y": 3, "priority": 2},
            ],
        }
        r = await client.post("/api/v1/missions/", json=payload)
        assert r.status_code == 201
        data = r.json()
        assert data["name"] == "Alpha Survey"
        assert len(data["objectives"]) == 2
        assert data["status"] == "draft"
        return data

    async def test_list_missions(self, client: AsyncClient):
        # Create one first
        await client.post("/api/v1/missions/", json={"name": "Test"})
        r = await client.get("/api/v1/missions/")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    async def test_get_mission_not_found(self, client: AsyncClient):
        r = await client.get("/api/v1/missions/nonexistent-id")
        assert r.status_code == 404

    async def test_mission_environment(self, client: AsyncClient):
        create_r = await client.post("/api/v1/missions/", json={"name": "Env Test"})
        mission_id = create_r.json()["id"]

        r = await client.get(f"/api/v1/missions/{mission_id}/environment")
        assert r.status_code == 200
        env = r.json()
        assert env["grid"]["width"] == 20
        assert env["grid"]["height"] == 20


class TestPlanningAndSimulation:
    async def test_full_v1_workflow(self, client: AsyncClient):
        # 1. Create mission
        m = await client.post("/api/v1/missions/", json={
            "name": "Workflow Test",
            "objectives": [
                {"type": "reach_waypoint", "target_x": 3, "target_y": 3, "priority": 1},
            ],
        })
        assert m.status_code == 201
        mission = m.json()
        mission_id = mission["id"]

        # 2. Start the mission
        start_r = await client.post(f"/api/v1/missions/{mission_id}/start")
        assert start_r.status_code == 200

        # 3. Spawn a rover
        rover_r = await client.post("/api/v1/simulation/rovers", json={
            "mission_id": mission_id,
            "name": "Curiosity-Enc-1",
            "start_x": 0,
            "start_y": 0,
        })
        assert rover_r.status_code == 201
        rover = rover_r.json()
        rover_id = rover["id"]

        # 4. Generate A* plan
        plan_r = await client.post("/api/v1/planning/auto", json={
            "mission_id": mission_id,
            "rover_id": rover_id,
            "start_x": 0,
            "start_y": 0,
        })
        assert plan_r.status_code == 201
        plan = plan_r.json()
        plan_id = plan["id"]
        assert plan["planner"] == "astar"
        assert plan["total_commands"] > 0

        # 5. Run the simulation
        run_r = await client.post("/api/v1/simulation/run", json={
            "mission_id": mission_id,
            "plan_id": plan_id,
        })
        assert run_r.status_code == 202

        # 6. Check explainability
        explain_r = await client.get(f"/api/v1/explain/plan/{plan_id}")
        assert explain_r.status_code == 200
        explanation = explain_r.json()
        assert "steps" in explanation
        assert explanation["planner"] == "astar"
