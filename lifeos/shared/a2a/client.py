import uuid
from typing import Any

import httpx

from lifeos.shared.a2a.models import (
    AgentCard,
    DataPart,
    JsonRpcRequest,
    JsonRpcResponse,
    Message,
    Task,
)


class A2AClient:
    """
    Client for communicating with domain agents over the Google A2A protocol.
    Sends standard JSON-RPC 2.0 messages and receives structured Tasks and Artifacts.
    """

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout

    async def get_agent_card(self, agent_url: str) -> AgentCard:
        """Fetch the public Agent Card metadata from /.well-known/agent-card.json."""
        url = f"{agent_url.rstrip('/')}/.well-known/agent-card.json"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return AgentCard.model_validate(resp.json())

    async def send_message(
        self,
        agent_url: str,
        skill: str,
        params: dict[str, Any],
        context_id: str | None = None,
        metadata: dict[str, Any] | None = None
    ) -> Task:
        """
        Sends an A2A SendMessage RPC to dispatch a subtask to a domain agent.
        """
        url = f"{agent_url.rstrip('/')}/a2a/v1"
        message = Message(
            role="user",
            messageId=f"msg_{uuid.uuid4().hex}",
            contextId=context_id,
            parts=[
                DataPart(
                    data={
                        "skill": skill,
                        "params": params
                    }
                )
            ],
            metadata=metadata or {}
        )

        req_id = f"rpc_{uuid.uuid4().hex[:8]}"
        rpc_request = JsonRpcRequest(
            id=req_id,
            method="SendMessage",
            params={"message": message.model_dump(exclude_none=True)}
        )

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, json=rpc_request.model_dump())
            resp.raise_for_status()
            rpc_resp = JsonRpcResponse.model_validate(resp.json())

            if rpc_resp.error:
                raise RuntimeError(
                    f"A2A Error from {agent_url} [code {rpc_resp.error.code}]: {rpc_resp.error.message} - {rpc_resp.error.data}"
                )

            return Task.model_validate(rpc_resp.result)

    async def get_task(self, agent_url: str, task_id: str) -> Task:
        """Polls task state by ID from a domain agent."""
        url = f"{agent_url.rstrip('/')}/a2a/v1"
        req_id = f"rpc_{uuid.uuid4().hex[:8]}"
        rpc_request = JsonRpcRequest(
            id=req_id,
            method="GetTask",
            params={"taskId": task_id}
        )
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, json=rpc_request.model_dump())
            resp.raise_for_status()
            rpc_resp = JsonRpcResponse.model_validate(resp.json())
            if rpc_resp.error:
                raise RuntimeError(f"A2A GetTask Error: {rpc_resp.error.message}")
            return Task.model_validate(rpc_resp.result)
