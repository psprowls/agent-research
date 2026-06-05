# Extend `gw scan` File Maps to App Entity Pages — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `gw scan` populate the `## File map` section on **app** entity pages with the same treatment package pages already get — deterministic path/kind rows injected, then code-reader fan-out fills per-file descriptions, with descriptions preserved across rescans.

**Architecture:** The scan pipeline already builds file maps for every workspace (apps included), snapshots descriptions kind-agnostically, and runs a kind-agnostic LLM description-fill (Step 10c). The *only* gap is Step 10b, which injects deterministic rows but iterates `package` nodes only. Extending Step 10b to also iterate `app` nodes lights up the entire downstream path with no other production change. A one-word log-wording fix in Step 10c follows for accuracy.

**Tech Stack:** Python 3.11+, `uv` workspace, `pytest` + `pytest-asyncio` (`asyncio_mode = "auto"`), sqlite-backed `graph_io`, `wiki_io.entity_writer`. LLM/Bedrock is mocked at the `SubagentPool.run_all` boundary — no live model calls.

**Source of truth:** `docs/superpowers/specs/2026-06-01-app-file-maps-design.md`

---

## Background the engineer needs

**The scan pipeline (in `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py`, function `run_scan`):**

- **Step 9a** (`scan.py:801`): `write_entities(conn, wiki, ADMITTED_KINDS)` renders one `wiki/entities/<slug>.md` page per graph node whose kind is admitted. `ADMITTED_KINDS` includes both `"package"` and `"app"` (`wiki_io/entity_writer.py:60`). Returns `entity_write_result` with `.created` / `.updated` (lists of node URIs touched this scan).
- **Step 10b** (`scan.py:941-975`): For each **package** node whose URI is in `refreshed = created | updated`, replaces that page's `## File map` section with the deterministic block from `workspaces[*]["file_map"]` (path + kind rows, Description cells left as `— TODO`). `inject_file_map(preserved=...)` merges back any prior descriptions. **This is the only place that hard-codes `package`.**
- **Step 10c** (`scan.py:989-1067`): For each page Step 10b just injected (tracked in `file_mapped_pages`) that still has `— TODO` rows, dispatches a `code_reader` subagent to fill the Description cells. Already kind-agnostic — it keys off `file_mapped_pages`.
- **Durability snapshot** `_snapshot_file_map_descriptions` (`scan.py:135`): runs BEFORE Step 9a re-renders pages, capturing filled Description cells by URI so Step 10b can restore them. Already kind-agnostic.

**Kind list functions** (`wiki_io/entity_writer.py:548`, `_kind_list_fns`) returns a dict mapping kind → `lambda conn: _queries.list_<kind>(conn)`. Relevant: `"package"` → `list_packages`, `"app"` → `list_apps`. Both return `NodeRecord` objects with `.name` and `.attrs["uri"]`.

**App URI scheme:** `app:{org}/{repo}/{name}` (`graph_io/uri.py:25`). Package scheme is `pkg:{org}/{repo}/{name}`.

**App template:** `wiki_io/assets/page-templates/entity-app.md:36-44` already ships a `## File map - {{app_name}}` section to inject into.

**How to run one test (from repo root):**
```bash
uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_scan_graph_integration.py::TEST_NAME -v
```

**Test-pattern reference:** The package equivalents of every test below already exist in `packages/graph-wiki-core/tests/unit/test_scan_graph_integration.py`:
- `test_file_map_injected_into_package_entity_page` (line 545)
- `test_file_map_descriptions_survive_rescan` (line 642)
- `test_code_reader_fanout_fills_todo_descriptions` (line 735)

The app tests in this plan mirror those exactly, swapping `package`/`pkg-a` for `app`/`app-x`. The module's autouse fixtures (`stub_pool_run_all`, `stub_make_llm`, and a stubbed role config) already neutralize Bedrock. `append_log` is **not** patched in this module, so it writes real entries to `wiki/log.md` — Task 4 asserts against that file.

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py` | Scan pipeline | Step 10b: iterate `package` **and** `app` nodes (Task 1). Step 10c: broaden log noun (Task 4). |
| `packages/graph-wiki-core/tests/unit/test_scan_graph_integration.py` | Scan→graph integration tests | Add `_seed_app_graph` helper + 3 app tests (Tasks 1–3) + 1 log-wording test (Task 4). |

No new files. No changes to `wiki_io` — `inject_file_map`, `_compute_collision_set`, `_snapshot_file_map_descriptions`, and Step 10c are already kind-agnostic.

---

### Task 1: Inject deterministic File-map rows into app entity pages (Step 10b)

This task contains the core production change and the first app test. The test fails on `main` (app pages keep their empty `## File map` template placeholder); the Step 10b change makes it pass.

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py:925-953`
- Test: `packages/graph-wiki-core/tests/unit/test_scan_graph_integration.py` (add `_seed_app_graph` helper + new test)

- [ ] **Step 1: Add the `_seed_app_graph` test helper**

Add this helper immediately after `_seed_minimal_graph` (ends at `test_scan_graph_integration.py:90`). It seeds a single `app` node into a fresh graph DB. Tasks 2 and 3 reuse it.

```python
def _seed_app_graph(db_path: Path) -> None:
    """Create a minimal sqlite DB with one `app` kind node.

    Layout:
      app node: app-x  (uri app:org/repo/app-x, path apps/app-x)

    Mirrors _seed_minimal_graph but seeds an app instead of packages. The
    `app:` uri scheme matches graph_io/uri.py:app_uri. No domain/repo nodes
    are needed — write_entities renders any admitted kind that has nodes.
    """
    from graph_io import schema

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        schema.apply_schema(conn)
        conn.execute(
            "INSERT INTO nodes(kind, name, path, line, attrs_json, uri) VALUES "
            "('app', 'app-x', 'apps/app-x', NULL, '{\"language\": \"python\"}', 'app:org/repo/app-x')"
        )
        conn.commit()
    finally:
        conn.close()
```

- [ ] **Step 2: Write the failing app-injection test**

Add this test to `test_scan_graph_integration.py` (place it next to `test_file_map_injected_into_package_entity_page`, after line 640). It mirrors the package test but seeds an app node and asserts the app entity page receives the injected deterministic rows.

```python
@pytest.mark.asyncio
async def test_file_map_injected_into_app_entity_page(
    tmp_workspace_with_packages, monkeypatch
):
    """File-map injection (apps): after write_entities creates an app entity
    page, run_scan replaces its `## File map` section with the deterministic
    `w["file_map"]` block (path + kind rows). Verified end-to-end against the
    real write_entities + packaged entity-app.md template. App parity with
    test_file_map_injected_into_package_entity_page.
    """
    workspace = tmp_workspace_with_packages
    wiki = workspace / "wiki"
    repo = workspace / "repo"

    db = workspace / ".graph" / "code.db"
    _seed_app_graph(db)

    monkeypatch.setattr(
        scan_module, "_cg_run_build", lambda repo, workspace, *, full: (exit_codes.SUCCESS, "", "")
    )

    # Deterministic file-map block as build_file_map would emit it for app-x.
    app_x_block = (
        "## File map - app-x\n"
        "TODO — overview of this app's tree.\n"
        "\n"
        "### app-x/\n"
        "TODO — describe what this directory contains.\n"
        "\n"
        "| Path | Kind | Description |\n"
        "|---|---|---|\n"
        "| `pyproject.toml` | file | — TODO |\n"
        "| `src/app_x/__init__.py` | file | — TODO |\n"
    )

    fake_workspaces = [
        {
            "name": "app-x",
            "path": "apps/app-x",
            "wiki_relative_path": "apps/app-x/overview.md",
            "type": "app",
            "language": "python",
            "changed_files": None,
            # Preset file_map survives because build_file_map is stubbed to None.
            "file_map": app_x_block,
        },
    ]
    monkeypatch.setattr(scan_module, "discover_workspaces", lambda *a, **kw: fake_workspaces)
    monkeypatch.setattr(scan_module, "_load_existing_pages", lambda wiki: __import__("wiki_io.scan_monorepo", fromlist=["ExistingPages"]).ExistingPages(legacy={}, entities={}))
    monkeypatch.setattr(scan_module, "attach_changed_files", lambda *a, **kw: None)
    monkeypatch.setattr(
        scan_module,
        "compute_diff",
        lambda ws, ex: {"new": ["app-x"], "unchanged": [], "deleted": [], "renamed": []},
    )
    monkeypatch.setattr(
        scan_module,
        "compute_state_gate",
        lambda repo: {"allowed": True, "reason": "clean", "head_commit": "x"},
    )
    # Keep the preset file_map values (do not overwrite via real build_file_map).
    monkeypatch.setattr(scan_module, "build_file_map", lambda *a, **kw: None)

    result = await scan_module.run_scan(
        workspace_path=workspace, repo_path=repo, no_file_map=False
    )

    # app-x was created this scan → its file map should be injected.
    assert "app:org/repo/app-x" in result.entities_created

    # Find the entity page for app-x by its frontmatter uri.
    import frontmatter

    entities = sorted((wiki / "entities").glob("*.md"))
    assert entities, "no entity pages written"
    app_x_page = next(
        p for p in entities if frontmatter.load(p).metadata.get("uri") == "app:org/repo/app-x"
    )
    text = app_x_page.read_text(encoding="utf-8")

    # Deterministic rows landed; the empty template placeholder rows are gone.
    assert "| `pyproject.toml` | file | — TODO |" in text
    assert "| `src/app_x/__init__.py` | file | — TODO |" in text
    assert "<Short description of file contents.>" not in text
    assert text.count("## File map - app-x") == 1
```

> Note: the package test uses `result = asyncio.run(scan_module.run_scan(...))` because it is a plain `def`. The module runs under `asyncio_mode = "auto"`, so writing these as `async def` + `@pytest.mark.asyncio` and `await`-ing `run_scan` directly is equivalent and cleaner. Either form works; this plan uses `async def` consistently. If you prefer to match the surrounding `def` + `asyncio.run` style exactly, do that instead — just be consistent within the test.

- [ ] **Step 3: Run the test to verify it fails**

Run:
```bash
uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_scan_graph_integration.py::test_file_map_injected_into_app_entity_page -v
```
Expected: **FAIL**. The app page is written but Step 10b skips app nodes, so the `— TODO` rows are never injected — the assertion `"| `pyproject.toml` | file | — TODO |" in text` fails (the page still holds the template's `<file>` / `<Short description of file contents.>` placeholder).

- [ ] **Step 4: Extend Step 10b to iterate package and app nodes**

In `scan.py`, replace the package-only setup. Current code (`scan.py:945-953`):

```python
            pkg_list_fn = _kind_list_fns().get("package")
            if refreshed and pkg_list_fn is not None:
                fm_collision_set = _compute_collision_set(
                    conn, ADMITTED_KINDS, _kind_list_fns(),
                )
                ws_fm_by_name = {
                    unscope(w["name"]): w.get("file_map", "") for w in workspaces
                }
                for node in pkg_list_fn(conn):
```

Replace with:

```python
            list_fns = _kind_list_fns()
            fm_list_fns = [list_fns.get("package"), list_fns.get("app")]
            if refreshed and any(fm_list_fns):
                fm_collision_set = _compute_collision_set(
                    conn, ADMITTED_KINDS, _kind_list_fns(),
                )
                ws_fm_by_name = {
                    unscope(w["name"]): w.get("file_map", "") for w in workspaces
                }
                fm_nodes = [n for fn in fm_list_fns if fn for n in fn(conn)]
                for node in fm_nodes:
```

Everything inside the `for node in ...:` loop body (`scan.py:954-975`) stays **unchanged** — `_compute_collision_set`, `inject_file_map(preserved=...)`, the `refreshed`-set guard, and `file_mapped_pages.append(...)` are all kind-agnostic.

Also broaden the one inaccurate word in the explanatory comment directly above (`scan.py:925-928`). Current:

```python
        # Step 10b: deterministic File-map injection (faithful port of the
        # plugin scanner-agent step). For every `package` entity page that
        # write_entities (re)wrote this scan — created or updated, i.e. whose
        # `## File map` section was just reset to the empty template — replace
```

Change `For every `package` entity page` to `For every `package`/`app` entity page`:

```python
        # Step 10b: deterministic File-map injection (faithful port of the
        # plugin scanner-agent step). For every `package`/`app` entity page that
        # write_entities (re)wrote this scan — created or updated, i.e. whose
        # `## File map` section was just reset to the empty template — replace
```

Leave the rest of the comment block untouched.

- [ ] **Step 5: Run the test to verify it passes**

Run:
```bash
uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_scan_graph_integration.py::test_file_map_injected_into_app_entity_page -v
```
Expected: **PASS**.

- [ ] **Step 6: Run the existing package file-map tests to confirm no regression**

Run:
```bash
uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_scan_graph_integration.py -k "file_map or code_reader" -v
```
Expected: **PASS** for `test_file_map_injected_into_package_entity_page`, `test_file_map_descriptions_survive_rescan`, `test_code_reader_fanout_fills_todo_descriptions`, and the new app test. The package path is unchanged behaviorally — `package` is still first in `fm_list_fns`, and `any(fm_list_fns)` is true whenever `package` resolves.

- [ ] **Step 7: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py packages/graph-wiki-core/tests/unit/test_scan_graph_integration.py
git commit -m "feat(scan): inject deterministic file-map rows into app entity pages

Step 10b iterated package nodes only; extend it to package + app so app
entity pages receive the same deterministic path/kind rows. Loop body,
collision set, and inject_file_map(preserved=...) are unchanged.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: App descriptions are filled by the code-reader fan-out (Step 10c flow-through)

Step 10c is already kind-agnostic — once Task 1 puts app pages into `file_mapped_pages`, the code-reader fan-out fills their `— TODO` cells with **no further production change**. This task adds the test that proves it. (The test fails on `main`/pre-Task-1 because apps never reach `file_mapped_pages`; it passes once Task 1 is merged. Treat it as the regression guard for the flow-through claim.)

**Files:**
- Test: `packages/graph-wiki-core/tests/unit/test_scan_graph_integration.py` (uses `_seed_app_graph` added in Task 1)

- [ ] **Step 1: Write the app description-fill test**

Mirrors `test_code_reader_fanout_fills_todo_descriptions` (line 735), swapping in the app seed. The `_role_aware_run_all` stub returns a `{path: description}` JSON for `code_reader` items and leaves the narrator pool empty.

```python
@pytest.mark.asyncio
async def test_code_reader_fanout_fills_app_todo_descriptions(
    tmp_workspace_with_packages, monkeypatch
):
    """Step 10c (apps): after the deterministic File map is injected with — TODO
    rows on an app page, the code_reader fan-out fills the Description cells from
    the model's {path: description} JSON. Proves Step 10c is kind-agnostic once
    Task 1 lands apps in file_mapped_pages.
    """
    workspace = tmp_workspace_with_packages
    wiki = workspace / "wiki"
    repo = workspace / "repo"

    db = workspace / ".graph" / "code.db"
    _seed_app_graph(db)

    monkeypatch.setattr(
        scan_module, "_cg_run_build", lambda repo, workspace, *, full: (exit_codes.SUCCESS, "", "")
    )

    app_x_block = (
        "## File map - app-x\n"
        "TODO — overview of this app's tree.\n"
        "\n"
        "### app-x/\n"
        "TODO — describe what this directory contains.\n"
        "\n"
        "| Path | Kind | Description |\n"
        "|---|---|---|\n"
        "| `pyproject.toml` | file | — TODO |\n"
        "| `src/app_x/__init__.py` | file | — TODO |\n"
    )

    fake_workspaces = [
        {
            "name": "app-x",
            "path": "apps/app-x",
            "wiki_relative_path": "apps/app-x/overview.md",
            "type": "app",
            "language": "python",
            "changed_files": None,
            "file_map": app_x_block,
        },
    ]
    monkeypatch.setattr(scan_module, "discover_workspaces", lambda *a, **kw: fake_workspaces)
    monkeypatch.setattr(scan_module, "_load_existing_pages", lambda wiki: __import__("wiki_io.scan_monorepo", fromlist=["ExistingPages"]).ExistingPages(legacy={}, entities={}))
    monkeypatch.setattr(scan_module, "attach_changed_files", lambda *a, **kw: None)
    monkeypatch.setattr(
        scan_module,
        "compute_diff",
        lambda ws, ex: {"new": ["app-x"], "unchanged": [], "deleted": [], "renamed": []},
    )
    monkeypatch.setattr(
        scan_module,
        "compute_state_gate",
        lambda repo: {"allowed": True, "reason": "clean", "head_commit": "x"},
    )
    monkeypatch.setattr(scan_module, "build_file_map", lambda *a, **kw: None)

    # Override the autouse empty-pool stub: the code_reader pool returns a
    # {path: description} JSON for each item's todo paths; the narrator pool
    # (role != code_reader) stays empty.
    from subagent_runtime.pool import FanOutResult

    async def _role_aware_run_all(self, *, items, task, role, model_id, max_concurrency):
        res = FanOutResult()
        if role == "code_reader":
            for it in items:
                _uri, _ws, _page, todo_paths = it
                obj = {p: f"desc for {p}" for p in todo_paths}
                res.successes.append((it, json.dumps(obj)))
        return res

    monkeypatch.setattr(scan_module.SubagentPool, "run_all", _role_aware_run_all)

    import frontmatter

    await scan_module.run_scan(
        workspace_path=workspace, repo_path=repo, no_file_map=False
    )

    app_x_page = next(
        p
        for p in (wiki / "entities").glob("*.md")
        if frontmatter.load(p).metadata.get("uri") == "app:org/repo/app-x"
    )
    text = app_x_page.read_text(encoding="utf-8")

    # The — TODO placeholders were replaced by the model's descriptions.
    assert "| `pyproject.toml` | file | desc for pyproject.toml |" in text
    assert (
        "| `src/app_x/__init__.py` | file | desc for src/app_x/__init__.py |"
        in text
    )
    assert "— TODO" not in text
```

- [ ] **Step 2: Run the test to verify it passes**

Run:
```bash
uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_scan_graph_integration.py::test_code_reader_fanout_fills_app_todo_descriptions -v
```
Expected: **PASS** (Task 1 already enabled the flow-through; no production change in this task). If it fails, Task 1's Step 10b change is incomplete — apps are not reaching `file_mapped_pages`.

- [ ] **Step 3: Commit**

```bash
git add packages/graph-wiki-core/tests/unit/test_scan_graph_integration.py
git commit -m "test(scan): code-reader fan-out fills app file-map descriptions

Regression guard proving Step 10c is kind-agnostic for app pages.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Filled app descriptions survive a rescan (durability flow-through)

The snapshot/merge path (`_snapshot_file_map_descriptions` + `inject_file_map(preserved=...)`) is kind-agnostic, so a human/ingest-filled app description must survive a second scan that re-renders the page from template. No production change — this test proves it.

**Files:**
- Test: `packages/graph-wiki-core/tests/unit/test_scan_graph_integration.py` (uses `_seed_app_graph` from Task 1)

- [ ] **Step 1: Write the app rescan-durability test**

Mirrors `test_file_map_descriptions_survive_rescan` (line 642) for an app.

```python
@pytest.mark.asyncio
async def test_app_file_map_descriptions_survive_rescan(
    tmp_workspace_with_packages, monkeypatch
):
    """Durability (apps): a Description filled into an app's File-map table
    survives a rescan, even though write_entities re-renders the page body from
    template. The snapshot-before-write_entities pass captures the filled cell;
    Step 10b inject_file_map(preserved=...) restores it. App parity with
    test_file_map_descriptions_survive_rescan.
    """
    workspace = tmp_workspace_with_packages
    wiki = workspace / "wiki"
    repo = workspace / "repo"

    db = workspace / ".graph" / "code.db"
    _seed_app_graph(db)

    monkeypatch.setattr(
        scan_module, "_cg_run_build", lambda repo, workspace, *, full: (exit_codes.SUCCESS, "", "")
    )

    app_x_block = (
        "## File map - app-x\n"
        "TODO — overview of this app's tree.\n"
        "\n"
        "### app-x/\n"
        "TODO — describe what this directory contains.\n"
        "\n"
        "| Path | Kind | Description |\n"
        "|---|---|---|\n"
        "| `pyproject.toml` | file | — TODO |\n"
        "| `src/app_x/__init__.py` | file | — TODO |\n"
    )

    fake_workspaces = [
        {
            "name": "app-x",
            "path": "apps/app-x",
            "wiki_relative_path": "apps/app-x/overview.md",
            "type": "app",
            "language": "python",
            "changed_files": None,
            "file_map": app_x_block,
        },
    ]
    monkeypatch.setattr(scan_module, "discover_workspaces", lambda *a, **kw: fake_workspaces)
    monkeypatch.setattr(scan_module, "_load_existing_pages", lambda wiki: __import__("wiki_io.scan_monorepo", fromlist=["ExistingPages"]).ExistingPages(legacy={}, entities={}))
    monkeypatch.setattr(scan_module, "attach_changed_files", lambda *a, **kw: None)
    monkeypatch.setattr(
        scan_module,
        "compute_diff",
        lambda ws, ex: {"new": ["app-x"], "unchanged": [], "deleted": [], "renamed": []},
    )
    monkeypatch.setattr(
        scan_module,
        "compute_state_gate",
        lambda repo: {"allowed": True, "reason": "clean", "head_commit": "x"},
    )
    monkeypatch.setattr(scan_module, "build_file_map", lambda *a, **kw: None)

    import frontmatter

    # Scan 1: page created, File map injected with — TODO rows.
    await scan_module.run_scan(
        workspace_path=workspace, repo_path=repo, no_file_map=False
    )
    app_x_page = next(
        p
        for p in (wiki / "entities").glob("*.md")
        if frontmatter.load(p).metadata.get("uri") == "app:org/repo/app-x"
    )

    # Human/ingest fills one description (the other stays — TODO).
    filled = app_x_page.read_text(encoding="utf-8").replace(
        "| `src/app_x/__init__.py` | file | — TODO |",
        "| `src/app_x/__init__.py` | file | the app entrypoint |",
    )
    app_x_page.write_text(filled, encoding="utf-8")

    # Scan 2: write_entities re-renders the page body from template (wiping the
    # injected File map); the snapshot+merge must restore the filled cell.
    await scan_module.run_scan(
        workspace_path=workspace, repo_path=repo, no_file_map=False
    )

    text2 = app_x_page.read_text(encoding="utf-8")
    assert "| `src/app_x/__init__.py` | file | the app entrypoint |" in text2, (
        f"filled description was wiped on rescan; page:\n{text2}"
    )
    # The un-filled row remains a — TODO placeholder.
    assert "| `pyproject.toml` | file | — TODO |" in text2
```

- [ ] **Step 2: Run the test to verify it passes**

Run:
```bash
uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_scan_graph_integration.py::test_app_file_map_descriptions_survive_rescan -v
```
Expected: **PASS**. The autouse `stub_pool_run_all` keeps the code-reader pool empty, so Scan 2's only effect on descriptions is the snapshot/merge restore.

- [ ] **Step 3: Commit**

```bash
git add packages/graph-wiki-core/tests/unit/test_scan_graph_integration.py
git commit -m "test(scan): app file-map descriptions survive rescan

Regression guard proving the snapshot/merge durability path covers apps.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Broaden the Step 10c description-fill log wording

The Step 10c log line hard-codes `package(s)` (`scan.py:1062`). Now that apps flow through the same path, the noun is inaccurate. Broaden it to `entity(s)`.

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py:1056-1067`
- Test: `packages/graph-wiki-core/tests/unit/test_scan_graph_integration.py`

- [ ] **Step 1: Write the failing log-wording test**

`append_log` is not patched in this module, so it writes real entries to `wiki/log.md`. This test runs an app description-fill scan and asserts the log line uses the broadened noun. It mirrors Task 2's setup (code-reader pool returns descriptions, so the `file descriptions filled` log line is emitted).

```python
@pytest.mark.asyncio
async def test_description_fill_log_uses_entity_noun(
    tmp_workspace_with_packages, monkeypatch
):
    """Step 10c log wording: the `file descriptions filled` line must read
    `entity(s)`, not `package(s)`, now that apps share the path. Asserts against
    the real log.md (append_log is unpatched in this module).
    """
    workspace = tmp_workspace_with_packages
    wiki = workspace / "wiki"
    repo = workspace / "repo"

    db = workspace / ".graph" / "code.db"
    _seed_app_graph(db)

    monkeypatch.setattr(
        scan_module, "_cg_run_build", lambda repo, workspace, *, full: (exit_codes.SUCCESS, "", "")
    )

    app_x_block = (
        "## File map - app-x\n"
        "TODO — overview of this app's tree.\n"
        "\n"
        "### app-x/\n"
        "TODO — describe what this directory contains.\n"
        "\n"
        "| Path | Kind | Description |\n"
        "|---|---|---|\n"
        "| `pyproject.toml` | file | — TODO |\n"
    )

    fake_workspaces = [
        {
            "name": "app-x",
            "path": "apps/app-x",
            "wiki_relative_path": "apps/app-x/overview.md",
            "type": "app",
            "language": "python",
            "changed_files": None,
            "file_map": app_x_block,
        },
    ]
    monkeypatch.setattr(scan_module, "discover_workspaces", lambda *a, **kw: fake_workspaces)
    monkeypatch.setattr(scan_module, "_load_existing_pages", lambda wiki: __import__("wiki_io.scan_monorepo", fromlist=["ExistingPages"]).ExistingPages(legacy={}, entities={}))
    monkeypatch.setattr(scan_module, "attach_changed_files", lambda *a, **kw: None)
    monkeypatch.setattr(
        scan_module,
        "compute_diff",
        lambda ws, ex: {"new": ["app-x"], "unchanged": [], "deleted": [], "renamed": []},
    )
    monkeypatch.setattr(
        scan_module,
        "compute_state_gate",
        lambda repo: {"allowed": True, "reason": "clean", "head_commit": "x"},
    )
    monkeypatch.setattr(scan_module, "build_file_map", lambda *a, **kw: None)

    from subagent_runtime.pool import FanOutResult

    async def _role_aware_run_all(self, *, items, task, role, model_id, max_concurrency):
        res = FanOutResult()
        if role == "code_reader":
            for it in items:
                _uri, _ws, _page, todo_paths = it
                obj = {p: f"desc for {p}" for p in todo_paths}
                res.successes.append((it, json.dumps(obj)))
        return res

    monkeypatch.setattr(scan_module.SubagentPool, "run_all", _role_aware_run_all)

    await scan_module.run_scan(
        workspace_path=workspace, repo_path=repo, no_file_map=False
    )

    log_text = (wiki / "log.md").read_text(encoding="utf-8")
    assert "file descriptions filled:" in log_text, (
        f"description-fill log line missing; log:\n{log_text}"
    )
    fill_line = next(
        line for line in log_text.splitlines() if "file descriptions filled:" in line
    )
    assert "entity(s)" in fill_line, f"expected 'entity(s)' noun; got: {fill_line!r}"
    assert "package(s)" not in fill_line, f"stale 'package(s)' noun; got: {fill_line!r}"
```

- [ ] **Step 2: Run the test to verify it fails**

Run:
```bash
uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_scan_graph_integration.py::test_description_fill_log_uses_entity_noun -v
```
Expected: **FAIL** on `assert "entity(s)" in fill_line` — the line currently reads `file descriptions filled: 1 package(s) (errors: 0)`.

- [ ] **Step 3: Broaden the log noun**

In `scan.py`, the Step 10c log call (`scan.py:1056-1067`). Current:

```python
                if describer_filled or describer_errors:
                    append_log(
                        wiki,
                        "scan",
                        (
                            f"file descriptions filled: {len(describer_filled)} "
                            f"package(s) (errors: {len(describer_errors)})"
                        ),
                        detail=None,
                        silent=True,
                        raise_exception=True,
                    )
```

Change `package(s)` to `entity(s)`:

```python
                if describer_filled or describer_errors:
                    append_log(
                        wiki,
                        "scan",
                        (
                            f"file descriptions filled: {len(describer_filled)} "
                            f"entity(s) (errors: {len(describer_errors)})"
                        ),
                        detail=None,
                        silent=True,
                        raise_exception=True,
                    )
```

Leave Step 10b's `"file maps injected: N (errors: ...)"` line (`scan.py:980-983`) unchanged — it has no noun to fix.

- [ ] **Step 4: Run the test to verify it passes**

Run:
```bash
uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_scan_graph_integration.py::test_description_fill_log_uses_entity_noun -v
```
Expected: **PASS**.

- [ ] **Step 5: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py packages/graph-wiki-core/tests/unit/test_scan_graph_integration.py
git commit -m "fix(scan): broaden description-fill log noun to entity(s)

Step 10c now fills apps as well as packages; the log line said 'package(s)'.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Full regression sweep

Confirm the change is isolated — no other scan or wiki-io test regressed.

**Files:** none (verification only)

- [ ] **Step 1: Run the full scan integration + commands test suite**

Run:
```bash
uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_scan_graph_integration.py packages/graph-wiki-core/tests/unit/test_commands_scan.py packages/graph-wiki-core/tests/commands/test_scan_parity.py -v
```
Expected: **all PASS**, including the four new app tests and the three pre-existing package file-map tests.

- [ ] **Step 2: Run the wiki-io entity-writer tests (kind-agnostic surfaces touched indirectly)**

Run:
```bash
uv run --package wiki-io pytest packages/wiki-io/tests -k "entity or file_map or inject" -v
```
Expected: **all PASS** (no `wiki_io` source changed; this confirms `inject_file_map` / `write_entities` behavior is unaffected).

- [ ] **Step 3: If any pre-existing test fails, stop and investigate**

A failure here means the Step 10b change altered the package path. Re-check that `package` remains first in `fm_list_fns` and that the loop body was copied verbatim. Do not proceed until green.

---

## Self-Review

**1. Spec coverage:**
- Spec "The change (single locus)" → Task 1 Step 4 (Step 10b iterates `package` + `app` via `fm_list_fns` / `fm_nodes`). ✅ Matches the spec's proposed snippet.
- Spec "Side adjustment — log wording" → Task 4. ✅
- Spec Testing #1 (app injection, TODO rows present) → Task 1 test. ✅
- Spec Testing #2 (app description fill) → Task 2 test. ✅
- Spec Testing #3 (rescan durability) → Task 3 test. ✅
- Spec "What is already in place (no change required)" → honored: no changes to file-map build, snapshot, app template, or Step 10c logic; only Step 10b iteration + one log word.
- Spec "Out of scope (YAGNI)" → no `max_depth`/`max_entries` tuning, no app-only toggle added. ✅

**2. Placeholder scan:** No `TBD`/`TODO`/"add error handling"/"similar to Task N" placeholders. The string `— TODO` appearing in test fixtures is literal File-map table content, not a plan placeholder. Every code step shows complete code.

**3. Type/name consistency:**
- `_seed_app_graph(db_path: Path)` defined in Task 1, referenced by name in Tasks 2–4. App node: kind `app`, name `app-x`, uri `app:org/repo/app-x` — consistent across all four tests.
- Production identifiers (`_kind_list_fns`, `list_fns`, `fm_list_fns`, `fm_nodes`, `_compute_collision_set`, `inject_file_map`, `file_mapped_pages`, `ADMITTED_KINDS`, `unscope`, `append_log`) all match the verified source at `scan.py`.
- `result.entities_created` field confirmed at `scan.py:253`. `run_scan` signature `run_scan(workspace_path=..., repo_path=..., no_file_map=...)` matches existing test calls.
- Stub-pool item tuple shape `(_uri, _ws, _page, todo_paths)` matches `describer_items` construction at `scan.py:999-1007` and the existing `_role_aware_run_all` stub at `test_scan_graph_integration.py:797-804`.
```
