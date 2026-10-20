import asyncio
import os
import uuid
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException
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

# Registry of domain agents
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
    user_id: Optional[str] = "user_default"


@agent_app.app.post("/api/command")
async def execute_user_command(req: CommandRequest):
    """
    Main user-facing entrypoint:
    1. Parse intent
    2. Decompose into subtasks
    3. Dispatch A2A subtasks in parallel
    4. Aggregate results
    """
    context_id = f"ctx_{uuid.uuid4().hex[:12]}"
    command_lower = req.command.lower()
    dispatched_tasks: Dict[str, Any] = {}

    # Simple heuristic routing for initial foundation (LLM-augmented in Week 5)
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
        # Default fallback: check calendar and tasks
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
                context_id=context_id
            )
            return agent_name, task
        except Exception as e:
            return agent_name, {"error": str(e)}

    # Parallel A2A dispatch
    results = await asyncio.gather(*[
        call_agent(name, skill, p) for name, skill, p in needed_agents
    ])

    for agent_name, res in results:
        dispatched_tasks[agent_name] = res.model_dump() if hasattr(res, "model_dump") else res

    return {
        "status": "completed",
        "context_id": context_id,
        "command": req.command,
        "agents_contacted": [name for name, _, _ in needed_agents],
        "results": dispatched_tasks
    }


@agent_app.app.get("/api/health/all")
async def health_check_all():
    """Checks reachability and agent cards across all 6 LifeOS agents."""
    health_status = {
        "orchestrator": "healthy",
        "domain_agents": {}
    }
    for name, url in DOMAIN_AGENTS.items():
        try:
            card_info = await a2a_client.get_agent_card(url)
            health_status["domain_agents"][name] = {
                "status": "online",
                "name": card_info.name,
                "version": card_info.version,
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
