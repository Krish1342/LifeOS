import pytest

from lifeos.shared.a2a import (
    AgentCard,
    AgentSkill,
    SupportedInterface,
)
from lifeos.shared.crypto import TokenEncryption
from lifeos.shared.http import ScopedHTTPClient, SecurityError
from lifeos.shared.llm import DataSensitivity, LocalLLMClient


def test_token_encryption_roundtrip():
    key = TokenEncryption.generate_key_b64()
    crypto = TokenEncryption(key)

    original_token = "ya29.a0ARrdaM_test_google_oauth_refresh_token_xyz"
    encrypted = crypto.encrypt(original_token)
    assert encrypted != original_token
    assert len(encrypted) > 20

    decrypted = crypto.decrypt(encrypted)
    assert decrypted == original_token


def test_scoped_http_client_sandbox():
    client = ScopedHTTPClient(allowed_hosts=["www.googleapis.com", "*.supabase.co"])

    # Permitted hosts
    client._verify_host("https://www.googleapis.com/calendar/v3/events")
    client._verify_host("https://xyz.supabase.co/rest/v1/tasks")

    # Blocked hosts
    with pytest.raises(SecurityError) as exc_info:
        client._verify_host("https://api.openai.com/v1/chat/completions")
    assert "Security Boundary Violation" in str(exc_info.value)

    with pytest.raises(SecurityError):
        client._verify_host("https://evil-site.com/steal-data")


def test_llm_privacy_violation_guard():
    # If someone tries to configure a remote endpoint and send private user data, it must reject
    remote_client = LocalLLMClient(base_url="https://external-llm-service.com")
    
    with pytest.raises(SecurityError) as exc_info:
        import asyncio
        asyncio.run(
            remote_client.generate(
                prompt="Summarize my email",
                sensitivity=DataSensitivity.PRIVATE
            )
        )
    assert "Privacy Violation" in str(exc_info.value)


def test_a2a_agent_card_validation():
    card = AgentCard(
        name="Test Agent",
        description="A test agent",
        url="http://localhost:8001",
        supportedInterfaces=[
            SupportedInterface(url="http://localhost:8001/a2a/v1")
        ],
        skills=[
            AgentSkill(id="test_skill", name="Test", description="A test skill")
        ]
    )
    dumped = card.model_dump()
    assert dumped["name"] == "Test Agent"
    assert dumped["skills"][0]["id"] == "test_skill"
