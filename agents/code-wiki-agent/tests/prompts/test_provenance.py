from __future__ import annotations

"""Unit tests for provenance headers in prompt fragment files.

Verifies that every file under `prompts/_fragments/` (excluding __init__.py)
carries the mandatory 3-line provenance header:

    # Source: packages/prompt-sources/<path>
    # Anchor: <section heading or line range>
    # Source-commit: <hex SHA>

Also verifies that Source: paths start with `packages/prompt-sources/` (they
point to the vendored copies in the deep-agents repo, not the sibling lattice
checkout).

Tests skip cleanly when _fragments/ does not exist yet or contains only
__init__.py (i.e., before 06-03 lands).
"""

import re
from pathlib import Path

import pytest

# Anchored to this file's location so it works regardless of cwd.
# agents/code-wiki-agent/tests/prompts/test_provenance.py
#   parent[0] → tests/prompts/
#   parent[1] → tests/
#   parent[2] → agents/code-wiki-agent/
#   parent[3] → agents/          (NOT used here, resolve through src)
FRAGMENT_DIR = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "code_wiki_agent"
    / "prompts"
    / "_fragments"
)

# packages/prompt-sources/ relative to the workspace root.
# agents/code-wiki-agent/tests/prompts/test_provenance.py
#   parent[0] → tests/prompts/
#   parent[1] → tests/
#   parent[2] → agents/code-wiki-agent/
#   parent[3] → agents/
#   parent[4] → workspace root
PROMPT_SOURCES_DIR = Path(__file__).resolve().parents[4] / "packages" / "prompt-sources"

# Matches the 3-line provenance header exactly.
# Pattern:
#   # Source: <anything>
#   # Anchor: <anything>
#   # Source-commit: <lowercase hex digits>
_PROVENANCE_RE = re.compile(
    r"^# Source: (?P<source>.+)\n"
    r"# Anchor: (?P<anchor>.+)\n"
    r"# Source-commit: (?P<sha>[a-f0-9]+)\s*$",
    re.MULTILINE,
)


def _fragment_files() -> list[Path]:
    """Return non-__init__.py .py files under FRAGMENT_DIR, or empty list."""
    if not FRAGMENT_DIR.exists():
        return []
    return [f for f in FRAGMENT_DIR.glob("*.py") if f.name != "__init__.py"]


def test_all_fragments_have_provenance_header() -> None:
    """Every _fragments/*.py file has the 3-line provenance header."""
    fragment_files = _fragment_files()
    if not fragment_files:
        pytest.skip("no fragment files yet (06-03 hasn't landed)")

    for fpath in fragment_files:
        text = fpath.read_text(encoding="utf-8")
        match = _PROVENANCE_RE.search(text)
        assert match, (
            f"{fpath.name}: missing or malformed provenance header. "
            "Expected:\n"
            "  # Source: packages/prompt-sources/<path>\n"
            "  # Anchor: <section>\n"
            "  # Source-commit: <hex sha>"
        )


def test_provenance_source_paths_resolve() -> None:
    """Source: paths in provenance headers start with packages/prompt-sources/ and exist."""
    fragment_files = _fragment_files()
    if not fragment_files:
        pytest.skip("no fragment files yet (06-03 hasn't landed)")

    for fpath in fragment_files:
        text = fpath.read_text(encoding="utf-8")
        match = _PROVENANCE_RE.search(text)
        if not match:
            # test_all_fragments_have_provenance_header will catch the missing header
            continue

        source_rel = match.group("source").strip()  # e.g. "packages/prompt-sources/SKILL.md"
        assert source_rel.startswith("packages/prompt-sources/"), (
            f"{fpath.name}: Source: path must start with 'packages/prompt-sources/', "
            f"got: {source_rel!r}"
        )

        # Strip prefix and verify the file exists in the vendored location.
        suffix = source_rel[len("packages/prompt-sources/"):]
        resolved = PROMPT_SOURCES_DIR / suffix
        assert resolved.exists(), (
            f"{fpath.name}: Source path {source_rel!r} does not resolve to an "
            f"existing file. Expected: {resolved}"
        )
