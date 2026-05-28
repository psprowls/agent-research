"""Unit + property tests for wiki_io.entity_writer (Phase 42 / Plan 01).

Validates the THREE Phase 42 contracts (D-10):

1. ADMITTED_KINDS is the 6 underscore-form kinds (D-02; `package_family`
   retired in Phase 51 PKGFAM-03).
2. SCANNER_OWNED_KEYS is disjoint from the human-only keys (D-09).
3. encode_slug + decode_slug round-trip on every admitted-kind URI (D-03)
   and the encoder is injective on a sample batch (D-05).

Property tests use Hypothesis (D-11, D-12). The 2 new URI builders
(`plugin_uri`, `dependency_uri`) from Plan 02 are NOT imported here —
Plan 01 + Plan 02 are Wave-1 parallel, so this test constructs their
URIs inline per Plan 01's <interfaces> note.
"""

from __future__ import annotations

import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

from graph_io.uri import (
    RepoContext,
    domain_uri,
    pkg_uri,
    repo_uri,
)
from graph_io.uri import test_suite_uri as _test_suite_uri  # alias: avoid pytest collection
from wiki_io.entity_writer import (
    ADMITTED_KINDS,
    SCANNER_OWNED_KEYS,
    decode_slug,
    encode_slug,
)


# ----------------------------------------------------------------------------
# Unit tests
# ----------------------------------------------------------------------------


def test_admitted_kinds_shape() -> None:
    """ADMITTED_KINDS is exactly the 6 underscore-form kinds (D-02;
    `package_family` retired in Phase 51 PKGFAM-03)."""
    expected = frozenset(
        {
            "repository",
            "domain",
            "package",
            "plugin",
            "dependency",
            "test_suite",
        }
    )
    assert ADMITTED_KINDS == expected
    # Sanity check: kinds that exist in graph_io._VALID_KINDS but are NOT
    # admitted to the entity lane (per the v1.8 design notes) must stay out.
    excluded = {"subpackage", "file", "function", "class", "method"}
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


@pytest.mark.parametrize(
    "uri,expected_slug",
    [
        ("pkg:agent-research/graph-io", "pkg__agent-research__graph-io"),
        ("domain:agent-research/billing", "domain__agent-research__billing"),
        (
            "test_suite:agent-research/eval-harness/unit",
            "test_suite__agent-research__eval-harness__unit",
        ),
        (
            "repo:agent-research/agent-research",
            "repo__agent-research__agent-research",
        ),
        ("plugin:graph-wiki", "plugin__graph-wiki"),
        ("dependency:pypi/boto3", "dependency__pypi__boto3"),
    ],
)
def test_slug_encode_examples(uri: str, expected_slug: str) -> None:
    """Parametrized examples from CONTEXT.md D-01."""
    assert encode_slug(uri) == expected_slug


def test_decode_slug_rejects_unknown_kind() -> None:
    """decode_slug raises ValueError on unrecognized URI prefix."""
    with pytest.raises(ValueError, match="unknown URI prefix"):
        decode_slug("notakind__x")


def test_decode_slug_rejects_too_few_segments() -> None:
    """decode_slug raises ValueError when the slug has no `__` separator."""
    with pytest.raises(ValueError, match="malformed slug"):
        decode_slug("pkg")


# ----------------------------------------------------------------------------
# Hypothesis strategies — one composite per admitted kind (D-12)
# ----------------------------------------------------------------------------

# Real-world package / org / suite names use ASCII alphanumerics plus dashes
# and dots. Underscores are EXCLUDED from the fragment alphabet because the
# slug encoding uses `__` as the separator: a fragment starting or ending
# with `_` produces 3+ consecutive underscores in the slug, which splits
# ambiguously and breaks round-trip. This restriction matches real-world
# PEP-8 / npm-package / cargo-crate naming conventions (dashes preferred to
# underscores in distribution names). See Pitfall 1 in PITFALLS.md.
_fragment_alphabet = st.characters(
    whitelist_categories=("Ll", "Nd"),
    whitelist_characters="-.",
)
_fragment = st.text(alphabet=_fragment_alphabet, min_size=1, max_size=20)


@st.composite
def _pkg_uri_strategy(draw: st.DrawFn) -> str:
    org = draw(_fragment)
    repo = draw(_fragment)
    name = draw(_fragment)
    for f in (org, repo, name):
        assume("__" not in f)
    return pkg_uri(RepoContext(org, repo), name)


@st.composite
def _domain_uri_strategy(draw: st.DrawFn) -> str:
    org = draw(_fragment)
    repo = draw(_fragment)
    name = draw(_fragment)
    for f in (org, repo, name):
        assume("__" not in f)
    return domain_uri(RepoContext(org, repo), name)


@st.composite
def _repository_uri_strategy(draw: st.DrawFn) -> str:
    org = draw(_fragment)
    repo = draw(_fragment)
    for f in (org, repo):
        assume("__" not in f)
    return repo_uri(RepoContext(org, repo))


@st.composite
def _test_suite_uri_strategy(draw: st.DrawFn) -> str:
    org = draw(_fragment)
    repo = draw(_fragment)
    suite = draw(_fragment)
    for f in (org, repo, suite):
        assume("__" not in f)
    return _test_suite_uri(RepoContext(org, repo), suite)


@st.composite
def _plugin_uri_strategy(draw: st.DrawFn) -> str:
    name = draw(_fragment)
    assume("__" not in name)
    return f"plugin:{name}"


@st.composite
def _dependency_uri_strategy(draw: st.DrawFn) -> str:
    ecosystem = draw(_fragment)
    name = draw(_fragment)
    for f in (ecosystem, name):
        assume("__" not in f)
    return f"dependency:{ecosystem}/{name}"


_admitted_uri_strategy = st.one_of(
    _pkg_uri_strategy(),
    _domain_uri_strategy(),
    _repository_uri_strategy(),
    _test_suite_uri_strategy(),
    _plugin_uri_strategy(),
    _dependency_uri_strategy(),
)


# ----------------------------------------------------------------------------
# Property tests
# ----------------------------------------------------------------------------


@given(uri=_admitted_uri_strategy)
@settings(
    max_examples=1000,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much],
)
def test_slug_round_trip(uri: str) -> None:
    """decode_slug(encode_slug(uri)) == uri for every admitted-kind URI (D-03)."""
    assert decode_slug(encode_slug(uri)) == uri


@given(
    uris=st.lists(
        _admitted_uri_strategy,
        min_size=50,
        max_size=200,
        unique=True,
    )
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much],
)
def test_slug_batch_injective(uris: list[str]) -> None:
    """Distinct URIs encode to distinct slugs — no collisions (D-05)."""
    slugs = {encode_slug(u) for u in uris}
    assert len(slugs) == len(uris)


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
    out = _render_entity_page(template_path, fm)
    lines = out.split("\n")
    assert lines[0] == "---"
    assert lines[1].startswith("uri:")
    assert lines[2].startswith("kind:")


def test_render_entity_page_byte_stable_across_runs(tmp_path):
    template_path = tmp_path / "tpl.md"
    template_path.write_text("---\nkind: package\n---\n# Test\n")
    fm = {"uri": "pkg:x", "kind": "package", "domains": ["a"]}
    out1 = _render_entity_page(template_path, fm)
    out2 = _render_entity_page(template_path, fm)
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
    monkeypatch.setattr(q_module, "list_domains", lambda c: c.list_nodes("domain"))
    monkeypatch.setattr(q_module, "list_test_suites", lambda c: c.list_nodes("test_suite"))
    monkeypatch.setattr(q_module, "list_dependencies", lambda c: c.list_nodes("dependency"))
    monkeypatch.setattr(q_module, "list_plugins", lambda c: c.list_nodes("plugin"))
    monkeypatch.setattr(q_module, "describe_repository",
                        lambda c: c.get_description("repository", None))
    monkeypatch.setattr(q_module, "describe_package",
                        lambda c, *, name: c.get_description("package", name))
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
    # Specific filenames
    entities = wiki_root / "entities"
    assert (entities / "pkg__local__agent-research__graph-io.md").exists()
    assert (entities / "plugin__graph-wiki.md").exists()


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
    assert not (wiki_root / "entities" / "pkg__local__agent-research__wiki-io.md").exists()
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
    page_path = wiki_root / "entities" / "pkg__local__agent-research__graph-io.md"
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
