"""Repo-level grep gate for the GRAPH_WIKI_RUN_INTEGRATION integration test pattern.

Phase 16 MCP-CAN-02 (D-10): every `**/tests/integration/test_*.py` across the
monorepo MUST either match the canonical `pytest.mark.skipif(not os.environ.get(
"GRAPH_WIKI_RUN_INTEGRATION"), ...)` pattern OR carry the
`# integration-gate-allow` marker comment.

This meta-test runs on every PR. Drift fails CI loudly.
"""

from __future__ import annotations

import re
from pathlib import Path

# Repo root: this file lives at <repo>/tests/test_integration_gate.py
_REPO_ROOT = Path(__file__).parent.parent

# Canonical pattern. Tolerates whitespace and newlines between tokens because
# auto-formatters (ruff, black) may reflow the argument list.
_CANONICAL_PATTERN = re.compile(
    r'pytest\.mark\.skipif\s*\(\s*'
    r'(?:not\s+)?os\.environ\.get\(\s*["\']GRAPH_WIKI_RUN_INTEGRATION["\']\s*\)',
    re.MULTILINE,
)

# Allowlist comment marker.
_ALLOW_MARKER = "# integration-gate-allow"


def _find_integration_test_files() -> list[Path]:
    """Walk the repo for every integration test file we should enforce against.

    Returns sorted list for deterministic test parametrization / failure output.
    Excludes virtualenvs and ephemeral agent worktrees under .claude/worktrees/,
    which contain stale snapshots that don't reflect current code.
    """
    matches: list[Path] = []
    for path in _REPO_ROOT.rglob("tests/integration/test_*.py"):
        parts = path.parts
        if ".venv" in parts or "site-packages" in parts:
            continue
        # Exclude ephemeral worktree snapshots when this check is being run
        # from the canonical main checkout. When this file IS executed from
        # inside a worktree (e.g., a Claude Code agent worktree at
        # `<repo>/.claude/worktrees/agent-*/`), use a path RELATIVE to
        # _REPO_ROOT so the exclusion only catches `.claude/worktrees/`
        # children of the worktree itself — not the worktree root itself.
        rel_parts = path.relative_to(_REPO_ROOT).parts
        if ".claude" in rel_parts and "worktrees" in rel_parts:
            continue
        matches.append(path)
    return sorted(matches)


def test_integration_test_files_use_canonical_gate() -> None:
    """Every `**/tests/integration/test_*.py` matches the canonical skipif pattern
    or carries the explicit allowlist comment marker.
    """
    files = _find_integration_test_files()
    assert files, (
        "no integration test files discovered — repo layout drift suspected; "
        "expected at least the agents/graph-wiki-agent/tests/integration/* files"
    )

    divergent: list[str] = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        if _CANONICAL_PATTERN.search(text):
            continue
        if _ALLOW_MARKER in text:
            continue
        divergent.append(str(path.relative_to(_REPO_ROOT)))

    assert not divergent, (
        "the following integration test files do not match the canonical "
        f"GRAPH_WIKI_RUN_INTEGRATION gate (see docs/testing.md): {divergent}"
    )
