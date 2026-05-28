"""Unit + property tests for wiki_io.entity_writer (Phase 42 / Plan 01).

Validates the surviving Phase 42 contracts (D-10):

1. ADMITTED_KINDS is the 7 underscore-form kinds (D-02; `package_family`
   retired in Phase 51 PKGFAM-03; `app` admitted in Phase 52 D-06).
2. SCANNER_OWNED_KEYS is disjoint from the human-only keys (D-09).

The bidirectional-slug machinery was removed in Phase 53 D-04..D-06;
its property tests are gone. The Phase 52 short_filename contract is
covered by `test_short_filename.py`.
"""

from __future__ import annotations

import pytest

from wiki_io.entity_writer import (
    ADMITTED_KINDS,
    SCANNER_OWNED_KEYS,
)


# ----------------------------------------------------------------------------
# Unit tests
# ----------------------------------------------------------------------------


def test_admitted_kinds_shape() -> None:
    """ADMITTED_KINDS is exactly the 7 underscore-form kinds (D-02;
    `package_family` retired in Phase 51 PKGFAM-03; `app` admitted in
    Phase 52 D-06)."""
    expected = frozenset(
        {
            "repository",
            "domain",
            "package",
            "app",
            "plugin",
            "dependency",
            "test_suite",
        }
    )
    assert ADMITTED_KINDS == expected
    # Sanity check: kinds that exist in graph_io._VALID_KINDS but are NOT
    # admitted to the entity lane (per the v1.8 design notes) must stay out.
    excluded = {"subpackage", "file", "function", "class", "method", "builtin"}
    assert ADMITTED_KINDS.isdisjoint(excluded)
    # Phase 51 regression guard: package_family must never re-appear here.
    assert "package_family" not in ADMITTED_KINDS


def test_scanner_owned_keys_disjoint_from_human() -> None:
    """SCANNER_OWNED_KEYS does not include any of the documented human keys (D-09)."""
    human_only = {"status", "last_reviewed", "owner", "notes"}
    assert SCANNER_OWNED_KEYS.isdisjoint(human_only)
    # Spot-check a baseline of D-07 keys ARE present.
    for key in ("uri", "kind", "domains", "depends_on", "ecosystem"):
        assert key in SCANNER_OWNED_KEYS, f"missing baseline key: {key!r}"


# ============================================================================
# Phase 43 Plan 02: write_entities + supporting helpers
# ============================================================================

import threading
import time

from hypothesis import given, strategies as st, settings

from wiki_io.entity_writer import (
    EntityWriteError,
    EntityWriteResult,
    STRUCTURAL_KEYS,
    WriteLockHeldError,
    _acquire_scan_lock,
    _append_deletion,
    _detect_structural_change,
    _render_entity_page,
    _rotate_deletions_log,
    merge_frontmatter,
    write_entities,
)


# ----------------------------------------------------------------------------
# Task 1 sanity: constants + result dataclass shape
# ----------------------------------------------------------------------------


def test_structural_keys_subset_invariant() -> None:
    from wiki_io.entity_writer import SCANNER_OWNED_KEYS
    assert STRUCTURAL_KEYS.issubset(SCANNER_OWNED_KEYS)
    # Phase 51 PKGFAM-03: dropped `members` (package_family carrier).
    assert len(STRUCTURAL_KEYS) == 9


def test_write_lock_held_error_is_runtime_error() -> None:
    assert issubclass(WriteLockHeldError, RuntimeError)


def test_entity_write_result_defaults() -> None:
    r = EntityWriteResult()
    assert r.created == []
    assert r.updated == []
    assert r.deleted == []
    assert r.unchanged == []
    assert r.needs_narrative == set()
    assert r.errors == []


# ----------------------------------------------------------------------------
# Task 2: merge_frontmatter
# ----------------------------------------------------------------------------


def test_merge_preserves_human_authored_status() -> None:
    existing = {"uri": "pkg:x/y/z", "kind": "package", "status": "deprecated"}
    scanner_update = {"uri": "pkg:x/y/z", "kind": "package", "domains": ["a"]}
    out = merge_frontmatter(existing, scanner_update)
    assert out["status"] == "deprecated"
    assert out["domains"] == ["a"]
    assert out["uri"] == "pkg:x/y/z"


def test_merge_replaces_scanner_keys() -> None:
    existing = {"uri": "x", "kind": "package", "depends_on": ["a", "b"]}
    scanner_update = {"uri": "x", "kind": "package", "depends_on": ["c"]}
    out = merge_frontmatter(existing, scanner_update)
    assert out["depends_on"] == ["c"]


def test_merge_key_order_uri_kind_first() -> None:
    existing = {"notes": "hi", "uri": "x", "kind": "package", "status": "live"}
    scanner_update = {"uri": "x", "kind": "package", "domains": ["d"]}
    out = merge_frontmatter(existing, scanner_update)
    keys = list(out.keys())
    assert keys[0] == "uri"
    assert keys[1] == "kind"


def test_merge_scanner_keys_alphabetical() -> None:
    from wiki_io.entity_writer import SCANNER_OWNED_KEYS
    existing = {"uri": "x", "kind": "package"}
    scanner_update = {
        "uri": "x", "kind": "package",
        "test_suites": ["t1"], "depends_on": ["d1"], "domains": ["x"],
    }
    out = merge_frontmatter(existing, scanner_update)
    scanner_keys_emitted = [
        k for k in out.keys()
        if k in SCANNER_OWNED_KEYS - {"uri", "kind"}
    ]
    assert scanner_keys_emitted == sorted(scanner_keys_emitted)


def test_merge_drops_empty_scanner_values() -> None:
    existing = {"uri": "x", "kind": "package"}
    scanner_update = {"uri": "x", "kind": "package",
                      "depends_on": [], "domains": ["d"]}
    out = merge_frontmatter(existing, scanner_update)
    assert "depends_on" not in out
    assert out["domains"] == ["d"]


def test_merge_sorts_and_dedupes_collection_values() -> None:
    existing = {"uri": "x", "kind": "package"}
    scanner_update = {"uri": "x", "kind": "package", "depends_on": ["b", "a", "b"]}
    out = merge_frontmatter(existing, scanner_update)
    assert out["depends_on"] == ["a", "b"]


def test_merge_preserves_human_key_order() -> None:
    from wiki_io.entity_writer import SCANNER_OWNED_KEYS
    existing = {
        "uri": "x", "kind": "package",
        "owner": "alice", "status": "live", "notes": "see ADR-12",
    }
    scanner_update = {"uri": "x", "kind": "package"}
    out = merge_frontmatter(existing, scanner_update)
    human_keys = [k for k in out.keys() if k not in SCANNER_OWNED_KEYS]
    assert human_keys == ["owner", "status", "notes"]


# Hypothesis property tests


def _scanner_owned_minus_uri_kind() -> list[str]:
    from wiki_io.entity_writer import SCANNER_OWNED_KEYS
    return sorted(SCANNER_OWNED_KEYS - {"uri", "kind"})


_HUMAN_KEY_NAMES = st.sampled_from(
    ["status", "owner", "notes", "last_reviewed", "tags", "custom_x"]
)
_SCANNER_KEY_NAMES = st.sampled_from(_scanner_owned_minus_uri_kind())
_VALUES = st.one_of(
    st.text(min_size=0, max_size=20),
    st.lists(st.text(min_size=1, max_size=10), min_size=0, max_size=5),
    st.integers(),
)


@st.composite
def existing_dict(draw):
    d = {"uri": "pkg:org/repo/p", "kind": "package"}
    for k in draw(st.lists(_HUMAN_KEY_NAMES, max_size=5, unique=True)):
        d[k] = draw(_VALUES)
    for k in draw(st.lists(_SCANNER_KEY_NAMES, max_size=5, unique=True)):
        d[k] = draw(_VALUES)
    return d


@st.composite
def scanner_dict(draw):
    d = {"uri": "pkg:org/repo/p", "kind": "package"}
    for k in draw(st.lists(_SCANNER_KEY_NAMES, max_size=5, unique=True)):
        d[k] = draw(_VALUES)
    return d


@given(existing=existing_dict(), scanner=scanner_dict())
@settings(max_examples=500, deadline=None)
def test_merge_property_non_whitelist_preserved(existing, scanner):
    from wiki_io.entity_writer import SCANNER_OWNED_KEYS
    out = merge_frontmatter(existing, scanner)
    for k, v in existing.items():
        if k not in SCANNER_OWNED_KEYS:
            assert k in out
            assert out[k] == v


@given(existing=existing_dict(), scanner=scanner_dict())
@settings(max_examples=500, deadline=None)
def test_merge_property_scanner_keys_taken_from_scanner(existing, scanner):
    from wiki_io.entity_writer import SCANNER_OWNED_KEYS
    out = merge_frontmatter(existing, scanner)
    for k in SCANNER_OWNED_KEYS - {"uri", "kind"}:
        if k in scanner:
            val = scanner[k]
            if val is None or val == "" or val == [] or val == {}:
                assert k not in out
            else:
                if isinstance(val, list):
                    assert out[k] == sorted(set(val), key=lambda x: (str(type(x)), str(x)))
                else:
                    assert out[k] == val


# ----------------------------------------------------------------------------
# Task 3: _acquire_scan_lock
# ----------------------------------------------------------------------------


def test_scan_lock_acquires_and_releases(tmp_path):
    with _acquire_scan_lock(tmp_path):
        assert (tmp_path / ".graph-wiki" / "scan.lock").exists()
    # After release, can re-acquire
    with _acquire_scan_lock(tmp_path):
        pass


def test_scan_lock_raises_on_contention(tmp_path):
    holder_acquired = threading.Event()
    holder_release = threading.Event()
    err: list[Exception] = []

    def holder():
        try:
            with _acquire_scan_lock(tmp_path):
                holder_acquired.set()
                holder_release.wait(timeout=5.0)
        except Exception as e:
            err.append(e)

    t = threading.Thread(target=holder)
    t.start()
    try:
        assert holder_acquired.wait(timeout=2.0)
        start = time.time()
        with pytest.raises(WriteLockHeldError):
            with _acquire_scan_lock(tmp_path):
                pass
        elapsed = time.time() - start
        assert elapsed < 0.5, f"LOCK_NB should fail fast; took {elapsed:.3f}s"
    finally:
        holder_release.set()
        t.join(timeout=5.0)
    assert not err, f"holder thread raised: {err}"


def test_scan_lock_released_on_exception(tmp_path):
    with pytest.raises(RuntimeError, match="injected"):
        with _acquire_scan_lock(tmp_path):
            raise RuntimeError("injected")
    # Lock was released — second acquire succeeds
    with _acquire_scan_lock(tmp_path):
        pass


def test_scan_lock_creates_graph_wiki_dir(tmp_path):
    assert not (tmp_path / ".graph-wiki").exists()
    with _acquire_scan_lock(tmp_path):
        pass
    assert (tmp_path / ".graph-wiki").is_dir()
    assert (tmp_path / ".graph-wiki" / "scan.lock").exists()


# ----------------------------------------------------------------------------
# Task 4: deletions.log helpers
# ----------------------------------------------------------------------------


def test_append_deletion_writes_jsonl(tmp_path):
    import json as _json

    log_path = tmp_path / ".graph-wiki" / "deletions.log"
    record1 = {
        "timestamp": "2026-05-27T03:14:21Z",
        "uri": "pkg:agent-research/foo",
        "slug": "pkg__agent-research__foo",
        "path": "wiki/entities/pkg__agent-research__foo.md",
        "kind": "package",
        "body_was_empty": True,
    }
    record2 = {**record1,
               "uri": "pkg:agent-research/bar",
               "slug": "pkg__agent-research__bar"}
    _append_deletion(log_path, record1)
    _append_deletion(log_path, record2)
    lines = log_path.read_text().strip().splitlines()
    assert len(lines) == 2
    parsed = [_json.loads(line) for line in lines]
    assert parsed[0]["uri"] == "pkg:agent-research/foo"
    assert parsed[1]["uri"] == "pkg:agent-research/bar"
    assert parsed[0]["body_was_empty"] is True


def test_deletions_log_rotates_at_threshold(tmp_path):
    log_path = tmp_path / ".graph-wiki" / "deletions.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("x" * 1500)
    _rotate_deletions_log(log_path, max_bytes=1000)
    rotated = log_path.with_suffix(".log.1")
    assert rotated.exists()
    assert not log_path.exists()
    assert rotated.read_text() == "x" * 1500


def test_deletions_log_rotation_overwrites_old_log1(tmp_path):
    log_path = tmp_path / ".graph-wiki" / "deletions.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    rotated = log_path.with_suffix(".log.1")
    rotated.write_text("old")
    log_path.write_text("y" * 1500)
    _rotate_deletions_log(log_path, max_bytes=1000)
    assert rotated.read_text() == "y" * 1500
    assert not log_path.exists()


def test_rotate_no_op_when_below_threshold(tmp_path):
    log_path = tmp_path / ".graph-wiki" / "deletions.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("small")
    _rotate_deletions_log(log_path, max_bytes=10_000_000)
    assert log_path.read_text() == "small"
    assert not log_path.with_suffix(".log.1").exists()


# ----------------------------------------------------------------------------
# Task 5: _detect_structural_change + _render_entity_page
# ----------------------------------------------------------------------------


def test_detect_structural_change_returns_true_on_list_diff() -> None:
    existing = {"depends_on": ["a", "b"], "domains": ["x"]}
    new = {"depends_on": ["a", "c"], "domains": ["x"]}
    assert _detect_structural_change(existing, new) is True


def test_detect_structural_change_returns_false_on_list_reorder() -> None:
    existing = {"depends_on": ["a", "b", "c"]}
    new = {"depends_on": ["c", "a", "b"]}
    assert _detect_structural_change(existing, new) is False


def test_detect_structural_change_ignores_non_structural_keys() -> None:
    existing = {"status": "live", "depends_on": ["a"]}
    new = {"status": "deprecated", "depends_on": ["a"]}
    assert _detect_structural_change(existing, new) is False


def test_detect_structural_change_on_create_no_existing() -> None:
    existing: dict = {}
    new = {"depends_on": ["a"]}
    assert _detect_structural_change(existing, new) is True


def test_render_entity_page_deterministic_key_order(tmp_path):
    template_path = tmp_path / "tpl.md"
    template_path.write_text("---\nkind: package\n---\n# Test\n\n## Narrative\n")
    fm = {"uri": "pkg:x/y/z", "kind": "package", "domains": ["a"], "status": "live"}
    out = _render_entity_page(template_path, fm, {})
    lines = out.split("\n")
    assert lines[0] == "---"
    assert lines[1].startswith("uri:")
    assert lines[2].startswith("kind:")


def test_render_entity_page_byte_stable_across_runs(tmp_path):
    template_path = tmp_path / "tpl.md"
    template_path.write_text("---\nkind: package\n---\n# Test\n")
    fm = {"uri": "pkg:x", "kind": "package", "domains": ["a"]}
    out1 = _render_entity_page(template_path, fm, {})
    out2 = _render_entity_page(template_path, fm, {})
    assert out1 == out2
    assert out1.endswith("\n")
    assert not out1.endswith("\n\n")


# ----------------------------------------------------------------------------
# Task 7: write_entities orchestrator (mocked graph)
# ----------------------------------------------------------------------------


def _wire_mock_queries(monkeypatch, q_module):
    """Bind MockGraphConn's per-kind data to graph_io.queries.list_* / describe_*."""
    monkeypatch.setattr(q_module, "list_repositories", lambda c: c.list_nodes("repository"))
    monkeypatch.setattr(q_module, "list_packages", lambda c: c.list_nodes("package"))
    monkeypatch.setattr(q_module, "list_apps", lambda c: c.list_nodes("app"))
    monkeypatch.setattr(q_module, "list_domains", lambda c: c.list_nodes("domain"))
    monkeypatch.setattr(q_module, "list_test_suites", lambda c: c.list_nodes("test_suite"))
    monkeypatch.setattr(q_module, "list_dependencies", lambda c: c.list_nodes("dependency"))
    monkeypatch.setattr(q_module, "list_plugins", lambda c: c.list_nodes("plugin"))
    monkeypatch.setattr(q_module, "describe_repository",
                        lambda c: c.get_description("repository", None))
    monkeypatch.setattr(q_module, "describe_package",
                        lambda c, *, name: c.get_description("package", name))
    monkeypatch.setattr(q_module, "describe_app",
                        lambda c, *, name: c.get_description("app", name))
    monkeypatch.setattr(q_module, "describe_domain",
                        lambda c, *, name: c.get_description("domain", name))
    monkeypatch.setattr(q_module, "describe_test_suite",
                        lambda c, *, suite_name: c.get_description("test_suite", suite_name))
    monkeypatch.setattr(q_module, "describe_dependency",
                        lambda c, *, ecosystem, name: c.get_description("dependency", (ecosystem, name)))
    monkeypatch.setattr(q_module, "describe_plugin",
                        lambda c, *, name: c.get_description("plugin", name))


def test_write_entities_creates_pages_per_admitted_kind(
    tmp_path, mock_graph_conn, monkeypatch,
):
    from graph_io import queries as q
    _wire_mock_queries(monkeypatch, q)

    wiki_root = tmp_path / "wiki"
    result = write_entities(mock_graph_conn, wiki_root, ADMITTED_KINDS)
    # 1 repo + 2 packages + 1 domain + 1 test_suite + 1 dep + 1 plugin = 7 created
    assert len(result.created) == 7, f"expected 7 created, got {len(result.created)}: {result.created}"
    assert len(result.updated) == 0
    assert len(result.deleted) == 0
    assert result.needs_narrative == set(result.created)
    assert result.errors == []
    # Specific filenames (Phase 52: short-form via `short_filename`)
    entities = wiki_root / "entities"
    assert (entities / "pkg_graph-io.md").exists()
    assert (entities / "plugin_graph-wiki.md").exists()


def test_write_entities_second_run_all_unchanged(
    tmp_path, mock_graph_conn, monkeypatch,
):
    from graph_io import queries as q
    _wire_mock_queries(monkeypatch, q)
    wiki_root = tmp_path / "wiki"
    r1 = write_entities(mock_graph_conn, wiki_root, ADMITTED_KINDS)
    r2 = write_entities(mock_graph_conn, wiki_root, ADMITTED_KINDS)
    assert r2.created == []
    assert r2.updated == []
    assert len(r2.unchanged) == len(r1.created)


def test_write_entities_deletes_pages_for_disappeared_nodes(
    tmp_path, mock_graph_conn, monkeypatch,
):
    from graph_io import queries as q
    _wire_mock_queries(monkeypatch, q)
    wiki_root = tmp_path / "wiki"
    write_entities(mock_graph_conn, wiki_root, ADMITTED_KINDS)
    # Remove wiki-io package from mock
    remaining = [n for n in mock_graph_conn.list_nodes("package") if n.name != "wiki-io"]
    mock_graph_conn.set_nodes("package", remaining)
    r2 = write_entities(mock_graph_conn, wiki_root, ADMITTED_KINDS)
    assert any("wiki-io" in uri for uri in r2.deleted), f"expected wiki-io in deleted, got {r2.deleted}"
    assert not (wiki_root / "entities" / "pkg_wiki-io.md").exists()
    log_path = tmp_path / ".graph-wiki" / "deletions.log"
    assert log_path.exists()
    lines = log_path.read_text().strip().splitlines()
    assert any("wiki-io" in line for line in lines)


def test_write_entities_preserves_human_authored_status(
    tmp_path, mock_graph_conn, monkeypatch,
):
    from graph_io import queries as q
    _wire_mock_queries(monkeypatch, q)
    wiki_root = tmp_path / "wiki"
    write_entities(mock_graph_conn, wiki_root, ADMITTED_KINDS)
    page_path = wiki_root / "entities" / "pkg_graph-io.md"
    raw = page_path.read_text()
    raw_new = raw.replace("kind: package\n", "kind: package\nstatus: deprecated\n", 1)
    page_path.write_text(raw_new)
    write_entities(mock_graph_conn, wiki_root, ADMITTED_KINDS)
    final = page_path.read_text()
    assert "status: deprecated" in final


def test_write_entities_needs_narrative_on_structural_change(
    tmp_path, mock_graph_conn, monkeypatch,
):
    from graph_io import queries as q
    from graph_io.queries import PackageDescription
    _wire_mock_queries(monkeypatch, q)
    wiki_root = tmp_path / "wiki"
    write_entities(mock_graph_conn, wiki_root, ADMITTED_KINDS)
    # Mutate package description so domains list changes — should trigger needs_narrative
    new_desc = PackageDescription(
        name="graph-io", language="python", version="0.2.1",
        files=["x"], counts={}, domains=["storage", "new-domain"],
        entry_points=[], test_suites=[],
    )
    mock_graph_conn.set_description("package", "graph-io", new_desc)
    r2 = write_entities(mock_graph_conn, wiki_root, ADMITTED_KINDS)
    assert any("graph-io" in uri for uri in r2.updated)
    assert any("graph-io" in uri for uri in r2.needs_narrative)


# ============================================================================
# Phase 52 Plan 02: short_filename integration in write_entities
# ============================================================================

import hashlib as _hashlib_phase52

from graph_io.queries import NodeRecord as _NodeRecord_phase52


def test_write_entities_short_filenames(tmp_path, mock_graph_conn, monkeypatch):
    """Phase 52 D-01/D-02/D-05/D-07: write_entities emits short-form filenames.

    Builds a graph with one node per admitted kind (test_suite carries
    suite_kind=unit so the kind-aware naming kicks in) and asserts each
    file lands at the expected short stem.
    """
    from graph_io import queries as q
    _wire_mock_queries(monkeypatch, q)

    # Override the default fixture's test_suite node to set suite_kind="unit"
    # and a path whose parent.name is the package name. Also overwrite the
    # default packages to predictable single-pkg shape for this test.
    mock_graph_conn.set_nodes("repository", [
        _NodeRecord_phase52(
            kind="repository", name="test-repo", path=None, line=None,
            attrs={"uri": "repo:test-org/test-repo", "owner": "test-org"},
        ),
    ])
    mock_graph_conn.set_nodes("package", [
        _NodeRecord_phase52(
            kind="package", name="widget", path="packages/widget", line=None,
            attrs={"uri": "pkg:test-org/test-repo/widget",
                   "language": "python", "version": "0.1.0"},
        ),
    ])
    mock_graph_conn.set_nodes("domain", [
        _NodeRecord_phase52(
            kind="domain", name="observability", path=None, line=None,
            attrs={"uri": "domain:test-org/test-repo/observability"},
        ),
    ])
    mock_graph_conn.set_nodes("plugin", [
        _NodeRecord_phase52(
            kind="plugin", name="demo-plugin", path=None, line=None,
            attrs={"uri": "plugin:demo-plugin", "ecosystem": "claude-code"},
        ),
    ])
    mock_graph_conn.set_nodes("dependency", [
        _NodeRecord_phase52(
            kind="dependency", name="example-lib", path=None, line=None,
            attrs={"uri": "dependency:pypi/example-lib",
                   "ecosystem": "pypi",
                   "versions_in_use": ["example-lib>=1.0"]},
        ),
    ])
    mock_graph_conn.set_nodes("test_suite", [
        _NodeRecord_phase52(
            kind="test_suite", name="widget-tests",
            path="packages/widget/tests", line=None,
            attrs={"uri": "test_suite:test-org/test-repo/packages/widget/tests",
                   "suite_kind": "unit", "file_count": 5},
        ),
    ])
    # Descriptions: only the package one is strictly required (existing
    # `_wire_mock_queries` wires describe_* to read from set_description).
    # Without it, scanner_frontmatter_for_node sees `d is None` and skips
    # the kind-specific fields — the URI + kind frontmatter is still set,
    # which is enough for short_filename to resolve a filename.

    wiki_root = tmp_path / "wiki"
    result = write_entities(mock_graph_conn, wiki_root, ADMITTED_KINDS)

    entities = wiki_root / "entities"
    expected_files = [
        "repo_test-repo.md",
        "pkg_widget.md",
        "domain_observability.md",
        "plugin_demo-plugin.md",
        "dep_example-lib.md",
        "unit_tests_widget.md",
    ]
    for fname in expected_files:
        assert (entities / fname).exists(), (
            f"expected {fname} on disk; "
            f"got: {sorted(p.name for p in entities.iterdir())}"
        )
    assert result.errors == [], f"unexpected errors: {result.errors}"


def test_write_entities_cross_org_collision(tmp_path, mock_graph_conn, monkeypatch):
    """Phase 52 D-04: ALL colliders get a `__<6hex>` suffix, not just N-1.

    NOTE: This diverges from the literal Roadmap §52 SC#3 wording (which
    implies one plain-stem winner) per the Phase 52 discussion-log
    acceptance — D-04's referentially-transparent semantics requires
    symmetric suffixes.
    """
    from graph_io import queries as q
    _wire_mock_queries(monkeypatch, q)

    mock_graph_conn.set_nodes("repository", [])
    mock_graph_conn.set_nodes("domain", [])
    mock_graph_conn.set_nodes("plugin", [])
    mock_graph_conn.set_nodes("dependency", [])
    mock_graph_conn.set_nodes("test_suite", [])
    mock_graph_conn.set_nodes("package", [
        _NodeRecord_phase52(
            kind="package", name="utils", path="org-a/repo/utils", line=None,
            attrs={"uri": "pkg:org-a/repo/utils",
                   "language": "python", "version": "0.1.0"},
        ),
        _NodeRecord_phase52(
            kind="package", name="utils", path="org-b/repo/utils", line=None,
            attrs={"uri": "pkg:org-b/repo/utils",
                   "language": "python", "version": "0.1.0"},
        ),
    ])

    wiki_root = tmp_path / "wiki"
    write_entities(mock_graph_conn, wiki_root, ADMITTED_KINDS)

    h_a = _hashlib_phase52.sha256(b"pkg:org-a/repo/utils").hexdigest()[:6]
    h_b = _hashlib_phase52.sha256(b"pkg:org-b/repo/utils").hexdigest()[:6]
    entities = wiki_root / "entities"
    assert (entities / f"pkg_utils__{h_a}.md").exists()
    assert (entities / f"pkg_utils__{h_b}.md").exists()
    # D-04 symmetric: no plain-stem winner.
    assert not (entities / "pkg_utils.md").exists()


def test_dep_prefix_alias(tmp_path, mock_graph_conn, monkeypatch):
    """Phase 52 D-05: `dependency:` URIs produce `dep_<name>.md`, not `dependency_<name>.md`."""
    from graph_io import queries as q
    _wire_mock_queries(monkeypatch, q)

    mock_graph_conn.set_nodes("repository", [])
    mock_graph_conn.set_nodes("package", [])
    mock_graph_conn.set_nodes("domain", [])
    mock_graph_conn.set_nodes("plugin", [])
    mock_graph_conn.set_nodes("test_suite", [])
    mock_graph_conn.set_nodes("dependency", [
        _NodeRecord_phase52(
            kind="dependency", name="sample-pkg", path=None, line=None,
            attrs={"uri": "dependency:pypi/sample-pkg",
                   "ecosystem": "pypi",
                   "versions_in_use": ["sample-pkg>=1.0"]},
        ),
    ])

    wiki_root = tmp_path / "wiki"
    write_entities(mock_graph_conn, wiki_root, ADMITTED_KINDS)

    entities = wiki_root / "entities"
    assert (entities / "dep_sample-pkg.md").exists()
    assert not (entities / "dependency_sample-pkg.md").exists()


# ============================================================================
# Phase 52 Plan 03: app kind admission in wiki_io
# ============================================================================


def test_entity_app_template_exists() -> None:
    """Phase 52 D-06: entity-app.md template exists and is loadable as `kind: app`."""
    import frontmatter as _fm

    from wiki_io.entity_writer import _template_path_for_kind

    path = _template_path_for_kind("app")
    assert path.exists(), f"entity-app.md template missing at {path}"
    post = _fm.load(path)
    assert post.metadata.get("kind") == "app"


def test_write_entities_renders_app_pages(tmp_path, mock_graph_conn, monkeypatch):
    """Phase 52 D-06: an `app:` node materializes as `app_<name>.md` on disk.

    Uses a minimal app node fixture: `describe_app` returns None for this
    name (no description registered), which exercises the graceful
    fallback path in `scanner_frontmatter_for_node` — only `uri` + `kind`
    frontmatter is written, but the short filename + template wiring is
    fully verified.
    """
    from graph_io import queries as q
    _wire_mock_queries(monkeypatch, q)

    # Override fixture: only an app node, plus the default required template kinds.
    mock_graph_conn.set_nodes("repository", [])
    mock_graph_conn.set_nodes("package", [])
    mock_graph_conn.set_nodes("domain", [])
    mock_graph_conn.set_nodes("plugin", [])
    mock_graph_conn.set_nodes("dependency", [])
    mock_graph_conn.set_nodes("test_suite", [])
    mock_graph_conn.set_nodes("app", [
        _NodeRecord_phase52(
            kind="app", name="demo-app",
            path="apps/demo-app", line=None,
            attrs={"uri": "app:test-org/test-repo/demo-app",
                   "language": "python", "version": "0.1.0"},
        ),
    ])

    wiki_root = tmp_path / "wiki"
    result = write_entities(mock_graph_conn, wiki_root, ADMITTED_KINDS)
    assert result.errors == [], f"unexpected errors: {result.errors}"

    page_path = wiki_root / "entities" / "app_demo-app.md"
    assert page_path.exists(), (
        f"expected app_demo-app.md at {page_path}; "
        f"got: {sorted(p.name for p in (wiki_root / 'entities').iterdir())}"
    )

    import frontmatter as _fm
    post = _fm.load(page_path)
    assert post.metadata.get("kind") == "app"
    assert post.metadata.get("uri") == "app:test-org/test-repo/demo-app"
