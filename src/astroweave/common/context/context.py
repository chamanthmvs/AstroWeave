from typing import Any, TypedDict

from astroweave.common.conversation import ConversationStore


class Context(TypedDict, total=False):
    conversation_id: str
    session_id: str
    username: str
    message_id: str
    methodology: str
    birth_details: dict[str, Any]
    conversation_store: ConversationStore
    request_fingerprint: str
    request_claim_token: str
