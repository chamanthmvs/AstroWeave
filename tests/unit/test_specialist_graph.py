import json
import unittest
from unittest.mock import MagicMock, patch

from astroweave.graphs.specialist.specialist_graph import build_specialist_graph


def _fake_llm(content: str) -> MagicMock:
    llm = MagicMock()
    llm.invoke.return_value = MagicMock(content=content)
    return llm


class SpecialistGraphTests(unittest.TestCase):
    @patch("astroweave.graphs.specialist.specialist_graph.get_llm")
    def test_executor_produces_a_specialist_result(self, mock_get_llm):
        mock_get_llm.return_value = _fake_llm(
            json.dumps(
                {
                    "analysis": "Jupiter aspects the 10th house.",
                    "conclusion": "A promotion is likely this year.",
                    "confidence": "high",
                }
            )
        )
        graph = build_specialist_graph()

        result = graph.invoke(
            {
                "user_query": "Will I get promoted?",
                "current_task": "career",
                "methodology": "vedic",
                "chart_data": {"d1": {}},
            },
            context={
                "conversation_id": "conversation-1",
                "session_id": "session-1",
                "username": "test-user",
            },
        )

        mock_get_llm.assert_called_once_with("specialist", agent_name="career")
        self.assertEqual(
            result["specialist_results"],
            [
                {
                    "specialist": "career",
                    "analysis": "Jupiter aspects the 10th house.",
                    "conclusion": "A promotion is likely this year.",
                    "confidence": "high",
                }
            ],
        )
        self.assertTrue(result["is_sufficient"])

    @patch("astroweave.graphs.specialist.specialist_graph.get_llm")
    def test_unknown_specialist_records_an_error(self, mock_get_llm):
        graph = build_specialist_graph()

        result = graph.invoke({"current_task": "unknown"})

        mock_get_llm.assert_not_called()
        self.assertEqual(result["specialist_results"], [])
        self.assertIn("Unknown specialist 'unknown'", result["errors"][0])

    @patch("astroweave.graphs.specialist.specialist_graph.get_llm")
    def test_malformed_llm_response_records_an_error(self, mock_get_llm):
        mock_get_llm.return_value = _fake_llm("not json")
        graph = build_specialist_graph()

        result = graph.invoke({"current_task": "career"})

        self.assertEqual(result["specialist_results"], [])
        self.assertTrue(result["errors"])

    def test_insufficient_result_forced_sufficient_in_v1(self):
        # v1 runs a single planner/executor pass; the evaluator always
        # reports "sufficient" so it never loops back to the planner.
        graph = build_specialist_graph()

        result = graph.invoke({"current_task": "unknown", "is_sufficient": False})

        self.assertTrue(result["is_sufficient"])


if __name__ == "__main__":
    unittest.main()
