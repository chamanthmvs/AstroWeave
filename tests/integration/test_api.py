import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock
from unittest.mock import patch

from fastapi.testclient import TestClient

from astroweave.api.main import app
from astroweave.common.conversation import ConversationStore
from astroweave.common.security import create_user_token
from astroweave.specialist_service import app as specialist_app


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def setUp(self):
        profile = patch("astroweave.api.main._user_profile", return_value={"email": "demo-user", "birth_details": {}})
        profile.start()
        self.addCleanup(profile.stop)

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
        mock_store.request_ids.return_value = None
        mock_store.load_context_messages.return_value = ([], [])
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
        self.assertEqual(context["username"], "demo-user")
        mock_store.persist_turn.assert_called_once()
        self.assertTrue(mock_store.persist_turn.call_args.kwargs["user_message_id"])

    @patch("astroweave.api.main._orchestrator_graph")
    @patch("astroweave.api.main._conversation_store")
    def test_run_replays_an_idempotent_response(self, mock_store, mock_graph):
        mock_store.request_ids.return_value = ("conversation-1", "session-1")
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
        mock_store.request_ids.return_value = None
        mock_store.load_context_messages.return_value = ([], [])
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
        mock_store.request_ids.return_value = None
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

    def test_connector_register_dag_persist_retry_and_direct_route(self):
        with tempfile.TemporaryDirectory() as directory:
            user_db = Path(directory) / "users.db"
            store = ConversationStore(Path(directory) / "conversations.db")
            orchestrator_llm = MagicMock()
            orchestrator_llm.invoke.side_effect = [
                MagicMock(content=json.dumps({
                    "specialists": ["career", "finance"],
                    "tasks": [
                        {"specialist": "career", "depends_on": []},
                        {"specialist": "finance", "depends_on": ["career"]},
                    ],
                    "methodology": "vedic", "reasoning": "Career and finance",
                })),
                MagicMock(content="Combined reading"),
            ]
            specialist_llm = MagicMock()
            specialist_llm.invoke.return_value = MagicMock(content=json.dumps({
                "analysis": "Analysis", "conclusion": "Individual reading", "confidence": "high",
            }))
            birth = {
                "date": "1990-01-01", "time": "10:00:00", "latitude": 13.08,
                "longitude": 80.27, "utc_offset_hours": 5.5, "place_name": "Chennai",
            }
            with patch("app.auth.DB_PATH", user_db), \
                 patch("astroweave.api.main._conversation_store", store), \
                 patch("astroweave.api.main._user_profile", side_effect=lambda username: self._real_profile(username)), \
                 patch("astroweave.graphs.orchestrator.orchestrator_graph.get_llm", return_value=orchestrator_llm), \
                 patch("astroweave.graphs.specialist.specialist_graph.get_llm", return_value=specialist_llm), \
                 patch("astroweave.orchestration.dispatcher.dispatcher.get_birth_chart", return_value={"d1": {}}) as chart, \
                 patch.dict("os.environ", {"ASTROWEAVE_APP_ROUTES": '{"career-app":"career"}'}):
                registration = self.client.post("/auth/register", json={
                    "email": "demo-user", "name": "Demo", "password": "securepass123",
                    "birth_details": birth,
                })
                self.assertEqual(registration.status_code, 200)
                headers = {"Authorization": f"Bearer {registration.json()['token']}"}
                request = {"query": "How will my job affect my finances?", "message_id": "first-message"}
                response = self.client.post("/run", json=request, headers=headers)
                self.assertEqual(response.status_code, 200, response.text)
                body = response.json()
                self.assertEqual(body["answer"], "Combined reading")
                self.assertEqual(body["state"]["completed_tasks"], ["career", "finance"])
                self.assertEqual(
                    [result["specialist"] for result in body["state"]["specialist_results"]],
                    ["career", "finance"],
                )
                self.assertIn(
                    "career", specialist_llm.invoke.call_args_list[1].args[0][1].content,
                )
                self.assertTrue(body["state"]["history_persisted"])
                self.assertEqual(chart.call_count, 1)
                replay = self.client.post("/run", json=request, headers=headers)
                self.assertEqual(replay.status_code, 200, replay.text)
                self.assertTrue(replay.json()["state"]["history_replayed"])
                self.assertEqual(replay.json()["conversation_id"], body["conversation_id"])
                self.assertEqual(orchestrator_llm.invoke.call_count, 2)
                messages = self.client.get(f"/conversations/{body['conversation_id']}/messages", headers=headers)
                self.assertEqual(len(messages.json()["messages"]), 2)

                direct = self.client.post("/run", json={
                    "query": "Career follow-up", "app_id": "career-app",
                    "conversation_id": body["conversation_id"], "session_id": body["session_id"],
                }, headers=headers)
                self.assertEqual(direct.status_code, 200, direct.text)
                self.assertEqual(direct.json()["answer"], "Individual reading")
                self.assertEqual(orchestrator_llm.invoke.call_count, 2)
                self.assertEqual(len(self.client.get(
                    f"/conversations/{body['conversation_id']}/messages", headers=headers,
                ).json()["messages"]), 4)

    @staticmethod
    def _real_profile(username):
        from app import auth
        with auth.get_connection() as connection:
            return auth.get_user(connection, username)

    def test_specialist_service_requires_auth_and_dispatches_only_registered_names(self):
        client = TestClient(specialist_app)
        payload = {"user_query": "Question", "chart_data": {"d1": {}}}
        self.assertEqual(client.post("/specialists/career/run", json=payload).status_code, 401)
        self.assertEqual(client.post(
            "/specialists/unknown/run", json=payload, headers=self._headers(),
        ).status_code, 404)
        with patch("astroweave.specialist_service.graph") as graph:
            graph.invoke.return_value = {"specialist_results": []}
            response = client.post("/specialists/career/run", json=payload, headers=self._headers())
            self.assertEqual(response.status_code, 200)
            self.assertEqual(graph.invoke.call_args.args[0]["current_task"], "career")

    def test_unconfigured_app_id_cannot_bypass_planning(self):
        response = self.client.post("/run", json={"query": "Question", "app_id": "unknown"}, headers=self._headers())
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()

