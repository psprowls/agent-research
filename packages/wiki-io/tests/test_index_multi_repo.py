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

    write_entities(conn, wiki_root, ADMITTED_KINDS)

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
