import json
import unittest
from unittest.mock import MagicMock, patch

from astroweave.graphs.orchestrator.orchestrator_graph import (
    build_orchestrator_graph,
)


class OrchestratorGraphTests(unittest.TestCase):
    @patch("astroweave.graphs.orchestrator.orchestrator_graph.execute_specialist")
    @patch("astroweave.graphs.orchestrator.orchestrator_graph.get_llm")
    def test_full_run_produces_a_synthesized_answer(self, mock_get_llm, mock_execute):
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
        mock_execute.return_value = {
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
        self.assertEqual(result["pending_tasks"], [])
        self.assertEqual(result["completed_tasks"], ["career"])
        mock_execute.assert_called_once()
        classifier_messages = llm.invoke.call_args_list[0].args[0]
        self.assertIn("Birth details available: yes", classifier_messages[1].content)

    @patch("astroweave.graphs.orchestrator.orchestrator_graph.execute_specialist")
    @patch("astroweave.graphs.orchestrator.orchestrator_graph.get_llm")
    def test_executes_each_planned_task_before_synthesis(self, mock_get_llm, mock_execute):
        llm = MagicMock()
        llm.invoke.side_effect = [
            MagicMock(content=json.dumps({
                "specialists": ["career", "finance"],
                "methodology": "both",
                "reasoning": "The question spans work and money.",
            })),
            MagicMock(content="Combined answer."),
        ]
        mock_get_llm.return_value = llm

        def execute(state, runtime, specialist_name):
            return {
                "chart_data": {"d1": {}},
                "specialist_results": [{
                    "specialist": specialist_name,
                    "analysis": f"{specialist_name} analysis",
                    "conclusion": f"{specialist_name} conclusion",
                    "confidence": "high",
                }],
                "errors": [],
            }

        mock_execute.side_effect = execute
        graph = build_orchestrator_graph()
        result = graph.invoke(
            {"user_query": "How will my promotion affect my finances?"},
            context={"birth_details": {"date": "1990-01-01"}},
        )

        self.assertEqual(
            [call.args[2] for call in mock_execute.call_args_list],
            ["career", "finance"],
        )
        self.assertEqual(result["completed_tasks"], ["career", "finance"])
        self.assertEqual(len(result["specialist_results"]), 2)
        self.assertEqual(result["answer"], "Combined answer.")

    @patch("astroweave.graphs.orchestrator.orchestrator_graph.execute_specialist")
    @patch("astroweave.graphs.orchestrator.orchestrator_graph.get_llm")
    def test_continues_queue_after_one_specialist_fails(self, mock_get_llm, mock_execute):
        llm = MagicMock()
        llm.invoke.side_effect = [
            MagicMock(content=json.dumps({
                "specialists": ["career", "finance"],
                "methodology": "vedic",
                "reasoning": "Both domains are relevant.",
            })),
            MagicMock(content="Finance-only synthesis."),
        ]
        mock_get_llm.return_value = llm
        mock_execute.side_effect = [
            {"errors": ["career specialist failed"], "specialist_results": []},
            {
                "errors": [],
                "specialist_results": [{
                    "specialist": "finance",
                    "analysis": "analysis",
                    "conclusion": "conclusion",
                    "confidence": "high",
                }],
            },
        ]

        result = build_orchestrator_graph().invoke(
            {"user_query": "Question"},
            context={"birth_details": {"date": "1990-01-01"}},
        )

        self.assertEqual(mock_execute.call_count, 2)
        self.assertEqual(result["completed_tasks"], ["career", "finance"])
        self.assertIn("career specialist failed", result["errors"])
        self.assertEqual(result["answer"], "Finance-only synthesis.")

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

    @patch("astroweave.graphs.orchestrator.orchestrator_graph.execute_specialist")
    @patch("astroweave.graphs.orchestrator.orchestrator_graph.get_llm")
    def test_unregistered_specialist_is_not_dispatched(
        self, mock_get_llm, mock_execute
    ):
        mock_get_llm.return_value = MagicMock()
        mock_get_llm.return_value.invoke.return_value = MagicMock(
            content=json.dumps(
                {
                    "specialists": ["invented"],
                    "methodology": "vedic",
                    "reasoning": "Unsupported domain.",
                }
            )
        )

        result = build_orchestrator_graph().invoke({"user_query": "Question"})

        mock_execute.assert_not_called()
        self.assertEqual(result["specialists"], [])
        self.assertIn("No specialist", result["answer"])

    @patch("astroweave.graphs.orchestrator.orchestrator_graph.execute_specialist")
    @patch("astroweave.graphs.orchestrator.orchestrator_graph.get_llm")
    def test_loads_both_history_scopes_and_persists_final_turn(
        self, mock_get_llm, mock_execute
    ):
        store = MagicMock()
        store.load_context_messages.return_value = (
            [{"message_id": "old-1", "role": "user", "content": "Earlier context"}],
            [{"message_id": "session-1", "role": "assistant", "content": "Recent answer"}],
        )
        llm = MagicMock()
        llm.invoke.side_effect = [
            MagicMock(content=json.dumps({
                "specialists": ["career"],
                "methodology": "vedic",
                "reasoning": "Career follow-up.",
            })),
            MagicMock(content="Follow-up response."),
        ]
        mock_get_llm.return_value = llm
        mock_execute.return_value = {
            "specialist_results": [{
                "specialist": "career",
                "analysis": "analysis",
                "conclusion": "conclusion",
                "confidence": "high",
            }],
            "errors": [],
        }

        result = build_orchestrator_graph().invoke(
            {"user_query": "What about timing?"},
            context={
                "conversation_id": "conversation-1",
                "session_id": "session-2",
                "username": "user@example.com",
                "message_id": "message-2",
                "conversation_store": store,
                "request_claim_token": "claim-token",
            },
        )

        classifier_content = llm.invoke.call_args_list[0].args[0][1].content
        self.assertIn("Earlier context", classifier_content)
        self.assertIn("Recent answer", classifier_content)
        self.assertEqual(result["conversation_history"][0]["content"], "Earlier context")
        self.assertEqual(result["session_history"][0]["content"], "Recent answer")
        self.assertTrue(result["history_persisted"])
        store.persist_turn.assert_called_once_with(
            conversation_id="conversation-1",
            session_id="session-2",
            owner="user@example.com",
            user_message_id="message-2",
            user_content="What about timing?",
            assistant_content="Follow-up response.",
            request_fingerprint=None,
            claim_token="claim-token",
        )


if __name__ == "__main__":
    unittest.main()
