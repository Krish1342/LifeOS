import pytest
from httpx import AsyncClient, ASGITransport

from lifeos.shared.a2a.models import AgentCard, AgentSkill, SupportedInterface
from lifeos.shared.a2a.registry import AgentRegistry
from lifeos.shared.scheduler.engine import WorkflowScheduler
from lifeos.agents.orchestrator.main import app as orch_app


@pytest.mark.asyncio
async def test_dynamic_agent_registry():
    registry = AgentRegistry()
    mock_card = AgentCard(
        name="LifeOS Custom Planner",
        description="Custom scheduling planner",
        url="http://localhost:8010",
        supportedInterfaces=[SupportedInterface(url="http://localhost:8010/a2a/v1")],
        skills=[AgentSkill(id="custom_plan", name="Custom Plan", description="Generates custom plans")]
    )

    registry.register_static("planner", "http://localhost:8010", mock_card)
    agent = registry.get_agent("planner")
    assert agent is not None
    assert agent.url == "http://localhost:8010"

    # Test skill matching
    matched = registry.find_agent_for_skill("custom_plan")
    assert matched is not None
    assert matched.name == "planner"

    unmatched = registry.find_agent_for_skill("nonexistent_skill")
    assert unmatched is None


@pytest.mark.asyncio
async def test_scheduler_lifecycle():
    executed_commands = []

    async def mock_executor(cmd: str):
        executed_commands.append(cmd)

    scheduler = WorkflowScheduler(executor=mock_executor)

    # 1. Add job
    job = await scheduler.add_job("Summarize my week", interval_seconds=1)
    assert job.command == "Summarize my week"
    assert job.id.startswith("sched_")

    # 2. List jobs
    jobs = await scheduler.list_jobs()
    assert any(j.id == job.id for j in jobs)

    # 3. Remove job
    deleted = await scheduler.remove_job(job.id)
    assert deleted is True

    jobs_after = await scheduler.list_jobs()
    assert not any(j.id == job.id for j in jobs_after)


@pytest.mark.asyncio
async def test_orchestrator_schedules_api():
    transport = ASGITransport(app=orch_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create schedule
        resp = await client.post(
            "/api/schedules",
            json={"command": "Summarize my week", "interval_seconds": 1800}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "created"
        job_id = data["schedule"]["id"]

        # List schedules
        list_resp = await client.get("/api/schedules")
        assert list_resp.status_code == 200
        schedules = list_resp.json()["schedules"]
        assert any(s["id"] == job_id for s in schedules)

        # Delete schedule
        del_resp = await client.delete(f"/api/schedules/{job_id}")
        assert del_resp.status_code == 200
        assert del_resp.json()["status"] == "deleted"
