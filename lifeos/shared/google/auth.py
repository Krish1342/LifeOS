import os
from typing import Dict, List, Optional
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from lifeos.shared.db.tokens import TokenStore

SCOPES_BY_SERVICE: Dict[str, List[str]] = {
    "google_calendar": [
        "https://www.googleapis.com/auth/calendar.readonly",
        "https://www.googleapis.com/auth/calendar.events"
    ],
    "gmail": [
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.send",
        "https://www.googleapis.com/auth/gmail.compose"
    ],
    "google_drive": [
        "https://www.googleapis.com/auth/drive.metadata.readonly",
        "https://www.googleapis.com/auth/drive.file"
    ]
}


class GoogleAuthManager:
    """Manages OAuth2 flows and builds authenticated Credentials objects for Google APIs."""

    def __init__(self, service_name: str):
        self.service_name = service_name
        self.client_id = os.getenv("GOOGLE_CLIENT_ID", "")
        self.client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "")
        self.redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/oauth/callback")
        self.token_store = TokenStore(allowed_service=service_name)

    def get_client_config(self) -> dict:
        return {
            "web": {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [self.redirect_uri]
            }
        }

    def generate_auth_url(self, user_id: str = "default_user") -> str:
        """Generates an OAuth authorization URL with incremental scoping."""
        scopes = SCOPES_BY_SERVICE.get(self.service_name, [])
        client_config = self.get_client_config()
        flow = Flow.from_client_config(
            client_config,
            scopes=scopes,
            redirect_uri=self.redirect_uri
        )
        auth_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
            state=f"{user_id}:{self.service_name}"
        )
        return auth_url

    async def exchange_code_and_save(self, code: str, user_id: str = "default_user") -> Credentials:
        """Exchanges an authorization code for tokens and saves them encrypted into MongoDB."""
        scopes = SCOPES_BY_SERVICE.get(self.service_name, [])
        client_config = self.get_client_config()
        flow = Flow.from_client_config(
            client_config,
            scopes=scopes,
            redirect_uri=self.redirect_uri
        )
        flow.fetch_token(code=code)
        credentials = flow.credentials

        await self.token_store.save_tokens(
            user_id=user_id,
            service=self.service_name,
            access_token=credentials.token,
            refresh_token=credentials.refresh_token,
            scopes=credentials.scopes or scopes,
            expires_at=credentials.expiry
        )
        return credentials

    async def get_credentials(self, user_id: str = "default_user") -> Optional[Credentials]:
        """Loads credentials from MongoDB and prepares a Google Credentials object."""
        token_data = await self.token_store.get_credentials(user_id, self.service_name)
        if not token_data or not token_data.get("access_token"):
            return None

        creds = Credentials(
            token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=self.client_id,
            client_secret=self.client_secret,
            scopes=token_data.get("scopes", SCOPES_BY_SERVICE.get(self.service_name, []))
        )
        return creds
