import pytest
from httpx import ASGITransport, AsyncClient

from lifeos.agents.orchestrator.main import app as orch_app


@pytest.mark.asyncio
async def test_story_1_summarize_my_week():
    transport = ASGITransport(app=orch_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/command",
            json={"command": "Summarize my week"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert "briefing" in data
        assert "Weekly Summary" in data["briefing"]
        assert "Calendar" in data["briefing"]
        assert "Inbox" in data["briefing"]


@pytest.mark.asyncio
async def test_story_2_create_tasks_with_confirmation():
    transport = ASGITransport(app=orch_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Step 1: Submit command without auto_confirm
        resp = await client.post(
            "/api/command",
            json={"command": "Create tasks from my unread emails", "auto_confirm": False}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "confirmation_required"
        assert "confirmation_id" in data
        assert len(data["pending_actions"]) > 0

        conf_id = data["confirmation_id"]

        # Step 2: Confirm execution
        conf_resp = await client.post(
            "/api/confirm",
            json={"confirmation_id": conf_id, "approved": True}
        )
        assert conf_resp.status_code == 200
        conf_data = conf_resp.json()
        assert conf_data["status"] == "completed"
        assert "Successfully created" in conf_data["message"]


@pytest.mark.asyncio
async def test_story_3_organize_drive_with_rejection():
    transport = ASGITransport(app=orch_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/command",
            json={"command": "Organize my drive project folder", "auto_confirm": False}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "confirmation_required"

        conf_id = data["confirmation_id"]

        # User rejects
        conf_resp = await client.post(
            "/api/confirm",
            json={"confirmation_id": conf_id, "approved": False}
        )
        assert conf_resp.status_code == 200
        conf_data = conf_resp.json()
        assert conf_data["status"] == "canceled"


@pytest.mark.asyncio
async def test_story_4_block_focus_time_tomorrow():
    transport = ASGITransport(app=orch_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/command",
            json={"command": "Block focus time tomorrow morning", "auto_confirm": True}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert "Focus block scheduled" in data["briefing"]
