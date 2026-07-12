"""Tests for `wiki_io.index_generator` — Phase 44 Plans 01 + 02.

Layout:
- Plan 01 unit tests: TestIndexWriteResult, TestQualifyingDomains, TestPlacement,
  TestCuratedScan, TestWorkScan, TestRenderDomainTree, TestRenderByKind, plus
  the happy-path integration test `test_generate_index_against_fixture_graph`.
- Plan 02 acceptance tests: determinism, write-if-changed, single-placement
  edge cases, sub-domain nesting, empty-omission, curated consolidation,
  generated-files exclusion, plus a syrupy snapshot against the live
  agent-research graph (skipped when no live graph is present).
"""

from __future__ import annotations

import dataclasses
import random
import sqlite3
import time
from pathlib import Path

import pytest
from graph_io.handle import GraphReader
from wiki_io.index_generator import (
    BY_KIND_ORDER,
    CURATED_LANES,
    GENERATED_FILES,
    KIND_HEADING_LABELS,
    IndexWriteResult,
    _compute_qualifying_domains,
    _consumer_pkgs,
    _consumer_pkgs_in_domain,
    _parse_repo_key,
    _place_entities,
    _render,
    _render_concepts_section,
    _render_guidance_section,
    _scan_curated_lane,
    _scan_guidance_topics,
    _scan_work,
    generate_index,
)


def _place(conn):
    """Call _place_entities with a no-pages wiki_root + empty collision_set.

    Repository grouping (2026-06-12): _place_entities returns
    (per_repo, name_to_entity, domain_repo). These placement tests only care
    about the per-repo buckets; with no entity pages on disk all summaries
    degrade to "".
    """
    per_repo, _name_to_entity, _domain_repo = _place_entities(conn, Path("/nonexistent-wiki-root"), frozenset())
    return per_repo


# ============================================================================
# Plan 01 / Task 1 — IndexWriteResult + module constants
# ============================================================================


class TestIndexWriteResult:
    def test_frozen(self):
        r = IndexWriteResult(
            path=Path("/x"),
            bytes_written=0,
            changed=False,
            entity_count=0,
            curated_count=0,
            domain_count=0,
            direct_count=0,
            repo_count=0,
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.changed = True  # type: ignore[misc]

    def test_module_constants(self):
        # D-R6: BY_KIND_ORDER survives as the kind-major heading order.
        assert BY_KIND_ORDER == ("app", "package", "agent_plugin")
        # D-R5: singular kind heading labels.
        assert KIND_HEADING_LABELS == {"app": "App", "package": "Package", "agent_plugin": "Agent Plugin"}
        assert len(CURATED_LANES) == 3
        assert CURATED_LANES[0] == ("adrs", "adrs", "ADRs")
        assert CURATED_LANES[1] == ("concepts", "concepts", "Concepts")
        assert CURATED_LANES[2] == ("sources", "sources", "Sources")
        assert "architecture/index.md" not in GENERATED_FILES
        assert "index.md" in GENERATED_FILES
        assert "concepts/index.md" in GENERATED_FILES

    def test_entry_link_wiki_vs_work(self):
        from wiki_io.wikilinks import vault_wikilink

        assert vault_wikilink("work/foo.md", "Foo") == "[[work/foo|Foo]]"
        assert vault_wikilink("concepts/foo.md", "Foo") == "[[concepts/foo|Foo]]"


# ============================================================================
# 2026-06-12 repository grouping Task 1 — _parse_repo_key (D-R7)
# ============================================================================


class TestParseRepoKey:
    """D-R7 — extract '{org}/{repo}' from the Phase-28 URI shapes."""

    @pytest.mark.parametrize(
        "uri",
        [
            "pkg:local/agent-research/pkg-a",
            "app:local/agent-research/myapp",
            "agent_plugin:local/agent-research/graph-wiki",
            "domain:local/agent-research/core",
            "test_suite:local/agent-research/unit",
            "test_suite:local/agent-research/packages/alpha/tests",
        ],
    )
    def test_repo_scoped_schemes(self, uri):
        assert _parse_repo_key(uri) == "local/agent-research"

    def test_repo_scheme_exactly_two_segments(self):
        assert _parse_repo_key("repo:local/agent-research") == "local/agent-research"

    @pytest.mark.parametrize("uri", ["dependency:pypi/boto3", "builtin:python/os"])
    def test_repo_less_schemes_return_none(self, uri):
        assert _parse_repo_key(uri) is None

    @pytest.mark.parametrize(
        "uri",
        [
            "",
            "no-colon",
            "pkg:",
            "pkg:pkg-a",  # 1 segment — no org/repo
            "pkg:agent-research/pkg-a",  # 2 segments — ambiguous, malformed
            "repo:agent-research",  # repo scheme needs exactly 2
            "repo:a/b/c",  # repo scheme needs exactly 2
        ],
    )
    def test_malformed_return_none(self, uri):
        assert _parse_repo_key(uri) is None


# ============================================================================
# Plan 01 / Task 2 — Qualifying domains + placement
# ============================================================================


class TestQualifyingDomains:
    def test_package_with_one_domain(self, make_index_fixture_graph):
        spec = {
            "nodes": [
                ("domain", "core", {"uri": "domain:core"}),
                ("package", "pkg-a", {"uri": "pkg:pkg-a"}),
            ],
            "edges": [
                ("package", "pkg-a", "domain", "core", "belongs_to_domain", {}),
            ],
        }
        conn = make_index_fixture_graph(spec)
        assert _compute_qualifying_domains(conn, kind="package", name="pkg-a") == {"core"}

    def test_package_with_zero_domains(self, make_index_fixture_graph):
        spec = {
            "nodes": [
                ("package", "pkg-a", {"uri": "pkg:pkg-a"}),
            ],
            "edges": [],
        }
        conn = make_index_fixture_graph(spec)
        assert _compute_qualifying_domains(conn, kind="package", name="pkg-a") == set()

    def test_package_with_multi_domains(self, make_index_fixture_graph):
        spec = {
            "nodes": [
                ("domain", "core", {"uri": "domain:core"}),
                ("domain", "billing", {"uri": "domain:billing"}),
                ("package", "pkg-a", {"uri": "pkg:pkg-a"}),
            ],
            "edges": [
                ("package", "pkg-a", "domain", "core", "belongs_to_domain", {}),
                ("package", "pkg-a", "domain", "billing", "belongs_to_domain", {}),
            ],
        }
        conn = make_index_fixture_graph(spec)
        assert _compute_qualifying_domains(conn, kind="package", name="pkg-a") == {"core", "billing"}

    def test_test_suite_one_hop(self, make_index_fixture_graph):
        spec = {
            "nodes": [
                ("domain", "core", {"uri": "domain:core"}),
                ("package", "pkg-a", {"uri": "pkg:pkg-a"}),
                ("test_suite", "suite-a", {"uri": "test_suite:suite-a"}),
            ],
            "edges": [
                ("package", "pkg-a", "domain", "core", "belongs_to_domain", {}),
                ("test_suite", "suite-a", "package", "pkg-a", "tests", {}),
            ],
        }
        conn = make_index_fixture_graph(spec)
        assert _compute_qualifying_domains(conn, kind="test_suite", name="suite-a", uri="test_suite:suite-a") == {
            "core"
        }

    def test_test_suite_multi_package_multi_domain(self, make_index_fixture_graph):
        spec = {
            "nodes": [
                ("domain", "d1", {"uri": "domain:d1"}),
                ("domain", "d2", {"uri": "domain:d2"}),
                ("package", "pkg-1", {"uri": "pkg:pkg-1"}),
                ("package", "pkg-2", {"uri": "pkg:pkg-2"}),
                ("test_suite", "suite", {"uri": "test_suite:suite"}),
            ],
            "edges": [
                ("package", "pkg-1", "domain", "d1", "belongs_to_domain", {}),
                ("package", "pkg-2", "domain", "d2", "belongs_to_domain", {}),
                ("test_suite", "suite", "package", "pkg-1", "tests", {}),
                ("test_suite", "suite", "package", "pkg-2", "tests", {}),
            ],
        }
        conn = make_index_fixture_graph(spec)
        assert _compute_qualifying_domains(conn, kind="test_suite", name="suite", uri="test_suite:suite") == {
            "d1",
            "d2",
        }

    def test_dependency_one_hop(self, make_index_fixture_graph):
        spec = {
            "nodes": [
                ("domain", "core", {"uri": "domain:core"}),
                ("package", "pkg-a", {"uri": "pkg:pkg-a"}),
                ("dependency", "boto3", {"uri": "dependency:pypi/boto3", "ecosystem": "pypi"}),
            ],
            "edges": [
                ("package", "pkg-a", "domain", "core", "belongs_to_domain", {}),
                ("package", "pkg-a", "dependency", "boto3", "used_by", {}),
            ],
        }
        conn = make_index_fixture_graph(spec)
        assert _compute_qualifying_domains(conn, kind="dependency", name="boto3") == {"core"}

    def test_dependency_multi_consumer_same_domain(self, make_index_fixture_graph):
        spec = {
            "nodes": [
                ("domain", "core", {"uri": "domain:core"}),
                ("package", "pkg-a", {"uri": "pkg:pkg-a"}),
                ("package", "pkg-b", {"uri": "pkg:pkg-b"}),
                ("dependency", "boto3", {"uri": "dependency:pypi/boto3", "ecosystem": "pypi"}),
            ],
            "edges": [
                ("package", "pkg-a", "domain", "core", "belongs_to_domain", {}),
                ("package", "pkg-b", "domain", "core", "belongs_to_domain", {}),
                ("package", "pkg-a", "dependency", "boto3", "used_by", {}),
                ("package", "pkg-b", "dependency", "boto3", "used_by", {}),
            ],
        }
        conn = make_index_fixture_graph(spec)
        assert _compute_qualifying_domains(conn, kind="dependency", name="boto3") == {"core"}

    def test_dependency_multi_consumer_multi_domain(self, make_index_fixture_graph):
        spec = {
            "nodes": [
                ("domain", "d1", {"uri": "domain:d1"}),
                ("domain", "d2", {"uri": "domain:d2"}),
                ("package", "pkg-a", {"uri": "pkg:pkg-a"}),
                ("package", "pkg-b", {"uri": "pkg:pkg-b"}),
                ("dependency", "boto3", {"uri": "dependency:pypi/boto3", "ecosystem": "pypi"}),
            ],
            "edges": [
                ("package", "pkg-a", "domain", "d1", "belongs_to_domain", {}),
                ("package", "pkg-b", "domain", "d2", "belongs_to_domain", {}),
                ("package", "pkg-a", "dependency", "boto3", "used_by", {}),
                ("package", "pkg-b", "dependency", "boto3", "used_by", {}),
            ],
        }
        conn = make_index_fixture_graph(spec)
        assert _compute_qualifying_domains(conn, kind="dependency", name="boto3") == {"d1", "d2"}

    def test_agent_plugin_always_empty(self, make_index_fixture_graph):
        spec = {
            "nodes": [
                ("agent_plugin", "graph-wiki", {"uri": "agent_plugin:o/r/graph-wiki", "ecosystem": "claude-code"}),
            ],
            "edges": [],
        }
        conn = make_index_fixture_graph(spec)
        assert _compute_qualifying_domains(conn, kind="agent_plugin", name="graph-wiki") == set()

    def test_invalid_kind_raises(self, make_index_fixture_graph):
        conn = make_index_fixture_graph({"nodes": [], "edges": []})
        with pytest.raises(ValueError):
            _compute_qualifying_domains(conn, kind="file", name="x")


REPO_NODE = ("repository", "agent-research", {"uri": "repo:local/agent-research"})


class TestPlacement:
    def test_single_domain_goes_to_section(self, make_index_fixture_graph):
        spec = {
            "nodes": [
                REPO_NODE,
                ("domain", "core", {"uri": "domain:local/agent-research/core"}),
                ("package", "pkg-a", {"uri": "pkg:local/agent-research/pkg-a"}),
            ],
            "edges": [
                ("package", "pkg-a", "domain", "core", "belongs_to_domain", {}),
            ],
        }
        conn = make_index_fixture_graph(spec)
        per_repo = _place(conn)
        assert list(per_repo) == ["agent-research"]
        buckets, direct = per_repo["agent-research"]
        assert "core" in buckets
        assert len(buckets["core"]) == 1
        assert buckets["core"][0].kind == "package"
        assert buckets["core"][0].name == "pkg-a"
        assert direct == []

    def test_zero_domain_goes_direct(self, make_index_fixture_graph):
        spec = {
            "nodes": [
                REPO_NODE,
                ("package", "pkg-cross", {"uri": "pkg:local/agent-research/pkg-cross"}),
            ],
            "edges": [],
        }
        conn = make_index_fixture_graph(spec)
        buckets, direct = _place(conn)["agent-research"]
        assert buckets == {}
        assert len(direct) == 1
        assert direct[0].kind == "package"
        assert direct[0].name == "pkg-cross"

    def test_multi_domain_goes_direct(self, make_index_fixture_graph):
        spec = {
            "nodes": [
                REPO_NODE,
                ("domain", "d1", {"uri": "domain:local/agent-research/d1"}),
                ("domain", "d2", {"uri": "domain:local/agent-research/d2"}),
                ("package", "pkg-1", {"uri": "pkg:local/agent-research/pkg-1"}),
                ("package", "pkg-2", {"uri": "pkg:local/agent-research/pkg-2"}),
                ("test_suite", "suite", {"uri": "test_suite:local/agent-research/suite"}),
            ],
            "edges": [
                ("package", "pkg-1", "domain", "d1", "belongs_to_domain", {}),
                ("package", "pkg-2", "domain", "d2", "belongs_to_domain", {}),
                ("test_suite", "suite", "package", "pkg-1", "tests", {}),
                ("test_suite", "suite", "package", "pkg-2", "tests", {}),
            ],
        }
        conn = make_index_fixture_graph(spec)
        buckets, direct = _place(conn)["agent-research"]
        suite_direct = [e for e in direct if e.name == "suite"]
        assert len(suite_direct) == 1
        for d in buckets.values():
            assert not any(e.name == "suite" for e in d)

    def test_agent_plugin_always_direct(self, make_index_fixture_graph):
        # agent_plugin URI parses to "o/r" which matches no repo node —
        # exercises the defensive single-repo fallback too.
        spec = {
            "nodes": [
                REPO_NODE,
                ("agent_plugin", "graph-wiki", {"uri": "agent_plugin:o/r/graph-wiki", "ecosystem": "claude-code"}),
            ],
            "edges": [],
        }
        conn = make_index_fixture_graph(spec)
        buckets, direct = _place(conn)["agent-research"]
        assert any(e.kind == "agent_plugin" and e.name == "graph-wiki" for e in direct)
        assert buckets == {}

    def test_direct_sort_order(self, make_index_fixture_graph):
        spec = {
            "nodes": [
                REPO_NODE,
                # insertion order intentionally not matching _PLACEABLE_KINDS
                ("agent_plugin", "graph-wiki", {"uri": "agent_plugin:o/r/graph-wiki", "ecosystem": "claude-code"}),
                ("package", "pkg-cross", {"uri": "pkg:local/agent-research/pkg-cross"}),
                ("dependency", "boto3", {"uri": "dependency:pypi/boto3", "ecosystem": "pypi"}),
            ],
            "edges": [],
        }
        conn = make_index_fixture_graph(spec)
        _buckets, direct = _place(conn)["agent-research"]
        kinds = [e.kind for e in direct if e.name in ("graph-wiki", "pkg-cross", "boto3")]
        assert kinds == ["package", "dependency", "agent_plugin"]

    def test_intra_domain_parent_pkgs_populated(self, make_index_fixture_graph):
        spec = {
            "nodes": [
                REPO_NODE,
                ("domain", "core", {"uri": "domain:local/agent-research/core"}),
                ("package", "pkg-a", {"uri": "pkg:local/agent-research/pkg-a"}),
                ("package", "pkg-b", {"uri": "pkg:local/agent-research/pkg-b"}),
                ("dependency", "boto3", {"uri": "dependency:pypi/boto3", "ecosystem": "pypi"}),
            ],
            "edges": [
                ("package", "pkg-a", "domain", "core", "belongs_to_domain", {}),
                ("package", "pkg-b", "domain", "core", "belongs_to_domain", {}),
                ("package", "pkg-a", "dependency", "boto3", "used_by", {}),
                ("package", "pkg-b", "dependency", "boto3", "used_by", {}),
            ],
        }
        conn = make_index_fixture_graph(spec)
        buckets, _direct = _place(conn)["agent-research"]
        deps = [e for e in buckets["core"] if e.kind == "dependency"]
        assert len(deps) == 1
        assert deps[0].parent_pkg_names == ("pkg-a", "pkg-b")

    # --- 2026-06-12 repository grouping: repo resolution ---

    def test_multi_repo_split_by_uri(self, make_index_fixture_graph):
        spec = {
            "nodes": [
                ("repository", "repo-alpha", {"uri": "repo:local/repo-alpha"}),
                ("repository", "repo-beta", {"uri": "repo:local/repo-beta"}),
                ("package", "pkg-one", {"uri": "pkg:local/repo-alpha/pkg-one"}),
                ("package", "pkg-two", {"uri": "pkg:local/repo-beta/pkg-two"}),
            ],
            "edges": [],
        }
        conn = make_index_fixture_graph(spec)
        per_repo = _place(conn)
        assert sorted(per_repo) == ["repo-alpha", "repo-beta"]
        _, direct_alpha = per_repo["repo-alpha"]
        _, direct_beta = per_repo["repo-beta"]
        assert [e.name for e in direct_alpha] == ["pkg-one"]
        assert [e.name for e in direct_beta] == ["pkg-two"]

    def test_domain_repo_membership_from_domain_uri(self, make_index_fixture_graph):
        # D-R2: the DOMAIN's own URI decides where its block lives — an
        # entity placed in that domain follows the domain, not its own URI.
        spec = {
            "nodes": [
                ("repository", "repo-alpha", {"uri": "repo:local/repo-alpha"}),
                ("repository", "repo-beta", {"uri": "repo:local/repo-beta"}),
                ("domain", "core", {"uri": "domain:local/repo-beta/core"}),
                ("package", "pkg-one", {"uri": "pkg:local/repo-alpha/pkg-one"}),
            ],
            "edges": [
                ("package", "pkg-one", "domain", "core", "belongs_to_domain", {}),
            ],
        }
        conn = make_index_fixture_graph(spec)
        per_repo = _place(conn)
        buckets_beta, _ = per_repo["repo-beta"]
        assert [e.name for e in buckets_beta["core"]] == ["pkg-one"]
        assert "repo-alpha" not in per_repo

    def test_unparseable_uri_with_single_repo_falls_in(self, make_index_fixture_graph):
        spec = {
            "nodes": [
                REPO_NODE,
                ("package", "pkg-x", {"uri": "pkg:pkg-x"}),  # 1 segment — malformed
            ],
            "edges": [],
        }
        conn = make_index_fixture_graph(spec)
        _buckets, direct = _place(conn)["agent-research"]
        assert [e.name for e in direct] == ["pkg-x"]

    def test_unparseable_uri_with_multi_repo_raises(self, make_index_fixture_graph):
        spec = {
            "nodes": [
                ("repository", "repo-alpha", {"uri": "repo:local/repo-alpha"}),
                ("repository", "repo-beta", {"uri": "repo:local/repo-beta"}),
                ("package", "pkg-x", {"uri": "pkg:pkg-x"}),
            ],
            "edges": [],
        }
        conn = make_index_fixture_graph(spec)
        with pytest.raises(ValueError, match="cannot resolve repository"):
            _place(conn)

    def test_zero_repos_with_entity_raises(self, make_index_fixture_graph):
        spec = {
            "nodes": [
                ("package", "pkg-x", {"uri": "pkg:local/agent-research/pkg-x"}),
            ],
            "edges": [],
        }
        conn = make_index_fixture_graph(spec)
        with pytest.raises(ValueError, match="cannot resolve repository"):
            _place(conn)

    def test_zero_repos_zero_entities_empty(self, make_index_fixture_graph):
        conn = make_index_fixture_graph({"nodes": [], "edges": []})
        assert _place(conn) == {}

    def test_parseable_uri_unmatched_key_multi_repo_raises(self, make_index_fixture_graph):
        # Well-formed URI whose {org}/{repo} matches NO repository node —
        # distinct branch from the malformed-URI case above.
        spec = {
            "nodes": [
                ("repository", "repo-alpha", {"uri": "repo:local/repo-alpha"}),
                ("repository", "repo-beta", {"uri": "repo:local/repo-beta"}),
                ("package", "pkg-x", {"uri": "pkg:local/nonexistent/pkg-x"}),
            ],
            "edges": [],
        }
        conn = make_index_fixture_graph(spec)
        with pytest.raises(ValueError, match="cannot resolve repository"):
            _place(conn)


# ============================================================================
# Plan 01 / Task 3 — Curated and work scan
# ============================================================================


def _write_curated_page(path: Path, *, title: str, summary: str = ""):
    """Helper — write a markdown page with frontmatter."""
    path.parent.mkdir(parents=True, exist_ok=True)
    content = f"---\ntitle: {title}\n"
    if summary:
        content += f"summary: {summary}\n"
    content += "---\n\nBody content.\n"
    path.write_text(content, encoding="utf-8")


class TestCuratedScan:
    def test_empty_directory(self, tmp_path):
        (tmp_path / "concepts").mkdir()
        assert _scan_curated_lane(tmp_path, "concepts") == []

    def test_missing_directory(self, tmp_path):
        assert _scan_curated_lane(tmp_path, "nonexistent") == []

    def test_basic_scan_with_frontmatter(self, tmp_path):
        _write_curated_page(tmp_path / "concepts" / "foo.md", title="Foo Page", summary="Test summary")
        entries = _scan_curated_lane(tmp_path, "concepts")
        assert len(entries) == 1
        assert entries[0]["title"] == "Foo Page"
        assert entries[0]["summary"] == "Test summary"
        assert entries[0]["path"] == "concepts/foo.md"

    def test_skips_generated_files(self, tmp_path):
        _write_curated_page(tmp_path / "concepts" / "foo.md", title="Foo")
        _write_curated_page(tmp_path / "concepts" / "index.md", title="Index")
        entries = _scan_curated_lane(tmp_path, "concepts")
        titles = [e["title"] for e in entries]
        assert titles == ["Foo"]

    def test_skips_dotfiles(self, tmp_path):
        _write_curated_page(tmp_path / "concepts" / ".git" / "foo.md", title="Foo")
        _write_curated_page(tmp_path / "concepts" / ".hidden" / "bar.md", title="Bar")
        assert _scan_curated_lane(tmp_path, "concepts") == []

    def test_title_fallback_from_filename(self, tmp_path):
        page = tmp_path / "concepts" / "my-cool-page.md"
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text("# My Cool Page\n\nbody", encoding="utf-8")  # no frontmatter
        entries = _scan_curated_lane(tmp_path, "concepts")
        assert len(entries) == 1
        assert entries[0]["title"] == "My Cool Page"

    def test_sort_order_alphabetical_by_title(self, tmp_path):
        _write_curated_page(tmp_path / "concepts" / "a.md", title="Zeta")
        _write_curated_page(tmp_path / "concepts" / "b.md", title="alpha")
        _write_curated_page(tmp_path / "concepts" / "c.md", title="Mu")
        entries = _scan_curated_lane(tmp_path, "concepts")
        assert [e["title"] for e in entries] == ["alpha", "Mu", "Zeta"]


class TestWorkScan:
    def test_no_work_directory(self, tmp_path):
        assert _scan_work(tmp_path) == []

    def test_basic_work_scan(self, tmp_path):
        _write_curated_page(tmp_path / "wiki" / "work" / "2026-05-03-foo.md", title="Foo work item")
        entries = _scan_work(tmp_path)
        assert len(entries) == 1
        assert entries[0]["path"] == "work/2026-05-03-foo.md"

    def test_skips_work_index(self, tmp_path):
        _write_curated_page(tmp_path / "wiki" / "work" / "foo.md", title="Foo")
        _write_curated_page(tmp_path / "wiki" / "work" / "index.md", title="Idx")
        entries = _scan_work(tmp_path)
        assert [e["title"] for e in entries] == ["Foo"]

    def test_skips_archived_subdir(self, tmp_path):
        _write_curated_page(tmp_path / "wiki" / "work" / "foo.md", title="Foo")
        _write_curated_page(tmp_path / "wiki" / "work" / "_archive" / "old.md", title="Old")
        entries = _scan_work(tmp_path)
        assert [e["title"] for e in entries] == ["Foo"]


# ============================================================================
# Plan 01 / Task 4 — Render helpers + integration
# ============================================================================


class TestRenderDomainTree:
    def test_single_domain_with_one_package(self, tmp_path, make_index_fixture_graph):
        spec = {
            "nodes": [
                ("repository", "agent-research", {"uri": "repo:agent-research"}),
                ("domain", "core", {"uri": "domain:agent-research/core"}),
                ("package", "pkg-a", {"uri": "pkg:agent-research/pkg-a"}),
            ],
            "edges": [
                ("package", "pkg-a", "domain", "core", "belongs_to_domain", {}),
            ],
        }
        conn = make_index_fixture_graph(spec)
        wiki_root = tmp_path / "wiki"
        wiki_root.mkdir(parents=True, exist_ok=True)
        text, *_ = _render(conn, wiki_root)
        assert "\n## Repository: agent-research" in text
        assert "## Domains" not in text
        assert "\n### Domain: core" in text
        assert "\n#### Package: pkg-a" in text
        assert "[[entities/pkg_pkg-a|open page]]" in text

    def test_sub_domain_nesting(self, tmp_path, make_index_fixture_graph):
        spec = {
            "nodes": [
                ("repository", "agent-research", {"uri": "repo:agent-research"}),
                ("domain", "core", {"uri": "domain:agent-research/core"}),
                ("domain", "billing", {"uri": "domain:agent-research/billing"}),
                ("package", "pkg-core", {"uri": "pkg:agent-research/pkg-core"}),
                ("package", "pkg-billing", {"uri": "pkg:agent-research/pkg-billing"}),
            ],
            "edges": [
                ("package", "pkg-core", "domain", "core", "belongs_to_domain", {}),
                ("package", "pkg-billing", "domain", "billing", "belongs_to_domain", {}),
                ("domain", "core", "domain", "billing", "domain_contains_domain", {}),
            ],
        }
        conn = make_index_fixture_graph(spec)
        wiki_root = tmp_path / "wiki"
        wiki_root.mkdir(parents=True, exist_ok=True)
        text, *_ = _render(conn, wiki_root)
        assert "\n### Domain: core" in text
        assert "\n#### Sub-Domain: billing" in text
        assert "\n### Domain: billing" not in text
        assert "\n#### Package: pkg-core" in text
        assert "\n##### Package: pkg-billing" in text

    def test_empty_domain_omitted(self, tmp_path, make_index_fixture_graph):
        spec = {
            "nodes": [
                ("repository", "agent-research", {"uri": "repo:agent-research"}),
                ("domain", "empty-domain", {"uri": "domain:empty-domain"}),
            ],
            "edges": [],
        }
        conn = make_index_fixture_graph(spec)
        wiki_root = tmp_path / "wiki"
        wiki_root.mkdir(parents=True, exist_ok=True)
        text, *_ = _render(conn, wiki_root)
        assert "Domain: empty-domain" not in text
        # repo has no entities at all -> whole repo section omitted (D-08)
        assert "## Repository:" not in text


class TestRenderDirectEntities:
    def test_direct_entities_kind_major_order(self, tmp_path, make_index_fixture_graph):
        # D-R6: apps first, then packages, then agent plugins — as `###`
        # kind-prefixed headings directly under the repo header. A dependency
        # used by a direct package nests UNDER that package (no flat groups).
        spec = {
            "nodes": [
                ("repository", "agent-research", {"uri": "repo:agent-research"}),
                ("app", "myapp", {"uri": "app:agent-research/myapp", "app_kind": "cli"}),
                ("package", "pkg-cross", {"uri": "pkg:pkg-cross"}),
                ("dependency", "boto3", {"uri": "dependency:pypi/boto3", "ecosystem": "pypi"}),
                ("agent_plugin", "graph-wiki", {"uri": "agent_plugin:o/r/graph-wiki", "ecosystem": "claude-code"}),
            ],
            "edges": [
                ("package", "pkg-cross", "dependency", "boto3", "used_by", {}),
            ],
        }
        conn = make_index_fixture_graph(spec)
        wiki_root = tmp_path / "wiki"
        wiki_root.mkdir(parents=True, exist_ok=True)
        text, *_ = _render(conn, wiki_root)
        assert "\n## Repository: agent-research" in text
        app_idx = text.find("\n### App: myapp")
        pkg_idx = text.find("\n### Package: pkg-cross")
        plug_idx = text.find("\n### Agent Plugin: graph-wiki")
        assert app_idx > -1 and pkg_idx > -1 and plug_idx > -1
        assert app_idx < pkg_idx < plug_idx
        assert "[[entities/pkg_pkg-cross|open page]]" in text
        assert "[[entities/app_myapp|open page]]" in text
        assert "[[entities/agent-plugin_graph-wiki|open page]]" in text
        # Removed structure never renders.
        assert "## By Kind" not in text
        assert "### Apps" not in text
        assert "### Packages" not in text
        assert "### Agent Plugins" not in text
        # No flat dependency group; boto3 still nests under pkg-cross (bullet).
        assert "  - Dependencies" in text
        assert "[[entities/dep_boto3|boto3]]" in text

    def test_direct_entity_summary_renders_before_open_page_link(self, tmp_path, make_index_fixture_graph):
        """A direct entity with a `summary:` renders `{summary} — [[…|open page]]`
        on the line beneath its kind-prefixed heading (summary-first ordering)."""
        spec = {
            "nodes": [
                ("repository", "agent-research", {"uri": "repo:agent-research"}),
                ("package", "pkg-cross", {"uri": "pkg:pkg-cross"}),  # zero domains
            ],
            "edges": [],
        }
        conn = make_index_fixture_graph(spec)
        wiki_root = tmp_path / "wiki"
        wiki_root.mkdir(parents=True, exist_ok=True)
        _write_curated_page(
            wiki_root / "entities" / "pkg_pkg-cross.md",
            title="pkg-cross",
            summary="Cross summary",
        )
        text, *_ = _render(conn, wiki_root)
        assert "\n### Package: pkg-cross" in text
        assert "Cross summary — [[entities/pkg_pkg-cross|open page]]" in text

    def test_no_direct_entities_no_stray_headings(self, tmp_path, make_index_fixture_graph):
        # All entities placed in domains -> repo section contains only the
        # domain block; no level-3 entity headings, no `## By Kind`.
        spec = {
            "nodes": [
                ("repository", "agent-research", {"uri": "repo:agent-research"}),
                ("domain", "core", {"uri": "domain:core"}),
                ("package", "pkg-a", {"uri": "pkg:pkg-a"}),
            ],
            "edges": [
                ("package", "pkg-a", "domain", "core", "belongs_to_domain", {}),
            ],
        }
        conn = make_index_fixture_graph(spec)
        wiki_root = tmp_path / "wiki"
        wiki_root.mkdir(parents=True, exist_ok=True)
        text, *_ = _render(conn, wiki_root)
        assert "## By Kind" not in text
        assert "\n### Domain: core" in text
        assert "\n#### Package: pkg-a" in text
        assert "\n### Package:" not in text

    def test_test_suites_subheading(self, tmp_path, make_index_fixture_graph):
        spec = {
            "nodes": [
                ("repository", "agent-research", {"uri": "repo:agent-research"}),
                ("domain", "d1", {"uri": "domain:d1"}),
                ("domain", "d2", {"uri": "domain:d2"}),
                ("package", "pkg-1", {"uri": "pkg:pkg-1"}),
                ("package", "pkg-2", {"uri": "pkg:pkg-2"}),
                ("test_suite", "suite", {"uri": "test_suite:suite"}),
            ],
            "edges": [
                ("package", "pkg-1", "domain", "d1", "belongs_to_domain", {}),
                ("package", "pkg-2", "domain", "d2", "belongs_to_domain", {}),
                ("test_suite", "suite", "package", "pkg-1", "tests", {}),
                ("test_suite", "suite", "package", "pkg-2", "tests", {}),
            ],
        }
        conn = make_index_fixture_graph(spec)
        wiki_root = tmp_path / "wiki"
        wiki_root.mkdir(parents=True, exist_ok=True)
        text, *_ = _render(conn, wiki_root)
        # No flat `### Test Suites` group. The multi-domain suite nests under
        # both pkg-1 (domain d1) and pkg-2 (domain d2) per D-10.
        assert "### Test Suites" not in text
        assert "  - Test Suites" in text
        assert text.count("[[entities/tests_suite|suite]]") == 2


def test_index_title_uses_display_name_when_given(tmp_path, make_index_fixture_graph):
    """A supplied display_name overrides the wiki dir name in the index title."""
    conn = make_index_fixture_graph(
        {"nodes": [("repository", "agent-research", {"uri": "repo:agent-research"})], "edges": []}
    )
    wiki_root = tmp_path / "wiki"
    wiki_root.mkdir(parents=True, exist_ok=True)

    generate_index(conn, wiki_root, display_name="Agent Research")
    assert (wiki_root / "index.md").read_text(encoding="utf-8").splitlines()[0] == "# Index — Agent Research"


def test_index_title_falls_back_to_wiki_dir_name(tmp_path, make_index_fixture_graph):
    """With no display_name, the title falls back to the wiki directory name."""
    conn = make_index_fixture_graph(
        {"nodes": [("repository", "agent-research", {"uri": "repo:agent-research"})], "edges": []}
    )
    wiki_root = tmp_path / "wiki"
    wiki_root.mkdir(parents=True, exist_ok=True)

    generate_index(conn, wiki_root)
    assert (wiki_root / "index.md").read_text(encoding="utf-8").splitlines()[0] == "# Index — wiki"


def test_generate_index_against_fixture_graph(tmp_path, make_index_fixture_graph):
    """Happy-path integration. Builds a realistic graph, writes vault, runs
    generate_index, asserts the resulting IndexWriteResult counts and the
    section structure of the rendered file."""
    spec = {
        "nodes": [
            ("repository", "agent-research", {"uri": "repo:agent-research"}),
            ("domain", "core", {"uri": "domain:agent-research/core"}),
            ("domain", "billing", {"uri": "domain:agent-research/billing"}),
            ("package", "pkg-a", {"uri": "pkg:agent-research/pkg-a"}),
            ("package", "pkg-b", {"uri": "pkg:agent-research/pkg-b"}),
            ("package", "pkg-cross", {"uri": "pkg:agent-research/pkg-cross"}),
            ("test_suite", "suite-a", {"uri": "test_suite:agent-research/pkg-a/unit"}),
            ("dependency", "boto3", {"uri": "dependency:pypi/boto3", "ecosystem": "pypi"}),
            ("agent_plugin", "graph-wiki", {"uri": "agent_plugin:o/r/graph-wiki", "ecosystem": "claude-code"}),
        ],
        "edges": [
            ("package", "pkg-a", "domain", "core", "belongs_to_domain", {}),
            ("package", "pkg-b", "domain", "billing", "belongs_to_domain", {}),
            ("test_suite", "suite-a", "package", "pkg-a", "tests", {}),
            ("package", "pkg-a", "dependency", "boto3", "used_by", {}),
            ("package", "pkg-b", "dependency", "boto3", "used_by", {}),
        ],
    }
    conn = make_index_fixture_graph(spec)
    wiki_root = tmp_path / "wiki"
    wiki_root.mkdir(parents=True, exist_ok=True)

    # Fixture vault: one ADR + one concept
    _write_curated_page(
        wiki_root / "adrs" / "0001-test-adr.md",
        title="Test ADR",
        summary="An ADR",
    )
    _write_curated_page(
        wiki_root / "concepts" / "foo.md",
        title="Foo Concept",
        summary="A concept",
    )

    result = generate_index(conn, wiki_root)
    assert result.changed is True
    assert result.entity_count == 6  # 3 pkgs + 1 ts + 1 dep + 1 agent_plugin
    assert result.curated_count == 2
    assert result.domain_count == 2
    assert result.repo_count == 1
    # D-R8: direct_count = heading entities rendered directly under a repo
    # header. boto3 (multi-domain dependency) only nests under its consumers,
    # so pkg-cross (package) + graph-wiki (agent_plugin) remain.
    assert result.direct_count == 2

    text = (wiki_root / "index.md").read_text(encoding="utf-8")
    assert "\n## Repository: agent-research" in text
    assert "## Domains" not in text
    assert "## By Kind" not in text
    assert "\n### Domain: billing" in text
    assert "\n### Domain: core" in text
    # Single-domain entities are `####` headings inside their domain block …
    assert "\n#### Package: pkg-a" in text
    assert "\n#### Package: pkg-b" in text
    # … and zero/multi-domain entities are `###` headings under the repo.
    assert "\n### Package: pkg-cross" in text
    assert "\n### Agent Plugin: graph-wiki" in text
    assert "\n### Package: pkg-a" not in text
    # Domains render before direct entities (spec section order); billing < core.
    billing_idx = text.find("\n### Domain: billing")
    core_idx = text.find("\n### Domain: core")
    cross_idx = text.find("\n### Package: pkg-cross")
    assert -1 < billing_idx < core_idx < cross_idx
    # Flat kind groups are gone.
    assert "### Apps" not in text
    assert "### Packages" not in text
    assert "### Agent Plugins" not in text
    assert "### Dependencies" not in text
    # boto3 nests under pkg-a (core) and pkg-b (billing) as bullets (D-10).
    assert "  - Dependencies" in text
    assert "[[entities/dep_boto3|boto3]]" in text
    assert "[[entities/pkg_pkg-a|open page]]" in text
    assert "## ADRs" in text
    assert "## Concepts" in text
    assert "## Sources" not in text
    assert "## Architecture" not in text
    assert "## Work" not in text

    # No per-folder index files written (D-14)
    assert not (wiki_root / "concepts" / "index.md").exists()
    assert not (wiki_root / "adrs" / "index.md").exists()


# ============================================================================
# Plan 02 / Task 1 — Determinism + write-if-changed
# ============================================================================


def _build_realistic_graph_spec():
    """Shared fixture spec for Plan 02 determinism / acceptance tests."""
    return {
        "nodes": [
            ("repository", "agent-research", {"uri": "repo:agent-research"}),
            ("domain", "core", {"uri": "domain:agent-research/core"}),
            ("domain", "billing", {"uri": "domain:agent-research/billing"}),
            ("package", "pkg-a", {"uri": "pkg:agent-research/pkg-a"}),
            ("package", "pkg-b", {"uri": "pkg:agent-research/pkg-b"}),
            ("package", "pkg-c", {"uri": "pkg:agent-research/pkg-c"}),
            ("package", "pkg-d", {"uri": "pkg:agent-research/pkg-d"}),
            ("package", "pkg-cross", {"uri": "pkg:agent-research/pkg-cross"}),  # zero domains
            ("test_suite", "suite-a", {"uri": "test_suite:agent-research/pkg-a/unit"}),
            ("test_suite", "suite-b", {"uri": "test_suite:agent-research/pkg-b/unit"}),
            ("test_suite", "suite-multi", {"uri": "test_suite:agent-research/cross/integration"}),
            ("dependency", "boto3", {"ecosystem": "pypi", "uri": "dependency:pypi/boto3"}),
            ("dependency", "langchain-aws", {"ecosystem": "pypi", "uri": "dependency:pypi/langchain-aws"}),
            ("dependency", "pytest", {"ecosystem": "pypi", "uri": "dependency:pypi/pytest"}),
            ("dependency", "multi-consumer-dep", {"ecosystem": "pypi", "uri": "dependency:pypi/multi-consumer-dep"}),
            ("agent_plugin", "graph-wiki", {"ecosystem": "claude-code", "uri": "agent_plugin:o/r/graph-wiki"}),
        ],
        "edges": [
            ("package", "pkg-a", "domain", "core", "belongs_to_domain", {}),
            ("package", "pkg-b", "domain", "core", "belongs_to_domain", {}),
            ("package", "pkg-c", "domain", "billing", "belongs_to_domain", {}),
            ("package", "pkg-d", "domain", "billing", "belongs_to_domain", {}),
            ("test_suite", "suite-a", "package", "pkg-a", "tests", {}),
            ("test_suite", "suite-b", "package", "pkg-b", "tests", {}),
            ("test_suite", "suite-multi", "package", "pkg-a", "tests", {}),
            ("test_suite", "suite-multi", "package", "pkg-c", "tests", {}),
            ("package", "pkg-a", "dependency", "boto3", "used_by", {}),
            ("package", "pkg-c", "dependency", "langchain-aws", "used_by", {}),
            ("package", "pkg-cross", "dependency", "pytest", "used_by", {}),
            ("package", "pkg-a", "dependency", "multi-consumer-dep", "used_by", {}),
            ("package", "pkg-c", "dependency", "multi-consumer-dep", "used_by", {}),
        ],
    }


def test_determinism_across_permutations(tmp_path, make_index_fixture_graph):
    """INDEX-04 — two builds with permuted insertion order produce byte-identical text."""
    spec = _build_realistic_graph_spec()
    rng = random.Random(42)

    spec_a = {"nodes": list(spec["nodes"]), "edges": list(spec["edges"])}
    spec_b = {"nodes": list(spec["nodes"]), "edges": list(spec["edges"])}
    rng.shuffle(spec_b["nodes"])
    rng.shuffle(spec_b["edges"])

    conn_a = make_index_fixture_graph(spec_a)
    conn_b = make_index_fixture_graph(spec_b)

    wiki_root = tmp_path / "wiki"
    wiki_root.mkdir(parents=True, exist_ok=True)

    text_a, *_ = _render(conn_a, wiki_root)
    text_b, *_ = _render(conn_b, wiki_root)

    assert text_a == text_b, "Non-determinism detected (Pitfall 5 regression)."


def test_write_if_changed(tmp_path, make_index_fixture_graph):
    """INDEX-04 — second consecutive call is a no-op (D-16)."""
    spec = _build_realistic_graph_spec()
    conn = make_index_fixture_graph(spec)
    wiki_root = tmp_path / "wiki"
    wiki_root.mkdir(parents=True, exist_ok=True)

    r1 = generate_index(conn, wiki_root)
    assert r1.changed is True
    assert r1.bytes_written > 0
    index_path = wiki_root / "index.md"
    assert index_path.exists()
    mtime_1 = index_path.stat().st_mtime

    time.sleep(0.05)

    r2 = generate_index(conn, wiki_root)
    assert r2.changed is False, f"Expected unchanged, got {r2}"
    assert r2.bytes_written == 0
    assert r2.entity_count == r1.entity_count
    assert r2.curated_count == r1.curated_count
    assert index_path.stat().st_mtime == mtime_1, "mtime should be unchanged"


def test_write_if_changed_writes_when_graph_mutates(tmp_path, make_index_fixture_graph):
    spec = _build_realistic_graph_spec()
    conn = make_index_fixture_graph(spec)
    wiki_root = tmp_path / "wiki"
    wiki_root.mkdir(parents=True, exist_ok=True)

    r1 = generate_index(conn, wiki_root)
    assert r1.changed is True

    spec["nodes"].append(("package", "pkg-new", {"uri": "pkg:agent-research/pkg-new"}))
    spec["edges"].append(("package", "pkg-new", "domain", "core", "belongs_to_domain", {}))
    conn2 = make_index_fixture_graph(spec)

    r2 = generate_index(conn2, wiki_root)
    assert r2.changed is True
    assert r2.bytes_written > 0
    assert r2.entity_count == r1.entity_count + 1


def test_atomic_write_no_tmp_remains(tmp_path, make_index_fixture_graph):
    spec = _build_realistic_graph_spec()
    conn = make_index_fixture_graph(spec)
    wiki_root = tmp_path / "wiki"
    wiki_root.mkdir(parents=True, exist_ok=True)

    generate_index(conn, wiki_root)
    tmp_files = list(wiki_root.glob("*.tmp"))
    assert tmp_files == [], f"Leftover .tmp files: {tmp_files}"


# ============================================================================
# Plan 02 / Task 2 — Placement + section structure acceptance
# ============================================================================


def test_cross_cutting_renders_direct_under_repo(tmp_path, make_index_fixture_graph):
    """INDEX-03 — cross-cutting packages render directly under the repo header."""
    spec = _build_realistic_graph_spec()
    conn = make_index_fixture_graph(spec)
    wiki_root = tmp_path / "wiki"
    wiki_root.mkdir(parents=True, exist_ok=True)

    text, *_ = _render(conn, wiki_root)
    cross_link = "[[entities/pkg_pkg-cross|open page]]"
    assert text.count(cross_link) == 1
    assert "\n### Package: pkg-cross" in text
    core_idx = text.find("\n### Domain: core")
    billing_idx = text.find("\n### Domain: billing")
    cross_idx = text.find("\n### Package: pkg-cross")
    assert core_idx > -1 and billing_idx > -1 and cross_idx > -1
    # Domain blocks render before direct entities inside the repo section.
    assert core_idx < cross_idx
    assert billing_idx < cross_idx


def test_multi_domain_entity_nests_only_under_consumers(tmp_path, make_index_fixture_graph):
    """INDEX-04/D-01/D-10 — a multi-domain test_suite is placed direct under the repo but
    nests under each package it tests (in those packages' domain sections),
    appearing once per tested package (duplication is expected, D-10)."""
    spec = _build_realistic_graph_spec()
    conn = make_index_fixture_graph(spec)
    wiki_root = tmp_path / "wiki"
    wiki_root.mkdir(parents=True, exist_ok=True)

    text, *_ = _render(conn, wiki_root)
    # Phase 53 D-05: short_filename for `test_suite:agent-research/cross/integration`
    # with no `suite_kind` attr falls back to `tests_<pkg>` where `<pkg>` is the
    # second-to-last URI segment (`cross`).
    multi_substr = "tests_cross"
    count = text.count(multi_substr)
    # suite-multi tests pkg-a (core) and pkg-c (billing) → nests under each (D-10).
    assert count == 2, f"suite-multi should nest under both packages; found {count}"
    # Phase 57 D-08: no flat `### Test Suites` group — it nests under packages.
    assert "### Test Suites" not in text
    assert "  - Test Suites" in text


def test_sub_domain_nesting(tmp_path, make_index_fixture_graph):
    """D-07 — sub-domains nest under parent via domain_contains_domain."""
    spec = {
        "nodes": [
            ("repository", "agent-research", {"uri": "repo:agent-research"}),
            ("domain", "core", {"uri": "domain:agent-research/core"}),
            ("domain", "billing", {"uri": "domain:agent-research/billing"}),
            ("package", "pkg-core", {"uri": "pkg:agent-research/pkg-core"}),
            ("package", "pkg-billing", {"uri": "pkg:agent-research/pkg-billing"}),
        ],
        "edges": [
            ("package", "pkg-core", "domain", "core", "belongs_to_domain", {}),
            ("package", "pkg-billing", "domain", "billing", "belongs_to_domain", {}),
            ("domain", "core", "domain", "billing", "domain_contains_domain", {}),
        ],
    }
    conn = make_index_fixture_graph(spec)
    wiki_root = tmp_path / "wiki"
    wiki_root.mkdir(parents=True, exist_ok=True)

    text, *_ = _render(conn, wiki_root)
    assert "\n### Domain: core" in text
    assert "\n#### Sub-Domain: billing" in text
    assert "\n### Domain: billing" not in text
    assert "\n#### Package: pkg-core" in text
    assert "\n##### Package: pkg-billing" in text
    core_idx = text.find("\n### Domain: core")
    sub_idx = text.find("\n#### Sub-Domain: billing")
    assert core_idx < sub_idx


def test_empty_sections_omitted(tmp_path, make_index_fixture_graph):
    """D-08 — empty sub-bullets + empty domains omitted."""
    spec = {
        "nodes": [
            ("repository", "agent-research", {"uri": "repo:agent-research"}),
            ("domain", "active-domain", {"uri": "domain:agent-research/active-domain"}),
            ("domain", "empty-domain", {"uri": "domain:agent-research/empty-domain"}),
            ("package", "pkg-solo", {"uri": "pkg:agent-research/pkg-solo"}),
        ],
        "edges": [
            ("package", "pkg-solo", "domain", "active-domain", "belongs_to_domain", {}),
        ],
    }
    conn = make_index_fixture_graph(spec)
    wiki_root = tmp_path / "wiki"
    wiki_root.mkdir(parents=True, exist_ok=True)

    text, *_ = _render(conn, wiki_root)
    assert "\n### Domain: active-domain" in text
    assert "\n#### Package: pkg-solo" in text
    assert "[[entities/pkg_pkg-solo|open page]]" in text
    # pkg-solo has no suites/deps -> no nested sub-lists anywhere (D-08).
    assert "Test Suites" not in text
    assert "Dependencies" not in text
    assert "Domain: empty-domain" not in text


def test_agent_plugin_always_direct_under_repo(tmp_path, make_index_fixture_graph):
    """D-04 — agent_plugins always direct under the repo header regardless of other state."""
    spec = {
        "nodes": [
            ("repository", "agent-research", {"uri": "repo:agent-research"}),
            ("domain", "core", {"uri": "domain:agent-research/core"}),
            ("package", "pkg-a", {"uri": "pkg:agent-research/pkg-a"}),
            ("agent_plugin", "graph-wiki", {"ecosystem": "claude-code", "uri": "agent_plugin:o/r/graph-wiki"}),
        ],
        "edges": [
            ("package", "pkg-a", "domain", "core", "belongs_to_domain", {}),
        ],
    }
    conn = make_index_fixture_graph(spec)
    wiki_root = tmp_path / "wiki"
    wiki_root.mkdir(parents=True, exist_ok=True)

    text, *_ = _render(conn, wiki_root)
    agent_plugin_slug = "agent-plugin_graph-wiki"
    assert text.count(agent_plugin_slug) == 1
    assert "\n### Agent Plugin: graph-wiki" in text
    core_idx = text.find("\n### Domain: core")
    plug_idx = text.find("\n### Agent Plugin: graph-wiki")
    assert -1 < core_idx < plug_idx


def test_multi_repo_renders_two_alphabetical_sections(tmp_path, make_index_fixture_graph):
    """D-R1 — two repository nodes render two self-contained, alphabetical
    `## Repository:` sections with entities split by URI (D-R7), domains
    nested in their own repo's section (D-R2)."""
    spec = {
        "nodes": [
            ("repository", "repo-alpha", {"uri": "repo:local/repo-alpha"}),
            ("repository", "repo-beta", {"uri": "repo:local/repo-beta"}),
            ("domain", "core", {"uri": "domain:local/repo-beta/core"}),
            ("package", "pkg-one", {"uri": "pkg:local/repo-alpha/pkg-one"}),
            ("package", "pkg-two", {"uri": "pkg:local/repo-beta/pkg-two"}),
            ("package", "pkg-three", {"uri": "pkg:local/repo-beta/pkg-three"}),
        ],
        "edges": [
            ("package", "pkg-two", "domain", "core", "belongs_to_domain", {}),
        ],
    }
    conn = make_index_fixture_graph(spec)
    wiki_root = tmp_path / "wiki"
    wiki_root.mkdir(parents=True, exist_ok=True)
    text, *_ = _render(conn, wiki_root)
    a_idx = text.find("\n## Repository: repo-alpha")
    b_idx = text.find("\n## Repository: repo-beta")
    assert -1 < a_idx < b_idx
    one_idx = text.find("\n### Package: pkg-one")
    dom_idx = text.find("\n### Domain: core")
    two_idx = text.find("\n#### Package: pkg-two")
    three_idx = text.find("\n### Package: pkg-three")
    # pkg-one inside alpha; beta holds its domain (with pkg-two) then pkg-three.
    assert a_idx < one_idx < b_idx
    assert b_idx < dom_idx < two_idx < three_idx


def test_empty_repo_section_omitted(tmp_path, make_index_fixture_graph):
    """D-08 — a repository node with no placed entities renders no section."""
    spec = {
        "nodes": [
            ("repository", "repo-alpha", {"uri": "repo:local/repo-alpha"}),
            ("repository", "repo-empty", {"uri": "repo:local/repo-empty"}),
            ("package", "pkg-one", {"uri": "pkg:local/repo-alpha/pkg-one"}),
        ],
        "edges": [],
    }
    conn = make_index_fixture_graph(spec)
    wiki_root = tmp_path / "wiki"
    wiki_root.mkdir(parents=True, exist_ok=True)
    text, *_ = _render(conn, wiki_root)
    assert "\n## Repository: repo-alpha" in text
    assert "Repository: repo-empty" not in text


def test_zero_repos_curated_lanes_only(tmp_path, make_index_fixture_graph):
    """Edge case — zero repository nodes (empty graph): no entity sections,
    curated lanes still render."""
    wiki_root = tmp_path / "wiki"
    _write_curated_page(wiki_root / "concepts" / "foo.md", title="Foo Concept")
    conn = make_index_fixture_graph({"nodes": [], "edges": []})
    result = generate_index(conn, wiki_root)
    text = (wiki_root / "index.md").read_text(encoding="utf-8")
    assert "## Repository:" not in text
    assert "## Concepts" in text
    assert result.repo_count == 0
    assert result.direct_count == 0
    assert result.domain_count == 0


# ============================================================================
# Plan 02 / Task 3 — Curated consolidation + GENERATED_FILES + snapshot
# ============================================================================


def test_curated_lanes_consolidated(tmp_path, make_index_fixture_graph):
    """INDEX-05 — curated lanes are sections IN wiki/index.md."""
    wiki_root = tmp_path / "wiki"
    _write_curated_page(wiki_root / "adrs" / "0001-alpha-adr.md", title="Alpha ADR", summary="First ADR")
    _write_curated_page(wiki_root / "adrs" / "0002-mu-adr.md", title="Mu ADR", summary="Middle ADR")
    _write_curated_page(wiki_root / "adrs" / "0003-zeta-adr.md", title="Zeta ADR", summary="Last ADR")
    _write_curated_page(wiki_root / "concepts" / "foo.md", title="Foo Concept")
    _write_curated_page(wiki_root / "concepts" / "bar.md", title="Bar Concept")

    conn = make_index_fixture_graph({"nodes": [], "edges": []})
    result = generate_index(conn, wiki_root)
    text = (wiki_root / "index.md").read_text(encoding="utf-8")

    assert "## ADRs" in text
    assert "## Concepts" in text
    assert "## Architecture" not in text
    assert "## Sources" not in text
    assert "## Work" not in text

    adr_start = text.find("## ADRs")
    next_h2 = text.find("\n## ", adr_start + 1)
    adr_section = text[adr_start : next_h2 if next_h2 > -1 else len(text)]
    alpha_idx = adr_section.find("Alpha ADR")
    mu_idx = adr_section.find("Mu ADR")
    zeta_idx = adr_section.find("Zeta ADR")
    assert alpha_idx > -1 and mu_idx > -1 and zeta_idx > -1
    assert alpha_idx < mu_idx < zeta_idx

    concept_start = text.find("## Concepts")
    concept_section = text[concept_start:]
    bar_idx = concept_section.find("Bar Concept")
    foo_idx = concept_section.find("Foo Concept")
    assert bar_idx < foo_idx

    assert result.curated_count == 5
    assert result.entity_count == 0


def test_generated_files_excluded(tmp_path, make_index_fixture_graph):
    """Research §Pitfall 2 — GENERATED_FILES excluded from curated scan."""
    wiki_root = tmp_path / "wiki"
    _write_curated_page(wiki_root / "index.md", title="Existing Index")
    _write_curated_page(wiki_root / "log.md", title="Existing Log")
    _write_curated_page(wiki_root / "concepts" / "index.md", title="Concepts Sub-Index")
    _write_curated_page(wiki_root / "concepts" / "real-page.md", title="Real Page")

    conn = make_index_fixture_graph({"nodes": [], "edges": []})
    generate_index(conn, wiki_root)
    text = (wiki_root / "index.md").read_text(encoding="utf-8")

    assert "Real Page" in text
    assert "Existing Index" not in text
    assert "Existing Log" not in text
    assert "Concepts Sub-Index" not in text


# ============================================================================
# Phase 57 — IDX-01 (app section), IDX-05 (internal deps), IDX-03 (summaries)
# ============================================================================


def test_app_zero_domain_renders_direct_apps_first(tmp_path, make_index_fixture_graph):
    """IDX-01/D-R6 — a zero-domain app renders directly under the repo header,
    before packages (apps first)."""
    spec = {
        "nodes": [
            ("repository", "agent-research", {"uri": "repo:agent-research"}),
            ("app", "myapp", {"uri": "app:agent-research/myapp", "app_kind": "cli", "app_signals": []}),
            ("package", "pkg-cross", {"uri": "pkg:agent-research/pkg-cross"}),
        ],
        "edges": [],
    }
    conn = make_index_fixture_graph(spec)
    wiki_root = tmp_path / "wiki"
    wiki_root.mkdir(parents=True, exist_ok=True)
    text, *_ = _render(conn, wiki_root)
    app_idx = text.find("\n### App: myapp")
    pkg_idx = text.find("\n### Package: pkg-cross")
    assert app_idx > -1
    assert pkg_idx > -1
    assert app_idx < pkg_idx  # apps listed first (D-R6)
    assert "[[entities/app_myapp|open page]]" in text


def test_app_single_domain_renders_under_its_domain(tmp_path, make_index_fixture_graph):
    """IDX-01/D-04 — a single-domain app renders under its `## Domain: X`
    section (same routing as packages), not in By-Kind."""
    spec = {
        "nodes": [
            ("repository", "agent-research", {"uri": "repo:agent-research"}),
            ("domain", "core", {"uri": "domain:agent-research/core"}),
            ("app", "myapp", {"uri": "app:agent-research/myapp", "app_kind": "cli"}),
        ],
        "edges": [
            ("app", "myapp", "domain", "core", "belongs_to_domain", {}),
        ],
    }
    conn = make_index_fixture_graph(spec)
    wiki_root = tmp_path / "wiki"
    wiki_root.mkdir(parents=True, exist_ok=True)
    text, *_ = _render(conn, wiki_root)
    assert "\n### Domain: core" in text
    assert "\n#### App: myapp" in text
    assert "[[entities/app_myapp|open page]]" in text
    assert "\n### App:" not in text  # not a direct entity


def test_internal_dependencies_subsection_distinct_from_dependencies(tmp_path, make_index_fixture_graph):
    """IDX-05/D-09 — a `depends_on_package` edge renders a separate
    `Internal dependencies` sub-list linking to the internal PACKAGE entity
    page, kept distinct from the external `Dependencies` sub-list."""
    spec = {
        "nodes": [
            ("repository", "agent-research", {"uri": "repo:agent-research"}),
            ("domain", "core", {"uri": "domain:agent-research/core"}),
            ("package", "consumer", {"uri": "pkg:agent-research/consumer"}),
            ("package", "target", {"uri": "pkg:agent-research/target"}),
            ("dependency", "boto3", {"uri": "dependency:pypi/boto3", "ecosystem": "pypi"}),
        ],
        "edges": [
            ("package", "consumer", "domain", "core", "belongs_to_domain", {}),
            ("package", "target", "domain", "core", "belongs_to_domain", {}),
            # external dep: consumer uses boto3
            ("package", "consumer", "dependency", "boto3", "used_by", {}),
            # internal dep: consumer depends on the target workspace package
            ("package", "consumer", "package", "target", "depends_on_package", {}),
        ],
    }
    conn = make_index_fixture_graph(spec)
    wiki_root = tmp_path / "wiki"
    wiki_root.mkdir(parents=True, exist_ok=True)
    text, *_ = _render(conn, wiki_root)

    # Two SEPARATE sub-headings under consumer (D-09 — never merged).
    assert "  - Dependencies" in text
    assert "  - Internal dependencies" in text
    # External dep → dependency entity page; internal dep → PACKAGE entity page.
    assert "[[entities/dep_boto3|boto3]]" in text
    assert "[[entities/pkg_target|target]]" in text
    # The internal-deps heading is distinct from (and after) the external one.
    dep_idx = text.find("  - Dependencies")
    internal_idx = text.find("  - Internal dependencies")
    assert dep_idx > -1 and internal_idx > -1
    assert dep_idx < internal_idx


def test_inline_summary_from_entity_page_frontmatter(tmp_path, make_index_fixture_graph):
    """IDX-03/D-06/D-07 — an entity entry shows ` — {summary}` read from the
    entity page's own `summary:` frontmatter; no suffix when absent."""
    spec = {
        "nodes": [
            ("repository", "agent-research", {"uri": "repo:agent-research"}),
            ("domain", "core", {"uri": "domain:agent-research/core"}),
            ("package", "pkg-a", {"uri": "pkg:agent-research/pkg-a"}),
            ("package", "pkg-b", {"uri": "pkg:agent-research/pkg-b"}),
        ],
        "edges": [
            ("package", "pkg-a", "domain", "core", "belongs_to_domain", {}),
            ("package", "pkg-b", "domain", "core", "belongs_to_domain", {}),
        ],
    }
    conn = make_index_fixture_graph(spec)
    wiki_root = tmp_path / "wiki"
    wiki_root.mkdir(parents=True, exist_ok=True)
    # pkg-a has an entity page with a summary; pkg-b has none.
    _write_curated_page(
        wiki_root / "entities" / "pkg_pkg-a.md",
        title="pkg-a",
        summary="Some summary",
    )
    text, *_ = _render(conn, wiki_root)
    # pkg-a renders its summary before the open-page link (D-R4 body shape).
    assert "\n#### Package: pkg-a" in text
    assert "Some summary — [[entities/pkg_pkg-a|open page]]" in text
    # pkg-b (no entity page) renders the bare link with NO summary prefix.
    assert "\n#### Package: pkg-b" in text
    assert "[[entities/pkg_pkg-b|open page]]\n" in text
    assert "— [[entities/pkg_pkg-b|open page]]" not in text


# --- Fan-out regression guard (SC#3 / D-07/D-08) ---


def _make_fanout_fixture() -> sqlite3.Connection:
    """Build a fan-out test graph directly (bypasses upsert path collapsing).

    Two suites share the legacy name 'tests' but have DISTINCT paths and URIs,
    mirroring the pre-Plan-02 state in production. We insert nodes directly so
    both suite rows exist in the DB (upsert_records collapses same-(kind,name,path)
    tuples, which would silently merge them).

    Each suite is connected via a 'tests' edge to only its own package.
    """
    from graph_io.schema import apply_schema

    conn = sqlite3.connect(":memory:")
    apply_schema(conn)

    # Insert nodes directly to allow two 'tests'-named suite rows
    conn.execute(
        "INSERT INTO nodes(kind, name, path, line, attrs_json, uri) VALUES (?,?,?,?,?,?)",
        ("domain", "d1", "", None, "{}", "domain:d1"),
    )
    conn.execute(
        "INSERT INTO nodes(kind, name, path, line, attrs_json, uri) VALUES (?,?,?,?,?,?)",
        ("package", "pkg-alpha", "", None, '{"uri":"pkg:pkg-alpha"}', "pkg:pkg-alpha"),
    )
    conn.execute(
        "INSERT INTO nodes(kind, name, path, line, attrs_json, uri) VALUES (?,?,?,?,?,?)",
        ("package", "pkg-beta", "", None, '{"uri":"pkg:pkg-beta"}', "pkg:pkg-beta"),
    )
    # Both suites named 'tests' but with different paths and URIs
    conn.execute(
        "INSERT INTO nodes(kind, name, path, line, attrs_json, uri) VALUES (?,?,?,?,?,?)",
        (
            "test_suite",
            "tests",
            "packages/alpha/tests",
            None,
            "{}",
            "test_suite:org/repo/packages/alpha/tests",
        ),
    )
    conn.execute(
        "INSERT INTO nodes(kind, name, path, line, attrs_json, uri) VALUES (?,?,?,?,?,?)",
        (
            "test_suite",
            "tests",
            "packages/beta/tests",
            None,
            "{}",
            "test_suite:org/repo/packages/beta/tests",
        ),
    )
    conn.commit()

    # Fetch IDs for edge wiring
    def nid(kind, name, path=""):
        return conn.execute(
            "SELECT id FROM nodes WHERE kind=? AND name=? AND path=?",
            (kind, name, path),
        ).fetchone()[0]

    d1 = nid("domain", "d1")
    pkg_a = nid("package", "pkg-alpha")
    pkg_b = nid("package", "pkg-beta")
    ts_a = nid("test_suite", "tests", "packages/alpha/tests")
    ts_b = nid("test_suite", "tests", "packages/beta/tests")

    conn.executemany(
        "INSERT INTO edges(src, dst, kind, attrs_json) VALUES (?,?,?,?)",
        [
            (pkg_a, d1, "belongs_to_domain", "{}"),
            (pkg_b, d1, "belongs_to_domain", "{}"),
            (ts_a, pkg_a, "tests", "{}"),  # alpha-suite tests only alpha-pkg
            (ts_b, pkg_b, "tests", "{}"),  # beta-suite tests only beta-pkg
        ],
    )
    conn.commit()
    return GraphReader(conn)


def test_consumer_pkgs_fanout_regression_guard():
    """Regression guard: two suites with the SAME name but DISTINCT URIs must
    each resolve to only their own consumer package via _consumer_pkgs.

    Before the fix, _consumer_pkgs joined on ts.name=? — both suites shared
    name='tests', so each returned BOTH packages (fan-out). After the fix,
    _consumer_pkgs joins on ts.uri=?, giving exactly one consumer per suite.

    The guard also covers _consumer_pkgs_in_domain with a domain variant, and
    confirms that a URI matching no suite returns empty (no name-fallback).
    """
    conn = _make_fanout_fixture()

    uri_alpha = "test_suite:org/repo/packages/alpha/tests"
    uri_beta = "test_suite:org/repo/packages/beta/tests"

    # _consumer_pkgs: each suite resolves to exactly its own consumer package
    pkgs_for_alpha = _consumer_pkgs(conn, kind="test_suite", entity_uri=uri_alpha)
    pkgs_for_beta = _consumer_pkgs(conn, kind="test_suite", entity_uri=uri_beta)
    assert pkgs_for_alpha == ("pkg-alpha",), f"expected ('pkg-alpha',), got {pkgs_for_alpha!r} — fan-out detected"
    assert pkgs_for_beta == ("pkg-beta",), f"expected ('pkg-beta',), got {pkgs_for_beta!r} — fan-out detected"

    # _consumer_pkgs_in_domain: same correctness within a domain
    pkgs_alpha_d1 = _consumer_pkgs_in_domain(conn, kind="test_suite", entity_uri=uri_alpha, domain_name="d1")
    pkgs_beta_d1 = _consumer_pkgs_in_domain(conn, kind="test_suite", entity_uri=uri_beta, domain_name="d1")
    assert pkgs_alpha_d1 == ("pkg-alpha",), f"expected ('pkg-alpha',), got {pkgs_alpha_d1!r} — domain fan-out detected"
    assert pkgs_beta_d1 == ("pkg-beta",), f"expected ('pkg-beta',), got {pkgs_beta_d1!r} — domain fan-out detected"

    # A URI matching no suite returns empty (no name-fallback)
    no_match = _consumer_pkgs(conn, kind="test_suite", entity_uri="test_suite:org/repo/no-such-suite")
    assert no_match == (), f"expected () for unmatched URI, got {no_match!r}"


# ============================================================================
# Guidance section
# ============================================================================


def _write_guidance_fixture_page(wiki_root: Path, topic: str, name: str, title: str):
    """Guidance content page under wiki/guidance/<topic>/."""
    _write_curated_page(wiki_root / "guidance" / topic / f"{name}.md", title=title)


class TestGuidanceSection:
    def test_scan_returns_sorted_topic_counts(self, tmp_path):
        wiki_root = tmp_path / "wiki"
        _write_guidance_fixture_page(wiki_root, "expo", "a", "A")
        _write_guidance_fixture_page(wiki_root, "deep-agents", "b", "B")
        _write_guidance_fixture_page(wiki_root, "deep-agents", "c", "C")
        assert _scan_guidance_topics(wiki_root) == [("deep-agents", 2), ("expo", 1)]

    def test_scan_missing_dir_and_index_only_topic(self, tmp_path):
        wiki_root = tmp_path / "wiki"
        wiki_root.mkdir(parents=True)
        assert _scan_guidance_topics(wiki_root) == []
        _write_curated_page(wiki_root / "guidance" / "empty" / "index.md", title="Idx")
        assert _scan_guidance_topics(wiki_root) == []

    def test_render_section_shape(self):
        lines = _render_guidance_section([("deep-agents", 9), ("expo", 1)])
        assert lines[0] == "## Guidance"
        assert "- [[guidance/index|All guidance topics]]" in lines
        assert "- [[guidance/deep-agents/index|Deep Agents]] — 9 pages" in lines
        assert "- [[guidance/expo/index|Expo]] — 1 page" in lines

    def test_render_section_empty_returns_nothing(self):
        assert _render_guidance_section([]) == []

    def test_generate_index_renders_guidance_after_sources_before_work(self, tmp_path, make_index_fixture_graph):
        conn = make_index_fixture_graph(
            {"nodes": [("repository", "agent-research", {"uri": "repo:agent-research"})], "edges": []}
        )
        wiki_root = tmp_path / "wiki"
        wiki_root.mkdir(parents=True)
        _write_curated_page(wiki_root / "sources" / "spec.md", title="A Spec")
        _write_curated_page(wiki_root / "work" / "2026-06-09-item.md", title="An Item")
        _write_guidance_fixture_page(wiki_root, "expo", "a", "A Guidance Page")

        generate_index(conn, wiki_root)
        text = (wiki_root / "index.md").read_text(encoding="utf-8")
        assert "## Guidance" in text
        assert "- [[guidance/index|All guidance topics]]" in text
        assert "- [[guidance/expo/index|Expo]] — 1 page" in text
        assert text.index("## Sources") < text.index("## Guidance") < text.index("## Work")

    def test_generate_index_omits_guidance_when_none(self, tmp_path, make_index_fixture_graph):
        conn = make_index_fixture_graph(
            {"nodes": [("repository", "agent-research", {"uri": "repo:agent-research"})], "edges": []}
        )
        wiki_root = tmp_path / "wiki"
        wiki_root.mkdir(parents=True)
        generate_index(conn, wiki_root)
        text = (wiki_root / "index.md").read_text(encoding="utf-8")
        assert "## Guidance" not in text

    def test_guidance_pages_not_in_curated_count(self, tmp_path, make_index_fixture_graph):
        conn = make_index_fixture_graph(
            {"nodes": [("repository", "agent-research", {"uri": "repo:agent-research"})], "edges": []}
        )
        wiki_root = tmp_path / "wiki"
        wiki_root.mkdir(parents=True)
        _write_curated_page(wiki_root / "concepts" / "foo.md", title="Foo")
        _write_guidance_fixture_page(wiki_root, "expo", "a", "A")
        _write_guidance_fixture_page(wiki_root, "expo", "b", "B")

        result = generate_index(conn, wiki_root)
        assert result.curated_count == 1  # the concept only; guidance is navigational

    def test_guidance_index_in_generated_files(self):
        from wiki_io.index_generator import GENERATED_FILES

        assert "guidance/index.md" in GENERATED_FILES


# ============================================================================
# _render_concepts_section — kind grouping
# ============================================================================


class TestRenderConceptsSection:
    @staticmethod
    def _entry(title, kind=""):
        return {"path": f"concepts/{title.lower()}.md", "title": title, "summary": "", "kind": kind}

    def test_mixed_kinds_grouped_in_fixed_order(self):
        lines = _render_concepts_section(
            [self._entry("Auth"), self._entry("Overview", "architecture"), self._entry("Retry", "pattern")]
        )
        text = "\n".join(lines)
        a, p, c = text.index("### Architecture"), text.index("### Patterns"), text.index("### Concepts")
        assert text.startswith("## Concepts")
        assert a < p < c

    def test_unknown_kind_falls_back_to_concepts_group(self):
        lines = _render_concepts_section([self._entry("Weird", "bogus"), self._entry("Overview", "architecture")])
        text = "\n".join(lines)
        assert "### Concepts" in text
        assert text.index("Weird") > text.index("### Concepts")

    def test_all_default_renders_flat(self):
        lines = _render_concepts_section([self._entry("Auth"), self._entry("Cache")])
        text = "\n".join(lines)
        assert "### " not in text
        assert text.startswith("## Concepts")

    def test_empty_returns_nothing(self):
        assert _render_concepts_section([]) == []
