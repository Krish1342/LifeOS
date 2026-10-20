import os
from typing import Any, Dict, List, Optional
from slack_sdk.web.async_client import AsyncWebClient


class SlackConnector:
    """Manages Slack API interactions for delivering notifications and alerts."""

    def __init__(self, token: Optional[str] = None):
        self.token = token or os.getenv("SLACK_BOT_TOKEN", "")
        self.default_channel = os.getenv("SLACK_DEFAULT_CHANNEL", "#lifeos-updates")
        self._client: Optional[AsyncWebClient] = None

    def _get_client(self) -> Optional[AsyncWebClient]:
        if not self.token or self.token.startswith("xoxb-your"):
            return None
        if self._client is None:
            self._client = AsyncWebClient(token=self.token)
        return self._client

    async def post_message(
        self,
        text: str,
        channel: Optional[str] = None,
        blocks: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Posts a message to a Slack channel or DM."""
        target_channel = channel or self.default_channel
        client = self._get_client()

        if not client:
            # Fallback mock when no live Slack bot token is configured
            return {
                "ok": True,
                "channel": target_channel,
                "ts": "1729450200.001234",
                "message": {"text": text},
                "is_mock": True
            }

        response = await client.chat_postMessage(
            channel=target_channel,
            text=text,
            blocks=blocks
        )
        return {
            "ok": response["ok"],
            "channel": response["channel"],
            "ts": response["ts"],
            "is_mock": False
        }
