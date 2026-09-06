import unittest

from langgraph.errors import GraphRecursionError

from astroweave.graphs.orchestrator.orchestrator_graph import (
    build_orchestrator_graph,
)


class OrchestratorGraphTests(unittest.TestCase):
    def test_sufficient_result_reaches_synthesizer(self):
        graph = build_orchestrator_graph()

        result = graph.invoke(
            {"user_query": "Will I get a new job this year?"},
            context={
                "conversation_id": "conversation-1",
                "session_id": "session-1",
                "username": "test-user",
            },
        )

        self.assertTrue(result["is_sufficient"])
        self.assertEqual(result["messages"], [])
        self.assertEqual(result["selected_specialists"], ["career"])
        self.assertEqual(result["tool_results"][0]["tool_name"], "career_demo_tool")
        self.assertIn("Demo orchestration completed", result["answer"])
        self.assertGreaterEqual(len(result["execution_trace"]), 10)
        self.assertEqual(result["errors"], [])

    def test_insufficient_result_replans(self):
        graph = build_orchestrator_graph()

        with self.assertRaises(GraphRecursionError):
            graph.invoke({"is_sufficient": False}, {"recursion_limit": 3})


if __name__ == "__main__":
    unittest.main()