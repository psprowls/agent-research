"""tree-sitter grammar loading via tree-sitter-language-pack."""

from __future__ import annotations

from functools import lru_cache

import tree_sitter
from tree_sitter_language_pack import get_language as _pack_get_language

from source_parser.errors import UnsupportedLanguageError

_KNOWN: frozenset[str] = frozenset({"python", "javascript", "typescript"})


@lru_cache(maxsize=None)
def get_language(name: str) -> tree_sitter.Language:
    """Return the tree-sitter Language for a language name. Cached."""
    if name not in _KNOWN:
        raise UnsupportedLanguageError(
            f"Unknown grammar name: {name!r}. Known: {sorted(_KNOWN)}",
            path=None,
            extension=None,
        )
    try:
        return _pack_get_language(name)
    except Exception as exc:
        raise UnsupportedLanguageError(
            f"Failed to load grammar for {name!r}: {exc}",
            path=None,
            extension=None,
        ) from exc
