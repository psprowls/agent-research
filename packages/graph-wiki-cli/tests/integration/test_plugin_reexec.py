"""Integration: plugin lint script self-heals via _uv_reexec from a bare env.

Runs plugins/graph-wiki/skills/graph-wiki/scripts/lint_wiki.py with a Python
interpreter that cannot import graph_wiki_core (the interpreter behind the
workspace venv, no workspace site-packages) and the GRAPH_WIKI_SHIM_REEXEC
guard unset. The shim must re-exec itself under
`uv run --project <repo>/packages/graph-wiki-core` (base closure — the
[bedrock] extra is never requested from the plugin path) and complete the
lint end-to-end. Keystone done-when #2.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

INTEGRATION_GATE = pytest.mark.skipif(
    not os.environ.get("GRAPH_WIKI_RUN_INTEGRATION"),
    reason="Set GRAPH_WIKI_RUN_INTEGRATION=1 to run real Bedrock invocations",
)

REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPT = REPO_ROOT / "plugins" / "graph-wiki" / "skills" / "graph-wiki" / "scripts" / "lint_wiki.py"


def _bare_python() -> Path | None:
    """A python that can NOT import graph_wiki_core — the base interpreter
    behind the workspace venv. None if unavailable (re-exec can't be forced)."""
    candidate = Path(sys.base_prefix) / "bin" / "python3"
    if not candidate.exists():
        return None
    probe = subprocess.run([str(candidate), "-c", "import graph_wiki_core"], capture_output=True, text=True)
    return candidate if probe.returncode != 0 else None


@INTEGRATION_GATE
@pytest.mark.integration
def test_lint_wiki_shim_reexecs_from_bare_env(tmp_path: Path) -> None:
    assert SCRIPT.is_file()
    bare = _bare_python()
    if bare is None:
        pytest.skip("no bare interpreter available to force the re-exec path")

    workspace = tmp_path / "workspace"
    wiki = workspace / "wiki"
    (wiki / "concepts").mkdir(parents=True)
    (wiki / "index.md").write_text(
        "---\ntitle: Index\ncategory: meta\nsummary: idx\n---\n\n[[concepts/a]]\n", encoding="utf-8"
    )
    (wiki / "concepts" / "a.md").write_text(
        "---\ntitle: A\ncategory: concept\nsummary: s\ntokens: 1\nupdated: 2099-01-01\n---\n\nbody\n",
        encoding="utf-8",
    )

    env = {k: v for k, v in os.environ.items() if k not in ("GRAPH_WIKI_SHIM_REEXEC", "VIRTUAL_ENV", "PYTHONPATH")}
    env["GRAPH_WIKI_WORKSPACE"] = str(workspace)

    # cwd is tmp_path on purpose: the shim's upward walk starts from ITS OWN
    # file location (inside the repo), not the cwd — resolution must not
    # depend on where the user happens to invoke the script from.
    result = subprocess.run(
        [str(bare), str(SCRIPT), "--json"],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(tmp_path),
        timeout=600,
    )
    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    report = json.loads(result.stdout)
    assert report["total_pages"] == 1
    assert report["broken_links"] == []
