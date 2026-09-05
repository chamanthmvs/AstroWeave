import unittest

from langgraph.errors import GraphRecursionError

from astroweave.graphs.specialists.specialist_graph import build_specialist_graph


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
        self.assertEqual(result["tool_results"], [])
        self.assertEqual(result["stage_results"], [])
        self.assertEqual(result["errors"], [])

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

        self.assertEqual(
            result["stage_results"],
            [{"stage": str(index), "result": index} for index in range(1, 6)],
        )

    def test_insufficient_result_replans(self):
        graph = build_specialist_graph()

        with self.assertRaises(GraphRecursionError):
            graph.invoke({"is_sufficient": False}, {"recursion_limit": 3})


if __name__ == "__main__":
    unittest.main()