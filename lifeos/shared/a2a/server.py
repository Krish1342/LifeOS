import logging
from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import FastAPI

from lifeos.shared.a2a.models import (
    AgentCard,
    JsonRpcErrorDetails,
    JsonRpcRequest,
    JsonRpcResponse,
    Message,
    Task,
    TaskState,
)

logger = logging.getLogger("a2a.server")

SkillHandler = Callable[[dict[str, Any], Message], Coroutine[Any, Any, Task]]


class A2AAgentApp:
    """
    Standardized FastAPI server implementation for an A2A Agent.
    Implements Agent Card discovery, JSON-RPC 2.0 routing, and task lifecycle management.
    """

    def __init__(self, agent_card: AgentCard):
        self.agent_card = agent_card
        self.app = FastAPI(
            title=agent_card.name,
            description=agent_card.description,
            version=agent_card.version,
        )
        self.skills: dict[str, SkillHandler] = {}
        self.tasks: dict[str, Task] = {}

        self._register_routes()

    def register_skill(self, skill_id: str, handler: SkillHandler) -> None:
        """Register a coroutine handler for a specific skill."""
        self.skills[skill_id] = handler

    def _register_routes(self) -> None:
        @self.app.get("/.well-known/agent-card.json")
        async def get_agent_card():
            return self.agent_card.model_dump(exclude_none=True)

        @self.app.get("/health")
        async def health():
            return {
                "status": "healthy",
                "agent": self.agent_card.name,
                "version": self.agent_card.version,
                "skills_registered": list(self.skills.keys())
            }

        @self.app.post("/a2a/v1", response_model=JsonRpcResponse)
        async def handle_rpc(request: JsonRpcRequest):
            req_id = request.id
            method = request.method

            try:
                if method == "SendMessage":
                    return await self._handle_send_message(req_id, request.params)
                elif method == "GetTask":
                    return self._handle_get_task(req_id, request.params)
                elif method == "CancelTask":
                    return self._handle_cancel_task(req_id, request.params)
                else:
                    return JsonRpcResponse(
                        id=req_id,
                        error=JsonRpcErrorDetails(
                            code=-32601,
                            message=f"Method '{method}' not found"
                        )
                    )
            except Exception as e:
                logger.exception("Error executing RPC method %s", method)
                return JsonRpcResponse(
                    id=req_id,
                    error=JsonRpcErrorDetails(
                        code=-32603,
                        message="Internal error",
                        data={"detail": str(e)}
                    )
                )

    async def _handle_send_message(self, req_id: Any, params: dict[str, Any]) -> JsonRpcResponse:
        message_data = params.get("message", {})
        if not message_data:
            return JsonRpcResponse(
                id=req_id,
                error=JsonRpcErrorDetails(
                    code=-32602,
                    message="Missing required parameter 'message'"
                )
            )

        message = Message.model_validate(message_data)
        
        # Extract skill and parameters from message parts
        skill_id = None
        skill_params = {}
        for part in message.parts:
            if part.type == "data" and "skill" in part.data:
                skill_id = part.data["skill"]
                skill_params = part.data.get("params", {})
                break

        if not skill_id:
            return JsonRpcResponse(
                id=req_id,
                error=JsonRpcErrorDetails(
                    code=-32602,
                    message="No skill identifier provided in message parts"
                )
            )

        handler = self.skills.get(skill_id)
        if not handler:
            return JsonRpcResponse(
                id=req_id,
                error=JsonRpcErrorDetails(
                    code=-32602,
                    message=f"Skill '{skill_id}' not supported by this agent",
                    data={"supported_skills": list(self.skills.keys())}
                )
            )

        # Execute registered skill handler
        task_result: Task = await handler(skill_params, message)
        self.tasks[task_result.taskId] = task_result

        return JsonRpcResponse(
            id=req_id,
            result=task_result.model_dump(exclude_none=True)
        )

    def _handle_get_task(self, req_id: Any, params: dict[str, Any]) -> JsonRpcResponse:
        task_id = params.get("taskId")
        if not task_id or task_id not in self.tasks:
            return JsonRpcResponse(
                id=req_id,
                error=JsonRpcErrorDetails(
                    code=-32001,
                    message="Task not found",
                    data={"taskId": task_id}
                )
            )
        return JsonRpcResponse(
            id=req_id,
            result=self.tasks[task_id].model_dump(exclude_none=True)
        )

    def _handle_cancel_task(self, req_id: Any, params: dict[str, Any]) -> JsonRpcResponse:
        task_id = params.get("taskId")
        if not task_id or task_id not in self.tasks:
            return JsonRpcResponse(
                id=req_id,
                error=JsonRpcErrorDetails(
                    code=-32001,
                    message="Task not found",
                    data={"taskId": task_id}
                )
            )
        task = self.tasks[task_id]
        if task.status.state in (TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELED):
            return JsonRpcResponse(
                id=req_id,
                error=JsonRpcErrorDetails(
                    code=-32002,
                    message="Task is in a terminal state and cannot be canceled",
                    data={"state": task.status.state}
                )
            )
        task.status.state = TaskState.CANCELED
        return JsonRpcResponse(
            id=req_id,
            result=task.model_dump(exclude_none=True)
        )
