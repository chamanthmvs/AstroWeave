import tempfile
import unittest
from pathlib import Path

from astroweave.common.conversation import (
    ConversationAccessError,
    ConversationConflictError,
    ConversationInProgressError,
    ConversationStore,
)


class ConversationStoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.store = ConversationStore(
            Path(self.temporary_directory.name) / "conversations.db"
        )

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_persists_and_loads_a_turn_in_order(self):
        persisted = self.store.persist_turn(
            conversation_id="conversation-1",
            session_id="session-1",
            owner="user@example.com",
            user_message_id="message-1",
            user_content="Will I get promoted?",
            assistant_content="A promotion is likely.",
        )

        messages = self.store.load_recent_messages(
            "conversation-1", "user@example.com"
        )

        self.assertTrue(persisted)
        self.assertEqual([message["role"] for message in messages], ["user", "assistant"])
        self.assertEqual(messages[0]["content"], "Will I get promoted?")
        self.assertEqual(messages[1]["content"], "A promotion is likely.")

    def test_recent_message_limit_returns_latest_messages_in_chat_order(self):
        for index in range(3):
            self.store.persist_turn(
                conversation_id="conversation-1",
                session_id="session-1",
                owner="user@example.com",
                user_message_id=f"message-{index}",
                user_content=f"question {index}",
                assistant_content=f"answer {index}",
            )

        messages = self.store.load_recent_messages(
            "conversation-1", "user@example.com", limit=3
        )

        self.assertEqual(
            [message["content"] for message in messages],
            ["answer 1", "question 2", "answer 2"],
        )

    def test_rejects_access_by_another_owner(self):
        self.store.persist_turn(
            conversation_id="conversation-1",
            session_id="session-1",
            owner="first@example.com",
            user_message_id="message-1",
            user_content="private question",
            assistant_content="private answer",
        )

        with self.assertRaises(ConversationAccessError):
            self.store.load_recent_messages("conversation-1", "second@example.com")

    def test_separates_current_session_from_prior_conversation_history(self):
        self.store.persist_turn(
            conversation_id="conversation-1",
            session_id="session-1",
            owner="user@example.com",
            user_message_id="message-1",
            user_content="Earlier question",
            assistant_content="Earlier answer",
        )
        self.store.persist_turn(
            conversation_id="conversation-1",
            session_id="session-2",
            owner="user@example.com",
            user_message_id="message-2",
            user_content="Current question",
            assistant_content="Current answer",
        )

        conversation_history, session_history = self.store.load_context_messages(
            conversation_id="conversation-1",
            session_id="session-2",
            owner="user@example.com",
        )

        self.assertEqual(
            [message["content"] for message in conversation_history],
            ["Earlier question", "Earlier answer"],
        )
        self.assertEqual(
            [message["content"] for message in session_history],
            ["Current question", "Current answer"],
        )

    def test_duplicate_user_message_is_not_persisted_twice(self):
        values = {
            "conversation_id": "conversation-1",
            "session_id": "session-1",
            "owner": "user@example.com",
            "user_message_id": "message-1",
            "user_content": "question",
            "assistant_content": "answer",
        }

        self.assertTrue(self.store.persist_turn(**values))
        self.assertFalse(self.store.persist_turn(**values))
        self.assertEqual(
            len(self.store.load_recent_messages("conversation-1", "user@example.com")),
            2,
        )
        self.assertEqual(
            self.store.get_persisted_response(
                conversation_id="conversation-1",
                owner="user@example.com",
                user_message_id="message-1",
            ),
            "answer",
        )

    def test_lists_only_the_owners_conversations(self):
        self.store.persist_turn(
            conversation_id="conversation-1",
            session_id="session-1",
            owner="first@example.com",
            user_message_id="message-1",
            user_content="My career question",
            assistant_content="answer",
        )
        self.store.persist_turn(
            conversation_id="conversation-2",
            session_id="session-2",
            owner="second@example.com",
            user_message_id="message-2",
            user_content="Another question",
            assistant_content="answer",
        )

        conversations = self.store.list_conversations("first@example.com")

        self.assertEqual(len(conversations), 1)
        self.assertEqual(conversations[0]["conversation_id"], "conversation-1")
        self.assertEqual(conversations[0]["title"], "My career question")

    def test_deletes_only_an_owned_conversation(self):
        self.store.persist_turn(
            conversation_id="conversation-1",
            session_id="session-1",
            owner="user@example.com",
            user_message_id="message-1",
            user_content="question",
            assistant_content="answer",
        )

        with self.assertRaises(ConversationAccessError):
            self.store.delete_conversation("conversation-1", "another@example.com")

        self.assertTrue(
            self.store.delete_conversation("conversation-1", "user@example.com")
        )
        self.assertEqual(self.store.list_conversations("user@example.com"), [])

    def test_deletion_removes_completed_request_replay(self):
        claim = {
            "conversation_id": "conversation-1",
            "session_id": "session-1",
            "owner": "user@example.com",
            "message_id": "message-1",
            "request_fingerprint": "fingerprint-1",
        }
        claim_token, _ = self.store.claim_request(**claim)
        self.store.persist_turn(
            conversation_id="conversation-1",
            session_id="session-1",
            owner="user@example.com",
            user_message_id="message-1",
            user_content="question",
            assistant_content="answer",
            request_fingerprint="fingerprint-1",
            claim_token=claim_token,
        )

        self.store.delete_conversation("conversation-1", "user@example.com")

        new_claim_token, answer = self.store.claim_request(**claim)
        self.assertIsNotNone(new_claim_token)
        self.assertIsNone(answer)

    def test_claims_completes_and_replays_a_request(self):
        claim = {
            "conversation_id": "conversation-1",
            "session_id": "session-1",
            "owner": "user@example.com",
            "message_id": "message-1",
            "request_fingerprint": "fingerprint-1",
        }

        claim_token, answer = self.store.claim_request(**claim)
        self.assertIsNotNone(claim_token)
        self.assertIsNone(answer)
        with self.assertRaises(ConversationInProgressError):
            self.store.claim_request(**claim)
        self.store.persist_turn(
            conversation_id="conversation-1",
            session_id="session-1",
            owner="user@example.com",
            user_message_id="message-1",
            user_content="question",
            assistant_content="canonical answer",
            request_fingerprint="fingerprint-1",
            claim_token=claim_token,
        )

        self.assertEqual(self.store.claim_request(**claim), (None, "canonical answer"))

    def test_rejects_reused_message_id_with_different_request_data(self):
        self.store.claim_request(
            conversation_id="conversation-1",
            session_id="session-1",
            owner="user@example.com",
            message_id="message-1",
            request_fingerprint="fingerprint-1",
        )

        with self.assertRaises(ConversationConflictError):
            self.store.claim_request(
                conversation_id="conversation-1",
                session_id="session-1",
                owner="user@example.com",
                message_id="message-1",
                request_fingerprint="different-fingerprint",
            )

    def test_reclaims_an_abandoned_request_claim(self):
        claim = {
            "conversation_id": "conversation-1",
            "session_id": "session-1",
            "owner": "user@example.com",
            "message_id": "message-1",
            "request_fingerprint": "fingerprint-1",
        }
        old_claim_token, _ = self.store.claim_request(**claim)
        with self.store._connect() as connection:
            connection.execute(
                """
                UPDATE conversation_requests
                SET created_at = datetime('now', '-2 hours')
                WHERE message_id = 'message-1'
                """
            )

        new_claim_token, answer = self.store.claim_request(**claim)
        self.assertIsNotNone(new_claim_token)
        self.assertNotEqual(old_claim_token, new_claim_token)
        self.assertIsNone(answer)
        self.store.release_request("message-1", old_claim_token)
        with self.assertRaises(ConversationInProgressError):
            self.store.claim_request(**claim)


if __name__ == "__main__":
    unittest.main()