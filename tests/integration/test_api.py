import unittest

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

    def test_run_executes_demo_flow(self):
        response = self.client.post(
            "/run",
            json={
                "query": "Will I get a new job this year?",
                "conversation_id": "conversation-1",
                "session_id": "session-1",
                "username": "demo-user",
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("Demo orchestration completed", body["answer"])
        self.assertEqual(body["context"]["conversation_id"], "conversation-1")
        self.assertEqual(
            body["runnable_config"]["configurable"]["thread_id"],
            "conversation-1",
        )
        self.assertEqual(
            body["runnable_config"]["metadata"],
            {"session_id": "session-1", "methodology": "Let the system decide"},
        )
        self.assertEqual(body["runnable_config"]["tags"], ["demo", "no-llm"])
        self.assertGreaterEqual(len(body["execution_trace"]), 10)
        self.assertEqual(
            [event["step"] for event in body["execution_trace"]],
            list(range(1, len(body["execution_trace"]) + 1)),
        )
        entry_points = [event["entry_point"] for event in body["execution_trace"]]
        self.assertLess(
            entry_points.index("dispatcher_entry"),
            entry_points.index("specialist_planner"),
        )
        self.assertLess(
            entry_points.index("specialist_synthesizer"),
            entry_points.index("dispatcher_exit"),
        )
        first_event = body["execution_trace"][0]
        self.assertEqual(first_event["entry_point"], "graph_entry")
        self.assertIn("user_query", first_event["state_before"])
        self.assertEqual(first_event["state_updates"], {})
        self.assertEqual(
            first_event["state_before"]["messages"][0]["content"],
            "Will I get a new job this year?",
        )
        self.assertEqual(first_event["state_before"], first_event["state_after"])
        self.assertEqual(body["state"]["messages"][0]["role"], "user")
        self.assertTrue(
            all(
                set(event["runnable_config"]) <= {"configurable", "metadata", "tags", "recursion_limit"}
                for event in body["execution_trace"]
            )
        )

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
