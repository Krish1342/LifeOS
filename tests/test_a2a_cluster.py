import pytest
from httpx import AsyncClient, ASGITransport

from lifeos.agents.calendar.main import app as calendar_app
from lifeos.agents.email.main import app as email_app
from lifeos.agents.task.main import app as task_app
from lifeos.shared.a2a.models import JsonRpcRequest, Message, DataPart, TaskState


@pytest.mark.asyncio
async def test_calendar_agent_agent_card():
    transport = ASGITransport(app=calendar_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/.well-known/agent-card.json")
        assert resp.status_code == 200
        card = resp.json()
        assert card["name"] == "LifeOS Calendar Agent"
        assert any(s["id"] == "list_events" for s in card["skills"])


@pytest.mark.asyncio
async def test_calendar_agent_send_message_rpc():
    transport = ASGITransport(app=calendar_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        rpc_req = JsonRpcRequest(
            id="req_001",
            method="SendMessage",
            params={
                "message": Message(
                    role="user",
                    parts=[
                        DataPart(
                            data={
                                "skill": "list_events",
                                "params": {"start_date": "2026-10-21", "end_date": "2026-10-28"}
                            }
                        )
                    ]
                ).model_dump()
            }
        )
        resp = await client.post("/a2a/v1", json=rpc_req.model_dump())
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "req_001"
        assert data["result"]["status"]["state"] == TaskState.COMPLETED
        assert len(data["result"]["artifacts"]) > 0


@pytest.mark.asyncio
async def test_email_agent_send_message_rpc():
    transport = ASGITransport(app=email_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        rpc_req = JsonRpcRequest(
            id="req_002",
            method="SendMessage",
            params={
                "message": Message(
                    role="user",
                    parts=[
                        DataPart(
                            data={
                                "skill": "summarize_inbox",
                                "params": {"query": "is:unread"}
                            }
                        )
                    ]
                ).model_dump()
            }
        )
        resp = await client.post("/a2a/v1", json=rpc_req.model_dump())
        assert resp.status_code == 200
        data = resp.json()
        assert data["result"]["status"]["state"] == TaskState.COMPLETED
