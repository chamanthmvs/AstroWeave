import unittest

from langgraph.errors import GraphRecursionError

from astroweave.graphs.orchestrator.orchestrator_graph import (
    build_orchestrator_graph,
)


class OrchestratorGraphTests(unittest.TestCase):
    def test_sufficient_result_reaches_synthesizer(self):
        graph = build_orchestrator_graph()

        result = graph.invoke(
            {"is_sufficient": True},
            context={
                "conversation_id": "conversation-1",
                "session_id": "session-1",
                "username": "test-user",
            },
        )

        self.assertTrue(result["is_sufficient"])
        self.assertEqual(result["messages"], [])
        self.assertEqual(result["tool_results"], [])
        self.assertEqual(result["stage_results"], [])
        self.assertEqual(result["errors"], [])

    def test_insufficient_result_replans(self):
        graph = build_orchestrator_graph()

        with self.assertRaises(GraphRecursionError):
            graph.invoke({"is_sufficient": False}, {"recursion_limit": 3})


if __name__ == "__main__":
    unittest.main()