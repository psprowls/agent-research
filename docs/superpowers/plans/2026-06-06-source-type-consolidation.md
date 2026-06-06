# Source-type Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Collapse the two overlapping Source-page classification fields (`source_kind`, `source_type`) into a single `source_type`, make the Bedrock core path actually *write* it to frontmatter, and fix the raw-folder detection wiring so `raw/<type>/` sources resolve authoritatively.

**Architecture:** One closed enum (`spec · article · pr · ticket · transcript · example · doc · note`) shared from `wiki_io.ingest_source` as `SOURCE_TYPE_ENUM` / `RAW_FOLDER_TYPES`. Determination order: a `raw/<type>/` folder is authoritative (LLM ignored); otherwise the ingestor LLM may override the path-guess (`doc` for in-repo, `note` for loose) with a more specific enum value; an empty/out-of-enum value keeps the path-guess. Both delivery surfaces (Bedrock core + Claude plugin) describe the same model.

**Tech Stack:** Python 3.11, `uv` workspace, pytest (per-package), syrupy snapshots, LangChain-AWS (Bedrock Converse).

---

## Background: the wiring bug this plan also fixes

`guess_source_type(rel_to_workspace, rel_to_repo)` returns `spec`/`article`/… only when its **first argument** contains the `raw/<type>/` path segments. Today both call sites compute that argument as `source_path.relative_to(wiki)` where `wiki = <workspace>/wiki`. But `raw/` is a **sibling** of `wiki/` (both under `<workspace>/`), so `relative_to(wiki)` raises for every real raw source → the arg is `None` → the `raw/<type>/` branch never fires. Empirically: a `raw/specs/auth.md` resolves to `note` (production, repo separate) or `doc` (when repo == workspace), never `spec`.

The user confirmed: **files are ingested from the workspace root**, so the guess must be computed relative to `<workspace>/` (where `raw/` lives). This plan feeds `guess_source_type` a workspace-relative path at both call sites. The `in_repo_doc` flag in `build_ingest_brief` keeps its existing `relative_to(wiki)`-based computation (surgical — do not change drift behavior).

## File structure

**Production code (6 files):**
- `packages/wiki-io/src/wiki_io/ingest_source.py` — add `SOURCE_TYPE_ENUM` + `RAW_FOLDER_TYPES`; rename `guess_source_type`'s first param `rel_to_wiki` → `rel_to_workspace` + fix docstring; feed `build_ingest_brief`'s guess a workspace-relative path.
- `packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py` — import the two constants; rewrite the source-type determination in `run_ingest_source`; rename `_set_source_kind_in_body` → `_set_source_type_in_body`; `_synthesize_frontmatter_block` writes `source_type`; rename `IngestResult.source_kind` → `source_type`; reword `build_ingest_source_prompt` human message.
- `packages/graph-wiki-core/src/graph_wiki_core/prompts/ingestor.py` — reword `_SOURCE_LANDING`.
- `packages/graph-wiki-core/src/graph_wiki_core/prompts/_fragments/frontmatter_rules.py` — reword the `source_kind` bullet.
- `packages/graph-wiki-cli/src/graph_wiki_cli/wiki_cli/main.py` — CLI echo rename.
- `packages/graph-wiki-mcp/src/graph_wiki_mcp/server.py` — MCP response-model rename.

**Plugin docs (4 files, doc-only):**
- `plugins/graph-wiki/agents/ingestor.md`
- `plugins/graph-wiki/skills/graph-wiki/references/wiki-schema.md`
- `plugins/graph-wiki/skills/graph-wiki/references/page-formats.md`
- `plugins/graph-wiki/skills/graph-wiki/references/ingest-workflow.md`

**Tests:** `test_ingest_source.py`, `test_ingest_source_prep.py` (wiki-io); `test_commands_ingest.py`, `test_suggest_pages.py`, snapshot `.ambr` (core); `test_wiki_cli.py` (cli); `test_mcp_new_tools.py` (mcp).

> **Conventions reminder:** This repo has **no migrations until v2.0** — do not write migration code. `ruff format` is NOT enforced and the src tree is format-dirty; **do not run `ruff format`** to "fix" your diff — match the surrounding multi-line style by hand. `wiki-io` modules put the docstring above `from __future__`.

---

## Task 1: Shared source-type constants (wiki-io)

**Files:**
- Modify: `packages/wiki-io/src/wiki_io/ingest_source.py`
- Test: `packages/wiki-io/tests/test_ingest_source.py`

- [ ] **Step 1: Write the failing test**

Add to `packages/wiki-io/tests/test_ingest_source.py`, immediately after the `test_constants_present` function (around line 232):

```python
# ---------------------------------------------------------------------------
# Source-type enum constants (source-type-consolidation design 2026-06-05)
# ---------------------------------------------------------------------------


def test_source_type_enum_contents() -> None:
    from wiki_io.ingest_source import SOURCE_TYPE_ENUM

    assert set(SOURCE_TYPE_ENUM) == {
        "spec",
        "article",
        "pr",
        "ticket",
        "transcript",
        "example",
        "doc",
        "note",
    }
    # No legacy/removed values.
    assert "unknown" not in SOURCE_TYPE_ENUM
    assert "rfc" not in SOURCE_TYPE_ENUM


def test_raw_folder_types_is_authoritative_subset() -> None:
    from wiki_io.ingest_source import RAW_FOLDER_TYPES, SOURCE_TYPE_ENUM

    assert set(RAW_FOLDER_TYPES) == {
        "spec",
        "article",
        "pr",
        "ticket",
        "transcript",
        "example",
    }
    # The raw-folder subset never includes the path-default catch-alls.
    assert set(RAW_FOLDER_TYPES) <= set(SOURCE_TYPE_ENUM)
    assert "doc" not in RAW_FOLDER_TYPES
    assert "note" not in RAW_FOLDER_TYPES
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --package wiki-io pytest tests/test_ingest_source.py::test_source_type_enum_contents tests/test_ingest_source.py::test_raw_folder_types_is_authoritative_subset -v`
Expected: FAIL with `ImportError: cannot import name 'SOURCE_TYPE_ENUM'`.

- [ ] **Step 3: Add the constants + fix the `guess_source_type` param name/docstring**

In `packages/wiki-io/src/wiki_io/ingest_source.py`, insert the constants immediately **above** `def guess_source_type` (currently line 134):

```python
# Source-type model (source-type-consolidation design 2026-06-05). One closed
# enum on every Source page; `note` is the catch-all (no `unknown`, no `rfc`).
SOURCE_TYPE_ENUM = frozenset(
    {"spec", "article", "pr", "ticket", "transcript", "example", "doc", "note"}
)
# The subset a `raw/<type>/` folder produces authoritatively. The LLM cannot
# override these — see run_ingest_source / build_ingest_brief.
RAW_FOLDER_TYPES = frozenset({"spec", "article", "pr", "ticket", "transcript", "example"})
```

Then replace the `guess_source_type` signature + docstring (lines 134–140) — rename the first parameter and correct the docstring to say *workspace*-relative:

```python
def guess_source_type(rel_to_workspace: Path | None, rel_to_repo: Path | None) -> str:
    """Guess source_type from where the file lives.

    `rel_to_workspace` is the source path relative to the WORKSPACE root (e.g.
    `raw/specs/x.md`) when the source lives under `<workspace>/raw/`. `raw/` is a
    sibling of `wiki/`, so this must be measured from the workspace root, NOT the
    wiki dir. `rel_to_repo` is the repo-relative path for an in-repo doc. Either
    may be None.
    """
    if rel_to_workspace is not None:
        parts = rel_to_workspace.parts
```

(Leave the `if "specs" in parts:` … body and the `rel_to_repo`/`note` tail unchanged.)

Finally update the module-docstring Exports block (around lines 9–20): change the `guess_source_type` line and add the constants. Replace:

```
    guess_source_type(rel_to_wiki, rel_to_repo) -> str
```

with:

```
    guess_source_type(rel_to_workspace, rel_to_repo) -> str
    SOURCE_TYPE_ENUM, RAW_FOLDER_TYPES   (closed source_type enum + raw-folder subset)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --package wiki-io pytest tests/test_ingest_source.py -v`
Expected: PASS — the two new tests plus all existing `guess_source_type`/`extract`/`slugify` tests (the isolated guess tests call positionally, so the param rename is transparent).

- [ ] **Step 5: Commit**

```bash
git add packages/wiki-io/src/wiki_io/ingest_source.py packages/wiki-io/tests/test_ingest_source.py
git commit -m "feat(wiki-io): add SOURCE_TYPE_ENUM/RAW_FOLDER_TYPES; clarify guess_source_type param"
```

---

## Task 2: Workspace-relative raw detection in `build_ingest_brief` (wiki-io)

This fixes the plugin-brief surface so `raw/<type>/` sources resolve to their folder type. `in_repo_doc` keeps its existing wiki-relative computation (do not change drift behavior).

**Files:**
- Modify: `packages/wiki-io/src/wiki_io/ingest_source.py:248-287` (`build_ingest_brief`)
- Test: `packages/wiki-io/tests/test_ingest_source_prep.py`

- [ ] **Step 1: Write the failing test**

Add to `packages/wiki-io/tests/test_ingest_source_prep.py`, after `test_build_ingest_brief_emits_brief_without_bedrock` (the new test mirrors that one's `_seed_db` + monkeypatch setup):

```python
def test_build_ingest_brief_raw_folder_is_authoritative(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A source under <workspace>/raw/specs/ resolves to source_type 'spec'
    (raw/ is a sibling of wiki/, so the guess is measured from the workspace
    root, not the wiki dir)."""
    monkeypatch.setitem(sys.modules, "model_adapter", None)
    monkeypatch.setitem(sys.modules, "subagent_runtime", None)

    import wiki_io.ingest_source as prep

    importlib.reload(prep)

    workspace = tmp_path
    wiki = workspace / "wiki"
    wiki.mkdir()
    repo = workspace / "repo"  # repo is a SEPARATE dir (production layout)
    repo.mkdir()
    src = workspace / "raw" / "specs" / "auth.md"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("# Auth Spec\n\nBody text.", encoding="utf-8")

    brief = prep.build_ingest_brief(
        source_path=src,
        wiki=wiki,
        repo=repo,
        workspace_root=workspace,
    )

    assert brief["source_type"] == "spec"
    # raw-staged sources are not in-repo docs.
    assert brief["in_repo_doc"] is False
```

> Note: this test relies on the existing module-level imports `sys`, `importlib`, `pytest`, `Path` and the `_seed_db` helper already present in `test_ingest_source_prep.py`. (It does not call `_seed_db` because no entity match is asserted; `entity_match` degrades gracefully when the graph DB is absent.)

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --package wiki-io pytest tests/test_ingest_source_prep.py::test_build_ingest_brief_raw_folder_is_authoritative -v`
Expected: FAIL — `assert 'note' == 'spec'` (the current wiki-relative computation yields `note` because `raw/specs/auth.md` is under neither `wiki/` nor the separate `repo/`).

- [ ] **Step 3: Compute a workspace-relative path for the guess**

In `build_ingest_brief` (lines 254–264), add a third relative-path computation and feed it to the guess. Replace:

```python
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
```

with:

```python
    rel_to_wiki = None
    rel_to_repo = None
    rel_to_workspace = None
    try:
        rel_to_wiki = source_path.relative_to(wiki)
    except ValueError:
        pass
    try:
        rel_to_repo = source_path.relative_to(repo)
    except ValueError:
        pass
    try:
        rel_to_workspace = source_path.relative_to(workspace_root)
    except ValueError:
        pass
    # raw/<type>/ folders are authoritative; guess from the WORKSPACE-relative
    # path because raw/ is a sibling of wiki/ (not under it). `in_repo_doc`
    # keeps its wiki-relative semantics below — drift behavior is unchanged.
    source_type = guess_source_type(rel_to_workspace, rel_to_repo)
```

Leave the `in_repo_doc = rel_to_repo is not None and rel_to_wiki is None` line (line 273) exactly as-is.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --package wiki-io pytest tests/test_ingest_source_prep.py -v`
Expected: PASS — the new raw test plus `test_build_ingest_brief_emits_brief_without_bedrock` (its `source_type == "doc"` still holds: the code file has no `raw/<type>/` segment, falls to the `rel_to_repo` branch).

- [ ] **Step 5: Commit**

```bash
git add packages/wiki-io/src/wiki_io/ingest_source.py packages/wiki-io/tests/test_ingest_source_prep.py
git commit -m "fix(wiki-io): resolve raw/<type>/ source_type from workspace root in build_ingest_brief"
```

---

## Task 3: Source-type determination + field/helper rename (core)

This is the largest task: it introduces the new behavior tests, implements the determination logic, removes `source_kind`, and repairs the pre-existing tests broken by the rename. Work the steps in order — the suite is red between Step 4 and Step 9.

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py`
- Test: `packages/graph-wiki-core/tests/unit/test_commands_ingest.py`
- Test (fixture touch-up): `packages/graph-wiki-core/tests/unit/test_suggest_pages.py`

### Part A — new behavior tests (TDD)

- [ ] **Step 1: Write the three new determination tests**

Add to `packages/graph-wiki-core/tests/unit/test_commands_ingest.py`, after `test_run_ingest_source_no_frontmatter_synthesizes_unknown` (around line 1167). These use the existing module-level `pytest`, `AsyncMock`, `MagicMock`, `patch`, `Path` imports and the `_build_workspace_with_repo` / `_seed_graph_db_for_ingest_tests` helpers defined earlier in the file.

```python
# ---------------------------------------------------------------------------
# Source-type determination (source-type-consolidation design 2026-06-05)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_ingest_source_raw_folder_type_is_authoritative(tmp_path: Path) -> None:
    """A source under raw/specs/ is stamped source_type: spec; a contrary LLM
    value is ignored (raw/<type>/ folders are authoritative)."""
    from graph_wiki_core.commands.ingest import run_ingest_source

    workspace, wiki, repo = _build_workspace_with_repo(tmp_path)
    source_file = workspace / "raw" / "specs" / "auth.md"
    source_file.parent.mkdir(parents=True)
    source_file.write_text("# Auth Spec\n\nBody.", encoding="utf-8")
    _seed_graph_db_for_ingest_tests(workspace, packages=[])

    # The LLM tries to call it an article — must be ignored.
    fake_llm_response = "---\nsource_type: article\ntarget_slug: auth\ntitle: Auth\nsummary: x\n---\nBody."

    with (
        patch("graph_wiki_core.commands.ingest.resolve_wiki_and_repo", return_value=(wiki, repo)),
        patch("graph_wiki_core.commands.ingest.make_llm") as mock_make_llm,
        patch("graph_wiki_core.commands.ingest.update_index"),
        patch("graph_wiki_core.commands.ingest.append_log"),
    ):
        fake_llm = MagicMock()
        fake_llm.ainvoke = AsyncMock(return_value=MagicMock(content=fake_llm_response))
        mock_make_llm.return_value = fake_llm
        result = await run_ingest_source(source_file, workspace)

    written = (wiki / "sources" / "auth.md").read_text(encoding="utf-8")
    assert "source_type: spec" in written
    assert "source_type: article" not in written
    assert result.source_type == "spec"


@pytest.mark.asyncio
async def test_run_ingest_source_llm_overrides_non_raw_type(tmp_path: Path) -> None:
    """For an in-repo doc (path-guess 'doc'), the LLM may override the type with
    a more specific enum value."""
    from graph_wiki_core.commands.ingest import run_ingest_source

    workspace, wiki, repo = _build_workspace_with_repo(tmp_path)
    source_file = workspace / "notes.md"  # in-repo, NOT under raw/
    source_file.write_text("# Notes\n\nA meeting transcript.", encoding="utf-8")
    _seed_graph_db_for_ingest_tests(workspace, packages=[])

    fake_llm_response = "---\nsource_type: transcript\ntarget_slug: notes\ntitle: Notes\nsummary: x\n---\nBody."

    with (
        patch("graph_wiki_core.commands.ingest.resolve_wiki_and_repo", return_value=(wiki, repo)),
        patch("graph_wiki_core.commands.ingest.make_llm") as mock_make_llm,
        patch("graph_wiki_core.commands.ingest.update_index"),
        patch("graph_wiki_core.commands.ingest.append_log"),
    ):
        fake_llm = MagicMock()
        fake_llm.ainvoke = AsyncMock(return_value=MagicMock(content=fake_llm_response))
        mock_make_llm.return_value = fake_llm
        result = await run_ingest_source(source_file, workspace)

    written = (wiki / "sources" / "notes.md").read_text(encoding="utf-8")
    assert "source_type: transcript" in written
    assert result.source_type == "transcript"


@pytest.mark.asyncio
async def test_run_ingest_source_falls_back_to_path_guess_on_bad_llm_type(tmp_path: Path) -> None:
    """An out-of-enum or absent LLM source_type falls back to the path-guess:
    'doc' for an in-repo file, 'note' for a loose file under neither workspace
    nor repo."""
    from graph_wiki_core.commands.ingest import run_ingest_source

    workspace, wiki, repo = _build_workspace_with_repo(tmp_path)
    _seed_graph_db_for_ingest_tests(workspace, packages=[])

    # (a) in-repo file, LLM returns out-of-enum garbage -> doc
    in_repo = workspace / "doc.md"
    in_repo.write_text("# Doc\n\nBody.", encoding="utf-8")
    resp_garbage = "---\nsource_type: nonsense\ntarget_slug: doc\ntitle: Doc\nsummary: x\n---\nBody."
    with (
        patch("graph_wiki_core.commands.ingest.resolve_wiki_and_repo", return_value=(wiki, repo)),
        patch("graph_wiki_core.commands.ingest.make_llm") as mock_make_llm,
        patch("graph_wiki_core.commands.ingest.update_index"),
        patch("graph_wiki_core.commands.ingest.append_log"),
    ):
        fake_llm = MagicMock()
        fake_llm.ainvoke = AsyncMock(return_value=MagicMock(content=resp_garbage))
        mock_make_llm.return_value = fake_llm
        result_doc = await run_ingest_source(in_repo, workspace)
    assert result_doc.source_type == "doc"
    assert "source_type: doc" in (wiki / "sources" / "doc.md").read_text(encoding="utf-8")

    # (b) loose file outside workspace+repo, LLM omits source_type -> note
    loose = tmp_path / "outside" / "loose.md"
    loose.parent.mkdir(parents=True)
    loose.write_text("# Loose\n\nBody.", encoding="utf-8")
    resp_empty = "---\ntarget_slug: loose\ntitle: Loose\nsummary: x\n---\nBody."
    with (
        patch("graph_wiki_core.commands.ingest.resolve_wiki_and_repo", return_value=(wiki, repo)),
        patch("graph_wiki_core.commands.ingest.make_llm") as mock_make_llm,
        patch("graph_wiki_core.commands.ingest.update_index"),
        patch("graph_wiki_core.commands.ingest.append_log"),
    ):
        fake_llm = MagicMock()
        fake_llm.ainvoke = AsyncMock(return_value=MagicMock(content=resp_empty))
        mock_make_llm.return_value = fake_llm
        result_note = await run_ingest_source(loose, workspace)
    assert result_note.source_type == "note"
    assert "source_type: note" in (wiki / "sources" / "loose.md").read_text(encoding="utf-8")
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_commands_ingest.py -k "raw_folder_type_is_authoritative or llm_overrides_non_raw_type or falls_back_to_path_guess" -v`
Expected: FAIL — `AttributeError: 'IngestResult' object has no attribute 'source_type'` (and the path-guess still mis-resolves until Step 3).

### Part B — implementation

- [ ] **Step 3: Import the constants**

In `packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py`, replace the import on line 43:

```python
from wiki_io.ingest_source import PREVIEW_CHARS, extract, guess_source_type, slugify
```

with:

```python
from wiki_io.ingest_source import (
    PREVIEW_CHARS,
    RAW_FOLDER_TYPES,
    SOURCE_TYPE_ENUM,
    extract,
    guess_source_type,
    slugify,
)
```

- [ ] **Step 4: Compute the path-guess from the workspace-relative path**

In `run_ingest_source`, replace the Step 3 block (lines 627–638):

```python
        # Step 3: guess source type
        rel_to_wiki: Path | None = None
        rel_to_repo: Path | None = None
        try:
            rel_to_wiki = source_path.relative_to(wiki)
        except ValueError:
            pass
        try:
            rel_to_repo = source_path.relative_to(repo)
        except ValueError:
            pass
        source_type = guess_source_type(rel_to_wiki, rel_to_repo)
```

with:

```python
        # Step 3: path-guess the source_type. raw/<type>/ folders are
        # authoritative, so guess from the WORKSPACE-relative path (raw/ is a
        # sibling of wiki/, not under it). In-repo docs fall to `doc`; loose
        # files to `note` (source-type-consolidation design 2026-06-05).
        rel_to_workspace: Path | None = None
        rel_to_repo: Path | None = None
        try:
            rel_to_workspace = source_path.relative_to(workspace_root)
        except ValueError:
            pass
        try:
            rel_to_repo = source_path.relative_to(repo)
        except ValueError:
            pass
        path_guess = guess_source_type(rel_to_workspace, rel_to_repo)
```

- [ ] **Step 5: Pass the path-guess as the prompt hint**

In `run_ingest_source`, line 666, replace:

```python
        prompt = build_ingest_source_prompt(text, source_path, source_type, vault_structure)
```

with:

```python
        prompt = build_ingest_source_prompt(text, source_path, path_guess, vault_structure)
```

- [ ] **Step 6: Resolve the final `source_type` after the LLM call**

In `run_ingest_source` (Step 6 region, lines 707–713), replace:

```python
        # Step 6: parse response to get source_kind and target_slug.
        # M3 Part A: classification is DECOUPLED from routing. Every ingested
        # doc becomes a Source page; `source_kind` is descriptive only and
        # defaults to "unknown" on a parse miss (empty fm).
        fm, _body = _parse_ingestor_response(llm_output)
        frontmatter_parsed = bool(fm)  # False ⟺ parse miss (spec §3.5)
        source_kind = str(fm.get("source_kind", "")).strip().lower() or "unknown"
```

with:

```python
        # Step 6: parse response to get source_type and target_slug.
        # M3 Part A: classification is DECOUPLED from routing — every ingested
        # doc becomes a Source page regardless of source_type.
        fm, _body = _parse_ingestor_response(llm_output)
        frontmatter_parsed = bool(fm)  # False ⟺ parse miss (spec §3.5)
        # Source-type determination (source-type-consolidation design 2026-06-05):
        # a raw/<type>/ folder is authoritative (LLM ignored); otherwise the LLM
        # may override the path-guess (doc/note) with a more specific enum value,
        # and an empty/out-of-enum value keeps the path-guess.
        if path_guess in RAW_FOLDER_TYPES:
            source_type = path_guess
        else:
            llm_value = str(fm.get("source_type", "")).strip().lower()
            source_type = llm_value if llm_value in SOURCE_TYPE_ENUM else path_guess
```

- [ ] **Step 7: Stamp `source_type` (rename the body helper + synthesize)**

In `run_ingest_source` (lines 728–736), replace:

```python
        if not frontmatter_parsed and not llm_output.lstrip().startswith("---"):
            llm_output = _synthesize_frontmatter_block(llm_output, source_kind, canonical_slug, canonical_uri)

        # Reconcile target_slug in the body with the on-disk filename slug, write
        # entity_uri (null when no graph match), and stamp source_kind. All three
        # helpers are idempotent and preserve comments/order.
        llm_output = _rewrite_target_slug_in_body(llm_output, canonical_slug)
        llm_output = _set_entity_uri_in_body(llm_output, canonical_uri)
        llm_output = _set_source_kind_in_body(llm_output, source_kind)
```

with:

```python
        if not frontmatter_parsed and not llm_output.lstrip().startswith("---"):
            llm_output = _synthesize_frontmatter_block(llm_output, source_type, canonical_slug, canonical_uri)

        # Reconcile target_slug in the body with the on-disk filename slug, write
        # entity_uri (null when no graph match), and stamp source_type. All three
        # helpers are idempotent and preserve comments/order.
        llm_output = _rewrite_target_slug_in_body(llm_output, canonical_slug)
        llm_output = _set_entity_uri_in_body(llm_output, canonical_uri)
        llm_output = _set_source_type_in_body(llm_output, source_type)
```

- [ ] **Step 8: Rename the helper, synthesize block, IngestResult field, prompt, and docstrings**

(a) Rename `_set_source_kind_in_body` → `_set_source_type_in_body`. Replace the section header comment (line 274) and the whole function (lines 278–304):

```python
# ---------------------------------------------------------------------------
# Source-type frontmatter + synthesize-frontmatter rule
# ---------------------------------------------------------------------------


def _set_source_type_in_body(text: str, source_type: str) -> str:
    """Insert or replace the `source_type:` line in the YAML frontmatter of `text`.

    Placement: inserted as the FIRST field of the frontmatter block. Idempotent
    — any existing `source_type:` line is dropped first, so only one ever
    appears. Operates on raw text (preserves comments/order); returns text
    unchanged when no `---` block is present.
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
    for line in fm_block.splitlines():
        if line.lstrip().startswith("source_type:"):
            continue  # drop existing line (idempotence)
        new_lines.append(line)
    new_lines.insert(0, f"source_type: {source_type}")
    new_fm = "\n".join(new_lines)
    return f"{leading_ws}---\n{new_fm}{body_and_close}"
```

(b) Rewrite `_synthesize_frontmatter_block` (lines 307–320) to take/write `source_type`:

```python
def _synthesize_frontmatter_block(body: str, source_type: str, target_slug: str, entity_uri: str | None) -> str:
    """Prepend a minimal YAML frontmatter block to a body that has none.

    The body-mutation helpers (_rewrite_target_slug_in_body /
    _set_entity_uri_in_body / _set_source_type_in_body) no-op when there is no
    `---` block. When the ingestor LLM emits a body with no frontmatter at all,
    this guarantees the Source page still lands with its metadata. The block
    carries all three fields so the downstream setters become idempotent no-ops.
    `entity_uri=None` is written as the literal `null` (mirrors
    _set_entity_uri_in_body).
    """
    uri_val = "null" if entity_uri is None else entity_uri
    return f"---\nsource_type: {source_type}\ntarget_slug: {target_slug}\nentity_uri: {uri_val}\n---\n\n{body}"
```

(c) Rename the `IngestResult` field. Replace line 137:

```python
    source_kind: str | None = None  # descriptive kind on Source pages; "unknown" on parse miss; None for work items
```

with:

```python
    source_type: str | None = None  # closed-enum classification on Source pages; None for work items
```

and the `frontmatter_parsed` comment on line 139:

```python
    frontmatter_parsed: bool = True  # False when we fell through to source_kind: unknown via a parse miss
```

with:

```python
    frontmatter_parsed: bool = True  # False when the ingestor frontmatter failed to parse (parse miss)
```

(d) Fix the `IngestResult` docstring. Replace the `page_type` clause (lines 102–104) phrase `see source_kind for the descriptive kind` with `see source_type for the closed-enum classification`, and replace the `source_kind:` docstring entry (lines 112–113):

```python
        source_kind:        Living Wiki M3: descriptive kind on Source pages
                            (run_ingest_source). "unknown" on a parse miss; None
                            for work items.
```

with:

```python
        source_type:        Closed-enum classification on Source pages
                            (run_ingest_source). raw/<type>/ folders are
                            authoritative; otherwise LLM-classified from content,
                            defaulting to the path-guess. None for work items.
```

and update line 119 `source_kind: unknown.` → `source_type via the path-guess fallback.`

(e) Return the field. In the `run_ingest_source` return (line 785), replace:

```python
            source_kind=source_kind,
```

with:

```python
            source_type=source_type,
```

(f) Reword the `build_ingest_source_prompt` human message. Replace the `return (...)` block (lines 558–568):

```python
    return (
        f"Source file: {source_path}\n"
        f"Source type: {source_type}\n"
        f"\nVault top-level categories:\n{vault_summary}\n"
        f"\n--- Source content ---\n{preview}\n--- End source ---\n"
        f"\nWrite a Source page for this document. It will be filed under "
        f"sources/. Provide a target_slug based on the content, and optionally a "
        f"descriptive source_kind. To associate this source with a code entity, "
        f"reference it with a [[entities/...]] wikilink in the body — do not "
        f"create a package page."
    )
```

with:

```python
    return (
        f"Source file: {source_path}\n"
        f"Source type (path-guess hint): {source_type}\n"
        f"\nVault top-level categories:\n{vault_summary}\n"
        f"\n--- Source content ---\n{preview}\n--- End source ---\n"
        f"\nWrite a Source page for this document. It will be filed under "
        f"sources/. Provide a target_slug based on the content, and a "
        f"source_type from the closed enum (spec, article, pr, ticket, "
        f"transcript, example, doc, note) — classify it from the content and "
        f"default to note when unsure. To associate this source with a code "
        f"entity, reference it with a [[entities/...]] wikilink in the body — do "
        f"not create a package page."
    )
```

(g) Update the prose docstring step in `run_ingest_source` (line 589): replace `read source_kind + target_slug` with `read source_type + target_slug`.

- [ ] **Step 9: Repair the pre-existing tests broken by the rename**

In `packages/graph-wiki-core/tests/unit/test_commands_ingest.py`, apply each edit below. (All sources placed at the workspace root or `tmp_path` root resolve to `doc`; the canonical test uses `mock_resolve.return_value = (wiki, tmp_path)`.)

1. **`test_run_ingest_source_extracts_and_routes`** (lines ~109–162): the source is `tmp_path/my-source.md` with repo `tmp_path` → `doc`.
   - Line 122 fixture — drop the `source_kind` line:
     ```python
     fake_llm_response = (
         "---\ntarget_slug: foo\ntitle: My Source\nsummary: A test concept\n---\n\nBody text here."
     )
     ```
   - Line 146: `assert "source_kind: source" in written_body` → `assert "source_type: doc" in written_body`
   - Line 160: `assert result.source_kind == "source"` → `assert result.source_type == "doc"`
   - Line 109 docstring: change `Fake ingestor returns source_kind=source;` → `Fake ingestor omits source_type so it falls to the doc path-guess;`

2. **Work-item test** (the test whose assertions are at lines 351 & 363):
   - `assert result.source_kind is None` → `assert result.source_type is None`
   - `assert parsed["source_kind"] is None` → `assert parsed["source_type"] is None`

3. **`_parse_ingestor_response` parser tests** (lines ~1029–1051): these use `source_kind` only as a generic YAML key. Replace `source_kind` with `source_type` in the three fixtures and their two assertions (`fm["source_kind"]` → `fm["source_type"]`) so no stale field name remains. Behavior is identical (generic parser).

4. **`test_set_source_kind_in_body_inserts_and_is_idempotent`** (lines 1067–1082): rename and retarget the helper:
   ```python
   def test_set_source_type_in_body_inserts_and_is_idempotent() -> None:
       from graph_wiki_core.commands.ingest import _set_source_type_in_body

       text = "---\ntarget_slug: foo\n---\nBody."
       out = _set_source_type_in_body(text, "note")
       lines = out.splitlines()
       assert lines[0] == "---"
       assert lines[1] == "source_type: note"
       # Idempotence: calling twice yields exactly one source_type: line.
       twice = _set_source_type_in_body(out, "spec")
       assert twice.count("source_type:") == 1
       assert "source_type: spec" in twice
       # No-frontmatter: returns text unchanged.
       assert _set_source_type_in_body("no frontmatter here", "note") == "no frontmatter here"
   ```

5. **`test_run_ingest_source_always_routes_to_sources_even_if_llm_says_adr`** (lines ~1090–1125): source `workspace/src.md` → `doc`.
   - Line 1102 comment: `# LLM claims adr AND emits a descriptive source_kind.` → `# LLM claims adr (page_type ignored — every ingest lands under sources/).`
   - Line 1104 fixture — drop the `source_kind` line:
     ```python
     fake_llm_response = (
         "---\ntitle: A Decision\npage_type: adr\ntarget_slug: a-decision\nsummary: x\n---\nBody."
     )
     ```
   - Line 1123: `assert result.source_kind == "source"` → `assert result.source_type == "doc"`

6. **`test_run_ingest_source_no_frontmatter_synthesizes_unknown`** (lines ~1128–1166): source `workspace/raw-notes.md` (a filename, not under a `raw/` folder) → `doc`.
   - Rename the function to `test_run_ingest_source_no_frontmatter_synthesizes_path_guess`.
   - Line 1133 docstring: replace `source_kind: unknown` with `source_type: doc (the path-guess)`.
   - Line 1159: `assert "source_kind: unknown" in written` → `assert "source_type: doc" in written`
   - Line 1164: `assert result.source_kind == "unknown"` → `assert result.source_type == "doc"`

7. **`test_run_ingest_source_surfaces_stripped_wikilinks_in_result`** (lines ~1169–1208): source `workspace/src.md` → `doc`.
   - Line 1186 fixture — drop the `"source_kind: source\n"` line from the multi-line string.
   - Line 1208: `assert result.source_kind == "source"` → `assert result.source_type == "doc"`

8. **Suggestion tests** (lines 1228, 1277, 1321, 1383): in each `ingestor_response`/fixture string, drop the leading `source_kind: source\n` (these tests assert on suggestions, not on type; the sources resolve to `doc`). Example for line 1228:
   ```python
   ingestor_response = "---\ntarget_slug: spec\ntitle: Spec\nsummary: x\n---\nBody."
   ```

9. **`test_synthesize_frontmatter_block_prepends_all_fields`** (lines 1434–1458):
   - Line 1442: `out = _synthesize_frontmatter_block(body, "unknown", "my-slug", None)` → `out = _synthesize_frontmatter_block(body, "note", "my-slug", None)`
   - Line 1444: `assert "source_kind: unknown" in out` → `assert "source_type: note" in out`
   - (Lines 1457–1458 use `"source"` as the source_type arg; they only assert on `entity_uri`, so leave them — or optionally change `"source"` → `"doc"` for realism.)

- [ ] **Step 10: Touch up the `test_suggest_pages.py` fixture**

In `packages/graph-wiki-core/tests/unit/test_suggest_pages.py`, line 140, replace the stale `source_kind` field in the on-disk Source-page fixture:

```python
        "---\nsource_type: doc\ntarget_slug: doc\nentity_uri: null\n---\n\nThe doc body.\n",
```

(`run_suggest_phase` does not read this field; the change just removes the dead `source_kind` name.)

- [ ] **Step 11: Run the full core ingest + suggest suites green**

Run:
```bash
uv run --package graph-wiki-core pytest tests/unit/test_commands_ingest.py tests/unit/test_suggest_pages.py -v
```
Expected: PASS — all tests, including the three new determination tests. There must be **zero** remaining `source_kind` references in `test_commands_ingest.py` except the parser-test fixtures you intentionally renamed; verify with:
```bash
grep -rn "source_kind" packages/graph-wiki-core/
```
Expected: no matches in `src/` or `tests/`.

- [ ] **Step 12: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py \
        packages/graph-wiki-core/tests/unit/test_commands_ingest.py \
        packages/graph-wiki-core/tests/unit/test_suggest_pages.py
git commit -m "feat(core): single source_type with raw-authoritative + LLM-override determination; drop source_kind"
```

---

## Task 4: Ingestor prompt rewording + snapshot regen (core)

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/prompts/ingestor.py:34-50` (`_SOURCE_LANDING`)
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/prompts/_fragments/frontmatter_rules.py:13`
- Test: `packages/graph-wiki-core/tests/prompts/test_prompt_snapshots.py` (regenerate `.ambr`)

- [ ] **Step 1: Reword the `source_kind` paragraph in `_SOURCE_LANDING`**

In `prompts/ingestor.py`, replace the second paragraph of `_SOURCE_LANDING` (lines 41–42):

```python
    "Optionally emit a descriptive `source_kind` field — use `source` for a "
    "document you can cleanly summarize. It is purely descriptive and does NOT "
    "control where the page is written.\n\n"
```

with:

```python
    "Emit a `source_type` field from this closed enum: `spec`, `article`, `pr`, "
    "`ticket`, `transcript`, `example`, `doc`, `note`. Classify it from the "
    "document's content. If the source is staged under a `raw/<type>/` folder "
    "(specs, articles, prs, tickets, transcripts, examples) the type is taken "
    "from that folder and your value is ignored — so this matters most for "
    "in-repo docs and loose files. Use `note` (the catch-all) when unsure. "
    "`source_type` is descriptive metadata and does NOT control where the page "
    "is written.\n\n"
```

- [ ] **Step 2: Reword the `source_kind` bullet in `FRONTMATTER_RULES`**

In `prompts/_fragments/frontmatter_rules.py`, replace line 13:

```
- `source_kind`: optional descriptive kind (e.g. `source`); does NOT control routing — every ingested doc lands under `sources/`
```

with:

```
- `source_type`: classification from the closed enum (`spec`, `article`, `pr`, `ticket`, `transcript`, `example`, `doc`, `note`); classify from content, default `note` when unsure. Files under `raw/<type>/` take the type from the folder. Does NOT control routing — every ingested doc lands under `sources/`
```

- [ ] **Step 3: Confirm the snapshot test now fails (drift detected)**

Run: `uv run --package graph-wiki-core pytest tests/prompts/test_prompt_snapshots.py::test_ingestor_system_snapshot tests/prompts/test_prompt_snapshots.py::test_ingestor_system_with_project_context -v`
Expected: FAIL — snapshot mismatch on the `INGESTOR_SYSTEM` text (the `source_kind` lines changed).

- [ ] **Step 4: Regenerate the snapshot and review the diff**

Run: `uv run --package graph-wiki-core pytest tests/prompts/test_prompt_snapshots.py --snapshot-update`
Then inspect the change to confirm it is *only* the ingestor source-type wording (no unrelated prompt drift):
```bash
git diff -- packages/graph-wiki-core/tests/prompts/__snapshots__/test_prompt_snapshots.ambr
```
Expected: the diff touches only the ingestor blocks; `source_kind` no longer appears, the new enum sentence does.

- [ ] **Step 5: Re-run the snapshot suite to verify green**

Run: `uv run --package graph-wiki-core pytest tests/prompts/test_prompt_snapshots.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/prompts/ingestor.py \
        packages/graph-wiki-core/src/graph_wiki_core/prompts/_fragments/frontmatter_rules.py \
        packages/graph-wiki-core/tests/prompts/__snapshots__/test_prompt_snapshots.ambr
git commit -m "feat(core): reword ingestor prompt to the single source_type enum + regen snapshots"
```

---

## Task 5: CLI surface rename (graph-wiki-cli)

**Files:**
- Modify: `packages/graph-wiki-cli/src/graph_wiki_cli/wiki_cli/main.py:326,329`
- Test: `packages/graph-wiki-cli/tests/unit/test_wiki_cli.py:90-115,129-152`

- [ ] **Step 1: Update the CLI test assertions/constructions**

In `packages/graph-wiki-cli/tests/unit/test_wiki_cli.py`:
- Line 98: `source_kind="unknown",` → `source_type="note",`
- Line 111 comment: `# stdout carries the ok line + the descriptive source_kind` → `# stdout carries the ok line + the source_type`
- Line 112: `assert "source_kind: unknown" in result.stdout` → `assert "source_type: note" in result.stdout`
- Line 137: `source_kind="source",` → `source_type="doc",`

- [ ] **Step 2: Run the CLI test to verify it fails**

Run: `uv run --package graph-wiki-cli pytest tests/unit/test_wiki_cli.py -k "ingest_source_cli" -v`
Expected: FAIL — `TypeError: ... unexpected keyword argument 'source_kind'` is gone, but `IngestResult(source_type=...)` is constructed and the CLI still echoes `source_kind: None` → assertion on `source_type: note` fails.

- [ ] **Step 3: Update the CLI echo**

In `packages/graph-wiki-cli/src/graph_wiki_cli/wiki_cli/main.py`, replace line 326:

```python
        typer.echo(f"     source_kind: {result.source_kind}, slug: {result.slug}")
```

with:

```python
        typer.echo(f"     source_type: {result.source_type}, slug: {result.slug}")
```

and replace line 329:

```python
                "⚠ frontmatter did not parse — wrote Source page with source_kind: unknown",
```

with:

```python
                "⚠ frontmatter did not parse — wrote Source page using the path-guess source_type",
```

- [ ] **Step 4: Run the CLI tests to verify they pass**

Run: `uv run --package graph-wiki-cli pytest tests/unit/test_wiki_cli.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/graph-wiki-cli/src/graph_wiki_cli/wiki_cli/main.py \
        packages/graph-wiki-cli/tests/unit/test_wiki_cli.py
git commit -m "refactor(cli): echo source_type instead of source_kind"
```

---

## Task 6: MCP surface rename (graph-wiki-mcp)

**Files:**
- Modify: `packages/graph-wiki-mcp/src/graph_wiki_mcp/server.py:327,379`
- Test: `packages/graph-wiki-mcp/tests/unit/test_mcp_new_tools.py:356-377,388-398`

- [ ] **Step 1: Update the MCP test constructions/assertions**

In `packages/graph-wiki-mcp/tests/unit/test_mcp_new_tools.py`:
- Line 364: `source_kind="unknown",` → `source_type="note",`
- Line 375: `assert out.source_kind == "unknown"` → `assert out.source_type == "note"`
- Line 396: `source_kind="source",` → `source_type="doc",`
- Line 352 docstring: `wiki_ingest surfaces source_kind / ...` → `wiki_ingest surfaces source_type / ...`

- [ ] **Step 2: Run the MCP test to verify it fails**

Run: `uv run --package graph-wiki-mcp pytest tests/unit/test_mcp_new_tools.py -k "passes_through_m3_fields" -v`
Expected: FAIL — `WikiIngestOutput` has no `source_type` field yet → validation/attribute error.

- [ ] **Step 3: Rename the field on the response model + mapping**

In `packages/graph-wiki-mcp/src/graph_wiki_mcp/server.py`, replace line 327:

```python
    source_kind: str | None = None
```

with:

```python
    source_type: str | None = None
```

and replace line 379:

```python
        source_kind=result.source_kind,
```

with:

```python
        source_type=result.source_type,
```

- [ ] **Step 4: Run the MCP tests to verify they pass**

Run: `uv run --package graph-wiki-mcp pytest tests/unit/test_mcp_new_tools.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/graph-wiki-mcp/src/graph_wiki_mcp/server.py \
        packages/graph-wiki-mcp/tests/unit/test_mcp_new_tools.py
git commit -m "refactor(mcp): rename wiki_ingest response field source_kind -> source_type"
```

---

## Task 7: Plugin-path doc alignment (graph-wiki plugin)

Doc-only — no tests. Align the plugin instructions to the same closed enum (`note` catch-all, no `rfc`), the `raw/<type>/`-authoritative rule, and content-classification for non-folder files.

**Files:**
- Modify: `plugins/graph-wiki/agents/ingestor.md`
- Modify: `plugins/graph-wiki/skills/graph-wiki/references/wiki-schema.md:243`
- Modify: `plugins/graph-wiki/skills/graph-wiki/references/page-formats.md:284`
- Modify: `plugins/graph-wiki/skills/graph-wiki/references/ingest-workflow.md:27`

- [ ] **Step 1: Correct the enum comment in `wiki-schema.md`**

Line 243 — replace:

```
source_type: spec                # spec | article | pr | ticket | transcript | rfc | doc | example
```

with:

```
source_type: spec                # spec | article | pr | ticket | transcript | example | doc | note
```

- [ ] **Step 2: Add the enum comment in `page-formats.md`**

Line 284 — replace the bare:

```
source_type: spec
```

with:

```
source_type: spec                # spec | article | pr | ticket | transcript | example | doc | note
```

- [ ] **Step 3: Correct the enum list in `ingest-workflow.md`**

Line 27 — replace:

```
- source_type guess (spec / article / pr / ticket / transcript / doc)
```

with:

```
- source_type guess (spec / article / pr / ticket / transcript / example / doc / note — raw/<type>/ folders are authoritative; in-repo docs default to `doc`, loose files to `note`)
```

- [ ] **Step 4: Add enum + classification guidance in `agents/ingestor.md`**

After line 50 (the "Required frontmatter: …, `source_type`, …" line in §4), insert a new paragraph:

```
`source_type` is a closed enum: `spec`, `article`, `pr`, `ticket`, `transcript`, `example`, `doc`, `note`. A source staged under a `raw/<type>/` folder takes its type from that folder (authoritative). For in-repo docs and loose files, classify from the document's content; default to `doc` for in-repo docs and `note` (the catch-all) when unsure. There is no `unknown` and no `rfc`.
```

- [ ] **Step 5: Verify no stale enum values remain in the plugin tree**

Run: `grep -rn "rfc\|source_kind" plugins/graph-wiki/`
Expected: no `source_kind` matches; no `rfc` matches in the `source_type` enum contexts (the `pr` substring inside other words is fine — confirm any `rfc` hit is unrelated).

- [ ] **Step 6: Commit**

```bash
git add plugins/graph-wiki/agents/ingestor.md \
        plugins/graph-wiki/skills/graph-wiki/references/wiki-schema.md \
        plugins/graph-wiki/skills/graph-wiki/references/page-formats.md \
        plugins/graph-wiki/skills/graph-wiki/references/ingest-workflow.md
git commit -m "docs(plugin): align ingestor docs to the single source_type enum (note catch-all, drop rfc)"
```

---

## Task 8: Full verification + manual smoke

**Files:** none (verification only).

- [ ] **Step 1: Run every affected package suite**

```bash
uv run --package wiki-io pytest tests/test_ingest_source.py tests/test_ingest_source_prep.py -v
uv run --package graph-wiki-core pytest -m "not integration" -q
uv run --package graph-wiki-cli pytest -m "not integration" -q
uv run --package graph-wiki-mcp pytest -m "not integration" -q
```
Expected: all PASS (integration/Bedrock tests skipped by default).

- [ ] **Step 2: Confirm `source_kind` is fully removed from production code**

```bash
grep -rn "source_kind" packages/ plugins/ | grep -v "/.venv/" | grep -v "/.worktrees/"
```
Expected: **no matches.** (If any remain, they are bugs — fix and re-run Step 1.)

- [ ] **Step 3: Lint**

Run: `uv run ruff check .`
Expected: no **new** errors introduced by this change. (The repo's src tree has pre-existing `ruff check`/`format` debt — do NOT run `ruff format`; only confirm you did not add new `ruff check` violations in the files you touched, e.g. `uv run ruff check packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py`.)

- [ ] **Step 4: Manual smoke (requires Bedrock access + the real workspace)**

This is the spec's manual acceptance check. It needs live Bedrock, so it is **not** an automated gate — run it against the pinned workspace when Bedrock is available:

```bash
# A raw-staged spec -> source_type: spec (path-authoritative)
uv run --package graph-wiki-cli gw wiki ingest source <workspace>/raw/specs/<some-spec>.md --json
# A loose in-repo doc -> source_type: doc (or LLM override), never source_kind
uv run --package graph-wiki-cli gw wiki ingest source docs/<some-doc>.md --json
```
Confirm in each written `<workspace>/wiki/sources/<slug>.md`:
- a `source_type:` line is present with the expected enum value,
- there is **no** `source_kind:` line,
- the JSON echo reports `source_type`, not `source_kind`.

- [ ] **Step 5: Final commit (if Step 3 required any lint touch-ups)**

```bash
git add -A
git commit -m "chore: source-type consolidation verification touch-ups"
```

---

## Self-review notes (author checklist — completed)

- **Spec coverage:** `source_kind` removal (Tasks 3, 5, 6, 7); core path *writes* `source_type` (Task 3, Steps 6–8); path-first + LLM-fallback determination (Task 3, Step 6); shared `SOURCE_TYPE_ENUM`/`RAW_FOLDER_TYPES` (Task 1); both surfaces consistent (Tasks 4, 7). Spec test matrix: raw-authoritative + override + fallback (Task 3 Part A); no-frontmatter synthesize → `source_type` (Task 3 Step 9.6); IngestResult field (Task 3); CLI/MCP (Tasks 5, 6); snapshot regen (Task 4); backlink consumer unchanged (no `test_backlink_index.py` edit — it already uses `source_type`). **Extra (beyond spec text):** the raw-folder wiring fix (Task 2 + Task 3 Step 4) — required because the spec assumed `guess_source_type` already returned the folder type, which it did not.
- **Type consistency:** field name `source_type` used uniformly in `IngestResult`, `WikiIngestOutput`, CLI echo; helper named `_set_source_type_in_body` consistently; `_synthesize_frontmatter_block(body, source_type, target_slug, entity_uri)` matches its single call site; `guess_source_type(rel_to_workspace, rel_to_repo)` matches both call sites (positional).
- **No placeholders:** every code/edit step shows the exact old→new text and the run command with expected output.
