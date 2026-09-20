import json

from astroweave.common.state import Message


def format_message_history(messages: list[Message]) -> str:
    """Format stored messages as delimited, untrusted conversational context."""

    if not messages:
        return "No prior messages."
    safe_messages = [
        {"role": message["role"], "content": message["content"]}
        for message in messages
    ]
    return "conversation_history_json=" + json.dumps(
        safe_messages, ensure_ascii=True, separators=(",", ":")
    )