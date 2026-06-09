# Raw Source Archive After Ingest — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A successful `run_ingest_source` automatically moves its raw-inbox source to `raw/_archived/<same relative path>`, so anything left under `<workspace>/raw/` (outside `_archived/`) is by definition un-ingested.

**Architecture:** A pure path helper (`archive_destination`) lives in `wiki_io/ingest_source.py` next to the existing raw-layout knowledge. `graph_wiki_core/commands/ingest.py` selects the *move unit* (skill directories move wholesale) in `run_ingest_source`, and `_run_common_tail` performs the move right before `append_log` — wrapped in try/except so a failed move never poisons a completed ingest. `IngestResult` gains `archived_to`, surfaced by the CLI and MCP. The Claude Code plugin gets the same behavior via instruction edits.

**Tech Stack:** Python 3.11, `uv` workspace monorepo, pytest (per-package, `--package` scoped), stdlib `shutil`/`pathlib`. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-06-09-raw-source-archive-design.md`

---

## Repo orientation (read once before starting)

- Run everything from the repo root `/Users/pat/Personal/agent-research`. Install once with `uv sync`.
- Tests are per-package: `uv run --package <pkg> pytest <path>` — never bare `pytest` from the root.
- **If you execute in a git worktree:** run `uv sync` inside the worktree first and use `<worktree>/.venv/bin/python` — a fresh worktree's `.pth` otherwise imports the parent repo's package source.
- The **workspace** (`<ws>`) is a directory holding `wiki/`, `raw/`, and `.graph-wiki/`; `raw/` is a *sibling* of `wiki/`, NOT inside it. `workspace_io.paths.raw_dir(ws)` returns `ws / "raw"`.
- In `run_ingest_source`, `wiki` is `<ws>/wiki`, so `wiki.parent` is the workspace root in every real flow and in all the tests below.
- Existing ingest tests mock the LLM two ways: `unittest.mock.patch("graph_wiki_core.commands.ingest.make_llm")` (older style) and `monkeypatch.setattr(ingest_mod, ...)` (newer skill-branch style). New tests below use the monkeypatch style.
- `packages/graph-wiki-core/tests/unit/test_commands_ingest.py` has an autouse fixture `_stub_extractor_llm` that defangs the M3 suggest phase for the whole module — new tests in that file get it for free, but we still stub `run_suggest_phase` directly so default-branch tests don't depend on extractor parsing.

## File structure

| File | Change |
| --- | --- |
| `packages/wiki-io/src/wiki_io/ingest_source.py` | Add `archive_destination(raw, unit)` pure helper + export-list docstring line |
| `packages/wiki-io/tests/test_ingest_source.py` | Unit tests for `archive_destination` |
| `packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py` | `IngestResult.archived_to`; `_run_common_tail(..., archive_unit=)` performs the move + log detail; `run_ingest_source` selects the move unit |
| `packages/graph-wiki-core/tests/unit/test_commands_ingest.py` | Integration tests (mocked LLM): moved / overwrite / loose-file no-op / skill dir wholesale / SKILL.md-in-kind-folder / simulated failure |
| `packages/graph-wiki-cli/src/graph_wiki_cli/wiki_cli/main.py` | Print `[ok] Archived source → ...` when set |
| `packages/graph-wiki-cli/tests/unit/test_wiki_cli.py` | CLI output test |
| `packages/graph-wiki-mcp/src/graph_wiki_mcp/server.py` | `WikiIngestOutput.archived_to` + mapping |
| `packages/graph-wiki-mcp/tests/unit/test_mcp_new_tools.py` | MCP field test |
| `plugins/graph-wiki/agents/ingestor.md`, `plugins/graph-wiki/commands/ingest.md`, `plugins/graph-wiki/skills/graph-wiki/references/ingest-workflow.md`, `plugins/graph-wiki/skills/graph-wiki/references/wiki-schema.md`, `plugins/graph-wiki/skills/graph-wiki/SKILL.md`, `plugins/graph-wiki/skills/graph-wiki/README.md`, `plugins/graph-wiki/CLAUDE.md` | Plugin parity: archive step + amend the "raw/ is immutable" rules that would otherwise forbid the move |

`run_ingest_work_item` is untouched (work items have no raw source). The eval-harness needs no changes — its corpora are never under `raw/`, so the destination guard makes archiving a no-op there (spec §5).

---

### Task 1: `archive_destination` pure helper (wiki-io)

**Files:**
- Modify: `packages/wiki-io/src/wiki_io/ingest_source.py` (helper after `guess_source_type`, ~line 182; docstring export list ~line 13)
- Test: `packages/wiki-io/tests/test_ingest_source.py`

- [ ] **Step 1: Write the failing tests**

Append to `packages/wiki-io/tests/test_ingest_source.py` (it already has `from pathlib import Path`; add the import shown):

```python
# ---------------------------------------------------------------------------
# archive_destination (raw-source-archive design 2026-06-09)
# ---------------------------------------------------------------------------


def test_archive_destination_kind_file() -> None:
    from wiki_io.ingest_source import archive_destination

    raw = Path("/ws/raw")
    assert archive_destination(raw, Path("/ws/raw/specs/x.md")) == Path("/ws/raw/_archived/specs/x.md")


def test_archive_destination_nested_unit() -> None:
    from wiki_io.ingest_source import archive_destination

    raw = Path("/ws/raw")
    # A directory unit (skill dir) maps wholesale to the mirrored path.
    assert archive_destination(raw, Path("/ws/raw/skill/foo")) == Path("/ws/raw/_archived/skill/foo")


def test_archive_destination_file_directly_in_raw() -> None:
    from wiki_io.ingest_source import archive_destination

    raw = Path("/ws/raw")
    assert archive_destination(raw, Path("/ws/raw/x.md")) == Path("/ws/raw/_archived/x.md")


def test_archive_destination_outside_raw_is_none() -> None:
    from wiki_io.ingest_source import archive_destination

    raw = Path("/ws/raw")
    assert archive_destination(raw, Path("/ws/docs/x.md")) is None
    assert archive_destination(raw, Path("/elsewhere/x.md")) is None


def test_archive_destination_already_archived_is_none() -> None:
    from wiki_io.ingest_source import archive_destination

    raw = Path("/ws/raw")
    assert archive_destination(raw, Path("/ws/raw/_archived/specs/x.md")) is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --package wiki-io pytest tests/test_ingest_source.py -k archive_destination -v`
Expected: 5 FAILED with `ImportError: cannot import name 'archive_destination'`

- [ ] **Step 3: Implement the helper**

In `packages/wiki-io/src/wiki_io/ingest_source.py`, insert immediately after `guess_source_type` (after its closing `return "note"`, before `def language_for`):

```python
def archive_destination(raw: Path, unit: Path) -> Path | None:
    """Return the `raw/_archived/` destination for an ingested move-unit, or None.

    `raw/_archived/<unit relative to raw>` when `unit` is under `raw/` and not
    already under `raw/_archived/`; otherwise None. Pure path math, no I/O —
    the caller performs (or skips) the actual move.
    """
    try:
        rel = unit.relative_to(raw)
    except ValueError:
        return None
    if not rel.parts or rel.parts[0] == "_archived":
        return None
    return raw / "_archived" / rel
```

Also add one line to the module docstring's Exports list (after the `guess_source_type` line):

```
    archive_destination(raw, unit) -> Path | None   (raw/_archived/ mapping; None when not applicable)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run --package wiki-io pytest tests/test_ingest_source.py -k archive_destination -v`
Expected: 5 PASSED

- [ ] **Step 5: Run the whole wiki-io suite (no regressions)**

Run: `uv run --package wiki-io pytest`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add packages/wiki-io/src/wiki_io/ingest_source.py packages/wiki-io/tests/test_ingest_source.py
git commit -m "feat(wiki-io): archive_destination maps raw/ units to raw/_archived/"
```

---

### Task 2: `archived_to` on IngestResult + the move in `_run_common_tail`

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py` (imports ~lines 21–64; `IngestResult` ~line 112; `_run_common_tail` ~line 940; `run_ingest_source` tail call ~line 1269)
- Test: `packages/graph-wiki-core/tests/unit/test_commands_ingest.py` (append at end of file)

- [ ] **Step 1: Write the failing tests**

Append to `packages/graph-wiki-core/tests/unit/test_commands_ingest.py`:

```python
# ---------------------------------------------------------------------------
# Raw-source archive after ingest (design 2026-06-09)
# ---------------------------------------------------------------------------


def _setup_archive_test_workspace(tmp_path, monkeypatch):
    """Workspace with a raw/ inbox; graph conn, entity lookups, and the suggest
    phase stubbed so default-branch ingests run offline."""
    from graph_wiki_core.commands import ingest as ingest_mod

    ws = tmp_path
    (ws / "wiki").mkdir()
    (ws / "wiki" / "log.md").write_text("", encoding="utf-8")
    (ws / "raw").mkdir()

    monkeypatch.setattr(ingest_mod, "resolve_wiki_and_repo", lambda wp: (ws / "wiki", ws))
    monkeypatch.setattr(ingest_mod, "render_project_context", lambda wiki: "")

    class _Conn:
        def close(self):
            pass

    monkeypatch.setattr(ingest_mod, "read_only_connect", lambda db: _Conn())
    monkeypatch.setattr(ingest_mod, "lookup_entity_by_path", lambda conn, repo, sp: None)
    monkeypatch.setattr(ingest_mod, "lookup_entity_by_name", lambda conn, name: None)
    monkeypatch.setattr(ingest_mod, "build_graph_tools", lambda conn: [])

    async def _fake_suggest(**kwargs):
        return [], {"reasoner": "skipped", "extractor": "skipped", "proposals": 0, "error": None}

    monkeypatch.setattr(ingest_mod, "run_suggest_phase", _fake_suggest)
    return ws


def _patch_default_branch_llm(monkeypatch, target_slug="auth-spec"):
    from graph_wiki_core.commands import ingest as ingest_mod

    response = f"---\ntarget_slug: {target_slug}\ntitle: Auth Spec\n---\n\nBody text.\n"

    class _LLM:
        async def ainvoke(self, messages):
            class _R:
                content = response
                usage_metadata = None

            return _R()

    monkeypatch.setattr(ingest_mod, "make_llm", lambda role, model_override=None: _LLM())


@pytest.mark.asyncio
async def test_run_ingest_source_archives_raw_source(tmp_path, monkeypatch):
    from graph_wiki_core.commands import ingest as ingest_mod

    ws = _setup_archive_test_workspace(tmp_path, monkeypatch)
    src = ws / "raw" / "specs" / "auth.md"
    src.parent.mkdir(parents=True)
    src.write_text("# Auth Spec\n\nbody\n", encoding="utf-8")
    _patch_default_branch_llm(monkeypatch)

    result = await ingest_mod.run_ingest_source(src, workspace_path=ws)

    assert result.status == "ok"
    assert result.archived_to == "raw/_archived/specs/auth.md"
    # source_path keeps the ORIGINAL path (spec §3).
    assert result.source_path == str(src)
    assert not src.exists()
    archived = ws / "raw" / "_archived" / "specs" / "auth.md"
    assert archived.read_text(encoding="utf-8") == "# Auth Spec\n\nbody\n"
    # The ingest log records the destination.
    log_text = (ws / "wiki" / "log.md").read_text(encoding="utf-8")
    assert "archived: raw/_archived/specs/auth.md" in log_text


@pytest.mark.asyncio
async def test_run_ingest_source_archive_overwrites_existing_destination(tmp_path, monkeypatch):
    from graph_wiki_core.commands import ingest as ingest_mod

    ws = _setup_archive_test_workspace(tmp_path, monkeypatch)
    stale = ws / "raw" / "_archived" / "specs" / "auth.md"
    stale.parent.mkdir(parents=True)
    stale.write_text("old version", encoding="utf-8")
    src = ws / "raw" / "specs" / "auth.md"
    src.parent.mkdir(parents=True)
    src.write_text("# Auth Spec v2\n", encoding="utf-8")
    _patch_default_branch_llm(monkeypatch)

    result = await ingest_mod.run_ingest_source(src, workspace_path=ws)

    assert result.archived_to == "raw/_archived/specs/auth.md"
    assert stale.read_text(encoding="utf-8") == "# Auth Spec v2\n"


@pytest.mark.asyncio
async def test_run_ingest_source_leaves_sources_outside_raw_untouched(tmp_path, monkeypatch):
    from graph_wiki_core.commands import ingest as ingest_mod

    ws = _setup_archive_test_workspace(tmp_path, monkeypatch)
    src = ws / "notes.md"
    src.write_text("# Loose Note\n\nbody\n", encoding="utf-8")
    _patch_default_branch_llm(monkeypatch, target_slug="loose-note")

    result = await ingest_mod.run_ingest_source(src, workspace_path=ws)

    assert result.status == "ok"
    assert result.archived_to is None
    assert src.exists()
    assert not (ws / "raw" / "_archived").exists()


@pytest.mark.asyncio
async def test_run_ingest_source_move_failure_does_not_fail_ingest(tmp_path, monkeypatch):
    from graph_wiki_core.commands import ingest as ingest_mod

    ws = _setup_archive_test_workspace(tmp_path, monkeypatch)
    src = ws / "raw" / "specs" / "auth.md"
    src.parent.mkdir(parents=True)
    src.write_text("# Auth Spec\n", encoding="utf-8")
    _patch_default_branch_llm(monkeypatch)

    def _boom(src_arg, dst_arg):
        raise OSError("disk says no")

    monkeypatch.setattr(ingest_mod.shutil, "move", _boom)

    result = await ingest_mod.run_ingest_source(src, workspace_path=ws)

    assert result.status == "ok"
    assert result.archived_to is None
    assert src.exists()


def test_ingest_result_archived_to_defaults_none_and_serializes():
    from graph_wiki_core.commands.ingest import IngestResult

    result = IngestResult(
        status="ok",
        page_path="sources/x.md",
        slug="x",
        title="X",
        page_type="source",
        source_path="/tmp/x.md",
        cross_refs_updated=1,
    )
    assert result.archived_to is None
    result.archived_to = "raw/_archived/specs/x.md"
    parsed = json.loads(json.dumps(dataclasses.asdict(result)))
    assert parsed["archived_to"] == "raw/_archived/specs/x.md"
```

(`json`, `dataclasses`, and `pytest` are already imported at the top of this test file.)

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_commands_ingest.py -k "archive or archived" -v`
Expected: FAIL — `AttributeError: ... no attribute 'shutil'` / `archived_to` missing / `TypeError: unexpected keyword`

- [ ] **Step 3: Implement**

All edits in `packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py`.

**3a — imports.** Add `import shutil` to the stdlib import block (after `import re`). Add `archive_destination` to the `from wiki_io.ingest_source import (...)` block (alphabetical — first entry, before `PREVIEW_CHARS` is fine given the existing ordering; match ruff's isort if it complains). Change the workspace_io import to:

```python
from workspace_io.paths import graph_dir, raw_dir
```

**3b — `IngestResult` field.** After the `guidance_pages_written` field (~line 173), add:

```python
    # Raw-source archive (design 2026-06-09): workspace-relative destination the
    # raw source was moved to (e.g. "raw/_archived/specs/x.md"). None when the
    # source was outside raw/, already archived, or the move failed.
    archived_to: str | None = None
```

Also add one line to the `IngestResult` docstring's field list:

```
        archived_to:        Workspace-relative raw/_archived/ destination the source
                            was moved to after a successful ingest; None for sources
                            outside raw/, work items, or when the move failed.
```

**3c — `_run_common_tail` signature.** Add the keyword-only parameter:

```python
async def _run_common_tail(
    branch: _IngestBranchResult,
    *,
    wiki: Path,
    conn,
    source_path: Path,
    source_text: str,
    title_guess: str,
    archive_unit: Path | None = None,
) -> IngestResult:
```

**3d — the move.** In `_run_common_tail`, immediately after `update_index(wiki)` and BEFORE the `detail = f"source: {source_path}"` line, insert:

```python
    # Archive the raw source (raw-source-archive design 2026-06-09). The raw
    # dir is derived from the workspace root (wiki.parent — matching
    # workspace_io.paths.raw_dir); sources outside raw/ map to None and are
    # never touched. A failed move logs a warning and leaves archived_to=None
    # — housekeeping never poisons a completed ingest.
    archived_to: str | None = None
    if archive_unit is not None:
        workspace_root = wiki.parent
        dest = archive_destination(raw_dir(workspace_root), archive_unit)
        if dest is not None:
            try:
                dest.parent.mkdir(parents=True, exist_ok=True)
                if dest.is_dir():
                    shutil.rmtree(dest)
                elif dest.exists():
                    dest.unlink()
                shutil.move(str(archive_unit), str(dest))
                archived_to = dest.relative_to(workspace_root).as_posix()
            except Exception:
                logger.warning(
                    "failed to archive ingested source %s; leaving it in place", archive_unit, exc_info=True
                )
                archived_to = None
```

**3e — log detail.** Change the detail construction to record the destination:

```python
    detail = f"source: {source_path}"
    if archived_to:
        detail += f"; archived: {archived_to}"
    if stripped_wikilinks:
        detail += f"; stripped {len(stripped_wikilinks)} unresolved wikilink(s): {stripped_wikilinks[:5]}"
```

**3f — result.** Add `archived_to=archived_to,` to the `IngestResult(...)` constructor at the end of `_run_common_tail` (after `guidance_pages_written=branch.guidance_pages_written,`).

**3g — caller.** In `run_ingest_source`, pass the unit to the tail (skill-aware selection comes in Task 3 — for now the unit is the source path itself):

```python
        return await _run_common_tail(
            branch,
            wiki=wiki,
            conn=conn,
            source_path=source_path,
            source_text=text,
            title_guess=title_guess,
            archive_unit=source_path,
        )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_commands_ingest.py -k "archive or archived" -v`
Expected: 5 PASSED (the 6th, dataclass test, also passes)

- [ ] **Step 5: Run the full ingest test module (no regressions)**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_commands_ingest.py`
Expected: all pass. Watch the two existing skill tests (`test_run_ingest_source_skill_*`) — their sources live under `raw/skill/` and will now be MOVED during the test; their assertions only check wiki output, so they should still pass. If one fails on a missing source file, the failure is in your change, not the test — the move must happen after all reads.

- [ ] **Step 6: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py packages/graph-wiki-core/tests/unit/test_commands_ingest.py
git commit -m "feat(graph-wiki-core): archive raw sources to raw/_archived/ after ingest"
```

---

### Task 3: Skill move-unit selection (directories move wholesale)

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py` (`run_ingest_source`, after the path-guess block ~line 1218)
- Test: `packages/graph-wiki-core/tests/unit/test_commands_ingest.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `packages/graph-wiki-core/tests/unit/test_commands_ingest.py`. These reuse `_setup_archive_test_workspace` from Task 2 and the planner/synthesizer fake from the existing skill tests:

```python
def _patch_skill_branch_llm(monkeypatch):
    from graph_wiki_core.commands import ingest as ingest_mod

    planner_yaml = (
        "- title: Use a Virtualizer\n"
        "  slug: use-virtualizer\n"
        "  topic: react-native\n"
        "  summary: Use a virtualizer.\n"
        "  applies_when: Rendering a list.\n"
        "  impact: high\n"
        "  triggers:\n    globs: []\n    keywords: []\n    entities: []\n"
        "  content: Use a virtualizer instead of ScrollView.\n"
    )
    guidance_page = (
        "---\ntitle: Use a Virtualizer\ncategory: guidance\ntopic: react-native\n"
        "summary: Use a virtualizer.\napplies_when: Rendering a list.\nimpact: high\n"
        "updated: 2026-06-08\ntokens: 0\n---\n\n## Guidance\nUse a virtualizer.\n"
    )

    def _fake_make_llm(role, model_override=None):
        out = planner_yaml if role == "skill_planner" else guidance_page

        class _LLM:
            async def ainvoke(self, messages):
                class _R:
                    content = out
                    usage_metadata = None

                return _R()

        return _LLM()

    monkeypatch.setattr(ingest_mod, "make_llm", _fake_make_llm)


@pytest.mark.asyncio
async def test_run_ingest_source_archives_skill_directory_wholesale(tmp_path, monkeypatch):
    from graph_wiki_core.commands import ingest as ingest_mod

    ws = _setup_archive_test_workspace(tmp_path, monkeypatch)
    skill_dir = ws / "raw" / "skill" / "react-native"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# RN Skill\nUse a virtualizer.\n", encoding="utf-8")
    (skill_dir / "extra.txt").write_text("companion\n", encoding="utf-8")
    _patch_skill_branch_llm(monkeypatch)

    # Pass the SKILL.md file — the anchor's PARENT directory must move wholesale.
    result = await ingest_mod.run_ingest_source(skill_dir / "SKILL.md", workspace_path=ws)

    assert result.status == "ok"
    assert result.archived_to == "raw/_archived/skill/react-native"
    assert not skill_dir.exists()
    archived = ws / "raw" / "_archived" / "skill" / "react-native"
    assert (archived / "SKILL.md").is_file()
    assert (archived / "extra.txt").is_file()
    # The kind folder itself stays put.
    assert (ws / "raw" / "skill").is_dir()


@pytest.mark.asyncio
async def test_run_ingest_source_skill_md_directly_in_kind_folder_moves_only_file(tmp_path, monkeypatch):
    from graph_wiki_core.commands import ingest as ingest_mod

    ws = _setup_archive_test_workspace(tmp_path, monkeypatch)
    kind_dir = ws / "raw" / "skill"
    kind_dir.mkdir(parents=True)
    src = kind_dir / "SKILL.md"
    src.write_text("# Bare Skill\nGuidance.\n", encoding="utf-8")
    # A sibling awaiting ingestion must NOT be swept along.
    sibling = kind_dir / "other-skill.md"
    sibling.write_text("# Other\n", encoding="utf-8")
    _patch_skill_branch_llm(monkeypatch)

    result = await ingest_mod.run_ingest_source(src, workspace_path=ws)

    assert result.status == "ok"
    assert result.archived_to == "raw/_archived/skill/SKILL.md"
    assert not src.exists()
    assert sibling.exists()
    assert kind_dir.is_dir()
    assert (ws / "raw" / "_archived" / "skill" / "SKILL.md").is_file()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_commands_ingest.py -k "wholesale or kind_folder" -v`
Expected: `test_..._archives_skill_directory_wholesale` FAILS — `archived_to == "raw/_archived/skill/react-native/SKILL.md"` (the file moved, not the directory). The kind-folder test may already pass (unit defaults to `source_path`); that's fine.

- [ ] **Step 3: Implement the move-unit selection**

In `run_ingest_source`, insert after the path-guess `if/else` block (right after `path_guess = guess_source_type(...)`, before the URI-drift comment block), and update the tail call:

```python
        # Archive move-unit (raw-source-archive design 2026-06-09): a skill
        # anchor moves its directory wholesale — unless the anchor sits
        # directly in a kind folder (e.g. raw/skill/SKILL.md, parent path has
        # fewer than 2 parts relative to raw/), where moving the parent would
        # archive the entire kind folder; move just the file there. Every
        # other source moves itself. Units outside raw/ no-op downstream
        # (archive_destination returns None).
        archive_unit: Path = source_path
        if anchor is not None:
            archive_unit = anchor.parent
            try:
                rel = anchor.parent.relative_to(raw_dir(wiki.parent))
                if len(rel.parts) < 2:
                    archive_unit = anchor
            except ValueError:
                pass
```

Then change the tail call's `archive_unit=source_path,` (from Task 2 step 3g) to `archive_unit=archive_unit,`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_commands_ingest.py -k "wholesale or kind_folder" -v`
Expected: 2 PASSED

- [ ] **Step 5: Run the full graph-wiki-core suite**

Run: `uv run --package graph-wiki-core pytest -m "not integration"`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py packages/graph-wiki-core/tests/unit/test_commands_ingest.py
git commit -m "feat(graph-wiki-core): skill directories archive wholesale; bare SKILL.md moves alone"
```

---

### Task 4: CLI surface — print the archive destination

**Files:**
- Modify: `packages/graph-wiki-cli/src/graph_wiki_cli/wiki_cli/main.py` (text-mode output, ~line 333)
- Test: `packages/graph-wiki-cli/tests/unit/test_wiki_cli.py` (append near the other ingest CLI tests)

- [ ] **Step 1: Write the failing test**

Append to `packages/graph-wiki-cli/tests/unit/test_wiki_cli.py` (module already has `runner`, `patch`; mirror `test_ingest_source_cli_prints_guidance_pages`):

```python
def test_ingest_source_cli_prints_archived_to(tmp_path):
    """Text-mode CLI reports the raw/_archived/ destination when set."""
    from unittest.mock import AsyncMock

    from graph_wiki_cli.wiki_cli.main import wiki_app
    from graph_wiki_core.commands.ingest import IngestResult

    src = tmp_path / "auth.md"
    src.write_text("# Auth Spec\n\nBody.", encoding="utf-8")

    fake_result = IngestResult(
        status="ok",
        page_path="sources/auth-spec.md",
        slug="auth-spec",
        title="Auth Spec",
        page_type="source",
        source_path=str(src),
        cross_refs_updated=1,
        source_type="spec",
        archived_to="raw/_archived/specs/auth.md",
    )

    with patch(
        "graph_wiki_cli.wiki_cli.main.run_ingest_source",
        new_callable=AsyncMock,
        return_value=fake_result,
    ):
        result = runner.invoke(wiki_app, ["ingest", str(src)])

    assert result.exit_code == 0
    assert "[ok] Archived source → raw/_archived/specs/auth.md" in result.stdout
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --package graph-wiki-cli pytest tests/unit/test_wiki_cli.py -k archived_to -v`
Expected: FAIL — assertion on stdout (no archived line printed)

- [ ] **Step 3: Implement**

In `packages/graph-wiki-cli/src/graph_wiki_cli/wiki_cli/main.py`, in the text-mode branch of `ingest_source`, directly after the `typer.echo(f"     source_type: ...")` line, add:

```python
        if result.archived_to:
            typer.echo(f"[ok] Archived source → {result.archived_to}")
```

(`--json` picks the field up automatically via `dataclasses.asdict`.)

- [ ] **Step 4: Run the test to verify it passes, then the package suite**

Run: `uv run --package graph-wiki-cli pytest tests/unit/test_wiki_cli.py -v`
Expected: all pass (including the JSON-mode tests — `archived_to: null` is additive)

- [ ] **Step 5: Commit**

```bash
git add packages/graph-wiki-cli/src/graph_wiki_cli/wiki_cli/main.py packages/graph-wiki-cli/tests/unit/test_wiki_cli.py
git commit -m "feat(graph-wiki-cli): report raw/_archived/ destination after ingest"
```

---

### Task 5: MCP surface — `WikiIngestOutput.archived_to`

**Files:**
- Modify: `packages/graph-wiki-mcp/src/graph_wiki_mcp/server.py` (`WikiIngestOutput` ~line 317; mapping ~line 374)
- Test: `packages/graph-wiki-mcp/tests/unit/test_mcp_new_tools.py` (append near the other wiki_ingest tests)

- [ ] **Step 1: Write the failing test**

Append to `packages/graph-wiki-mcp/tests/unit/test_mcp_new_tools.py` (module already imports `MagicMock`, `AsyncMock`, `patch`; async tests run bare under `asyncio_mode = "auto"`):

```python
async def test_wiki_ingest_output_carries_archived_to() -> None:
    """WikiIngestOutput mirrors IngestResult.archived_to."""
    from graph_wiki_core.commands.ingest import IngestResult
    from graph_wiki_mcp.server import WikiIngestInput, wiki_ingest

    mock_result = IngestResult(
        status="ok",
        page_path="sources/auth-spec.md",
        slug="auth-spec",
        title="Auth Spec",
        page_type="source",
        source_path="/ws/raw/specs/auth.md",
        cross_refs_updated=1,
        archived_to="raw/_archived/specs/auth.md",
    )

    mock_ctx = MagicMock()
    mock_ctx.report_progress = AsyncMock()

    with patch("graph_wiki_mcp.server.run_ingest_source", new_callable=AsyncMock) as mock_source:
        mock_source.return_value = mock_result
        out = await wiki_ingest(WikiIngestInput(type="source", source_path="/ws/raw/specs/auth.md"), mock_ctx)

    assert out.archived_to == "raw/_archived/specs/auth.md"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --package graph-wiki-mcp pytest tests/unit/test_mcp_new_tools.py -k archived_to -v`
Expected: FAIL — `AttributeError: 'WikiIngestOutput' object has no attribute 'archived_to'`

- [ ] **Step 3: Implement**

In `packages/graph-wiki-mcp/src/graph_wiki_mcp/server.py`:

After `guidance_pages_written: list[str] = Field(default_factory=list)` in `WikiIngestOutput`, add:

```python
    # Raw-source archive (design 2026-06-09): workspace-relative raw/_archived/
    # destination, None when the source was outside raw/ or the move failed.
    archived_to: str | None = None
```

And in the `return WikiIngestOutput(...)` call, after `guidance_pages_written=result.guidance_pages_written,`, add:

```python
        archived_to=result.archived_to,
```

- [ ] **Step 4: Run the test to verify it passes, then the package suite**

Run: `uv run --package graph-wiki-mcp pytest -m "not integration"`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add packages/graph-wiki-mcp/src/graph_wiki_mcp/server.py packages/graph-wiki-mcp/tests/unit/test_mcp_new_tools.py
git commit -m "feat(graph-wiki-mcp): expose archived_to on WikiIngestOutput"
```

---

### Task 6: Plugin parity — instruction edits

The Claude Code plugin ingests via agent/command instructions, not via `run_ingest_source`, so the same behavior is added by editing markdown. The plugin docs currently say `raw/` is strictly immutable in several places — those rules would forbid the archive move, so each contradicting line is amended (move-only carve-out; file *contents* stay immutable). No automated tests; verification is by grep.

**Files (all Modify):**
- `plugins/graph-wiki/agents/ingestor.md`
- `plugins/graph-wiki/commands/ingest.md`
- `plugins/graph-wiki/skills/graph-wiki/references/ingest-workflow.md`
- `plugins/graph-wiki/skills/graph-wiki/references/wiki-schema.md`
- `plugins/graph-wiki/skills/graph-wiki/SKILL.md`
- `plugins/graph-wiki/skills/graph-wiki/README.md`
- `plugins/graph-wiki/CLAUDE.md`

- [ ] **Step 1: `agents/ingestor.md` — add the archive step and amend the rule**

Insert a new step between `### 11. Log` and `### 12. Report`, renumbering Report to 13:

```markdown
### 12. Archive the source
If the source lives under `<workspace>/raw/` (and not already under `raw/_archived/`), move it to the mirrored archive path so the inbox only holds un-ingested material:

```bash
mkdir -p "$(dirname "<workspace>/raw/_archived/<rel-path>")"
mv "<workspace>/raw/<rel-path>" "<workspace>/raw/_archived/<rel-path>"
```

- Skill directories move wholesale (e.g. `raw/skill/foo/` → `raw/_archived/skill/foo/`). A bare `SKILL.md` sitting directly in a kind folder (`raw/skill/SKILL.md`) moves alone — never move the kind folder itself.
- If the destination already exists, replace it (re-ingest semantics; old versions are recoverable via workspace git).
- Sources outside `raw/` (in-repo docs, loose notes) are never touched.
- If the move fails, note the warning and continue — the ingest still succeeded.

### 13. Report
```

In `## Rules`, replace:

```markdown
- **`raw/` is immutable.** Read only.
```

with:

```markdown
- **`raw/` is an inbox.** Never edit file contents under `raw/` — the only permitted write is the post-ingest archive move into `raw/_archived/` (step 12). Anything under `raw/` outside `_archived/` is un-ingested.
```

- [ ] **Step 2: `commands/ingest.md` — add the step and amend the rule**

In `## What happens`, insert between items 10 (Log) and 11 (Report), renumbering Report to 12:

```markdown
11. **Archive** — moves the raw source to `raw/_archived/<same relative path>` (skill directories move wholesale; an existing destination is replaced; sources outside `raw/` are never touched)
```

In `## Rules`, replace:

```markdown
- `raw/` is immutable — the ingestor reads only
```

with:

```markdown
- `raw/` file contents are never edited — after a successful ingest the source is moved to `raw/_archived/<same relative path>`, so anything left under `raw/` is un-ingested
```

- [ ] **Step 3: `references/ingest-workflow.md` — source-location note + step**

Replace the `## Source locations` bullet:

```markdown
- **`<workspace>/raw/<...>`** — clipped articles, specs, PRs, transcripts you've staged. Immutable; the LLM never edits. Owned by `workspace_io`.
```

with:

```markdown
- **`<workspace>/raw/<...>`** — clipped articles, specs, PRs, transcripts you've staged. File contents are never edited; after a successful ingest the source is moved to `raw/_archived/<same relative path>`, so `raw/` (outside `_archived/`) only holds un-ingested material. Owned by `workspace_io`.
```

In `## Step-by-step`, insert between `### 11. Append to log.md` and `### 12. Report back to the user`, renumbering Report to 13:

```markdown
### 12. Archive the raw source
If the source lives under `<workspace>/raw/` (and not already under `raw/_archived/`), `mkdir -p` the mirrored `_archived` parent and `mv` the source there (`raw/specs/x.md` → `raw/_archived/specs/x.md`). Skill directories move wholesale; a bare `SKILL.md` directly in a kind folder moves alone. Replace an existing destination (re-ingest semantics). Sources outside `raw/` are never touched. A failed move is a warning, not a failed ingest.
```

- [ ] **Step 4: amend the remaining immutability rules (one line each)**

`plugins/graph-wiki/CLAUDE.md` line ~65, replace:

```markdown
- `<workspace>/raw/` — immutable ingested sources. The LLM never edits files here. Owned by `workspace_io`.
```

with:

```markdown
- `<workspace>/raw/` — staging inbox for sources. The LLM never edits file contents here; a successful ingest moves the source to `raw/_archived/<same relative path>`. Owned by `workspace_io`.
```

`plugins/graph-wiki/CLAUDE.md` iron rule 2 (~line 79), replace:

```markdown
2. The LLM never writes to `<workspace>/raw/`; all LLM writes for the wiki go under `<workspace>/wiki/`.
```

with:

```markdown
2. The LLM never edits file contents under `<workspace>/raw/`; all LLM writes for the wiki go under `<workspace>/wiki/`. Single exception: after a successful ingest the source is *moved* to `<workspace>/raw/_archived/<same relative path>`.
```

`plugins/graph-wiki/skills/graph-wiki/SKILL.md` rules 2–3 (~lines 188–189), replace:

```markdown
2. **The LLM never edits files in `raw/`.** Sources are immutable.
3. **All LLM writes for the wiki go under `<workspace>/wiki/`.** Work items go to `<workspace>/work/` (owned by `workspace_io`); ingested sources stay in `<workspace>/raw/` (immutable). No exceptions.
```

with:

```markdown
2. **The LLM never edits file contents in `raw/`.** The only permitted `raw/` write is the post-ingest move to `raw/_archived/<same relative path>`.
3. **All LLM writes for the wiki go under `<workspace>/wiki/`.** Work items go to `<workspace>/work/` (owned by `workspace_io`); ingested sources are archived under `<workspace>/raw/_archived/`.
```

`plugins/graph-wiki/skills/graph-wiki/SKILL.md` line ~36: change the parenthetical "(immutable ingested sources)" to "(source inbox; ingested sources move to `raw/_archived/`)".

`plugins/graph-wiki/skills/graph-wiki/README.md` line ~111: change "The LLM never edits `<workspace>/raw/`;" to "The LLM never edits file contents under `<workspace>/raw/` (ingested sources are moved to `raw/_archived/`);".

`plugins/graph-wiki/skills/graph-wiki/references/wiki-schema.md` line ~7: change the parenthetical "(immutable sources)" to "(source inbox; ingested sources move to `raw/_archived/`)".

`plugins/graph-wiki/skills/graph-wiki/references/wiki-schema.md` rule 2 (~line 43), replace:

```markdown
2. **`<workspace>/raw/` is immutable.** The LLM reads from `raw/` but never writes to it. Never rename, never delete, never edit.
```

with:

```markdown
2. **`<workspace>/raw/` contents are read-only.** The LLM never edits, renames within, or deletes staged sources — the single permitted operation is moving a successfully-ingested source to `raw/_archived/<same relative path>`.
```

Leave `agents/ingestor.md` line 58 ("raw/-staged sources ... are immutable — do NOT set these fields") unchanged — it's about drift-detection frontmatter fields and remains true.

- [ ] **Step 5: Verify by grep**

Run: `grep -rn "_archived" plugins/graph-wiki --include="*.md" | wc -l`
Expected: ≥ 12 matches (every file touched above mentions the archive path)

Run: `grep -rn 'is immutable' plugins/graph-wiki --include="*.md"`
Expected: no matches. (`agents/ingestor.md:58` says "**are** immutable" about drift-detection fields and is intentionally kept — it doesn't match this pattern.)

- [ ] **Step 6: Commit**

```bash
git add plugins/graph-wiki
git commit -m "docs(graph-wiki-plugin): archive ingested raw sources to raw/_archived/ (parity with run_ingest_source)"
```

---

### Task 7: Final verification sweep

- [ ] **Step 1: Run every affected package suite**

```bash
uv run --package wiki-io pytest
uv run --package graph-wiki-core pytest -m "not integration"
uv run --package graph-wiki-cli pytest -m "not integration"
uv run --package graph-wiki-mcp pytest -m "not integration"
```

Expected: all pass.

- [ ] **Step 2: Lint the changed files**

Run: `uv run ruff check packages/wiki-io packages/graph-wiki-core packages/graph-wiki-cli packages/graph-wiki-mcp`
Expected: no NEW errors in the files this plan touched (the repo carries pre-existing ruff noise — do NOT run `ruff format` across the tree; match surrounding style instead).

- [ ] **Step 3: Spec cross-check**

Confirm each spec decision is implemented: automatic trigger with no opt-out flag (Tasks 2–3), wholesale skill-dir move with the kind-folder exception (Task 3), overwrite-on-collision (Task 2, `rmtree`/`unlink` before move), sources outside `raw/` untouched (Task 2 guard via `archive_destination`), warn-and-continue failure posture (Task 2 try/except), plugin parity (Task 6), `run_ingest_work_item` untouched (no edits made to it).

- [ ] **Step 4: Commit anything outstanding**

```bash
git status
```

Expected: clean tree (each task committed as it went). If anything is left, commit it with a message matching the task it belongs to.
