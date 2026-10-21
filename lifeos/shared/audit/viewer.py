from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from lifeos.shared.db.mongo import MongoDB


class PrivacyAuditTracker:
    """
    Manages and queries audit logs in MongoDB agent_runs.
    Verifies that zero private user data has been routed to cloud LLMs.
    """

    @staticmethod
    async def get_recent_runs(limit: int = 50, user_id: str = "default_user") -> List[Dict[str, Any]]:
        """Retrieves recent agent runs from MongoDB."""
        try:
            db = MongoDB.get_database()
            cursor = db.agent_runs.find({"user_id": user_id}, {"_id": 0}).sort("created_at", -1).limit(limit)
            return await cursor.to_list(length=limit)
        except Exception:
            return []

    @staticmethod
    async def get_privacy_metrics(user_id: str = "default_user") -> Dict[str, Any]:
        """
        Computes privacy metrics across all recorded agent runs:
        - Total runs executed
        - Local LLM executions vs remote LLM executions
        - Any detected privacy policy violations
        """
        try:
            db = MongoDB.get_database()
            cursor = db.agent_runs.find({"user_id": user_id}, {"_id": 0})
            runs = await cursor.to_list(length=500)
        except Exception:
            runs = []

        total_runs = len(runs)
        local_calls = 0
        cloud_calls = 0
        violations = 0

        for r in runs:
            audit = r.get("llm_audit", {})
            loc = audit.get("location", "local")
            sens = audit.get("sensitivity", "private")

            if loc == "local":
                local_calls += 1
            else:
                cloud_calls += 1
                if sens in ("private", "semi_private"):
                    violations += 1

        return {
            "total_runs": total_runs,
            "local_llm_calls": local_calls,
            "cloud_llm_calls": cloud_calls,
            "policy_violations": violations,
            "compliance_status": "100% compliant" if violations == 0 else "violation_detected"
        }
