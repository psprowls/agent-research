# `.gitkeep` Placeholder for `wiki/entities/` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the never-populated `wiki/entities/_index.md` sentinel page with a `.gitkeep` placeholder that exists only while `entities/` is empty and is self-healed by `gw scan`.

**Architecture:** Bootstrap (`init_vault.init_wiki`) writes an empty `entities/.gitkeep` instead of the fake `_index.md`. The entity-write path (`entity_writer.write_entities`) owns the placeholder lifecycle: at the end of its scan-lock block it removes `.gitkeep` when real `*.md` pages exist and (re)creates it when the directory is empty. The two reader walks (`scan_monorepo._load_existing_pages`, `commands/scan._snapshot_file_map_descriptions`) drop their now-dead `_index.md` skips — `glob("*.md")` never matches a dotfile.

**Tech Stack:** Python 3.11+, `uv` workspace, `pytest`, `python-frontmatter`, in-repo `wiki-io` + `graph-wiki-core` packages.

---

## Background: why these specific hooks

- `init_vault.init_wiki` (`packages/wiki-io/src/wiki_io/init_vault.py:208-218`) currently writes a sentinel-comment `entities/_index.md` purely to keep the dir committable. `entities` is already in `FIXED_VAULT_DIRS` (`init_vault.py:50`) so the directory is always `mkdir`-ed; only the *placeholder file* changes.
- `write_entities` (`packages/wiki-io/src/wiki_io/entity_writer.py:705`) is the single owner of `entities/`: it `mkdir`s it (`:721`), runs the per-kind create/merge loop, then a deletion sweep, all inside `with _acquire_scan_lock(...)` (`:736`). Hooking the placeholder lifecycle at the end of that block means every scan maintains it.
- Two reader walks skip `_index.md` today and become dead-code skips once `_index.md` is never written:
  - `_load_existing_pages` deletion-index walk (`scan_monorepo.py:967`)
  - `_snapshot_file_map_descriptions` walk (`commands/scan.py:150`) — **not listed in the spec**, removed here for consistency.

## File Structure

- **Modify** `packages/wiki-io/src/wiki_io/init_vault.py` — swap `_index.md` block for `.gitkeep` (Task 1).
- **Modify** `packages/wiki-io/src/wiki_io/entity_writer.py` — remove `_index.md` skip in deletion sweep; add placeholder self-heal at end of lock block (Task 2).
- **Modify** `packages/wiki-io/src/wiki_io/scan_monorepo.py` — remove `_index.md` skip in entity walk; update two docstrings (Task 3).
- **Modify** `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py` — remove `_index.md` skip in File-map snapshot walk (Task 4).
- **Modify** `packages/wiki-io/tests/test_init_vault.py` — rewrite `test_entities_dir_bootstrapped_after_init_wiki` for `.gitkeep` (Task 1).
- **Modify** `packages/wiki-io/tests/test_load_existing_pages.py` — delete `test_entities_walk_skips_index_md` (Task 3).
- **Modify** `packages/wiki-io/tests/integration/test_entity_writer_integration.py` — drop `!= "_index.md"` filter; add two placeholder-lifecycle tests (Task 2).

## Commands reference

Run tests scoped to one workspace member with `uv`:

- All wiki-io tests: `uv run --package wiki-io pytest packages/wiki-io/tests -q`
- A single test: `uv run --package wiki-io pytest packages/wiki-io/tests/test_init_vault.py::test_entities_dir_bootstrapped_after_init_wiki -v`
- graph-wiki-core scan tests: `uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_scan_graph_integration.py -q`

---

### Task 1: Bootstrap writes `.gitkeep` instead of `_index.md`

**Files:**
- Modify: `packages/wiki-io/src/wiki_io/init_vault.py:208-218`
- Test: `packages/wiki-io/tests/test_init_vault.py:224-262`

- [ ] **Step 1: Rewrite the bootstrap test to expect `.gitkeep`**

Replace the entire `test_entities_dir_bootstrapped_after_init_wiki` function (lines 224-262) with:

```python
def test_entities_dir_bootstrapped_with_gitkeep(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """init_wiki creates wiki/entities/.gitkeep so the empty dir is committable.

    Uses the same monkeypatch pattern as test_init_wiki_creates_section_index_stubs:
    stub out _workspace_init and _resolve_pinned_containers so the test exercises
    only the directory-creation + placeholder-write path.
    """
    from wiki_io import init_vault

    repo = tmp_path / "repo"
    workspace = tmp_path / "ws"
    wiki = workspace / "wiki"
    repo.mkdir()
    (repo / "pyproject.toml").write_text(
        '[project]\nname="solo"\nversion="0.0.1"\n', encoding="utf-8"
    )

    monkeypatch.setattr(init_vault, "_workspace_init", lambda *a, **k: None)
    monkeypatch.setattr(init_vault, "_resolve_pinned_containers", lambda *a, **k: [])

    result = init_vault.init_wiki(
        wiki, repo, topic="test", tool="claude-code", force=False, non_interactive=True
    )

    entities_dir = wiki / "entities"
    gitkeep = entities_dir / ".gitkeep"
    assert entities_dir.is_dir(), f"entities/ dir not created: {entities_dir}"
    assert gitkeep.is_file(), f".gitkeep not created: {gitkeep}"
    assert gitkeep.read_text(encoding="utf-8") == "", (
        f".gitkeep must be empty, got: {gitkeep.read_text(encoding='utf-8')!r}"
    )
    assert not (entities_dir / "_index.md").exists(), (
        "_index.md must no longer be created"
    )
    assert "entities/.gitkeep" in result["installed_files"], (
        f"installed_files missing entities/.gitkeep: {result['installed_files']}"
    )
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --package wiki-io pytest packages/wiki-io/tests/test_init_vault.py::test_entities_dir_bootstrapped_with_gitkeep -v`
Expected: FAIL — `.gitkeep` not created (init_vault still writes `_index.md`).

- [ ] **Step 3: Swap the `_index.md` block for `.gitkeep` in init_vault**

In `packages/wiki-io/src/wiki_io/init_vault.py`, replace lines 208-218:

```python
    # Phase 42 D-14/D-15: seed wiki/entities/ with a sentinel-comment _index.md
    # so the directory is non-empty under git and Obsidian surfaces the folder.
    # The real entity index lives at wiki/index.md (Phase 44 generator).
    entities_index = wiki_path / "entities" / "_index.md"
    if not entities_index.exists():
        entities_index.write_text(
            "<!-- generated by graph-wiki-agent scan; "
            "see ../index.md for the canonical listing -->\n",
            encoding="utf-8",
        )
        installed_files.append(str(entities_index.relative_to(wiki_path)))
```

with:

```python
    # Seed wiki/entities/ with an empty .gitkeep so the otherwise-empty dir is
    # committable. write_entities() self-heals it away once real entity pages
    # exist (and restores it if a deletion sweep empties the dir again).
    entities_gitkeep = wiki_path / "entities" / ".gitkeep"
    if not entities_gitkeep.exists():
        entities_gitkeep.write_text("", encoding="utf-8")
        installed_files.append(str(entities_gitkeep.relative_to(wiki_path)))
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run --package wiki-io pytest packages/wiki-io/tests/test_init_vault.py::test_entities_dir_bootstrapped_with_gitkeep -v`
Expected: PASS.

- [ ] **Step 5: Run the full init_vault suite for regressions**

Run: `uv run --package wiki-io pytest packages/wiki-io/tests/test_init_vault.py -q`
Expected: PASS (no remaining references to `_index.md` in this file).

- [ ] **Step 6: Commit**

```bash
git add packages/wiki-io/src/wiki_io/init_vault.py packages/wiki-io/tests/test_init_vault.py
git commit -m "feat(wiki-io): bootstrap entities/ with .gitkeep instead of _index.md"
```

---

### Task 2: `write_entities` owns the `.gitkeep` lifecycle

**Files:**
- Modify: `packages/wiki-io/src/wiki_io/entity_writer.py:823-826` (remove skip) and `:853-854` (add self-heal at end of lock block)
- Test: `packages/wiki-io/tests/integration/test_entity_writer_integration.py`

This task has two production edits plus two new tests. Write the tests first.

- [ ] **Step 1: Add the "populated scan removes `.gitkeep`" test**

In `packages/wiki-io/tests/integration/test_entity_writer_integration.py`, add this function immediately after `test_write_entities_round_trip_on_synthetic_workspace` (after line 124):

```python
def test_write_entities_removes_gitkeep_when_pages_created(tmp_path):
    """A scan that creates >=1 entity page deletes the entities/.gitkeep placeholder."""
    _build_fixture_workspace(tmp_path)
    _init_git_repo(tmp_path)
    conn = _ingest(tmp_path)
    wiki_root = tmp_path / "wiki"

    # Simulate a freshly-bootstrapped vault: entities/ exists with only .gitkeep.
    entities = wiki_root / "entities"
    entities.mkdir(parents=True)
    (entities / ".gitkeep").write_text("", encoding="utf-8")

    result = write_entities(conn, wiki_root, ADMITTED_KINDS)

    assert result.created, "fixture should create at least one entity page"
    assert not (entities / ".gitkeep").exists(), (
        ".gitkeep must be removed once real entity pages exist"
    )
    assert any(entities.glob("*.md")), "expected entity *.md pages on disk"


def test_write_entities_restores_gitkeep_when_dir_empty(tmp_path):
    """A scan that leaves entities/ empty (re)creates the .gitkeep placeholder."""
    _build_fixture_workspace(tmp_path)
    _init_git_repo(tmp_path)
    conn = _ingest(tmp_path)
    wiki_root = tmp_path / "wiki"

    # Empty admitted set => no kinds processed, nothing created; dir stays empty.
    result = write_entities(conn, wiki_root, frozenset())

    assert result.created == []
    entities = wiki_root / "entities"
    assert list(entities.glob("*.md")) == [], "no entity pages expected"
    assert (entities / ".gitkeep").is_file(), (
        ".gitkeep must be restored when entities/ is empty"
    )
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `uv run --package wiki-io pytest "packages/wiki-io/tests/integration/test_entity_writer_integration.py::test_write_entities_removes_gitkeep_when_pages_created" "packages/wiki-io/tests/integration/test_entity_writer_integration.py::test_write_entities_restores_gitkeep_when_dir_empty" -v`
Expected: FAIL — `test_..._removes_gitkeep...` fails because `.gitkeep` is left in place; `test_..._restores_gitkeep...` fails because no `.gitkeep` is created.

- [ ] **Step 3: Remove the `_index.md` skip in the deletion sweep**

In `packages/wiki-io/src/wiki_io/entity_writer.py`, replace lines 823-826:

```python
        # --- Deletion sweep ---
        for page_path in sorted(entities_dir.glob("*.md")):
            if page_path.name == "_index.md":
                continue
            try:
```

with:

```python
        # --- Deletion sweep ---
        for page_path in sorted(entities_dir.glob("*.md")):
            try:
```

- [ ] **Step 4: Add the placeholder self-heal at the end of the lock block**

In `packages/wiki-io/src/wiki_io/entity_writer.py`, the deletion-sweep loop ends at line 853 with its `errors.append(...)` block, still inside `with _acquire_scan_lock(...)`. Immediately after that loop and still inside the `with` block (before the `return EntityWriteResult(...)` at line 855), add:

```python
        # --- Placeholder self-heal (runs after create/merge + deletion sweep,
        # so it reflects post-sweep state). Keep entities/ committable when
        # empty; drop the placeholder once real pages exist. ---
        gitkeep = entities_dir / ".gitkeep"
        if any(entities_dir.glob("*.md")):
            gitkeep.unlink(missing_ok=True)
        elif not gitkeep.exists():
            gitkeep.write_text("", encoding="utf-8")
```

The block must be indented to the `with _acquire_scan_lock(...)` body level (8 spaces) — same indentation as the `# --- Deletion sweep ---` comment.

- [ ] **Step 5: Run the new tests to verify they pass**

Run: `uv run --package wiki-io pytest "packages/wiki-io/tests/integration/test_entity_writer_integration.py::test_write_entities_removes_gitkeep_when_pages_created" "packages/wiki-io/tests/integration/test_entity_writer_integration.py::test_write_entities_restores_gitkeep_when_dir_empty" -v`
Expected: PASS.

- [ ] **Step 6: Drop the `!= "_index.md"` filter in the existing round-trip test**

In `packages/wiki-io/tests/integration/test_entity_writer_integration.py:259`, replace:

```python
    pages = [p for p in entities.glob("*.md") if p.name != "_index.md"]
```

with:

```python
    pages = sorted(entities.glob("*.md"))
```

- [ ] **Step 7: Run the full entity-writer integration suite**

Run: `uv run --package wiki-io pytest packages/wiki-io/tests/integration/test_entity_writer_integration.py -q`
Expected: PASS — all tests, including the modified round-trip test.

- [ ] **Step 8: Commit**

```bash
git add packages/wiki-io/src/wiki_io/entity_writer.py packages/wiki-io/tests/integration/test_entity_writer_integration.py
git commit -m "feat(wiki-io): self-heal entities/.gitkeep in write_entities"
```

---

### Task 3: Drop dead `_index.md` skip in `_load_existing_pages`

**Files:**
- Modify: `packages/wiki-io/src/wiki_io/scan_monorepo.py:966-968` (remove skip), `:842` and `:864-865` (docstrings)
- Test: `packages/wiki-io/tests/test_load_existing_pages.py:92-105` (delete obsolete test)

- [ ] **Step 1: Delete the obsolete `_index.md`-skip test**

In `packages/wiki-io/tests/test_load_existing_pages.py`, delete the entire `test_entities_walk_skips_index_md` method (lines 92-105):

```python
    def test_entities_walk_skips_index_md(self, tmp_path):
        wiki = tmp_path / "wiki"
        entities_dir = wiki / "entities"
        entities_dir.mkdir(parents=True)
        # _index.md should NOT appear in result.entities even if it has a URI
        (entities_dir / "_index.md").write_text(
            "---\nuri: NOT_A_REAL_URI\n---\n\n# Index\n", encoding="utf-8"
        )
        self._write_entity_page(entities_dir, "pkg__real", "pkg:real")

        result = _load_existing_pages(wiki)

        assert "NOT_A_REAL_URI" not in result.entities
        assert "pkg:real" in result.entities

```

(Delete through the trailing blank line so the next method `test_entities_walk_skips_pages_missing_uri` keeps its surrounding spacing.)

- [ ] **Step 2: Remove the skip in the entity walk**

In `packages/wiki-io/src/wiki_io/scan_monorepo.py`, replace lines 966-968:

```python
        for page_path in sorted(entities_dir.glob("*.md")):
            if page_path.name == "_index.md":
                continue
            try:
```

with:

```python
        for page_path in sorted(entities_dir.glob("*.md")):
            try:
```

- [ ] **Step 3: Update the two docstrings that mention `_index.md`**

In `packages/wiki-io/src/wiki_io/scan_monorepo.py:842`, replace:

```python
              skipped silently. `_index.md` is skipped (Phase 43 convention).
```

with:

```python
              skipped silently. `.gitkeep` is never matched by the `*.md` walk.
```

In `packages/wiki-io/src/wiki_io/scan_monorepo.py:864`, replace:

```python
    `entities` is built by walking `wiki/entities/*.md` (excluding `_index.md`)
```

with:

```python
    `entities` is built by walking `wiki/entities/*.md` (`.gitkeep` never matches)
```

- [ ] **Step 4: Run the load-existing-pages suite**

Run: `uv run --package wiki-io pytest packages/wiki-io/tests/test_load_existing_pages.py -q`
Expected: PASS — the deleted test is gone; the remaining `test_entities_walk_skips_pages_missing_uri` and others still pass.

- [ ] **Step 5: Commit**

```bash
git add packages/wiki-io/src/wiki_io/scan_monorepo.py packages/wiki-io/tests/test_load_existing_pages.py
git commit -m "refactor(wiki-io): drop dead _index.md skip in entity walk"
```

---

### Task 4: Drop dead `_index.md` skip in `_snapshot_file_map_descriptions`

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py:149-151`

> **Note:** This skip is not listed in the spec but is the same dead-code pattern. `entities_dir.glob("*.md")` never matches `.gitkeep`, so removing the skip is behavior-preserving once `_index.md` is no longer created. `scan.py` already has uncommitted (unrelated File-map) changes in the working tree — keep this commit limited to the three lines below.

- [ ] **Step 1: Confirm no test asserts the `_index.md` skip here**

Run: `grep -rn "_index.md" packages/graph-wiki-core/`
Expected: only the single source line at `commands/scan.py:150` (no test references). If a test reference appears, stop and report it before editing.

- [ ] **Step 2: Remove the skip**

In `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py`, replace lines 149-151:

```python
    for page_path in entities_dir.glob("*.md"):
        if page_path.name == "_index.md":
            continue
        try:
```

with:

```python
    for page_path in entities_dir.glob("*.md"):
        try:
```

- [ ] **Step 3: Run the scan integration suite**

Run: `uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_scan_graph_integration.py -q`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py
git commit -m "refactor(graph-wiki-core): drop dead _index.md skip in File-map snapshot"
```

---

### Task 5: Full-repo verification

**Files:** none (verification only).

- [ ] **Step 1: Confirm no `_index.md` references remain**

Run: `grep -rn "_index.md" packages/wiki-io/ packages/graph-wiki-core/`
Expected: no output. Any remaining hit is an unfinished edit — resolve before proceeding.

- [ ] **Step 2: Run both affected package suites**

Run: `uv run --package wiki-io pytest packages/wiki-io/tests -q && uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests -q`
Expected: PASS for both.

- [ ] **Step 3: Sanity-check a fresh bootstrap produces a committable dir**

Run:
```bash
uv run --package wiki-io python -c "
import tempfile, pathlib
from unittest import mock
from wiki_io import init_vault
d = pathlib.Path(tempfile.mkdtemp())
repo = d / 'repo'; repo.mkdir()
(repo / 'pyproject.toml').write_text('[project]\nname=\"x\"\nversion=\"0.0.1\"\n')
with mock.patch.object(init_vault, '_workspace_init', lambda *a, **k: None), \
     mock.patch.object(init_vault, '_resolve_pinned_containers', lambda *a, **k: []):
    init_vault.init_wiki(d/'ws'/'wiki', repo, topic='t', tool='claude-code', force=False, non_interactive=True)
e = d/'ws'/'wiki'/'entities'
print('gitkeep:', (e/'.gitkeep').is_file())
print('no _index:', not (e/'_index.md').exists())
"
```
Expected: `gitkeep: True` and `no _index: True`.

---

## Self-Review

**Spec coverage:**
- Spec §1 (init_vault) → Task 1. ✓
- Spec §2 (entity_writer: remove skip + add self-heal) → Task 2, Steps 3-4. ✓
- Spec §3 (scan_monorepo walk) → Task 3, Step 2. ✓
- Spec Tests bullet 1 (test_init_vault rewrite) → Task 1, Step 1. ✓
- Spec Tests bullet 2 (delete test_entities_walk_skips_index_md) → Task 3, Step 1. ✓
- Spec Tests bullet 3 (drop `!= "_index.md"` filter in integration test) → Task 2, Step 6. ✓
- Spec Tests bullet 4 (new write_entities coverage, both directions) → Task 2, Step 1. ✓
- Spec "Not doing" (no backward-compat, no `.gitignore`) → respected; no such tasks. ✓
- **Beyond spec:** Task 4 removes a fourth `_index.md` skip in `commands/scan.py` the spec missed; flagged in the task note. Task 3 also updates two docstrings the spec did not enumerate (purely descriptive, kept accurate).

**Placeholder scan:** No TBD/TODO/"handle edge cases" steps; every code step shows exact before/after text and exact commands with expected output.

**Type/identifier consistency:** Placeholder filename is `.gitkeep` throughout; the lifecycle variable is `gitkeep`/`entities_gitkeep`/`entities_dir`; `write_entities`/`init_wiki`/`_load_existing_pages`/`_snapshot_file_map_descriptions` names match the source. `unlink(missing_ok=True)` (Python ≥3.8) is valid on the ≥3.11 floor.
