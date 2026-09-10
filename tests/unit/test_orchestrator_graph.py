import json
import unittest
from unittest.mock import MagicMock, patch

from astroweave.graphs.orchestrator.orchestrator_graph import (
    build_orchestrator_graph,
)


class OrchestratorGraphTests(unittest.TestCase):
    @patch("astroweave.graphs.orchestrator.orchestrator_graph.run_dispatcher")
    @patch("astroweave.graphs.orchestrator.orchestrator_graph.get_llm")
    def test_full_run_produces_a_synthesized_answer(self, mock_get_llm, mock_run_dispatcher):
        llm = MagicMock()
        llm.invoke.side_effect = [
            MagicMock(
                content=json.dumps(
                    {
                        "specialists": ["career"],
                        "methodology": "vedic",
                        "reasoning": "Career question about promotion.",
                    }
                )
            ),
            MagicMock(content="You are likely to be promoted this year."),
        ]
        mock_get_llm.return_value = llm
        mock_run_dispatcher.return_value = {
            "chart_data": {"d1": {}},
            "specialist_results": [
                {
                    "specialist": "career",
                    "analysis": "Jupiter aspects the 10th house.",
                    "conclusion": "A promotion is likely.",
                    "confidence": "high",
                }
            ],
            "errors": [],
        }

        graph = build_orchestrator_graph()
        result = graph.invoke(
            {"user_query": "Will I get promoted this year?"},
            context={
                "conversation_id": "conversation-1",
                "session_id": "session-1",
                "username": "test-user",
                "birth_details": {
                    "date": "1990-01-01",
                    "time": "10:00:00",
                    "latitude": 13.08,
                    "longitude": 80.27,
                    "utc_offset_hours": 5.5,
                },
            },
        )

        self.assertEqual(result["specialists"], ["career"])
        self.assertEqual(result["methodology"], "vedic")
        self.assertEqual(result["answer"], "You are likely to be promoted this year.")
        mock_run_dispatcher.assert_called_once()

    @patch("astroweave.graphs.orchestrator.orchestrator_graph.get_llm")
    def test_empty_query_short_circuits_before_dispatch(self, mock_get_llm):
        graph = build_orchestrator_graph()

        result = graph.invoke(
            {"user_query": ""},
            context={
                "conversation_id": "conversation-1",
                "session_id": "session-1",
                "username": "test-user",
            },
        )

        mock_get_llm.assert_not_called()
        self.assertEqual(result["specialist_results"], [])
        self.assertEqual(result["answer"], "No question was provided.")


if __name__ == "__main__":
    unittest.main()
