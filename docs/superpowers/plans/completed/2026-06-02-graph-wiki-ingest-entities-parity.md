# graph-wiki ingest → `entities/` parity (Slice 4) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring `ingest` onto the single-`entities/`-folder wiki model on both the `gw` core (`graph_wiki_core.run_ingest_source`) and the `graph-wiki` Claude Code plugin — ingest writes durable forward-links (`entity_uri:` + `[[entities/...]]`) into preserved pages, and the scanner derives a `## Referenced in wiki` backlink section onto entity pages.

**Architecture:** Ingest never edits `entities/` pages. The core principle (spec §"Core principle"): *ingest writes forward-links into preserved categories; the scanner derives backlinks*. Three slices of change — (A) shared routing rules so `run_ingest_source` stops writing `packages/`, (B) a pure-Python scanner pass that regenerates `## Referenced in wiki` on every entity page, (C) a Bedrock-free prep `main()` that fixes the plugin's broken shim plus doc rewrites.

**Tech Stack:** Python 3.11+, `uv` workspace. Packages touched: `wiki-io` (new `entity_lookup.py`, new `backlink_index.py`, prep `main()` in `ingest_source.py`, entity + source templates), `graph-wiki-core` (`commands/ingest.py`, `commands/scan.py`, `prompts/ingestor.py`), and the `graph-wiki` plugin (shim already correct once `main()` exists; agents/commands/references docs). Tests: `pytest` + `pytest-asyncio`.

---

## File Structure

**New files:**
- `packages/wiki-io/src/wiki_io/entity_lookup.py` — Bedrock-free graph lookups (`lookup_entity_by_path`, `lookup_entity_by_name`, `entity_filename_for_uri`, `ENTITY_KINDS`) shared by `run_ingest_source` and the plugin prep. Moves the lookups out of `commands/ingest.py` (which imports `model_adapter`).
- `packages/wiki-io/src/wiki_io/backlink_index.py` — `inject_referenced_in_wiki` (single-H2-region rewriter, sibling of `inject_narrative`) + `regenerate_referenced_in_wiki` (walks preserved pages, rebuilds each entity's backlink section).
- `packages/wiki-io/tests/test_entity_lookup.py` — unit tests for the shared lookups + filename mapping.
- `packages/wiki-io/tests/test_backlink_index.py` — unit tests for inject + regenerate (idempotent, multi-entity, scanner-owned preservation).
- `packages/wiki-io/tests/test_ingest_source_prep.py` — prep `main()` JSON-brief test with `model_adapter`/`subagent_runtime` un-importable.

**Modified files:**
- `packages/wiki-io/src/wiki_io/ingest_source.py` — add prep `main()`.
- `packages/wiki-io/src/wiki_io/assets/page-templates/entity-*.md` (7 files) — add `## Referenced in wiki`.
- `packages/wiki-io/src/wiki_io/assets/page-templates/source.md` — `## Touches` → `[[entities/...]]`; add `entity_uri:` frontmatter.
- `packages/wiki-io/pyproject.toml` — declare `graph-io` dependency (made first-class by `entity_lookup.py`).
- `packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py` — drop `package` route, decouple entity match from slug/route, inject `[[entities/...]]`, import shared lookups.
- `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py` — wire in `regenerate_referenced_in_wiki`.
- `packages/graph-wiki-core/src/graph_wiki_core/prompts/ingestor.py` — drop `package` from the page-type menu; reference entities via `[[entities/...]]`.
- `packages/graph-wiki-core/tests/unit/test_commands_ingest.py` — update two behavior tests for decoupled routing.
- `plugins/graph-wiki/agents/ingestor.md`, `plugins/graph-wiki/commands/ingest.md`, `plugins/graph-wiki/skills/graph-wiki/references/ingest-workflow.md` — rewrite to the entities/ link model.

**Unchanged (verified):** `plugins/graph-wiki/skills/graph-wiki/scripts/ingest_source.py` (the shim's top-level `from wiki_io.ingest_source import main` starts working once `main()` exists; argv contract unchanged). `short_filename`, `SCANNER_OWNED_KEYS`, `ADMITTED_KINDS`, `write_entities`, `run_ingest_work_item`.

---

## Task 1: Shared Bedrock-free entity lookups (`wiki_io.entity_lookup`)

Moves the graph lookups out of `graph_wiki_core.commands.ingest` (which imports `model_adapter`/`subagent_runtime` at module top) into a Bedrock-free home, and adds `entity_filename_for_uri` — the shared URI→entity-filename mapping that uses the **same** rule the scanner uses (`short_filename`), replacing the legacy `slug_from_uri` for entity links.

**Files:**
- Create: `packages/wiki-io/src/wiki_io/entity_lookup.py`
- Modify: `packages/wiki-io/pyproject.toml`
- Test: `packages/wiki-io/tests/test_entity_lookup.py`

- [ ] **Step 1: Declare the `graph-io` dependency on `wiki-io`**

`entity_lookup.py` imports `graph_io` (transitively via `entity_writer`, and the prep imports `graph_io.store` directly). `entity_writer.py` already imports `graph_io` undeclared; make it first-class so plugin installs don't break.

In `packages/wiki-io/pyproject.toml`, change the `dependencies` list from:

```toml
dependencies = [
    "python-frontmatter>=1.1",
    "boto3>=1.38",
    "workspace-io",
]
```

to:

```toml
dependencies = [
    "python-frontmatter>=1.1",
    "boto3>=1.38",
    "workspace-io",
    "graph-io",
]
```

Then add the workspace-source mapping if it is not already present. Check the bottom of the file:

Run: `grep -n "tool.uv.sources" packages/wiki-io/pyproject.toml`

If `[tool.uv.sources]` exists, ensure it contains `graph-io = { workspace = true }`; if the table does not exist, append:

```toml
[tool.uv.sources]
graph-io = { workspace = true }
workspace-io = { workspace = true }
```

(Match the exact form already used for `workspace-io` — read the file first and mirror it. If `workspace-io` already has a sources entry, only add the `graph-io` line.)

- [ ] **Step 2: Sync the workspace**

Run: `uv sync`
Expected: completes without resolution errors; `graph-io` resolves to the workspace member.

- [ ] **Step 3: Write the failing test for `entity_lookup`**

Create `packages/wiki-io/tests/test_entity_lookup.py`:

```python
from __future__ import annotations

"""Unit tests for wiki_io.entity_lookup — Bedrock-free graph lookups + the
URI→entity-filename mapping shared by run_ingest_source and the plugin prep
(Slice 4)."""

from pathlib import Path

import pytest


def _seed_db(workspace: Path, packages, extra_nodes=None) -> Path:
    """Create <workspace>/.graph/code.db with package + optional extra nodes.

    `packages`: list of (name, uri, rel_file_path | None).
    `extra_nodes`: list of (kind, name, path | None, uri | None).
    URI is written to the dedicated nodes.uri column.
    """
    from graph_io.store import connect
    from workspace_io.paths import graph_dir

    db = graph_dir(workspace) / "code.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(db, create=True)
    try:
        nid = 1
        for name, uri, rel_path in packages:
            pkg_id = nid
            nid += 1
            conn.execute(
                "INSERT INTO nodes (id, kind, name, path, line, attrs_json, uri) "
                "VALUES (?, 'package', ?, NULL, NULL, NULL, ?)",
                (pkg_id, name, uri),
            )
            if rel_path is not None:
                file_id = nid
                nid += 1
                conn.execute(
                    "INSERT INTO nodes (id, kind, name, path, line, attrs_json, uri) "
                    "VALUES (?, 'file', ?, ?, NULL, NULL, NULL)",
                    (file_id, Path(rel_path).name, rel_path),
                )
                conn.execute(
                    "INSERT INTO edges (src, dst, kind, attrs_json) "
                    "VALUES (?, ?, 'contains', NULL)",
                    (pkg_id, file_id),
                )
        for kind, name, path, uri in extra_nodes or []:
            conn.execute(
                "INSERT INTO nodes (id, kind, name, path, line, attrs_json, uri) "
                "VALUES (?, ?, ?, ?, NULL, NULL, ?)",
                (nid, kind, name, path, uri),
            )
            nid += 1
    finally:
        conn.close()
    return db


def test_lookup_entity_by_path_returns_uri_and_name(tmp_path: Path) -> None:
    from graph_io.store import read_only_connect
    from wiki_io.entity_lookup import lookup_entity_by_path

    rel = "packages/graph-io/src/graph_io/store.py"
    db = _seed_db(tmp_path, [("graph-io", "pkg:o/r/graph-io", rel)])
    conn = read_only_connect(db)
    try:
        result = lookup_entity_by_path(conn, tmp_path, tmp_path / rel)
    finally:
        conn.close()
    assert result == ("pkg:o/r/graph-io", "graph-io")


def test_lookup_entity_by_name_unique_match(tmp_path: Path) -> None:
    from graph_io.store import read_only_connect
    from wiki_io.entity_lookup import lookup_entity_by_name

    db = _seed_db(tmp_path, [("graph-io", "pkg:o/r/graph-io", None)])
    conn = read_only_connect(db)
    try:
        result = lookup_entity_by_name(conn, "graph-io")
    finally:
        conn.close()
    assert result == ("pkg:o/r/graph-io", "graph-io")


def test_lookup_entity_by_name_multi_match_returns_none(tmp_path: Path) -> None:
    from graph_io.store import read_only_connect
    from wiki_io.entity_lookup import lookup_entity_by_name

    db = _seed_db(
        tmp_path,
        [],
        extra_nodes=[
            ("class", "Helper", "a/helper.py", "cls:o/a/Helper"),
            ("class", "Helper", "b/helper.py", "cls:o/b/Helper"),
        ],
    )
    conn = read_only_connect(db)
    try:
        result = lookup_entity_by_name(conn, "Helper")
    finally:
        conn.close()
    assert result is None


def test_entity_filename_for_uri_package_matches_short_filename() -> None:
    from wiki_io.entity_lookup import entity_filename_for_uri
    from wiki_io.entity_writer import short_filename

    uri = "pkg:o/r/graph-io"
    assert entity_filename_for_uri(uri) == short_filename(uri, frozenset())
    assert entity_filename_for_uri(uri) == "pkg_graph-io"


def test_entity_filename_for_uri_non_entity_prefix_returns_none() -> None:
    from wiki_io.entity_lookup import entity_filename_for_uri

    # cls:/fn:/method: have no entity page → no wikilink target.
    assert entity_filename_for_uri("cls:subagent_runtime.pool.SubagentPool") is None
    assert entity_filename_for_uri("") is None
```

- [ ] **Step 4: Run the test to verify it fails**

Run: `uv run pytest packages/wiki-io/tests/test_entity_lookup.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'wiki_io.entity_lookup'`.

- [ ] **Step 5: Create `wiki_io/entity_lookup.py`**

Create `packages/wiki-io/src/wiki_io/entity_lookup.py`:

```python
from __future__ import annotations

"""Bedrock-free graph lookups shared by ingest — core (`run_ingest_source`)
and the plugin's Claude-branch prep.

Slice 4 moved these out of `graph_wiki_core.commands.ingest` (which imports
`model_adapter` / `subagent_runtime` at module top) so the prep can resolve the
entity a source belongs to without dragging in the Bedrock stack.

`entity_filename_for_uri` is the URI→entity-filename mapping that uses the SAME
rule the scanner uses (`wiki_io.entity_writer.short_filename`), so an ingest
`[[entities/<stem>]]` wikilink resolves to the file `write_entities` produced —
replacing the legacy `slug_from_uri` for entity links.
"""

import sys
from pathlib import Path

from wiki_io.entity_writer import (
    ADMITTED_KINDS,
    _compute_collision_set,
    _kind_list_fns,
    short_filename,
)

# Entity-kind nodes worth a name-fallback match (file names are noisy).
# Mirrors the former `_ENTITY_KINDS` in graph_wiki_core.commands.ingest.
ENTITY_KINDS: frozenset[str] = frozenset(
    {"package", "class", "function", "method", "domain"}
)


def lookup_entity_by_path(conn, repo_root: Path, source_path: Path):
    """Return (uri, name) for the package CONTAINING the source file, or None.

    Resolves source_path relative to repo_root (POSIX-style), then joins
    nodes(file) -> edges(contains) -> nodes(package). Reads URI from the
    dedicated `nodes.uri` column. Returns None when source_path is outside
    repo_root or no package contains it.
    """
    try:
        rel = source_path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return None
    row = conn.execute(
        "SELECT p.name, p.uri FROM nodes f "
        "JOIN edges e ON e.dst = f.id AND e.kind='contains' "
        "JOIN nodes p ON e.src = p.id "
        "WHERE f.kind='file' AND f.path = ? AND p.kind='package' "
        "LIMIT 1",
        (rel,),
    ).fetchone()
    if row is None:
        return None
    name, uri = row
    if not uri:
        return None
    return uri, name


def lookup_entity_by_name(conn, name: str):
    """Return (uri, name) for the unique entity-kind match by name, or None.

    When more than one entity-kind node shares the name, emit one stderr
    warning and return None (fall back to the no-match path).
    """
    if not name:
        return None
    placeholders = ",".join("?" for _ in ENTITY_KINDS)
    sql = (
        f"SELECT name, uri, kind FROM nodes "
        f"WHERE name = ? AND kind IN ({placeholders}) AND uri IS NOT NULL"
    )
    rows = conn.execute(sql, [name, *sorted(ENTITY_KINDS)]).fetchall()
    if not rows:
        return None
    if len(rows) > 1:
        uris = [r[1] for r in rows]
        sys.stderr.write(
            f"[ingest: name {name!r} matches multiple graph nodes "
            f"({', '.join(uris)}); falling back to LLM-guessed slug]\n"
        )
        return None
    matched_name, matched_uri, _kind = rows[0]
    return matched_uri, matched_name


def entity_filename_for_uri(uri: str, conn=None) -> str | None:
    """Return the scanner's on-disk entity filename stem for a graph URI, or
    None when the URI maps to no admitted entity page.

    Bedrock-free. Mirrors `write_entities` / `short_filename` so an ingest
    `[[entities/<stem>]]` wikilink resolves to a real page. When `conn` is
    given, the exact collision set is computed so colliding stems carry the
    same `__<hex>` suffix the scanner uses; otherwise an empty collision set is
    assumed (correct for the no-collision common case).

    Returns None for URI prefixes with no entity page (cls:/fn:/method:),
    since `short_filename` raises ValueError on those — ingest only matches
    package/domain entities for linkable targets.
    """
    if not uri:
        return None
    collision_set: frozenset[str] = frozenset()
    if conn is not None:
        try:
            collision_set = _compute_collision_set(
                conn, ADMITTED_KINDS, _kind_list_fns()
            )
        except Exception:  # noqa: BLE001 — collision precompute is best-effort
            collision_set = frozenset()
    try:
        return short_filename(uri, collision_set)
    except ValueError:
        return None
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `uv run pytest packages/wiki-io/tests/test_entity_lookup.py -v`
Expected: PASS (5 tests).

- [ ] **Step 7: Commit**

```bash
git add packages/wiki-io/src/wiki_io/entity_lookup.py packages/wiki-io/tests/test_entity_lookup.py packages/wiki-io/pyproject.toml uv.lock
git commit -m "feat(wiki-io): shared Bedrock-free entity_lookup (lookups + entity_filename_for_uri)"
```

---

## Task 2: Retarget `run_ingest_source` — drop `packages/`, decouple match from slug, inject `[[entities/...]]`

`run_ingest_source` must stop writing the legacy `packages/` layout, stop forcing the slug from the URI, and instead write the matched entity as a durable `[[entities/<stem>]]` forward-link (the scanner derives the backlink in Task 5). The `entity_uri:` frontmatter anchor is unchanged.

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py`
- Test: `packages/graph-wiki-core/tests/unit/test_commands_ingest.py`

- [ ] **Step 1: Write the failing core routing test**

Add to `packages/graph-wiki-core/tests/unit/test_commands_ingest.py` (append after the existing `test_run_ingest_source_path_match_overrides_slug` block, near line 743):

```python
@pytest.mark.asyncio
async def test_run_ingest_source_path_match_links_entity_never_packages(
    tmp_path: Path,
) -> None:
    """Slice 4: a path-matched package routes to sources/ (never packages/),
    sets entity_uri, and embeds a [[entities/pkg_<name>]] wikilink whose target
    equals short_filename for the URI. The slug is NOT forced from the URI."""
    from wiki_io.entity_writer import short_filename

    from graph_wiki_core.commands.ingest import run_ingest_source

    workspace, wiki, repo = _build_workspace_with_repo(tmp_path)
    rel_path = "packages/graph-io/src/graph_io/store.py"
    source_file = workspace / rel_path
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_text("# store\n\nBody.", encoding="utf-8")

    canonical_uri = "pkg:agent-research/agent-research/graph-io"
    _seed_graph_db_for_ingest_tests(
        workspace, packages=[("graph-io", canonical_uri, rel_path)]
    )

    # LLM picks page_type=source with a clean slug; entity match must NOT
    # override it (decoupled).
    fake_llm_response = _FM_TEMPLATE.format(
        title="Store",
        category="source",
        page_type="source",
        slug="2026-06-store",
    )

    with (
        patch("graph_wiki_core.commands.ingest.resolve_wiki_and_repo") as mock_resolve,
        patch("graph_wiki_core.commands.ingest.make_llm") as mock_make_llm,
        patch("graph_wiki_core.commands.ingest.update_index"),
        patch("graph_wiki_core.commands.ingest.append_log"),
    ):
        mock_resolve.return_value = (wiki, repo)
        fake_llm = MagicMock()
        fake_llm.ainvoke = AsyncMock(return_value=MagicMock(content=fake_llm_response))
        mock_make_llm.return_value = fake_llm

        result = await run_ingest_source(source_file, workspace)

    # Never the legacy packages/ folder.
    assert not (wiki / "packages").exists()
    stem = short_filename(canonical_uri, frozenset())  # "pkg_graph-io"
    expected_page = wiki / "sources" / "2026-06-store.md"
    assert expected_page.exists(), f"expected page at {expected_page}"
    body = expected_page.read_text(encoding="utf-8")
    assert f"entity_uri: {canonical_uri}" in body
    assert f"[[entities/{stem}]]" in body
    assert result.page_type == "source"
    assert result.slug == "2026-06-store"   # LLM slug preserved, not URI tail
    assert result.entity_uri == canonical_uri
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest "packages/graph-wiki-core/tests/unit/test_commands_ingest.py::test_run_ingest_source_path_match_links_entity_never_packages" -v`
Expected: FAIL — page lands in `packages/graph-io.md` (old routing) and body has no `[[entities/pkg_graph-io]]` link.

- [ ] **Step 3: Drop `package` from the route table and add the touch-link helper**

In `packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py`:

Change `_PAGE_TYPE_DIRS` (currently at line 123):

```python
_PAGE_TYPE_DIRS: dict[str, str] = {
    "package": "packages",
    "concept": "concepts",
    "adr": "adrs",
    "source": "sources",
}
```

to:

```python
# Slice 4: `package` is no longer an ingest target — entity pages are
# scanner-owned and live under entities/. Valid ingest page_types collapse to
# source | concept | adr (all ingest-owned, preserved dirs). The default
# fallback (page_type not in _PAGE_TYPE_DIRS -> concept) is unchanged.
_PAGE_TYPE_DIRS: dict[str, str] = {
    "concept": "concepts",
    "adr": "adrs",
    "source": "sources",
}
```

- [ ] **Step 4: Replace the in-module lookups with the shared `wiki_io` ones**

Delete the now-duplicated `_ENTITY_KINDS` constant (line 132), `_lookup_entity_by_path` (lines 135–163), and `_lookup_entity_by_name` (lines 166–193) from `commands/ingest.py`.

Remove the now-unused import (line 46):

```python
from graph_wiki_core.uri_slug import slug_from_uri
```

Add to the import block (near line 36, with the other `wiki_io` imports):

```python
from wiki_io.entity_lookup import (
    entity_filename_for_uri,
    lookup_entity_by_name,
    lookup_entity_by_path,
)
```

Add the touch-link regex near the other module-level regexes (e.g. just after `_WIKILINK_RE` at line 316):

```python
# Slice 4: anchor for the matched entity's durable forward-link. Inserted under
# the body's `## Touches` section (created if absent). Idempotent.
_TOUCHES_HEADING_RE = re.compile(r"^## Touches[ \t]*\n", re.MULTILINE)


def _ensure_entity_touch_link(text: str, stem: str) -> str:
    """Guarantee a `[[entities/<stem>]]` wikilink is present in the body.

    This is the durable forward-anchor the scanner reads to derive the entity's
    `## Referenced in wiki` backlink, so it must survive `_resolve_wikilinks`
    stripping — call this LAST, after wikilink resolution. Idempotent: inserts
    a bullet under an existing `## Touches` heading, else appends the section.
    """
    link = f"[[entities/{stem}]]"
    if link in text:
        return text
    m = _TOUCHES_HEADING_RE.search(text)
    if m is not None:
        insert_at = m.end()
        return text[:insert_at] + f"- {link}\n" + text[insert_at:]
    sep = "" if text.endswith("\n") else "\n"
    return f"{text}{sep}\n## Touches\n- {link}\n"
```

- [ ] **Step 5: Update the entity-match call sites + remove slug forcing**

In `run_ingest_source`, the canonical-match block (currently lines 599–604) reads:

```python
        canonical: tuple[str, str] | None = _lookup_entity_by_path(
            conn, repo, source_path
        )
        if canonical is None:
            canonical = _lookup_entity_by_name(conn, title_guess)
        canonical_uri: str | None = canonical[0] if canonical else None
```

Replace with (use the imported names; add the entity-stem computation):

```python
        canonical: tuple[str, str] | None = lookup_entity_by_path(
            conn, repo, source_path
        )
        if canonical is None:
            canonical = lookup_entity_by_name(conn, title_guess)
        canonical_uri: str | None = canonical[0] if canonical else None
        # Slice 4: the matched entity drives a [[entities/<stem>]] forward-link
        # whose target equals the scanner's on-disk filename. None when the
        # match has no entity page (cls:/fn:/method:) — no link is written.
        entity_stem: str | None = (
            entity_filename_for_uri(canonical_uri, conn) if canonical_uri else None
        )
```

Then DELETE the D-04 slug-forcing block (currently lines 664–666):

```python
        # D-04: graph is ground truth for slugs of entity-backed pages.
        if canonical_uri is not None:
            target_slug = slug_from_uri(canonical_uri)
```

- [ ] **Step 6: Inject the entity touch-link as the final write step**

In `run_ingest_source`, the write block (currently lines 684–690) reads:

```python
        target_path.write_text(llm_output, encoding="utf-8")
        # Plan 06-14 / UAT G4: strip wikilinks the LLM fabricated for pages
        # that do not exist in the vault. Two writes is acceptable — vaults
        # are local-disk and writes are <1ms.
        resolved_output, stripped_wikilinks = _resolve_wikilinks(llm_output, wiki)
        if stripped_wikilinks:
            target_path.write_text(resolved_output, encoding="utf-8")
```

Replace with:

```python
        target_path.write_text(llm_output, encoding="utf-8")
        # Plan 06-14 / UAT G4: strip wikilinks the LLM fabricated for pages
        # that do not exist in the vault. Two writes is acceptable — vaults
        # are local-disk and writes are <1ms.
        resolved_output, stripped_wikilinks = _resolve_wikilinks(llm_output, wiki)
        current_output = resolved_output if stripped_wikilinks else llm_output
        if stripped_wikilinks:
            target_path.write_text(resolved_output, encoding="utf-8")
        # Slice 4: ensure the matched entity's forward-link is present. Runs
        # AFTER _resolve_wikilinks so it is never stripped (the entity page may
        # not exist on disk yet at ingest time — the scanner backfills it).
        if entity_stem:
            linked_output = _ensure_entity_touch_link(current_output, entity_stem)
            if linked_output != current_output:
                target_path.write_text(linked_output, encoding="utf-8")
```

- [ ] **Step 7: Update the prompt-builder page-type list + the IngestResult docstring**

In `build_ingest_source_prompt` (lines 515–516), change:

```python
        f"Choose the most appropriate page_type (source, package, concept, or adr) "
        f"and a target_slug based on the content."
```

to:

```python
        f"Choose the most appropriate page_type (source, concept, or adr) "
        f"and a target_slug based on the content. To associate this source with "
        f"a code entity, reference it with a [[entities/...]] wikilink in the "
        f"body — do not create a package page."
```

In the `IngestResult.page_type` docstring (lines 96–100), change `source, package, concept, or adr` to `source, concept, or adr`.

- [ ] **Step 8: Run the new routing test**

Run: `uv run pytest "packages/graph-wiki-core/tests/unit/test_commands_ingest.py::test_run_ingest_source_path_match_links_entity_never_packages" -v`
Expected: PASS.

- [ ] **Step 9: Update the two now-obsolete behavior tests**

The decoupling breaks `test_run_ingest_source_path_match_overrides_slug` and `test_run_ingest_source_name_fallback_overrides_slug` (they assert the old `packages/` route and URI-forced slug).

(a) **Delete** `test_run_ingest_source_path_match_overrides_slug` (lines 698–742) entirely — its case (path match) is now covered by Step 1's `test_run_ingest_source_path_match_links_entity_never_packages`.

(b) **Replace** `test_run_ingest_source_name_fallback_overrides_slug` (lines 750–800) with the new **no-link, uri-only** name-match test below:

```python
@pytest.mark.asyncio
async def test_run_ingest_source_name_match_sets_uri_without_entity_link(
    tmp_path: Path,
) -> None:
    """Slice 4: a name-matched class (cls: URI, no entity page) sets entity_uri
    but writes NO [[entities/...]] link and does NOT force the slug."""
    from graph_wiki_core.commands.ingest import run_ingest_source

    workspace, wiki, repo = _build_workspace_with_repo(tmp_path)
    source_file = workspace / "random" / "src.md"
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_text("# SubagentPool\n\nBody.", encoding="utf-8")

    canonical_uri = "cls:subagent_runtime.pool.SubagentPool"
    _seed_graph_db_for_ingest_tests(
        workspace,
        packages=[],
        extra_nodes=[("class", "SubagentPool", None, canonical_uri)],
    )

    fake_llm_response = _FM_TEMPLATE.format(
        title="SubagentPool",
        category="concept",
        page_type="concept",
        slug="some-other-thing",
    )

    with (
        patch("graph_wiki_core.commands.ingest.resolve_wiki_and_repo") as mock_resolve,
        patch("graph_wiki_core.commands.ingest.make_llm") as mock_make_llm,
        patch("graph_wiki_core.commands.ingest.update_index"),
        patch("graph_wiki_core.commands.ingest.append_log"),
    ):
        mock_resolve.return_value = (wiki, repo)
        fake_llm = MagicMock()
        fake_llm.ainvoke = AsyncMock(return_value=MagicMock(content=fake_llm_response))
        mock_make_llm.return_value = fake_llm

        result = await run_ingest_source(source_file, workspace)

    assert result.entity_uri == canonical_uri
    assert result.slug == "some-other-thing"  # LLM slug preserved (no forcing)
    written = (wiki / "concepts" / "some-other-thing.md").read_text(encoding="utf-8")
    assert f"entity_uri: {canonical_uri}" in written
    assert "[[entities/" not in written  # cls: has no entity page → no link
```

Delete the old `test_run_ingest_source_path_match_overrides_slug` function body (its case is now covered by Step 1's test). Leave any other tests in the file unchanged.

- [ ] **Step 10: Run the full ingest test module**

Run: `uv run pytest packages/graph-wiki-core/tests/unit/test_commands_ingest.py -v`
Expected: PASS (all tests green; no references to a `packages/` route or `slug_from_uri` remain).

- [ ] **Step 11: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py packages/graph-wiki-core/tests/unit/test_commands_ingest.py
git commit -m "feat(ingest): route to sources/concepts/adrs only; link matched entity via [[entities/...]]"
```

---

## Task 3: Ingestor prompt — drop `package`, reference entities by wikilink

The ingestor system prompt still offers `page_type: package -> packages/`. Remove it and instruct the model to reference code entities via `[[entities/...]]`.

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/prompts/ingestor.py`
- Test: `packages/graph-wiki-core/tests/prompts/` (add a focused assertion)

- [ ] **Step 1: Write the failing prompt test**

Run: `ls packages/graph-wiki-core/tests/prompts/` to find the ingestor prompt test file (likely `test_ingestor.py` or similar). If a file testing `build_ingestor_system` exists, add to it; otherwise create `packages/graph-wiki-core/tests/prompts/test_ingestor_prompt.py`:

```python
from __future__ import annotations

from graph_wiki_core.prompts.ingestor import build_ingestor_system


def test_ingestor_prompt_has_no_package_page_type() -> None:
    """Slice 4: the ingestor must not offer a package page_type or packages/ route."""
    system = build_ingestor_system()
    assert "page_type: package" not in system
    assert "-> `packages/`" not in system
    # It must instead steer the model to entity wikilinks.
    assert "[[entities/" in system
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest packages/graph-wiki-core/tests/prompts/test_ingestor_prompt.py -v`
Expected: FAIL — `page_type: package` still present.

- [ ] **Step 3: Rewrite the `_PAGE_TYPE_ROUTING` fragment**

In `packages/graph-wiki-core/src/graph_wiki_core/prompts/ingestor.py`, replace `_PAGE_TYPE_ROUTING` (lines 34–43):

```python
_PAGE_TYPE_ROUTING = (
    "## Page-type routing\n\n"
    "Choose exactly one `page_type`. The on-disk destination is determined by `page_type`:\n\n"
    "- `page_type: source` -> `sources/` (specs, PRs, articles, transcripts, in-repo docs)\n"
    "- `page_type: package` -> `packages/` (a workspace member with a manifest)\n"
    "- `page_type: concept` -> `concepts/` (cross-cutting technical idea, comparison page)\n"
    "- `page_type: adr` -> `adrs/` (dated decision record)\n\n"
    "`category` should agree with `page_type` (`source` -> `source`, `package` -> `package`, etc.).\n"
    "`update_index()` and `append_log()` run automatically — omit those steps."
)
```

with:

```python
_PAGE_TYPE_ROUTING = (
    "## Page-type routing\n\n"
    "Choose exactly one `page_type`. The on-disk destination is determined by `page_type`:\n\n"
    "- `page_type: source` -> `sources/` (specs, PRs, articles, transcripts, in-repo docs)\n"
    "- `page_type: concept` -> `concepts/` (cross-cutting technical idea, comparison page)\n"
    "- `page_type: adr` -> `adrs/` (dated decision record)\n\n"
    "Do NOT author a package page. Code entities (packages, apps, domains, "
    "dependencies, test suites) are scanner-owned and live under `entities/`. "
    "To associate this source with a code entity, reference it from the body with "
    "a `[[entities/<prefix>_<name>]]` wikilink (e.g. `[[entities/pkg_graph-io]]`) "
    "under a `## Touches` section — the scanner derives the backlink onto the "
    "entity page. Never write into `entities/` pages.\n\n"
    "`category` should agree with `page_type` (`source` -> `source`, "
    "`concept` -> `concept`, `adr` -> `adr`).\n"
    "`update_index()` and `append_log()` run automatically — omit those steps."
)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest packages/graph-wiki-core/tests/prompts/test_ingestor_prompt.py -v`
Expected: PASS.

- [ ] **Step 5: Run the prompt test module to catch snapshot drift**

Run: `uv run pytest packages/graph-wiki-core/tests/prompts/ -v`
Expected: PASS. If a syrupy snapshot of the ingestor prompt exists and now differs, review the diff to confirm it only drops `package`/adds the entities guidance, then run `uv run pytest packages/graph-wiki-core/tests/prompts/ --snapshot-update` and re-run to confirm green.

- [ ] **Step 6: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/prompts/ingestor.py packages/graph-wiki-core/tests/prompts/
git commit -m "feat(ingestor-prompt): drop package page_type; reference code entities via [[entities/...]]"
```

---

## Task 4: Add `## Referenced in wiki` to the 7 entity templates

Every admitted entity page gets a scanner-owned `## Referenced in wiki` section with a placeholder mirroring `## Narrative`. Placement: immediately after `## Narrative` (so both scanner-owned regions sit at the top, before human-authored sections).

**Files:**
- Modify: `packages/wiki-io/src/wiki_io/assets/page-templates/entity-package.md`, `entity-app.md`, `entity-domain.md`, `entity-repository.md`, `entity-dependency.md`, `entity-test-suite.md`, `entity-agent-plugin.md`
- Test: `packages/wiki-io/tests/test_entity_templates.py`

- [ ] **Step 1: Write the failing template test**

Add to `packages/wiki-io/tests/test_entity_templates.py`:

```python
def test_all_entity_templates_have_referenced_in_wiki_section() -> None:
    """Slice 4: every entity template carries the scanner-owned
    `## Referenced in wiki` section with a placeholder."""
    from importlib.resources import files

    tdir = files("wiki_io.assets.page-templates")
    kinds = [
        "package", "app", "domain", "repository",
        "dependency", "test-suite", "agent-plugin",
    ]
    for kind in kinds:
        body = (tdir / f"entity-{kind}.md").read_text(encoding="utf-8")
        assert "## Referenced in wiki" in body, f"missing in entity-{kind}.md"
        # Placeholder mirrors the ## Narrative convention.
        idx = body.index("## Referenced in wiki")
        after = body[idx:]
        assert "_(scanner will populate on next scan)_" in after.split("\n\n", 1)[0] \
            or "_(scanner will populate" in after[:120], f"no placeholder in entity-{kind}.md"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest packages/wiki-io/tests/test_entity_templates.py -k referenced_in_wiki -v`
Expected: FAIL — `## Referenced in wiki` not found.

- [ ] **Step 3: Insert the section in each template**

For each of the 7 `entity-*.md` templates, insert these three lines immediately AFTER the `## Narrative` placeholder block and before the next section. The `## Narrative` block in every template is exactly:

```markdown
## Narrative
_(scanner will populate on next scan)_
```

Insert directly after it:

```markdown

## Referenced in wiki
_(scanner will populate on next scan)_
```

Apply to all 7: `entity-package.md`, `entity-app.md`, `entity-domain.md`, `entity-repository.md`, `entity-dependency.md`, `entity-test-suite.md`, `entity-agent-plugin.md`.

For example, in `entity-package.md` the region becomes:

```markdown
# {{package_name}}

## Narrative
_(scanner will populate on next scan)_

## Referenced in wiki
_(scanner will populate on next scan)_

## Purpose
> TODO: <One paragraph: what this package does, who uses it, why it exists.>
```

(In `entity-repository.md` the next section is `## Overview`; in `entity-agent-plugin.md` it is `## Purpose`; in `entity-domain.md` it is `## Scope`. Insert in the same position — right after the Narrative placeholder — in each.)

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest packages/wiki-io/tests/test_entity_templates.py -k referenced_in_wiki -v`
Expected: PASS.

- [ ] **Step 5: Run the full entity-templates module (catch structural assertions)**

Run: `uv run pytest packages/wiki-io/tests/test_entity_templates.py -v`
Expected: PASS. If a test asserts an exact section list or section count per template, update that expectation to include `## Referenced in wiki`.

- [ ] **Step 6: Commit**

```bash
git add packages/wiki-io/src/wiki_io/assets/page-templates/entity-*.md packages/wiki-io/tests/test_entity_templates.py
git commit -m "feat(templates): add scanner-owned ## Referenced in wiki to all 7 entity templates"
```

---

## Task 5: Scanner backlink regeneration (`wiki_io.backlink_index`)

A pure-Python pass that rebuilds each entity page's `## Referenced in wiki` from the `[[entities/<stem>]]` wikilinks found across preserved pages. Mirrors `inject_narrative`'s single-H2-region rewrite. No Bedrock.

**Files:**
- Create: `packages/wiki-io/src/wiki_io/backlink_index.py`
- Test: `packages/wiki-io/tests/test_backlink_index.py`

- [ ] **Step 1: Write the failing tests**

Create `packages/wiki-io/tests/test_backlink_index.py`:

```python
from __future__ import annotations

"""Unit tests for wiki_io.backlink_index — scanner-derived `## Referenced in
wiki` regeneration (Slice 4). Pure Python, no Bedrock."""

from pathlib import Path


def _entity_page(entities: Path, stem: str, extra_h2: str = "") -> Path:
    entities.mkdir(parents=True, exist_ok=True)
    p = entities / f"{stem}.md"
    body = (
        "---\n"
        f"uri: pkg:o/r/{stem}\n"
        "kind: package\n"
        "---\n\n"
        f"# {stem}\n\n"
        "## Narrative\n"
        "Some prose.\n\n"
        "## Referenced in wiki\n"
        "_(scanner will populate on next scan)_\n\n"
        f"{extra_h2}"
        "## Purpose\n"
        "Human-authored text that must survive.\n"
    )
    p.write_text(body, encoding="utf-8")
    return p


def _source_page(wiki: Path, slug: str, links: list[str], **fm) -> Path:
    d = wiki / "sources"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{slug}.md"
    meta = "".join(f"{k}: {v}\n" for k, v in fm.items())
    link_block = "\n".join(f"- {lnk}" for lnk in links)
    p.write_text(
        f"---\ntitle: {fm.get('title', slug)}\ncategory: source\n{meta}---\n\n"
        f"# {slug}\n\n## Touches\n{link_block}\n",
        encoding="utf-8",
    )
    return p


def test_inject_referenced_in_wiki_replaces_only_that_region(tmp_path: Path) -> None:
    from wiki_io.backlink_index import inject_referenced_in_wiki

    page = _entity_page(tmp_path / "entities", "pkg_foo")
    inject_referenced_in_wiki(page, "- [[sources/2026-06-spec]] — Spec")
    text = page.read_text(encoding="utf-8")
    assert "- [[sources/2026-06-spec]] — Spec" in text
    # Other regions preserved verbatim.
    assert "## Narrative\nSome prose." in text
    assert "Human-authored text that must survive." in text


def test_regenerate_builds_sorted_backlinks(tmp_path: Path) -> None:
    from wiki_io.backlink_index import regenerate_referenced_in_wiki

    wiki = tmp_path / "wiki"
    _entity_page(wiki / "entities", "pkg_foo")
    _source_page(
        wiki, "2026-06-spec", ["[[entities/pkg_foo]]"],
        title="Auth Spec", source_type="spec", source_date="2026-06",
    )
    updated = regenerate_referenced_in_wiki(wiki)
    assert "pkg_foo" in updated
    text = (wiki / "entities" / "pkg_foo.md").read_text(encoding="utf-8")
    assert "[[sources/2026-06-spec]]" in text
    assert "Auth Spec" in text
    assert "spec" in text


def test_regenerate_multi_entity_source_backlinks_from_all(tmp_path: Path) -> None:
    from wiki_io.backlink_index import regenerate_referenced_in_wiki

    wiki = tmp_path / "wiki"
    _entity_page(wiki / "entities", "pkg_foo")
    _entity_page(wiki / "entities", "pkg_bar")
    _source_page(
        wiki, "2026-06-multi",
        ["[[entities/pkg_foo]]", "[[entities/pkg_bar]]"],
        title="Multi", source_type="spec",
    )
    regenerate_referenced_in_wiki(wiki)
    foo = (wiki / "entities" / "pkg_foo.md").read_text(encoding="utf-8")
    bar = (wiki / "entities" / "pkg_bar.md").read_text(encoding="utf-8")
    assert "[[sources/2026-06-multi]]" in foo
    assert "[[sources/2026-06-multi]]" in bar


def test_regenerate_is_idempotent(tmp_path: Path) -> None:
    from wiki_io.backlink_index import regenerate_referenced_in_wiki

    wiki = tmp_path / "wiki"
    _entity_page(wiki / "entities", "pkg_foo")
    _source_page(wiki, "2026-06-spec", ["[[entities/pkg_foo]]"], title="Spec")
    regenerate_referenced_in_wiki(wiki)
    first = (wiki / "entities" / "pkg_foo.md").read_text(encoding="utf-8")
    regenerate_referenced_in_wiki(wiki)
    second = (wiki / "entities" / "pkg_foo.md").read_text(encoding="utf-8")
    assert first == second


def test_regenerate_empty_when_no_references(tmp_path: Path) -> None:
    from wiki_io.backlink_index import regenerate_referenced_in_wiki

    wiki = tmp_path / "wiki"
    _entity_page(wiki / "entities", "pkg_lonely")
    regenerate_referenced_in_wiki(wiki)
    text = (wiki / "entities" / "pkg_lonely.md").read_text(encoding="utf-8")
    # Placeholder replaced by the deterministic "no references" line.
    assert "_No wiki pages reference this entity yet._" in text
    assert "Human-authored text that must survive." in text


def test_regenerate_preserves_other_h2s(tmp_path: Path) -> None:
    """Scanner-owned: only ## Referenced in wiki is rewritten."""
    from wiki_io.backlink_index import regenerate_referenced_in_wiki

    wiki = tmp_path / "wiki"
    _entity_page(
        wiki / "entities", "pkg_foo",
        extra_h2="## Custom Notes\nHand-written, keep me.\n\n",
    )
    _source_page(wiki, "2026-06-spec", ["[[entities/pkg_foo]]"], title="Spec")
    regenerate_referenced_in_wiki(wiki)
    text = (wiki / "entities" / "pkg_foo.md").read_text(encoding="utf-8")
    assert "## Custom Notes\nHand-written, keep me." in text
    assert "## Narrative\nSome prose." in text
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest packages/wiki-io/tests/test_backlink_index.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'wiki_io.backlink_index'`.

- [ ] **Step 3: Create `wiki_io/backlink_index.py`**

Create `packages/wiki-io/src/wiki_io/backlink_index.py`:

```python
from __future__ import annotations

"""Scanner-derived `## Referenced in wiki` backlink regeneration (Slice 4).

Ingest writes durable forward-links (`entity_uri:` + `[[entities/<stem>]]`) into
preserved pages; this module derives the inverse — for each entity page, the
sorted list of preserved pages that link it. It is the backlink half of the
Slice 4 core principle: *ingest writes forward-links; the scanner derives
backlinks; ingest never edits entities/ pages.*

`## Referenced in wiki` is scanner-owned in the same sense as `## Narrative`
(D-16): the H2 heading is a hard convention, the body region is rewritten on
every scan, and everything outside it is preserved verbatim. Pure Python, no
Bedrock — runs in both narrated and `narrate=False` scans.
"""

import os
import re
from pathlib import Path

import frontmatter

_logger_name = __name__

# Hard convention — humans must not rename this heading.
_HEADING = "## Referenced in wiki"
# Match the heading at column 0 followed only by optional trailing whitespace.
_HEADING_RE = re.compile(r"^## Referenced in wiki[ \t]*\n", re.MULTILINE)
# Next H2 at column 0 — bounds the rewritable body region.
_NEXT_H2_RE = re.compile(r"^## ", re.MULTILINE)
# A [[entities/<stem>]] wikilink, tolerating an Obsidian |alias or #anchor.
_ENTITY_LINK_RE = re.compile(r"\[\[entities/([^\]|#\n]+?)(?:[|#][^\]\n]*)?\]\]")

# Empty-state body (deterministic, idempotent).
_EMPTY_BODY = "_No wiki pages reference this entity yet._"

# Preserved categories (folder name -> category label used in the bullet link).
# `work` lives at <workspace>/work (sibling of wiki); handled separately.
_PRESERVED_WIKI_DIRS = ("sources", "concepts", "adrs", "architecture")


def inject_referenced_in_wiki(page_path: Path, body: str) -> None:
    """Replace the body of the `## Referenced in wiki` section with `body`.

    Locates the FIRST `## Referenced in wiki` H2 at column 0; replaces the
    region from end-of-heading up to the next H2 (or EOF) with `body.strip()`.
    Writes atomically (temp-file + os.replace). Idempotent.

    Returns without writing (no error) when the page lacks the heading —
    entity templates always carry it after Task 4.

    Raises:
        FileNotFoundError: when `page_path` does not exist.
    """
    text = page_path.read_text(encoding="utf-8")
    match = _HEADING_RE.search(text)
    if match is None:
        return
    body_start = match.end()
    next_h2 = _NEXT_H2_RE.search(text, body_start)
    body_end = next_h2.start() if next_h2 is not None else len(text)
    cleaned = body.strip()
    new_body = f"\n{cleaned}\n\n" if cleaned else "\n\n"
    new_content = text[:body_start] + new_body + text[body_end:]
    if new_content == text:
        return
    tmp_path = page_path.with_suffix(page_path.suffix + ".tmp")
    tmp_path.write_text(new_content, encoding="utf-8")
    os.replace(tmp_path, page_path)


def _iter_preserved_pages(wiki: Path):
    """Yield (category, page_path) for every preserved page that may carry
    [[entities/...]] forward-links."""
    for folder in _PRESERVED_WIKI_DIRS:
        d = wiki / folder
        if d.is_dir():
            for p in sorted(d.rglob("*.md")):
                if p.name == "index.md":
                    continue
                yield folder, p
    # work/ is a sibling of the wiki (workspace-rooted).
    work_dir = wiki.parent / "work"
    if work_dir.is_dir():
        for p in sorted(work_dir.rglob("*.md")):
            if p.name == "index.md":
                continue
            yield "work", p


def _format_bullet(category: str, slug: str, post) -> str:
    """Render one backlink bullet: `- [[<cat>/<slug>]] — <title> (<type>, <date>)`."""
    md = post.metadata if hasattr(post, "metadata") else {}
    title = str(md.get("title") or slug)
    stype = md.get("source_type")
    date = md.get("source_date") or md.get("date") or md.get("updated")
    suffix = ""
    parts = [str(p) for p in (stype, date) if p]
    if parts:
        suffix = " (" + ", ".join(parts) + ")"
    return f"- [[{category}/{slug}]] — {title}{suffix}"


def regenerate_referenced_in_wiki(wiki: Path) -> list[str]:
    """Rebuild `## Referenced in wiki` on every entity page from the
    `[[entities/<stem>]]` wikilinks found across preserved pages.

    Backlinks key off body wikilinks (not the singular `entity_uri:` field), so
    a source touching several entities backlinks from all of them. Deterministic
    sort (by category, then slug). Idempotent. Returns the list of entity stems
    whose pages were (re)written.
    """
    entities_dir = wiki / "entities"
    if not entities_dir.is_dir():
        return []

    # stem -> list[(category, slug, post)] of referencing pages.
    refs: dict[str, list[tuple[str, str, object]]] = {}
    for category, page_path in _iter_preserved_pages(wiki):
        try:
            post = frontmatter.load(page_path)
        except Exception:  # noqa: BLE001 — a malformed page must not abort regen
            continue
        slug = page_path.stem
        seen_here: set[str] = set()
        for m in _ENTITY_LINK_RE.finditer(post.content):
            stem = m.group(1).strip().removesuffix(".md")
            if stem in seen_here:
                continue
            seen_here.add(stem)
            refs.setdefault(stem, []).append((category, slug, post))

    updated: list[str] = []
    for page_path in sorted(entities_dir.glob("*.md")):
        stem = page_path.stem
        entries = refs.get(stem, [])
        if entries:
            entries_sorted = sorted(entries, key=lambda e: (e[0], e[1]))
            body = "\n".join(
                _format_bullet(cat, slug, post) for cat, slug, post in entries_sorted
            )
        else:
            body = _EMPTY_BODY
        inject_referenced_in_wiki(page_path, body)
        updated.append(stem)
    return updated
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest packages/wiki-io/tests/test_backlink_index.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/wiki-io/src/wiki_io/backlink_index.py packages/wiki-io/tests/test_backlink_index.py
git commit -m "feat(wiki-io): backlink_index — scanner-derived ## Referenced in wiki regeneration"
```

---

## Task 6: Wire backlink regeneration into `run_scan`

Run the regen after index regeneration, in both narrated and `narrate=False` scans, independent of the graph conn (it operates on on-disk pages).

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py`
- Test: `packages/graph-wiki-core/tests/commands/` (scan integration)

- [ ] **Step 1: Write the failing wiring test**

Find the scan command test dir: `ls packages/graph-wiki-core/tests/commands/`. Add a test that drives `run_scan(narrate=False)` against a fixture vault and asserts the backlink section is populated. If seeding a full graph is heavy, prefer a focused test that the regen is *called* by patching it. Create `packages/graph-wiki-core/tests/commands/test_scan_backlinks.py`:

```python
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.mark.asyncio
async def test_run_scan_regenerates_referenced_in_wiki(tmp_path: Path) -> None:
    """run_scan calls regenerate_referenced_in_wiki(wiki) (both narrate modes)."""
    from graph_wiki_core.commands import scan as scan_mod

    wiki = tmp_path / "wiki"
    (wiki / "entities").mkdir(parents=True)
    (wiki / "log.md").write_text("", encoding="utf-8")

    with (
        patch.object(scan_mod, "resolve_wiki_and_repo", return_value=(wiki, tmp_path)),
        patch.object(scan_mod, "_cg_run_build", return_value=(0, "", "")),
        patch.object(scan_mod, "read_only_connect", side_effect=scan_mod.GraphNotInitializedError("x")),
        patch.object(scan_mod, "regenerate_referenced_in_wiki", return_value=["pkg_foo"]) as mock_regen,
    ):
        # With no graph conn, the entity-write path is skipped, but the backlink
        # regen must still run (it is graph-independent).
        await scan_mod.run_scan(workspace_path=tmp_path, narrate=False)

    mock_regen.assert_called_once_with(wiki)
```

Notes: `GraphNotInitializedError` and `read_only_connect` are imported at the top of `scan.py`, so `scan_mod.GraphNotInitializedError` / `scan_mod.read_only_connect` resolve. The pre-regen pipeline (`compute_state_gate`, `discover_workspaces`, `regenerate_dependencies_index`, `update_index`) runs against an empty `tmp_path` repo — if any of those raise in this minimal fixture, model the fixture on an existing passing scan test in `packages/graph-wiki-core/tests/commands/` (which already constructs a working `run_scan` invocation) and add the same patches. The load-bearing assertion is only `mock_regen.assert_called_once_with(wiki)`.

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest packages/graph-wiki-core/tests/commands/test_scan_backlinks.py -v`
Expected: FAIL — `AttributeError: ... has no attribute 'regenerate_referenced_in_wiki'`.

- [ ] **Step 3: Import and wire the regen into `run_scan`**

In `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py`, add the import near the other `wiki_io` imports (e.g. after the `from wiki_io.update_index import update_index` line at 64):

```python
from wiki_io.backlink_index import regenerate_referenced_in_wiki
```

Then, in `run_scan`, immediately after the `update_index(wiki)` try/except block (currently lines 1199–1202):

```python
        try:
            update_index(wiki)  # per-folder */index.md sub-indexes only (Phase 45 D-02)
        except Exception as exc:
            logger.warning("update_index failed (non-fatal): %s", exc)
```

insert:

```python
        # Step 12b (Slice 4): regenerate the scanner-owned `## Referenced in
        # wiki` backlink section on every entity page from the [[entities/...]]
        # forward-links in preserved pages. Pure Python, graph-independent —
        # runs in both narrated and narrate=False scans.
        try:
            backlinked = regenerate_referenced_in_wiki(wiki)
            append_log(
                wiki,
                "scan",
                f"referenced-in-wiki: {len(backlinked)} entity page(s)",
                detail=None,
                silent=True,
                raise_exception=True,
            )
        except Exception as exc:  # noqa: BLE001 — non-fatal post-processing
            logger.warning(
                "regenerate_referenced_in_wiki failed (non-fatal): %s", exc
            )
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest packages/graph-wiki-core/tests/commands/test_scan_backlinks.py -v`
Expected: PASS.

- [ ] **Step 5: Run the scan command tests (regression)**

Run: `uv run pytest packages/graph-wiki-core/tests/commands/ -v -k scan`
Expected: PASS (existing scan tests unaffected — the new step is additive and exception-guarded).

- [ ] **Step 6: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py packages/graph-wiki-core/tests/commands/test_scan_backlinks.py
git commit -m "feat(scan): regenerate ## Referenced in wiki backlinks after index regen"
```

---

## Task 7: Prep `main()` for the plugin shim (`wiki_io.ingest_source`)

Restore the Bedrock-free prep `main()` the plugin shim imports (`from wiki_io.ingest_source import main`). It emits the JSON brief `agents/ingestor.md` step 1 consumes, including the entity-match hint (URI + entity filename). This fixes the current `ImportError`.

**Files:**
- Modify: `packages/wiki-io/src/wiki_io/ingest_source.py`
- Test: `packages/wiki-io/tests/test_ingest_source_prep.py`

- [ ] **Step 1: Write the failing prep test**

Create `packages/wiki-io/tests/test_ingest_source_prep.py`:

```python
from __future__ import annotations

"""Prep main() for the plugin's Claude-branch ingest shim (Slice 4).

The brief must be produced WITHOUT importing model_adapter / subagent_runtime
(the Claude branch is Bedrock-free) and must carry the entity-match hint."""

import importlib
import json
import sys
from pathlib import Path

import pytest


def _seed_db(workspace: Path, name: str, uri: str, rel_path: str) -> None:
    from graph_io.store import connect
    from workspace_io.paths import graph_dir

    db = graph_dir(workspace) / "code.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(db, create=True)
    try:
        conn.execute(
            "INSERT INTO nodes (id, kind, name, path, line, attrs_json, uri) "
            "VALUES (1, 'package', ?, NULL, NULL, NULL, ?)",
            (name, uri),
        )
        conn.execute(
            "INSERT INTO nodes (id, kind, name, path, line, attrs_json, uri) "
            "VALUES (2, 'file', ?, ?, NULL, NULL, NULL)",
            (Path(rel_path).name, rel_path),
        )
        conn.execute(
            "INSERT INTO edges (src, dst, kind, attrs_json) VALUES (1, 2, 'contains', NULL)"
        )
    finally:
        conn.close()


def test_prep_main_emits_brief_without_bedrock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    # Make the Bedrock stack un-importable; the prep must not need it.
    monkeypatch.setitem(sys.modules, "model_adapter", None)
    monkeypatch.setitem(sys.modules, "subagent_runtime", None)

    import wiki_io.ingest_source as prep

    importlib.reload(prep)

    workspace = tmp_path
    wiki = workspace / "wiki"
    wiki.mkdir()
    rel = "packages/graph-io/src/graph_io/store.py"
    src = workspace / rel
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("# Graph IO Store\n\nBody text.", encoding="utf-8")
    _seed_db(workspace, "graph-io", "pkg:o/r/graph-io", rel)

    monkeypatch.setattr(
        sys, "argv", ["ingest_source.py", rel, "--workspace", str(workspace), "--json"]
    )
    monkeypatch.setattr(prep, "resolve_wiki_and_repo", lambda *_a, **_k: (wiki, workspace))

    prep.main()
    brief = json.loads(capsys.readouterr().out)

    assert brief["title"]
    assert brief["source_type"] == "doc"
    assert brief["entity_match"]["uri"] == "pkg:o/r/graph-io"
    assert brief["entity_match"]["entity_filename"] == "pkg_graph-io"
    assert brief["suggested_summary_path"].startswith("sources/")
    assert "state_gate" in brief


def test_prep_main_is_importable(monkeypatch: pytest.MonkeyPatch) -> None:
    """The ImportError the broken shim raised is gone — main() exists."""
    monkeypatch.setitem(sys.modules, "model_adapter", None)
    monkeypatch.setitem(sys.modules, "subagent_runtime", None)
    import importlib

    import wiki_io.ingest_source as prep

    importlib.reload(prep)
    assert callable(prep.main)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest packages/wiki-io/tests/test_ingest_source_prep.py -v`
Expected: FAIL — `AttributeError: module 'wiki_io.ingest_source' has no attribute 'main'`.

- [ ] **Step 3: Add `main()` to `wiki_io/ingest_source.py`**

Append to `packages/wiki-io/src/wiki_io/ingest_source.py` (keep the heavy graph imports lazy inside `main()` so importing the library stays light):

```python
def _build_entity_match(workspace_root: Path, repo: Path, source_path: Path, title_guess: str) -> dict:
    """Resolve the entity a source belongs to and the on-disk entity filename.

    Bedrock-free. Opens a read-only graph conn; returns
    {"uri": None, "entity_filename": None} when the graph is missing or no
    entity matches (the harness agent proceeds without a link in that case).
    """
    from graph_io.store import GraphNotInitializedError, read_only_connect
    from workspace_io.paths import graph_dir

    from wiki_io.entity_lookup import (
        entity_filename_for_uri,
        lookup_entity_by_name,
        lookup_entity_by_path,
    )

    empty = {"uri": None, "entity_filename": None}
    try:
        conn = read_only_connect(graph_dir(workspace_root) / "code.db")
    except GraphNotInitializedError:
        return empty
    try:
        match = lookup_entity_by_path(conn, repo, source_path)
        if match is None:
            match = lookup_entity_by_name(conn, title_guess)
        if match is None:
            return empty
        uri = match[0]
        return {"uri": uri, "entity_filename": entity_filename_for_uri(uri, conn)}
    finally:
        try:
            conn.close()
        except Exception:
            pass


def main() -> None:
    """Emit the ingest prep brief (JSON) consumed by the harness ingestor agent.

    Bedrock-free: builds on this module's library functions plus the shared
    `wiki_io.entity_lookup`. Never imports model_adapter / subagent_runtime.
    """
    import argparse
    import datetime
    import json
    import sys

    parser = argparse.ArgumentParser(description="Prepare a source for ingestion.")
    parser.add_argument("source", nargs="?", default=None, help="Path to the source file/folder")
    parser.add_argument("--source", dest="source_opt", default=None, help="Path to the source (alt form)")
    parser.add_argument("--workspace", default="", help="Workspace path (default: env / git heuristic)")
    parser.add_argument("--json", action="store_true", dest="json_output", help="Emit JSON brief")
    args = parser.parse_args()

    source_arg = args.source_opt or args.source
    if not source_arg:
        print("[error] no source path given", file=sys.stderr)
        sys.exit(1)
    source_path = Path(source_arg)

    workspace_path = Path(args.workspace) if args.workspace else None
    wiki, repo = resolve_wiki_and_repo(workspace_path)
    if repo is None:
        repo = Path.cwd()
    workspace_root = workspace_path if workspace_path is not None else wiki.parent

    # Folder ingest (raw/examples/<dir>/).
    if source_path.is_dir():
        rel_to_wiki = None
        try:
            rel_to_wiki = source_path.relative_to(wiki)
        except ValueError:
            pass
        brief: dict = {
            "is_folder": True,
            **folder_brief(source_path, rel_to_wiki),
            "state_gate": compute_state_gate(repo),
        }
        if "_error" in brief:
            print(f"[error] {brief['_error']}", file=sys.stderr)
            sys.exit(1)
        if args.json_output:
            print(json.dumps(brief, indent=2))
        return

    # Single-file ingest.
    text, title = extract(source_path)
    title_guess = title or source_path.stem.replace("-", " ").title()
    slug = slugify(title_guess)

    rel_to_wiki = None
    rel_to_repo = None
    try:
        rel_to_wiki = source_path.relative_to(wiki)
    except ValueError:
        pass
    try:
        rel_to_repo = source_path.relative_to(repo)
    except ValueError:
        pass
    source_type = guess_source_type(rel_to_wiki, rel_to_repo)

    preview = text[:PREVIEW_CHARS]
    if len(text) > PREVIEW_CHARS:
        preview += "\n[TRUNCATED]"

    month = datetime.date.today().strftime("%Y-%m")
    suggested = f"sources/{month}-{slug}.md"
    page_exists = (wiki / suggested).exists()

    in_repo_doc = rel_to_repo is not None and rel_to_wiki is None

    brief = {
        "source_path": str(source_path),
        "title": title_guess,
        "source_type": source_type,
        "slug": slug,
        "preview": preview,
        "word_count": len(text.split()),
        "suggested_summary_path": suggested,
        "merge_mode": page_exists,
        "in_repo_doc": in_repo_doc,
        "entity_match": _build_entity_match(workspace_root, repo, source_path, title_guess),
        "state_gate": compute_state_gate(repo),
    }
    if args.json_output:
        print(json.dumps(brief, indent=2))
    else:
        print(f"Title: {brief['title']}")
        print(f"Source type: {brief['source_type']}")
        print(f"Suggested summary: {brief['suggested_summary_path']}")
        em = brief["entity_match"]
        if em["uri"]:
            print(f"Entity match: {em['uri']} -> [[entities/{em['entity_filename']}]]")
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest packages/wiki-io/tests/test_ingest_source_prep.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Verify the plugin shim now imports cleanly**

Run: `uv run --package graph-wiki-cli python -c "from wiki_io.ingest_source import main; print('ok')"`
Expected: `ok` (the `ImportError` is gone).

- [ ] **Step 6: Verify the Bedrock-shim argv contract test still passes**

Run: `uv run --package graph-wiki-cli python -m pytest packages/graph-wiki-cli/tests/unit/test_plugin_bedrock_shims.py -v`
Expected: PASS — the `ingest_source.py` row still shells `gw wiki ingest source` with preserved argv; the real `main()` now satisfies the top-level import without altering the bedrock branch.

- [ ] **Step 7: Commit**

```bash
git add packages/wiki-io/src/wiki_io/ingest_source.py packages/wiki-io/tests/test_ingest_source_prep.py
git commit -m "fix(plugin): restore Bedrock-free ingest prep main() with entity-match hint"
```

---

## Task 8: Rewrite plugin docs + `source.md` template to the entities/ link model

The Claude-branch agent/command/reference docs and the `source.md` template still describe the legacy `packages/`+`domains/` page model. Rewrite to: link entities via `[[entities/...]]`, never edit entity pages, scanner backfills `## Referenced in wiki`.

**Files:**
- Modify: `plugins/graph-wiki/agents/ingestor.md`
- Modify: `plugins/graph-wiki/commands/ingest.md`
- Modify: `plugins/graph-wiki/skills/graph-wiki/references/ingest-workflow.md`
- Modify: `packages/wiki-io/src/wiki_io/assets/page-templates/source.md`

- [ ] **Step 1: Write the failing source-template test**

Add to `packages/wiki-io/tests/test_entity_templates.py` (or a nearby template test module):

```python
def test_source_template_uses_entities_and_has_entity_uri() -> None:
    from importlib.resources import files

    body = (files("wiki_io.assets.page-templates") / "source.md").read_text(encoding="utf-8")
    # Forward-link to entities, not legacy packages/domains.
    assert "[[entities/" in body
    assert "[[packages/" not in body
    assert "[[domains/" not in body
    # Singular canonical anchor present in frontmatter.
    assert "entity_uri:" in body
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest packages/wiki-io/tests/test_entity_templates.py -k source_template -v`
Expected: FAIL — `[[packages/<pkg>]]` still present, `entity_uri:` absent.

- [ ] **Step 3: Rewrite `source.md`**

In `packages/wiki-io/src/wiki_io/assets/page-templates/source.md`:

Add `entity_uri:` to the frontmatter — insert after the `source_path:` line (line 5):

```yaml
entity_uri:                      # canonical code entity this source primarily documents (e.g. pkg:org/repo/graph-io), or null
```

Change `## Proposed changes (if applicable)` bullet (line 26) from:

```markdown
- `packages/<pkg>` — ...
```

to:

```markdown
- `entities/<prefix>_<name>` — ...
```

Change the `## Touches` section (lines 34–37) from:

```markdown
## Touches
- [[packages/<pkg>]]
- [[domains/<domain>]]
- [[concepts/<concept>]]
```

to:

```markdown
## Touches
- [[entities/<prefix>_<name>]]
- [[concepts/<concept>]]
```

Change the `## Where it's cited in this wiki` section (lines 42–44) from:

```markdown
## Where it's cited in this wiki
- [[packages/<pkg>]]
- [[domains/<domain>]]
```

to:

```markdown
## Where it's cited in this wiki
- [[entities/<prefix>_<name>]]
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest packages/wiki-io/tests/test_entity_templates.py -k source_template -v`
Expected: PASS.

- [ ] **Step 5: Rewrite `agents/ingestor.md`**

In `plugins/graph-wiki/agents/ingestor.md`:

- Frontmatter `description` (line 3): replace `updates 5-15 cross-referenced pages` with `writes the source summary, links the relevant code entities via [[entities/...]] wikilinks (the scanner derives backlinks), and updates concept/ADR pages`.
- `## Role` (line 15): replace `touching every relevant package, domain, concept, and architecture page` with `writing a source summary, linking the relevant code entities via [[entities/...]] wikilinks, and updating concept/architecture/ADR pages — never editing entity pages (the scanner owns them)`.
- Replace step **5. Update package pages** (lines 60–61) and step **6. Update domain / concept / dependency pages** (lines 63–64) with a single step:

```markdown
### 5. Link the code entities (never edit entity pages)
For each code entity (package, app, domain, dependency) the source touches, add a `[[entities/<prefix>_<name>]]` wikilink under the source summary's `## Touches` section. Entity pages are scanner-owned and live under `entities/` — **do not edit them**. The scanner regenerates each entity's `## Referenced in wiki` section from these forward-links on the next `/graph-wiki:scan`. Set the source page's `entity_uri:` frontmatter to the primary/canonical entity's URI (or `null` if none).

### 6. Update concept / dependency pages
For each cross-cutting concept the source mentions: update `## Key claims` / `## Used in`, add to `## Sources`, or create a stub concept page. (Concept and dependency *content* pages under `concepts/`/`dependencies/` are still hand-maintained; the graph-derived `entities/dep_*` pages are not.)
```

- In `## Rules`, change the wikilink rule (line 95) so the example uses `[[entities/...]]`, and change `Minimum 3 file touches` line (line 100) to keep "source summary + index + log" (unchanged), but update the parenthetical to drop "package/domain page" language.

- [ ] **Step 6: Rewrite `commands/ingest.md`**

In `plugins/graph-wiki/commands/ingest.md`:

- `description` (line 3) and the intro (line 10): replace `update package/domain/concept pages` with `link relevant code entities via [[entities/...]] and update concept/ADR pages`.
- The "Source types → typical touches" table (lines 30–38): replace `Package pages for every package modified` / `Domain/architecture pages + ADR` style cells with entity-link phrasing, e.g. `[[entities/...]] links for every package modified + ADR`. Concretely, change the `Typical touches` column entries that name `package`/`domain` *pages* to `[[entities/...]] links + <concept/ADR/architecture> pages`.
- The "What happens" step list (lines 44–52): change step 6 from `Update — 5-15 pages across packages/domains/concepts` to `Link entities — add [[entities/...]] under ## Touches; do not edit entity pages` and note the scanner backfills `## Referenced in wiki`.

- [ ] **Step 7: Rewrite `references/ingest-workflow.md`**

In `plugins/graph-wiki/skills/graph-wiki/references/ingest-workflow.md`:

- Step **1. Prepare the brief** (lines 21–30): add the `entity_match` (`uri` + `entity_filename`) field to the brief's listed outputs.
- Step **5. Update relevant package pages** (lines 56–62) and Step **6. Update domain pages** (lines 64–69): replace both with a single "Link code entities" step matching the agent doc — add `[[entities/<prefix>_<name>]]` under `## Touches`, set `entity_uri:`, never edit entity pages, scanner backfills `## Referenced in wiki`.
- The example-variant notes (lines 162–168) that mirror `[[packages/X]]`/`[[domains/X]]` under `## Inspirations`: update to `[[entities/...]]` and note the scanner-derived backlink replaces the manual `## Appears in sources` / `## Inspirations` reciprocity for entity pages (concept/architecture pages keep manual reciprocity).

- [ ] **Step 8: Verify no legacy page-folder wikilinks remain in the rewritten docs**

Run:
```bash
grep -nE "\[\[packages/|\[\[domains/" plugins/graph-wiki/agents/ingestor.md plugins/graph-wiki/commands/ingest.md plugins/graph-wiki/skills/graph-wiki/references/ingest-workflow.md
```
Expected: no matches (exit 1 / empty). Legacy `[[packages/...]]`/`[[domains/...]]` references in the ingest docs are gone.

- [ ] **Step 9: Commit**

```bash
git add plugins/graph-wiki/agents/ingestor.md plugins/graph-wiki/commands/ingest.md plugins/graph-wiki/skills/graph-wiki/references/ingest-workflow.md packages/wiki-io/src/wiki_io/assets/page-templates/source.md packages/wiki-io/tests/test_entity_templates.py
git commit -m "docs(plugin): ingest links entities via [[entities/...]]; scanner derives backlinks"
```

---

## Task 9: Full-suite verification

**Files:** none (verification only)

- [ ] **Step 1: Run the wiki-io suite**

Run: `uv run pytest packages/wiki-io/ -q`
Expected: PASS (new `entity_lookup`, `backlink_index`, `ingest_source_prep`, template tests + existing tests).

- [ ] **Step 2: Run the graph-wiki-core suite**

Run: `uv run pytest packages/graph-wiki-core/ -q`
Expected: PASS (updated ingest tests, ingestor prompt test, scan backlink wiring).

- [ ] **Step 3: Run the graph-wiki-cli shim contract test**

Run: `uv run --package graph-wiki-cli python -m pytest packages/graph-wiki-cli/tests/unit/test_plugin_bedrock_shims.py -q`
Expected: PASS.

- [ ] **Step 4: Confirm no orphaned references to removed symbols**

Run:
```bash
grep -rn "slug_from_uri" packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py
grep -rn "_PAGE_TYPE_DIRS\[.package.\]\|\"package\": \"packages\"" packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py
```
Expected: no matches — `slug_from_uri` import removed from `ingest.py`; no `package -> packages` route remains. (`uri_slug.py` itself stays for any other callers — verify with `grep -rn "from graph_wiki_core.uri_slug import" packages/` and leave it untouched if other modules import it.)

- [ ] **Step 5: Final commit (if any cleanup was needed)**

```bash
git add -A
git commit -m "test(slice4): full-suite verification for ingest entities/ parity"
```

---

## Notes for the implementer

- **No migration (backward-compat rule).** Pre-existing legacy `packages/`/`domains/` ingest pages become orphans under the entities/ layout; the user rebuilds. Slice-3 lint surfaces such orphans — do not write migration code.
- **`run_ingest_work_item` is out of scope.** Work items file under `work/` via `file_work_item`, bypassing `_route_target_path` — leave that path untouched.
- **`## Referenced in wiki` is scanner-owned in the `## Narrative` sense.** There is no separate lint registry to update; it is owned because the scanner rewrites it (Task 5/6) and humans don't author it. The hard convention (don't rename the heading) is documented in `backlink_index.py`'s module docstring.
- **`entity_filename_for_uri` collision exactness.** With a `conn`, it computes the exact collision set so colliding stems get the scanner's `__<hex>` suffix. Ingest never matches `test_suite` entities (ENTITY_KINDS = package/class/function/method/domain), so the suite-kind filename branch is irrelevant here.
- **Keep `gw` and the plugin convergent.** Both `run_ingest_source` (Bedrock) and the prep `main()` (Claude) now resolve entities via the same `wiki_io.entity_lookup` helpers and the same `entity_filename_for_uri` filename rule — this convergence is the point of the slice.
