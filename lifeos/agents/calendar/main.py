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
from lifeos.shared.google.calendar import CalendarConnector

# Per-agent outbound security boundary: Calendar Agent can ONLY contact Google APIs
http_client = ScopedHTTPClient(allowed_hosts=["www.googleapis.com"])

card = AgentCard(
    name="LifeOS Calendar Agent",
    description="Manages Google Calendar events: reading, creating, updating, conflict detection, and focus time scheduling.",
    url="http://localhost:8001",
    supportedInterfaces=[
        SupportedInterface(url="http://localhost:8001/a2a/v1", protocolBinding="JSONRPC")
    ],
    skills=[
        AgentSkill(id="list_events", name="List Events", description="List calendar events for a date range.", tags=["calendar", "read"]),
        AgentSkill(id="get_event", name="Get Event", description="Get details of a specific event.", tags=["calendar", "read"]),
        AgentSkill(id="create_event", name="Create Event", description="Create a new calendar event.", tags=["calendar", "write"]),
        AgentSkill(id="update_event", name="Update Event", description="Modify an existing event.", tags=["calendar", "write"]),
        AgentSkill(id="delete_event", name="Delete Event", description="Remove a calendar event.", tags=["calendar", "write"]),
        AgentSkill(id="find_free_slots", name="Find Free Slots", description="Find available time slots.", tags=["calendar", "read"]),
        AgentSkill(id="detect_conflicts", name="Detect Conflicts", description="Identify overlapping events.", tags=["calendar", "read"]),
        AgentSkill(id="suggest_focus_block", name="Suggest Focus Block", description="Suggest optimal focus time.", tags=["calendar", "read"]),
    ]
)

agent = A2AAgentApp(card)
connector = CalendarConnector()


async def handle_list_events(params: Dict[str, Any], message: Message) -> Task:
    start_date = params.get("start_date")
    end_date = params.get("end_date")
    events = await connector.list_events(time_min=start_date, time_max=end_date)
    conflicts = await connector.detect_conflicts(time_min=start_date, time_max=end_date)

    return Task(
        contextId=message.contextId,
        status=TaskStatus(state=TaskState.COMPLETED),
        artifacts=[
            Artifact(
                name="events_list",
                parts=[
                    DataPart(
                        data={
                            "events": events,
                            "total_count": len(events),
                            "conflicts": conflicts
                        }
                    )
                ]
            )
        ]
    )


async def handle_create_event(params: Dict[str, Any], message: Message) -> Task:
    summary = params.get("summary", "New LifeOS Event")
    start = params.get("start")
    end = params.get("end")
    description = params.get("description", "")
    location = params.get("location", "")

    event = await connector.create_event(
        summary=summary,
        start_time=start,
        end_time=end,
        description=description,
        location=location
    )

    return Task(
        contextId=message.contextId,
        status=TaskStatus(state=TaskState.COMPLETED),
        artifacts=[
            Artifact(
                name="created_event",
                parts=[DataPart(data={"event": event})]
            )
        ]
    )

agent.register_skill("list_events", handle_list_events)
agent.register_skill("create_event", handle_create_event)
app = agent.app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001)
