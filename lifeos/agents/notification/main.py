from typing import Any, Dict
from lifeos.shared.a2a import (
    A2AAgentApp,
    AgentCard,
    AgentSkill,
    SupportedInterface,
    Task,
    TaskState,
    TaskStatus,
    Artifact,
    DataPart,
    Message,
)
from lifeos.shared.http import ScopedHTTPClient

# Per-agent outbound security boundary: Notification Agent can ONLY contact Slack API
http_client = ScopedHTTPClient(allowed_hosts=["slack.com"])

card = AgentCard(
    name="LifeOS Notification Agent",
    description="Delivers formatted messages and alerts to Slack channels and DMs.",
    url="http://localhost:8005",
    supportedInterfaces=[
        SupportedInterface(url="http://localhost:8005/a2a/v1", protocolBinding="JSONRPC")
    ],
    skills=[
        AgentSkill(id="send_slack", name="Send Slack Message", description="Post a message to a Slack channel.", tags=["notification", "write"]),
        AgentSkill(id="send_dm", name="Send DM", description="Send a Slack direct message.", tags=["notification", "write"]),
        AgentSkill(id="update_message", name="Update Message", description="Update a previously sent Slack message.", tags=["notification", "write"]),
        AgentSkill(id="send_confirmation_request", name="Send Confirmation", description="Send an interactive confirmation prompt.", tags=["notification", "write"]),
    ]
)

agent = A2AAgentApp(card)


async def handle_send_slack(params: Dict[str, Any], message: Message) -> Task:
    channel = params.get("channel", "#lifeos-updates")
    text = params.get("message", "")
    return Task(
        contextId=message.contextId,
        status=TaskStatus(state=TaskState.COMPLETED),
        artifacts=[
            Artifact(
                name="slack_delivery_receipt",
                parts=[
                    DataPart(
                        data={
                            "delivered": True,
                            "channel": channel,
                            "text_preview": text[:60] + ("..." if len(text) > 60 else ""),
                            "mock": True
                        }
                    )
                ]
            )
        ]
    )

agent.register_skill("send_slack", handle_send_slack)
app = agent.app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8005)
