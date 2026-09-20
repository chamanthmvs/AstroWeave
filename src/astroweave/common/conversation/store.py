from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from uuid import uuid4

from astroweave.common.config import get_logger
from astroweave.common.state import Message

logger = get_logger(__name__)

_DEFAULT_SESSION_HISTORY_LIMIT = 12
_DEFAULT_CONVERSATION_HISTORY_LIMIT = 8
_DEFAULT_REQUEST_CLAIM_TTL_SECONDS = 30 * 60


class ConversationAccessError(ValueError):
    """Raised when a conversation or session belongs to another user."""


class ConversationConflictError(ValueError):
    """Raised when an idempotency key is reused for different request data."""


class ConversationInProgressError(ValueError):
    """Raised when another process is already handling the same request."""


def get_conversation_db_path() -> Path:
    configured = os.environ.get("ASTROWEAVE_CONVERSATIONS_DB") or os.environ.get(
        "ASTROWEAVE_USERS_DB"
    )
    if configured:
        return Path(configured)
    repository_root = Path(__file__).resolve().parents[4]
    return repository_root / "app" / "data" / "astroweave.db"


def _get_history_limit(variable_name: str, default: int) -> int:
    raw_value = os.environ.get(variable_name, "")
    if not raw_value:
        return default
    try:
        value = int(raw_value)
    except ValueError:
        logger.warning("Ignoring invalid %s=%r", variable_name, raw_value)
        return default
    return max(0, value)


def get_session_history_limit() -> int:
    return _get_history_limit(
        "ASTROWEAVE_SESSION_HISTORY_LIMIT", _DEFAULT_SESSION_HISTORY_LIMIT
    )


def get_conversation_history_limit() -> int:
    return _get_history_limit(
        "ASTROWEAVE_CONVERSATION_HISTORY_LIMIT",
        _DEFAULT_CONVERSATION_HISTORY_LIMIT,
    )


def get_request_claim_ttl_seconds() -> int:
    return max(
        60,
        _get_history_limit(
            "ASTROWEAVE_REQUEST_CLAIM_TTL_SECONDS",
            _DEFAULT_REQUEST_CLAIM_TTL_SECONDS,
        ),
    )


class ConversationStore:
    """SQLite-backed durable transcripts with owner-isolated access."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or get_conversation_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    conversation_id TEXT PRIMARY KEY,
                    owner TEXT NOT NULL,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                    archived_at TEXT
                );

                CREATE TABLE IF NOT EXISTS conversation_sessions (
                    session_id TEXT PRIMARY KEY,
                    owner TEXT NOT NULL,
                    started_at TEXT NOT NULL DEFAULT (datetime('now')),
                    last_seen_at TEXT NOT NULL DEFAULT (datetime('now')),
                    ended_at TEXT
                );

                CREATE TABLE IF NOT EXISTS conversation_messages (
                    message_id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    owner TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                    content TEXT NOT NULL,
                    sequence_number INTEGER NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    UNIQUE (conversation_id, sequence_number),
                    FOREIGN KEY (conversation_id) REFERENCES conversations(conversation_id)
                        ON DELETE CASCADE,
                    FOREIGN KEY (session_id) REFERENCES conversation_sessions(session_id)
                        ON DELETE RESTRICT
                );

                CREATE TABLE IF NOT EXISTS conversation_requests (
                    message_id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    owner TEXT NOT NULL,
                    request_fingerprint TEXT NOT NULL,
                    claim_token TEXT,
                    status TEXT NOT NULL CHECK (status IN ('pending', 'completed')),
                    answer TEXT,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    completed_at TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_conversation_messages_order
                    ON conversation_messages (conversation_id, sequence_number);
                CREATE INDEX IF NOT EXISTS idx_conversations_owner_updated
                    ON conversations (owner, updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_sessions_owner_last_seen
                    ON conversation_sessions (owner, last_seen_at DESC);
                CREATE INDEX IF NOT EXISTS idx_conversation_requests_owner
                    ON conversation_requests (owner, conversation_id);
                """
            )
            columns = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(conversation_requests)"
                ).fetchall()
            }
            if "claim_token" not in columns:
                connection.execute(
                    "ALTER TABLE conversation_requests ADD COLUMN claim_token TEXT"
                )

    @staticmethod
    def _assert_owner(
        connection: sqlite3.Connection,
        table: str,
        id_column: str,
        identifier: str,
        owner: str,
    ) -> None:
        row = connection.execute(
            f"SELECT owner FROM {table} WHERE {id_column} = ?",  # noqa: S608
            (identifier,),
        ).fetchone()
        if row is not None and row["owner"] != owner:
            raise ConversationAccessError(
                f"{id_column.replace('_', ' ').title()} is not owned by this user."
            )

    def load_recent_messages(
        self,
        conversation_id: str,
        owner: str,
        limit: int | None = None,
    ) -> list[Message]:
        resolved_limit = (
            get_session_history_limit() if limit is None else max(0, limit)
        )
        with self._connect() as connection:
            self._assert_owner(
                connection,
                "conversations",
                "conversation_id",
                conversation_id,
                owner,
            )
            if resolved_limit == 0:
                return []
            rows = connection.execute(
                """
                SELECT message_id, role, content
                FROM (
                    SELECT message_id, role, content, sequence_number
                    FROM conversation_messages
                    WHERE conversation_id = ? AND owner = ?
                    ORDER BY sequence_number DESC
                    LIMIT ?
                )
                ORDER BY sequence_number ASC
                """,
                (conversation_id, owner, resolved_limit),
            ).fetchall()
        return [
            {
                "message_id": row["message_id"],
                "role": row["role"],
                "content": row["content"],
            }
            for row in rows
        ]

    def load_context_messages(
        self,
        *,
        conversation_id: str,
        session_id: str,
        owner: str,
        session_limit: int | None = None,
        conversation_limit: int | None = None,
    ) -> tuple[list[Message], list[Message]]:
        """Load prior-session context and current-session history separately."""

        resolved_session_limit = (
            get_session_history_limit() if session_limit is None else max(0, session_limit)
        )
        resolved_conversation_limit = (
            get_conversation_history_limit()
            if conversation_limit is None
            else max(0, conversation_limit)
        )
        with self._connect() as connection:
            self._assert_owner(
                connection,
                "conversations",
                "conversation_id",
                conversation_id,
                owner,
            )
            self._assert_owner(
                connection,
                "conversation_sessions",
                "session_id",
                session_id,
                owner,
            )
            prior_rows = self._load_message_rows(
                connection,
                conversation_id=conversation_id,
                owner=owner,
                limit=resolved_conversation_limit,
                excluded_session_id=session_id,
            )
            session_rows = self._load_message_rows(
                connection,
                conversation_id=conversation_id,
                owner=owner,
                limit=resolved_session_limit,
                session_id=session_id,
            )
        return self._rows_to_messages(prior_rows), self._rows_to_messages(session_rows)

    def get_persisted_response(
        self,
        *,
        conversation_id: str,
        owner: str,
        user_message_id: str,
    ) -> str | None:
        """Return the saved assistant response for an idempotent request retry."""

        with self._connect() as connection:
            self._assert_owner(
                connection,
                "conversations",
                "conversation_id",
                conversation_id,
                owner,
            )
            user_message = connection.execute(
                """
                SELECT conversation_id, owner, role, sequence_number
                FROM conversation_messages
                WHERE message_id = ?
                """,
                (user_message_id,),
            ).fetchone()
            if user_message is None:
                return None
            if (
                user_message["conversation_id"] != conversation_id
                or user_message["owner"] != owner
                or user_message["role"] != "user"
            ):
                raise ConversationAccessError(
                    "Message ID is already associated with another conversation."
                )
            assistant_message = connection.execute(
                """
                SELECT content
                FROM conversation_messages
                WHERE conversation_id = ? AND sequence_number = ? AND role = 'assistant'
                """,
                (conversation_id, user_message["sequence_number"] + 1),
            ).fetchone()
        return assistant_message["content"] if assistant_message else None

    def claim_request(
        self,
        *,
        conversation_id: str,
        session_id: str,
        owner: str,
        message_id: str,
        request_fingerprint: str,
    ) -> tuple[str | None, str | None]:
        """Return ``(claim_token, answer)`` for new or completed work."""

        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._assert_owner(
                connection, "conversations", "conversation_id", conversation_id, owner
            )
            self._assert_owner(
                connection,
                "conversation_sessions",
                "session_id",
                session_id,
                owner,
            )
            row = connection.execute(
                "SELECT * FROM conversation_requests WHERE message_id = ?",
                (message_id,),
            ).fetchone()
            if row is None:
                claim_token = str(uuid4())
                connection.execute(
                    """
                    INSERT INTO conversation_requests (
                        message_id, conversation_id, session_id, owner,
                        request_fingerprint, claim_token, status
                    ) VALUES (?, ?, ?, ?, ?, ?, 'pending')
                    """,
                    (
                        message_id,
                        conversation_id,
                        session_id,
                        owner,
                        request_fingerprint,
                        claim_token,
                    ),
                )
                return claim_token, None
            if (
                row["conversation_id"] != conversation_id
                or row["session_id"] != session_id
                or row["owner"] != owner
                or row["request_fingerprint"] != request_fingerprint
            ):
                raise ConversationConflictError(
                    "Message ID was already used for different request data."
                )
            if row["status"] == "pending":
                stale_modifier = f"-{get_request_claim_ttl_seconds()} seconds"
                is_stale = connection.execute(
                    "SELECT datetime(?) <= datetime('now', ?)",
                    (row["created_at"], stale_modifier),
                ).fetchone()[0]
                if is_stale:
                    claim_token = str(uuid4())
                    connection.execute(
                        """
                        UPDATE conversation_requests
                        SET created_at = datetime('now'), claim_token = ?
                        WHERE message_id = ? AND status = 'pending'
                        """,
                        (claim_token, message_id),
                    )
                    logger.warning("reclaimed stale request claim message_id=%s", message_id)
                    return claim_token, None
                raise ConversationInProgressError(
                    "A request with this message ID is already in progress."
                )
            return None, row["answer"]

    def release_request(self, message_id: str, claim_token: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                DELETE FROM conversation_requests
                WHERE message_id = ? AND claim_token = ? AND status = 'pending'
                """,
                (message_id, claim_token),
            )

    @staticmethod
    def _load_message_rows(
        connection: sqlite3.Connection,
        *,
        conversation_id: str,
        owner: str,
        limit: int,
        session_id: str | None = None,
        excluded_session_id: str | None = None,
    ) -> list[sqlite3.Row]:
        if limit == 0:
            return []
        condition = ""
        parameters: list[object] = [conversation_id, owner]
        if session_id is not None:
            condition = "AND session_id = ?"
            parameters.append(session_id)
        elif excluded_session_id is not None:
            condition = "AND session_id != ?"
            parameters.append(excluded_session_id)
        parameters.append(limit)
        return connection.execute(
            f"""
            SELECT message_id, role, content
            FROM (
                SELECT message_id, role, content, sequence_number
                FROM conversation_messages
                WHERE conversation_id = ? AND owner = ? {condition}
                ORDER BY sequence_number DESC
                LIMIT ?
            )
            ORDER BY sequence_number ASC
            """,  # noqa: S608 - condition is selected from constants above
            parameters,
        ).fetchall()

    @staticmethod
    def _rows_to_messages(rows: list[sqlite3.Row]) -> list[Message]:
        return [
            {
                "message_id": row["message_id"],
                "role": row["role"],
                "content": row["content"],
            }
            for row in rows
        ]

    def persist_turn(
        self,
        *,
        conversation_id: str,
        session_id: str,
        owner: str,
        user_message_id: str,
        user_content: str,
        assistant_content: str,
        request_fingerprint: str | None = None,
        claim_token: str | None = None,
    ) -> bool:
        """Persist one user/assistant turn atomically; return False if duplicated."""

        if not all(
            [
                conversation_id.strip(),
                session_id.strip(),
                owner.strip(),
                user_message_id.strip(),
            ]
        ):
            raise ValueError(
                "conversation_id, session_id, owner, and user_message_id are required"
            )
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._assert_owner(
                connection,
                "conversations",
                "conversation_id",
                conversation_id,
                owner,
            )
            self._assert_owner(
                connection,
                "conversation_sessions",
                "session_id",
                session_id,
                owner,
            )
            duplicate = connection.execute(
                """
                SELECT conversation_id, owner, role
                FROM conversation_messages
                WHERE message_id = ?
                """,
                (user_message_id,),
            ).fetchone()
            if duplicate is not None:
                if (
                    duplicate["conversation_id"] != conversation_id
                    or duplicate["owner"] != owner
                    or duplicate["role"] != "user"
                ):
                    raise ConversationAccessError(
                        "Message ID is already associated with another conversation."
                    )
                logger.info(
                    "conversation turn already persisted conversation_id=%s message_id=%s",
                    conversation_id,
                    user_message_id,
                )
                return False

            connection.execute(
                """
                INSERT INTO conversation_sessions (session_id, owner)
                VALUES (?, ?)
                ON CONFLICT(session_id) DO UPDATE SET last_seen_at = datetime('now')
                """,
                (session_id, owner),
            )
            connection.execute(
                """
                INSERT INTO conversations (conversation_id, owner, title)
                VALUES (?, ?, ?)
                ON CONFLICT(conversation_id) DO UPDATE SET updated_at = datetime('now')
                """,
                (conversation_id, owner, user_content.strip()[:80] or "New conversation"),
            )
            next_sequence = connection.execute(
                """
                SELECT COALESCE(MAX(sequence_number), 0) + 1
                FROM conversation_messages
                WHERE conversation_id = ?
                """,
                (conversation_id,),
            ).fetchone()[0]
            connection.execute(
                """
                INSERT INTO conversation_messages (
                    message_id, conversation_id, session_id, owner, role,
                    content, sequence_number
                ) VALUES (?, ?, ?, ?, 'user', ?, ?)
                """,
                (
                    user_message_id,
                    conversation_id,
                    session_id,
                    owner,
                    user_content,
                    next_sequence,
                ),
            )
            if request_fingerprint is not None:
                cursor = connection.execute(
                    """
                    UPDATE conversation_requests
                    SET status = 'completed', answer = ?, completed_at = datetime('now')
                    WHERE message_id = ? AND conversation_id = ? AND session_id = ?
                        AND owner = ? AND request_fingerprint = ? AND claim_token = ?
                        AND status = 'pending'
                    """,
                    (
                        assistant_content,
                        user_message_id,
                        conversation_id,
                        session_id,
                        owner,
                        request_fingerprint,
                        claim_token,
                    ),
                )
                if cursor.rowcount != 1:
                    raise ConversationConflictError(
                        "The request claim could not be completed."
                    )
            connection.execute(
                """
                INSERT INTO conversation_messages (
                    message_id, conversation_id, session_id, owner, role,
                    content, sequence_number
                ) VALUES (?, ?, ?, ?, 'assistant', ?, ?)
                """,
                (
                    str(uuid4()),
                    conversation_id,
                    session_id,
                    owner,
                    assistant_content,
                    next_sequence + 1,
                ),
            )
        logger.info(
            "persisted conversation turn conversation_id=%s session_id=%s owner=%s",
            conversation_id,
            session_id,
            owner,
        )
        return True

    def list_conversations(self, owner: str, limit: int = 50) -> list[dict[str, str]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT conversation_id, title, created_at, updated_at
                FROM conversations
                WHERE owner = ? AND archived_at IS NULL
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (owner, max(1, limit)),
            ).fetchall()
        return [dict(row) for row in rows]

    def delete_conversation(self, conversation_id: str, owner: str) -> bool:
        with self._connect() as connection:
            self._assert_owner(
                connection,
                "conversations",
                "conversation_id",
                conversation_id,
                owner,
            )
            connection.execute(
                "DELETE FROM conversation_requests WHERE conversation_id = ? AND owner = ?",
                (conversation_id, owner),
            )
            cursor = connection.execute(
                "DELETE FROM conversations WHERE conversation_id = ? AND owner = ?",
                (conversation_id, owner),
            )
        deleted = cursor.rowcount > 0
        logger.info(
            "deleted conversation conversation_id=%s owner=%s deleted=%s",
            conversation_id,
            owner,
            deleted,
        )
        return deleted