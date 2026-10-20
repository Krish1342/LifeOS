import base64
from email.message import EmailMessage
from typing import Any, Dict, List, Optional
from googleapiclient.discovery import build
from lifeos.shared.google.auth import GoogleAuthManager


class GmailConnector:
    """Connector for Gmail API with mock fallback when unauthenticated."""

    def __init__(self, user_id: str = "default_user"):
        self.user_id = user_id
        self.auth_manager = GoogleAuthManager(service_name="gmail")

    async def _get_service(self):
        creds = await self.auth_manager.get_credentials(self.user_id)
        if not creds:
            return None
        return build("gmail", "v1", credentials=creds, cache_discovery=False)

    async def list_messages(self, query: str = "is:unread", max_results: int = 10) -> List[Dict[str, Any]]:
        service = await self._get_service()
        if not service:
            return [
                {
                    "id": "msg_mock_001",
                    "thread_id": "thread_mock_001",
                    "subject": "Review requested: Q4 product roadmap & budget doc",
                    "sender": "sarah.lead@company.com",
                    "snippet": "Hi team, please review the Q4 budget figures by Friday end of day.",
                    "date": "2026-10-20T10:30:00Z",
                    "is_mock": True
                },
                {
                    "id": "msg_mock_002",
                    "thread_id": "thread_mock_002",
                    "subject": "Contract Renewal confirmation needed",
                    "sender": "vendor.billing@saas.com",
                    "snippet": "Action required: Confirm renewal terms before Oct 25 to avoid service interruption.",
                    "date": "2026-10-20T14:15:00Z",
                    "is_mock": True
                }
            ]

        results = service.users().messages().list(
            userId="me",
            q=query,
            maxResults=max_results
        ).execute()

        messages = results.get("messages", [])
        detailed_list = []
        for m in messages:
            msg_data = service.users().messages().get(
                userId="me",
                id=m["id"],
                format="metadata",
                metadataHeaders=["Subject", "From", "Date"]
            ).execute()

            headers = {
                h["name"]: h["value"]
                for h in msg_data.get("payload", {}).get("headers", [])
            }
            detailed_list.append({
                "id": m["id"],
                "thread_id": m.get("threadId"),
                "subject": headers.get("Subject", "(No Subject)"),
                "sender": headers.get("From", "Unknown"),
                "date": headers.get("Date", ""),
                "snippet": msg_data.get("snippet", "")
            })
        return detailed_list

    async def draft_reply(
        self,
        to: str,
        subject: str,
        body: str,
        thread_id: Optional[str] = None
    ) -> Dict[str, Any]:
        service = await self._get_service()
        if not service:
            return {
                "id": f"draft_mock_{to}",
                "to": to,
                "subject": subject,
                "body": body,
                "is_mock": True
            }

        msg = EmailMessage()
        msg.set_content(body)
        msg["To"] = to
        msg["Subject"] = subject
        encoded = base64.urlsafe_b64encode(msg.as_bytes()).decode()

        draft_body = {"message": {"raw": encoded}}
        if thread_id:
            draft_body["message"]["threadId"] = thread_id

        draft = service.users().drafts().create(userId="me", body=draft_body).execute()
        return {
            "id": draft.get("id"),
            "to": to,
            "subject": subject
        }

    async def send_message(
        self,
        to: str,
        subject: str,
        body: str,
        thread_id: Optional[str] = None
    ) -> Dict[str, Any]:
        service = await self._get_service()
        if not service:
            return {
                "id": "msg_mock_sent",
                "to": to,
                "subject": subject,
                "status": "delivered_mock",
                "is_mock": True
            }

        msg = EmailMessage()
        msg.set_content(body)
        msg["To"] = to
        msg["Subject"] = subject
        encoded = base64.urlsafe_b64encode(msg.as_bytes()).decode()

        send_body = {"raw": encoded}
        if thread_id:
            send_body["threadId"] = thread_id

        sent = service.users().messages().send(userId="me", body=send_body).execute()
        return {
            "id": sent.get("id"),
            "threadId": sent.get("threadId"),
            "status": "sent"
        }
