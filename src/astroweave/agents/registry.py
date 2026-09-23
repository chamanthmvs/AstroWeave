from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field

from astroweave.common.tools import ToolRegistry


@dataclass(frozen=True, slots=True)
class AgentDefinition:
    name: str
    description: str
    prompt: str
    tools: ToolRegistry = field(default_factory=ToolRegistry)


class AgentRegistry:
    """Orchestrator-facing catalog of available agent definitions."""

    def __init__(self, agents: Iterable[AgentDefinition] = ()) -> None:
        self._agents: dict[str, AgentDefinition] = {}
        for agent in agents:
            self.register(agent)

    def register(self, agent: AgentDefinition) -> AgentDefinition:
        if agent.name in self._agents:
            raise ValueError(f"Agent '{agent.name}' is already registered")
        self._agents[agent.name] = agent
        return agent

    def get(self, name: str) -> AgentDefinition | None:
        return self._agents.get(name)

    def require(self, name: str) -> AgentDefinition:
        agent = self.get(name)
        if agent is None:
            raise KeyError(f"Unknown agent '{name}'")
        return agent

    def __contains__(self, name: object) -> bool:
        return name in self._agents

    def __iter__(self) -> Iterator[AgentDefinition]:
        return iter(self._agents.values())

    def __len__(self) -> int:
        return len(self._agents)