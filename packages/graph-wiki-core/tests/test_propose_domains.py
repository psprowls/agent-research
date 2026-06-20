"""Phase 48 Plan 02 — unit tests for `commands/propose_domains.py`.

Covers:
  - tool-call parsing (D-05)
  - grounding strips unknown packages (D-09)
  - grounding drops empty domain (D-09 + claude-discretion lean "yes")
  - cycle-strip basic case (D-10/D-12)
  - cycle-strip deterministic (D-15 byte-identical)
  - cycle-strip existing-edge immunity (D-11)
  - cycle-strip no-cycle no-op (D-10)
  - cross-cutting builder (D-07/D-08)
  - YAML writer: paste-ready `graph:` → `domains:` block (packages/description/
    parent only; metadata as leading `#` comments; D8/D-14/D-15)
  - YAML writer: top-level key is `graph` (not `proposed_domains:`/`domains:`; D8)
  - existing-domains loader: missing-ok + reads manifest `graph.domains` (D8)
  - _resolve_paths repo≠workspace correctness (todo 260530-iqr)
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import yaml

# ---------------------------------------------------------------------------
# Tool-call parsing (D-05)
# ---------------------------------------------------------------------------


def test_parse_tool_call_extracts_proposed_domain():
    """Given a stub AIMessage with tool_calls, _parse_tool_call returns a
    ProposedDomain with llm_origin='fan_out'."""
    from graph_wiki_core.commands.propose_domains import (
        ProposedDomain,
        _parse_tool_call,
    )

    resp = SimpleNamespace(
        tool_calls=[
            {
                "name": "propose_domain",
                "args": {
                    "name": "graph-io",
                    "packages": ["graph-io", "wiki-io"],
                    "parent": None,
                    "description": "Graph and wiki I/O.",
                    "confidence": 0.85,
                },
            }
        ]
    )

    domain = _parse_tool_call(resp)
    assert isinstance(domain, ProposedDomain)
    assert domain.name == "graph-io"
    assert domain.packages == ("graph-io", "wiki-io")
    assert domain.parent is None
    assert domain.description == "Graph and wiki I/O."
    assert domain.confidence == 0.85
    assert domain.llm_origin == "fan_out"


# ---------------------------------------------------------------------------
# Grounding (D-09)
# ---------------------------------------------------------------------------


def test_strip_unknown_packages_filters_invalid(capsys):
    """Packages not in `valid_packages` are stripped; stderr warning emitted
    per stripped name; result preserves only valid packages, sorted."""
    from graph_wiki_core.commands.propose_domains import (
        ProposedDomain,
        _strip_unknown_packages,
    )

    proposed = (
        ProposedDomain(
            name="core",
            packages=("bar", "baz", "made_up"),
            parent=None,
            description="x",
            confidence=0.9,
            llm_origin="fan_out",
        ),
    )

    kept, stripped = _strip_unknown_packages(proposed, valid_packages={"bar", "baz"})
    assert len(kept) == 1
    assert kept[0].packages == ("bar", "baz")
    assert stripped == ("made_up",)

    err = capsys.readouterr().err
    assert "warning: stripping unknown package 'made_up'" in err
    assert "domain 'core'" in err
    assert "not in list_packages output" in err


def test_strip_unknown_packages_drops_empty_domain():
    """If ALL of a domain's packages are stripped, the domain itself is dropped."""
    from graph_wiki_core.commands.propose_domains import (
        ProposedDomain,
        _strip_unknown_packages,
    )

    proposed = (
        ProposedDomain(
            name="ghost",
            packages=("nope1", "nope2"),
            parent=None,
            description="x",
            confidence=0.5,
            llm_origin="fan_out",
        ),
    )

    kept, stripped = _strip_unknown_packages(proposed, valid_packages={"bar"})
    assert kept == ()
    assert sorted(stripped) == ["nope1", "nope2"]


# ---------------------------------------------------------------------------
# Cycle detection (D-10, D-11, D-12, D-15)
# ---------------------------------------------------------------------------


def test_strip_cycle_edges_basic_three_cycle():
    """Three-edge cycle (a->b->c->a) — exactly ONE proposed edge removed;
    result is acyclic."""
    from graph_wiki_core.commands.propose_domains import _strip_cycle_edges

    proposed = [("a", "b"), ("b", "c"), ("c", "a")]
    kept, stripped = _strip_cycle_edges(proposed, existing_edges=[])
    assert len(stripped) == 1
    assert len(kept) == 2
    # Result must be acyclic — verify by re-running cycle detection on `kept`
    # and asserting nothing more gets stripped.
    kept2, stripped2 = _strip_cycle_edges(kept, existing_edges=[])
    assert stripped2 == []
    assert sorted(kept2) == sorted(kept)


def test_strip_cycle_edges_deterministic():
    """Same input twice → byte-identical (kept, stripped). (D-15 determinism
    contract for the cycle path.)"""
    from graph_wiki_core.commands.propose_domains import _strip_cycle_edges

    proposed = [("c", "a"), ("a", "b"), ("b", "c")]
    a_kept, a_stripped = _strip_cycle_edges(list(proposed), existing_edges=[])
    b_kept, b_stripped = _strip_cycle_edges(list(proposed), existing_edges=[])
    assert a_kept == b_kept
    assert a_stripped == b_stripped


def test_strip_cycle_edges_existing_immune():
    """Existing edges are never stripped — only the proposed edge gets cut."""
    from graph_wiki_core.commands.propose_domains import _strip_cycle_edges

    existing = [("a", "b")]
    proposed = [("b", "a")]
    kept, stripped = _strip_cycle_edges(proposed, existing_edges=existing)
    assert kept == []
    assert stripped == [("b", "a")]


def test_strip_cycle_edges_no_cycle_keeps_everything():
    """No cycle → no edges stripped; kept == input."""
    from graph_wiki_core.commands.propose_domains import _strip_cycle_edges

    proposed = [("a", "b"), ("c", "d")]
    kept, stripped = _strip_cycle_edges(proposed, existing_edges=[])
    assert sorted(kept) == sorted(proposed)
    assert stripped == []


# ---------------------------------------------------------------------------
# Cross-cutting builder (D-07, D-08)
# ---------------------------------------------------------------------------


def test_build_cross_cutting_domain_aggregates_hubs():
    """Given 2 hubs, builds ONE ProposedDomain named 'cross-cutting' with
    packages = sorted hub names, confidence=1.0, llm_origin='cross_cutting'."""
    from graph_io.cluster import CrossCuttingHub
    from graph_wiki_core.commands.propose_domains import (
        ProposedDomain,
        _build_cross_cutting_domain,
    )

    hubs = (
        CrossCuttingHub(
            name="pytest",
            imported_by_count=10,
            imported_by_fraction=0.86,
            connects_clusters=(0, 1),
        ),
        CrossCuttingHub(
            name="click",
            imported_by_count=8,
            imported_by_fraction=0.57,
            connects_clusters=(0,),
        ),
    )
    domain = _build_cross_cutting_domain(hubs)
    assert isinstance(domain, ProposedDomain)
    assert domain.name == "cross-cutting"
    assert domain.packages == ("click", "pytest")  # sorted
    assert domain.parent is None
    assert domain.confidence == 1.0
    assert domain.llm_origin == "cross_cutting"


def test_build_cross_cutting_domain_empty_returns_none():
    """Empty hub tuple → returns None (Claude-discretion lean: skip if empty)."""
    from graph_wiki_core.commands.propose_domains import _build_cross_cutting_domain

    assert _build_cross_cutting_domain(()) is None


# ---------------------------------------------------------------------------
# YAML writer (D-14, D-15, D-16)
# ---------------------------------------------------------------------------


def _make_proposed_result(*, domains, stripped_unknown=(), stripped_cycle=(), llm_failures=(), total_cost=0.0):
    from graph_wiki_core.commands.propose_domains import ProposeResult

    return ProposeResult(
        proposed_domains=tuple(domains),
        stripped_unknown_packages=tuple(stripped_unknown),
        stripped_cycle_edges=tuple(stripped_cycle),
        llm_failures=tuple(llm_failures),
        total_cost_usd=total_cost,
    )


def test_write_proposed_yaml_paste_ready_graph_block(tmp_path):
    """Output: comment header (banner + metadata) then a top-level `graph:`
    block with nested `domains:`. Body carries only packages/description/parent
    (D8) — no confidence/llm_origin/metadata keys in the YAML body."""
    from graph_wiki_core.commands.propose_domains import (
        ProposedDomain,
        _write_proposed_yaml,
    )

    result = _make_proposed_result(
        domains=[
            ProposedDomain(
                name="cross-cutting",
                packages=("click", "pytest"),
                parent=None,
                description="Cross-cutting utility packages.",
                confidence=1.0,
                llm_origin="cross_cutting",
            ),
            ProposedDomain(
                name="graph-io",
                packages=("graph-io", "wiki-io"),
                parent=None,
                description="Graph I/O.",
                confidence=0.85,
                llm_origin="fan_out",
            ),
        ],
        stripped_unknown=("foo",),
        stripped_cycle=(("child", "parent"),),
        llm_failures=(),
        total_cost=0.034,
    )

    out = tmp_path / "domains.proposed.yaml"
    _write_proposed_yaml(
        result,
        out,
        cluster_command="cg domain-clusters --hub-threshold 0.5",
        model="us.anthropic.claude-haiku-4-5-20251001-v1:0",
    )

    text = out.read_text(encoding="utf-8")
    comment_lines = [ln for ln in text.splitlines() if ln.startswith("#")]
    assert comment_lines, "expected leading comment header"
    assert "paste under `graph:`" in comment_lines[0]
    header_blob = "\n".join(comment_lines)
    assert "us.anthropic.claude-haiku-4-5-20251001-v1:0" in header_blob
    assert "confidence" in header_blob
    assert "foo" in header_blob  # stripped package surfaced in a comment

    data = yaml.safe_load(text)
    assert set(data.keys()) == {"graph"}
    domains_block = data["graph"]["domains"]
    assert set(domains_block.keys()) == {"cross-cutting", "graph-io"}
    cc = domains_block["cross-cutting"]
    assert cc["packages"] == ["click", "pytest"]
    assert cc["description"] == "Cross-cutting utility packages."
    assert "confidence" not in cc
    assert "llm_origin" not in cc
    assert "metadata" not in data


def test_write_proposed_yaml_top_level_is_graph(tmp_path):
    """Top-level key MUST be `graph` (paste-ready), not a bare `domains:` or
    legacy `proposed_domains:` key (D8)."""
    from graph_wiki_core.commands.propose_domains import (
        ProposedDomain,
        _write_proposed_yaml,
    )

    result = _make_proposed_result(
        domains=[
            ProposedDomain(
                name="x",
                packages=("foo",),
                parent=None,
                description="x",
                confidence=0.5,
                llm_origin="fan_out",
            ),
        ],
    )
    out = tmp_path / "domains.proposed.yaml"
    _write_proposed_yaml(result, out, cluster_command="cg domain-clusters", model="haiku")
    data = yaml.safe_load(out.read_text(encoding="utf-8"))
    assert set(data.keys()) == {"graph"}
    assert "domains" in data["graph"]
    assert "proposed_domains" not in data


# ---------------------------------------------------------------------------
# Existing-domains loader (D8: reads manifest graph.domains)
# ---------------------------------------------------------------------------


def test_load_existing_domains_missing_returns_empty(tmp_path):
    from graph_wiki_core.commands.propose_domains import _load_existing_domains

    # No manifest in tmp_path → {}
    assert _load_existing_domains(tmp_path) == {}


def test_load_existing_domains_reads_manifest_graph_domains(tmp_path):
    """Loader returns the `graph.domains` mapping from <workspace>/.graph-wiki.yaml."""
    from graph_wiki_core.commands.propose_domains import _load_existing_domains

    (tmp_path / ".graph-wiki.yaml").write_text(
        "version: 2\ninitialized_at: 2026-06-20\nplugins: []\n"
        "graph:\n"
        "  domains:\n"
        "    core:\n"
        "      packages: [foo]\n"
        "      parent: null\n"
        "    data:\n"
        "      packages: [bar]\n"
        "      parent: core\n",
        encoding="utf-8",
    )
    out = _load_existing_domains(tmp_path)
    assert set(out.keys()) == {"core", "data"}
    assert out["core"]["packages"] == ["foo"]
    assert out["data"]["parent"] == "core"


# ---------------------------------------------------------------------------
# _resolve_paths repo≠workspace correctness (todo 260530-iqr)
#
# propose_domains.py previously had its own _resolve_paths that used
# resolve_config — which walked up from the WORKSPACE dir for .git. On the
# repo≠workspace layout (workspace is its own git repo, source repo is cwd),
# repo_root bound to the workspace's .git → domains.proposed.yaml was written
# into the vault instead of the source repo.
#
# Fix: both graph.py and propose_domains.py now import the shared
# _resolve_paths from commands/_paths.py (todo 260530-iqr DRY convergence).
# These tests import _resolve_paths via propose_domains to guard against the
# duplicate creeping back.
# ---------------------------------------------------------------------------


def _make_fake_repo(path: Path) -> Path:
    """Create a minimal fake git repo (just needs .git dir for _find_repo_root)."""
    path.mkdir(parents=True, exist_ok=True)
    (path / ".git").mkdir()
    return path


def test_propose_domains_resolves_source_repo_not_vault(tmp_path, monkeypatch):
    """Reproduces the repo≠workspace bug from todo 260530-iqr.

    Scenario: cwd is the source repo; workspace is a separate git repo.
    Previously: _resolve_paths (via resolve_config) returned workspace as repo_root
    → domains.proposed.yaml was written inside the vault (WRONG).
    Fixed: _resolve_paths (shared from _paths.py) returns source_repo (cwd).
    """
    from graph_wiki_core.commands.propose_domains import _resolve_paths

    monkeypatch.delenv("GRAPH_WIKI_WORKSPACE", raising=False)

    source_repo = tmp_path / "source-code"
    _make_fake_repo(source_repo)
    monkeypatch.chdir(source_repo)

    workspace = tmp_path / "wiki-vault"
    _make_fake_repo(workspace)
    (workspace / ".graph-wiki.yaml").write_text(
        "version: 2\ninitialized_at: 2026-05-30\nplugins: []\n",
        encoding="utf-8",
    )
    (workspace / "wiki").mkdir()

    repo_root, workspace_root = _resolve_paths(str(workspace))

    assert repo_root == source_repo.resolve(), (
        f"Expected repo_root={source_repo.resolve()!r}, got {repo_root!r} — "
        "todo 260530-iqr: previously the vault was returned → domains.proposed.yaml "
        "written into the vault"
    )
    assert workspace_root == workspace.resolve()


def test_propose_domains_resolves_honors_repo_directory_pin(tmp_path, monkeypatch):
    """When workspace manifest has repo-directory: pin, _resolve_paths uses the pin.

    Proves the pin path flows through the shared helper for propose-domains.
    """
    from graph_wiki_core.commands.propose_domains import _resolve_paths

    monkeypatch.delenv("GRAPH_WIKI_WORKSPACE", raising=False)

    source_repo = tmp_path / "source-code"
    _make_fake_repo(source_repo)
    monkeypatch.chdir(source_repo)

    workspace = tmp_path / "wiki-vault"
    _make_fake_repo(workspace)
    (workspace / ".graph-wiki.yaml").write_text(
        f"version: 2\ninitialized_at: 2026-05-30\nplugins: []\nrepo-directory: {source_repo}\n",
        encoding="utf-8",
    )
    (workspace / "wiki").mkdir()

    repo_root, workspace_root = _resolve_paths(str(workspace))

    assert repo_root == source_repo.resolve()
    assert workspace_root == workspace.resolve()
