import json
import logging
import re
from typing import Any

from lifeos.shared.llm.client import DataSensitivity, LocalLLMClient

logger = logging.getLogger("lifeos.planner")

AVAILABLE_SKILLS = {
    "calendar": ["list_events", "get_event", "create_event", "find_free_slots", "detect_conflicts", "suggest_focus_block"],
    "email": ["list_messages", "get_message", "summarize_inbox", "extract_action_items", "draft_reply", "search_messages"],
    "file": ["list_files", "search_files", "get_file_metadata", "move_file", "rename_file", "create_folder"],
    "task": ["create_task", "update_task", "complete_task", "list_open_tasks", "prioritize_tasks", "bulk_create_tasks"],
    "notification": ["send_slack", "send_dm", "update_message"]
}

WRITE_SKILLS = {
    "calendar": ["create_event"],
    "email": ["send_message"],
    "file": ["move_file", "rename_file", "create_folder"],
    "task": ["create_task", "update_task", "complete_task", "prioritize_tasks", "bulk_create_tasks"],
    "notification": ["send_slack", "send_dm"]
}

PLANNER_SYSTEM_PROMPT = """You are the LifeOS Orchestration Planner.
Given a user command, return a JSON array of subtasks to execute across domain agents.
Only use the following agents and skills:
- calendar: list_events, create_event, find_free_slots, suggest_focus_block
- email: list_messages, summarize_inbox, extract_action_items, search_messages
- file: list_files, search_files, create_folder, rename_file, move_file
- task: list_open_tasks, create_task, complete_task, bulk_create_tasks
- notification: send_slack

Output MUST be valid JSON only. Format:
[
  {"agent": "agent_name", "skill": "skill_name", "params": {}}
]
Do not include explanations or markdown fences."""


class TaskPlanner:
    """Decomposes natural language instructions into validated A2A agent subtasks."""

    def __init__(self, llm_client: LocalLLMClient | None = None):
        self.llm = llm_client or LocalLLMClient()

    async def plan(self, command: str) -> list[dict[str, Any]]:
        """Decomposes a command using the local LLM, with deterministic fallback."""
        cmd_lower = command.lower().strip()

        # Try LLM-based decomposition if available
        try:
            res = await self.llm.generate(
                prompt=f"Command: {command}\nPlan:",
                system_prompt=PLANNER_SYSTEM_PROMPT,
                sensitivity=DataSensitivity.NON_PRIVATE,
                temperature=0.1
            )
            raw_text = res.get("text", "").strip()
            # Clean possible markdown fences
            raw_text = re.sub(r"^```(json)?", "", raw_text)
            raw_text = re.sub(r"```$", "", raw_text).strip()
            parsed = json.loads(raw_text)
            if isinstance(parsed, list) and len(parsed) > 0:
                validated = self._validate_plan(parsed)
                if validated:
                    return validated
        except Exception as e:
            logger.debug(f"LLM planner unavailable or non-JSON output ({e}). Falling back to rule-based planner.")

        # Deterministic rule-based fallback
        return self._heuristic_plan(cmd_lower)

    def _validate_plan(self, plan: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Validates that agents and skills in the plan exist in registry."""
        validated = []
        for step in plan:
            agent = step.get("agent")
            skill = step.get("skill")
            params = step.get("params", {})
            if agent in AVAILABLE_SKILLS and skill in AVAILABLE_SKILLS[agent]:
                validated.append({
                    "agent": agent,
                    "skill": skill,
                    "params": params if isinstance(params, dict) else {},
                    "is_write": skill in WRITE_SKILLS.get(agent, [])
                })
        return validated

    def _heuristic_plan(self, cmd_lower: str) -> list[dict[str, Any]]:
        """Heuristic decomposition for offline execution."""
        plan = []

        # Calendar intent
        if any(w in cmd_lower for w in ["meeting", "calendar", "event", "schedule", "week"]):
            plan.append({
                "agent": "calendar",
                "skill": "list_events",
                "params": {},
                "is_write": False
            })

        # Email intent
        if any(w in cmd_lower for w in ["email", "inbox", "gmail", "message", "mail"]):
            if any(w in cmd_lower for w in ["action", "task", "extract"]):
                plan.append({
                    "agent": "email",
                    "skill": "extract_action_items",
                    "params": {"query": "is:unread"},
                    "is_write": False
                })
            else:
                plan.append({
                    "agent": "email",
                    "skill": "summarize_inbox",
                    "params": {},
                    "is_write": False
                })

        # Task intent
        if any(w in cmd_lower for w in ["task", "todo", "to-do", "action item", "week"]):
            plan.append({
                "agent": "task",
                "skill": "list_open_tasks",
                "params": {},
                "is_write": False
            })

        # File intent
        if any(w in cmd_lower for w in ["file", "drive", "folder", "document"]):
            plan.append({
                "agent": "file",
                "skill": "list_files",
                "params": {"folder_id": "root"},
                "is_write": False
            })

        # Default fallback if no keywords matched
        if not plan:
            plan = [
                {"agent": "calendar", "skill": "list_events", "params": {}, "is_write": False},
                {"agent": "task", "skill": "list_open_tasks", "params": {}, "is_write": False}
            ]

        return plan
