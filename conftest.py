"""Root conftest, loaded for both whole-suite and --package-scoped test runs.

A shell-exported FORCE_COLOR forces rich/click to emit ANSI escapes even when
output isn't a tty, which breaks CLI help-text and no-color-mode assertions
that check for literal substrings. Tests should be deterministic regardless
of the invoking shell's environment.
"""

from __future__ import annotations

import os

import pytest

os.environ.pop("FORCE_COLOR", None)


@pytest.fixture(scope="session", autouse=True)
def _isolate_ambient_graph_wiki_workspace():
    """Clear `GRAPH_WIKI_WORKSPACE` for the whole test session, every package.

    Test fixtures build their own tmp workspaces and set this var explicitly
    (via `monkeypatch.setenv`) when a test needs it. But `workspace_io.config.resolve()`
    checks the ambient env var first, and any fixture or CLI subprocess call that
    omits an explicit workspace override resolves through it instead of deriving
    from its own repo_root — a shell (or this repo's `.claude/settings.local.json`)
    pinning it to a real workspace then means those calls silently write graph/wiki
    data there instead of to an isolated tmp path. Clearing it once, session-wide,
    closes that gap regardless of which package, fixture, or subprocess is involved
    (subprocess.run inherits this same, now-cleared os.environ); per-test
    `monkeypatch.setenv(...)` still layers on top normally.
    """
    mp = pytest.MonkeyPatch()
    mp.delenv("GRAPH_WIKI_WORKSPACE", raising=False)
    yield
    mp.undo()
