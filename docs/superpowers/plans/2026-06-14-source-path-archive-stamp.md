# Source `source_path` Archive-Stamp Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use graph-wiki:subagent-driven-development (recommended) or graph-wiki:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a source page's `source_path` frontmatter record where the source currently lives — `raw/_archive/...` after the post-ingest move — on both ingest surfaces, and add a lint check that flags stale `raw/` pointers.

**Architecture:** The Bedrock harness already moves the raw source and computes `archived_to` at the tail of `_run_common_tail`; we add a deterministic frontmatter rewrite after a successful move. The CC plugin agent writes the page before archiving, so we update its instructions to record the (deterministic) post-archive path up front. A new mechanical lint check flags source pages whose `raw/` `source_path` no longer exists on disk.

**Tech Stack:** Python 3.11, `uv` workspace, pytest (`asyncio_mode = "auto"`), Typer CLI. Packages: `graph-wiki-core` (ingest + lint), `graph-wiki-cli` (lint report), `wiki-io` (template), plus the `plugins/graph-wiki/` markdown surface.

**Spec:** `docs/superpowers/specs/2026-06-14-source-path-archive-stamp-design.md`

---

### Task 1: Stamp the archive location into the source page frontmatter (Bedrock harness)

**Goal:** After a successful raw-source archive move, rewrite the written source page's `source_path:` frontmatter to the workspace-relative archive destination.

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py` (add `_set_source_path_in_body` near `_set_source_type_in_body` ~line 366; wire into `_run_common_tail` after the archive block ~line 1046)
- Test: `packages/graph-wiki-core/tests/unit/test_commands_ingest.py`

**Acceptance Criteria:**
- [ ] `_set_source_path_in_body` replaces an existing `source_path:` line in place (preserving indent/order), inserts as the first frontmatter field when absent, is idempotent, and returns text unchanged when there is no `---` block.
- [ ] After ingesting a source under `raw/`, the written page on disk contains `source_path: raw/_archive/<rel>` matching `result.archived_to`.
- [ ] A source outside `raw/` (archived_to is None) leaves the page's `source_path` untouched.
- [ ] A failed move leaves the page's `source_path` untouched.
- [ ] `result.source_path` (the `IngestResult` field) still equals the original input path — existing contract unchanged.

**Verify:** `uv run --package graph-wiki-core pytest tests/unit/test_commands_ingest.py -k "source_path or archive" -v` → all PASS

**Steps:**

- [ ] **Step 1: Write the failing unit tests for the helper**

Add to `packages/graph-wiki-core/tests/unit/test_commands_ingest.py` (near the existing `test_set_source_type_in_body_inserts_and_is_idempotent` ~line 1170):

```python
def test_set_source_path_in_body_replaces_in_place_and_is_idempotent() -> None:
    from graph_wiki_core.commands.ingest import _set_source_path_in_body

    text = "---\ntitle: X\nsource_path: raw/specs/x.md\nsource_type: spec\n---\n\nBody\n"
    out = _set_source_path_in_body(text, "raw/_archive/specs/x.md")
    assert "source_path: raw/_archive/specs/x.md" in out
    assert "raw/specs/x.md" not in out
    # order preserved: source_path stays between title and source_type
    assert out.index("title:") < out.index("source_path:") < out.index("source_type:")
    # idempotent
    assert _set_source_path_in_body(out, "raw/_archive/specs/x.md") == out


def test_set_source_path_in_body_inserts_when_absent() -> None:
    from graph_wiki_core.commands.ingest import _set_source_path_in_body

    text = "---\ntitle: X\n---\n\nBody\n"
    out = _set_source_path_in_body(text, "raw/_archive/specs/x.md")
    assert "source_path: raw/_archive/specs/x.md" in out


def test_set_source_path_in_body_no_frontmatter_passthrough() -> None:
    from graph_wiki_core.commands.ingest import _set_source_path_in_body

    assert _set_source_path_in_body("no frontmatter", "raw/_archive/x.md") == "no frontmatter"
```

- [ ] **Step 2: Run the helper tests to verify they fail**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_commands_ingest.py -k set_source_path -v`
Expected: FAIL with `ImportError` / `AttributeError: ... _set_source_path_in_body`

- [ ] **Step 3: Implement the helper**

Add to `packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py`, immediately after `_set_source_type_in_body` (ends ~line 365):

```python
def _set_source_path_in_body(text: str, source_path: str) -> str:
    """Insert or replace the `source_path:` line in the YAML frontmatter of `text`.

    Placement: replaces an existing `source_path:` line in place (preserving its
    indent and position); when absent, inserts as the FIRST field of the
    frontmatter block. Idempotent. Operates on raw text (preserves comments and
    field order); returns text unchanged when no `---` block is present.
    """
    stripped = text.lstrip()
    if not stripped.startswith("---"):
        return text
    after_open = stripped[3:].lstrip("\n")
    close_idx = after_open.find("\n---")
    if close_idx == -1:
        return text
    leading_ws = text[: len(text) - len(stripped)]
    fm_block = after_open[:close_idx]
    body_and_close = after_open[close_idx:]

    new_lines: list[str] = []
    replaced = False
    for line in fm_block.splitlines():
        stripped_line = line.lstrip()
        if stripped_line.startswith("source_path:"):
            indent = line[: len(line) - len(stripped_line)]
            new_lines.append(f"{indent}source_path: {source_path}")
            replaced = True
            continue
        new_lines.append(line)
    if not replaced:
        new_lines.insert(0, f"source_path: {source_path}")
    new_fm = "\n".join(new_lines)
    return f"{leading_ws}---\n{new_fm}{body_and_close}"
```

- [ ] **Step 4: Run the helper tests to verify they pass**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_commands_ingest.py -k set_source_path -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Write the failing integration assertions**

Extend the existing archive test `test_run_ingest_source_archives_raw_source` (~line 2408) by appending, after the existing assertions:

```python
    # The PAGE frontmatter now records the archive location (2026-06-14).
    page = (ws / "wiki" / result.page_path).read_text(encoding="utf-8")
    assert "source_path: raw/_archive/specs/auth.md" in page
```

And add a dedicated test that the page is untouched when not archived. Place it after `test_run_ingest_source_leaves_sources_outside_raw_untouched` (~line 2452):

```python
@pytest.mark.asyncio
async def test_run_ingest_source_outside_raw_page_keeps_source_path(tmp_path, monkeypatch):
    from graph_wiki_core.commands import ingest as ingest_mod

    ws = _setup_archive_test_workspace(tmp_path, monkeypatch)
    src = ws / "notes.md"
    src.write_text("# Loose Note\n\nbody\n", encoding="utf-8")
    # LLM emits a page that already carries a source_path line.
    response = "---\ntarget_slug: loose-note\ntitle: Loose Note\nsource_path: notes.md\n---\n\nBody.\n"

    class _LLM:
        async def ainvoke(self, messages):
            class _R:
                content = response
                usage_metadata = None

            return _R()

    monkeypatch.setattr(ingest_mod, "make_llm", lambda role, model_override=None: _LLM())

    result = await ingest_mod.run_ingest_source(src, workspace_path=ws)
    assert result.archived_to is None
    page = (ws / "wiki" / result.page_path).read_text(encoding="utf-8")
    assert "source_path: notes.md" in page
    assert "_archive" not in page
```

Run: `uv run --package graph-wiki-core pytest tests/unit/test_commands_ingest.py -k "archives_raw_source or keeps_source_path" -v`
Expected: `test_run_ingest_source_archives_raw_source` FAILS on the new assertion (page has no `_archive` source_path yet); the keeps_source_path test PASSES (no rewrite path exercised).

- [ ] **Step 6: Wire the rewrite into `_run_common_tail`**

In `packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py`, in `_run_common_tail`, immediately after the archive block (the `if archive_unit is not None:` block ending ~line 1046) and BEFORE `detail = f"source: {source_path}"` (~line 1048), insert:

```python
    # Stamp the archive location into the page frontmatter so the source page
    # records where the source now lives (raw-source-archive 2026-06-14). Only on
    # a successful move — a no-op move (outside raw/) or a failed move leaves the
    # page's source_path as written.
    if archived_to:
        current_page = target_path.read_text(encoding="utf-8")
        stamped_page = _set_source_path_in_body(current_page, archived_to)
        if stamped_page != current_page:
            target_path.write_text(stamped_page, encoding="utf-8")
```

- [ ] **Step 7: Run the full ingest suite**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_commands_ingest.py -v`
Expected: PASS (all tests, including the updated archive test)

- [ ] **Step 8: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py packages/graph-wiki-core/tests/unit/test_commands_ingest.py
git commit -m "feat(graph-wiki-core): stamp archive location into source page source_path"
```

---

### Task 2: Lint check for stale `raw/` `source_path`

**Goal:** Flag any source page whose `source_path` is a workspace-relative `raw/...` path that no longer exists on disk.

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/lint.py` (`LintResult` field ~line 99; compute in `_mechanical_pass` before the return dict ~line 278; add to return dict ~line 284; wire into `run_lint`'s `LintResult(...)` ~line 540)
- Modify: `packages/graph-wiki-cli/src/graph_wiki_cli/wiki_cli/main.py` (report renderer ~line 139)
- Test: `packages/graph-wiki-core/tests/unit/test_commands_lint.py`

**Acceptance Criteria:**
- [ ] `LintResult` has a `source_path_drift: list[str]` field (defaults to empty list, serializes).
- [ ] `_mechanical_pass` returns `source_path_drift` listing source pages whose `raw/...` `source_path` does not exist under `wiki.parent`.
- [ ] A source page pointing at an existing `raw/_archive/...` path is NOT flagged; a repo-relative doc path is NOT flagged; an absolute path is NOT flagged; a page with no `source_path` is NOT flagged.
- [ ] The CLI report renders a `Source path drift` section.

**Verify:** `uv run --package graph-wiki-core pytest tests/unit/test_commands_lint.py -k source_path_drift -v` → PASS

**Steps:**

- [ ] **Step 1: Write the failing test**

Add to `packages/graph-wiki-core/tests/unit/test_commands_lint.py`:

```python
def test_mechanical_pass_flags_stale_raw_source_path(tmp_path: Path) -> None:
    from graph_wiki_core.commands.lint import _mechanical_pass

    ws = tmp_path
    wiki = ws / "wiki"
    (wiki / "sources").mkdir(parents=True)
    (wiki / "log.md").write_text("", encoding="utf-8")
    (ws / "raw" / "_archive" / "specs").mkdir(parents=True)
    (ws / "raw" / "_archive" / "specs" / "live.md").write_text("x", encoding="utf-8")

    def _page(slug: str, source_path: str) -> None:
        (wiki / "sources" / f"{slug}.md").write_text(
            f"---\ntitle: {slug}\ncategory: source\nsummary: s\nsource_path: {source_path}\n---\n\nbody\n",
            encoding="utf-8",
        )

    _page("stale", "raw/specs/gone.md")          # raw/ path, missing -> flagged
    _page("archived", "raw/_archive/specs/live.md")  # archived, exists -> not flagged
    _page("indoc", "docs/architecture.md")        # repo-relative doc -> not flagged

    mech = _mechanical_pass(wiki, stale_days=9999, log_gap_days=9999)
    assert mech["source_path_drift"] == ["sources/stale"]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_commands_lint.py -k stale_raw_source_path -v`
Expected: FAIL with `KeyError: 'source_path_drift'`

- [ ] **Step 3: Compute drift in `_mechanical_pass`**

In `packages/graph-wiki-core/src/graph_wiki_core/commands/lint.py`, just before the `return {` dict in `_mechanical_pass` (~line 278), add:

```python
    # source_path drift: a source page whose workspace-relative raw/ source_path
    # no longer exists on disk (the file was archived). Conservative — skips
    # absolute paths and repo-relative in-repo doc paths (raw-source-archive
    # 2026-06-14).
    workspace_root = wiki.parent
    source_path_drift = []
    for key, page in pages.items():
        if not key.startswith("sources/"):
            continue
        sp = page["fm"].get("source_path")
        if not isinstance(sp, str) or not sp or sp.startswith("/") or not sp.startswith("raw/"):
            continue
        if not (workspace_root / sp).exists():
            source_path_drift.append(key)
    source_path_drift.sort()
```

Then add to the returned dict (after `"missing_frontmatter": sorted(missing_fm),` ~line 283):

```python
        "source_path_drift": source_path_drift,
```

- [ ] **Step 4: Add the `LintResult` field**

In `packages/graph-wiki-core/src/graph_wiki_core/commands/lint.py`, in the `LintResult` dataclass, after `missing_frontmatter` (~line 95):

```python
    source_path_drift: list[str] = field(default_factory=list)
```

- [ ] **Step 5: Wire it into `run_lint`**

In the `return LintResult(` block in `run_lint` (~line 540), after `missing_frontmatter=mech["missing_frontmatter"],`:

```python
        source_path_drift=mech["source_path_drift"],
```

- [ ] **Step 6: Run the lint test to verify it passes**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_commands_lint.py -k stale_raw_source_path -v`
Expected: PASS

- [ ] **Step 7: Render it in the CLI report**

In `packages/graph-wiki-cli/src/graph_wiki_cli/wiki_cli/main.py`, after `_section("Missing frontmatter", result.missing_frontmatter)` (~line 139), add:

```python
        _section("Source path drift", result.source_path_drift)
```

- [ ] **Step 8: Run both affected suites**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_commands_lint.py -v && uv run --package graph-wiki-cli pytest -m "not integration" -k "lint or wiki_cli" -v`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/lint.py packages/graph-wiki-core/tests/unit/test_commands_lint.py packages/graph-wiki-cli/src/graph_wiki_cli/wiki_cli/main.py
git commit -m "feat(graph-wiki-core): lint check for stale raw/ source_path pointers"
```

---

### Task 3: Update CC plugin ingest instructions + template comment

**Goal:** Make the plugin agent record the post-archive `source_path`, and update the template/reference comments accordingly. Docs/template only — no Python.

**Files:**
- Modify: `plugins/graph-wiki/agents/ingestor.md` (step 4 ~line 130; step 12 ~line 181)
- Modify: `plugins/graph-wiki/skills/graph-wiki/references/ingest-workflow.md` (step 4 ~line 66; step 12 ~line 118)
- Modify: `plugins/graph-wiki/commands/ingest.md` (archive step ~line 104)
- Modify: `packages/wiki-io/src/wiki_io/assets/page-templates/source.md` (`source_path:` comment ~line 5)
- Modify: `plugins/graph-wiki/skills/graph-wiki/references/page-formats.md` (`source_path:` example ~line 283)

**Acceptance Criteria:**
- [ ] `ingestor.md` step 4 instructs that for a `raw/` source, `source_path` records the post-archive path `raw/_archive/<rel-path>` (because step 12 moves it there); in-repo docs keep their repo-relative path.
- [ ] `ingest-workflow.md` step 4 carries the same instruction.
- [ ] Step 12 in both files cross-references that the page `source_path` must match the archive destination.
- [ ] The template `source.md` `source_path:` comment notes `raw/_archive/<...>` for archived clips.
- [ ] No source-text instruction tells the agent to archive a non-raw source or to rewrite an in-repo doc path.

**Verify:** `git diff --stat plugins/ packages/wiki-io/src/wiki_io/assets/page-templates/source.md` shows the 5 files changed; manual read confirms the wording. (Docs-only — no automated test.)

**Steps:**

- [ ] **Step 1: Update `ingestor.md` step 4**

In `plugins/graph-wiki/agents/ingestor.md`, replace the step-4 frontmatter sentence (~line 130):

Old:
```
`<workspace>/wiki/sources/<YYYY-MM>-<slug>.md`. Use the source template. Required frontmatter: `title`, `category: source`, `summary`, `source_path`, `source_type`, `ingested`, `updated`.
```

New:
```
`<workspace>/wiki/sources/<YYYY-MM>-<slug>.md`. Use the source template. Required frontmatter: `title`, `category: source`, `summary`, `source_path`, `source_type`, `ingested`, `updated`. For a source under `raw/`, `source_path` records the **post-archive** location `raw/_archive/<rel-path>` (step 12 moves the file there). For in-repo docs and loose files, `source_path` is the path where the file stays (repo-relative for in-repo docs).
```

- [ ] **Step 2: Update `ingestor.md` step 12**

In `plugins/graph-wiki/agents/ingestor.md`, after the `mv` code block (~line 186), add a bullet to the existing list:

```
- The source page's `source_path` frontmatter (step 4) must equal this archive destination (`raw/_archive/<rel-path>`), so a reader can find the original.
```

- [ ] **Step 3: Update `ingest-workflow.md` step 4**

In `plugins/graph-wiki/skills/graph-wiki/references/ingest-workflow.md`, after the step-4 frontmatter sentence (~line 66), append:

```
For a source under `raw/`, set `source_path` to the post-archive location `raw/_archive/<rel-path>` (step 12 moves the file there). In-repo docs keep their repo-relative `source_path`.
```

- [ ] **Step 4: Update `ingest-workflow.md` step 12**

In `plugins/graph-wiki/skills/graph-wiki/references/ingest-workflow.md`, at the end of the step-12 paragraph (~line 118), append:

```
The source page's `source_path` (step 4) must match this destination.
```

- [ ] **Step 5: Update `commands/ingest.md`**

In `plugins/graph-wiki/commands/ingest.md`, in the archive step (~line 104), append to the sentence:

```
 — and the source page's `source_path` frontmatter records that archive destination.
```

- [ ] **Step 6: Update the template comment**

In `packages/wiki-io/src/wiki_io/assets/page-templates/source.md`, change the `source_path:` line comment (~line 5):

Old:
```
source_path: raw/<path-to-source>           # raw/<...> for ingested clips, or a repo-relative path for in-repo docs (e.g. docs/architecture.md)
```

New:
```
source_path: raw/_archive/<path-to-source>  # raw/_archive/<...> for archived clips (where the ingested source now lives), or a repo-relative path for in-repo docs (e.g. docs/architecture.md)
```

- [ ] **Step 7: Update `page-formats.md` example**

In `plugins/graph-wiki/skills/graph-wiki/references/page-formats.md`, change the source template example (~line 283):

Old:
```
source_path: raw/specs/auth-migration.md
```

New:
```
source_path: raw/_archive/specs/auth-migration.md
```

- [ ] **Step 8: Verify and commit**

Run: `git diff --stat plugins/ packages/wiki-io/src/wiki_io/assets/page-templates/source.md`
Expected: 5 files changed.

```bash
git add plugins/graph-wiki/agents/ingestor.md plugins/graph-wiki/skills/graph-wiki/references/ingest-workflow.md plugins/graph-wiki/commands/ingest.md plugins/graph-wiki/skills/graph-wiki/references/page-formats.md packages/wiki-io/src/wiki_io/assets/page-templates/source.md
git commit -m "docs(graph-wiki): record post-archive source_path in plugin ingest instructions"
```

---

## Notes for the executor

- Run tests scoped per-package (`uv run --package <pkg> pytest ...`), never from the workspace root (guarded `norecursedirs`).
- `IngestResult.source_path` is intentionally left as the original input path — only the on-disk **page frontmatter** is rewritten. Do not change the existing `assert result.source_path == str(src)` in `test_run_ingest_source_archives_raw_source`.
- Tasks are independent (no shared state) and may be done in any order. Task 1 and Task 3 both make the two surfaces consistent; Task 2 is the safety net that surfaces any page (existing or future) that drifts.
- No migration code (repo policy: no migrations before v2.0).
