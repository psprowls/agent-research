"""Phase 45 D-04 / D-07 / D-08 / D-15: end-to-end run_scan integration tests.

These tests exercise the rewired scan pipeline against a real on-disk sqlite
graph + a real wiki tree. They monkeypatch the pre-scan `cg update`
(`_capture_run`) so the test doesn't need a real `git`/`cg` toolchain and
stub the narrator LLM so they don't call Bedrock. The graph queries, file
writes, `write_entities` + `inject_narrative` + `generate_index` +
`update_index` calls all run for real.
"""

# integration-gate-allow — narrator LLM stubbed + cg update monkeypatched

from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import graph_wiki_agent.commands.scan as scan_module
from graph_io import exit_codes


# ---------------------------------------------------------------------------
# Fixture: build a minimal real workspace + wiki + graph DB + entity templates
# ---------------------------------------------------------------------------


def _seed_graph(db_path: Path) -> None:
    """Seed `code.db` with a tiny graph: one repository + one package + one domain."""
    from graph_io import schema

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        schema.apply_schema(conn)
        conn.execute(
            "INSERT INTO nodes(kind, name, path, line, attrs_json, uri) VALUES "
            "('repository', 'agent-research', '', NULL, '{}', 'repo:agent-research/agent-research')"
        )
        conn.execute(
            "INSERT INTO nodes(kind, name, path, line, attrs_json, uri) VALUES "
            "('package', 'foo', 'packages/foo', NULL, '{\"language\": \"python\"}', 'pkg:agent-research/foo')"
        )
        conn.execute(
            "INSERT INTO nodes(kind, name, path, line, attrs_json, uri) VALUES "
            "('domain', 'billing', NULL, NULL, '{}', 'domain:agent-research/billing')"
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def fixture_wiki_with_graph(tmp_path: Path, monkeypatch):
    """Real workspace + wiki + on-disk sqlite graph. Returns (wiki_path, workspace).

    Patches `_capture_run` so the pre-scan cg update step reports SUCCESS
    without executing real git/cg work.
    """
    workspace = tmp_path / "workspace"
    wiki = workspace / "wiki"
    wiki.mkdir(parents=True)
    (wiki / "log.md").write_text("", encoding="utf-8")
    (wiki / "CLAUDE.md").write_text("# Wiki\n", encoding="utf-8")
    (wiki / ".graph-wiki").mkdir(parents=True)

    # Build the real graph DB at <workspace>/.graph/code.db.
    db_path = workspace / ".graph" / "code.db"
    _seed_graph(db_path)

    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(workspace))
    monkeypatch.setattr(
        scan_module,
        "_capture_run",
        lambda *a, **k: (exit_codes.SUCCESS, "", ""),
    )

    return wiki, workspace


def _patch_narrator_llm(monkeypatch, content: str = "NARRATIVE BODY"):
    """Patch make_llm to return a stub LLM whose ainvoke yields `content`."""
    fake_resp = MagicMock()
    fake_resp.content = content
    fake_resp.usage_metadata = None
    fake_llm = MagicMock()
    fake_llm.ainvoke = AsyncMock(return_value=fake_resp)
    monkeypatch.setattr(
        scan_module, "make_llm", lambda role: fake_llm if role == "narrator" else fake_llm
    )
    return fake_llm


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_run_scan_creates_entity_pages_from_graph(fixture_wiki_with_graph, monkeypatch):
    """Step 9a writes wiki/entities/<slug>.md for every admitted graph node."""
    wiki, workspace = fixture_wiki_with_graph
    _patch_narrator_llm(monkeypatch)

    result = asyncio.run(scan_module.run_scan(workspace_path=workspace, no_file_map=True))

    assert (wiki / "entities").exists(), "wiki/entities/ should have been created"
    entity_pages = list((wiki / "entities").glob("*.md"))
    assert len(entity_pages) > 0, "Expected at least one entity page"
    assert isinstance(result, scan_module.ScanResult)
    assert len(result.entities_created) > 0, (
        f"entities_created should be populated; got {result.entities_created!r}"
    )


def test_run_scan_writes_no_legacy_package_pages(fixture_wiki_with_graph, monkeypatch):
    """Phase 45 D-08: wiki/packages/<n>/<n>.md is NOT written from a fresh scan."""
    wiki, workspace = fixture_wiki_with_graph
    _patch_narrator_llm(monkeypatch)

    asyncio.run(scan_module.run_scan(workspace_path=workspace, no_file_map=True))

    # No legacy package pages should be created. The directory may not exist
    # at all; if it does, no `<name>/<name>.md` should live under it.
    if (wiki / "packages").exists():
        for sub in (wiki / "packages").iterdir():
            if sub.is_dir():
                same_name = sub / f"{sub.name}.md"
                assert not same_name.exists(), (
                    f"Legacy package page should not be written: {same_name}"
                )


def test_run_scan_narrator_gates_on_needs_narrative(fixture_wiki_with_graph, monkeypatch):
    """Second scan against the same graph has empty needs_narrative — narrator pool does NOT run."""
    wiki, workspace = fixture_wiki_with_graph

    call_counter = {"narrator": 0}
    fake_resp = MagicMock()
    fake_resp.content = "NARRATIVE"
    fake_resp.usage_metadata = None
    fake_llm = MagicMock()

    async def _ainvoke(*a, **k):
        call_counter["narrator"] += 1
        return fake_resp

    fake_llm.ainvoke = _ainvoke
    monkeypatch.setattr(scan_module, "make_llm", lambda role: fake_llm)

    # First scan — narrator should fire for every admitted URI.
    r1 = asyncio.run(scan_module.run_scan(workspace_path=workspace, no_file_map=True))
    first_call_count = call_counter["narrator"]
    assert first_call_count > 0, "First scan should invoke the narrator at least once"

    # Second scan against the same graph — no URIs need narrating.
    call_counter["narrator"] = 0
    r2 = asyncio.run(scan_module.run_scan(workspace_path=workspace, no_file_map=True))
    assert call_counter["narrator"] == 0, (
        "Narrator must NOT fire when needs_narrative is empty (D-04)"
    )
    assert r2.entities_narrated == []


def test_step_12_dual_writer_index(fixture_wiki_with_graph, monkeypatch):
    """Step 12 produces wiki/index.md (generate_index) AND per-folder sub-indexes (update_index)."""
    wiki, workspace = fixture_wiki_with_graph
    # Seed a concept page so update_index has something to write.
    (wiki / "concepts").mkdir(parents=True, exist_ok=True)
    (wiki / "concepts" / "foo.md").write_text(
        "---\ncategory: concept\ntitle: Foo\n---\n\nbody\n",
        encoding="utf-8",
    )
    _patch_narrator_llm(monkeypatch)

    asyncio.run(scan_module.run_scan(workspace_path=workspace, no_file_map=True))

    assert (wiki / "index.md").exists(), "wiki/index.md should be written by generate_index"
    assert (wiki / "concepts" / "index.md").exists(), (
        "wiki/concepts/index.md should be written by update_index"
    )


def test_step_12_calls_generate_then_update(fixture_wiki_with_graph, monkeypatch):
    """Order check: generate_index is called before update_index."""
    wiki, workspace = fixture_wiki_with_graph
    _patch_narrator_llm(monkeypatch)

    call_order: list[str] = []
    real_generate = scan_module.generate_index
    real_update = scan_module.update_index

    def wrapped_generate(conn, wiki_root):
        call_order.append("generate_index")
        return real_generate(conn, wiki_root)

    def wrapped_update(w):
        call_order.append("update_index")
        return real_update(w)

    monkeypatch.setattr(scan_module, "generate_index", wrapped_generate)
    monkeypatch.setattr(scan_module, "update_index", wrapped_update)

    asyncio.run(scan_module.run_scan(workspace_path=workspace, no_file_map=True))

    assert "generate_index" in call_order
    assert "update_index" in call_order
    gi = call_order.index("generate_index")
    ui = call_order.index("update_index")
    assert gi < ui, (
        f"generate_index must be called before update_index; got {call_order!r}"
    )


def test_entity_pages_prose_only_no_frontmatter_drift(fixture_wiki_with_graph, monkeypatch):
    """Phase 45 D-05/SCANINT-02: narrator output is injected as prose only.

    Even if the narrator returns a string that LOOKS like frontmatter or an H1,
    `inject_narrative` only touches the body between `## Narrative` and the
    next H2 — the page's frontmatter (uri, kind) is preserved.
    """
    import frontmatter

    wiki, workspace = fixture_wiki_with_graph
    bad_content = (
        "---\nuri: HACKED\nkind: HACKED\n---\n\n"
        "# H1 HEADING\n\nbody\n"
    )
    _patch_narrator_llm(monkeypatch, content=bad_content)

    asyncio.run(scan_module.run_scan(workspace_path=workspace, no_file_map=True))

    entity_pages = list((wiki / "entities").glob("*.md"))
    assert len(entity_pages) > 0
    for page in entity_pages:
        post = frontmatter.load(page)
        assert post.metadata.get("uri") != "HACKED", (
            f"Frontmatter URI was contaminated in {page.name}"
        )
        assert post.metadata.get("kind") != "HACKED", (
            f"Frontmatter kind was contaminated in {page.name}"
        )
        # Real URIs from the seeded graph start with one of the admitted prefixes.
        uri = post.metadata.get("uri", "")
        assert uri.startswith(
            ("pkg:", "domain:", "repo:", "test_suite:", "dependency:", "plugin:")
        ), f"Page {page.name} has unexpected URI: {uri!r}"


def test_step_11_legacy_stale_tag_still_runs_for_non_entity_deletions(
    fixture_wiki_with_graph, monkeypatch
):
    """Phase 45 D-09: Step 11's stale-tag loop continues to fire for any
    non-entity legacy-layout deletion (no behavior change)."""
    wiki, workspace = fixture_wiki_with_graph

    # Pre-seed a legacy-layout vault page with no matching graph node.
    legacy_dir = wiki / "packages" / "legacy_only"
    legacy_dir.mkdir(parents=True, exist_ok=True)
    (legacy_dir / "legacy_only.md").write_text(
        "---\ntitle: legacy_only\ncategory: package\n---\n\nbody\n",
        encoding="utf-8",
    )

    _patch_narrator_llm(monkeypatch)

    # Force compute_diff to mark `legacy_only` as deleted so Step 11 fires.
    real_compute_diff = scan_module.compute_diff

    def fake_compute_diff(workspaces, existing):
        diff = real_compute_diff(workspaces, existing)
        diff["deleted"] = list(set(diff["deleted"]) | {"legacy_only"})
        return diff

    monkeypatch.setattr(scan_module, "compute_diff", fake_compute_diff)

    asyncio.run(scan_module.run_scan(workspace_path=workspace, no_file_map=True))

    text = (legacy_dir / "legacy_only.md").read_text(encoding="utf-8")
    assert "stale: true" in text, (
        f"Expected stale-tag on legacy page; got:\n{text}"
    )


def test_scan_result_populated_with_entity_fields(fixture_wiki_with_graph, monkeypatch):
    """ScanResult.entities_created / entities_narrated reflect Step 9a + 9b outputs."""
    wiki, workspace = fixture_wiki_with_graph
    _patch_narrator_llm(monkeypatch)

    result = asyncio.run(scan_module.run_scan(workspace_path=workspace, no_file_map=True))

    assert isinstance(result.entities_created, list)
    assert isinstance(result.entities_updated, list)
    assert isinstance(result.entities_deleted, list)
    assert isinstance(result.entities_narrated, list)
    assert isinstance(result.entity_errors, list)
    # First scan against a fresh vault creates entity pages; they're all narrated.
    assert len(result.entities_created) > 0
    assert sorted(result.entities_narrated) == sorted(result.entities_created), (
        "Every created entity should have been narrated on first scan"
    )
