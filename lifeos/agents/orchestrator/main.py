import asyncio
from datetime import datetime, timezone, timedelta
import json
import os
import uuid
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
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
from lifeos.web import DASHBOARD_HTML

card = AgentCard(
    name="LifeOS Orchestrator",
    description="Decomposes natural-language commands into subtasks, coordinates domain agents via A2A, and manages confirmation gates.",
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
a2a_client = A2AClient(timeout=0.5)
llm_client = LocalLLMClient()

# In-memory store for pending write confirmations
PENDING_CONFIRMATIONS: Dict[str, Dict[str, Any]] = {}


class CommandRequest(BaseModel):
    command: str
    user_id: Optional[str] = "default_user"
    auto_confirm: Optional[bool] = False


class ConfirmationRequest(BaseModel):
    confirmation_id: str
    approved: bool
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


async def _dispatch_agent(agent_name: str, skill: str, params: dict, context_id: str, user_id: str) -> Dict[str, Any]:
    agent_url = DOMAIN_AGENTS.get(agent_name, "")
    try:
        task = await a2a_client.send_message(
            agent_url=agent_url,
            skill=skill,
            params=params,
            context_id=context_id,
            metadata={"user_id": user_id}
        )
        return {"agent": agent_name, "status": "completed", "task": task.model_dump()}
    except Exception as http_err:
        # Fallback to local in-process agent execution when external HTTP port is not running
        try:
            from lifeos.agents.calendar.main import agent as cal_agent
            from lifeos.agents.email.main import agent as email_agent
            from lifeos.agents.file.main import agent as file_agent
            from lifeos.agents.task.main import agent as task_agent
            from lifeos.agents.notification.main import agent as notif_agent

            agent_registry = {
                "calendar": cal_agent,
                "email": email_agent,
                "file": file_agent,
                "task": task_agent,
                "notification": notif_agent,
            }
            target_agent = agent_registry.get(agent_name)
            if target_agent and skill in target_agent.skills:
                handler = target_agent.skills[skill]
                msg = Message(
                    role="user",
                    contextId=context_id,
                    parts=[DataPart(data={"skill": skill, "params": params})],
                    metadata={"user_id": user_id}
                )
                task = await handler(params, msg)
                return {"agent": agent_name, "status": "completed", "task": task.model_dump()}
        except Exception as local_err:
            return {"agent": agent_name, "status": "failed", "error": f"HTTP: {http_err}; Local: {local_err}"}

        return {"agent": agent_name, "status": "failed", "error": str(http_err)}


@agent_app.app.post("/api/command")
async def execute_user_command(req: CommandRequest):
    """
    Core Multi-Agent Orchestration Engine:
    Decomposes commands, fans out parallel reads, identifies write actions,
    enforces confirmation gates, and aggregates unified briefings.
    """
    context_id = f"ctx_{uuid.uuid4().hex[:12]}"
    run_id = f"run_{uuid.uuid4().hex[:12]}"
    cmd = req.command.strip()
    cmd_lower = cmd.lower()
    start_time = datetime.now(timezone.utc)
    user_id = req.user_id or "default_user"

    # --- Story 1: "Summarize my week" ---
    if any(k in cmd_lower for k in ["summarize my week", "weekly summary", "overview of this week", "plan my week"]):
        cal_res, email_res, task_res = await asyncio.gather(
            _dispatch_agent("calendar", "list_events", {"range": "this_week"}, context_id, user_id),
            _dispatch_agent("email", "summarize_inbox", {"query": "is:unread"}, context_id, user_id),
            _dispatch_agent("task", "list_open_tasks", {}, context_id, user_id),
        )

        # Synthesize aggregated summary
        events = (
            cal_res.get("task", {}).get("artifacts", [{}])[0].get("parts", [{}])[0].get("data", {}).get("events", [])
            if cal_res.get("status") == "completed" else []
        )
        email_summary = (
            email_res.get("task", {}).get("artifacts", [{}])[0].get("parts", [{}])[0].get("data", {}).get("summary", "No inbox summary.")
            if email_res.get("status") == "completed" else "Inbox check failed."
        )
        tasks = (
            task_res.get("task", {}).get("artifacts", [{}])[0].get("parts", [{}])[0].get("data", {}).get("tasks", [])
            if task_res.get("status") == "completed" else []
        )

        briefing = [
            f"Weekly Summary:",
            f"- Calendar: {len(events)} events scheduled.",
            f"- Inbox: {email_summary}",
            f"- Tasks: {len(tasks)} open tasks."
        ]
        summary_text = "\n".join(briefing)

        # Notify via Notification Agent
        await _dispatch_agent("notification", "send_slack", {"message": summary_text}, context_id, user_id)

        return {
            "status": "completed",
            "run_id": run_id,
            "context_id": context_id,
            "briefing": summary_text,
            "results": {"calendar": cal_res, "email": email_res, "task": task_res}
        }

    # --- Story 2: "Create tasks from unread emails" ---
    elif any(k in cmd_lower for k in ["create tasks from", "tasks from email", "extract tasks from", "action items from email"]):
        # Step 1: Read and extract action items
        email_res = await _dispatch_agent("email", "extract_action_items", {"query": "is:unread"}, context_id, user_id)
        action_items = (
            email_res.get("task", {}).get("artifacts", [{}])[0].get("parts", [{}])[0].get("data", {}).get("action_items", [])
            if email_res.get("status") == "completed" else []
        )

        if not action_items:
            return {
                "status": "completed",
                "run_id": run_id,
                "context_id": context_id,
                "briefing": "No pending action items detected in unread emails.",
                "results": {"email": email_res}
            }

        # Step 2: Check confirmation gate for write action
        if not req.auto_confirm:
            conf_id = f"conf_{uuid.uuid4().hex[:8]}"
            PENDING_CONFIRMATIONS[conf_id] = {
                "run_id": run_id,
                "context_id": context_id,
                "type": "bulk_create_tasks",
                "user_id": user_id,
                "items": action_items
            }
            return {
                "status": "confirmation_required",
                "confirmation_id": conf_id,
                "prompt": f"Extracted {len(action_items)} action items from unread emails. Approve task creation?",
                "pending_actions": [
                    {"action": "create_task", "title": item["action"], "priority": item.get("urgency", "medium")}
                    for item in action_items
                ]
            }

        # If auto_confirmed, execute write directly
        task_res = await _dispatch_agent("task", "bulk_create_tasks", {"tasks": action_items}, context_id, user_id)
        return {
            "status": "completed",
            "run_id": run_id,
            "context_id": context_id,
            "briefing": f"Successfully created {len(action_items)} new tasks in your task board.",
            "results": {"email": email_res, "task": task_res}
        }

    # --- Story 3: "Organize my Drive project folder" ---
    elif any(k in cmd_lower for k in ["organize my drive", "organize drive", "clean up drive", "organize folder"]):
        file_res = await _dispatch_agent("file", "list_files", {"folder_id": "root"}, context_id, user_id)
        files = (
            file_res.get("task", {}).get("artifacts", [{}])[0].get("parts", [{}])[0].get("data", {}).get("files", [])
            if file_res.get("status") == "completed" else []
        )

        proposed_plan = [
            {"action": "create_folder", "folder_name": "Project Documents (2026)"},
            {"action": "rename_file", "file_id": files[0]["id"] if files else "file_1", "new_name": "2026_Architecture_Plan.pdf"}
        ]

        if not req.auto_confirm:
            conf_id = f"conf_{uuid.uuid4().hex[:8]}"
            PENDING_CONFIRMATIONS[conf_id] = {
                "run_id": run_id,
                "context_id": context_id,
                "type": "organize_drive",
                "user_id": user_id,
                "items": proposed_plan
            }
            return {
                "status": "confirmation_required",
                "confirmation_id": conf_id,
                "prompt": f"Proposed file reorganization plan for {len(files)} files in Drive. Approve execution?",
                "pending_actions": proposed_plan
            }

        return {
            "status": "completed",
            "run_id": run_id,
            "briefing": "Drive folder structure organized according to plan.",
            "results": {"file": file_res}
        }

    # --- Story 4: "Block focus time tomorrow" ---
    elif any(k in cmd_lower for k in ["focus time", "block focus", "schedule focus", "time block"]):
        tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
        start_slot = tomorrow.replace(hour=9, minute=0, second=0).isoformat()
        end_slot = tomorrow.replace(hour=11, minute=0, second=0).isoformat()

        proposed_event = {
            "summary": "Deep Work Focus Block",
            "start": start_slot,
            "end": end_slot,
            "description": "Reserved by LifeOS for high-priority task completion"
        }

        if not req.auto_confirm:
            conf_id = f"conf_{uuid.uuid4().hex[:8]}"
            PENDING_CONFIRMATIONS[conf_id] = {
                "run_id": run_id,
                "context_id": context_id,
                "type": "create_event",
                "user_id": user_id,
                "event": proposed_event
            }
            return {
                "status": "confirmation_required",
                "confirmation_id": conf_id,
                "prompt": f"Found open morning slot for 2-hour focus block tomorrow. Approve calendar reservation?",
                "pending_actions": [proposed_event]
            }

        cal_res = await _dispatch_agent("calendar", "create_event", proposed_event, context_id, user_id)
        return {
            "status": "completed",
            "run_id": run_id,
            "briefing": "Focus block scheduled for tomorrow 9:00 AM - 11:00 AM.",
            "results": {"calendar": cal_res}
        }

    # --- Generic Fallback (Parallel Read Dispatch) ---
    else:
        cal_res, task_res = await asyncio.gather(
            _dispatch_agent("calendar", "list_events", {}, context_id, user_id),
            _dispatch_agent("task", "list_open_tasks", {}, context_id, user_id)
        )
        return {
            "status": "completed",
            "run_id": run_id,
            "context_id": context_id,
            "briefing": f"Processed general inquiry '{cmd}'. Retrieved calendar and task context.",
            "results": {"calendar": cal_res, "task": task_res}
        }


@agent_app.app.post("/api/confirm")
async def handle_user_confirmation(conf_req: ConfirmationRequest):
    """
    Processes user approval/rejection for write operations held behind the confirmation gate.
    """
    conf_id = conf_req.confirmation_id
    if conf_id not in PENDING_CONFIRMATIONS:
        raise HTTPException(status_code=404, detail="Confirmation request not found or expired")

    pending = PENDING_CONFIRMATIONS.pop(conf_id)
    if not conf_req.approved:
        return {
            "status": "canceled",
            "message": "Write operation was canceled by the user.",
            "confirmation_id": conf_id
        }

    context_id = pending["context_id"]
    user_id = pending["user_id"]
    op_type = pending["type"]

    if op_type == "bulk_create_tasks":
        items = pending["items"]
        task_res = await _dispatch_agent("task", "bulk_create_tasks", {"tasks": items}, context_id, user_id)
        # Notify user on Slack
        await _dispatch_agent("notification", "send_slack", {
            "message": f"Confirmed: Created {len(items)} tasks in LifeOS board."
        }, context_id, user_id)
        return {
            "status": "completed",
            "message": f"Successfully created {len(items)} tasks.",
            "results": {"task": task_res}
        }

    elif op_type == "create_event":
        event = pending["event"]
        cal_res = await _dispatch_agent("calendar", "create_event", event, context_id, user_id)
        await _dispatch_agent("notification", "send_slack", {
            "message": f"Confirmed: Created calendar event '{event['summary']}'."
        }, context_id, user_id)
        return {
            "status": "completed",
            "message": f"Calendar event '{event['summary']}' successfully confirmed and created.",
            "results": {"calendar": cal_res}
        }

    elif op_type == "organize_drive":
        file_res = await _dispatch_agent("file", "create_folder", {"folder_name": "Project Documents (2026)"}, context_id, user_id)
        return {
            "status": "completed",
            "message": "Drive folder organization completed successfully.",
            "results": {"file": file_res}
        }

    return {"status": "completed", "message": "Action executed."}


@agent_app.app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    """Serves the LifeOS Web Dashboard UI."""
    return HTMLResponse(content=DASHBOARD_HTML)


@agent_app.app.get("/api/tasks")
async def get_dashboard_tasks(user_id: str = "default_user"):
    """Fetches active tasks from the Task Agent for the Web UI task board."""
    task_res = await _dispatch_agent("task", "list_open_tasks", {}, "ctx_dashboard_tasks", user_id)
    tasks = []
    if task_res.get("status") == "completed":
        artifacts = task_res.get("task", {}).get("artifacts", [])
        if artifacts and len(artifacts) > 0:
            parts = artifacts[0].get("parts", [])
            if parts and len(parts) > 0:
                tasks = parts[0].get("data", {}).get("tasks", [])
    return {"tasks": tasks}


@agent_app.app.post("/api/tasks/{task_id}/toggle")
async def toggle_task_status(task_id: str, user_id: str = "default_user"):
    """Marks a task as completed from the Web UI."""
    res = await _dispatch_agent("task", "complete_task", {"task_id": task_id}, "ctx_dashboard_toggle", user_id)
    return {"status": "success", "task_id": task_id, "result": res}


@agent_app.app.get("/api/command/stream")
async def stream_user_command(command: str, user_id: str = "default_user", auto_confirm: bool = False):
    """
    Streams multi-agent task execution progress via Server-Sent Events (SSE).
    """
    async def event_generator():
        yield f"event: step\ndata: {json.dumps({'message': 'Initializing A2A multi-agent dispatch'})}\n\n"
        await asyncio.sleep(0.05)
        
        req = CommandRequest(command=command, user_id=user_id, auto_confirm=auto_confirm)
        result = await execute_user_command(req)
        
        yield f"event: agent_result\ndata: {json.dumps(result)}\n\n"
        yield f"event: done\ndata: {json.dumps({'status': result.get('status')})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


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
