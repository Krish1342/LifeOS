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
from lifeos.shared.google.drive import DriveConnector
from lifeos.shared.http import ScopedHTTPClient

# Per-agent outbound security boundary: File Agent can ONLY contact Google Drive APIs
http_client = ScopedHTTPClient(allowed_hosts=["www.googleapis.com"])

card = AgentCard(
    name="LifeOS File Agent",
    description="Manages Google Drive files: listing, searching, moving, renaming, and organizing.",
    url="http://localhost:8003",
    supportedInterfaces=[
        SupportedInterface(url="http://localhost:8003/a2a/v1", protocolBinding="JSONRPC")
    ],
    skills=[
        AgentSkill(id="list_files", name="List Files", description="List files in a folder.", tags=["drive", "read"]),
        AgentSkill(id="search_files", name="Search Files", description="Search across Drive.", tags=["drive", "read"]),
        AgentSkill(id="get_file_metadata", name="Get File Metadata", description="Get metadata for a file.", tags=["drive", "read"]),
        AgentSkill(id="move_file", name="Move File", description="Move a file to another folder.", tags=["drive", "write"]),
        AgentSkill(id="rename_file", name="Rename File", description="Rename a file.", tags=["drive", "write"]),
        AgentSkill(id="create_folder", name="Create Folder", description="Create a new folder.", tags=["drive", "write"]),
        AgentSkill(id="organize_folder", name="Organize Folder", description="Reorganize folder contents.", tags=["drive", "write"]),
        AgentSkill(id="suggest_organization", name="Suggest Organization", description="Suggest organization without executing.", tags=["drive", "read"]),
    ]
)

agent = A2AAgentApp(card)
connector = DriveConnector()


async def handle_list_files(params: dict[str, Any], message: Message) -> Task:
    folder_id = params.get("folder_id", "root")
    max_results = params.get("max_results", 20)
    files = await connector.list_files(folder_id=folder_id, max_results=max_results)

    return Task(
        contextId=message.contextId,
        status=TaskStatus(state=TaskState.COMPLETED),
        artifacts=[
            Artifact(
                name="drive_files",
                parts=[
                    DataPart(
                        data={
                            "folder_id": folder_id,
                            "files": files,
                            "total_count": len(files)
                        }
                    )
                ]
            )
        ]
    )


async def handle_rename_file(params: dict[str, Any], message: Message) -> Task:
    file_id = params.get("file_id")
    new_name = params.get("new_name")
    res = await connector.rename_file(file_id=file_id, new_name=new_name)

    return Task(
        contextId=message.contextId,
        status=TaskStatus(state=TaskState.COMPLETED),
        artifacts=[
            Artifact(
                name="renamed_file",
                parts=[DataPart(data={"file": res})]
            )
        ]
    )


async def handle_create_folder(params: dict[str, Any], message: Message) -> Task:
    folder_name = params.get("folder_name")
    parent_id = params.get("parent_id", "root")
    folder = await connector.create_folder(folder_name=folder_name, parent_id=parent_id)

    return Task(
        contextId=message.contextId,
        status=TaskStatus(state=TaskState.COMPLETED),
        artifacts=[
            Artifact(
                name="created_folder",
                parts=[DataPart(data={"folder": folder})]
            )
        ]
    )

agent.register_skill("list_files", handle_list_files)
agent.register_skill("rename_file", handle_rename_file)
agent.register_skill("create_folder", handle_create_folder)
app = agent.app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8003)
