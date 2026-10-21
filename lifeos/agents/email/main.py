from typing import Any

from lifeos.shared.a2a import (
    A2AAgentApp,
    AgentCard,
    AgentSkill,
    Artifact,
    DataPart,
    Message,
    SupportedInterface,
    Task,
    TaskState,
    TaskStatus,
)
from lifeos.shared.google.gmail import GmailConnector
from lifeos.shared.http import ScopedHTTPClient
from lifeos.shared.llm import DataSensitivity, LocalLLMClient

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
connector = GmailConnector()
llm = LocalLLMClient()


async def handle_summarize_inbox(params: dict[str, Any], message: Message) -> Task:
    query = params.get("query", "is:unread")
    messages = await connector.list_messages(query=query)

    summary_text = "No unread messages found."
    if messages:
        # Prepare email snippets for local LLM summarization
        email_content = "\n".join([
            f"- From: {m['sender']} | Subject: {m['subject']} | Snippet: {m['snippet']}"
            for m in messages
        ])
        prompt = (
            "Summarize the following inbox emails concisely in 2-3 bullet points, highlighting any urgent items:\n"
            f"{email_content}"
        )
        try:
            llm_result = await llm.generate(
                prompt=prompt,
                sensitivity=DataSensitivity.PRIVATE
            )
            summary_text = llm_result["text"]
        except Exception:
            # Fallback heuristic summary if local LLM is temporarily offline
            summary_text = f"Found {len(messages)} unread messages. Highlights: " + "; ".join(
                [f"'{m['subject']}' from {m['sender']}" for m in messages[:3]]
            )

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
                            "summary": summary_text,
                            "total_processed": len(messages),
                            "messages": messages
                        }
                    )
                ]
            )
        ]
    )


async def handle_extract_action_items(params: dict[str, Any], message: Message) -> Task:
    query = params.get("query", "is:unread")
    messages = await connector.list_messages(query=query)
    action_items = []

    for m in messages:
        snippet_lower = m.get("snippet", "").lower() + " " + m.get("subject", "").lower()
        if any(w in snippet_lower for w in ["action", "review", "confirm", "approve", "deadline", "by friday"]):
            action_items.append({
                "source_message_id": m.get("id"),
                "subject": m.get("subject"),
                "sender": m.get("sender"),
                "action": f"Review and respond to {m.get('subject')}",
                "urgency": "high" if "urgent" in snippet_lower or "confirm" in snippet_lower else "medium"
            })

    return Task(
        contextId=message.contextId,
        status=TaskStatus(state=TaskState.COMPLETED),
        artifacts=[
            Artifact(
                name="extracted_action_items",
                parts=[
                    DataPart(
                        data={
                            "action_items": action_items,
                            "total_processed": len(messages)
                        }
                    )
                ]
            )
        ]
    )


async def handle_draft_reply(params: dict[str, Any], message: Message) -> Task:
    to = params.get("to")
    subject = params.get("subject", "Re: Follow up")
    body = params.get("body", "Thank you for the update. I have reviewed this and will proceed.")
    draft = await connector.draft_reply(to=to, subject=subject, body=body)

    return Task(
        contextId=message.contextId,
        status=TaskStatus(state=TaskState.COMPLETED),
        artifacts=[
            Artifact(
                name="draft_reply",
                parts=[DataPart(data={"draft": draft})]
            )
        ]
    )

agent.register_skill("summarize_inbox", handle_summarize_inbox)
agent.register_skill("extract_action_items", handle_extract_action_items)
agent.register_skill("draft_reply", handle_draft_reply)
app = agent.app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8002)
