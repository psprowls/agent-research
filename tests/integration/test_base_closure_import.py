"""Integration: every non-Bedrock-gated graph-wiki-core module imports against
the BASE dependency closure (no [bedrock] extra).

The permanent regression net for module-scope import leaks in base core
modules (package-layering-review S6; the plugin path depends on this closure —
see plugins/graph-wiki/skills/graph-wiki/scripts/_uv_reexec.py). Two-sided:
non-gated modules MUST import in the base closure; BEDROCK_GATED modules MUST
FAIL to import there, so the denylist cannot rot into over-blocking.
End-to-end proof of the plugin lint path itself lives in
packages/graph-wiki-cli/tests/integration/test_plugin_reexec.py.

Why `--isolated`: `packages/graph-wiki-core` is a member of this repo's uv
workspace, and other members (graph-wiki-cli, graph-wiki-mcp, eval-harness,
subagent-cli) declare `graph-wiki-core[bedrock]`, so the workspace's shared
`.venv` has the Bedrock stack installed regardless of what graph-wiki-core
itself declares — `uv run --project packages/graph-wiki-core` alone resolves
to that same shared venv and would prove nothing. `--isolated` makes uv treat
the target pyproject as a standalone project instead of discovering the
enclosing workspace, so it builds an ephemeral venv seeded from *only*
graph-wiki-core's own `[project.dependencies]` (its BASE closure) — confirmed
empirically: `model_adapter` fails to import under `--isolated` but imports
fine without it.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.environ.get("GRAPH_WIKI_RUN_INTEGRATION"),
        reason="spawns uv subprocesses — set GRAPH_WIKI_RUN_INTEGRATION=1 to run",
    ),
]

REPO_ROOT = Path(__file__).resolve().parents[2]
CORE_SRC = REPO_ROOT / "packages" / "graph-wiki-core" / "src"

# module -> why it is bedrock-gated (its module-scope bedrock-stack import,
# direct or transitive). Enumerated empirically via:
#   env -u VIRTUAL_ENV -u PYTHONPATH \
#     uv run --isolated --project packages/graph-wiki-core python - <<'EOF'
#   ... (import every packages/graph-wiki-core/src/**/*.py module, print failures)
#   EOF
# The two-sided test below keeps this list honest.
BEDROCK_GATED: dict[str, str] = {
    "graph_wiki_core.roles": "module-scope `from model_adapter import make_bedrock_llm, make_gateway_llm`"
    " + `from langchain_core.language_models import BaseChatModel`",
    "graph_wiki_core.agent_loop": "module-scope `from langchain_core.messages import ToolMessage`"
    " + `from langchain_core.tools import BaseTool`",
    "graph_wiki_core.agent_tools": "module-scope `from langchain_core.tools import BaseTool`",
    "graph_wiki_core.graph_tools": "module-scope `from langchain_core.tools import BaseTool, tool`",
    "graph_wiki_core.commands.guidance_recall": "module-scope"
    " `from langchain_core.messages import HumanMessage, SystemMessage`",
    "graph_wiki_core.commands.guidance_scan": "module-scope"
    " `from langchain_core.messages import HumanMessage, SystemMessage`",
    "graph_wiki_core.commands.guidance_suggest": "transitively imports commands.guidance_recall and"
    " commands.next_guidance (both langchain_core.messages-gated)",
    "graph_wiki_core.commands.ingest": "module-scope"
    " `from langchain_core.messages import HumanMessage, SystemMessage`"
    " + `from subagent_runtime.pool import SubagentPool, TaskResult`",
    "graph_wiki_core.commands.lint": "module-scope"
    " `from langchain_core.messages import HumanMessage, SystemMessage`"
    " + `from subagent_runtime.pool import FanOutResult, SubagentPool, TaskResult`"
    " + `from graph_wiki_core.roles import load_role_config, make_llm`",
    "graph_wiki_core.commands.propagate_drift": "module-scope"
    " `from langchain_core.messages import HumanMessage, SystemMessage`",
    "graph_wiki_core.commands.proposal_reasoner": "module-scope"
    " `from langchain_core.messages import HumanMessage, SystemMessage`"
    " + `from langchain_core.tools import BaseTool, tool` (via agent_loop/roles)",
    "graph_wiki_core.commands.propose_domains": "module-scope"
    " `from langchain_core.messages import HumanMessage`"
    " + `from subagent_runtime.pool import FanOutResult, SubagentPool, TaskResult`",
    "graph_wiki_core.commands.query": "module-scope `import bm25s` ([bedrock]-extra-pinned dependency)",
    "graph_wiki_core.commands.query_orchestrator": "module-scope"
    " `from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage`"
    " + `from subagent_runtime.pool import ...` (also transitively imports commands.query's bm25s)",
    "graph_wiki_core.commands.scan": "module-scope `from langchain_core.messages import HumanMessage, SystemMessage`",
    "graph_wiki_core.commands.suggest_pages": "module-scope"
    " `from langchain_core.messages import HumanMessage, SystemMessage`"
    " (also transitively imports commands.proposal_reasoner)",
    "graph_wiki_core.commands.work": "transitively imports"
    " `graph_wiki_core.commands.ingest` (IngestResult), which is langchain_core/subagent_runtime-gated",
    "graph_wiki_core.commands.archive_all": "transitively imports commands.work (gated via commands.ingest)",
    "graph_wiki_core.commands.graph": "transitively imports commands.propose_domains at module scope"
    ' (`graph_app.command("propose-domains")` wiring near end of file)',
    "graph_wiki_core.commands.lint_all": "transitively imports commands.lint and commands.work (both gated)",
    "graph_wiki_core.commands.next_guidance": "transitively imports commands.guidance_recall"
    " (langchain_core.messages) and commands.work (gated via commands.ingest)",
    "graph_wiki_core.commands.package_reader": "module-scope"
    " `from langchain_core.messages import HumanMessage, SystemMessage`"
    " + `from langchain_core.tools import BaseTool, tool` (via agent_loop/agent_tools)",
}


def _all_core_modules() -> list[str]:
    mods: list[str] = []
    for py in sorted(CORE_SRC.rglob("*.py")):
        rel = py.relative_to(CORE_SRC)
        if "__pycache__" in rel.parts:
            continue
        parts = list(rel.with_suffix("").parts)
        if parts[-1] == "__init__":
            parts = parts[:-1]
        mods.append(".".join(parts))
    return mods


def _run_in_base_closure(code: str) -> subprocess.CompletedProcess[str]:
    """Run python code against graph-wiki-core's BASE closure (no extras).

    `--isolated` is required, not optional: without it, `uv run --project`
    resolves to this repo's shared workspace venv, which already has the
    [bedrock] extra installed transitively (other workspace members depend on
    `graph-wiki-core[bedrock]`) and would defeat the whole point of this test.
    The env scrub mirrors the plugin's _uv_reexec mechanism and keeps the
    executing checkout's own VIRTUAL_ENV/PYTHONPATH from leaking in.
    """
    env = {k: v for k, v in os.environ.items() if k not in ("VIRTUAL_ENV", "PYTHONPATH")}
    return subprocess.run(
        [
            "uv",
            "run",
            "--isolated",
            "--project",
            str(REPO_ROOT / "packages" / "graph-wiki-core"),
            "python",
            "-c",
            code,
        ],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=env,
    )


def test_non_gated_core_modules_import_in_base_closure() -> None:
    mods = [m for m in _all_core_modules() if m not in BEDROCK_GATED]
    assert mods, "module sweep found nothing — CORE_SRC layout drift suspected"
    code = (
        "import importlib, sys\n"
        f"mods = {mods!r}\n"
        "for m in mods:\n"
        "    try:\n"
        "        importlib.import_module(m)\n"
        "    except Exception as exc:\n"
        "        print(f'{m}: {type(exc).__name__}: {exc}', file=sys.stderr)\n"
        "        raise SystemExit(1)\n"
    )
    result = _run_in_base_closure(code)
    assert result.returncode == 0, f"base-closure import failed (module named in stderr):\n{result.stderr}"


def test_gated_modules_fail_to_import_in_base_closure() -> None:
    code = (
        "import importlib, sys\n"
        f"mods = {sorted(BEDROCK_GATED)!r}\n"
        "rotten = []\n"
        "for m in mods:\n"
        "    try:\n"
        "        importlib.import_module(m)\n"
        "    except ImportError:\n"
        "        continue\n"
        "    rotten.append(m)\n"
        "if rotten:\n"
        "    print('unexpectedly import fine in base closure: ' + ', '.join(rotten), file=sys.stderr)\n"
        "    raise SystemExit(1)\n"
    )
    result = _run_in_base_closure(code)
    assert result.returncode == 0, f"BEDROCK_GATED rot — remove these entries from the denylist:\n{result.stderr}"
