from typing import Any, TypedDict


class Context(TypedDict, total=False):
    conversation_id: str
    session_id: str
    username: str
    birth_details: dict[str, Any]
