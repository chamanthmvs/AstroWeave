import unittest

from langgraph.errors import GraphRecursionError

from astroweave.graphs.specialist.specialist_graph import build_specialist_graph


class SpecialistGraphTests(unittest.TestCase):
    def test_sufficient_result_reaches_synthesizer(self):
        graph = build_specialist_graph()

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
        self.assertEqual(result["tool_results"][0]["tool_name"], "career_demo_tool")
        self.assertEqual(len(result["stage_results"]), 1)
        self.assertEqual(result["errors"], [])
        self.assertEqual(len(result["execution_trace"]), 5)

    def test_stage_results_are_limited_to_latest_five(self):
        graph = build_specialist_graph()

        result = graph.invoke(
            {
                "is_sufficient": True,
                "stage_results": [
                    {"stage": str(index), "result": index} for index in range(6)
                ],
            }
        )

        self.assertEqual(len(result["stage_results"]), 5)
        self.assertEqual(result["stage_results"][-1]["stage"], "executor")

    def test_insufficient_result_replans(self):
        graph = build_specialist_graph()

        with self.assertRaises(GraphRecursionError):
            graph.invoke({"is_sufficient": False}, {"recursion_limit": 3})


if __name__ == "__main__":
    unittest.main()