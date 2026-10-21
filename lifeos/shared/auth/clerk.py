import logging
import os
from typing import Any

import httpx
import jwt
from jwt import PyJWKClient

from lifeos.shared.db.tokens import TokenStore

logger = logging.getLogger("lifeos.auth.clerk")


class ClerkAuthManager:
    """Manages authentication and OAuth token retrieval via Clerk.
    
    Clerk provides a 100% free tier (up to 10,000 MAUs, no credit card required)
    for user management and OAuth social connections (Google, Microsoft, etc.).
    """

    def __init__(
        self,
        secret_key: str | None = None,
        publishable_key: str | None = None,
        jwks_url: str | None = None,
    ):
        self.secret_key = secret_key or os.getenv("CLERK_SECRET_KEY", "")
        self.publishable_key = publishable_key or os.getenv("CLERK_PUBLISHABLE_KEY", "")
        self.jwks_url = jwks_url or os.getenv("CLERK_JWKS_URL", "https://api.clerk.com/v1/jwks")
        self.api_base = "https://api.clerk.com/v1"
        self._jwks_client: PyJWKClient | None = None

    @property
    def is_configured(self) -> bool:
        """Returns True if Clerk secret key is configured."""
        return bool(self.secret_key)

    def _get_jwks_client(self) -> PyJWKClient:
        if self._jwks_client is None:
            self._jwks_client = PyJWKClient(self.jwks_url)
        return self._jwks_client

    async def verify_session_token(self, token: str) -> dict[str, Any] | None:
        """Verifies a Clerk JWT session token.
        
        If Clerk is not configured (offline / local development), returns
        a mock local session for seamless local execution.
        """
        if not self.is_configured:
            return {"sub": "local_dev_user", "mode": "development_offline"}

        try:
            jwks_client = self._get_jwks_client()
            signing_key = jwks_client.get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                options={"verify_aud": False},
            )
            return payload
        except Exception as e:
            logger.warning(f"Clerk JWT verification failed: {e}")
            return None

    async def get_oauth_access_token(
        self, user_id: str, provider: str = "oauth_google"
    ) -> dict[str, Any] | None:
        """Retrieves external OAuth access tokens for a user from Clerk Backend API.
        
        Endpoint: GET /v1/users/{user_id}/oauth_access_tokens/{provider}
        """
        if not self.is_configured:
            logger.info("Clerk secret key not configured; skipping remote token fetch.")
            return None

        url = f"{self.api_base}/users/{user_id}/oauth_access_tokens/{provider}"
        headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, list) and len(data) > 0:
                        return data[0]
                else:
                    logger.warning(f"Clerk OAuth token fetch failed ({resp.status_code}): {resp.text}")
                    return None
        except Exception as e:
            logger.error(f"Error fetching OAuth token from Clerk: {e}")
            return None

    async def sync_tokens_to_db(self, user_id: str, provider: str = "oauth_google") -> bool:
        """Fetches the latest provider token from Clerk and saves into encrypted TokenStore in MongoDB."""
        token_info = await self.get_oauth_access_token(user_id=user_id, provider=provider)
        if not token_info or not token_info.get("token"):
            return False

        access_token = token_info.get("token")
        scopes = token_info.get("scopes", [])

        if provider == "oauth_google":
            services = ["google_calendar", "gmail", "google_drive"]
            for s in services:
                store = TokenStore(allowed_service=s)
                await store.save_tokens(
                    user_id=user_id,
                    service=s,
                    access_token=access_token,
                    refresh_token=None,
                    scopes=scopes,
                )
            return True
        elif provider == "oauth_microsoft":
            store = TokenStore(allowed_service="microsoft_graph")
            await store.save_tokens(
                user_id=user_id,
                service="microsoft_graph",
                access_token=access_token,
                refresh_token=None,
                scopes=scopes,
            )
            return True

        return False
