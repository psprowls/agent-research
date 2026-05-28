"""Phase 48 Plan 03 — end-to-end tests for `graph propose-domains`.

These are *integration* tests in the sense that they exercise the full
pipeline (cg update → compute_clusters → propose_domains_cmd → YAML write +
JSONL trace), but the LLM call is stubbed via monkeypatch so no live Bedrock
network traffic is required. They run by default in CI.

Tests covered:
  - test_propose_domains_e2e_stubbed_llm           — PROPOSE-01 + PROPOSE-04
  - test_propose_domains_e2e_model_override         — PROPOSE-06 (--model flag)
  - test_propose_domains_e2e_no_domains_yaml        — graceful no-existing-domains
  - test_propose_domains_e2e_partial_failure        — D-01 partial-success
"""

# integration-gate-allow — LLM stubbed, runs in CI

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
import yaml

from graph_io import update
from workspace_io.paths import graph_dir

_FIXTURE_SRC = (
    Path(__file__).parent.parent.parent.parent.parent
    / "packages"
    / "graph-io"
    / "tests"
    / "fixtures"
    / "sample_monorepo"
)


# --------------------------------------------------------------------------- #
# Shared fixture: seeded workspace (copied from sample_monorepo + cg update)
# --------------------------------------------------------------------------- #


def _git_init_and_commit(repo_root: Path) -> None:
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo_root, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo_root, check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "test"], cwd=repo_root, check=True,
    )
    subprocess.run(["git", "add", "."], cwd=repo_root, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "seed"], cwd=repo_root, check=True,
    )


@pytest.fixture
def seeded_workspace(tmp_path, monkeypatch):
    """Copy sample_monorepo to tmp_path, git-init, and run `cg update`.

    Returns (repo_root, workspace) tuple. The workspace is the default
    `graph-wiki/` subdirectory inside the repo (per DEFAULT_WORKSPACE_NAME).
    """
    repo_root = tmp_path / "repo"
    shutil.copytree(_FIXTURE_SRC, repo_root)
    _git_init_and_commit(repo_root)
    update.run(repo_root, full=True)
    workspace = (repo_root / "graph-wiki").resolve()
    # Pin GRAPH_WIKI_WORKSPACE so any nested resolve() calls find this
    # workspace deterministically regardless of cwd.
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(workspace))
    return repo_root, workspace


# --------------------------------------------------------------------------- #
# Stub LLM helpers
# --------------------------------------------------------------------------- #


def _make_stub_resp(
    *, name: str, packages: list[str], parent: Any = None,
    description: str = "Stubbed.", confidence: float = 0.9,
) -> Any:
    """Build a stub AIMessage-like object whose `tool_calls` field matches
    the propose_domain tool-use response shape (D-05)."""
    return SimpleNamespace(
        tool_calls=[
            {
                "name": "propose_domain",
                "args": {
                    "name": name,
                    "packages": packages,
                    "parent": parent,
                    "description": description,
                    "confidence": confidence,
                },
            }
        ]
    )


class _StubLLM:
    """Minimal stub for `_GuardedChatBedrockConverse`.

    `bind_tools([...])` returns self; `ainvoke(messages)` returns a precomputed
    response (or raises if `raise_on_call` is set). One stub instance per call;
    `responses` is a list of (response_or_exception) entries consumed in order.
    """

    def __init__(self, responses: list[Any]):
        self._responses = list(responses)
        # Counter so we can assert call count.
        self.call_count = 0

    def bind_tools(self, _tools: list) -> "_StubLLM":
        return self

    async def ainvoke(self, _messages: list) -> Any:
        self.call_count += 1
        if not self._responses:
            # No more queued responses — keep returning the last one.
            return _make_stub_resp(name="extra", packages=[], confidence=0.0)
        item = self._responses.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


def _patch_make_llm(monkeypatch, stub: _StubLLM) -> None:
    """Patch `model_adapter.loader.make_llm` (both the symbol exported by
    `model_adapter.loader` AND the one re-exported into the
    `commands/propose_domains.py` module namespace) so the stub is returned
    regardless of role/override."""
    import model_adapter.loader as _loader_mod
    import graph_wiki_agent.commands.propose_domains as _pd_mod

    def _fake_make_llm(role: str, *, model_override: str | None = None):
        # Stash the requested model_id on the stub so callers (tests) can
        # assert that --model round-tripped through.
        stub.requested_model_override = model_override
        stub.requested_role = role
        return stub

    monkeypatch.setattr(_loader_mod, "make_llm", _fake_make_llm)
    monkeypatch.setattr(_pd_mod, "make_llm", _fake_make_llm)


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #


def test_propose_domains_e2e_stubbed_llm(seeded_workspace, monkeypatch):
    """End-to-end: cg update → propose_domains_cmd → write
    domains.proposed.yaml with proposed_domains+metadata; per-cluster trace
    records land in <workspace>/.graph-wiki/traces/."""
    from graph_wiki_agent.commands.propose_domains import propose_domains_cmd

    repo_root, workspace = seeded_workspace

    # Provide enough stub responses for any plausible cluster count. The
    # sample fixture has 5 packages and a few clusters at hub_threshold=0.5.
    stub = _StubLLM(
        responses=[
            _make_stub_resp(name="core-utils", packages=["mypkg", "pyutil"]),
            _make_stub_resp(name="web-frontend", packages=["jspkg", "webutil"]),
            _make_stub_resp(name="commons", packages=["commonlib"]),
        ]
    )
    _patch_make_llm(monkeypatch, stub)

    propose_domains_cmd(
        workspace=str(workspace), hub_threshold=0.5, model=None
    )

    out = repo_root / "domains.proposed.yaml"
    assert out.exists(), "domains.proposed.yaml must be written"

    text = out.read_text(encoding="utf-8")
    assert text.startswith(
        "# Generated by graph-wiki-agent graph propose-domains"
    )
    data = yaml.safe_load(text)
    assert "proposed_domains" in data
    assert "metadata" in data
    # Every proposed_domains entry must carry the five required keys (D-14).
    for name, info in data["proposed_domains"].items():
        for key in ("packages", "description", "parent", "confidence", "llm_origin"):
            assert key in info, f"domain '{name}' missing key: {key}"

    md = data["metadata"]
    assert isinstance(md["total_cost_usd"], (int, float))
    assert md["total_cost_usd"] >= 0
    assert md["cluster_command"].startswith("cg domain-clusters")

    # Per-cluster trace records must land in <workspace>/.graph-wiki/traces/
    trace_dir = workspace / ".graph-wiki" / "traces"
    assert trace_dir.exists()
    jsonl_files = list(trace_dir.glob("*.jsonl"))
    assert jsonl_files, "expected at least one .jsonl trace file"
    # At least one record must be present — sanity-check by reading the
    # first non-empty line.
    found_record = False
    for jf in jsonl_files:
        for line in jf.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                if rec.get("role") == "domain-proposer":
                    found_record = True
                    break
        if found_record:
            break
    assert found_record, "no domain-proposer trace record found"


def test_propose_domains_e2e_model_override(seeded_workspace, monkeypatch):
    """PROPOSE-06: --model flag round-trips through to trace records and
    metadata."""
    from graph_wiki_agent.commands.propose_domains import propose_domains_cmd

    repo_root, workspace = seeded_workspace
    override = "us.amazon.nova-lite-v1:0"

    stub = _StubLLM(
        responses=[_make_stub_resp(name="x", packages=["mypkg"])] * 6
    )
    _patch_make_llm(monkeypatch, stub)

    propose_domains_cmd(
        workspace=str(workspace), hub_threshold=0.5, model=override
    )

    # Trace records must carry model_id == override (model_adapter received
    # model_override; SubagentPool was told the same effective model_id).
    trace_dir = workspace / ".graph-wiki" / "traces"
    jsonl_files = list(trace_dir.glob("*.jsonl"))
    assert jsonl_files
    saw_override_in_trace = False
    for jf in jsonl_files:
        for line in jf.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec.get("role") == "domain-proposer" and rec.get("model_id") == override:
                saw_override_in_trace = True
    assert saw_override_in_trace, (
        f"expected at least one trace record with model_id={override!r}"
    )

    # YAML metadata.model must also reflect the override.
    out = repo_root / "domains.proposed.yaml"
    data = yaml.safe_load(out.read_text(encoding="utf-8"))
    assert data["metadata"]["model"] == override

    # Sanity-check that the stub recorded the override at the make_llm boundary.
    assert getattr(stub, "requested_model_override", None) == override
    assert getattr(stub, "requested_role", None) == "domain-proposer"


def test_propose_domains_e2e_no_domains_yaml(seeded_workspace, monkeypatch):
    """Workspace without `domains.yaml` does not crash; existing domains
    default to empty, and proposed entries default `parent: null`."""
    from graph_wiki_agent.commands.propose_domains import propose_domains_cmd

    repo_root, workspace = seeded_workspace
    # Remove the seeded domains.yaml so the loader returns {}.
    (repo_root / "domains.yaml").unlink()

    stub = _StubLLM(
        responses=[_make_stub_resp(name="x", packages=["mypkg"])] * 6
    )
    _patch_make_llm(monkeypatch, stub)

    # Must not raise.
    propose_domains_cmd(
        workspace=str(workspace), hub_threshold=0.5, model=None
    )

    out = repo_root / "domains.proposed.yaml"
    assert out.exists()
    data = yaml.safe_load(out.read_text(encoding="utf-8"))
    for _name, info in data["proposed_domains"].items():
        # No existing domains → LLM has no parent options. Our stub returns
        # parent=None anyway; either way the schema must allow null.
        assert info["parent"] is None


def test_propose_domains_e2e_partial_failure(seeded_workspace, monkeypatch):
    """D-01 partial-success: one cluster failure does not abort the run; the
    failed cluster surfaces in metadata.llm_failures."""
    from graph_wiki_agent.commands.propose_domains import propose_domains_cmd

    repo_root, workspace = seeded_workspace

    # First call succeeds, second raises, remaining succeed.
    stub = _StubLLM(
        responses=[
            _make_stub_resp(name="ok-one", packages=["mypkg"]),
            RuntimeError("synthetic LLM failure for partial-success test"),
            _make_stub_resp(name="ok-two", packages=["pyutil"]),
            _make_stub_resp(name="ok-three", packages=["commonlib"]),
            _make_stub_resp(name="ok-four", packages=["jspkg"]),
        ]
    )
    _patch_make_llm(monkeypatch, stub)

    # Must not raise — partial-success semantics from SubagentPool.run_all.
    propose_domains_cmd(
        workspace=str(workspace), hub_threshold=0.5, model=None
    )

    out = repo_root / "domains.proposed.yaml"
    assert out.exists()
    data = yaml.safe_load(out.read_text(encoding="utf-8"))
    assert "metadata" in data
    failures = data["metadata"]["llm_failures"]
    assert isinstance(failures, list)
    assert len(failures) >= 1, (
        "expected at least one cluster failure to surface in metadata.llm_failures"
    )
    # Other clusters still produced proposals.
    assert len(data["proposed_domains"]) >= 1
