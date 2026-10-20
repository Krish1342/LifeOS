from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from lifeos.shared.crypto.encryption import TokenEncryption
from lifeos.shared.db.mongo import MongoDB
from lifeos.shared.http.client import SecurityError


class TokenStore:
    """
    Manages OAuth2 access and refresh tokens stored encrypted in MongoDB.
    Enforces per-agent scoping: agents can only read tokens for their declared service.
    """

    def __init__(self, allowed_service: Optional[str] = None):
        self.allowed_service = allowed_service
        self.crypto = TokenEncryption()
        self._memory_tokens: Dict[str, Dict[str, Any]] = {}

    def _verify_service(self, service: str) -> None:
        if self.allowed_service and self.allowed_service != service:
            raise SecurityError(
                f"Scope Violation: Agent restricted to service '{self.allowed_service}' attempted to access tokens for '{service}'"
            )

    async def save_tokens(
        self,
        user_id: str,
        service: str,
        access_token: str,
        refresh_token: Optional[str],
        scopes: List[str],
        expires_at: Optional[datetime] = None
    ) -> None:
        """Encrypts tokens and stores or updates them in the oauth_tokens collection."""
        self._verify_service(service)
        encrypted_access = self.crypto.encrypt(access_token)
        encrypted_refresh = self.crypto.encrypt(refresh_token) if refresh_token else None

        doc = {
            "user_id": user_id,
            "service": service,
            "access_token": encrypted_access,
            "refresh_token": encrypted_refresh,
            "token_type": "Bearer",
            "scopes": scopes,
            "expires_at": expires_at or datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }

        try:
            db = MongoDB.get_database()
            await db.oauth_tokens.update_one(
                {"user_id": user_id, "service": service},
                {
                    "$set": doc,
                    "$setOnInsert": {"created_at": datetime.now(timezone.utc)}
                },
                upsert=True
            )
        except Exception:
            self._memory_tokens[f"{user_id}:{service}"] = doc

    async def get_credentials(self, user_id: str, service: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves and decrypts credentials for a given user and service.
        Returns a dict with plaintext access_token and refresh_token.
        """
        self._verify_service(service)
        token_doc = None

        try:
            db = MongoDB.get_database()
            token_doc = await db.oauth_tokens.find_one({"user_id": user_id, "service": service})
        except Exception:
            token_doc = self._memory_tokens.get(f"{user_id}:{service}")

        if not token_doc:
            return None

        access_token = self.crypto.decrypt(token_doc["access_token"])
        refresh_token = (
            self.crypto.decrypt(token_doc["refresh_token"])
            if token_doc.get("refresh_token")
            else None
        )

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "scopes": token_doc.get("scopes", []),
            "expires_at": token_doc.get("expires_at"),
            "token_type": token_doc.get("token_type", "Bearer")
        }
