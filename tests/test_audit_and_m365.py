import pytest
from httpx import AsyncClient, ASGITransport

from lifeos.shared.m365.client import M365Connector
from lifeos.shared.audit.viewer import PrivacyAuditTracker
from lifeos.agents.orchestrator.main import app as orch_app


@pytest.mark.asyncio
async def test_m365_connector_methods():
    connector = M365Connector()
    events = await connector.list_calendar_events()
    assert isinstance(events, list)
    assert len(events) > 0
    assert events[0]["provider"] == "microsoft_365"

    messages = await connector.list_messages()
    assert isinstance(messages, list)
    assert len(messages) > 0
    assert messages[0]["provider"] == "microsoft_365"


@pytest.mark.asyncio
async def test_privacy_audit_metrics():
    metrics = await PrivacyAuditTracker.get_privacy_metrics()
    assert "compliance_status" in metrics
    assert metrics["compliance_status"] == "100% compliant"
    assert metrics["policy_violations"] == 0


@pytest.mark.asyncio
async def test_orchestrator_audit_and_privacy_endpoints():
    transport = ASGITransport(app=orch_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Audit logs endpoint
        audit_resp = await client.get("/api/audit")
        assert audit_resp.status_code == 200
        assert "runs" in audit_resp.json()
        assert "X-Response-Time-Ms" in audit_resp.headers

        # Privacy verification endpoint
        priv_resp = await client.get("/api/privacy/status")
        assert priv_resp.status_code == 200
        data = priv_resp.json()
        assert data["compliance_status"] == "100% compliant"
