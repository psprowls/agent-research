"""Multi-repo regression tests for the index + entity-filename layers.

Task 9 of the multi-repo-workspace feature — VERIFICATION that:

1. An index built from a DB with TWO ``repository`` nodes renders TWO
   ``## Repository:`` sections and reports ``repo_count == 2`` through the
   public ``generate_index`` entry point (not just ``_render``).
2. Two packages named the SAME (e.g. ``common``) in DIFFERENT repos produce
   two DISTINCT ``entities/*.md`` filenames via the existing collision-set
   ``__<6hex>`` disambiguator — proven through the real on-disk write path
   (``write_entities``).

Both layers already support multi-repo (the prereq Tasks 1/2 landed the
``repository`` node + ``nodes.repo`` column; the collision logic predates this
feature). These tests lock that behavior against regression. They reuse the
``make_index_fixture_graph`` factory (conftest) so they exercise the same
``graph_io.upsert`` schema path production code uses — no reimplementation.
"""

from __future__ import annotations

import sqlite3

from graph_io import upsert
from graph_io.handle import GraphReader
from graph_io.schema import apply_schema
from source_parser.projections.graph import GraphNode, GraphRecords
from wiki_io.entity_writer import ADMITTED_KINDS, write_entities
from wiki_io.index_generator import generate_index

# ============================================================================
# Acceptance 1 — generate_index renders N repository sections
# ============================================================================


def test_generate_index_two_repositories_render_two_sections(tmp_path, make_index_fixture_graph):
    """A DB with two ``repository`` nodes (each with one entity) yields
    ``repo_count == 2`` and two ``## Repository:`` headings in the written file."""
    spec = {
        "nodes": [
            ("repository", "repo-alpha", {"uri": "repo:local/repo-alpha"}),
            ("repository", "repo-beta", {"uri": "repo:local/repo-beta"}),
            ("package", "pkg-alpha", {"uri": "pkg:local/repo-alpha/pkg-alpha"}),
            ("package", "pkg-beta", {"uri": "pkg:local/repo-beta/pkg-beta"}),
        ],
        "edges": [],
    }
    conn = make_index_fixture_graph(spec)
    wiki_root = tmp_path / "wiki"
    wiki_root.mkdir()

    result = generate_index(conn, wiki_root)

    assert result.repo_count == 2

    text = (wiki_root / "index.md").read_text(encoding="utf-8")
    assert "\n## Repository: repo-alpha" in text
    assert "\n## Repository: repo-beta" in text
    assert text.count("\n## Repository: ") == 2
    # Each repo's own entity renders inside its own section (alphabetical order).
    alpha_idx = text.find("\n## Repository: repo-alpha")
    beta_idx = text.find("\n## Repository: repo-beta")
    pkg_alpha_idx = text.find("\n### Package: pkg-alpha")
    pkg_beta_idx = text.find("\n### Package: pkg-beta")
    assert alpha_idx < pkg_alpha_idx < beta_idx < pkg_beta_idx


# ============================================================================
# Acceptance 1b — a URI-less node resolves via the authoritative repo column
# ============================================================================


def test_uri_less_node_resolved_via_repo_column(tmp_path, make_index_fixture_graph):
    """A package node whose URI carries no ``{org}/{repo}`` segment but has a
    valid ``repo`` column must place under the repo named by its ``repo``
    column — ``_place_entities`` must NOT raise in a multi-repo graph.

    Defense-in-depth for the multi-repo index ``_repo_for``: previously such a
    node raised ``ValueError`` when >1 repository existed and the URI failed to
    resolve. The fallback to the authoritative ``nodes.repo`` column keeps the
    whole index from crashing on one stray node. A real entity-page URI is
    given so the downstream rendering / collision machinery is exercised
    normally — only the *repo resolution* depends on the column here.
    """
    from wiki_io.entity_writer import ADMITTED_KINDS as _ADMITTED_KINDS
    from wiki_io.entity_writer import _compute_collision_set, _kind_list_fns
    from wiki_io.index_generator import _place_entities

    spec = {
        "nodes": [
            ("repository", "repo-alpha", {"uri": "repo:local/repo-alpha"}),
            ("repository", "repo-beta", {"uri": "repo:local/repo-beta"}),
            ("package", "pkg-beta", {"uri": "pkg:local/repo-beta/pkg-beta"}),
            # A repo-less URI shape (only 2 segments after the scheme -> no
            # {org}/{repo} match in _parse_repo_key); resolvable only via the
            # repo column.
            ("package", "stub-pkg", {"uri": "pkg:stub-pkg"}),
        ],
        "edges": [],
    }
    conn = make_index_fixture_graph(spec)
    # Stamp the stray node's authoritative repo column (the only resolver).
    conn.execute(
        "UPDATE nodes SET repo = ? WHERE kind='package' AND name='stub-pkg'",
        ("repo:local/repo-alpha",),
    )
    wiki_root = tmp_path / "wiki"
    wiki_root.mkdir()

    collision_set = _compute_collision_set(conn, _ADMITTED_KINDS, _kind_list_fns())
    # Must NOT raise — the repo column resolves the stray node.
    per_repo, _name_to_entity = _place_entities(conn, wiki_root, collision_set)

    # The stub package is bucketed under repo-alpha (its repo column), direct.
    alpha_direct = per_repo["repo-alpha"]
    assert any(e.name == "stub-pkg" for e in alpha_direct)
    # And NOT under repo-beta.
    if "repo-beta" in per_repo:
        beta_direct = per_repo["repo-beta"]
        assert all(e.name != "stub-pkg" for e in beta_direct)


def test_single_repo_uri_less_node_unchanged(tmp_path, make_index_fixture_graph):
    """Single-repo behavior is unaffected: a node with an unresolvable URI still
    falls into the lone repository via the ``len(repos) == 1`` fallback (no repo
    column needed). Asserts the column fallback is a no-op for single-repo."""
    from wiki_io.entity_writer import ADMITTED_KINDS as _ADMITTED_KINDS
    from wiki_io.entity_writer import _compute_collision_set, _kind_list_fns
    from wiki_io.index_generator import _place_entities

    spec = {
        "nodes": [
            ("repository", "solo", {"uri": "repo:local/solo"}),
            ("package", "stub-pkg", {"uri": "pkg:stub-pkg"}),
        ],
        "edges": [],
    }
    conn = make_index_fixture_graph(spec)
    wiki_root = tmp_path / "wiki"
    wiki_root.mkdir()

    collision_set = _compute_collision_set(conn, _ADMITTED_KINDS, _kind_list_fns())
    per_repo, _name_to_entity = _place_entities(conn, wiki_root, collision_set)
    solo_direct = per_repo["solo"]
    assert any(e.name == "stub-pkg" for e in solo_direct)


# ============================================================================
# Acceptance 1c — a global dependency (repo=NULL, repo-less URI) consumed by
# packages in MULTIPLE repos places under each consumer's repo (no crash)
# ============================================================================


def test_global_dependency_placed_in_consumer_repos(tmp_path, make_index_fixture_graph):
    """A single GLOBAL ``dependency`` node (``repo`` NULL, repo-less URI
    ``dependency:npm/shared-dep``) consumed by packages in TWO different repos
    must NOT crash ``_place_entities`` and must render nested under each
    consumer package in its respective repository section.

    Reproduces the StickerGiant e2e crash: external npm deps are ONE global
    graph node (``repo=NULL``); ``_repo_for`` cannot resolve a repo from the
    URI or the (NULL) repo column, and with >1 repository node the old
    ``len(repos)==1`` fallback didn't fire → ValueError. The dep's natural home
    is the repo(s) of its CONSUMER packages (via ``used_by``).
    """
    spec = {
        "nodes": [
            ("repository", "repo-a", {"uri": "repo:local/repo-a"}),
            ("repository", "repo-b", {"uri": "repo:local/repo-b"}),
            ("package", "pkg-a", {"uri": "pkg:local/repo-a/pkg-a"}),
            ("package", "pkg-b", {"uri": "pkg:local/repo-b/pkg-b"}),
            # Global dependency: repo-less URI, repo column left NULL.
            ("dependency", "shared-dep", {"uri": "dependency:npm/shared-dep"}),
        ],
        # used_by edge: (package) -[used_by]-> (dependency); pkg-a and pkg-b
        # both consume the one shared dependency node.
        "edges": [
            ("package", "pkg-a", "dependency", "shared-dep", "used_by", {}),
            ("package", "pkg-b", "dependency", "shared-dep", "used_by", {}),
        ],
    }
    conn = make_index_fixture_graph(spec)
    wiki_root = tmp_path / "wiki"
    wiki_root.mkdir()

    # Must NOT raise — the consumer-repo placement resolves the global dep.
    result = generate_index(conn, wiki_root)

    assert result.repo_count == 2

    text = (wiki_root / "index.md").read_text(encoding="utf-8")
    repo_a_idx = text.find("\n## Repository: repo-a")
    repo_b_idx = text.find("\n## Repository: repo-b")
    assert repo_a_idx != -1 and repo_b_idx != -1

    repo_a_block = text[repo_a_idx:repo_b_idx]
    repo_b_block = text[repo_b_idx:]
    # The dependency nests under its consumer package in EACH repo section.
    assert "### Package: pkg-a" in repo_a_block
    assert "shared-dep" in repo_a_block
    assert "### Package: pkg-b" in repo_b_block
    assert "shared-dep" in repo_b_block


def test_orphan_global_dependency_does_not_crash(tmp_path, make_index_fixture_graph):
    """A global dependency with ZERO consumer packages must not crash the index.

    Fallback choice: an unconsumed external dep has no natural repo home, so it
    is SKIPPED from direct placement entirely (it would never render anyway —
    deps only render nested under consumer packages, and there are none).
    """
    spec = {
        "nodes": [
            ("repository", "repo-a", {"uri": "repo:local/repo-a"}),
            ("repository", "repo-b", {"uri": "repo:local/repo-b"}),
            ("package", "pkg-a", {"uri": "pkg:local/repo-a/pkg-a"}),
            # Orphan global dependency: no used_by edges at all.
            ("dependency", "orphan-dep", {"uri": "dependency:npm/orphan-dep"}),
        ],
        "edges": [],
    }
    conn = make_index_fixture_graph(spec)
    wiki_root = tmp_path / "wiki"
    wiki_root.mkdir()

    # Must NOT raise.
    result = generate_index(conn, wiki_root)
    assert result.repo_count >= 1

    text = (wiki_root / "index.md").read_text(encoding="utf-8")
    # The orphan dep has no consumer, so it renders nowhere.
    assert "orphan-dep" not in text


# ============================================================================
# Acceptance 2 — same-named packages across repos get distinct entity stems
# ============================================================================


def test_same_named_packages_across_repos_get_distinct_filenames(tmp_path):
    """Two packages both named ``common`` in different repos produce two
    distinct ``entities/*.md`` stems via the ``__<6hex>`` disambiguator.

    Proven end-to-end through ``write_entities`` (the real on-disk path that
    invokes ``_compute_collision_set`` internally), so the filenames asserted
    are the actual files the scanner would write.

    Built directly (not via ``make_index_fixture_graph``) so each ``common``
    package carries a DISTINCT ``path`` — node identity is ``(kind, name,
    path)`` (``graph_io.upsert``), and in a real multi-repo build the two
    ``common`` packages live at different filesystem paths. The factory's
    blank ``path=""`` would collapse them into one node (a fixture artifact,
    not production behavior).
    """
    conn = sqlite3.connect(":memory:")
    apply_schema(conn)
    nodes = (
        GraphNode(kind="repository", name="repo-alpha", path="", line=None, attrs={"uri": "repo:local/repo-alpha"}),
        GraphNode(kind="repository", name="repo-beta", path="", line=None, attrs={"uri": "repo:local/repo-beta"}),
        GraphNode(
            kind="package",
            name="common",
            path="repo-alpha/packages/common",
            line=None,
            attrs={"uri": "pkg:local/repo-alpha/common"},
        ),
        GraphNode(
            kind="package",
            name="common",
            path="repo-beta/packages/common",
            line=None,
            attrs={"uri": "pkg:local/repo-beta/common"},
        ),
    )
    upsert.upsert_records(conn, GraphRecords(nodes=nodes, edges=()))
    wiki_root = tmp_path / "wiki"
    wiki_root.mkdir()

    write_entities(GraphReader(conn), wiki_root, ADMITTED_KINDS)

    entities = wiki_root / "entities"
    # Assert structurally (glob), NOT by recomputing the production hash —
    # so the test keeps catching regressions if the disambiguator algorithm,
    # encoding, or slice length ever changes (and pytest prints the real
    # filenames on failure).
    common_pages = sorted(entities.glob("pkg_common*.md"))
    assert len(common_pages) == 2  # two distinct entity files, one per repo
    assert common_pages[0].name != common_pages[1].name  # disambiguated stems differ
    # collision rule: both URIs collide on `pkg_common`, so neither keeps the
    # plain stem — both carry the `__<6hex>` suffix.
    assert not (entities / "pkg_common.md").exists()
