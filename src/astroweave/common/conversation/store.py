from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    inspect,
    text,
)
from sqlalchemy.engine import Connection, Engine

from astroweave.common.config import get_logger
from astroweave.common.database import resolve_engine
from astroweave.common.state import Message

logger = get_logger(__name__)

_DEFAULT_SESSION_HISTORY_LIMIT = 12
_DEFAULT_CONVERSATION_HISTORY_LIMIT = 8
_DEFAULT_REQUEST_CLAIM_TTL_SECONDS = 30 * 60

# Timestamps are written as UTC strings in this fixed format so ordering and the
# stale-claim comparison are consistent on both SQLite and Postgres (the stores
# used to lean on SQLite's datetime('now'), which Postgres does not have).
_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"


def _now() -> str:
    return datetime.now(timezone.utc).strftime(_TIMESTAMP_FORMAT)


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


_metadata = MetaData()

conversations = Table(
    "conversations",
    _metadata,
    Column("conversation_id", String, primary_key=True),
    Column("owner", String, nullable=False),
    Column("title", String, nullable=False),
    Column("created_at", String, nullable=False, server_default=text("CURRENT_TIMESTAMP")),
    Column("updated_at", String, nullable=False, server_default=text("CURRENT_TIMESTAMP")),
    Column("archived_at", String),
    Index("idx_conversations_owner_updated", "owner", "updated_at"),
)

conversation_sessions = Table(
    "conversation_sessions",
    _metadata,
    Column("session_id", String, primary_key=True),
    Column("owner", String, nullable=False),
    Column("started_at", String, nullable=False, server_default=text("CURRENT_TIMESTAMP")),
    Column("last_seen_at", String, nullable=False, server_default=text("CURRENT_TIMESTAMP")),
    Column("ended_at", String),
    Index("idx_sessions_owner_last_seen", "owner", "last_seen_at"),
)

conversation_messages = Table(
    "conversation_messages",
    _metadata,
    Column("message_id", String, primary_key=True),
    Column(
        "conversation_id",
        String,
        ForeignKey("conversations.conversation_id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "session_id",
        String,
        ForeignKey("conversation_sessions.session_id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("owner", String, nullable=False),
    Column("role", String, nullable=False),
    Column("content", Text, nullable=False),
    Column("sequence_number", Integer, nullable=False),
    Column("created_at", String, nullable=False, server_default=text("CURRENT_TIMESTAMP")),
    CheckConstraint("role IN ('user', 'assistant')", name="ck_messages_role"),
    UniqueConstraint("conversation_id", "sequence_number", name="uq_messages_conversation_sequence"),
    Index("idx_conversation_messages_order", "conversation_id", "sequence_number"),
)

conversation_requests = Table(
    "conversation_requests",
    _metadata,
    Column("message_id", String, primary_key=True),
    Column("conversation_id", String, nullable=False),
    Column("session_id", String, nullable=False),
    Column("owner", String, nullable=False),
    Column("request_fingerprint", String, nullable=False),
    Column("claim_token", String),
    Column("status", String, nullable=False),
    Column("answer", Text),
    Column("created_at", String, nullable=False, server_default=text("CURRENT_TIMESTAMP")),
    Column("completed_at", String),
    CheckConstraint("status IN ('pending', 'completed')", name="ck_requests_status"),
    Index("idx_conversation_requests_owner", "owner", "conversation_id"),
)


class ConversationStore:
    """Durable transcripts with owner-isolated access.

    Backed by the shared engine (SQLite locally, Postgres in production). A
    ``db_path`` or ``engine`` may still be passed to target a specific database
    (tests use a temp file); otherwise it uses ``DATABASE_URL``.
    """

    def __init__(self, db_path: Path | None = None, engine: Engine | None = None) -> None:
        self.db_path = db_path
        self._engine = resolve_engine(db_path, engine)
        self._initialize()

    def _initialize(self) -> None:
        _metadata.create_all(bind=self._engine, checkfirst=True)
        # Legacy databases created before claim_token existed get it added.
        columns = {col["name"] for col in inspect(self._engine).get_columns("conversation_requests")}
        if "claim_token" not in columns:
            with self._engine.begin() as connection:
                connection.execute(text("ALTER TABLE conversation_requests ADD COLUMN claim_token TEXT"))

    @staticmethod
    def _assert_owner(
        connection: Connection,
        table: str,
        id_column: str,
        identifier: str,
        owner: str,
    ) -> None:
        row = connection.execute(
            text(f"SELECT owner FROM {table} WHERE {id_column} = :identifier"),  # noqa: S608 - table/column are constants
            {"identifier": identifier},
        ).mappings().first()
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
        with self._engine.connect() as connection:
            self._assert_owner(connection, "conversations", "conversation_id", conversation_id, owner)
            if resolved_limit == 0:
                return []
            rows = connection.execute(
                text(
                    """
                    SELECT message_id, role, content FROM (
                        SELECT message_id, role, content, sequence_number
                        FROM conversation_messages
                        WHERE conversation_id = :conversation_id AND owner = :owner
                        ORDER BY sequence_number DESC
                        LIMIT :limit
                    ) AS recent
                    ORDER BY sequence_number ASC
                    """
                ),
                {"conversation_id": conversation_id, "owner": owner, "limit": resolved_limit},
            ).mappings().all()
        return self._rows_to_messages(rows)

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
        with self._engine.connect() as connection:
            self._assert_owner(connection, "conversations", "conversation_id", conversation_id, owner)
            self._assert_owner(connection, "conversation_sessions", "session_id", session_id, owner)
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

        with self._engine.connect() as connection:
            self._assert_owner(connection, "conversations", "conversation_id", conversation_id, owner)
            user_message = connection.execute(
                text(
                    """
                    SELECT conversation_id, owner, role, sequence_number
                    FROM conversation_messages
                    WHERE message_id = :message_id
                    """
                ),
                {"message_id": user_message_id},
            ).mappings().first()
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
                text(
                    """
                    SELECT content
                    FROM conversation_messages
                    WHERE conversation_id = :conversation_id
                        AND sequence_number = :sequence_number AND role = 'assistant'
                    """
                ),
                {"conversation_id": conversation_id, "sequence_number": user_message["sequence_number"] + 1},
            ).mappings().first()
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

        with self._engine.begin() as connection:
            self._assert_owner(connection, "conversations", "conversation_id", conversation_id, owner)
            self._assert_owner(connection, "conversation_sessions", "session_id", session_id, owner)
            row = connection.execute(
                text("SELECT * FROM conversation_requests WHERE message_id = :message_id"),
                {"message_id": message_id},
            ).mappings().first()
            if row is None:
                claim_token = str(uuid4())
                connection.execute(
                    text(
                        """
                        INSERT INTO conversation_requests (
                            message_id, conversation_id, session_id, owner,
                            request_fingerprint, claim_token, status, created_at
                        ) VALUES (
                            :message_id, :conversation_id, :session_id, :owner,
                            :request_fingerprint, :claim_token, 'pending', :now
                        )
                        """
                    ),
                    {
                        "message_id": message_id,
                        "conversation_id": conversation_id,
                        "session_id": session_id,
                        "owner": owner,
                        "request_fingerprint": request_fingerprint,
                        "claim_token": claim_token,
                        "now": _now(),
                    },
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
                cutoff = (datetime.now(timezone.utc) - timedelta(seconds=get_request_claim_ttl_seconds())).strftime(
                    _TIMESTAMP_FORMAT
                )
                if row["created_at"] <= cutoff:  # the prior claim is stale
                    claim_token = str(uuid4())
                    connection.execute(
                        text(
                            """
                            UPDATE conversation_requests
                            SET created_at = :now, claim_token = :claim_token
                            WHERE message_id = :message_id AND status = 'pending'
                            """
                        ),
                        {"now": _now(), "claim_token": claim_token, "message_id": message_id},
                    )
                    logger.warning("reclaimed stale request claim message_id=%s", message_id)
                    return claim_token, None
                raise ConversationInProgressError(
                    "A request with this message ID is already in progress."
                )
            return None, row["answer"]

    def request_ids(self, message_id: str, owner: str) -> tuple[str, str] | None:
        with self._engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT conversation_id, session_id, owner FROM conversation_requests WHERE message_id = :message_id"
                ),
                {"message_id": message_id},
            ).mappings().first()
        if row is None:
            return None
        if row["owner"] != owner:
            raise ConversationAccessError("Message ID is not owned by this user.")
        return row["conversation_id"], row["session_id"]

    def release_request(self, message_id: str, claim_token: str) -> None:
        with self._engine.begin() as connection:
            connection.execute(
                text(
                    """
                    DELETE FROM conversation_requests
                    WHERE message_id = :message_id AND claim_token = :claim_token AND status = 'pending'
                    """
                ),
                {"message_id": message_id, "claim_token": claim_token},
            )

    @staticmethod
    def _load_message_rows(
        connection: Connection,
        *,
        conversation_id: str,
        owner: str,
        limit: int,
        session_id: str | None = None,
        excluded_session_id: str | None = None,
    ) -> list:
        if limit == 0:
            return []
        condition = ""
        parameters: dict[str, object] = {
            "conversation_id": conversation_id,
            "owner": owner,
            "limit": limit,
        }
        if session_id is not None:
            condition = "AND session_id = :session_id"
            parameters["session_id"] = session_id
        elif excluded_session_id is not None:
            condition = "AND session_id != :excluded_session_id"
            parameters["excluded_session_id"] = excluded_session_id
        return connection.execute(
            text(
                f"""
                SELECT message_id, role, content FROM (
                    SELECT message_id, role, content, sequence_number
                    FROM conversation_messages
                    WHERE conversation_id = :conversation_id AND owner = :owner {condition}
                    ORDER BY sequence_number DESC
                    LIMIT :limit
                ) AS recent
                ORDER BY sequence_number ASC
                """  # noqa: S608 - condition is selected from constants above
            ),
            parameters,
        ).mappings().all()

    @staticmethod
    def _rows_to_messages(rows: list) -> list[Message]:
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
        with self._engine.begin() as connection:
            self._assert_owner(connection, "conversations", "conversation_id", conversation_id, owner)
            self._assert_owner(connection, "conversation_sessions", "session_id", session_id, owner)
            duplicate = connection.execute(
                text(
                    """
                    SELECT conversation_id, owner, role
                    FROM conversation_messages
                    WHERE message_id = :message_id
                    """
                ),
                {"message_id": user_message_id},
            ).mappings().first()
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

            now = _now()
            connection.execute(
                text(
                    """
                    INSERT INTO conversation_sessions (session_id, owner, started_at, last_seen_at)
                    VALUES (:session_id, :owner, :now, :now)
                    ON CONFLICT (session_id) DO UPDATE SET last_seen_at = :now
                    """
                ),
                {"session_id": session_id, "owner": owner, "now": now},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO conversations (conversation_id, owner, title, created_at, updated_at)
                    VALUES (:conversation_id, :owner, :title, :now, :now)
                    ON CONFLICT (conversation_id) DO UPDATE SET updated_at = :now
                    """
                ),
                {
                    "conversation_id": conversation_id,
                    "owner": owner,
                    "title": user_content.strip()[:80] or "New conversation",
                    "now": now,
                },
            )
            next_sequence = int(
                connection.execute(
                    text(
                        """
                        SELECT COALESCE(MAX(sequence_number), 0) + 1
                        FROM conversation_messages
                        WHERE conversation_id = :conversation_id
                        """
                    ),
                    {"conversation_id": conversation_id},
                ).scalar()
            )
            connection.execute(
                text(
                    """
                    INSERT INTO conversation_messages (
                        message_id, conversation_id, session_id, owner, role,
                        content, sequence_number, created_at
                    ) VALUES (
                        :message_id, :conversation_id, :session_id, :owner, 'user',
                        :content, :sequence_number, :now
                    )
                    """
                ),
                {
                    "message_id": user_message_id,
                    "conversation_id": conversation_id,
                    "session_id": session_id,
                    "owner": owner,
                    "content": user_content,
                    "sequence_number": next_sequence,
                    "now": now,
                },
            )
            if request_fingerprint is not None:
                result = connection.execute(
                    text(
                        """
                        UPDATE conversation_requests
                        SET status = 'completed', answer = :answer, completed_at = :now
                        WHERE message_id = :message_id AND conversation_id = :conversation_id
                            AND session_id = :session_id AND owner = :owner
                            AND request_fingerprint = :request_fingerprint AND claim_token = :claim_token
                            AND status = 'pending'
                        """
                    ),
                    {
                        "answer": assistant_content,
                        "now": now,
                        "message_id": user_message_id,
                        "conversation_id": conversation_id,
                        "session_id": session_id,
                        "owner": owner,
                        "request_fingerprint": request_fingerprint,
                        "claim_token": claim_token,
                    },
                )
                if result.rowcount != 1:
                    raise ConversationConflictError(
                        "The request claim could not be completed."
                    )
            connection.execute(
                text(
                    """
                    INSERT INTO conversation_messages (
                        message_id, conversation_id, session_id, owner, role,
                        content, sequence_number, created_at
                    ) VALUES (
                        :message_id, :conversation_id, :session_id, :owner, 'assistant',
                        :content, :sequence_number, :now
                    )
                    """
                ),
                {
                    "message_id": str(uuid4()),
                    "conversation_id": conversation_id,
                    "session_id": session_id,
                    "owner": owner,
                    "content": assistant_content,
                    "sequence_number": next_sequence + 1,
                    "now": now,
                },
            )
        logger.info(
            "persisted conversation turn conversation_id=%s session_id=%s owner=%s",
            conversation_id,
            session_id,
            owner,
        )
        return True

    def list_conversations(self, owner: str, limit: int = 50) -> list[dict[str, str]]:
        with self._engine.connect() as connection:
            rows = connection.execute(
                text(
                    """
                    SELECT conversation_id, title, created_at, updated_at
                    FROM conversations
                    WHERE owner = :owner AND archived_at IS NULL
                    ORDER BY updated_at DESC
                    LIMIT :limit
                    """
                ),
                {"owner": owner, "limit": max(1, limit)},
            ).mappings().all()
        return [dict(row) for row in rows]

    def delete_conversation(self, conversation_id: str, owner: str) -> bool:
        with self._engine.begin() as connection:
            self._assert_owner(connection, "conversations", "conversation_id", conversation_id, owner)
            connection.execute(
                text("DELETE FROM conversation_requests WHERE conversation_id = :conversation_id AND owner = :owner"),
                {"conversation_id": conversation_id, "owner": owner},
            )
            result = connection.execute(
                text("DELETE FROM conversations WHERE conversation_id = :conversation_id AND owner = :owner"),
                {"conversation_id": conversation_id, "owner": owner},
            )
            deleted = result.rowcount > 0
        logger.info(
            "deleted conversation conversation_id=%s owner=%s deleted=%s",
            conversation_id,
            owner,
            deleted,
        )
        return deleted
