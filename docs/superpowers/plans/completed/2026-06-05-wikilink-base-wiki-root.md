# Standardize Wikilink Base on the Wiki Root — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the wiki root (`<workspace>/wiki/`) the single base for all vault-relative paths and wikilink resolution, by moving `work/` under the wiki and rebasing both linters' vault walks from the workspace root to the wiki root — eliminating spurious "broken wikilink" reports for `[[entities/…]]`, `[[concepts/…]]`, `[[adrs/…]]`, `[[sources/…]]`, `[[architecture/…]]`.

**Architecture:** `workspace_io.paths.work_dir()` becomes the single definition of where `work/` lives (now `wiki_dir(workspace) / "work"`). Every other `work` locator routes through that helper. The two linters (`wiki_io/lint_wiki.py:scan` and `graph_wiki_core/commands/lint.py:_mechanical_pass`) walk `wiki.rglob("*.md")` and key pages relative to the wiki, so a page's top path-part is its real category dir (`entities`, `concepts`, `work`, …) instead of the literal `"wiki"`. `LINTED_TOPS` is re-derived to enumerate every real top-level vault dir so the *same* pages keep getting the *same* checks.

**Tech Stack:** Python 3.11, `uv` workspace, `pytest` (per-package), `pathlib`.

---

## Context the executor must know

- **No migration code.** Single-developer research project; the user deletes and rebuilds the workspace on layout changes (`CLAUDE.md`, `.claude/rules/backward-compatibility.md`). Do **not** write a move script.
- **Workspace ≠ repo.** The *workspace* holds `wiki/`, `raw/`, and (today) a sibling `work/`. After this change `work/` lives at `<workspace>/wiki/work/`.
- **`resolve_wiki_and_repo(workspace_path)` returns `wiki_dir(workspace_path)`** — i.e. it *appends* `/wiki`. This matters for every test: to make the resolved `wiki` point at real content, the test must place content under `<passed_path>/wiki/…` (or pass the content dir's parent). Several existing tests violate this and only pass today because the linter currently walks `wiki.parent` (the workspace). Rebasing the walk to the wiki **breaks them** — this plan fixes them.
- **Line numbers in this plan are current as of HEAD `14dd7397`** (after the `part-1-cleanup-boundary` merge). The original spec (`docs/superpowers/specs/2026-06-05-wikilink-base-wiki-root-design.md`) was written before that merge; its line numbers and its `link_rewriter.py` reference are stale. `link_rewriter.py` is **already deleted** — ignore the spec's SSOT-guard exception for it.
- **Run tests scoped per package**, never from the workspace root:
  - `uv run --package workspace-io pytest`
  - `uv run --package wiki-io pytest`
  - `uv run --package graph-wiki-core pytest -m "not integration"`
- **Shadowing trap:** four files have a local variable literally named `work_dir`. After importing the `work_dir` helper, the local must be renamed (this plan uses `work_root`) or the helper is shadowed.

---

## File Structure (what each task touches)

| Task | File | Responsibility |
|---|---|---|
| 1 | `packages/workspace-io/src/workspace_io/paths.py` | SSOT chokepoint: `work_dir` → under the wiki |
| 1 | `packages/workspace-io/tests/test_paths.py` | Update `test_work_dir` expectation |
| 2 | `packages/wiki-io/src/wiki_io/backlink_index.py` | Route work locator through helper |
| 2 | `packages/wiki-io/src/wiki_io/ingest_work_item.py` | Route work locator through helper |
| 2 | `packages/wiki-io/src/wiki_io/update_tokens.py` | Route work locator through helper (report path unchanged) |
| 3 | `packages/wiki-io/src/wiki_io/update_index.py` | `scan_work` locator + `rel`-to-wiki; work index path |
| 4 | `packages/wiki-io/src/wiki_io/index_generator.py` | `_scan_work` locator + `rel`-to-wiki |
| 4 | `packages/wiki-io/tests/test_index_generator.py` | Move work fixtures under `wiki/work/` |
| 5 | `packages/wiki-io/src/wiki_io/init_vault.py` | Create `work/` under the wiki; fix result path + layout strings |
| 6 | `packages/wiki-io/src/wiki_io/lint_wiki.py` | Rebase walk to wiki root; re-derive `LINTED_TOPS` |
| 6 | `packages/wiki-io/tests/test_lint_wiki.py` | Update keys; add regression + behavior-preservation tests |
| 7 | `packages/graph-wiki-core/src/graph_wiki_core/commands/lint.py` | Rebase `_mechanical_pass` walk to wiki root; re-derive `LINTED_TOPS` |
| 7 | `packages/graph-wiki-core/tests/unit/test_commands_lint.py` | Fix faithful layout; add regression + behavior-preservation tests |
| 7 | `packages/graph-wiki-core/tests/commands/test_lint_parity.py` | Wrap fixture so resolved wiki = fixture |
| 8 | — | SSOT grep guard + full-suite verification |

---

## Task 1: Redefine the `work_dir` chokepoint

**Files:**
- Modify: `packages/workspace-io/src/workspace_io/paths.py:23-24`
- Test: `packages/workspace-io/tests/test_paths.py:12-13`

- [ ] **Step 1: Update the failing test first**

In `packages/workspace-io/tests/test_paths.py`, change `test_work_dir` to expect the wiki-nested location:

```python
def test_work_dir(tmp_path):
    assert work_dir(tmp_path) == tmp_path / "wiki" / "work"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --package workspace-io pytest tests/test_paths.py::test_work_dir -v`
Expected: FAIL — `assert .../work == .../wiki/work` (helper still returns `tmp_path / "work"`).

- [ ] **Step 3: Redefine `work_dir` in `paths.py`**

Replace lines 23-24:

```python
def work_dir(workspace: Path) -> Path:
    return Path(workspace) / "work"
```

with:

```python
def work_dir(workspace: Path) -> Path:
    # work/ lives UNDER the wiki so [[work/foo]] resolves against the wiki
    # root identically to [[concepts/foo]] (single vault-relative base).
    return wiki_dir(workspace) / "work"
```

(`wiki_dir` is defined directly above in the same module — no import needed.)

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run --package workspace-io pytest tests/test_paths.py -v`
Expected: PASS (all paths tests).

- [ ] **Step 5: Commit**

```bash
git add packages/workspace-io/src/workspace_io/paths.py packages/workspace-io/tests/test_paths.py
git commit -m "feat(paths): work_dir resolves under the wiki root (single vault base)"
```

---

## Task 2: Route the simple work locators through the helper

These three callers only *locate* the work directory (iterate it / create pages in it). None of them emit wikilinks whose base changed, and `update_tokens` keeps its workspace-relative report path. Each has a local variable that shadows the helper — rename it to `work_root`.

**Files:**
- Modify: `packages/wiki-io/src/wiki_io/backlink_index.py:78-79`
- Modify: `packages/wiki-io/src/wiki_io/ingest_work_item.py:147`
- Modify: `packages/wiki-io/src/wiki_io/update_tokens.py:196-201`

- [ ] **Step 1: `backlink_index.py` — import helper + rebase locator**

Add the import near the top (after line 19 `from pathlib import Path`):

```python
from workspace_io.paths import work_dir
```

Replace lines 78-79:

```python
    # work/ is a sibling of the wiki (workspace-rooted).
    work_dir = wiki.parent / "work"
    if work_dir.is_dir():
        for p in sorted(work_dir.rglob("*.md")):
```

with:

```python
    # work/ lives under the wiki (wiki-rooted, like every other category).
    work_root = work_dir(wiki.parent)
    if work_root.is_dir():
        for p in sorted(work_root.rglob("*.md")):
```

- [ ] **Step 2: `ingest_work_item.py` — import helper + rebase locator**

Add the import after line 26 (`from typing import NoReturn`):

```python
from workspace_io.paths import work_dir
```

Replace line 147:

```python
    work_root = wiki.parent / "work"
```

with:

```python
    work_root = work_dir(wiki.parent)
```

(The local is already `work_root` here — only the right-hand side changes. The `detail=f"work/{page_path.name}"` log string on line 165 stays — it is already wiki-relative.)

- [ ] **Step 3: `update_tokens.py` — import helper + rebase locator (keep report path)**

Add the import after line 15 (`from pathlib import Path`):

```python
from workspace_io.paths import work_dir
```

Replace lines 196-201:

```python
    # Process work items (sibling of wiki)
    work_dir = workspace / "work"
    if work_dir.exists():
        for page in iter_pages(work_dir):
            status, _ = update_page(page, dry_run=dry_run, model_id=model_id, region=region)
            result[status].append(str(page.relative_to(workspace)))
```

with:

```python
    # Process work items (now under the wiki)
    work_root = work_dir(workspace)
    if work_root.exists():
        for page in iter_pages(work_root):
            status, _ = update_page(page, dry_run=dry_run, model_id=model_id, region=region)
            result[status].append(str(page.relative_to(workspace)))
```

(`page.relative_to(workspace)` stays: this is a status-report list, and wiki pages on line 194 also report workspace-relative — keeping work pages workspace-relative remains internally consistent.)

- [ ] **Step 4: Run the affected unit tests**

Run: `uv run --package wiki-io pytest tests/test_backlink_index.py tests/test_ingest_work_item.py tests/test_update_tokens.py -v`
Expected: PASS. (These tests assert page existence / log detail / report shape, none of which changed. `test_ingest_work_item` reads `result["page_path"]` and asserts it exists — the page is now created under `wiki/work/` and still exists.)

- [ ] **Step 5: Commit**

```bash
git add packages/wiki-io/src/wiki_io/backlink_index.py packages/wiki-io/src/wiki_io/ingest_work_item.py packages/wiki-io/src/wiki_io/update_tokens.py
git commit -m "refactor(wiki-io): route simple work locators through work_dir helper"
```

---

## Task 3: `update_index.scan_work` — locator + wiki-relative keys

`scan_work` feeds `_entry_link`, which decides the wikilink prefix by testing `stem.startswith("work/")`. After moving `work/` under the wiki, the entry `path` must still start with `work/` — so `rel` must be computed relative to the **wiki**, not the workspace. This task changes both the locator and `rel`.

**Files:**
- Modify: `packages/wiki-io/src/wiki_io/update_index.py:126-160` (`scan_work`)
- Modify: `packages/wiki-io/src/wiki_io/update_index.py:300-306` (work index path)

- [ ] **Step 1: Write a failing test for `scan_work` wiki-rooted location**

Append to `packages/wiki-io/tests/test_update_index_surgical.py` (create the import block if the file lacks it — check the top of the file first):

```python
def test_scan_work_reads_work_under_wiki(tmp_path):
    """scan_work locates work/ under the wiki and keys entries 'work/<name>'."""
    from wiki_io.update_index import scan_work

    workspace = tmp_path
    work = workspace / "wiki" / "work"
    work.mkdir(parents=True)
    (work / "2026-05-03-foo.md").write_text(
        "---\ntitle: Foo\nsummary: s\n---\n\nBody.\n", encoding="utf-8"
    )

    entries = scan_work(workspace)

    assert len(entries) == 1
    assert entries[0]["path"] == "work/2026-05-03-foo.md"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run --package wiki-io pytest tests/test_update_index_surgical.py::test_scan_work_reads_work_under_wiki -v`
Expected: FAIL — `scan_work` looks at `workspace/work` (absent) → returns `[]` → `len(entries) == 0`.

- [ ] **Step 3: Add the import**

In `packages/wiki-io/src/wiki_io/update_index.py`, add after line 14 (`from pathlib import Path`):

```python
from workspace_io.paths import wiki_dir, work_dir
```

- [ ] **Step 4: Rebase `scan_work` (lines 126-145)**

Replace:

```python
def scan_work(workspace):
    """Scan <workspace>/work/ for work-item pages.

    Returns a list of entries shaped like scan_vault() values. Paths are
    workspace-relative (e.g. "work/2026-05-03-foo.md") so they render as
    workspace-rooted wikilinks. Skips the generated work index, dotfiles,
    and the archived/ sub-namespace (owned by graph-wiki work lifecycle).
    """
    work_dir = workspace / "work"
    if not work_dir.exists():
        return []
    entries = []
    for md in sorted(work_dir.rglob("*.md")):
        rel = md.relative_to(workspace)
```

with:

```python
def scan_work(workspace):
    """Scan <workspace>/wiki/work/ for work-item pages.

    Returns a list of entries shaped like scan_vault() values. Paths are
    wiki-relative (e.g. "work/2026-05-03-foo.md") so they render as
    wiki-rooted wikilinks. Skips the generated work index, dotfiles,
    and the archived/ sub-namespace (owned by graph-wiki work lifecycle).
    """
    work_root = work_dir(workspace)
    if not work_root.exists():
        return []
    wiki = wiki_dir(workspace)
    entries = []
    for md in sorted(work_root.rglob("*.md")):
        rel = md.relative_to(wiki)
```

(`work_root` = `<workspace>/wiki/work`; `wiki` = `<workspace>/wiki`; so `rel` = `work/<name>.md` — the emitted `path` is unchanged. The rest of the loop body and the `archived` skip are unchanged.)

- [ ] **Step 5: Rebase the work index path (lines 300-306)**

Replace:

```python
    if work_entries:
        work_index_path = wiki.parent / "work" / "index.md"
```

with:

```python
    if work_entries:
        work_index_path = work_dir(wiki.parent) / "index.md"
```

(`wiki` here is the local `vault`/`wiki` param of `update_index`; `wiki.parent` is the workspace, so `work_dir(wiki.parent)` = `<workspace>/wiki/work`.)

- [ ] **Step 6: Run the new test + existing update_index tests**

Run: `uv run --package wiki-io pytest tests/test_update_index_surgical.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add packages/wiki-io/src/wiki_io/update_index.py packages/wiki-io/tests/test_update_index_surgical.py
git commit -m "feat(update_index): scan_work reads work/ under the wiki, keys wiki-relative"
```

---

## Task 4: `index_generator._scan_work` — locator + wiki-relative keys

Same shape as Task 3: `_scan_work` feeds `_entry_link` (line 447-456), which keeps `work/`-prefixed paths un-prefixed. After the move, `rel` must be relative to the wiki so the path still starts with `work/`. This task also fixes the existing `TestWorkScan` fixtures, which create work files at `tmp_path/work/` and must move to `tmp_path/wiki/work/`.

**Files:**
- Modify: `packages/wiki-io/src/wiki_io/index_generator.py:487-513` (`_scan_work`)
- Modify: `packages/wiki-io/tests/test_index_generator.py` (`TestWorkScan`)

- [ ] **Step 1: Update the `TestWorkScan` fixtures (failing first)**

In `packages/wiki-io/tests/test_index_generator.py`, the `TestWorkScan` class creates work files via `_write_curated_page(tmp_path / "work" / …)` and calls `_scan_work(tmp_path)`. Change every `tmp_path / "work"` inside `TestWorkScan` to `tmp_path / "wiki" / "work"`. The three affected methods:

```python
class TestWorkScan:
    def test_no_work_directory(self, tmp_path):
        assert _scan_work(tmp_path) == []

    def test_basic_work_scan(self, tmp_path):
        _write_curated_page(
            tmp_path / "wiki" / "work" / "2026-05-03-foo.md", title="Foo work item"
        )
        entries = _scan_work(tmp_path)
        assert len(entries) == 1
        assert entries[0]["path"] == "work/2026-05-03-foo.md"

    def test_skips_work_index(self, tmp_path):
        _write_curated_page(tmp_path / "wiki" / "work" / "foo.md", title="Foo")
        _write_curated_page(tmp_path / "wiki" / "work" / "index.md", title="Idx")
        entries = _scan_work(tmp_path)
        assert [e["title"] for e in entries] == ["Foo"]

    def test_skips_archived_subdir(self, tmp_path):
        _write_curated_page(tmp_path / "wiki" / "work" / "foo.md", title="Foo")
        _write_curated_page(tmp_path / "wiki" / "work" / "archived" / "old.md", title="Old")
```

(Keep the remainder of `test_skips_archived_subdir` — its assertions — unchanged. `test_no_work_directory` needs no edit: `tmp_path/wiki/work` is absent → `[]`.)

- [ ] **Step 2: Run to verify `test_basic_work_scan` / `test_skips_work_index` fail**

Run: `uv run --package wiki-io pytest tests/test_index_generator.py::TestWorkScan -v`
Expected: FAIL — `_scan_work(tmp_path)` still reads `tmp_path/work` (now empty) → entries empty.

- [ ] **Step 3: Add the import**

In `packages/wiki-io/src/wiki_io/index_generator.py`, add after line 45 (`from pathlib import Path`):

```python
from workspace_io.paths import wiki_dir, work_dir
```

- [ ] **Step 4: Rebase `_scan_work` (lines 487-504)**

Replace:

```python
def _scan_work(workspace_root: Path) -> list[dict[str, str]]:
    """Walk `workspace_root / 'work'` for *.md pages; workspace-rooted paths.

    Returns [] if `work/` does not exist. Skips `index.md`, dotfiles, and
    the `archived/` sub-namespace.
    """
    work_dir = workspace_root / "work"
    if not work_dir.exists():
        return []
    entries: list[dict[str, str]] = []
    for md in sorted(work_dir.rglob("*.md")):
        rel = md.relative_to(workspace_root)
```

with:

```python
def _scan_work(workspace_root: Path) -> list[dict[str, str]]:
    """Walk `workspace_root / 'wiki' / 'work'` for *.md pages; wiki-rooted paths.

    Returns [] if `work/` does not exist. Skips `index.md`, dotfiles, and
    the `archived/` sub-namespace.
    """
    work_root = work_dir(workspace_root)
    if not work_root.exists():
        return []
    wiki = wiki_dir(workspace_root)
    entries: list[dict[str, str]] = []
    for md in sorted(work_root.rglob("*.md")):
        rel = md.relative_to(wiki)
```

(The loop body, `index.md`/dotfile/`archived` skips, and entry construction are unchanged. `rel` = `work/<name>.md`.)

- [ ] **Step 5: Run the work-scan tests + the full index_generator suite**

Run: `uv run --package wiki-io pytest tests/test_index_generator.py -v`
Expected: PASS (TestWorkScan green; `test_entry_link_wiki_vs_work` unaffected — `_entry_link` was not touched).

- [ ] **Step 6: Commit**

```bash
git add packages/wiki-io/src/wiki_io/index_generator.py packages/wiki-io/tests/test_index_generator.py
git commit -m "feat(index_generator): _scan_work reads work/ under the wiki, keys wiki-relative"
```

---

## Task 5: `init_vault` — create `work/` under the wiki

**Files:**
- Modify: `packages/wiki-io/src/wiki_io/init_vault.py:118-121` (creation)
- Modify: `packages/wiki-io/src/wiki_io/init_vault.py:218` (result path)
- Modify: `packages/wiki-io/src/wiki_io/init_vault.py:233,238` (layout description strings — now stale)

- [ ] **Step 1: Add the import**

In `packages/wiki-io/src/wiki_io/init_vault.py`, add after line 23 (`from workspace_io.init import init as _workspace_init`):

```python
from workspace_io.paths import work_dir
```

- [ ] **Step 2: Create `work/` under the wiki (lines 118-121)**

Replace:

```python
    workspace_path = wiki_path.parent
    # Create raw/ and work/ workspace sibling directories.
    (workspace_path / "raw").mkdir(parents=True, exist_ok=True)
    (workspace_path / "work").mkdir(parents=True, exist_ok=True)
```

with:

```python
    workspace_path = wiki_path.parent
    # raw/ is a workspace sibling; work/ now lives under the wiki.
    (workspace_path / "raw").mkdir(parents=True, exist_ok=True)
    work_dir(workspace_path).mkdir(parents=True, exist_ok=True)
```

- [ ] **Step 3: Fix the result path (line 218) and layout strings (lines 233, 238)**

Replace line 218:

```python
        "work_path": str(workspace_path / "work"),
```

with:

```python
        "work_path": str(work_dir(workspace_path)),
```

Replace the `layers["work"]` line (233):

```python
            "work": f"{workspace_path}/work/ — work item pages",
```

with:

```python
            "work": f"{wiki_path}/work/ — work item pages",
```

Replace the first `next_steps` entry (line 238):

```python
            f"Open {workspace_path} in Obsidian (sidebar shows wiki/, raw/, work/ as siblings)",
```

with:

```python
            f"Open {workspace_path} in Obsidian (sidebar shows wiki/ and raw/; work/ lives under wiki/)",
```

- [ ] **Step 4: Write a test asserting work/ is created under the wiki**

Append to `packages/wiki-io/tests/test_init_vault.py`. This mirrors the existing tests' setup and `init_wiki(...)` call shape exactly (see `test_init_wiki_*` at the top of that file):

```python
def test_work_dir_created_under_wiki(tmp_path, monkeypatch):
    from wiki_io import init_vault
    from workspace_io.paths import work_dir

    repo = tmp_path / "repo"
    workspace = tmp_path / "ws"
    wiki = workspace / "wiki"
    repo.mkdir()
    (repo / "pyproject.toml").write_text(
        '[project]\nname="solo"\nversion="0.0.1"\n', encoding="utf-8"
    )
    monkeypatch.setattr(init_vault, "_workspace_init", lambda *a, **k: None)

    init_vault.init_wiki(
        wiki, repo, topic="Agent Research", tool="claude-code", force=False, non_interactive=True
    )

    assert work_dir(workspace).is_dir(), "work/ must be created under the wiki"
    assert not (workspace / "work").exists(), "no stale sibling work/ dir"
```

- [ ] **Step 5: Run init_vault tests**

Run: `uv run --package wiki-io pytest tests/test_init_vault.py -v`
Expected: PASS — including the new test and all pre-existing ones (none asserted the sibling `work/` location).

- [ ] **Step 6: Commit**

```bash
git add packages/wiki-io/src/wiki_io/init_vault.py packages/wiki-io/tests/test_init_vault.py
git commit -m "feat(init_vault): create work/ under the wiki; correct layout description"
```

---

## Task 6: Rebase `wiki_io/lint_wiki.py:scan` to the wiki root

Walk `wiki.rglob` instead of `workspace.rglob`; key pages relative to the wiki; re-derive `LINTED_TOPS` to enumerate every real top-level vault dir so the same pages keep getting the same checks.

**Files:**
- Modify: `packages/wiki-io/src/wiki_io/lint_wiki.py:47` (`LINTED_TOPS`)
- Modify: `packages/wiki-io/src/wiki_io/lint_wiki.py:72,79-80,141-142` (walk root)
- Modify/Add: `packages/wiki-io/tests/test_lint_wiki.py`

- [ ] **Step 1: Add a regression test (failing first)**

Append to `packages/wiki-io/tests/test_lint_wiki.py`:

```python
def test_wiki_rooted_links_not_broken(tmp_path):
    """[[entities/x]], [[concepts/y]], [[work/z]] all resolve against the
    wiki root → zero broken links."""
    from wiki_io.lint_wiki import scan

    workspace = tmp_path / "workspace"
    wiki = workspace / "wiki"
    (wiki / "entities").mkdir(parents=True)
    (wiki / "concepts").mkdir(parents=True)
    (wiki / "work").mkdir(parents=True)

    (wiki / "entities" / "x.md").write_text(
        "---\ntitle: X\nuri: pkg:o/r/x\nkind: package\n---\n\nbody\n", encoding="utf-8"
    )
    (wiki / "concepts" / "y.md").write_text(
        "---\ntitle: Y\ncategory: concept\nsummary: s\ntokens: 1\n---\n\nbody\n", encoding="utf-8"
    )
    (wiki / "work" / "z.md").write_text(
        "---\ntitle: Z\ncategory: work\nsummary: s\n---\n\nbody\n", encoding="utf-8"
    )
    (wiki / "concepts" / "hub.md").write_text(
        "---\ntitle: Hub\ncategory: concept\nsummary: s\ntokens: 1\n---\n\n"
        "[[entities/x]] [[concepts/y]] [[work/z]]\n",
        encoding="utf-8",
    )

    result = scan(wiki, stale_days=90, log_gap_days=14)

    assert result["broken_links"] == [], result["broken_links"]


def test_all_vault_categories_are_linted(tmp_path):
    """Behavior preservation: a malformed page in every real top-level vault dir
    is flagged for missing frontmatter (i.e. every category is linted)."""
    from wiki_io.lint_wiki import scan

    workspace = tmp_path / "workspace"
    wiki = workspace / "wiki"
    curated_tops = ["concepts", "adrs", "architecture", "sources", "proposals"]
    for top in curated_tops:
        (wiki / top).mkdir(parents=True)
        # missing category + summary → flagged under the curated contract
        (wiki / top / "bad.md").write_text("---\ntitle: B\n---\n\nbody\n", encoding="utf-8")
    # entities/ page missing uri → flagged under the entity contract
    (wiki / "entities").mkdir(parents=True)
    (wiki / "entities" / "bad.md").write_text(
        "---\ntitle: B\nkind: package\n---\n\nbody\n", encoding="utf-8"
    )
    # work/ page missing category + summary → flagged (work is linted)
    (wiki / "work").mkdir(parents=True)
    (wiki / "work" / "bad.md").write_text("---\ntitle: B\n---\n\nbody\n", encoding="utf-8")

    result = scan(wiki, stale_days=90, log_gap_days=14)
    mf = set(result["missing_frontmatter"])

    for top in curated_tops:
        assert f"{top}/bad" in mf, f"{top}/bad not linted/flagged: {mf}"
    assert "entities/bad" in mf
    assert "work/bad" in mf
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run --package wiki-io pytest tests/test_lint_wiki.py::test_wiki_rooted_links_not_broken tests/test_lint_wiki.py::test_all_vault_categories_are_linted -v`
Expected: FAIL — today `scan` walks `wiki.parent`, so pages key as `wiki/entities/x` (links don't match → broken) and `LINTED_TOPS = {"wiki","work"}` keys real category dirs as not-linted once we rebase. (Pre-change: links broken → first test fails; second may pass-by-accident because `top=="wiki"` today, but it will be the guard after the rebase.)

- [ ] **Step 3: Re-derive `LINTED_TOPS` (line 47)**

Replace:

```python
LINTED_TOPS = {"wiki", "work"}
```

with:

```python
# Every real top-level vault dir under the wiki root. Walking from the wiki
# (not the workspace) means a page's top path-part is its category dir, so
# LINTED_TOPS must enumerate them all to keep the same pages linted as before.
LINTED_TOPS = {"concepts", "adrs", "architecture", "sources", "entities", "proposals", "work"}
```

- [ ] **Step 4: Rebase the walk root (lines 72, 79-80, 141-142)**

Line 72 stays as-is — `workspace = wiki.parent` is still needed for the `check_workflow_hints(pages, workspace)` call on line 337. Only the two `rglob` loops change.

First loop — replace lines 79-80:

```python
    for md in workspace.rglob("*.md"):
        rel = md.relative_to(workspace)
```

with:

```python
    for md in wiki.rglob("*.md"):
        rel = md.relative_to(wiki)
```

Second loop (index.md parser) — replace lines 141-142:

```python
    for md in workspace.rglob("*.md"):
        rel = md.relative_to(workspace)
```

with:

```python
    for md in wiki.rglob("*.md"):
        rel = md.relative_to(wiki)
```

(`top in LINTED_TOPS` on line 107 now reads the real category names directly; no `effective_linted_tops` shim exists in this module.)

- [ ] **Step 5: Update existing key-prefixed assertions**

Two existing tests assert `wiki/…`-prefixed keys. After the rebase those keys lose the `wiki/` prefix.

In `test_schema_files_excluded_from_page_enumeration` (lines ~122-128) change every `"wiki/CLAUDE"` → `"CLAUDE"` and `"wiki/AGENTS"` → `"AGENTS"`:

```python
    assert "CLAUDE" not in result["missing_frontmatter"]
    assert "AGENTS" not in result["missing_frontmatter"]
    assert "CLAUDE" not in result["missing_tokens"]
    assert "AGENTS" not in result["missing_tokens"]
    assert "CLAUDE" not in result["orphans"]
    assert "AGENTS" not in result["orphans"]
```

In `test_entity_pages_use_entity_frontmatter_contract` (lines ~282-285) change the keys:

```python
    assert "entities/pkg_alpha" not in result["missing_frontmatter"]
    assert "entities/pkg_alpha" not in result["missing_tokens"]
    # The curated page is still held to the curated contract.
    assert "concepts/bad" in result["missing_frontmatter"]
    assert "concepts/bad" in result["missing_tokens"]
```

(The code-drift tests assert counts, not keys, and code-drift iterates all pages regardless of `linted` — they need no change.)

- [ ] **Step 6: Run the full lint_wiki suite**

Run: `uv run --package wiki-io pytest tests/test_lint_wiki.py -v`
Expected: PASS (regression + behavior-preservation green; updated key assertions green; code-drift / schema tests green).

- [ ] **Step 7: Commit**

```bash
git add packages/wiki-io/src/wiki_io/lint_wiki.py packages/wiki-io/tests/test_lint_wiki.py
git commit -m "fix(lint_wiki): walk the wiki root; enumerate all vault tops in LINTED_TOPS"
```

---

## Task 7: Rebase `graph_wiki_core/commands/lint.py:_mechanical_pass` to the wiki root

Same rebase as Task 6, for the Bedrock linter. Drop the `effective_linted_tops` shim and the now-unused `workspace` parameter; re-derive `LINTED_TOPS`. Then fix the tests whose fixtures relied on walk-from-workspace.

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/lint.py:57-62` (`LINTED_TOPS`)
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/lint.py:117-211` (`_mechanical_pass`)
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/lint.py:526` (call site)
- Modify: `packages/graph-wiki-core/tests/unit/test_commands_lint.py`
- Modify: `packages/graph-wiki-core/tests/commands/test_lint_parity.py`

- [ ] **Step 1: Add regression + behavior-preservation tests (failing first)**

Append to `packages/graph-wiki-core/tests/unit/test_commands_lint.py`:

```python
@pytest.mark.asyncio
async def test_run_lint_wiki_rooted_links_not_broken(tmp_path) -> None:
    """[[entities/x]] / [[concepts/y]] / [[work/z]] resolve against the wiki
    root → result.broken_links is empty."""
    from graph_wiki_core.commands.lint import run_lint
    from subagent_runtime.pool import FanOutResult

    wiki = tmp_path / "wiki"
    (wiki / "entities").mkdir(parents=True)
    (wiki / "concepts").mkdir(parents=True)
    (wiki / "work").mkdir(parents=True)
    (wiki / "entities" / "x.md").write_text(
        "---\ntitle: X\ncategory: entity\nsummary: s\n---\n\nbody\n", encoding="utf-8"
    )
    (wiki / "concepts" / "y.md").write_text(
        "---\ntitle: Y\ncategory: concept\nsummary: s\n---\n\nbody\n", encoding="utf-8"
    )
    (wiki / "work" / "z.md").write_text(
        "---\ntitle: Z\ncategory: work\nsummary: s\n---\n\nbody\n", encoding="utf-8"
    )
    (wiki / "concepts" / "hub.md").write_text(
        "---\ntitle: Hub\ncategory: concept\nsummary: s\n---\n\n"
        "[[entities/x]] [[concepts/y]] [[work/z]]\n",
        encoding="utf-8",
    )

    with patch("graph_wiki_core.commands.lint.SubagentPool") as MockPool:
        mock_pool = MagicMock()
        MockPool.return_value = mock_pool
        mock_pool.run_all = AsyncMock(return_value=FanOutResult(successes=[], errors=[]))
        # workspace_path=tmp_path → resolve appends /wiki → wiki dir above.
        result = await run_lint(workspace_path=tmp_path)

    assert result.broken_links == [], result.broken_links


@pytest.mark.asyncio
async def test_run_lint_all_vault_categories_linted(tmp_path) -> None:
    """A malformed page in every real top-level vault dir is flagged for
    missing frontmatter (every category is linted after the rebase)."""
    from graph_wiki_core.commands.lint import run_lint
    from subagent_runtime.pool import FanOutResult

    wiki = tmp_path / "wiki"
    tops = ["concepts", "adrs", "architecture", "sources", "entities", "proposals", "work"]
    for top in tops:
        (wiki / top).mkdir(parents=True)
        (wiki / top / "bad.md").write_text("---\ntitle: B\n---\n\nbody\n", encoding="utf-8")

    with patch("graph_wiki_core.commands.lint.SubagentPool") as MockPool:
        mock_pool = MagicMock()
        MockPool.return_value = mock_pool
        mock_pool.run_all = AsyncMock(return_value=FanOutResult(successes=[], errors=[]))
        result = await run_lint(workspace_path=tmp_path)

    mf = set(result.missing_frontmatter)
    for top in tops:
        assert f"{top}/bad" in mf, f"{top}/bad not flagged (not linted): {mf}"
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_commands_lint.py::test_run_lint_wiki_rooted_links_not_broken tests/unit/test_commands_lint.py::test_run_lint_all_vault_categories_linted -v`
Expected: FAIL — today `_mechanical_pass` walks `wiki.parent` (= `tmp_path`), keys pages `wiki/entities/x` etc., so the hub's links are broken and `entities`/`proposals`/etc. are linted only via the `{wiki.name}` shim (which the rebase removes).

- [ ] **Step 3: Re-derive `LINTED_TOPS` (lines 57-62)**

Replace:

```python
# Tops that get full lint treatment (orphans, stale, missing-fm checks).
# Adapted from lint_wiki.py (line 59) — diverges from upstream {"wiki", "work"}:
# upstream's vault top-level is "wiki" which contains all category dirs, but in
# the new architecture the wiki root IS the vault path, so LINTED_TOPS covers
# the category dirs directly: concepts, packages, apps, domains, adrs, work.
LINTED_TOPS = {"wiki", "work", "concepts", "packages", "apps", "domains", "adrs"}
```

with:

```python
# Every real top-level vault dir under the wiki root. The mechanical pass walks
# from the wiki (not the workspace), so a page's top path-part is its category
# dir; LINTED_TOPS must enumerate them all to keep the same pages linted.
LINTED_TOPS = {"concepts", "adrs", "architecture", "sources", "entities", "proposals", "work"}
```

- [ ] **Step 4: Rebase `_mechanical_pass` — signature + both loops + drop the shim**

Change the signature (lines 117-122) from:

```python
def _mechanical_pass(
    wiki: Path,
    workspace: Path,
    stale_days: int,
    log_gap_days: int,
) -> dict:
```

to:

```python
def _mechanical_pass(
    wiki: Path,
    stale_days: int,
    log_gap_days: int,
) -> dict:
```

Delete the `effective_linted_tops` shim (lines 137-141):

```python
    # Build effective linted tops: the wiki directory name (usually "wiki") + "work",
    # plus the wiki directory name for any vault that uses a different name (e.g. fixtures).
    # This matches lint_wiki.py behavior where LINTED_TOPS = {"wiki", "work"} and the
    # vault is always named "wiki".
    effective_linted_tops = LINTED_TOPS | {wiki.name}
```

(remove these five lines entirely).

First loop — replace lines 143-144:

```python
    for md in workspace.rglob("*.md"):
        rel = md.relative_to(workspace)
```

with:

```python
    for md in wiki.rglob("*.md"):
        rel = md.relative_to(wiki)
```

On line 166, replace the `linted` computation that used the shim:

```python
            "linted": top in effective_linted_tops,
```

with:

```python
            "linted": top in LINTED_TOPS,
```

Second loop (index.md parser) — replace lines 203-204:

```python
    for md in workspace.rglob("*.md"):
        rel = md.relative_to(workspace)
```

with:

```python
    for md in wiki.rglob("*.md"):
        rel = md.relative_to(wiki)
```

- [ ] **Step 5: Update the call site (line 526)**

`run_lint` still computes `workspace = wiki.parent` on line 523 for `_module_pass(repo, wiki, workspace, pages)` (line 530) — leave that. Only the `_mechanical_pass` call changes. Replace line 526:

```python
    mech = _mechanical_pass(wiki, workspace, stale_days, log_gap_days)
```

with:

```python
    mech = _mechanical_pass(wiki, stale_days, log_gap_days)
```

- [ ] **Step 6: Run the new tests to verify they pass**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_commands_lint.py::test_run_lint_wiki_rooted_links_not_broken tests/unit/test_commands_lint.py::test_run_lint_all_vault_categories_linted -v`
Expected: PASS.

- [ ] **Step 7: Fix the broken-link unit test's layout (test 3)**

`test_run_lint_broken_links_skip_placeholder_targets` builds content under `tmp_path/wiki/…` but passes `workspace_path=wiki`, so the resolved wiki becomes `tmp_path/wiki/wiki` (empty) after the rebase. Fix it to pass the parent so the resolved wiki = the content dir. Change the final call from:

```python
        result = await run_lint(workspace_path=wiki)
```

to:

```python
        # resolve_wiki_and_repo appends /wiki, so pass the parent.
        result = await run_lint(workspace_path=tmp_path)
```

(No other line in that test changes — content is already under `tmp_path/wiki/concepts`.)

- [ ] **Step 8: Make the edge-case-vault tests resolve correctly (test 2)**

`test_run_lint_mechanical_finds_orphans_in_fixture` passes `workspace_path=EDGE_CASE_VAULT`; after the rebase the resolved wiki is `EDGE_CASE_VAULT/wiki` (absent). Wrap the fixture so the resolved wiki lands on it. Add this helper near the top of `test_commands_lint.py` (after the `EDGE_CASE_VAULT` definition):

```python
def _workspace_for(tmp_path: Path, vault: Path) -> Path:
    """Return a workspace dir whose `wiki/` is a symlink to `vault`, so
    resolve_wiki_and_repo(workspace) lands the walk on the fixture content."""
    link = tmp_path / "wiki"
    if not link.exists():
        link.symlink_to(vault, target_is_directory=True)
    return tmp_path
```

Then change `test_run_lint_mechanical_finds_orphans_in_fixture` to take `tmp_path` and use it:

```python
@pytest.mark.asyncio
async def test_run_lint_mechanical_finds_orphans_in_fixture(tmp_path) -> None:
    """run_lint against edge-case-vault: result.orphans is a list."""
    from graph_wiki_core.commands.lint import run_lint
    from subagent_runtime.pool import FanOutResult

    with patch("graph_wiki_core.commands.lint.SubagentPool") as MockPool:
        mock_pool = MagicMock()
        MockPool.return_value = mock_pool
        mock_pool.run_all = AsyncMock(return_value=FanOutResult(successes=[], errors=[]))
        result = await run_lint(workspace_path=_workspace_for(tmp_path, EDGE_CASE_VAULT))

    assert isinstance(result.orphans, list)
    assert isinstance(result.total_pages, int)
    assert result.total_pages >= 0
```

(Tests 6-10 in this file already work: test 6 mocks `resolve_wiki_and_repo` to return the real wiki; test 10 uses the faithful nested layout; tests 7-9 keep weak invariants under an empty walk. Leave them unchanged.)

- [ ] **Step 9: Fix the parity tests (wrap the fixture)**

`test_lint_parity.py`'s four tests pass `workspace_path=EDGE_CASE_VAULT` and assert non-empty `broken_links` / `missing_frontmatter`. Add the same helper and route each call through a wrapped workspace. Add near the top (after `EDGE_CASE_VAULT`):

```python
def _workspace_for(tmp_path: Path, vault: Path) -> Path:
    link = tmp_path / "wiki"
    if not link.exists():
        link.symlink_to(vault, target_is_directory=True)
    return tmp_path
```

Then give each of the four tests a `tmp_path` parameter and replace `workspace_path=EDGE_CASE_VAULT` with `workspace_path=_workspace_for(tmp_path, EDGE_CASE_VAULT)`. Concretely, for each test signature add `, tmp_path` and change the call. Example for `test_lint_edge_case_vault_has_broken_links`:

```python
@pytest.mark.asyncio
async def test_lint_edge_case_vault_has_broken_links(no_semantic_pool, tmp_path) -> None:
    """edge-case-vault has known broken links — result.broken_links is non-empty."""
    from graph_wiki_core.commands.lint import run_lint

    result = await run_lint(workspace_path=_workspace_for(tmp_path, EDGE_CASE_VAULT))

    assert isinstance(result.broken_links, list)
    assert len(result.broken_links) >= 1, (
        f"Expected at least 1 broken link in edge-case-vault, got: {result.broken_links}"
    )
```

Apply the identical `_workspace_for(tmp_path, EDGE_CASE_VAULT)` substitution to `test_lint_result_json_serializable`, `test_lint_edge_case_vault_has_missing_frontmatter`, and `test_lint_no_placeholder_targets_in_broken_links` (add `tmp_path` to each signature).

> Note on the fixture: `edge-case-vault` keys its pages directly (`concepts/broken-wikilinks` etc.). Its broken links are genuinely broken targets (not category-prefix mismatches), so they still surface as broken after the rebase. Its `missing-title` / `truncated-frontmatter` pages live under `concepts/` (in `LINTED_TOPS`), so they remain flagged.

- [ ] **Step 10: Run both core lint test files**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_commands_lint.py tests/commands/test_lint_parity.py -v`
Expected: PASS (all tests, including the two new ones).

- [ ] **Step 11: Run the override test that patches `_mechanical_pass`**

Run: `uv run --package graph-wiki-core pytest tests/test_command_overrides.py -v -k lint`
Expected: PASS — it patches `_mechanical_pass` with `return_value=…`, so the signature change is transparent.

- [ ] **Step 12: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/lint.py packages/graph-wiki-core/tests/unit/test_commands_lint.py packages/graph-wiki-core/tests/commands/test_lint_parity.py
git commit -m "fix(lint): walk the wiki root in _mechanical_pass; enumerate all vault tops"
```

---

## Task 8: SSOT guard + full-suite verification

**Files:** none (verification only).

- [ ] **Step 1: SSOT guard — `work` path-segment construction lives only in `paths.py`**

Run: `grep -rn '/ "work"' packages/*/src`
Expected: exactly one hit — `packages/workspace-io/src/workspace_io/paths.py`. (`link_rewriter.py` is already deleted, so the spec's exception for it no longer applies. Other `"work"` occurrences are dict keys / category labels / `top == "work"` comparisons / `LINTED_TOPS` members — not path constructions — and are out of scope.)

If any other `/ "work"` remains, route it through `work_dir(...)` per Tasks 2-5.

- [ ] **Step 2: Re-run the full affected suites**

Run:
```bash
uv run --package workspace-io pytest
uv run --package wiki-io pytest
uv run --package graph-wiki-core pytest -m "not integration"
```
Expected: all green.

- [ ] **Step 3: Lint + format check**

Run: `uv run ruff check packages/workspace-io/src packages/wiki-io/src packages/graph-wiki-core/src`
Expected: no new errors in the files this plan touched. (Do **not** run `ruff format` to fix unrelated pre-existing diff — match surrounding style by hand. See memory: the src tree is pre-existing format-dirty.)

- [ ] **Step 4: Manual smoke (optional but recommended)**

The real workspace pins `work/` as a sibling today. Per the no-migration policy, either rebuild the workspace or move the dir once:

```bash
# Inspect first — only move if a sibling work/ exists with pages worth keeping.
ls /Users/pat/Personal/graph-wiki/agent-research-bedrock/work 2>/dev/null
# If present and you want to keep it:
#   mv /Users/pat/Personal/graph-wiki/agent-research-bedrock/work \
#      /Users/pat/Personal/graph-wiki/agent-research-bedrock/wiki/work
```

Then run the linter and confirm the spurious broken-link errors are gone and `work/` pages are discovered under `wiki/work/`:

```bash
uv run --package graph-wiki-cli gw lint 2>&1 | grep -A3 'broken wikilink'
```

Expected: `[OK] broken wikilinks: 0` (or only genuinely-broken targets), and `work/…` pages present in the page set.

- [ ] **Step 5: Final commit (if any verification-driven tweaks were made)**

```bash
git add -A
git commit -m "test: verify wikilink-base rebase (SSOT guard + suites green)"
```

---

## Self-Review notes

- **Spec coverage:** §1 chokepoint → Task 1. §2 route locators → Tasks 2-5 (spec's `update_index.py:386` duplicate is gone post-merge; only the one at `:301` remains). §3 rebase vault walks → Tasks 6-7 (`scan_work` rel-to-wiki → Task 3; the spec missed the symmetric `index_generator._scan_work` rel fix → Task 4). §4 directory creation → Task 5. Verification (regression/behavior-preservation/SSOT/suites/manual) → embedded in Tasks 6, 7, 8.
- **Deviations from the spec, with rationale:**
  - The spec's `link_rewriter.py` SSOT exception is dropped — the file was deleted by the `part-1-cleanup-boundary` merge.
  - `index_generator._scan_work` gets the `rel`-to-wiki change (spec only flagged the locator); without it, emitted `[[work/…]]` links would double-prefix to `[[wiki/work/…]]`.
  - `_mechanical_pass` loses its now-unused `workspace` parameter (clean-up of an orphan created by the rebase); the call site and the one mock test that patches it both tolerate this.
  - Test-fixture fixes (Tasks 4, 6, 7) are **not** in the spec but are required: the lint fixtures pass the vault root as `workspace_path` and rely on the old walk-from-workspace; rebasing breaks them.
- **Type/name consistency:** the helper is `work_dir(workspace) -> Path`; every local that previously held `… / "work"` is renamed to `work_root` to avoid shadowing it. `wiki_dir(workspace)` is the rel base wherever a wiki-relative key is emitted (`scan_work`, `_scan_work`).
- **Out of scope (unchanged):** `lint/domain.py` (keys off vanished `domains/`/`packages/`), entity-page missing-frontmatter noise (preserved exactly), and any pre-existing `[[wiki/…]]`-prefixed links (would now flag broken — migration territory).
