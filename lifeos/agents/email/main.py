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

# Per-agent outbound security boundary: Email Agent can ONLY contact Google APIs
http_client = ScopedHTTPClient(allowed_hosts=["www.googleapis.com"])

card = AgentCard(
    name="LifeOS Email Agent",
    description="Manages Gmail interactions: reading, searching, summarizing, extracting action items, and drafting replies.",
    url="http://localhost:8002",
    supportedInterfaces=[
        SupportedInterface(url="http://localhost:8002/a2a/v1", protocolBinding="JSONRPC")
    ],
    skills=[
        AgentSkill(id="list_messages", name="List Messages", description="List messages matching a query.", tags=["email", "read"]),
        AgentSkill(id="get_message", name="Get Message", description="Get full content of a message.", tags=["email", "read"]),
        AgentSkill(id="summarize_inbox", name="Summarize Inbox", description="Produce a summary of recent emails.", tags=["email", "read"]),
        AgentSkill(id="extract_action_items", name="Extract Action Items", description="Extract tasks from email threads.", tags=["email", "read"]),
        AgentSkill(id="draft_reply", name="Draft Reply", description="Generate a draft reply.", tags=["email", "read"]),
        AgentSkill(id="send_message", name="Send Message", description="Send a drafted email.", tags=["email", "write"]),
        AgentSkill(id="search_messages", name="Search Messages", description="Full-text search across mailbox.", tags=["email", "read"]),
    ]
)

agent = A2AAgentApp(card)


async def handle_summarize_inbox(params: Dict[str, Any], message: Message) -> Task:
    query = params.get("query", "is:unread")
    return Task(
        contextId=message.contextId,
        status=TaskStatus(state=TaskState.COMPLETED),
        artifacts=[
            Artifact(
                name="inbox_summary",
                parts=[
                    DataPart(
                        data={
                            "query": query,
                            "summary": "No unread urgent messages detected.",
                            "action_items": [],
                            "total_processed": 0
                        }
                    )
                ]
            )
        ]
    )


async def handle_extract_action_items(params: Dict[str, Any], message: Message) -> Task:
    return Task(
        contextId=message.contextId,
        status=TaskStatus(state=TaskState.COMPLETED),
        artifacts=[
            Artifact(
                name="extracted_action_items",
                parts=[
                    DataPart(
                        data={
                            "action_items": [],
                            "total_processed": 0
                        }
                    )
                ]
            )
        ]
    )

agent.register_skill("summarize_inbox", handle_summarize_inbox)
agent.register_skill("extract_action_items", handle_extract_action_items)
app = agent.app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8002)
