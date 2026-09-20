import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from astroweave.api.main import app
from astroweave.common.security import create_user_token


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_health(self):
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "service": "astroweave-api"})

    @staticmethod
    def _headers(username: str = "demo-user") -> dict[str, str]:
        return {"Authorization": f"Bearer {create_user_token(username)}"}

    @patch("astroweave.api.main._orchestrator_graph")
    @patch("astroweave.api.main._conversation_store")
    def test_run_returns_the_synthesized_answer(self, mock_store, mock_graph):
        mock_store.claim_request.return_value = ("claim-token", None)
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
            headers=self._headers(),
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["answer"], "You are likely to be promoted this year.")
        mock_graph.invoke.assert_called_once()
        context = mock_graph.invoke.call_args.kwargs["context"]
        self.assertTrue(context["message_id"])
        self.assertIsNotNone(context["conversation_store"])
        self.assertTrue(context["request_fingerprint"])
        self.assertEqual(context["request_claim_token"], "claim-token")

    @patch("astroweave.api.main._orchestrator_graph")
    @patch("astroweave.api.main._conversation_store")
    def test_run_replays_an_idempotent_response(self, mock_store, mock_graph):
        mock_store.claim_request.return_value = (None, "Saved answer")

        response = self.client.post(
            "/run",
            json={
                "query": "Question",
                "conversation_id": "conversation-1",
                "session_id": "session-1",
                "message_id": "message-1",
                "username": "demo-user",
            },
            headers=self._headers(),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["answer"], "Saved answer")
        self.assertTrue(response.json()["state"]["history_replayed"])
        mock_graph.invoke.assert_not_called()

    @patch("astroweave.api.main._orchestrator_graph")
    @patch("astroweave.api.main._conversation_store")
    def test_run_surfaces_orchestrator_failures_as_502(self, mock_store, mock_graph):
        mock_store.claim_request.return_value = ("claim-token", None)
        mock_graph.invoke.side_effect = RuntimeError("chart service unreachable")

        response = self.client.post(
            "/run",
            json={
                "query": "Will I get a new job this year?",
                "conversation_id": "conversation-1",
                "session_id": "session-1",
                "username": "demo-user",
            },
            headers=self._headers(),
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
            headers=self._headers(),
        )

        self.assertEqual(response.status_code, 422)

    @patch("astroweave.api.main._conversation_store")
    def test_lists_the_users_conversations(self, mock_store):
        mock_store.list_conversations.return_value = [
            {
                "conversation_id": "conversation-1",
                "title": "Career question",
                "created_at": "2026-09-20 10:00:00",
                "updated_at": "2026-09-20 10:00:00",
            }
        ]

        response = self.client.get("/conversations", headers=self._headers())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["conversations"][0]["conversation_id"],
            "conversation-1",
        )
        mock_store.list_conversations.assert_called_once_with("demo-user", 50)

    @patch("astroweave.api.main._conversation_store")
    def test_returns_conversation_messages(self, mock_store):
        mock_store.load_recent_messages.return_value = [
            {"message_id": "message-1", "role": "user", "content": "Question"}
        ]

        response = self.client.get(
            "/conversations/conversation-1/messages",
            params={"limit": 20},
            headers=self._headers(),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["messages"][0]["content"], "Question")
        mock_store.load_recent_messages.assert_called_once_with(
            "conversation-1", "demo-user", 20
        )

    @patch("astroweave.api.main._conversation_store")
    def test_rejects_messages_owned_by_another_user(self, mock_store):
        from astroweave.common.conversation import ConversationAccessError

        mock_store.load_recent_messages.side_effect = ConversationAccessError(
            "Conversation ID is not owned by this user."
        )

        response = self.client.get(
            "/conversations/conversation-1/messages",
            headers=self._headers("another-user"),
        )

        self.assertEqual(response.status_code, 403)

    @patch("astroweave.api.main._conversation_store")
    def test_deletes_an_owned_conversation(self, mock_store):
        mock_store.delete_conversation.return_value = True

        response = self.client.delete(
            "/conversations/conversation-1",
            headers=self._headers(),
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["deleted"])
        mock_store.delete_conversation.assert_called_once_with(
            "conversation-1", "demo-user"
        )

    def test_protected_endpoint_requires_a_token(self):
        response = self.client.get("/conversations")

        self.assertEqual(response.status_code, 401)

    @patch("astroweave.api.main._conversation_store")
    def test_run_rejects_a_username_different_from_token(self, mock_store):
        response = self.client.post(
            "/run",
            json={
                "query": "Question",
                "conversation_id": "conversation-1",
                "session_id": "session-1",
                "username": "victim@example.com",
            },
            headers=self._headers("attacker@example.com"),
        )

        self.assertEqual(response.status_code, 403)
        mock_store.claim_request.assert_not_called()

    @patch("astroweave.api.main._conversation_store")
    def test_run_returns_conflict_for_an_in_progress_message(self, mock_store):
        from astroweave.common.conversation import ConversationInProgressError

        mock_store.claim_request.side_effect = ConversationInProgressError(
            "A request with this message ID is already in progress."
        )

        response = self.client.post(
            "/run",
            json={
                "query": "Question",
                "conversation_id": "conversation-1",
                "session_id": "session-1",
                "message_id": "message-1",
                "username": "demo-user",
            },
            headers=self._headers(),
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.json()["detail"]["code"], "request_in_progress"
        )


if __name__ == "__main__":
    unittest.main()

