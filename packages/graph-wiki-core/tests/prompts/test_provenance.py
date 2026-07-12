"""Provenance-gate helper unit tests.

Locks the two pure helpers this module exercises:

1. **Whitelist** (`_starts_with_allowed_prefix`) — a source path starts with one
   of the allowed prefixes (`plugins/graph-wiki/`, the exact
   `packages/workspace-io/.../CLAUDE.md.template` literal, or
   `agents/graph-wiki-core/src/graph_wiki_core/prompts/sources/`); any other
   prefix fails.
2. **Slugification** (`slugify`) — the GitHub anchor-slug rule for markdown
   headings.

The full D-08 provenance gate's resolution + semantic-drift checks (and their
supporting scaffold) were retired; only these helper locks remain.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Slugification (GitHub-flavoured)
# ---------------------------------------------------------------------------

# Drop characters that are NOT alphanumeric, hyphen, underscore, or whitespace.
# Em-dash (U+2014), parens, periods, commas, etc. are removed WITHOUT being
# replaced — adjacent whitespace stays, which is what produces the double-hyphen
# in the canonical em-dash example (`Pass 2 — Semantic` → `pass-2--semantic`).
_PUNCT_DROP_RE = re.compile(r"[^\w\-\s]", re.UNICODE)


def slugify(heading: str) -> str:
    """Map a markdown heading line to its GitHub anchor slug.

    Algorithm (mechanical, no special cases):
      1. Strip the leading `#+` and any surrounding whitespace.
      2. Lowercase.
      3. Drop characters that are not alphanumeric, hyphen, underscore, or
         whitespace (em-dashes vanish; parens vanish; periods vanish).
      4. Replace each remaining whitespace character with a single hyphen
         (do NOT collapse runs — that is how `— ` becomes `--`).
      5. Strip leading/trailing hyphens.

    Examples:
      `### 4. Write the source summary`  → `4-write-the-source-summary`
      `### Pass 2 — Semantic (read and think)` → `pass-2--semantic-read-and-think`
      `## Iron rules` → `iron-rules`
    """
    # 1. Strip leading hash run + whitespace.
    s = heading.lstrip("#").strip()
    # 2. Lowercase.
    s = s.lower()
    # 3. Drop punctuation (excluding hyphens, underscores, whitespace).
    s = _PUNCT_DROP_RE.sub("", s)
    # 4. Per-char whitespace → hyphen (no run collapse).
    s = re.sub(r"\s", "-", s)
    # 5. Trim leading/trailing hyphens for tidiness.
    return s.strip("-")


# ---------------------------------------------------------------------------
# Path mapping
# ---------------------------------------------------------------------------


def _starts_with_allowed_prefix(source_path: str) -> bool:
    """D-08 step 1 helper — returns True iff `source_path` matches the whitelist.

    `plugins/graph-wiki/` and `agents/.../prompts/sources/` are directory
    prefixes; `packages/workspace-io/.../CLAUDE.md.template` is an exact whole-
    path literal (subdirectories under `packages/workspace-io/` are rejected).
    """
    template_literal = "packages/workspace-io/src/workspace_io/assets/CLAUDE.md.template"
    if source_path == template_literal:
        return True
    return source_path.startswith("plugins/graph-wiki/") or source_path.startswith(
        "agents/graph-wiki-core/src/graph_wiki_core/prompts/sources/"
    )


# ---- Helper unit tests --------------------------------------------------


def test_disallowed_prefix_rejected() -> None:
    """The whitelist helper rejects non-allowlisted prefixes.

    Includes the historical `packages/prompt-sources/` path (deleted in
    Plan 04) and any sibling under `packages/workspace-io/` other than the
    one CLAUDE.md.template literal.
    """
    assert not _starts_with_allowed_prefix("packages/prompt-sources/foo.md"), (
        "whitelist must reject the historical prompt-sources prefix"
    )
    assert not _starts_with_allowed_prefix("packages/workspace-io/foo.md"), (
        "only the CLAUDE.md.template literal is allowed under packages/workspace-io/"
    )
    assert not _starts_with_allowed_prefix(""), "empty string is not a valid source"
    assert not _starts_with_allowed_prefix("plugins/other/foo.md"), (
        "plugins/ prefix must specifically be plugins/graph-wiki/"
    )
    # Positive cases — sanity-check the helper accepts the allowed prefixes.
    assert _starts_with_allowed_prefix("plugins/graph-wiki/agents/scanner.md")
    assert _starts_with_allowed_prefix("packages/workspace-io/src/workspace_io/assets/CLAUDE.md.template")
    assert _starts_with_allowed_prefix("agents/graph-wiki-core/src/graph_wiki_core/prompts/sources/code_reader.md")


def test_slugify_known_cases() -> None:
    """Lock the GitHub-slug rule against the audit's known-good slug pairs."""
    assert slugify("### 4. Write the source summary") == "4-write-the-source-summary"
    # Em-dash (U+2014) is stripped without replacement; adjacent spaces remain,
    # so each becomes a hyphen → double-hyphen.
    assert slugify("### Pass 2 — Semantic (read and think)") == "pass-2--semantic-read-and-think"
    assert slugify("### Pass 3 — Report") == "pass-3--report"
    assert slugify("## Iron rules") == "iron-rules"
    assert slugify("## Log format") == "log-format"
    assert slugify("## Style") == "style"
    assert slugify("## Cross-tool compatibility") == "cross-tool-compatibility"
    assert slugify("## Page categories") == "page-categories"
    assert slugify("## Architecture") == "architecture"
    assert slugify("## Rules") == "rules"
    assert slugify("## Red flags") == "red-flags"
