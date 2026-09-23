import unittest

from astroweave.agents.registry import AgentDefinition, AgentRegistry
from astroweave.agents.specialists import SPECIALIST_REGISTRY
from astroweave.common.tools import BaseToolReturnType, ToolRegistry, tool


class AgentRegistryTests(unittest.TestCase):
    def test_specialists_are_available_to_the_orchestrator(self):
        self.assertEqual(
            {agent.name for agent in SPECIALIST_REGISTRY},
            {"career", "finance", "love", "sports"},
        )
        self.assertEqual(len(SPECIALIST_REGISTRY.require("career").tools), 0)

    def test_agent_owns_its_tool_registry(self):
        @tool(description="Find a career focus.")
        def career_focus() -> BaseToolReturnType:
            return BaseToolReturnType(success=True)

        tools = ToolRegistry([career_focus])
        registry = AgentRegistry(
            [AgentDefinition("career", "Career specialist", "prompt", tools)]
        )

        self.assertIs(
            registry.require("career").tools.require("career_focus"),
            career_focus,
        )

    def test_registry_rejects_duplicate_agent_names(self):
        agent = AgentDefinition("career", "Career specialist", "prompt")

        with self.assertRaisesRegex(ValueError, "already registered"):
            AgentRegistry([agent, agent])


if __name__ == "__main__":
    unittest.main()