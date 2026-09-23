"""Lightweight token estimation helpers for sliding-window memory budgeting."""

import math
import re

# Rough English token:average-character ratio; 4 chars per token is a safe
# approximation for budgeting that caps active window sizes even when a real
# LLM tokenizer is not available in this phase.
_AVG_CHARS_PER_TOKEN = 4.0

_WHITESPACE_RE = re.compile(r"\s+")


def estimate_content_tokens(text: str) -> int:
    """Return an approximate token count for a single text blob."""
    normalized = _WHITESPACE_RE.sub(" ", text or "")
    if not normalized.strip():
        return 0
    return max(1, math.ceil(len(normalized) / _AVG_CHARS_PER_TOKEN))


def estimate_dialogue_tokens(sender: str = "", content: str = "") -> int:
    """Return an approximate token count for one dialogue message."""
    return estimate_content_tokens(f"{sender} {content}".strip())


def estimate_node_tokens(summary: str, messages: list = None) -> int:
    """Return an approximate token count for one node plus its attached messages."""
    total = estimate_content_tokens(summary)
    for message in messages or []:
        total += estimate_dialogue_tokens(
            getattr(message, "sender", str(message.get("sender", ""))),
            getattr(message, "content", str(message.get("content", ""))),
        )
    return total