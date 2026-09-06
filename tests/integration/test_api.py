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

    def test_run_endpoint_is_reserved_for_next_branch(self):
        response = self.client.post(
            "/run",
            json={
                "query": "Will I get a new job this year?",
                "conversation_id": "conversation-1",
                "session_id": "session-1",
                "username": "demo-user",
            },
        )

        self.assertEqual(response.status_code, 501)
        self.assertIn("not implemented", response.json()["detail"])

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
