# Test-suite file maps (`gw scan`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every `test_suite` entity wiki page a populated `## File map` section whose tree starts at the suite root (`node.attrs["path"]`), with per-file descriptions filled by the same `code_reader` LLM fan-out that packages and apps already use.

**Architecture:** Add a dedicated, self-contained test-suite branch (selected design A) rather than folding `test_suite` into the package/app loops. A new unpartitioned builder `build_dir_file_map` emits the deterministic block; a new "Step 10b-ts" in `run_scan` injects it into refreshed test-suite pages and queues them for the existing Step 10c describer pass; durability is satisfied entirely by reusing the existing snapshot→merge machinery.

**Tech Stack:** Python 3.11+, `uv` workspace, pytest + pytest-asyncio, `graph-io` (sqlite graph), `wiki-io` (vault I/O), `graph-wiki-core` (`run_scan` pipeline).

---

## Background you need before starting

Read these once — every task references them.

**The two files you will edit:**
- `packages/wiki-io/src/wiki_io/scan_monorepo.py` — the deterministic file-map builders. You add `build_dir_file_map` here. The shared row emitter is `_emit_file_map_block(pkg_name, files, truncated, max_depth, max_entries)` (`scan_monorepo.py:420`); the git lister is `_git_ls_files(path)` (`scan_monorepo.py:338`), which returns `list[str]` of root-relative paths or `None` when `path` is not under git. The existing `build_file_maps` (`scan_monorepo.py:519`) shows the contracts to mirror: `None` on non-git, `- (no tracked files)` short-circuit on empty, `max_entries` truncation marker.
- `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py` — the `run_scan` pipeline. You add the test-suite injection branch (Step 10b-ts) right after the package/app file-map block, and you extend the Step 10c describer scoping.

**How a `test_suite` node looks (graph-io):** `queries.list_test_suites(conn)` (`packages/graph-io/src/graph_io/queries.py:877`) returns `NodeRecord`s. A test-suite node's `.attrs` dict carries (`packages/graph-io/src/graph_io/test_suites.py:344`):
- `attrs["uri"]` — e.g. `test_suite:org/repo/pkg-a/tests` (folded in from the `uri` column by `_row_to_node`).
- `attrs["path"]` — the suite root path relative to the repo, e.g. `packages/pkg-a/tests`.
- `attrs["suite_kind"]` — `unit` | `integration` | `e2e` | `contract` | `""`.
- `attrs["language"]` — optional, e.g. `python`.

**The filename slug for a test-suite page** is computed by `short_filename(uri, collision_set, suite_kind=..., pkg_for_suite=...)` (`packages/wiki-io/src/wiki_io/entity_writer.py:159`). For test suites, `pkg_for_suite` is conventionally `Path(suite_path).parent.name` (the owning package's directory name). Example: `short_filename("test_suite:org/repo/pkg-a/tests", frozenset(), suite_kind="unit", pkg_for_suite="pkg-a")` → `"unit_tests_pkg-a"`. This logic currently lives inline in a **nested** `_entity_page_path` closure (`scan.py:888-907`); Task 2 hoists it to a reusable module-level helper.

**The durability machinery (reused as-is, no new code):**
- `_snapshot_file_map_descriptions(wiki)` (`scan.py:135`) globs **all** `entities/*.md`, keys filled descriptions by frontmatter `uri` **without filtering by kind** — so it already captures test-suite pages. It reads the package label from the `## File map - <pkg_name>` heading and reconstructs suite-root-relative paths via `_section_path_context` / `_file_map_full_path` (`entity_writer.py:961-980`).
- `inject_file_map(page_path, block, preserved=...)` (`entity_writer.py:1065`) replaces the whole `## File map` section (it finds the heading via `_FILE_MAP_HEADING_RE = ^## File map\b.*\n` regardless of the label) and restores preserved descriptions onto matching rows via `_merge_preserved_descriptions`.
- `file_map_todo_paths(page_path)` (`entity_writer.py:1134`) returns only file rows still `— TODO`, so a fully-described suite yields `[]` and triggers no model call.

**The one durability obligation (from the spec):** the `pkg_name` label in the `## File map - <pkg_name>` heading **must be deterministic and stable** for a given suite, because snapshot→merge strips it to recover suite-root-relative path keys. `build_dir_file_map` satisfies this by labelling with the **suite-root directory basename** (`path.name`) — stable unless the suite physically moves, exactly how packages use their dir name.

**The test-suite page template** (`packages/wiki-io/src/wiki_io/assets/page-templates/entity-test-suite.md`) already carries a `## File map - {{PACKAGE_SLUG}}` section — no template change is needed. `inject_file_map` replaces that section wholesale with our block.

**How integration tests avoid git/Bedrock** (`packages/graph-wiki-core/tests/unit/test_scan_graph_integration.py`): the test repo is **not** a git repo, so the real builder would return `None`. The existing package/app tests monkeypatch `scan_module.build_file_map` to `None` and preset `w["file_map"]` on fake workspace dicts. The test-suite branch builds its block inline via a module-level `build_dir_file_map` reference, so tests monkeypatch `scan_module.build_dir_file_map` to return a preset block. The autouse fixtures `stub_pool_run_all` and `stub_make_llm` keep Bedrock out; `_cg_run_build` is stubbed per-test to return `(exit_codes.SUCCESS, "", "")`.

**Scope guardrails (do not touch):**
- `build_file_map` / `build_file_maps` stay prod-only — **do not modify them**.
- The `graph-wiki` plugin and `plugins/graph-wiki/.../scan_monorepo.py` are out of scope.
- The narrator-hint extension (spec §4) is **intentionally deferred** — see "Deferred" at the end. It is explicitly droppable in the spec and would require feeding suite file-map text into the Step 9b narrator fan-out, which runs *before* the file maps are built. Not worth the reordering for a grounding hint the spec marks optional.

**Commands** (run from repo root `/Users/pat/Personal/agent-research`):
- wiki-io tests: `uv run --package wiki-io pytest packages/wiki-io/tests/test_scan_monorepo.py -v`
- graph-wiki-core tests: `uv run --package graph-wiki-agent pytest packages/graph-wiki-core/tests/unit/test_scan_graph_integration.py -v`
  (graph-wiki-core's tests are run via the `graph-wiki-agent` member that depends on it; if that package name is wrong in your checkout, fall back to `uv run pytest packages/graph-wiki-core/tests/unit/test_scan_graph_integration.py -v`.)

---

## File structure

| File | Change | Responsibility |
|------|--------|----------------|
| `packages/wiki-io/src/wiki_io/scan_monorepo.py` | add `build_dir_file_map` | Unpartitioned `## File map - <root-basename>` block for any directory root. |
| `packages/wiki-io/tests/test_scan_monorepo.py` | add `TestBuildDirFileMap` | Unit-test the builder's contracts. |
| `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py` | hoist `_entity_page_path`; add `build_dir_file_map` import; add Step 10b-ts; extend Step 10c | Inject suite file maps + describer scoping. |
| `packages/graph-wiki-core/tests/unit/test_scan_graph_integration.py` | add 3 tests | Suite injection, code-reader fill, durability + no-describer-on-rescan. |

---

## Task 1: `build_dir_file_map` builder + unit tests

**Files:**
- Modify: `packages/wiki-io/src/wiki_io/scan_monorepo.py` (add function after `build_file_map`, ~line 597)
- Test: `packages/wiki-io/tests/test_scan_monorepo.py` (add a class after `TestBuildFileMap`, ~line 303)

- [ ] **Step 1: Write the failing tests**

Add this helper + class to `packages/wiki-io/tests/test_scan_monorepo.py` immediately after the `TestBuildFileMap` class (after line 302). It mirrors the existing `_bfm` helper pattern (line 180).

```python
def _bdfm(root_name: str, files: list[str] | None, **kwargs):
    """Call build_dir_file_map() with a mocked _git_ls_files."""
    from wiki_io.scan_monorepo import build_dir_file_map

    root_path = Path(f"/fake/{root_name}")
    with patch("wiki_io.scan_monorepo._git_ls_files", return_value=files):
        return build_dir_file_map(root_path, **kwargs)


class TestBuildDirFileMap:
    """Tests for build_dir_file_map() — unpartitioned single-root file map."""

    def test_heading_uses_root_basename(self) -> None:
        """The block heading is labelled with the root directory basename."""
        result = _bdfm("tests", ["test_main.py"])
        assert result is not None
        assert "## File map - tests" in result
        assert "### tests/" in result

    def test_unpartitioned_lists_root_conftest_and_plain_helper(self) -> None:
        """No prod/test split: a root conftest.py AND a plain helpers.py both
        appear (build_file_map's prod/test partition would drop one of them)."""
        result = _bdfm("tests", ["conftest.py", "helpers.py", "unit/test_x.py"])
        assert result is not None
        assert "| `conftest.py` | file | — TODO |" in result
        assert "| `helpers.py` | file | — TODO |" in result
        # The nested test file lands in its depth-1 section.
        assert "### tests/unit/" in result
        assert "| `test_x.py` | file | — TODO |" in result

    def test_empty_root_short_circuit(self) -> None:
        """Empty root → the legacy `- (no tracked files)` short-circuit, no table."""
        result = _bdfm("tests", [])
        assert result is not None
        assert "## File map - tests" in result
        assert "- (no tracked files)" in result
        assert "| Path | Kind | Description |" not in result

    def test_non_git_returns_none(self) -> None:
        """Returns None when _git_ls_files returns None (root not under git)."""
        assert _bdfm("tests", None) is None

    def test_truncation_marker(self) -> None:
        """When file count > max_entries, the truncation blockquote is appended."""
        files = [f"test_{i}.py" for i in range(5)]
        result = _bdfm("tests", files, max_entries=3)
        assert result is not None
        assert "> Truncated at 3 files." in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --package wiki-io pytest packages/wiki-io/tests/test_scan_monorepo.py::TestBuildDirFileMap -v`
Expected: FAIL — `ImportError: cannot import name 'build_dir_file_map'`.

- [ ] **Step 3: Implement `build_dir_file_map`**

Add this function to `packages/wiki-io/src/wiki_io/scan_monorepo.py` immediately after `build_file_map` (after line 596, before `discover_workspaces`):

```python
def build_dir_file_map(path: Path, max_depth: int = 4, max_entries: int = 80) -> str | None:
    """Return an unpartitioned ``## File map - <root-basename>`` block covering
    ALL tracked files under ``path``.

    Unlike ``build_file_map`` (prod-only) / ``build_file_maps`` (prod+test
    split), this lists everything under the root with no prod/test partition.
    Used for test-suite entity pages: everything under a suite root is
    test-related, so partitioning would mis-route files (a root ``conftest.py``
    into the dropped test half, a plain ``helpers.py`` into prod).

    The heading label is the root directory basename (``path.name``) — stable
    unless the suite physically moves. This stability is load-bearing for
    cross-rescan description preservation: the snapshot/merge round-trip strips
    this label to reconstruct suite-root-relative path keys.

    Returns ``None`` when ``_git_ls_files(path)`` returns ``None`` (not git).
    Emits the ``- (no tracked files)`` short-circuit for an empty root. Honors
    ``max_entries`` truncation. Mirrors ``build_file_maps``' contracts.
    """
    files = _git_ls_files(path)
    if files is None:
        return None

    name = path.name
    truncated = len(files) > max_entries
    if truncated:
        files = files[:max_entries]

    if not files:
        title_line = f"## File map - {name}"
        overview_placeholder = "TODO — overview of this package's tree."
        block = f"{title_line}\n{overview_placeholder}\n\n- (no tracked files)\n"
        if truncated:
            block = block.rstrip("\n") + f"\n\n> Truncated at {max_entries} files.\n"
        return block

    return _emit_file_map_block(name, files, truncated, max_depth, max_entries)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --package wiki-io pytest packages/wiki-io/tests/test_scan_monorepo.py::TestBuildDirFileMap -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Run the full wiki-io scan suite to confirm no regression**

Run: `uv run --package wiki-io pytest packages/wiki-io/tests/test_scan_monorepo.py -v`
Expected: PASS (all pre-existing tests still green; `build_file_map`/`build_file_maps` untouched).

- [ ] **Step 6: Commit**

```bash
git add packages/wiki-io/src/wiki_io/scan_monorepo.py packages/wiki-io/tests/test_scan_monorepo.py
git commit -m "feat(wiki-io): add build_dir_file_map (unpartitioned single-root file map)"
```

---

## Task 2: Hoist `_entity_page_path` to a module-level helper

This is a pure refactor — no behavior change. The suite-aware page-path logic currently lives in a nested closure (`scan.py:888-907`) reachable only inside the narrator block. Step 10b-ts (Task 3) needs the same logic, so we lift it to module scope. Existing tests must stay green.

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py` (add helper near line 550; edit the narrator block at lines 884-913)
- Test: `packages/graph-wiki-core/tests/unit/test_scan_graph_integration.py` (add one helper-locking unit test)

- [ ] **Step 1: Write the failing test**

Add this test to `packages/graph-wiki-core/tests/unit/test_scan_graph_integration.py` at the end of the file (after line 1237). It pins the hoisted helper's contract directly.

```python
def test_entity_page_path_suite_aware_slug():
    """Module-level _entity_page_path applies the suite-aware slug for
    test_suite kinds (suite_kind + pkg_for_suite derived from attrs['path'])."""
    from types import SimpleNamespace

    wiki = Path("/fake/wiki")
    node = SimpleNamespace(
        kind="test_suite",
        name="pkg-a-unit-tests",
        attrs={
            "uri": "test_suite:org/repo/pkg-a/tests",
            "suite_kind": "unit",
            "path": "packages/pkg-a/tests",
        },
    )
    page = scan_module._entity_page_path(
        wiki, "test_suite", node, "test_suite:org/repo/pkg-a/tests", frozenset()
    )
    assert page == wiki / "entities" / "unit_tests_pkg-a.md"

    # A package node uses the plain kind prefix (no suite logic).
    pkg_node = SimpleNamespace(
        kind="package", name="pkg-a", attrs={"uri": "pkg:org/repo/pkg-a"}
    )
    pkg_page = scan_module._entity_page_path(
        wiki, "package", pkg_node, "pkg:org/repo/pkg-a", frozenset()
    )
    assert pkg_page == wiki / "entities" / "pkg_pkg-a.md"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --package graph-wiki-agent pytest packages/graph-wiki-core/tests/unit/test_scan_graph_integration.py::test_entity_page_path_suite_aware_slug -v`
Expected: FAIL — `AttributeError: module ... has no attribute '_entity_page_path'`.

- [ ] **Step 3: Add the module-level helper**

Insert this function in `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py` immediately before `def _add_stale_tag` (before line 518):

```python
def _entity_page_path(
    wiki: Path,
    kind: str,
    node: Any,
    uri: str,
    collision_set: frozenset[str],
) -> Path:
    """Resolve the ``entities/<stem>.md`` path for a graph node.

    Applies the suite-aware slug (``suite_kind`` + ``pkg_for_suite`` derived
    from ``attrs['path']``) for ``test_suite`` kinds, matching what
    ``write_entities`` produces; all other kinds use the plain prefix slug.
    """
    suite_kind: str | None = None
    pkg_for_suite: str | None = None
    if kind == "test_suite":
        attrs = node.attrs if isinstance(node.attrs, dict) else {}
        suite_kind = attrs.get("suite_kind") or None
        suite_path = attrs.get("path")
        if suite_path:
            pkg_for_suite = Path(suite_path).parent.name or None
    stem = short_filename(
        uri,
        collision_set,
        suite_kind=suite_kind,
        pkg_for_suite=pkg_for_suite,
    )
    return wiki / "entities" / f"{stem}.md"
```

- [ ] **Step 4: Replace the nested closure in the narrator block with a call to the helper**

In `run_scan`, the narrator block currently defines a nested `_entity_page_path` and calls it. Replace lines 888-913 (the nested `def _entity_page_path(...)` through the `for item, prose in narrator_result.successes:` loop body that calls it) so the nested def is removed and the loop calls the module-level helper.

Find this block (starting at line 888):

```python
            def _entity_page_path(kind_inner: str, node_inner: Any, uri_inner: str) -> Path:
                suite_kind_inner: str | None = None
                pkg_for_suite_inner: str | None = None
                if kind_inner == "test_suite":
                    attrs_inner = (
                        node_inner.attrs if isinstance(node_inner.attrs, dict) else {}
                    )
                    suite_kind_inner = attrs_inner.get("suite_kind") or None
                    suite_path_inner = attrs_inner.get("path")
                    if suite_path_inner:
                        pkg_for_suite_inner = (
                            Path(suite_path_inner).parent.name or None
                        )
                stem = short_filename(
                    uri_inner,
                    inject_collision_set,
                    suite_kind=suite_kind_inner,
                    pkg_for_suite=pkg_for_suite_inner,
                )
                return wiki / "entities" / f"{stem}.md"

            for item, prose in narrator_result.successes:
                uri_inner, kind_inner, node_inner = item
                entity_page_path = _entity_page_path(
                    kind_inner, node_inner, uri_inner,
                )
```

Replace it with (the nested def is gone; the loop calls the module-level helper, passing `wiki` and `inject_collision_set`):

```python
            for item, prose in narrator_result.successes:
                uri_inner, kind_inner, node_inner = item
                entity_page_path = _entity_page_path(
                    wiki, kind_inner, node_inner, uri_inner, inject_collision_set,
                )
```

Leave everything after `entity_page_path = ...` (the `try: inject_narrative(...)` block, lines 914-923) unchanged.

- [ ] **Step 5: Run the helper test + full integration suite**

Run: `uv run --package graph-wiki-agent pytest packages/graph-wiki-core/tests/unit/test_scan_graph_integration.py -v`
Expected: PASS — the new `test_entity_page_path_suite_aware_slug` passes and all 16 pre-existing tests stay green (the refactor is behavior-preserving).

- [ ] **Step 6: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py packages/graph-wiki-core/tests/unit/test_scan_graph_integration.py
git commit -m "refactor(scan): hoist _entity_page_path to a reusable module-level helper"
```

---

## Task 3: Step 10b-ts — inject test-suite file maps

Add the test-suite injection branch right after the package/app file-map block, sharing the collision set. After this task, a refreshed `test_suite` page gets its `## File map` section replaced with the suite-root tree (`— TODO` descriptions), and the page is queued into `file_mapped_pages` for Step 10c.

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py` (import at lines 44-54; Step 10b block at lines 941-989)
- Test: `packages/graph-wiki-core/tests/unit/test_scan_graph_integration.py` (add suite-injection test + a seeding helper)

- [ ] **Step 1: Write the failing test**

Add a test-suite graph seeder next to `_seed_minimal_graph` / `_seed_app_graph` (after line 116) in `test_scan_graph_integration.py`:

```python
def _seed_test_suite_graph(db_path: Path) -> None:
    """Seed a minimal DB with one test_suite node owned by pkg-a.

    Layout:
      test_suite node: name 'pkg-a-unit-tests', path 'packages/pkg-a/tests',
        uri 'test_suite:org/repo/pkg-a/tests', attrs {suite_kind: unit,
        path: packages/pkg-a/tests, language: python}
    """
    from graph_io import schema

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        schema.apply_schema(conn)
        conn.execute(
            "INSERT INTO nodes(kind, name, path, line, attrs_json, uri) VALUES "
            "('test_suite', 'pkg-a-unit-tests', 'packages/pkg-a/tests', NULL, "
            "'{\"suite_kind\": \"unit\", \"path\": \"packages/pkg-a/tests\", \"language\": \"python\"}', "
            "'test_suite:org/repo/pkg-a/tests')"
        )
        conn.commit()
    finally:
        conn.close()
```

Then add this test at the end of the file:

```python
@pytest.mark.asyncio
async def test_file_map_injected_into_test_suite_entity_page(
    tmp_workspace_with_packages, monkeypatch
):
    """Step 10b-ts: after write_entities creates a test_suite entity page,
    run_scan replaces its `## File map` section with the deterministic
    build_dir_file_map block rooted at the suite path (path + kind rows)."""
    workspace = tmp_workspace_with_packages
    wiki = workspace / "wiki"
    repo = workspace / "repo"

    db = workspace / ".graph" / "code.db"
    _seed_test_suite_graph(db)

    monkeypatch.setattr(
        scan_module, "_cg_run_build", lambda repo, workspace, *, full: (exit_codes.SUCCESS, "", "")
    )

    # Deterministic suite block as build_dir_file_map would emit it. The heading
    # label is the suite-root basename ("tests").
    suite_block = (
        "## File map - tests\n"
        "TODO — overview of this package's tree.\n"
        "\n"
        "### tests/\n"
        "TODO — describe what this directory contains.\n"
        "\n"
        "| Path | Kind | Description |\n"
        "|---|---|---|\n"
        "| `conftest.py` | file | — TODO |\n"
        "| `test_pkg_a.py` | file | — TODO |\n"
    )
    monkeypatch.setattr(
        scan_module, "build_dir_file_map", lambda *a, **kw: suite_block
    )
    # No package/app workspaces — only the seeded test_suite drives this scan.
    monkeypatch.setattr(scan_module, "discover_workspaces", lambda *a, **kw: [])
    monkeypatch.setattr(scan_module, "_load_existing_pages", lambda wiki: __import__("wiki_io.scan_monorepo", fromlist=["ExistingPages"]).ExistingPages(legacy={}, entities={}))
    monkeypatch.setattr(scan_module, "attach_changed_files", lambda *a, **kw: None)
    monkeypatch.setattr(
        scan_module,
        "compute_diff",
        lambda ws, ex: {"new": [], "unchanged": [], "deleted": [], "renamed": []},
    )
    monkeypatch.setattr(
        scan_module,
        "compute_state_gate",
        lambda repo: {"allowed": True, "reason": "clean", "head_commit": "x"},
    )
    monkeypatch.setattr(scan_module, "build_file_map", lambda *a, **kw: None)

    import frontmatter

    result = await scan_module.run_scan(
        workspace_path=workspace, repo_path=repo, no_file_map=False
    )

    # The test_suite page was created this scan → file map injected.
    assert "test_suite:org/repo/pkg-a/tests" in result.entities_created

    suite_page = wiki / "entities" / "unit_tests_pkg-a.md"
    assert suite_page.exists(), f"suite page not written; entities: {list((wiki / 'entities').glob('*.md'))}"
    text = suite_page.read_text(encoding="utf-8")

    assert "## File map - tests" in text
    assert "| `conftest.py` | file | — TODO |" in text
    assert "| `test_pkg_a.py` | file | — TODO |" in text
    # The template's placeholder file row is gone.
    assert "| `<file>` | file | — TODO |" not in text
    # Neighboring template sections survive injection.
    assert "## Test conventions" in text
    assert "## Coverage" in text
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --package graph-wiki-agent pytest packages/graph-wiki-core/tests/unit/test_scan_graph_integration.py::test_file_map_injected_into_test_suite_entity_page -v`
Expected: FAIL — either `AttributeError` on `scan_module.build_dir_file_map` (not yet imported) or the suite page's `## File map` still shows the template placeholder row (injection branch not implemented).

- [ ] **Step 3: Import `build_dir_file_map` into scan.py**

In `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py`, the `from wiki_io.scan_monorepo import (...)` block is at lines 44-54. Add `build_dir_file_map` to it (alphabetical-ish, next to `build_file_map`):

```python
from wiki_io.scan_monorepo import (
    ExistingPages,
    _load_existing_pages,
    _wiki_relative_path_for,
    attach_changed_files,
    build_dir_file_map,
    build_file_map,
    compute_diff,
    compute_state_gate,
    discover_workspaces,
    regenerate_dependencies_index,
)
```

- [ ] **Step 4: Hoist the collision set + add Step 10b-ts**

In `run_scan`, the package/app file-map block is `if entity_write_result is not None and conn is not None:` at lines 941-989. Two edits inside it:

**(4a)** Hoist the collision set so both branches share it. Find (lines 941-950):

```python
        if entity_write_result is not None and conn is not None:
            refreshed = set(entity_write_result.created) | set(
                entity_write_result.updated
            )
            list_fns = _kind_list_fns()
            fm_list_fns = [list_fns.get("package"), list_fns.get("app")]
            if refreshed and any(fm_list_fns):
                fm_collision_set = _compute_collision_set(
                    conn, ADMITTED_KINDS, _kind_list_fns(),
                )
                ws_fm_by_name = {
```

Replace with (collision set computed once before the inner `if`):

```python
        if entity_write_result is not None and conn is not None:
            refreshed = set(entity_write_result.created) | set(
                entity_write_result.updated
            )
            list_fns = _kind_list_fns()
            # Collision set shared by the package/app and test-suite branches.
            fm_collision_set = (
                _compute_collision_set(conn, ADMITTED_KINDS, list_fns)
                if refreshed
                else frozenset()
            )
            fm_list_fns = [list_fns.get("package"), list_fns.get("app")]
            if refreshed and any(fm_list_fns):
                ws_fm_by_name = {
```

(Only the `fm_collision_set` assignment moved out of the inner `if` and now reuses the already-built `list_fns`. The package/app loop keeps using `fm_collision_set` — `slug = short_filename(node_uri, fm_collision_set)` at line 964 is unchanged.)

**(4b)** Add the test-suite branch. Find the package/app log line at the end of the block (lines 978-989):

```python
            if entities_file_mapped or file_map_errors:
                append_log(
                    wiki,
                    "scan",
                    (
                        f"file maps injected: {len(entities_file_mapped)} "
                        f"(errors: {len(file_map_errors)})"
                    ),
                    detail=None,
                    silent=True,
                    raise_exception=True,
                )
```

Insert the test-suite branch **before** that `if entities_file_mapped or file_map_errors:` log line (so its counts fold into the single log line), still inside the `if entity_write_result is not None and conn is not None:` block:

```python
            # Step 10b-ts: test-suite File-map injection. Mirrors Step 10b but
            # for test_suite entity pages — the suite map starts at the suite
            # root (node.attrs["path"]) and is UNPARTITIONED (every tracked file
            # under the root). Reuses the shared collision set and the same
            # snapshot→merge durability path (preserved=...). Appends each
            # injected page to file_mapped_pages so Step 10c fills its TODO rows.
            if refreshed:
                for node in queries.list_test_suites(conn):
                    if not isinstance(node.attrs, dict):
                        continue
                    suite_uri = node.attrs.get("uri")
                    if not suite_uri or suite_uri not in refreshed:
                        continue
                    suite_path = node.attrs.get("path")
                    if not suite_path:
                        continue
                    block = build_dir_file_map(repo / suite_path, max_depth=max_depth)
                    if not block:
                        continue
                    ts_page_path = _entity_page_path(
                        wiki, "test_suite", node, suite_uri, fm_collision_set,
                    )
                    try:
                        inject_file_map(
                            ts_page_path,
                            block,
                            preserved=prior_file_map_descs.get(suite_uri),
                        )
                        entities_file_mapped.append(suite_uri)
                        file_mapped_pages.append((suite_uri, node, ts_page_path))
                    except Exception as fm_exc:  # noqa: BLE001 — partial-success
                        file_map_errors.append(
                            f"{suite_uri}: inject_file_map failed: {fm_exc!r}"
                        )

            if entities_file_mapped or file_map_errors:
                append_log(
```

- [ ] **Step 5: Run the suite-injection test**

Run: `uv run --package graph-wiki-agent pytest packages/graph-wiki-core/tests/unit/test_scan_graph_integration.py::test_file_map_injected_into_test_suite_entity_page -v`
Expected: PASS.

- [ ] **Step 6: Run the full integration suite (no regression)**

Run: `uv run --package graph-wiki-agent pytest packages/graph-wiki-core/tests/unit/test_scan_graph_integration.py -v`
Expected: PASS — all package/app tests still green (collision-set hoist is behavior-preserving), plus the new suite test.

- [ ] **Step 7: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py packages/graph-wiki-core/tests/unit/test_scan_graph_integration.py
git commit -m "feat(scan): inject test-suite file maps (Step 10b-ts)"
```

---

## Task 4: Step 10c describer scoping for test suites

Step 10c currently does `ws_dict = ws_by_name.get(node.name)`, which is `None` for test-suite nodes (they're not workspace dicts), so suite pages get queued but never described. Synthesize a minimal dict for `test_suite` nodes so `build_file_describer_prompt` + `pick_representative` sample from the suite root.

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py` (Step 10c loop at lines 1002-1009)
- Test: `packages/graph-wiki-core/tests/unit/test_scan_graph_integration.py` (add code-reader-fill test for a suite)

- [ ] **Step 1: Write the failing test**

Add this test at the end of `test_scan_graph_integration.py`:

```python
@pytest.mark.asyncio
async def test_code_reader_fills_test_suite_todo_descriptions(
    tmp_workspace_with_packages, monkeypatch
):
    """Step 10c: after the suite File map is injected with — TODO rows, the
    code_reader fan-out fills the Description cells from the model's
    {path: description} JSON. Proves the synthesized test_suite describer dict
    routes the suite into the describer pool."""
    workspace = tmp_workspace_with_packages
    wiki = workspace / "wiki"
    repo = workspace / "repo"

    db = workspace / ".graph" / "code.db"
    _seed_test_suite_graph(db)

    monkeypatch.setattr(
        scan_module, "_cg_run_build", lambda repo, workspace, *, full: (exit_codes.SUCCESS, "", "")
    )

    suite_block = (
        "## File map - tests\n"
        "TODO — overview of this package's tree.\n"
        "\n"
        "### tests/\n"
        "TODO — describe what this directory contains.\n"
        "\n"
        "| Path | Kind | Description |\n"
        "|---|---|---|\n"
        "| `conftest.py` | file | — TODO |\n"
        "| `test_pkg_a.py` | file | — TODO |\n"
    )
    monkeypatch.setattr(scan_module, "build_dir_file_map", lambda *a, **kw: suite_block)
    monkeypatch.setattr(scan_module, "discover_workspaces", lambda *a, **kw: [])
    monkeypatch.setattr(scan_module, "_load_existing_pages", lambda wiki: __import__("wiki_io.scan_monorepo", fromlist=["ExistingPages"]).ExistingPages(legacy={}, entities={}))
    monkeypatch.setattr(scan_module, "attach_changed_files", lambda *a, **kw: None)
    monkeypatch.setattr(
        scan_module,
        "compute_diff",
        lambda ws, ex: {"new": [], "unchanged": [], "deleted": [], "renamed": []},
    )
    monkeypatch.setattr(
        scan_module,
        "compute_state_gate",
        lambda repo: {"allowed": True, "reason": "clean", "head_commit": "x"},
    )
    monkeypatch.setattr(scan_module, "build_file_map", lambda *a, **kw: None)

    from subagent_runtime.pool import FanOutResult

    captured_paths: dict = {}

    async def _role_aware_run_all(self, *, items, task, role, model_id, max_concurrency):
        res = FanOutResult()
        if role == "code_reader":
            for it in items:
                uri_inner, ws_dict, _page, todo_paths = it
                captured_paths[uri_inner] = (ws_dict, list(todo_paths))
                obj = {p: f"desc for {p}" for p in todo_paths}
                res.successes.append((it, json.dumps(obj)))
        return res

    monkeypatch.setattr(scan_module.SubagentPool, "run_all", _role_aware_run_all)

    await scan_module.run_scan(
        workspace_path=workspace, repo_path=repo, no_file_map=False
    )

    # The suite was routed into the code_reader pool with a synthesized dict.
    suite_uri = "test_suite:org/repo/pkg-a/tests"
    assert suite_uri in captured_paths, f"suite not dispatched to describer; got {captured_paths}"
    ws_dict, todo = captured_paths[suite_uri]
    assert ws_dict["type"] == "test_suite"
    assert ws_dict["path"] == "packages/pkg-a/tests"
    assert ws_dict["language"] == "python"
    assert set(todo) == {"conftest.py", "test_pkg_a.py"}

    text = (wiki / "entities" / "unit_tests_pkg-a.md").read_text(encoding="utf-8")
    assert "| `conftest.py` | file | desc for conftest.py |" in text
    assert "| `test_pkg_a.py` | file | desc for test_pkg_a.py |" in text
    assert "— TODO" not in text
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --package graph-wiki-agent pytest packages/graph-wiki-core/tests/unit/test_scan_graph_integration.py::test_code_reader_fills_test_suite_todo_descriptions -v`
Expected: FAIL — `suite_uri not in captured_paths` (the suite is skipped because `ws_by_name.get(node.name)` is `None`), so the `assert suite_uri in captured_paths` fails.

- [ ] **Step 3: Synthesize the describer dict for test_suite nodes**

In `run_scan`, Step 10c builds `describer_items` at lines 1002-1009:

```python
            for node_uri, node, page_path in file_mapped_pages:
                todo_paths = file_map_todo_paths(page_path)
                if not todo_paths:
                    continue
                ws_dict = ws_by_name.get(node.name)
                if ws_dict is None:
                    continue
                describer_items.append((node_uri, ws_dict, page_path, todo_paths))
```

Replace with (synthesize a minimal dict for test_suite nodes; package/app path unchanged):

```python
            for node_uri, node, page_path in file_mapped_pages:
                todo_paths = file_map_todo_paths(page_path)
                if not todo_paths:
                    continue
                if node.kind == "test_suite":
                    attrs = node.attrs if isinstance(node.attrs, dict) else {}
                    ws_dict: dict | None = {
                        "name": node.name,
                        "path": attrs.get("path"),
                        "type": "test_suite",
                        "language": attrs.get("language", "unknown"),
                    }
                else:
                    ws_dict = ws_by_name.get(node.name)
                    if ws_dict is None:
                        continue
                describer_items.append((node_uri, ws_dict, page_path, todo_paths))
```

- [ ] **Step 4: Run the code-reader-fill test**

Run: `uv run --package graph-wiki-agent pytest packages/graph-wiki-core/tests/unit/test_scan_graph_integration.py::test_code_reader_fills_test_suite_todo_descriptions -v`
Expected: PASS.

- [ ] **Step 5: Run the full integration suite**

Run: `uv run --package graph-wiki-agent pytest packages/graph-wiki-core/tests/unit/test_scan_graph_integration.py -v`
Expected: PASS (all tests).

- [ ] **Step 6: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py packages/graph-wiki-core/tests/unit/test_scan_graph_integration.py
git commit -m "feat(scan): describe test-suite file maps via synthesized code_reader dict"
```

---

## Task 5: Durability — descriptions survive rescan, no model call

Confirm the snapshot→merge round-trip preserves a filled suite description across a rescan and that a fully-described suite triggers **no** code_reader call. This should work entirely via reused machinery (Task 3's `preserved=...` + `file_map_todo_paths`), so this task is primarily a test that locks the behavior.

**Files:**
- Test: `packages/graph-wiki-core/tests/unit/test_scan_graph_integration.py` (add durability test)

- [ ] **Step 1: Write the test**

Add at the end of `test_scan_graph_integration.py`:

```python
@pytest.mark.asyncio
async def test_test_suite_file_map_descriptions_survive_rescan(
    tmp_workspace_with_packages, monkeypatch
):
    """Durability: descriptions filled into a suite's File map survive a rescan
    (write_entities re-renders the body; snapshot+merge restores them). A fully
    described suite triggers NO code_reader call on the second scan."""
    workspace = tmp_workspace_with_packages
    wiki = workspace / "wiki"
    repo = workspace / "repo"

    db = workspace / ".graph" / "code.db"
    _seed_test_suite_graph(db)

    monkeypatch.setattr(
        scan_module, "_cg_run_build", lambda repo, workspace, *, full: (exit_codes.SUCCESS, "", "")
    )

    suite_block = (
        "## File map - tests\n"
        "TODO — overview of this package's tree.\n"
        "\n"
        "### tests/\n"
        "TODO — describe what this directory contains.\n"
        "\n"
        "| Path | Kind | Description |\n"
        "|---|---|---|\n"
        "| `conftest.py` | file | — TODO |\n"
        "| `test_pkg_a.py` | file | — TODO |\n"
    )
    monkeypatch.setattr(scan_module, "build_dir_file_map", lambda *a, **kw: suite_block)
    monkeypatch.setattr(scan_module, "discover_workspaces", lambda *a, **kw: [])
    monkeypatch.setattr(scan_module, "_load_existing_pages", lambda wiki: __import__("wiki_io.scan_monorepo", fromlist=["ExistingPages"]).ExistingPages(legacy={}, entities={}))
    monkeypatch.setattr(scan_module, "attach_changed_files", lambda *a, **kw: None)
    monkeypatch.setattr(
        scan_module,
        "compute_diff",
        lambda ws, ex: {"new": [], "unchanged": [], "deleted": [], "renamed": []},
    )
    monkeypatch.setattr(
        scan_module,
        "compute_state_gate",
        lambda repo: {"allowed": True, "reason": "clean", "head_commit": "x"},
    )
    monkeypatch.setattr(scan_module, "build_file_map", lambda *a, **kw: None)

    from subagent_runtime.pool import FanOutResult

    code_reader_dispatches: list[list] = []

    async def _recording_run_all(self, *, items, task, role, model_id, max_concurrency):
        if role == "code_reader":
            code_reader_dispatches.append([it[0] for it in items])
        return FanOutResult()

    monkeypatch.setattr(scan_module.SubagentPool, "run_all", _recording_run_all)

    import frontmatter

    # Scan 1: suite page created, File map injected with — TODO rows.
    await scan_module.run_scan(workspace_path=workspace, repo_path=repo, no_file_map=False)
    suite_page = wiki / "entities" / "unit_tests_pkg-a.md"
    assert suite_page.exists()

    # Human fills BOTH descriptions.
    filled = suite_page.read_text(encoding="utf-8")
    filled = filled.replace(
        "| `conftest.py` | file | — TODO |",
        "| `conftest.py` | file | shared pytest fixtures |",
    ).replace(
        "| `test_pkg_a.py` | file | — TODO |",
        "| `test_pkg_a.py` | file | unit tests for pkg-a |",
    )
    suite_page.write_text(filled, encoding="utf-8")

    code_reader_dispatches.clear()

    # Scan 2: write_entities re-renders the body; snapshot+merge must restore both.
    await scan_module.run_scan(workspace_path=workspace, repo_path=repo, no_file_map=False)

    text2 = suite_page.read_text(encoding="utf-8")
    assert "| `conftest.py` | file | shared pytest fixtures |" in text2, (
        f"filled description wiped on rescan; page:\n{text2}"
    )
    assert "| `test_pkg_a.py` | file | unit tests for pkg-a |" in text2
    assert "— TODO" not in text2

    # A fully-described suite has no TODO paths → no code_reader dispatch at all.
    flat = [uri for batch in code_reader_dispatches for uri in batch]
    assert "test_suite:org/repo/pkg-a/tests" not in flat, (
        f"fully-described suite should trigger no describer call; dispatches={code_reader_dispatches}"
    )
```

- [ ] **Step 2: Run the durability test**

Run: `uv run --package graph-wiki-agent pytest packages/graph-wiki-core/tests/unit/test_scan_graph_integration.py::test_test_suite_file_map_descriptions_survive_rescan -v`
Expected: PASS. (If it fails on the "wiped on rescan" assertion, the snapshot label/merge keys are misaligned — verify `build_dir_file_map` labels the heading with the suite-root basename `path.name`, matching what the snapshot strips. This is the load-bearing durability invariant from the spec.)

- [ ] **Step 3: Run the full integration suite + both package suites**

Run:
```bash
uv run --package graph-wiki-agent pytest packages/graph-wiki-core/tests/unit/test_scan_graph_integration.py -v
uv run --package wiki-io pytest packages/wiki-io/tests/test_scan_monorepo.py -v
```
Expected: PASS for both.

- [ ] **Step 4: Commit**

```bash
git add packages/graph-wiki-core/tests/unit/test_scan_graph_integration.py
git commit -m "test(scan): test-suite file-map descriptions survive rescan, no model call"
```

---

## Deferred (intentionally out of this plan)

**Narrator hint (spec §4).** The spec marks passing the suite's file map to the narrator for `kind == "test_suite"` as "Optional — may be dropped to keep scope minimal without affecting the core feature." It is dropped here: the narrator fan-out (Step 9b, `scan.py:832-873`) runs **before** the file maps are built (Step 10b/10b-ts), so wiring this would require either pre-computing suite maps before narration or calling `build_dir_file_map` a second time inside the narrator closure. That's added complexity (and an extra git subprocess per suite) for a grounding hint the spec explicitly calls droppable. The core deliverable — a populated, durable, describable `## File map` on test-suite pages — is complete without it. Revisit only if suite narratives prove too thin in practice.

**Sparse describer snippets for suites (known limitation, not a bug to fix here).** Step 10c's `pick_representative` (`scan.py:175`) skips files whose names contain `test`/`spec`/`fixture`/`mock`, so for a test-suite root most files are filtered out and the describer prompt gets few or no code snippets. The spec scopes Step 10c as "reused, unchanged," and `build_file_describer_prompt` treats snippets as best-effort context (metadata + the TODO path list still drive the descriptions). Improving snippet sampling for test directories is a separate enhancement, not part of this feature.

---

## Self-review notes

- **Spec coverage:** §1 builder → Task 1. §2 Step 10b-ts (refreshed filter, suite-root resolution, suite-aware slug via shared helper, append to `file_mapped_pages`, folded log) → Tasks 2-3. §3 Step 10c synthesized dict → Task 4. §4 narrator hint → Deferred (spec-sanctioned). Durability §1-3 → Task 5. Testing (unit builder + integration injection/durability) → Tasks 1, 3, 4, 5.
- **Type consistency:** `build_dir_file_map(path, max_depth=4, max_entries=80) -> str | None` (Task 1) is called as `build_dir_file_map(repo / suite_path, max_depth=max_depth)` (Task 3). `_entity_page_path(wiki, kind, node, uri, collision_set) -> Path` (Task 2) is called identically in the narrator block (Task 2) and Step 10b-ts (Task 3). `file_mapped_pages` entries are `(uri, node, page_path)` tuples in both the package/app branch and the suite branch, consumed uniformly by Step 10c.
- **No double-listing:** package/app maps stay prod-only (`build_file_map` untouched); the suite page is the sole home for the test tree.
