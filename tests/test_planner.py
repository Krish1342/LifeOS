from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from lifeos.agents.orchestrator.main import app
from lifeos.shared.llm.planner import TaskPlanner


@pytest.mark.asyncio
async def test_planner_heuristic_calendar_and_task():
    planner = TaskPlanner()
    plan = await planner.plan("Check my meetings for tomorrow")
    assert len(plan) > 0
    agents = [p["agent"] for p in plan]
    assert "calendar" in agents


@pytest.mark.asyncio
async def test_planner_heuristic_email_actions():
    planner = TaskPlanner()
    plan = await planner.plan("Extract action items from email")
    assert len(plan) > 0
    skills = [p["skill"] for p in plan]
    assert "extract_action_items" in skills


@pytest.mark.asyncio
async def test_planner_heuristic_files():
    planner = TaskPlanner()
    plan = await planner.plan("List files in my google drive")
    assert len(plan) > 0
    agents = [p["agent"] for p in plan]
    assert "file" in agents


@pytest.mark.asyncio
async def test_planner_llm_json_parsing():
    planner = TaskPlanner()
    mock_llm_response = {
        "text": '[{"agent": "calendar", "skill": "list_events", "params": {}}, {"agent": "task", "skill": "list_open_tasks", "params": {}}]'
    }
    with patch.object(planner.llm, "generate", new_callable=AsyncMock, return_value=mock_llm_response):
        plan = await planner.plan("Give me a comprehensive operational overview")
        assert len(plan) == 2
        assert plan[0]["agent"] == "calendar"
        assert plan[1]["agent"] == "task"


@pytest.mark.asyncio
async def test_orchestrator_dynamic_command_execution():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/command",
            json={"command": "Check my pending tasks and meetings", "auto_confirm": True}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert "results" in data
        assert "briefing" in data
