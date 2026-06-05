"""Single source of truth for vault-relative wikilink rendering.

Every producer of vault wikilinks (index generators, entity-page builders,
prompt examples that are rendered) routes through `vault_wikilink` so the link
form lives in exactly one place. Links are **wiki-root-relative**: the Obsidian
vault opens at `<workspace>/wiki/`, so `[[concepts/foo]]`, `[[entities/pkg_x]]`,
and `[[work/<slug>]]` all resolve against the same base. The legacy `wiki/`
prefix is forbidden — passing one in is a programming error.
"""

from __future__ import annotations


def vault_wikilink(rel_path: str, text: str | None = None) -> str:
    """Render a wiki-root-relative Obsidian wikilink.

    `rel_path` is a vault-relative page path (e.g. ``concepts/foo``,
    ``entities/pkg_x``, ``work/2026-05-03-foo``), with or without a trailing
    ``.md``. Returns ``[[<stem>]]`` or ``[[<stem>|<text>]]``.

    Raises ``ValueError`` if `rel_path` carries a leading ``wiki/`` segment —
    that is the legacy workspace-root form this helper exists to eliminate.
    """
    stem = rel_path[:-3] if rel_path.endswith(".md") else rel_path
    if stem == "wiki" or stem.startswith("wiki/"):
        raise ValueError(
            f"vault_wikilink: refusing leading 'wiki/' segment in {rel_path!r}; "
            "pass a wiki-root-relative path (e.g. 'concepts/foo', 'entities/pkg_x')"
        )
    return f"[[{stem}|{text}]]" if text is not None else f"[[{stem}]]"
