"""Integration: real claude -p run produces tools.json and satisfies a tools assertion.

Requires the claude binary and CLAUDE_CODE_OAUTH_TOKEN. Run with -m integration.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest
from claude_code_evals.orchestrator import run_one
from claude_code_evals.schemas import Config, Scenario

pytestmark = pytest.mark.integration

requires_claude = pytest.mark.skipif(
    shutil.which("claude") is None or not os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"),
    reason="needs claude binary and CLAUDE_CODE_OAUTH_TOKEN",
)


@requires_claude
def test_tools_json_and_assertion_end_to_end(tmp_path: Path):
    fixture = tmp_path / "fixture_src"
    fixture.mkdir()
    (fixture / "README.md").write_text("# Demo\nThe magic word is xyzzy.\n")

    scenario_dir = tmp_path / "evals" / "scenarios" / "tools-it"
    scenario_dir.mkdir(parents=True)
    (scenario_dir / "prompt.md").write_text(
        "Use the Agent tool to dispatch a subagent that reads README.md and reports "
        "the magic word. Then state the magic word yourself."
    )

    scenario = Scenario.model_validate(
        {
            "name": "tools-it",
            "isolation_mode": "fixture",
            "fixture_dir": str(fixture),
            "budgets": {"max_wall_seconds": 240},
            "verify": [
                {
                    "kind": "tools",
                    "assertions": [
                        {"tool": "Agent", "min_count": 1},
                        {"tool": "Read", "params": {"file_path": "README"}, "include_subagents": True},
                    ],
                }
            ],
        }
    )
    config = Config.model_validate({"name": "base"})

    result = run_one(scenario, config, evals_root=tmp_path / "evals")

    assert result.final_status in ("success", "budget_exceeded"), result.error_reason

    tools_path = result.run_dir / "tools.json"
    assert tools_path.exists()
    doc = json.loads(tools_path.read_text())
    assert doc["total_calls"] >= 1
    assert [c["seq"] for c in doc["calls"]] == sorted(c["seq"] for c in doc["calls"])

    # the main agent dispatched a subagent...
    agent_calls = [c for c in doc["calls"] if c["tool"] == "Agent" and c["source"] == "main"]
    assert agent_calls, f"no Agent dispatch found in {[c['tool'] for c in doc['calls']]}"

    # ...so EITHER subagent calls were captured (from stream or JSONL — the
    # empirical question) OR a warning explains their absence. Silence is a bug.
    subagent_calls = [c for c in doc["calls"] if c["source"] == "subagent"]
    assert subagent_calls or doc["warnings"], "Agent dispatched but no subagent calls captured and no warning emitted"

    # record the empirical answer in the test output for the commit message
    feeds = {c.get("parent_tool_use_id") is not None for c in subagent_calls}
    print(
        f"\nEMPIRICAL: {len(subagent_calls)} subagent calls captured; "
        f"parent_tool_use_id present: {feeds}; warnings: {doc['warnings']}"
    )

    # the tools verifier ran and its outcome is in verify.json
    verify_doc = json.loads((result.run_dir / "verify.json").read_text())
    kinds = [v["kind"] for v in verify_doc["verifiers"]]
    assert "ToolsVerifier" in kinds
