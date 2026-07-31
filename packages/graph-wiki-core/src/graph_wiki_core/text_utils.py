"""Base-closure-safe text helpers.

Deliberately dependency-free: `prompts/` modules and the mechanical scan half
import this, and both must load without the [bedrock] extra installed.
"""

from __future__ import annotations


def truncate_text(text: str, max_chars: int) -> str:
    """Return `text` capped at `max_chars`, with an explicit truncation marker."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n\n[TRUNCATED after {max_chars} chars]"
