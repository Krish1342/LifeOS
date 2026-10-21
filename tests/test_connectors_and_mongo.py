import pytest
from httpx import ASGITransport, AsyncClient

from lifeos.agents.task.main import app as task_app
from lifeos.shared.a2a.models import DataPart, JsonRpcRequest, Message, TaskState
from lifeos.shared.db.tokens import TokenStore
from lifeos.shared.google.calendar import CalendarConnector
from lifeos.shared.google.drive import DriveConnector
from lifeos.shared.google.gmail import GmailConnector
from lifeos.shared.http.client import SecurityError


@pytest.mark.asyncio
async def test_calendar_connector_methods():
    connector = CalendarConnector()
    events = await connector.list_events()
    assert isinstance(events, list)
    assert len(events) > 0
    assert "summary" in events[0]

    conflicts = await connector.detect_conflicts()
    assert isinstance(conflicts, list)

    new_evt = await connector.create_event(
        summary="Test Planning Session",
        start_time="2026-10-22T10:00:00Z",
        end_time="2026-10-22T11:00:00Z"
    )
    assert new_evt["summary"] == "Test Planning Session"


@pytest.mark.asyncio
async def test_gmail_connector_methods():
    connector = GmailConnector()
    messages = await connector.list_messages(query="is:unread")
    assert isinstance(messages, list)
    assert len(messages) > 0
    assert "subject" in messages[0]

    draft = await connector.draft_reply(
        to="colleague@example.com",
        subject="Re: Review",
        body="I have approved the budget."
    )
    assert draft["to"] == "colleague@example.com"


@pytest.mark.asyncio
async def test_drive_connector_methods():
    connector = DriveConnector()
    files = await connector.list_files()
    assert isinstance(files, list)
    assert len(files) > 0
    assert "name" in files[0]

    folder = await connector.create_folder("Q4 Invoices")
    assert folder["name"] == "Q4 Invoices"


@pytest.mark.asyncio
async def test_token_store_scope_isolation():
    cal_store = TokenStore(allowed_service="google_calendar")
    # Trying to access gmail tokens with a calendar-scoped token store must trigger a SecurityError
    with pytest.raises(SecurityError) as exc_info:
        await cal_store.get_credentials("user123", "gmail")
    assert "Scope Violation" in str(exc_info.value)


@pytest.mark.asyncio
async def test_task_agent_create_and_list():
    transport = ASGITransport(app=task_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create a task
        create_req = JsonRpcRequest(
            id="req_t1",
            method="SendMessage",
            params={
                "message": Message(
                    role="user",
                    parts=[
                        DataPart(
                            data={
                                "skill": "create_task",
                                "params": {
                                    "title": "Review Q4 Strategy",
                                    "priority": "high",
                                    "due_date": "2026-10-25"
                                }
                            }
                        )
                    ]
                ).model_dump()
            }
        )
        resp = await client.post("/a2a/v1", json=create_req.model_dump())
        assert resp.status_code == 200
        data = resp.json()
        assert data["result"]["status"]["state"] == TaskState.COMPLETED
        created_task = data["result"]["artifacts"][0]["parts"][0]["data"]["task"]
        assert created_task["title"] == "Review Q4 Strategy"

        # 2. List open tasks
        list_req = JsonRpcRequest(
            id="req_t2",
            method="SendMessage",
            params={
                "message": Message(
                    role="user",
                    parts=[
                        DataPart(
                            data={
                                "skill": "list_open_tasks",
                                "params": {}
                            }
                        )
                    ]
                ).model_dump()
            }
        )
        list_resp = await client.post("/a2a/v1", json=list_req.model_dump())
        assert list_resp.status_code == 200
        list_data = list_resp.json()
        tasks = list_data["result"]["artifacts"][0]["parts"][0]["data"]["tasks"]
        assert any(t["title"] == "Review Q4 Strategy" for t in tasks)
