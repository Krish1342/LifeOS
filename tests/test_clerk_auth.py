from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from lifeos.agents.orchestrator.main import app
from lifeos.shared.auth.clerk import ClerkAuthManager
from lifeos.shared.db.tokens import TokenStore


@pytest.mark.asyncio
async def test_clerk_auth_unconfigured_fallback():
    mgr = ClerkAuthManager(secret_key="", publishable_key="")
    assert not mgr.is_configured

    # Verification returns local session in development
    payload = await mgr.verify_session_token("some_token")
    assert payload is not None
    assert payload.get("sub") == "local_dev_user"

    # Token fetch returns None when unconfigured
    tok = await mgr.get_oauth_access_token("user_123", "oauth_google")
    assert tok is None


@pytest.mark.asyncio
async def test_clerk_get_oauth_access_token_success():
    mgr = ClerkAuthManager(secret_key="sk_test_12345", publishable_key="pk_test_12345")
    assert mgr.is_configured

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = [
        {
            "object": "oauth_access_token",
            "token": "mock_google_oauth_token_from_clerk",
            "provider": "oauth_google",
            "scopes": ["https://www.googleapis.com/auth/calendar"],
        }
    ]

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        token_data = await mgr.get_oauth_access_token("user_abc", "oauth_google")

        assert token_data is not None
        assert token_data["token"] == "mock_google_oauth_token_from_clerk"
        assert token_data["provider"] == "oauth_google"


@pytest.mark.asyncio
async def test_clerk_sync_tokens_to_encrypted_store():
    mgr = ClerkAuthManager(secret_key="sk_test_12345")

    with patch.object(
        mgr,
        "get_oauth_access_token",
        new_callable=AsyncMock,
        return_value={
            "token": "mock_access_token_123",
            "scopes": ["https://www.googleapis.com/auth/calendar.readonly"],
        },
    ):
        synced = await mgr.sync_tokens_to_db("user_clerk_999", "oauth_google")
        assert synced is True

        # Verify token is in TokenStore and decrypts properly
        store = TokenStore(allowed_service="google_calendar")
        creds = await store.get_credentials("user_clerk_999", "google_calendar")
        assert creds is not None
        assert creds["access_token"] == "mock_access_token_123"


@pytest.mark.asyncio
async def test_orchestrator_auth_config_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/auth/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "auth_provider" in data
        assert "free_tier_status" in data
        assert "zero cost" in data["free_tier_status"]


@pytest.mark.asyncio
async def test_orchestrator_clerk_sync_tokens_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch(
            "lifeos.shared.auth.clerk.ClerkAuthManager.sync_tokens_to_db",
            new_callable=AsyncMock,
            return_value=True,
        ), patch(
            "lifeos.shared.auth.clerk.ClerkAuthManager.is_configured",
            return_value=True,
        ):
            resp = await client.post(
                "/api/auth/clerk/sync-tokens",
                json={"user_id": "usr_test1", "provider": "oauth_google"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "synced"
            assert data["user_id"] == "usr_test1"
