import unittest

from astroweave.agents.registry import AgentDefinition, AgentRegistry
from astroweave.agents.specialists import SPECIALIST_REGISTRY
from astroweave.common.tools import BaseToolReturnType, ToolRegistry, tool


class AgentRegistryTests(unittest.TestCase):
    def test_specialists_are_available_to_the_orchestrator(self):
        self.assertEqual(
            {agent.name for agent in SPECIALIST_REGISTRY},
            {"career", "finance", "love", "sports", "general"},
        )
        # Domain specialists carry intent-grouped tool catalogs; general has none.
        self.assertEqual(len(SPECIALIST_REGISTRY.require("general").tools), 0)
        for agent in SPECIALIST_REGISTRY:
            if agent.name == "general":
                continue
            grouped_tools = agent.tools.grouped_metadata()
            self.assertEqual(len(grouped_tools), 4)
            self.assertEqual(sum(map(len, grouped_tools.values())), 12)
            self.assertTrue(all(metadata.intent for metadata in agent.tools.metadata()))

    def test_router_can_select_every_registered_specialist(self):
        from astroweave.graphs.orchestrator.prompts import ORCHESTRATOR_ROUTING_SCHEMA

        names = {agent.name for agent in SPECIALIST_REGISTRY}
        properties = ORCHESTRATOR_ROUTING_SCHEMA["properties"]
        self.assertEqual(set(properties["specialists"]["items"]["enum"]), names)
        task = properties["tasks"]["items"]["properties"]
        self.assertEqual(set(task["specialist"]["enum"]), names)
        self.assertEqual(set(task["depends_on"]["items"]["enum"]), names)

    def test_general_specialist_prompt_covers_whole_person_readings(self):
        prompt = SPECIALIST_REGISTRY.require("general").prompt
        for marker in ("element_balance", "janma nakshatra", "D9", "Response format"):
            self.assertIn(marker, prompt)

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