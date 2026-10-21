from typing import Any

from lifeos.shared.db.tokens import TokenStore
from lifeos.shared.http.client import ScopedHTTPClient

M365_SCOPES = [
    "https://graph.microsoft.com/Calendars.ReadWrite",
    "https://graph.microsoft.com/Mail.ReadWrite",
    "https://graph.microsoft.com/Mail.Send"
]


class M365Connector:
    """
    Microsoft 365 (Graph API) connector for Outlook Calendar and Mail.
    Enforces per-agent outbound sandboxing to graph.microsoft.com.
    """

    def __init__(self, user_id: str = "default_user"):
        self.user_id = user_id
        self.token_store = TokenStore(allowed_service="m365_outlook")
        self.http_client = ScopedHTTPClient(allowed_hosts=["graph.microsoft.com", "login.microsoftonline.com"])

    async def list_calendar_events(self, start_date: str | None = None, end_date: str | None = None) -> list[dict[str, Any]]:
        """Queries calendar events from Outlook."""
        creds = await self.token_store.get_credentials(self.user_id, "m365_outlook")
        if not creds:
            # Fallback mock when unauthenticated
            return [
                {
                    "id": "m365_evt_001",
                    "subject": "Sprint Planning (Outlook)",
                    "start": "2026-10-22T09:00:00Z",
                    "end": "2026-10-22T10:00:00Z",
                    "provider": "microsoft_365",
                    "is_mock": True
                }
            ]

        headers = {"Authorization": f"Bearer {creds['access_token']}"}
        url = "https://graph.microsoft.com/v1.0/me/calendar/events?$select=id,subject,start,end,location"
        resp = await self.http_client.get(url, headers=headers)
        resp.raise_for_status()
        items = resp.json().get("value", [])
        return [
            {
                "id": item.get("id"),
                "subject": item.get("subject"),
                "start": item.get("start", {}).get("dateTime"),
                "end": item.get("end", {}).get("dateTime"),
                "provider": "microsoft_365"
            }
            for item in items
        ]

    async def list_messages(self, max_results: int = 10) -> list[dict[str, Any]]:
        """Queries messages from Outlook inbox."""
        creds = await self.token_store.get_credentials(self.user_id, "m365_outlook")
        if not creds:
            return [
                {
                    "id": "m365_msg_001",
                    "subject": "Project update from client",
                    "sender": "client@enterprise.com",
                    "snippet": "Attached is the signed agreement.",
                    "provider": "microsoft_365",
                    "is_mock": True
                }
            ]

        headers = {"Authorization": f"Bearer {creds['access_token']}"}
        url = f"https://graph.microsoft.com/v1.0/me/messages?$top={max_results}&$select=id,subject,from,receivedDateTime,bodyPreview"
        resp = await self.http_client.get(url, headers=headers)
        resp.raise_for_status()
        items = resp.json().get("value", [])
        return [
            {
                "id": item.get("id"),
                "subject": item.get("subject"),
                "sender": item.get("from", {}).get("emailAddress", {}).get("address"),
                "snippet": item.get("bodyPreview"),
                "provider": "microsoft_365"
            }
            for item in items
        ]
