from typing import TypedDict


class Context(TypedDict, total=False):
    conversation_id: str
    session_id: str
    username: str