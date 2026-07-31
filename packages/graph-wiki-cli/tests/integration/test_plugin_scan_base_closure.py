"""Integration: the plugin scan shim's emit phase runs in the BASE closure.

Epic regression property (e). Before the scan/scan_bedrock split this failed at
import (`ModuleNotFoundError: No module named 'langchain_core'`) — the plugin's
_uv_reexec targets core's base closure on purpose, so a clean plugin install had
no working scan at all. Two-sided module-level coverage lives in
tests/integration/test_base_closure_import.py; this is the end-to-end shape.

`--isolated` is load-bearing: without it `uv run --project` resolves to this
repo's shared workspace venv, which has the [bedrock] extra installed via other
workspace members and would prove nothing.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

INTEGRATION_GATE = pytest.mark.skipif(
    not os.environ.get("GRAPH_WIKI_RUN_INTEGRATION"),
    reason="spawns uv subprocesses — set GRAPH_WIKI_RUN_INTEGRATION=1 to run",
)

REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPT = REPO_ROOT / "plugins" / "graph-wiki" / "skills" / "graph-wiki" / "scripts" / "scan_monorepo.py"
FIXTURE = REPO_ROOT / "packages" / "graph-io" / "tests" / "fixtures" / "sample_monorepo"


def _seed_repo(dest: Path) -> Path:
    shutil.copytree(FIXTURE, dest)
    for argv in (
        ["git", "init", "-q", "-b", "main"],
        ["git", "config", "user.email", "test@example.com"],
        ["git", "config", "user.name", "test"],
        ["git", "add", "."],
        # -c commit.gpgsign=false: a runner with global signing on (and no cached
        # passphrase) would otherwise hang or fail this seed step.
        ["git", "-c", "commit.gpgsign=false", "commit", "-q", "-m", "seeded init"],
    ):
        subprocess.run(argv, cwd=dest, check=True)
    return dest


def _seed_wiki(workspace: Path) -> None:
    wiki = workspace / "wiki"
    (wiki / "entities").mkdir(parents=True)
    (wiki / "log.md").write_text("", encoding="utf-8")
    (wiki / "CLAUDE.md").write_text("# Wiki\n", encoding="utf-8")
    (wiki / "index.md").write_text("---\ntitle: Index\ncategory: meta\nsummary: idx\n---\n\n", encoding="utf-8")
    (workspace / ".graph-wiki").mkdir(parents=True, exist_ok=True)


def _run_shim(args: list[str], *, repo: Path, workspace: Path) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if k not in ("VIRTUAL_ENV", "PYTHONPATH")}
    env["GRAPH_WIKI_WORKSPACE"] = str(workspace)
    env["GRAPH_WIKI_SHIM_REEXEC"] = "1"  # already inside uv run — do not re-exec
    return subprocess.run(
        [
            "uv",
            "run",
            "--isolated",
            "--project",
            str(REPO_ROOT / "packages" / "graph-wiki-core"),
            "python",
            str(SCRIPT),
            *args,
        ],
        capture_output=True,
        text=True,
        cwd=str(repo),
        env=env,
        timeout=900,
    )


@INTEGRATION_GATE
@pytest.mark.integration
def test_plugin_emit_runs_without_the_bedrock_stack(tmp_path: Path) -> None:
    assert SCRIPT.is_file()
    if not FIXTURE.exists():
        pytest.skip(f"sample_monorepo fixture not found at {FIXTURE}")

    repo = _seed_repo(tmp_path / "repo")
    workspace = tmp_path / "workspace"
    _seed_wiki(workspace)
    worklist = workspace / ".graph-wiki" / "worklist.json"

    result = _run_shim(
        ["--emit-worklist", str(worklist), "--workspace", str(workspace)],
        repo=repo,
        workspace=workspace,
    )

    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"

    payload = json.loads(result.stdout)
    assert payload["worklist_path"] == str(worklist)
    assert payload["briefs_dir"] == str(worklist.parent / "briefs")
    assert payload["results_dir"] == str(worklist.parent / "results")
    assert "scan_result" in payload

    assert json.loads(worklist.read_text(encoding="utf-8"))["schema"] == 2
    assert Path(payload["results_dir"]).is_dir()
    briefs = list(Path(payload["briefs_dir"]).glob("*.md"))
    assert briefs, "expected at least one refresh brief from a first-time scan of a populated fixture repo"
    # Briefs must be self-contained: the ownership contract travels with them.
    assert "Deterministic sections are OFF-LIMITS" in briefs[0].read_text(encoding="utf-8")


@INTEGRATION_GATE
@pytest.mark.integration
def test_plugin_apply_round_trips_a_brief_shaped_result_in_the_base_closure(tmp_path: Path) -> None:
    """The apply half of the same round trip, in the same isolated base closure.

    A final whole-feature review found that apply only ever worked when a
    result file was hand-written in the internal ProseRefreshResult.to_dict()
    shape (dict-valued "sections", "uri" present) — never the shape
    PROSE_REFRESHER_SYSTEM actually documents to an out-of-process subagent
    (list-valued "sections", no "uri" mentioned). This writes a result file
    exactly as an agent following the emitted brief's text would, runs apply
    under `uv run --isolated` against core's base closure (no langchain/
    Bedrock stack installed), and reads the entity page back to confirm the
    prose actually landed — not just that apply reported success.
    """
    assert SCRIPT.is_file()
    if not FIXTURE.exists():
        pytest.skip(f"sample_monorepo fixture not found at {FIXTURE}")

    repo = _seed_repo(tmp_path / "repo")
    workspace = tmp_path / "workspace"
    _seed_wiki(workspace)
    worklist = workspace / ".graph-wiki" / "worklist.json"

    emitted = _run_shim(
        ["--emit-worklist", str(worklist), "--workspace", str(workspace)],
        repo=repo,
        workspace=workspace,
    )
    assert emitted.returncode == 0, f"stdout:\n{emitted.stdout}\nstderr:\n{emitted.stderr}"
    payload = json.loads(emitted.stdout)
    briefs_dir = Path(payload["briefs_dir"])
    results_dir = Path(payload["results_dir"])

    # Pick a brief whose declared prose surface includes "## Narrative" (every
    # entity page has it, but this stays honest about reading the brief's own
    # text rather than assuming graph internals).
    brief_path = next(
        p
        for p in sorted(briefs_dir.glob("*.md"))
        if "## Narrative" in p.read_text(encoding="utf-8").split("Current prose sections", 1)[1]
    )
    brief_text = brief_path.read_text(encoding="utf-8")
    uri_line = next(line for line in brief_text.splitlines() if line.startswith("Entity URI: "))
    entity_uri = uri_line.removeprefix("Entity URI: ").strip()
    assert entity_uri

    marker = "Applied via the plugin-path base-closure round trip."
    result_path = results_dir / f"{brief_path.stem}.json"
    result_path.write_text(
        json.dumps(
            {
                "uri": entity_uri,
                "sections": [{"heading": "## Narrative", "replacement_markdown": marker}],
            }
        ),
        encoding="utf-8",
    )

    applied_run = _run_shim(
        ["--results-dir", str(results_dir), "--workspace", str(workspace)],
        repo=repo,
        workspace=workspace,
    )
    assert applied_run.returncode == 0, f"stdout:\n{applied_run.stdout}\nstderr:\n{applied_run.stderr}"
    applied = json.loads(applied_run.stdout)
    assert applied["entity_errors"] == [], applied["entity_errors"]
    assert applied["narrated"] == 1

    pages = [
        p
        for p in (workspace / "wiki" / "entities").glob("*.md")
        if f"uri: {entity_uri}" in p.read_text(encoding="utf-8")
    ]
    assert pages, f"no entity page found with uri {entity_uri}"
    assert marker in pages[0].read_text(encoding="utf-8")
