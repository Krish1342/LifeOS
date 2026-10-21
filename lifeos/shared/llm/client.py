import os
from enum import Enum
from typing import Any

import httpx

from lifeos.shared.http.client import SecurityError


class DataSensitivity(str, Enum):
    PRIVATE = "private"           # User emails, event details, file contents
    SEMI_PRIVATE = "semi_private" # Structural metadata
    NON_PRIVATE = "non_private"   # High-level command intent (e.g. "plan my week")


class LocalLLMClient:
    """
    Client for interacting with local open-weight LLMs via Ollama.
    Enforces privacy routing: private user data is strictly forbidden from third-party cloud APIs.
    """

    def __init__(
        self,
        base_url: str | None = None,
        default_model: str | None = None,
        fallback_model: str | None = None
    ):
        self.base_url = (base_url or os.getenv("OLLAMA_URL", "http://localhost:11434")).rstrip("/")
        self.default_model = default_model or os.getenv("OLLAMA_MODEL", "llama3.1:8b-instruct-q4_K_M")
        self.fallback_model = fallback_model or os.getenv("OLLAMA_FALLBACK_MODEL", "phi3:mini")

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        sensitivity: DataSensitivity = DataSensitivity.PRIVATE,
        model: str | None = None,
        temperature: float = 0.2
    ) -> dict[str, Any]:
        """
        Executes an LLM completion.
        Guarantees private data is only processed locally on localhost Ollama.
        """
        target_model = model or self.default_model

        # Strictly assert local endpoint for private data
        if sensitivity in (DataSensitivity.PRIVATE, DataSensitivity.SEMI_PRIVATE):
            if "localhost" not in self.base_url and "127.0.0.1" not in self.base_url:
                raise SecurityError(
                    f"Privacy Violation: Cannot route {sensitivity.value} user data to remote host {self.base_url}"
                )

        endpoint = f"{self.base_url}/api/generate"
        payload = {
            "model": target_model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature
            }
        }
        if system_prompt:
            payload["system"] = system_prompt

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(endpoint, json=payload)
                response.raise_for_status()
                data = response.json()
                return {
                    "text": data.get("response", ""),
                    "model": target_model,
                    "location": "local",
                    "sensitivity": sensitivity.value,
                    "done": data.get("done", True)
                }
            except (httpx.ConnectError, httpx.TimeoutException) as e:
                # If default model fails and fallback is available, attempt fallback
                if target_model != self.fallback_model and self.fallback_model:
                    payload["model"] = self.fallback_model
                    try:
                        fb_resp = await client.post(endpoint, json=payload)
                        fb_resp.raise_for_status()
                        fb_data = fb_resp.json()
                        return {
                            "text": fb_data.get("response", ""),
                            "model": self.fallback_model,
                            "location": "local",
                            "sensitivity": sensitivity.value,
                            "done": fb_data.get("done", True),
                            "note": f"Fell back from {target_model} due to connection error"
                        }
                    except Exception:
                        pass
                raise RuntimeError(
                    f"Local LLM service unavailable at {self.base_url}. Ensure Ollama is running (`ollama serve`). Error: {e!s}"
                ) from e
