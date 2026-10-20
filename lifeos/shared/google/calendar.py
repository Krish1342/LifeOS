from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from googleapiclient.discovery import build
from lifeos.shared.google.auth import GoogleAuthManager


class CalendarConnector:
    """Connector for Google Calendar API with fallback demo mode when unauthenticated."""

    def __init__(self, user_id: str = "default_user"):
        self.user_id = user_id
        self.auth_manager = GoogleAuthManager(service_name="google_calendar")

    async def _get_service(self):
        creds = await self.auth_manager.get_credentials(self.user_id)
        if not creds:
            return None
        return build("calendar", "v3", credentials=creds, cache_discovery=False)

    async def list_events(
        self,
        time_min: Optional[str] = None,
        time_max: Optional[str] = None,
        max_results: int = 20
    ) -> List[Dict[str, Any]]:
        service = await self._get_service()
        if not service:
            # Return demo/mock events if credentials not yet connected
            now = datetime.now(timezone.utc)
            return [
                {
                    "id": "evt_demo_1",
                    "summary": "Team Weekly Sync",
                    "start": (now + timedelta(days=1, hours=2)).isoformat(),
                    "end": (now + timedelta(days=1, hours=3)).isoformat(),
                    "location": "Google Meet",
                    "status": "confirmed",
                    "is_mock": True
                },
                {
                    "id": "evt_demo_2",
                    "summary": "Product Architecture Review",
                    "start": (now + timedelta(days=2, hours=4)).isoformat(),
                    "end": (now + timedelta(days=2, hours=5)).isoformat(),
                    "location": "Conference Room A",
                    "status": "confirmed",
                    "is_mock": True
                }
            ]

        t_min = time_min or datetime.now(timezone.utc).isoformat()
        t_max = time_max or (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()

        events_result = service.events().list(
            calendarId="primary",
            timeMin=t_min,
            timeMax=t_max,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime"
        ).execute()

        raw_events = events_result.get("items", [])
        formatted_events = []
        for e in raw_events:
            start = e.get("start", {}).get("dateTime") or e.get("start", {}).get("date")
            end = e.get("end", {}).get("dateTime") or e.get("end", {}).get("date")
            formatted_events.append({
                "id": e.get("id"),
                "summary": e.get("summary", "Untitled Event"),
                "description": e.get("description", ""),
                "start": start,
                "end": end,
                "location": e.get("location", ""),
                "status": e.get("status", "confirmed"),
                "html_link": e.get("htmlLink", "")
            })
        return formatted_events

    async def detect_conflicts(
        self,
        time_min: Optional[str] = None,
        time_max: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        events = await self.list_events(time_min=time_min, time_max=time_max)
        conflicts = []
        for i in range(len(events)):
            for j in range(i + 1, len(events)):
                e1 = events[i]
                e2 = events[j]
                if e1["start"] < e2["end"] and e2["start"] < e1["end"]:
                    conflicts.append({
                        "event_a": e1["summary"],
                        "event_b": e2["summary"],
                        "start": max(e1["start"], e2["start"]),
                        "end": min(e1["end"], e2["end"])
                    })
        return conflicts

    async def create_event(
        self,
        summary: str,
        start_time: str,
        end_time: str,
        description: str = "",
        location: str = ""
    ) -> Dict[str, Any]:
        service = await self._get_service()
        if not service:
            return {
                "id": f"evt_mock_{int(datetime.now().timestamp())}",
                "summary": summary,
                "start": start_time,
                "end": end_time,
                "description": description,
                "location": location,
                "status": "confirmed",
                "is_mock": True
            }

        body = {
            "summary": summary,
            "description": description,
            "location": location,
            "start": {"dateTime": start_time},
            "end": {"dateTime": end_time}
        }
        event = service.events().insert(calendarId="primary", body=body).execute()
        return {
            "id": event.get("id"),
            "summary": event.get("summary"),
            "start": event.get("start", {}).get("dateTime"),
            "end": event.get("end", {}).get("dateTime"),
            "html_link": event.get("htmlLink")
        }
