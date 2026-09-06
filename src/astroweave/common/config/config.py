from typing import TypedDict


class AgentConfig(TypedDict):
    agent_name: str
    domain: str
    enabled_methodologies: list[str]
    allowed_tools: list[str]
    retrieval_namespace: str