from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field
import uuid
from datetime import datetime, timezone


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
    uri: Optional[str] = None
    bytes: Optional[str] = None


class FilePart(BaseModel):
    type: Literal["file"] = "file"
    mimeType: str
    file: FileReference


class DataPart(BaseModel):
    type: Literal["data"] = "data"
    data: Dict[str, Any]


Part = Union[TextPart, FilePart, DataPart]


class Artifact(BaseModel):
    id: str = Field(default_factory=lambda: f"art_{uuid.uuid4().hex[:12]}")
    name: Optional[str] = None
    description: Optional[str] = None
    parts: List[Part] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Message(BaseModel):
    role: Literal["user", "agent"]
    messageId: str = Field(default_factory=lambda: f"msg_{uuid.uuid4().hex}")
    contextId: Optional[str] = None
    taskId: Optional[str] = None
    parts: List[Part] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TaskStatus(BaseModel):
    state: TaskState
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    message: Optional[Message] = None


class Task(BaseModel):
    taskId: str = Field(default_factory=lambda: f"task_{uuid.uuid4().hex}")
    contextId: Optional[str] = None
    status: TaskStatus
    artifacts: List[Artifact] = Field(default_factory=list)
    history: List[Message] = Field(default_factory=list)


# --- JSON-RPC 2.0 Specifications ---

class JsonRpcRequest(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    id: Union[str, int]
    method: str
    params: Dict[str, Any] = Field(default_factory=dict)


class JsonRpcErrorDetails(BaseModel):
    code: int
    message: str
    data: Optional[Any] = None


class JsonRpcResponse(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    id: Union[str, int]
    result: Optional[Any] = None
    error: Optional[JsonRpcErrorDetails] = None


# --- Agent Card Models ---

class AgentSkill(BaseModel):
    id: str
    name: str
    description: str
    tags: List[str] = Field(default_factory=list)
    examples: List[str] = Field(default_factory=list)
    inputModes: List[str] = Field(default_factory=lambda: ["application/json"])
    outputModes: List[str] = Field(default_factory=lambda: ["application/json"])


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
    provider: Dict[str, str] = Field(
        default_factory=lambda: {"organization": "LifeOS"}
    )
    documentationUrl: Optional[str] = None
    supportedInterfaces: List[SupportedInterface]
    capabilities: AgentCapabilities = Field(default_factory=AgentCapabilities)
    defaultInputModes: List[str] = Field(default_factory=lambda: ["application/json"])
    defaultOutputModes: List[str] = Field(default_factory=lambda: ["application/json"])
    skills: List[AgentSkill] = Field(default_factory=list)
    securitySchemes: Dict[str, Any] = Field(default_factory=dict)
