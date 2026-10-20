import asyncio
from datetime import datetime, timezone
import os
import uuid
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from lifeos.shared.a2a import (
    A2AAgentApp,
    A2AClient,
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
from lifeos.shared.llm import LocalLLMClient, DataSensitivity
from lifeos.shared.db.mongo import MongoDB
from lifeos.shared.google.auth import GoogleAuthManager

card = AgentCard(
    name="LifeOS Orchestrator",
    description="Decomposes natural-language commands into subtasks and coordinates domain agents.",
    url="http://localhost:8000",
    supportedInterfaces=[
        SupportedInterface(url="http://localhost:8000/a2a/v1", protocolBinding="JSONRPC")
    ],
    skills=[
        AgentSkill(
            id="execute_command",
            name="Execute User Command",
            description="Accepts a natural-language instruction and orchestrates its execution across domain agents.",
            tags=["orchestration", "planning"]
        )
    ]
)

DOMAIN_AGENTS = {
    "calendar": "http://localhost:8001",
    "email": "http://localhost:8002",
    "file": "http://localhost:8003",
    "task": "http://localhost:8004",
    "notification": "http://localhost:8005",
}

agent_app = A2AAgentApp(card)
a2a_client = A2AClient()
llm_client = LocalLLMClient()


class CommandRequest(BaseModel):
    command: str
    user_id: Optional[str] = "default_user"


@agent_app.app.get("/oauth/connect/{service}")
async def connect_oauth_service(service: str, user_id: str = "default_user"):
    """Generates an OAuth authorization redirect URL for Google Calendar, Gmail, or Drive."""
    if service not in ("google_calendar", "gmail", "google_drive"):
        raise HTTPException(status_code=400, detail=f"Unsupported service: {service}")
    auth_mgr = GoogleAuthManager(service_name=service)
    auth_url = auth_mgr.generate_auth_url(user_id=user_id)
    return RedirectResponse(url=auth_url)


@agent_app.app.get("/oauth/callback")
async def oauth_callback(code: str, state: str):
    """Handles OAuth callback and stores encrypted tokens into MongoDB."""
    parts = state.split(":")
    user_id = parts[0] if len(parts) > 0 else "default_user"
    service = parts[1] if len(parts) > 1 else "google_calendar"

    auth_mgr = GoogleAuthManager(service_name=service)
    await auth_mgr.exchange_code_and_save(code=code, user_id=user_id)
    return {
        "status": "success",
        "message": f"Successfully connected and encrypted tokens for {service}."
    }


@agent_app.app.post("/api/command")
async def execute_user_command(req: CommandRequest):
    """
    Main user-facing entrypoint:
    1. Parse intent
    2. Decompose into subtasks
    3. Dispatch A2A subtasks in parallel
    4. Aggregate results and log to MongoDB agent_runs
    """
    context_id = f"ctx_{uuid.uuid4().hex[:12]}"
    run_id = f"run_{uuid.uuid4().hex[:12]}"
    command_lower = req.command.lower()
    start_time = datetime.now(timezone.utc)
    dispatched_tasks: Dict[str, Any] = {}

    needed_agents = []
    if any(k in command_lower for k in ["week", "summarize", "overview", "schedule", "calendar", "event"]):
        needed_agents.append(("calendar", "list_events", {"range": "this_week"}))
    if any(k in command_lower for k in ["week", "summarize", "email", "inbox", "unread"]):
        needed_agents.append(("email", "summarize_inbox", {"query": "is:unread"}))
    if any(k in command_lower for k in ["week", "summarize", "task", "todo", "finish"]):
        needed_agents.append(("task", "list_open_tasks", {}))
    if any(k in command_lower for k in ["drive", "file", "folder", "organize"]):
        needed_agents.append(("file", "list_files", {"folder_id": "root"}))

    if not needed_agents:
        needed_agents = [
            ("calendar", "list_events", {}),
            ("task", "list_open_tasks", {})
        ]

    async def call_agent(agent_name: str, skill: str, params: dict):
        agent_url = DOMAIN_AGENTS[agent_name]
        try:
            task = await a2a_client.send_message(
                agent_url=agent_url,
                skill=skill,
                params=params,
                context_id=context_id,
                metadata={"user_id": req.user_id}
            )
            return agent_name, task
        except Exception as e:
            return agent_name, {"error": str(e)}

    # Dispatch to domain agents concurrently
    results = await asyncio.gather(*[
        call_agent(name, skill, p) for name, skill, p in needed_agents
    ])

    for agent_name, res in results:
        dispatched_tasks[agent_name] = res.model_dump() if hasattr(res, "model_dump") else res

    duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)

    # Persist audit record in MongoDB agent_runs collection
    run_log = {
        "run_id": run_id,
        "user_id": req.user_id,
        "command_text": req.command,
        "agent_name": "orchestrator",
        "a2a_context_id": context_id,
        "status": "completed",
        "agents_contacted": [name for name, _, _ in needed_agents],
        "duration_ms": duration_ms,
        "created_at": start_time,
        "completed_at": datetime.now(timezone.utc)
    }

    try:
        db = MongoDB.get_database()
        await db.agent_runs.insert_one(dict(run_log))
    except Exception:
        pass

    return {
        "status": "completed",
        "run_id": run_id,
        "context_id": context_id,
        "command": req.command,
        "agents_contacted": [name for name, _, _ in needed_agents],
        "duration_ms": duration_ms,
        "results": dispatched_tasks
    }


@agent_app.app.get("/api/health/all")
async def health_check_all():
    health_status = {
        "orchestrator": "healthy",
        "database": "mongodb",
        "domain_agents": {}
    }
    for name, url in DOMAIN_AGENTS.items():
        try:
            card_info = await a2a_client.get_agent_card(url)
            health_status["domain_agents"][name] = {
                "status": "online",
                "name": card_info.name,
                "url": url,
                "skills": [s.id for s in card_info.skills]
            }
        except Exception as e:
            health_status["domain_agents"][name] = {
                "status": "offline",
                "url": url,
                "error": str(e)
            }
    return health_status

app = agent_app.app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
