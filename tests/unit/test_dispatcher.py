import unittest
from unittest.mock import MagicMock, patch

import httpx

from astroweave.orchestration.dispatcher.dispatcher import run_dispatcher


def _runtime(context: dict) -> MagicMock:
    runtime = MagicMock()
    runtime.context = context
    return runtime


class DispatcherTests(unittest.TestCase):
    @patch("astroweave.orchestration.dispatcher.dispatcher._get_specialist_graph")
    @patch("astroweave.orchestration.dispatcher.dispatcher.get_birth_chart")
    def test_fans_out_to_each_specialist(self, mock_get_birth_chart, mock_get_graph):
        mock_get_birth_chart.return_value = {"d1": {}}
        specialist_graph = MagicMock()
        specialist_graph.invoke.return_value = {
            "specialist_results": [
                {"specialist": "career", "analysis": "a", "conclusion": "c", "confidence": "high"}
            ]
        }
        mock_get_graph.return_value = specialist_graph

        result = run_dispatcher(
            {"specialists": ["career"], "methodology": "vedic", "user_query": "q"},
            _runtime(
                {
                    "birth_details": {
                        "date": "1990-01-01",
                        "time": "10:00:00",
                        "latitude": 13.08,
                        "longitude": 80.27,
                        "utc_offset_hours": 5.5,
                    }
                }
            ),
        )

        mock_get_birth_chart.assert_called_once()
        self.assertEqual(len(result["specialist_results"]), 1)
        self.assertEqual(result["errors"], [])

    def test_missing_birth_details_records_an_error(self):
        result = run_dispatcher({"specialists": ["career"]}, _runtime({}))

        self.assertIn("Birth details", result["errors"][0])

    def test_no_specialists_records_an_error(self):
        result = run_dispatcher({"specialists": []}, _runtime({"birth_details": {}}))

        self.assertIn("No specialist", result["errors"][0])

    @patch("astroweave.orchestration.dispatcher.dispatcher._get_specialist_graph")
    @patch("astroweave.orchestration.dispatcher.dispatcher.get_birth_chart")
    def test_specialist_level_errors_are_surfaced(self, mock_get_birth_chart, mock_get_graph):
        mock_get_birth_chart.return_value = {"d1": {}}
        specialist_graph = MagicMock()
        specialist_graph.invoke.return_value = {
            "specialist_results": [],
            "errors": ["career_executor returned a non-JSON response"],
        }
        mock_get_graph.return_value = specialist_graph

        result = run_dispatcher(
            {"specialists": ["career"]},
            _runtime({"birth_details": {"date": "1990-01-01"}}),
        )

        self.assertEqual(result["specialist_results"], [])
        self.assertIn("career_executor returned a non-JSON response", result["errors"])

    @patch("astroweave.orchestration.dispatcher.dispatcher.get_birth_chart")
    def test_chart_service_failure_records_an_error(self, mock_get_birth_chart):
        mock_get_birth_chart.side_effect = httpx.ConnectError("refused")

        result = run_dispatcher(
            {"specialists": ["career"]},
            _runtime({"birth_details": {"date": "1990-01-01"}}),
        )

        self.assertIn("Could not compute a birth chart", result["errors"][0])

    def test_skips_when_state_already_has_errors(self):
        result = run_dispatcher({"errors": ["earlier failure"]}, _runtime({}))

        self.assertEqual(result, {})


if __name__ == "__main__":
    unittest.main()
