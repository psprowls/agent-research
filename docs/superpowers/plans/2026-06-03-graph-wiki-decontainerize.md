# graph-wiki De-containerize Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the container concept (classification, pinned layout block, `package-family`, docs-container support) from the shared `wiki_io`/`graph_wiki_core` core and the `graph-wiki` plugin, so entity discovery is purely graph-driven — without changing the wiki output.

**Architecture:** The graph (`cg build`) is already the sole source of truth for entity pages (`write_entities(conn, ...)`). This plan deletes the vestigial layout-block apparatus whose only live job is feeding file-map *text* and a "legacy view" diff. File maps are re-sourced from graph node paths (the pattern the `test_suite` branch already uses). A characterization-test harness (golden snapshot of the `entities/` tree, captured on current `main`) guards every change: the refactor must keep it byte-identical.

**Tech Stack:** Python 3.11, `uv` workspace, pytest, `graph-io` (kuzu graph), `wiki-io`, `graph-wiki-core`.

**Companion specs:** `docs/superpowers/specs/2026-06-03-graph-wiki-decontainerize-design.md` (design), `…-graph-wiki-plugin-staleness-audit.md` (findings).

---

## Branch setup

- [ ] **Step 0: Create the working branch**

Run:
```bash
cd /Users/pat/Personal/agent-research
git checkout -b decontainerize-graph-wiki
git add docs/superpowers/specs/2026-06-03-graph-wiki-decontainerize-design.md docs/superpowers/specs/2026-06-03-graph-wiki-plugin-staleness-audit.md docs/superpowers/plans/2026-06-03-graph-wiki-decontainerize.md
git commit -m "docs: de-containerize design, findings audit, and implementation plan"
```

---

## File Structure

**Modified (code):**
- `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py` — remove layout/discover steps; re-source file maps from graph; collapse legacy `ScanResult` fields.
- `packages/wiki-io/src/wiki_io/init_vault.py` — stop detecting containers / writing the layout block.
- `packages/wiki-io/src/wiki_io/lint_wiki.py` — drop container + source-sync checks; switch code-drift discovery to unpinned.
- `packages/wiki-io/src/wiki_io/scan_monorepo.py` — remove `discover_workspaces`/`_discover_from_pinned`/`reconcile_layout`/`_wiki_relative_path_for`/`discover_docs`/`_existing_source_paths`.
- `packages/graph-wiki-core/src/graph_wiki_core/commands/lint.py`, `prompts/project_context.py` — drop layout consumption.

**Deleted (code):**
- `packages/wiki-io/src/wiki_io/detect_containers.py`
- `packages/wiki-io/src/wiki_io/layout_io.py`
- `packages/wiki-io/src/wiki_io/lint/container.py`
- `packages/wiki-io/src/wiki_io/lint/source_sync.py`
- `plugins/graph-wiki/skills/graph-wiki/scripts/detect_containers.py`
- `plugins/graph-wiki/skills/graph-wiki/references/detection-workflow.md`

**Modified (plugin docs):** `bootstrap.md`, `scan.md`, `ingest.md`, `scanner.md`, `linter.md`, `SKILL.md`, `CLAUDE.md`, `README.md`, `skills/graph-wiki/README.md`, `.claude-plugin/plugin.json`, `page-formats.md`, `wiki-schema.md`, `lint-workflow.md`.

**New (test):** `packages/graph-wiki-core/tests/unit/test_scan_decontainerize_parity.py`

---

## Phase 0 — Characterization harness (safety net, build FIRST)

### Task 0.1: Golden-snapshot parity test for the `entities/` tree

**Files:**
- Test: `packages/graph-wiki-core/tests/unit/test_scan_decontainerize_parity.py`

The test runs `run_scan(narrate=False)` against a fixture repo and serializes the resulting `wiki/entities/` tree (relative filename → file text) into a dict. Captured on current `main`, it becomes the golden the whole refactor is checked against.

- [ ] **Step 1: Write the parity test (passes on current code)**

```python
"""Characterization harness: the entities/ tree must not change as containers are removed."""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from graph_wiki_core.commands.scan import run_scan


def _snapshot_entities(wiki: Path) -> dict[str, str]:
    """Map entities/<file> -> text, for byte-stable comparison."""
    ents = wiki / "entities"
    if not ents.exists():
        return {}
    return {
        str(p.relative_to(ents)): p.read_text(encoding="utf-8")
        for p in sorted(ents.rglob("*.md"))
    }


@pytest.fixture
def scanned_workspace(seeded_graph_workspace):
    """Reuse the existing seeded-graph workspace fixture; return (wiki, repo)."""
    return seeded_graph_workspace


def test_scan_entities_tree_snapshot(scanned_workspace, snapshot):
    wiki, repo = scanned_workspace
    asyncio.run(run_scan(workspace_path=wiki.parent, narrate=False))
    assert _snapshot_entities(wiki) == snapshot
```

> Note: this reuses the seeded-graph workspace fixture already used by `test_seeded_graph_workspace_smoke.py`. If its name/return shape differs, adapt `scanned_workspace` to yield `(wiki_path, repo_path)`. Uses `syrupy`'s `snapshot` fixture (already a dev dep).

- [ ] **Step 2: Capture the golden on current code**

Run:
```bash
uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_scan_decontainerize_parity.py --snapshot-update -q
```
Expected: 1 snapshot written. Inspect the generated `__snapshots__/` file — it must contain real entity pages (`pkg_*`, `app_*`, etc.), not an empty dict.

- [ ] **Step 3: Verify it passes (golden locked)**

Run:
```bash
uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_scan_decontainerize_parity.py -q
```
Expected: PASS.

- [ ] **Step 4: Commit the harness**

```bash
git add packages/graph-wiki-core/tests/unit/test_scan_decontainerize_parity.py packages/graph-wiki-core/tests/unit/__snapshots__/
git commit -m "test(scan): golden snapshot of entities/ tree as de-containerize safety net"
```

**This snapshot must stay green through Phase 1.** If a task changes it, the change is a regression — stop and investigate, do not `--snapshot-update`.

---

## Phase 1 — Slice A: shared-core de-containerize

### Task 1.1: Re-source package/app file maps from graph node paths

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py` (Step 10b, ~`:984-1012`)

Step 10b already iterates graph nodes (`fm_nodes` from `fm_list_fns` = package + app queries). It only needs to build the file-map text from each node's path instead of from `ws_fm_by_name`.

- [ ] **Step 1: Replace the `ws_fm_by_name` lookup with a node-path build**

Find (the current package/app file-map loop body, ~`:986-997`):
```python
                ws_fm_by_name = {
                    unscope(w["name"]): w.get("file_map", "") for w in workspaces
                }
                fm_nodes = [n for fn in fm_list_fns if fn for n in fn(conn)]
                for node in fm_nodes:
                    ...
                    node_uri = node.attrs.get("uri")
                    if not node_uri or node_uri not in refreshed:
                        continue
                    file_map = ws_fm_by_name.get(node.name, "")
                    if not file_map:
                        continue
```
Replace the `ws_fm_by_name` construction and the `file_map = ws_fm_by_name.get(...)` line with a node-path build (mirrors the `test_suite` branch's `node.attrs["path"]` → `build_*` pattern, but uses the **partitioned** `build_file_map`):
```python
                fm_nodes = [n for fn in fm_list_fns if fn for n in fn(conn)]
                for node in fm_nodes:
                    if not isinstance(node.attrs, dict):
                        continue
                    node_uri = node.attrs.get("uri")
                    if not node_uri or node_uri not in refreshed:
                        continue
                    node_path = node.attrs.get("path")
                    if not node_path:
                        continue
                    file_map = build_file_map(repo / node_path, max_depth=max_depth)
                    if not file_map:
                        continue
```
(`no_file_map` short-circuit: keep whatever guard wraps this block today; if file maps were previously skipped via `no_file_map` dropping `w["file_map"]`, replace that with an explicit `if no_file_map: <skip block>` guard at the top of Step 10b.)

- [ ] **Step 2: Run the parity snapshot**

Run:
```bash
uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_scan_decontainerize_parity.py -q
```
Expected: PASS (file-map text identical — `build_file_map` is the same builder that produced the golden, now fed the same path via the graph).

- [ ] **Step 3: Run the file-map + scan unit tests**

Run:
```bash
uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_commands_scan.py packages/graph-wiki-core/tests/unit/test_scan_graph_integration.py -q
```
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py
git commit -m "feat(scan): source package/app file maps from graph node paths"
```

### Task 1.2: Remove layout-read + discover_workspaces + legacy diff from run_scan

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py`

Now that file maps come from the graph, the whole discover/layout/legacy-diff section is dead.

- [ ] **Step 1: Delete the dead steps**

Remove, in `run_scan`:
- Step 2 "read layout block" (`:759-772`) — the `pinned` block.
- Step 3 `workspaces = discover_workspaces(...)` (`:774-775`).
- Step 3.5 graph-URI decoration loop (`:777-811`).
- Step 4 per-workspace `build_file_map` loop (`:813-819`).
- Step 6 `attach_changed_files(...)` (`:824-825`).
- Step 7 `diff = compute_diff(...)` (`:827-828`).
- `ws_by_name = {...}` (`:833-835`) and any remaining `workspaces`/`diff`/`pinned` references.
- The now-unused imports at the top: `read_layout`, `discover_workspaces`, `attach_changed_files`, `compute_diff`, and `_query_package_uris`/`_query_package_domains` if only used by Step 3.5.

Keep: Step 5 `existing_pages` only if still used by `_snapshot_file_map_descriptions`/narrator (audit; if `existing_pages.legacy` was its only consumer, remove it too).

- [ ] **Step 2: Collapse the legacy `ScanResult` fields**

In the `ScanResult` dataclass (`:237-267`), remove `added`, `updated`, `deleted`, `renamed`, `errors` (the legacy name-keyed fan-out fields). Keep `state_gate` and all `entities_*` + `entity_errors` fields. Update the docstring. Update the `ScanResult(...)` construction at the end of `run_scan` to drop those kwargs.

- [ ] **Step 3: Update ScanResult consumers**

Run to find them:
```bash
grep -rn "\.added\b\|\.renamed\b\|ScanResult(" packages/graph-wiki-core packages/graph-wiki-cli plugins/graph-wiki | grep -v __pycache__
```
Update the CLI formatter (`graph_wiki_cli`), the plugin shim's JSON/report path (`scan_monorepo.py` shim already only prints `entities_*` — verify), and any tests that assert the removed fields.

- [ ] **Step 4: Run parity + scan suites**

Run:
```bash
uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_scan_decontainerize_parity.py packages/graph-wiki-core/tests/ -q -k scan
```
Expected: PASS. The parity snapshot is unchanged (entity pages are graph-written, untouched by this deletion).

- [ ] **Step 5: Commit**

```bash
git add -A packages/graph-wiki-core packages/graph-wiki-cli
git commit -m "refactor(scan): drop layout-read, discover_workspaces, and legacy ScanResult fields"
```

### Task 1.3: Stop pinning the layout block in init_vault

**Files:**
- Modify: `packages/wiki-io/src/wiki_io/init_vault.py`

- [ ] **Step 1: Write the failing test**

Add to `packages/wiki-io/tests/test_init_vault.py` (or nearest init test module):
```python
def test_init_writes_no_layout_block(tmp_repo):
    repo, wiki = tmp_repo  # adapt to the module's fixture shape
    init_wiki(wiki_path=wiki, repo_path=repo, topic="x", tool="claude-code", force=True, non_interactive=True)
    claude = (wiki / "CLAUDE.md").read_text()
    assert "graph-wiki:layout" not in claude
    assert "classification" not in claude
```

- [ ] **Step 2: Run it (expect FAIL — block is still written)**

Run:
```bash
uv run pytest packages/wiki-io/tests/test_init_vault.py::test_init_writes_no_layout_block -q
```
Expected: FAIL.

- [ ] **Step 3: Remove detection + layout pinning**

In `init_vault.py`:
- Delete imports `from wiki_io.detect_containers import detect as _detect_containers` (`:37`) and `from wiki_io.layout_io import write_layout as _write_layout` (`:38`).
- Delete `_resolve_pinned_containers` (`:96-118`) and its call (`:189`).
- Delete the `layout = {...}` build + `_write_layout` loop (`:260-273`).
- Remove `non_interactive`/`interactive` plumbing that existed only to drive the ambiguous-container prompt (keep the param as a no-op only if external callers pass it; otherwise drop — check `run_init` and the CLI).

- [ ] **Step 4: Run the test + init suite**

Run:
```bash
uv run pytest packages/wiki-io/tests/test_init_vault.py packages/graph-wiki-core/tests/unit/test_commands_bootstrap.py -q
```
Expected: PASS (update any test asserting the layout block is written — those assertions are now invalid and should be inverted/removed).

- [ ] **Step 5: Commit**

```bash
git add -A packages/wiki-io packages/graph-wiki-core
git commit -m "refactor(init): stop detecting containers and writing the layout block"
```

### Task 1.4: Drop container + source-sync lint checks; unpin code-drift discovery

**Files:**
- Modify: `packages/wiki-io/src/wiki_io/lint_wiki.py`
- Delete: `packages/wiki-io/src/wiki_io/lint/container.py`, `packages/wiki-io/src/wiki_io/lint/source_sync.py`

- [ ] **Step 1: Remove the two checks from the registry**

In `lint_wiki.py`:
- Delete imports `check_container_drift` (`:48`) and `check_source_sync_drift` (`:53`).
- Delete their invocations (`:340-345`) and result-dict keys `container_drift`, `source_sync_drift` (`:382-383`).
- Delete their reporting blocks (`:462-471`).
- Switch code-drift discovery off the layout block: at `:250-251` and `:360-361`, replace `pinned_containers = layout.get("containers") ...; workspaces = _scan_discover(repo, pinned_containers=pinned)` with unpinned discovery `_scan_discover(repo)` — or, preferably, graph-based package enumeration via `queries.list_packages`. Use whichever keeps `package_sync`/code-drift tests green; unpinned `_scan_discover(repo)` is the smaller change.
- Remove the `layout = read_layout(...)` reads feeding only those lines.

- [ ] **Step 2: Delete the two lint modules**

Run:
```bash
git rm packages/wiki-io/src/wiki_io/lint/container.py packages/wiki-io/src/wiki_io/lint/source_sync.py
```

- [ ] **Step 3: Run the lint suite**

Run:
```bash
uv run pytest packages/wiki-io/tests -q -k "lint" && uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/commands/test_lint_parity.py packages/graph-wiki-core/tests/unit/test_commands_lint.py -q
```
Expected: PASS. Remove/adjust tests that asserted `container_drift`/`source_sync_drift` output.

- [ ] **Step 4: Commit**

```bash
git add -A packages/wiki-io packages/graph-wiki-core
git commit -m "refactor(lint): drop container-drift + source-sync checks; unpin code-drift discovery"
```

### Task 1.5: Drop layout injection from project_context + graph-wiki-core lint

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/prompts/project_context.py`, `packages/graph-wiki-core/src/graph_wiki_core/commands/lint.py`

- [ ] **Step 1: Remove layout reads**

Run to locate:
```bash
grep -n "layout\|read_layout\|container" packages/graph-wiki-core/src/graph_wiki_core/prompts/project_context.py packages/graph-wiki-core/src/graph_wiki_core/commands/lint.py
```
Delete the layout-block read + its injection into the prompt/lint flow. If `project_context` rendered a "containers" section, remove that section and its test assertions.

- [ ] **Step 2: Run affected suites**

Run:
```bash
uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/prompts/test_project_context.py packages/graph-wiki-core/tests/prompts/test_prompt_snapshots.py -q
```
Expected: PASS (update prompt snapshots with `--snapshot-update` ONLY for the intended layout-section removal, then eyeball the diff).

- [ ] **Step 3: Commit**

```bash
git add -A packages/graph-wiki-core
git commit -m "refactor(prompts,lint): drop layout-block injection"
```

### Task 1.6: Delete classifier + layout IO + dead scan_monorepo functions

**Files:**
- Delete: `packages/wiki-io/src/wiki_io/detect_containers.py`, `packages/wiki-io/src/wiki_io/layout_io.py`
- Modify: `packages/wiki-io/src/wiki_io/scan_monorepo.py`, `packages/wiki-io/src/wiki_io/__init__.py`

- [ ] **Step 1: Remove now-orphaned scan_monorepo functions**

In `scan_monorepo.py`, delete (after confirming no remaining callers with the grep in Step 2): `discover_workspaces`, `_discover_from_pinned`, `_discover_heuristic`, `_wiki_relative_path_for`, `reconcile_layout`, `discover_docs` (`:1151`), `_existing_source_paths` (`:1132`), and the `doc_candidates` path (`:1485-1487`). Keep `build_file_map`, `build_dir_file_map`, `build_file_maps`, `unscope`, `_is_test_path`, and any helper still imported by `scan.py`.

- [ ] **Step 2: Confirm no callers remain, then delete the modules**

Run:
```bash
grep -rn "detect_containers\|layout_io\|read_layout\|write_layout\|reconcile_layout\|discover_workspaces\|discover_docs" packages/ --include="*.py" | grep -v __pycache__ | grep -v /tests/
```
Expected: only lines inside the files being deleted. Then:
```bash
git rm packages/wiki-io/src/wiki_io/detect_containers.py packages/wiki-io/src/wiki_io/layout_io.py
```
Remove their re-exports from `wiki_io/__init__.py` if present.

- [ ] **Step 3: Run the full wiki-io + core suites**

Run:
```bash
uv run pytest packages/wiki-io packages/graph-wiki-core -q
```
Expected: PASS. Delete tests that exclusively exercised the removed functions (`test_layout_io.py`, container-drift tests, `detect_containers` tests).

- [ ] **Step 4: Commit**

```bash
git add -A packages/wiki-io packages/graph-wiki-core
git commit -m "refactor(wiki-io): delete detect_containers, layout_io, and dead discovery functions"
```

### Task 1.7: Remove `package-family` from code, templates, and tests

**Files:**
- Modify: dependency-kind validator + dependency template/asset; tests `test_uri.py`, `test_cli_main.py`, `test_assets.py`, `test_entity_writer.py`, `test_entity_templates.py`

- [ ] **Step 1: Find the dependency-kind enum**

Run:
```bash
grep -rn "package-family\|package_family\|\"service\"\|'service'\|kind.*package.*service" packages/*/src --include="*.py" | grep -v __pycache__
grep -rn "package-family\|package_family" packages/wiki-io/src/wiki_io/assets
```

- [ ] **Step 2: Reduce the kind enum to `package | service`**

Wherever the dependency `kind` is validated/enumerated (lint dependency check, entity writer, templates), drop `package-family`. Remove `family:`/`members:`/`co_required:` family-only fields from the dependency template asset if present.

- [ ] **Step 3: Update the tests**

In each listed test, remove `package-family` cases/assertions. Run:
```bash
uv run pytest packages/wiki-io/tests/test_uri.py packages/wiki-io/tests/test_assets.py packages/wiki-io/tests/test_entity_writer.py packages/wiki-io/tests/test_entity_templates.py packages/graph-wiki-cli/tests/graph_cli/test_cli_main.py -q
```
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add -A packages/
git commit -m "refactor: remove unused package-family dependency kind"
```

### Task 1.8: Slice A gate — full suite + grep sweep

- [ ] **Step 1: Grep gate (no container surface remains in src)**

Run:
```bash
grep -rn "detect_container\|layout_io\|reconcile_layout\|package-family\|pinned_container\|discover_docs\|graph-wiki:layout" packages/ --include="*.py" | grep -v __pycache__ | grep -v /tests/
```
Expected: no output.

- [ ] **Step 2: Full test suite**

Run:
```bash
uv run pytest packages/ -q
```
Expected: PASS. Parity snapshot from Task 0.1 still green.

- [ ] **Step 3: Manual bootstrap+scan smoke**

Run:
```bash
uv run --package graph-wiki-cli gw bootstrap --topic smoke --force && uv run --package graph-wiki-cli gw scan --no-narrate
grep -c "graph-wiki:layout" graph-wiki/wiki/CLAUDE.md || echo "no layout block (expected)"
```
Expected: scan reports `entities +N ~M -D`; no layout block in CLAUDE.md. (Clean up the smoke `graph-wiki/` dir after.)

- [ ] **Step 4: Commit any fixups**

```bash
git add -A && git commit -m "test: Slice A green — full suite + grep gate pass" --allow-empty
```

---

## Phase 2 — Slice B: plugin script + markdown sweep

> Markdown tasks have no failing unit test; verification is grep-based + a final read-through. Apply edits per the findings report (`…-plugin-staleness-audit.md`) Categories A & B, and do NOT touch Category C items.

### Task 2.1: Delete the plugin classifier shim + detection-workflow doc

- [ ] **Step 1: Delete files**

```bash
git rm plugins/graph-wiki/skills/graph-wiki/scripts/detect_containers.py
git rm plugins/graph-wiki/skills/graph-wiki/references/detection-workflow.md
```

- [ ] **Step 2: Verify nothing references them**

```bash
grep -rn "detect_containers\|detection-workflow" plugins/graph-wiki | grep -v __pycache__
```
Expected: hits only in files edited by Task 2.2/2.3 (fix those there).

- [ ] **Step 3: Commit**

```bash
git add -A plugins/graph-wiki
git commit -m "docs(plugin): delete detect_containers shim and detection-workflow.md"
```

### Task 2.2: Strip container/layout language from command + agent + skill markdown (Category A)

- [ ] **Step 1: Apply edits**

Per findings Category A:
- `commands/bootstrap.md` — delete the entire `## Container detection` section (`:28-42`); fix the "Next steps" to: bootstrap → scan.
- `commands/scan.md` — delete the drift/reconcile block (`:39-49`) and the docs-container ingest-candidate paragraph.
- `commands/ingest.md` — remove the `docs`-container path (`:28`, `:38` table row, `:60`).
- `agents/scanner.md:39` — delete the "Layout-aware" bullet.
- `agents/linter.md:39` — drop `check_container_drift` + source-sync drift mention; keep package-sync/code-drift.
- `SKILL.md` — rewrite `:3` description (no "detects … containers … pins the layout"); delete `:65` layout clause; delete `detect_containers.py` row (`:130`); delete `detection-workflow.md` ref (`:171`).
- `CLAUDE.md` — delete the container-layout invariant bullet (`:68`); fix the "when changing layout, update these refs" list (`:72`) to drop `detection-workflow.md` and reframe.
- `README.md` + `skills/graph-wiki/README.md` — rewrite container-detection framing (`README.md:7,27,29`; skill `README.md:7,27,29,64`).
- `.claude-plugin/plugin.json` — rewrite `description` to entity/graph framing (drop "classifies top-level dirs as apps, packages, domains, or docs containers, and pins the layout").

- [ ] **Step 2: Grep gate**

```bash
grep -rni "layout block\|pinned container\|container detection\|detect_container\|classification\|docs container\|layout-aware" plugins/graph-wiki --include="*.md" --include="*.json" | grep -v "testcontainers"
```
Expected: no output (testcontainers is the only legit `container` match — Category C).

- [ ] **Step 3: Commit**

```bash
git add -A plugins/graph-wiki
git commit -m "docs(plugin): remove container/layout-block language from commands, agents, skill"
```

### Task 2.3: Fix Category B drift (templates, file-map model, counts) + package-family in docs

- [ ] **Step 1: Apply edits**

- `SKILL.md:186`, `README.md:29`, `skills/graph-wiki/README.md` — replace template inventories with the real names: `entity-repository.md`, `entity-domain.md`, `entity-package.md`, `entity-app.md`, `entity-agent-plugin.md`, `entity-dependency.md`, `entity-test-suite.md` + curated `concept.md`, `concept-pattern.md`, `source.md`, `adr.md`, `architecture.md`, `dependency.md`, `work.md`, `index.md`.
- `README.md:27` — "7 Python tools" → "6 Python tools" and drop `detect_containers` from the list.
- `page-formats.md:17` — rewrite the prod-vs-test File-map section: entity pages are single `entities/<prefix>_<name>.md` with a `## File map` section; test files belong to their own `test_suite` entity pages (no `overview.md`/`testing.md` sub-pages).
- `wiki-schema.md`, `lint-workflow.md`, `page-formats.md` — remove dependency `kind: package-family` (the enum, `dep-family-without-members` rule, `members:`/`co_required:` family frontmatter). Dependency `kind` is now `package | service`.

- [ ] **Step 2: Grep gate**

```bash
grep -rn "package-family\|overview\.md\|testing\.md sub-page\|app\.md.*package\.md.*domain\.md" plugins/graph-wiki --include="*.md"
```
Expected: no output (code-path/example matches excluded; verify any remaining `overview.md` hits are inside fixture/example prose, not layout instructions).

- [ ] **Step 3: Read-through**

Open `SKILL.md`, `README.md`, `commands/bootstrap.md`, `commands/scan.md`, `page-formats.md` and confirm they describe a graph-driven, single-`entities/`, no-container workflow end to end.

- [ ] **Step 4: Commit**

```bash
git add -A plugins/graph-wiki
git commit -m "docs(plugin): fix template inventories, file-map model, tool count; drop package-family"
```

### Task 2.4: Final verification

- [ ] **Step 1: Full suite + plugin shim contract**

```bash
uv run pytest packages/ -q
uv run --package graph-wiki-cli python -m pytest packages/graph-wiki-cli/tests/unit/test_plugin_bedrock_shims.py -q
```
Expected: PASS.

- [ ] **Step 2: Repo-wide container-surface grep**

```bash
grep -rn "detect_container\|layout_io\|reconcile_layout\|package-family\|pinned_container\|graph-wiki:layout" packages/ plugins/ --include="*.py" --include="*.md" --include="*.json" | grep -v __pycache__ | grep -v /tests/ | grep -v docs/superpowers
```
Expected: no output.

- [ ] **Step 3: Final commit**

```bash
git add -A && git commit -m "chore: de-containerize verification pass" --allow-empty
```

---

## Self-review notes

- **Spec coverage:** Slice A → Tasks 1.1–1.8; Slice B → Tasks 2.1–2.4; parity safety net → Phase 0; `package-family` → 1.7 (code) + 2.3 (docs); docs-container removal → 1.6 (`discover_docs`) + 2.2 (markdown); drift decomposition → 1.4 (remove container+source-sync) keeps package-sync/code-drift. All design sections mapped.
- **Risk sequencing:** harness first (Phase 0); `scan.py` file-map re-source (1.1) before the discover deletion (1.2) so file maps never regress; grep gate before module deletion (1.6).
- **Known unknowns flagged inline** (adapt-to-fixture notes): seeded-graph fixture name in 0.1; exact `no_file_map` guard in 1.1; whether `existing_pages` survives in 1.2; code-drift discovery replacement choice in 1.4. Each has a concrete fallback.
