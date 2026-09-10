import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from astroweave.api.main import app


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_health(self):
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "service": "astroweave-api"})

    @patch("astroweave.api.main._orchestrator_graph")
    def test_run_returns_the_synthesized_answer(self, mock_graph):
        mock_graph.invoke.return_value = {
            "answer": "You are likely to be promoted this year.",
            "specialists": ["career"],
        }

        response = self.client.post(
            "/run",
            json={
                "query": "Will I get a new job this year?",
                "conversation_id": "conversation-1",
                "session_id": "session-1",
                "username": "demo-user",
                "birth_details": {
                    "date": "1990-01-01",
                    "time": "10:00:00",
                    "latitude": 13.08,
                    "longitude": 80.27,
                    "utc_offset_hours": 5.5,
                },
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["answer"], "You are likely to be promoted this year.")
        mock_graph.invoke.assert_called_once()

    @patch("astroweave.api.main._orchestrator_graph")
    def test_run_surfaces_orchestrator_failures_as_502(self, mock_graph):
        mock_graph.invoke.side_effect = RuntimeError("chart service unreachable")

        response = self.client.post(
            "/run",
            json={
                "query": "Will I get a new job this year?",
                "conversation_id": "conversation-1",
                "session_id": "session-1",
                "username": "demo-user",
            },
        )

        self.assertEqual(response.status_code, 502)
        self.assertIn("chart service unreachable", response.json()["detail"])

    def test_run_requires_query(self):
        response = self.client.post(
            "/run",
            json={
                "conversation_id": "conversation-1",
                "session_id": "session-1",
                "username": "demo-user",
            },
        )

        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()

