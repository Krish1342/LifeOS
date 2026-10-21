from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Literal, Union

from pydantic import BaseModel, Field


class TaskState(str, Enum):
    SUBMITTED = "submitted"
    WORKING = "working"
    INPUT_REQUIRED = "input-required"
    AUTH_REQUIRED = "auth-required"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"
    REJECTED = "rejected"


class TextPart(BaseModel):
    type: Literal["text"] = "text"
    text: str


class FileReference(BaseModel):
    name: str
    uri: str | None = None
    bytes: str | None = None


class FilePart(BaseModel):
    type: Literal["file"] = "file"
    mimeType: str
    file: FileReference


class DataPart(BaseModel):
    type: Literal["data"] = "data"
    data: dict[str, Any]


Part = Union[TextPart, FilePart, DataPart]


class Artifact(BaseModel):
    id: str = Field(default_factory=lambda: f"art_{uuid.uuid4().hex[:12]}")
    name: str | None = None
    description: str | None = None
    parts: list[Part] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Message(BaseModel):
    role: Literal["user", "agent"]
    messageId: str = Field(default_factory=lambda: f"msg_{uuid.uuid4().hex}")
    contextId: str | None = None
    taskId: str | None = None
    parts: list[Part] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaskStatus(BaseModel):
    state: TaskState
    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )
    message: Message | None = None


class Task(BaseModel):
    taskId: str = Field(default_factory=lambda: f"task_{uuid.uuid4().hex}")
    contextId: str | None = None
    status: TaskStatus
    artifacts: list[Artifact] = Field(default_factory=list)
    history: list[Message] = Field(default_factory=list)


# --- JSON-RPC 2.0 Specifications ---

class JsonRpcRequest(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    id: str | int
    method: str
    params: dict[str, Any] = Field(default_factory=dict)


class JsonRpcErrorDetails(BaseModel):
    code: int
    message: str
    data: Any | None = None


class JsonRpcResponse(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    id: str | int
    result: Any | None = None
    error: JsonRpcErrorDetails | None = None


# --- Agent Card Models ---

class AgentSkill(BaseModel):
    id: str
    name: str
    description: str
    tags: list[str] = Field(default_factory=list)
    examples: list[str] = Field(default_factory=list)
    inputModes: list[str] = Field(default_factory=lambda: ["application/json"])
    outputModes: list[str] = Field(default_factory=lambda: ["application/json"])


class SupportedInterface(BaseModel):
    url: str
    protocolBinding: Literal["JSONRPC", "gRPC", "HTTP"] = "JSONRPC"
    protocolVersion: str = "1.0"


class AgentCapabilities(BaseModel):
    streaming: bool = False
    pushNotifications: bool = False
    extendedAgentCard: bool = True
    stateTransitionHistory: bool = True


class AgentCard(BaseModel):
    name: str
    description: str
    version: str = "0.1.0"
    url: str
    provider: dict[str, str] = Field(
        default_factory=lambda: {"organization": "LifeOS"}
    )
    documentationUrl: str | None = None
    supportedInterfaces: list[SupportedInterface]
    capabilities: AgentCapabilities = Field(default_factory=AgentCapabilities)
    defaultInputModes: list[str] = Field(default_factory=lambda: ["application/json"])
    defaultOutputModes: list[str] = Field(default_factory=lambda: ["application/json"])
    skills: list[AgentSkill] = Field(default_factory=list)
    securitySchemes: dict[str, Any] = Field(default_factory=dict)
