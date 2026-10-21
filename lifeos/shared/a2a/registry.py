import logging

import httpx

from lifeos.shared.a2a.models import AgentCard

logger = logging.getLogger("a2a.registry")


class AgentRegistration:
    def __init__(self, name: str, url: str, card: AgentCard):
        self.name = name
        self.url = url.rstrip("/")
        self.card = card
        self.is_healthy = True


class AgentRegistry:
    """
    Dynamic discovery registry for A2A domain agents.
    Discovers capabilities and skills from /.well-known/agent-card.json.
    """

    def __init__(self, timeout: float = 3.0):
        self.timeout = timeout
        self._agents: dict[str, AgentRegistration] = {}

    async def register(self, url: str) -> AgentCard | None:
        """Discovers an agent by URL, queries its agent card, and registers it."""
        clean_url = url.rstrip("/")
        card_url = f"{clean_url}/.well-known/agent-card.json"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.get(card_url)
                resp.raise_for_status()
                card_data = resp.json()
                card = AgentCard.model_validate(card_data)

                # Derive agent key identifier from card name
                key = card.name.lower().replace("lifeos", "").replace("agent", "").strip()
                if not key:
                    key = card.name.lower()

                self._agents[key] = AgentRegistration(name=key, url=clean_url, card=card)
                logger.info(f"Registered agent '{key}' at {clean_url} with {len(card.skills)} skills")
                return card
            except Exception as e:
                logger.warning(f"Failed to register agent at {url}: {e}")
                return None

    def register_static(self, name: str, url: str, card: AgentCard) -> None:
        """Registers a known static agent entry."""
        self._agents[name] = AgentRegistration(name=name, url=url.rstrip("/"), card=card)

    def get_agent(self, name: str) -> AgentRegistration | None:
        return self._agents.get(name)

    def get_all(self) -> dict[str, AgentRegistration]:
        return self._agents

    def find_agent_for_skill(self, skill_id: str) -> AgentRegistration | None:
        """Finds an agent that exposes the requested skill."""
        for reg in self._agents.values():
            for skill in reg.card.skills:
                if skill.id == skill_id:
                    return reg
        return None

    async def health_check_all(self) -> dict[str, bool]:
        """Pings health endpoints of all registered agents."""
        results = {}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for name, reg in self._agents.items():
                health_url = f"{reg.url}/health"
                try:
                    resp = await client.get(health_url)
                    is_ok = resp.status_code == 200
                    reg.is_healthy = is_ok
                    results[name] = is_ok
                except Exception:
                    reg.is_healthy = False
                    results[name] = False
        return results
