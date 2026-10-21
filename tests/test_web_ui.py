import pytest
from httpx import AsyncClient, ASGITransport
from lifeos.agents.orchestrator.main import app as orch_app


@pytest.mark.asyncio
async def test_dashboard_html_served():
    transport = ASGITransport(app=orch_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "LifeOS" in resp.text
        assert "commandInput" in resp.text
        assert "pipelineCard" in resp.text


@pytest.mark.asyncio
async def test_dashboard_tasks_api():
    transport = ASGITransport(app=orch_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/tasks")
        assert resp.status_code == 200
        data = resp.json()
        assert "tasks" in data
        assert isinstance(data["tasks"], list)


@pytest.mark.asyncio
async def test_dashboard_task_toggle():
    transport = ASGITransport(app=orch_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/tasks/task_demo_001/toggle")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["task_id"] == "task_demo_001"


@pytest.mark.asyncio
async def test_sse_streaming_command():
    transport = ASGITransport(app=orch_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/command/stream?command=Summarize+my+week")
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]
        body = resp.text
        assert "event: step" in body
        assert "event: agent_result" in body
        assert "event: done" in body
