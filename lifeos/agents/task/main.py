import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List
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
from lifeos.shared.db.mongo import MongoDB

card = AgentCard(
    name="LifeOS Task Agent",
    description="Manages the internal task board in MongoDB: creating, updating, prioritizing, and completing tasks.",
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

# In-memory storage cache as fallback when MongoDB cluster is offline
_in_memory_tasks: List[Dict[str, Any]] = [
    {
        "task_id": "task_demo_001",
        "title": "Review Q4 budget proposal",
        "description": "Extracted from Sarah's email",
        "status": "open",
        "priority": "high",
        "due_date": "2026-10-24",
        "source": "email:msg_mock_001",
        "created_at": "2026-10-20T12:00:00Z"
    }
]


async def handle_create_task(params: Dict[str, Any], message: Message) -> Task:
    task_id = f"task_{uuid.uuid4().hex[:10]}"
    user_id = message.metadata.get("user_id", "default_user") if message.metadata else "default_user"
    new_task = {
        "task_id": task_id,
        "user_id": user_id,
        "title": params.get("title", "Untitled Task"),
        "description": params.get("description", ""),
        "status": params.get("status", "open"),
        "priority": params.get("priority", "medium"),
        "due_date": params.get("due_date"),
        "source": params.get("source", "manual"),
        "source_ref": params.get("source_ref"),
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    try:
        db = MongoDB.get_database()
        await db.tasks.insert_one(dict(new_task))
    except Exception:
        _in_memory_tasks.append(new_task)

    return Task(
        contextId=message.contextId,
        status=TaskStatus(state=TaskState.COMPLETED),
        artifacts=[
            Artifact(
                name="task_created",
                parts=[DataPart(data={"task": new_task})]
            )
        ]
    )


async def handle_list_open_tasks(params: Dict[str, Any], message: Message) -> Task:
    user_id = message.metadata.get("user_id", "default_user") if message.metadata else "default_user"
    tasks = []

    try:
        db = MongoDB.get_database()
        cursor = db.tasks.find({"user_id": user_id, "status": {"$ne": "completed"}}, {"_id": 0})
        tasks = await cursor.to_list(length=100)
    except Exception:
        tasks = [t for t in _in_memory_tasks if t.get("status") != "completed"]

    return Task(
        contextId=message.contextId,
        status=TaskStatus(state=TaskState.COMPLETED),
        artifacts=[
            Artifact(
                name="open_tasks",
                parts=[
                    DataPart(
                        data={
                            "tasks": tasks,
                            "total_open": len(tasks)
                        }
                    )
                ]
            )
        ]
    )


async def handle_complete_task(params: Dict[str, Any], message: Message) -> Task:
    task_id = params.get("task_id")
    updated = False

    try:
        db = MongoDB.get_database()
        res = await db.tasks.update_one(
            {"task_id": task_id},
            {"$set": {"status": "completed", "completed_at": datetime.now(timezone.utc).isoformat()}}
        )
        updated = res.modified_count > 0
    except Exception:
        for t in _in_memory_tasks:
            if t["task_id"] == task_id:
                t["status"] = "completed"
                updated = True
                break

    return Task(
        contextId=message.contextId,
        status=TaskStatus(state=TaskState.COMPLETED),
        artifacts=[
            Artifact(
                name="task_completed",
                parts=[DataPart(data={"task_id": task_id, "success": updated})]
            )
        ]
    )

agent.register_skill("create_task", handle_create_task)
agent.register_skill("list_open_tasks", handle_list_open_tasks)
agent.register_skill("complete_task", handle_complete_task)
app = agent.app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8004)
