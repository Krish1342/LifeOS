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

# Per-agent outbound security boundary: Task Agent can ONLY contact Supabase
http_client = ScopedHTTPClient(allowed_hosts=["*.supabase.co"])

card = AgentCard(
    name="LifeOS Task Agent",
    description="Manages the internal task board: creating, updating, prioritizing, and completing tasks.",
    url="http://localhost:8004",
    supportedInterfaces=[
        SupportedInterface(url="http://localhost:8004/a2a/v1", protocolBinding="JSONRPC")
    ],
    skills=[
        AgentSkill(id="create_task", name="Create Task", description="Create a new task.", tags=["task", "write"]),
        AgentSkill(id="update_task", name="Update Task", description="Update task fields.", tags=["task", "write"]),
        AgentSkill(id="complete_task", name="Complete Task", description="Mark a task as completed.", tags=["task", "write"]),
        AgentSkill(id="list_open_tasks", name="List Open Tasks", description="List incomplete tasks.", tags=["task", "read"]),
        AgentSkill(id="prioritize_tasks", name="Prioritize Tasks", description="Re-rank tasks.", tags=["task", "write"]),
        AgentSkill(id="link_to_event", name="Link to Event", description="Associate task with a calendar event.", tags=["task", "write"]),
        AgentSkill(id="get_task", name="Get Task", description="Get task details.", tags=["task", "read"]),
        AgentSkill(id="bulk_create_tasks", name="Bulk Create Tasks", description="Create multiple tasks at once.", tags=["task", "write"]),
    ]
)

agent = A2AAgentApp(card)


async def handle_list_open_tasks(params: Dict[str, Any], message: Message) -> Task:
    return Task(
        contextId=message.contextId,
        status=TaskStatus(state=TaskState.COMPLETED),
        artifacts=[
            Artifact(
                name="open_tasks",
                parts=[
                    DataPart(
                        data={
                            "tasks": [],
                            "total_open": 0
                        }
                    )
                ]
            )
        ]
    )

agent.register_skill("list_open_tasks", handle_list_open_tasks)
app = agent.app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8004)
