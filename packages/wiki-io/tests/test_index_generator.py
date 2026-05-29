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

from wiki_io.index_generator import (
    BY_KIND_ORDER,
    CURATED_LANES,
    GENERATED_FILES,
    KIND_LABELS,
    IndexWriteResult,
    PlacedEntity,
    _compute_qualifying_domains,
    _consumer_pkgs,
    _consumer_pkgs_in_domain,
    _entry_link,
    _place_entities,
    _render,
    _scan_curated_lane,
    _scan_work,
    generate_index,
)


def _place(conn):
    """Call _place_entities with a no-pages wiki_root + empty collision_set.

    Phase 57: _place_entities now takes (conn, wiki_root, collision_set) and
    returns (domain_buckets, by_kind, name_to_entity). Placement tests below
    only care about buckets/by_kind; with no entity pages on disk all summaries
    degrade to "". Returns the (buckets, by_kind) pair the old tests expect.
    """
    buckets, by_kind, _name_to_entity = _place_entities(
        conn, Path("/nonexistent-wiki-root"), frozenset()
    )
    return buckets, by_kind


# ============================================================================
# Plan 01 / Task 1 — IndexWriteResult + module constants
# ============================================================================


class TestIndexWriteResult:
    def test_shape(self):
        r = IndexWriteResult(
            path=Path("/tmp/wiki/index.md"),
            bytes_written=1234,
            changed=True,
            entity_count=10,
            curated_count=5,
            domain_count=2,
            by_kind_count=3,
        )
        assert r.path == Path("/tmp/wiki/index.md")
        assert r.bytes_written == 1234
        assert r.changed is True
        assert r.entity_count == 10
        assert r.curated_count == 5
        assert r.domain_count == 2
        assert r.by_kind_count == 3

    def test_frozen(self):
        r = IndexWriteResult(
            path=Path("/x"),
            bytes_written=0,
            changed=False,
            entity_count=0,
            curated_count=0,
            domain_count=0,
            by_kind_count=0,
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.changed = True  # type: ignore[misc]

    def test_module_constants(self):
        # Phase 57 D-03/D-08: flat By-Kind groups are app/package/plugin only.
        assert BY_KIND_ORDER == ("app", "package", "plugin")
        assert len(CURATED_LANES) == 4
        assert CURATED_LANES[0] == ("architecture", "architecture", "Architecture")
        assert CURATED_LANES[1] == ("adrs", "adrs", "ADRs")
        assert CURATED_LANES[2] == ("concepts", "concepts", "Concepts")
        assert CURATED_LANES[3] == ("sources", "sources", "Sources")
        assert KIND_LABELS["app"] == "Apps"
        assert KIND_LABELS["package"] == "Packages"
        assert KIND_LABELS["plugin"] == "Plugins"
        # test_suite/dependency are no longer flat groups, but their labels
        # remain as the nested sub-heading strings.
        assert "index.md" in GENERATED_FILES
        assert "concepts/index.md" in GENERATED_FILES

    def test_entry_link_wiki_vs_work(self):
        assert _entry_link("work/foo.md", "Foo") == "[[work/foo|Foo]]"
        assert _entry_link("concepts/foo.md", "Foo") == "[[wiki/concepts/foo|Foo]]"


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
        assert _compute_qualifying_domains(
            conn, kind="package", name="pkg-a"
        ) == {"core", "billing"}

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
        assert _compute_qualifying_domains(
            conn, kind="test_suite", name="suite-a", uri="test_suite:suite-a"
        ) == {"core"}

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
        assert _compute_qualifying_domains(
            conn, kind="test_suite", name="suite", uri="test_suite:suite"
        ) == {"d1", "d2"}

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
        assert _compute_qualifying_domains(
            conn, kind="dependency", name="boto3"
        ) == {"core"}

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
        assert _compute_qualifying_domains(
            conn, kind="dependency", name="boto3"
        ) == {"core"}

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
        assert _compute_qualifying_domains(
            conn, kind="dependency", name="boto3"
        ) == {"d1", "d2"}

    def test_plugin_always_empty(self, make_index_fixture_graph):
        spec = {
            "nodes": [
                ("plugin", "graph-wiki", {"uri": "plugin:graph-wiki", "ecosystem": "claude-code"}),
            ],
            "edges": [],
        }
        conn = make_index_fixture_graph(spec)
        assert _compute_qualifying_domains(conn, kind="plugin", name="graph-wiki") == set()

    def test_invalid_kind_raises(self, make_index_fixture_graph):
        conn = make_index_fixture_graph({"nodes": [], "edges": []})
        with pytest.raises(ValueError):
            _compute_qualifying_domains(conn, kind="file", name="x")


class TestPlacement:
    def test_single_domain_goes_to_section(self, make_index_fixture_graph):
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
        buckets, by_kind = _place(conn)
        assert "core" in buckets
        assert len(buckets["core"]) == 1
        assert buckets["core"][0].kind == "package"
        assert buckets["core"][0].name == "pkg-a"
        assert by_kind == []

    def test_zero_domain_goes_to_by_kind(self, make_index_fixture_graph):
        spec = {
            "nodes": [
                ("package", "pkg-cross", {"uri": "pkg:pkg-cross"}),
            ],
            "edges": [],
        }
        conn = make_index_fixture_graph(spec)
        buckets, by_kind = _place(conn)
        assert buckets == {}
        assert len(by_kind) == 1
        assert by_kind[0].kind == "package"
        assert by_kind[0].name == "pkg-cross"

    def test_multi_domain_goes_to_by_kind(self, make_index_fixture_graph):
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
        buckets, by_kind = _place(conn)
        # suite should be in by_kind, not in d1 or d2 (packages can still be there)
        suite_in_by_kind = [e for e in by_kind if e.name == "suite"]
        assert len(suite_in_by_kind) == 1
        for d in buckets.values():
            assert not any(e.name == "suite" for e in d)

    def test_plugin_always_in_by_kind(self, make_index_fixture_graph):
        spec = {
            "nodes": [
                ("plugin", "graph-wiki", {"uri": "plugin:graph-wiki", "ecosystem": "claude-code"}),
            ],
            "edges": [],
        }
        conn = make_index_fixture_graph(spec)
        buckets, by_kind = _place(conn)
        assert any(e.kind == "plugin" and e.name == "graph-wiki" for e in by_kind)
        assert buckets == {}

    def test_by_kind_sort_order(self, make_index_fixture_graph):
        spec = {
            "nodes": [
                # insertion order intentionally not matching BY_KIND_ORDER
                ("plugin", "graph-wiki", {"uri": "plugin:graph-wiki", "ecosystem": "claude-code"}),
                ("package", "pkg-cross", {"uri": "pkg:pkg-cross"}),
                ("dependency", "boto3", {"uri": "dependency:pypi/boto3", "ecosystem": "pypi"}),
            ],
            "edges": [],
        }
        conn = make_index_fixture_graph(spec)
        _buckets, by_kind = _place(conn)
        # Filter to the three known names; order must be package, dependency, plugin
        kinds = [e.kind for e in by_kind if e.name in ("graph-wiki", "pkg-cross", "boto3")]
        assert kinds == ["package", "dependency", "plugin"]

    def test_intra_domain_parent_pkgs_populated(self, make_index_fixture_graph):
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
        buckets, _by_kind = _place(conn)
        # boto3 should be placed under 'core' with parent_pkg_names == ('pkg-a','pkg-b')
        deps = [e for e in buckets["core"] if e.kind == "dependency"]
        assert len(deps) == 1
        assert deps[0].parent_pkg_names == ("pkg-a", "pkg-b")


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
        _write_curated_page(
            tmp_path / "concepts" / "foo.md", title="Foo Page", summary="Test summary"
        )
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
        _write_curated_page(
            tmp_path / "work" / "2026-05-03-foo.md", title="Foo work item"
        )
        entries = _scan_work(tmp_path)
        assert len(entries) == 1
        assert entries[0]["path"] == "work/2026-05-03-foo.md"

    def test_skips_work_index(self, tmp_path):
        _write_curated_page(tmp_path / "work" / "foo.md", title="Foo")
        _write_curated_page(tmp_path / "work" / "index.md", title="Idx")
        entries = _scan_work(tmp_path)
        assert [e["title"] for e in entries] == ["Foo"]

    def test_skips_archived_subdir(self, tmp_path):
        _write_curated_page(tmp_path / "work" / "foo.md", title="Foo")
        _write_curated_page(tmp_path / "work" / "archived" / "old.md", title="Old")
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
        assert "## Domains — agent-research" in text
        assert "## Domain: core" in text
        assert "[[wiki/entities/pkg_pkg-a|pkg-a]]" in text

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
        assert "## Domain: core" in text
        assert "### Sub-Domain: billing" in text
        assert "## Domain: billing\n" not in text

    def test_empty_domain_omitted(self, tmp_path, make_index_fixture_graph):
        spec = {
            "nodes": [
                ("domain", "empty-domain", {"uri": "domain:empty-domain"}),
            ],
            "edges": [],
        }
        conn = make_index_fixture_graph(spec)
        wiki_root = tmp_path / "wiki"
        wiki_root.mkdir(parents=True, exist_ok=True)
        text, *_ = _render(conn, wiki_root)
        assert "## Domain: empty-domain" not in text


class TestRenderByKind:
    def test_by_kind_section_order(self, tmp_path, make_index_fixture_graph):
        # Phase 57 D-03/D-08: flat By-Kind groups are app/package/plugin only,
        # apps first. A dependency used by a by-kind package nests UNDER that
        # package (no flat `### Dependencies` group).
        spec = {
            "nodes": [
                ("app", "myapp", {"uri": "app:agent-research/myapp", "app_kind": "cli"}),
                ("package", "pkg-cross", {"uri": "pkg:pkg-cross"}),
                ("dependency", "boto3", {"uri": "dependency:pypi/boto3", "ecosystem": "pypi"}),
                ("plugin", "graph-wiki", {"uri": "plugin:graph-wiki", "ecosystem": "claude-code"}),
            ],
            "edges": [
                # boto3 is used by pkg-cross (which is by-kind: zero domains)
                ("package", "pkg-cross", "dependency", "boto3", "used_by", {}),
            ],
        }
        conn = make_index_fixture_graph(spec)
        wiki_root = tmp_path / "wiki"
        wiki_root.mkdir(parents=True, exist_ok=True)
        text, *_ = _render(conn, wiki_root)
        app_idx = text.find("### Apps")
        pkg_idx = text.find("### Packages")
        plug_idx = text.find("### Plugins")
        assert app_idx > -1 and pkg_idx > -1 and plug_idx > -1
        # Apps first, then packages, then plugins (D-03).
        assert app_idx < pkg_idx < plug_idx
        # No flat dependency group; boto3 nests under pkg-cross.
        assert "### Dependencies" not in text
        assert "  - Dependencies" in text
        assert "[[wiki/entities/dep_boto3|boto3]]" in text

    def test_empty_by_kind_omitted(self, tmp_path, make_index_fixture_graph):
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
        wiki_root = tmp_path / "wiki"
        wiki_root.mkdir(parents=True, exist_ok=True)
        text, *_ = _render(conn, wiki_root)
        assert "## By Kind" not in text

    def test_test_suites_subheading(self, tmp_path, make_index_fixture_graph):
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
        wiki_root = tmp_path / "wiki"
        wiki_root.mkdir(parents=True, exist_ok=True)
        text, *_ = _render(conn, wiki_root)
        # Phase 57 D-08: no flat `### Test Suites` group. The multi-domain suite
        # nests under both pkg-1 (domain d1) and pkg-2 (domain d2) per D-10.
        assert "### Test Suites" not in text
        assert "  - Test Suites" in text
        # suite tests pkg-1 and pkg-2 → its link appears under each (duplicated).
        assert text.count("[[wiki/entities/tests_suite|suite]]") == 2


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
            ("plugin", "graph-wiki", {"uri": "plugin:graph-wiki", "ecosystem": "claude-code"}),
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
    assert result.entity_count == 6  # 3 pkgs + 1 ts + 1 dep + 1 plugin
    assert result.curated_count == 2
    assert result.domain_count == 2
    # Phase 57 D-03/D-08: by_kind_count is the flat top-level group count
    # (app/package/plugin). boto3 (a by-kind dependency) no longer renders as a
    # flat group — it nests under its consumer packages — so only pkg-cross
    # (package) + graph-wiki (plugin) remain as flat By-Kind bullets.
    assert result.by_kind_count == 2

    text = (wiki_root / "index.md").read_text(encoding="utf-8")
    assert "## Domains — agent-research" in text
    assert "## Domain: billing" in text
    assert "## Domain: core" in text
    assert "## By Kind" in text
    assert "### Packages" in text
    # No flat dependency group; boto3 nests under pkg-a (core) and pkg-b
    # (billing) as a `  - Dependencies` sub-list (D-08/D-10).
    assert "### Dependencies" not in text
    assert "  - Dependencies" in text
    assert "### Plugins" in text
    # Piped human-readable links (IDX-02/D-05).
    assert "[[wiki/entities/pkg_pkg-a|pkg-a]]" in text
    assert "[[wiki/entities/dep_boto3|boto3]]" in text
    assert "## ADRs" in text
    assert "## Concepts" in text
    # Empty curated lanes omitted (D-08)
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
            ("plugin", "graph-wiki", {"ecosystem": "claude-code", "uri": "plugin:graph-wiki"}),
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

    spec["nodes"].append(
        ("package", "pkg-new", {"uri": "pkg:agent-research/pkg-new"})
    )
    spec["edges"].append(
        ("package", "pkg-new", "domain", "core", "belongs_to_domain", {})
    )
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


def test_cross_cutting_in_by_kind_only(tmp_path, make_index_fixture_graph):
    """INDEX-03 — cross-cutting packages only in by_kind."""
    spec = _build_realistic_graph_spec()
    conn = make_index_fixture_graph(spec)
    wiki_root = tmp_path / "wiki"
    wiki_root.mkdir(parents=True, exist_ok=True)

    text, *_ = _render(conn, wiki_root)
    cross_link = "[[wiki/entities/pkg_pkg-cross|pkg-cross]]"
    assert text.count(cross_link) == 1
    by_kind_idx = text.find("## By Kind")
    cross_idx = text.find(cross_link)
    assert by_kind_idx > -1
    assert by_kind_idx < cross_idx
    core_idx = text.find("## Domain: core")
    billing_idx = text.find("## Domain: billing")
    assert core_idx > -1 and billing_idx > -1
    assert core_idx < by_kind_idx
    assert billing_idx < by_kind_idx


def test_multi_domain_entity_in_by_kind(tmp_path, make_index_fixture_graph):
    """INDEX-04/D-01/D-10 — a multi-domain test_suite is placed in by_kind but
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
    assert "## Domain: core" in text
    assert "### Sub-Domain: billing" in text
    assert "## Domain: billing\n" not in text
    core_idx = text.find("## Domain: core")
    sub_idx = text.find("### Sub-Domain: billing")
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
    assert "## Domain: active-domain" in text
    assert "[[wiki/entities/pkg_pkg-solo|pkg-solo]]" in text
    active_start = text.find("## Domain: active-domain")
    next_section = text.find("##", active_start + len("## Domain: active-domain"))
    active_section = text[active_start:next_section if next_section > -1 else None]
    assert "Test Suites" not in active_section
    assert "Dependencies" not in active_section
    assert "## Domain: empty-domain" not in text


def test_plugin_always_by_kind(tmp_path, make_index_fixture_graph):
    """D-04 — plugins always in by_kind regardless of other state."""
    spec = {
        "nodes": [
            ("repository", "agent-research", {"uri": "repo:agent-research"}),
            ("domain", "core", {"uri": "domain:agent-research/core"}),
            ("package", "pkg-a", {"uri": "pkg:agent-research/pkg-a"}),
            ("plugin", "graph-wiki", {"ecosystem": "claude-code", "uri": "plugin:graph-wiki"}),
        ],
        "edges": [
            ("package", "pkg-a", "domain", "core", "belongs_to_domain", {}),
        ],
    }
    conn = make_index_fixture_graph(spec)
    wiki_root = tmp_path / "wiki"
    wiki_root.mkdir(parents=True, exist_ok=True)

    text, *_ = _render(conn, wiki_root)
    plugin_slug = "plugin_graph-wiki"
    assert text.count(plugin_slug) == 1
    by_kind_idx = text.find("## By Kind")
    plugins_idx = text.find("### Plugins")
    plug_link_idx = text.find(plugin_slug)
    assert by_kind_idx > -1
    assert plugins_idx > by_kind_idx
    assert plug_link_idx > plugins_idx


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
    adr_section = text[adr_start: next_h2 if next_h2 > -1 else len(text)]
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


def test_app_zero_domain_renders_in_by_kind_apps_first(
    tmp_path, make_index_fixture_graph
):
    """IDX-01/D-03/D-04 — a zero-domain app renders in `### Apps`, before
    `### Packages`."""
    spec = {
        "nodes": [
            ("app", "myapp", {"uri": "app:agent-research/myapp",
                              "app_kind": "cli", "app_signals": []}),
            ("package", "pkg-cross", {"uri": "pkg:agent-research/pkg-cross"}),
        ],
        "edges": [],
    }
    conn = make_index_fixture_graph(spec)
    wiki_root = tmp_path / "wiki"
    wiki_root.mkdir(parents=True, exist_ok=True)
    text, *_ = _render(conn, wiki_root)
    apps_idx = text.find("### Apps")
    pkgs_idx = text.find("### Packages")
    assert apps_idx > -1
    assert pkgs_idx > -1
    assert apps_idx < pkgs_idx  # apps listed first (D-03)
    assert "[[wiki/entities/app_myapp|myapp]]" in text


def test_app_single_domain_renders_under_its_domain(
    tmp_path, make_index_fixture_graph
):
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
    assert "## Domain: core" in text
    # App link present under its domain; no By-Kind section at all (only entity).
    assert "[[wiki/entities/app_myapp|myapp]]" in text
    assert "### Apps" not in text


def test_internal_dependencies_subsection_distinct_from_dependencies(
    tmp_path, make_index_fixture_graph
):
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
    assert "[[wiki/entities/dep_boto3|boto3]]" in text
    assert "[[wiki/entities/pkg_target|target]]" in text
    # The internal-deps heading is distinct from (and after) the external one.
    dep_idx = text.find("  - Dependencies")
    internal_idx = text.find("  - Internal dependencies")
    assert dep_idx > -1 and internal_idx > -1
    assert dep_idx < internal_idx


def test_inline_summary_from_entity_page_frontmatter(
    tmp_path, make_index_fixture_graph
):
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
    # pkg-a renders the inline summary suffix (D-07).
    assert "[[wiki/entities/pkg_pkg-a|pkg-a]] — Some summary" in text
    # pkg-b (no entity page) renders the link with NO ` — ` suffix.
    assert "[[wiki/entities/pkg_pkg-b|pkg-b]]\n" in text
    assert "[[wiki/entities/pkg_pkg-b|pkg-b]] —" not in text


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
    return conn


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
    assert pkgs_for_alpha == ("pkg-alpha",), (
        f"expected ('pkg-alpha',), got {pkgs_for_alpha!r} — fan-out detected"
    )
    assert pkgs_for_beta == ("pkg-beta",), (
        f"expected ('pkg-beta',), got {pkgs_for_beta!r} — fan-out detected"
    )

    # _consumer_pkgs_in_domain: same correctness within a domain
    pkgs_alpha_d1 = _consumer_pkgs_in_domain(
        conn, kind="test_suite", entity_uri=uri_alpha, domain_name="d1"
    )
    pkgs_beta_d1 = _consumer_pkgs_in_domain(
        conn, kind="test_suite", entity_uri=uri_beta, domain_name="d1"
    )
    assert pkgs_alpha_d1 == ("pkg-alpha",), (
        f"expected ('pkg-alpha',), got {pkgs_alpha_d1!r} — domain fan-out detected"
    )
    assert pkgs_beta_d1 == ("pkg-beta",), (
        f"expected ('pkg-beta',), got {pkgs_beta_d1!r} — domain fan-out detected"
    )

    # A URI matching no suite returns empty (no name-fallback)
    no_match = _consumer_pkgs(
        conn, kind="test_suite", entity_uri="test_suite:org/repo/no-such-suite"
    )
    assert no_match == (), f"expected () for unmatched URI, got {no_match!r}"


# --- Snapshot test against the live agent-research graph (skip when absent) ---


def _resolve_workspace_root() -> Path | None:
    """Walk up from this test file to find a workspace with .graph-wiki/graph.db."""
    cur = Path(__file__).resolve().parent
    for _ in range(8):
        if (cur / ".graph-wiki" / "graph.db").exists():
            return cur
        cur = cur.parent
    return None


_WS_ROOT = _resolve_workspace_root()


@pytest.mark.skipif(_WS_ROOT is None, reason="no live agent-research graph")
def test_snapshot_against_agent_research(snapshot):
    db = _WS_ROOT / ".graph-wiki" / "graph.db"
    conn = sqlite3.connect(str(db))
    try:
        wiki_root = _WS_ROOT / ".graph-wiki" / "wiki"
        text, *_ = _render(conn, wiki_root)
        assert text == snapshot
    finally:
        conn.close()
