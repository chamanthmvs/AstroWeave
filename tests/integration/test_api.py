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
        # Keep the real rate-limit DB out of the tests; allow by default.
        from astroweave.common.ratelimit import RateLimitResult

        limiter = patch("astroweave.api.main._rate_limiter")
        self.rate_limiter = limiter.start()
        self.addCleanup(limiter.stop)
        self.rate_limiter.check_and_consume.return_value = RateLimitResult(allowed=True)
        # Keep the real usage DB out of the tests.
        usage = patch("astroweave.api.main._usage_store")
        self.usage_store = usage.start()
        self.usage_store.record_run.return_value = 0.0  # fed into round(float(...)) in /run
        self.addCleanup(usage.stop)
        # Isolate the per-user chart cache so tests always "miss" and don't touch the real DB.
        cache = patch("astroweave.api.main._chart_cache")
        self.chart_cache = cache.start()
        self.chart_cache.get.return_value = None
        self.addCleanup(cache.stop)

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

    @patch("astroweave.api.main._orchestrator_graph")
    @patch("astroweave.api.main._conversation_store")
    def test_run_returns_503_when_chart_service_is_unavailable(self, mock_store, mock_graph):
        from astroweave.common.tools.chart_client import ChartServiceUnavailable

        mock_store.request_ids.return_value = None
        mock_store.load_context_messages.return_value = ([], [])
        mock_store.claim_request.return_value = ("claim-token", None)
        mock_graph.invoke.side_effect = ChartServiceUnavailable("chart service is down")

        response = self.client.post(
            "/run",
            json={"query": "Will I get a new job this year?", "username": "demo-user"},
            headers=self._headers(),
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"]["code"], "chart_service_unavailable")
        # A failed run must release its claim so a retry is not rejected as in-progress.
        mock_store.release_request.assert_called_once()

    @patch("astroweave.api.main._orchestrator_graph")
    @patch("astroweave.api.main._conversation_store")
    def test_run_includes_an_execution_trace(self, mock_store, mock_graph):
        mock_store.request_ids.return_value = None
        mock_store.load_context_messages.return_value = ([], [])
        mock_store.claim_request.return_value = ("claim-token", None)
        mock_graph.invoke.return_value = {
            "answer": "Steady progress ahead.",
            "methodology": "both",
            "specialists": ["career", "finance"],
            "specialist_results": [
                {"specialist": "career", "analysis": "…", "conclusion": "Promotion likely.", "confidence": "high"},
                {"specialist": "finance", "analysis": "…", "conclusion": "Gains likely.", "confidence": "medium"},
            ],
            "errors": [],
        }

        response = self.client.post(
            "/run",
            json={"query": "Career and finances this year?", "username": "demo-user"},
            headers=self._headers(),
        )

        self.assertEqual(response.status_code, 200)
        trace = response.json()["execution_trace"]
        self.assertEqual(trace[0]["step"], "plan")
        self.assertEqual(trace[0]["specialists"], ["career", "finance"])
        specialist_steps = [step for step in trace if step["step"] == "specialist"]
        self.assertEqual([step["specialist"] for step in specialist_steps], ["career", "finance"])
        self.assertEqual(specialist_steps[0]["conclusion"], "Promotion likely.")

    @patch("astroweave.api.main._orchestrator_graph")
    @patch("astroweave.api.main._conversation_store")
    def test_run_records_token_usage(self, mock_store, mock_graph):
        mock_store.request_ids.return_value = None
        mock_store.load_context_messages.return_value = ([], [])
        mock_store.claim_request.return_value = ("claim-token", None)
        mock_graph.invoke.return_value = {
            "answer": "ok",
            "token_usage": [{"model": "claude-opus-5-5", "input_tokens": 1000, "output_tokens": 500, "cache_read_tokens": 0}],
        }

        response = self.client.post(
            "/run",
            json={"query": "Will I get a new job this year?", "username": "demo-user"},
            headers=self._headers(),
        )

        self.assertEqual(response.status_code, 200)
        self.usage_store.record_run.assert_called_once()
        args = self.usage_store.record_run.call_args.args
        self.assertEqual(args[0], "demo-user")  # owner
        self.assertEqual(args[3][0]["model"], "claude-opus-5-5")  # usage list passed through

    @patch("astroweave.api.main._orchestrator_graph")
    @patch("astroweave.api.main._conversation_store")
    def test_run_refused_when_rate_limited(self, mock_store, mock_graph):
        from astroweave.common.ratelimit import RateLimitResult

        mock_store.request_ids.return_value = None
        mock_store.claim_request.return_value = ("claim-token", None)
        self.rate_limiter.check_and_consume.return_value = RateLimitResult(
            allowed=False, scope="user", limit=50, used=50, retry_after_seconds=3600
        )

        response = self.client.post(
            "/run",
            json={"query": "Will I get a new job this year?", "username": "demo-user"},
            headers=self._headers(),
        )

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["detail"]["code"], "rate_limited")
        self.assertEqual(response.headers["Retry-After"], "3600")
        # The expensive model run must not happen, and the claim is released for retry.
        mock_graph.invoke.assert_not_called()
        mock_store.release_request.assert_called_once()

    @patch("astroweave.api.main._orchestrator_graph")
    @patch("astroweave.api.main._conversation_store")
    def test_idempotent_replay_does_not_consume_budget(self, mock_store, mock_graph):
        mock_store.request_ids.return_value = ("conversation-1", "session-1")
        mock_store.claim_request.return_value = (None, "Saved answer")

        response = self.client.post(
            "/run",
            json={"query": "Question", "conversation_id": "conversation-1",
                  "session_id": "session-1", "message_id": "message-1", "username": "demo-user"},
            headers=self._headers(),
        )

        self.assertEqual(response.status_code, 200)
        self.rate_limiter.check_and_consume.assert_not_called()

    @patch("astroweave.api.main._conversation_store")
    def test_usage_endpoint_reports_quota(self, _mock_store):
        self.rate_limiter.usage_today.return_value = {
            "day": "2026-10-16", "resets_in_seconds": 3600,
            "user": {"used": 2, "limit": 50, "remaining": 48},
            "global": {"used": 2, "limit": None, "remaining": None},
        }

        response = self.client.get("/usage", headers=self._headers())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["user"]["remaining"], 48)
        self.rate_limiter.usage_today.assert_called_once_with("demo-user")

    def test_admin_summary_requires_an_admin_email(self):
        self.usage_store.summary.return_value = {"overall": {"runs": 0}, "by_user": [], "by_day": [], "by_model": []}
        # demo-user is not in the (empty) admin allowlist.
        with patch.dict("os.environ", {"ASTROWEAVE_ADMIN_EMAILS": ""}):
            forbidden = self.client.get("/admin/summary", headers=self._headers())
        self.assertEqual(forbidden.status_code, 403)
        self.usage_store.summary.assert_not_called()

        with patch.dict("os.environ", {"ASTROWEAVE_ADMIN_EMAILS": "boss@astroweave.com, demo-user"}):
            allowed = self.client.get("/admin/summary", headers=self._headers())
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(allowed.json()["overall"]["runs"], 0)
        self.usage_store.summary.assert_called_once()

    def test_admin_summary_requires_a_token(self):
        self.assertEqual(self.client.get("/admin/summary").status_code, 401)

    def test_config_reports_readings_flag(self):
        with patch.dict("os.environ", {"ASTROWEAVE_ENABLE_READINGS": "false"}):
            body = self.client.get("/config").json()
        self.assertFalse(body["readings_enabled"])
        self.assertIsInstance(body["readings_disabled_message"], str)

    def test_run_disabled_on_free_tier(self):
        with patch.dict("os.environ", {"ASTROWEAVE_ENABLE_READINGS": "false"}):
            r = self.client.post("/run", json={"query": "hi", "message_id": "m-off"}, headers=self._headers())
        self.assertEqual(r.status_code, 503)
        self.assertEqual(r.json()["detail"]["code"], "readings_disabled")

    def test_full_chart_disabled_on_free_tier(self):
        with patch.dict("os.environ", {"ASTROWEAVE_ENABLE_READINGS": "false"}):
            r = self.client.get("/me/chart/full", headers=self._headers())
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "disabled")

    def test_ready_reports_chart_service(self):
        # Chart service isn't running in tests -> reachable key, value False.
        response = self.client.get("/ready")
        self.assertEqual(response.status_code, 200)
        self.assertIn("chart_service", response.json())
        self.assertIsInstance(response.json()["chart_service"], bool)

    def test_root_is_api_only(self):
        # Backend is API-only now; the frontend is the separate Next.js app.
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["service"], "astroweave-api")

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
        # The run reuses the user's cached full chart; pretend it's already cached.
        self.chart_cache.get.return_value = {"d1": {}}
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
                 patch("astroweave.api.main.get_birth_chart", return_value={"d1": {}}) as chart, \
                 patch.dict("os.environ", {"ASTROWEAVE_APP_ROUTES": '{"career-app":"career"}', "ASTROWEAVE_SIGNUP_MODE": "open", "ASTROWEAVE_ALLOWED_EMAIL_DOMAINS": ""}):
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

    _BIRTH = {"date": "1990-01-01", "time": "12:00:00", "place_name": "Chennai",
              "latitude": 13.08, "longitude": 80.27, "utc_offset_hours": 5.5, "date_known": True}

    def test_me_chart_summary_returns_rasi_nakshatra_lagna(self):
        with patch("astroweave.api.main._user_profile", return_value={"email": "demo-user", "birth_details": self._BIRTH}), \
             patch("astroweave.api.main.get_birth_chart", return_value={"d1": {}}), \
             patch("astroweave.api.main.build_chart_view", return_value={"summary": {
                 "moon_sign": "Aquarius", "janma_nakshatra": "Dhanishta pada 4 (lord Mars)",
                 "lagna": "Pisces", "lagna_degree": 16.47, "sun_sign": "Sagittarius"}}):
            response = self.client.get("/me/chart", headers=self._headers())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "rasi": "Aquarius", "nakshatra": "Dhanishta pada 4 (lord Mars)",
            "lagna": "Pisces", "lagna_degree": 16.47, "sun_sign": "Sagittarius"})

    def test_me_chart_requires_birth_details(self):
        with patch("astroweave.api.main._user_profile", return_value={"email": "demo-user", "birth_details": {}}):
            self.assertEqual(self.client.get("/me/chart", headers=self._headers()).status_code, 404)

    def test_me_chart_503_when_chart_service_down(self):
        from astroweave.common.tools.chart_client import ChartServiceUnavailable
        with patch("astroweave.api.main._user_profile", return_value={"email": "demo-user", "birth_details": self._BIRTH}), \
             patch("astroweave.api.main.get_birth_chart", side_effect=ChartServiceUnavailable("down")):
            self.assertEqual(self.client.get("/me/chart", headers=self._headers()).status_code, 503)

    def test_match_passes_user_and_partner_to_chart_service(self):
        partner = {"date": "1992-05-20", "time": "08:30:00", "place_name": "Mumbai",
                   "latitude": 19.08, "longitude": 72.88, "utc_offset_hours": 5.5}
        canned = {"north": {"total": 24.0, "out_of": 36}, "south": {"matched_count": 7, "out_of": 10}}
        with patch("astroweave.api.main._user_profile", return_value={"email": "demo-user", "birth_details": self._BIRTH}), \
             patch("astroweave.api.main.match_charts", return_value=canned) as mock_match:
            response = self.client.post("/match", json={"partner": partner, "person_is_groom": False}, headers=self._headers())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["north"]["total"], 24.0)
        person_arg = mock_match.call_args.args[0]
        self.assertNotIn("date_known", person_arg)  # stripped before sending
        self.assertEqual(person_arg["place_name"], "Chennai")
        self.assertFalse(mock_match.call_args.kwargs["person_is_groom"])


class PasswordResetTests(unittest.TestCase):
    """End-to-end reset/change-password against a real temp auth DB (no LLM)."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def setUp(self):
        import tempfile
        from pathlib import Path
        from app import auth

        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        db = Path(self._dir.name) / "auth.db"
        conn = auth.get_connection(db)
        auth.create_user(conn, "u@example.com", "U", "original-pass-1", {
            "date": "1990-01-01", "time": "12:00:00", "place_name": "Chennai",
            "latitude": 13.08, "longitude": 80.27, "utc_offset_hours": 5.5, "date_known": True,
        })
        conn.close()
        patcher = patch("app.auth.DB_PATH", db)
        patcher.start()
        self.addCleanup(patcher.stop)
        secret = patch.dict("os.environ", {"ASTROWEAVE_AUTH_SECRET": "reset-test-secret"})
        secret.start()
        self.addCleanup(secret.stop)

    def _token(self, username="u@example.com"):
        from astroweave.common.security import create_user_token
        return {"Authorization": f"Bearer {create_user_token(username)}"}

    def test_request_reset_is_generic_for_any_email(self):
        known = self.client.post("/auth/request-reset", json={"email": "u@example.com"})
        unknown = self.client.post("/auth/request-reset", json={"email": "nobody@example.com"})
        # Identical response => no account enumeration.
        self.assertEqual(known.status_code, 200)
        self.assertEqual(known.json(), unknown.json())

    def test_admin_can_mint_a_reset_token_and_it_resets_the_password(self):
        from astroweave.common.security import create_user_token

        with patch.dict("os.environ", {"ASTROWEAVE_ADMIN_EMAILS": "admin@astroweave.com"}):
            minted = self.client.post(
                "/admin/reset-token", json={"email": "u@example.com"},
                headers={"Authorization": f"Bearer {create_user_token('admin@astroweave.com')}"},
            )
        self.assertEqual(minted.status_code, 200)
        token = minted.json()["reset_token"]

        ok = self.client.post("/auth/reset", json={"token": token, "new_password": "brand-new-pass-9"})
        self.assertEqual(ok.status_code, 200)
        # New password works; the token is now single-use (spent).
        self.assertEqual(self.client.post("/auth/sign-in", json={"email": "u@example.com", "password": "brand-new-pass-9"}).status_code, 200)
        reused = self.client.post("/auth/reset", json={"token": token, "new_password": "another-pass-10"})
        self.assertEqual(reused.status_code, 400)

    def test_reset_rejects_short_password_and_bad_token(self):
        self.assertEqual(self.client.post("/auth/reset", json={"token": "x.y.z", "new_password": "longenough1"}).status_code, 400)
        from astroweave.common.security import create_reset_token
        from app import auth
        with auth.get_connection() as conn:
            token = create_reset_token("u@example.com", auth.get_password_hash(conn, "u@example.com"))
        self.assertEqual(self.client.post("/auth/reset", json={"token": token, "new_password": "short"}).status_code, 422)

    def test_change_password_requires_the_correct_current_password(self):
        wrong = self.client.post("/auth/change-password", json={"current_password": "nope", "new_password": "new-pass-1234"}, headers=self._token())
        self.assertEqual(wrong.status_code, 403)
        ok = self.client.post("/auth/change-password", json={"current_password": "original-pass-1", "new_password": "new-pass-1234"}, headers=self._token())
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(self.client.post("/auth/sign-in", json={"email": "u@example.com", "password": "new-pass-1234"}).status_code, 200)

    def test_admin_reset_token_requires_admin(self):
        with patch.dict("os.environ", {"ASTROWEAVE_ADMIN_EMAILS": ""}):
            r = self.client.post("/admin/reset-token", json={"email": "u@example.com"}, headers=self._token())
        self.assertEqual(r.status_code, 403)

    def test_registration_user_starts_unverified_then_verifies(self):
        from astroweave.common.security import create_verification_token

        with patch.dict("os.environ", {"ASTROWEAVE_SIGNUP_MODE": "open", "ASTROWEAVE_ALLOWED_EMAIL_DOMAINS": ""}):
            registration = self.client.post("/auth/register", json={
                "email": "new@example.com", "name": "New", "password": "securepass123",
                "birth_details": {
                    "date": "1992-02-02", "time": "09:30:00", "place_name": "Mumbai",
                    "latitude": 19.07, "longitude": 72.88, "utc_offset_hours": 5.5, "date_known": True,
                },
            })
        self.assertEqual(registration.status_code, 200, registration.text)
        self.assertFalse(registration.json()["user"]["email_verified"])
        self.assertIn("email_verification", registration.json())

        # The link carries a verification token; confirm it flips the flag.
        token = create_verification_token("new@example.com")
        verified = self.client.post("/auth/verify", json={"token": token})
        self.assertEqual(verified.status_code, 200, verified.text)
        me = self.client.get("/auth/me", headers=self._token("new@example.com"))
        self.assertTrue(me.json()["user"]["email_verified"])

    def test_verify_rejects_an_invalid_token(self):
        self.assertEqual(self.client.post("/auth/verify", json={"token": "garbage"}).status_code, 400)

    def test_run_blocks_unverified_users_only_when_verification_is_required(self):
        # u@example.com was created unverified in setUp.
        with patch.dict("os.environ", {"ASTROWEAVE_REQUIRE_EMAIL_VERIFICATION": "true"}):
            blocked = self.client.post(
                "/run", json={"query": "hello", "message_id": "m-gate"}, headers=self._token(),
            )
        self.assertEqual(blocked.status_code, 403, blocked.text)
        self.assertEqual(blocked.json()["detail"]["code"], "email_unverified")

    _BIRTH = {
        "date": "1991-03-03", "time": "08:00:00", "place_name": "Delhi",
        "latitude": 28.61, "longitude": 77.21, "utc_offset_hours": 5.5, "date_known": True,
    }

    def _register(self, email):
        return self.client.post("/auth/register", json={
            "email": email, "name": "X", "password": "securepass123", "birth_details": self._BIRTH,
        })

    def _admin_headers(self, email="astroweaveastrology@gmail.com"):
        from astroweave.common.security import create_user_token
        return {"Authorization": f"Bearer {create_user_token(email)}"}

    def test_invite_only_blocks_strangers_and_allows_after_admin_grant(self):
        # Default mode is invite: an unlisted (but valid Gmail) email is refused.
        self.assertEqual(self._register("stranger@gmail.com").status_code, 403)

        admin = "astroweaveastrology@gmail.com"
        with patch.dict("os.environ", {"ASTROWEAVE_ADMIN_EMAILS": admin}):
            granted = self.client.post(
                "/admin/allowlist", json={"email": "stranger@gmail.com"}, headers=self._admin_headers(admin),
            )
            self.assertEqual(granted.status_code, 200, granted.text)
            listed = self.client.get("/admin/allowlist", headers=self._admin_headers(admin)).json()
            self.assertIn("stranger@gmail.com", [row["email"] for row in listed["allowed"]])

        # Now the same email may register.
        self.assertEqual(self._register("stranger@gmail.com").status_code, 200)

    def test_access_status_reports_invite_and_domain(self):
        # Not invited -> allowed false (invite reason); non-gmail -> domain reason.
        unlisted = self.client.get("/auth/access-status", params={"email": "nobody@gmail.com"}).json()
        self.assertEqual((unlisted["allowed"], unlisted["reason"]), (False, "invite"))
        bad = self.client.get("/auth/access-status", params={"email": "nobody@outlook.com"}).json()
        self.assertEqual((bad["allowed"], bad["reason"]), (False, "domain"))
        admin = "astroweaveastrology@gmail.com"
        with patch.dict("os.environ", {"ASTROWEAVE_ADMIN_EMAILS": admin}):
            ok = self.client.get("/auth/access-status", params={"email": admin}).json()
            self.assertTrue(ok["allowed"])

    def test_non_gmail_is_rejected_on_register_and_request_access(self):
        self.assertEqual(self._register("someone@outlook.com").status_code, 422)
        self.assertEqual(
            self.client.post("/auth/request-access", json={"email": "someone@outlook.com"}).status_code, 422
        )

    def test_request_access_is_recorded_and_admin_can_approve(self):
        asked = self.client.post(
            "/auth/request-access", json={"email": "hopeful@gmail.com", "name": "Hopeful", "note": "please!"},
        )
        self.assertEqual(asked.status_code, 200, asked.text)

        admin = "astroweaveastrology@gmail.com"
        with patch.dict("os.environ", {"ASTROWEAVE_ADMIN_EMAILS": admin}):
            listed = self.client.get("/admin/access-requests", headers=self._admin_headers(admin)).json()
            self.assertIn("hopeful@gmail.com", [r["email"] for r in listed["requests"]])
            approved = self.client.post(
                "/admin/access-requests/hopeful@gmail.com/approve", headers=self._admin_headers(admin),
            )
            self.assertEqual(approved.status_code, 200)
            # Request cleared, email now allowlisted.
            after = self.client.get("/admin/access-requests", headers=self._admin_headers(admin)).json()
            self.assertNotIn("hopeful@gmail.com", [r["email"] for r in after["requests"]])
        self.assertEqual(self._register("hopeful@gmail.com").status_code, 200)

    def test_admin_email_can_always_register(self):
        admin = "astroweaveastrology@gmail.com"
        with patch.dict("os.environ", {"ASTROWEAVE_ADMIN_EMAILS": admin}):
            self.assertEqual(self._register(admin).status_code, 200)

    def test_allowlist_endpoints_require_admin(self):
        with patch.dict("os.environ", {"ASTROWEAVE_ADMIN_EMAILS": "someone-else@astroweave.com"}):
            self.assertEqual(
                self.client.post("/admin/allowlist", json={"email": "x@example.com"}, headers=self._token()).status_code,
                403,
            )
            self.assertEqual(self.client.get("/admin/allowlist", headers=self._token()).status_code, 403)


if __name__ == "__main__":
    unittest.main()

