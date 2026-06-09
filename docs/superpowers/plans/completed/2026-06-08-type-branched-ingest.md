# Type-Branched Ingest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `source_type` dispatcher to `run_ingest_source()` so a `skill` source runs a two-pass (planner → synthesizer) flow that writes `guidance` pages directly, while every other type continues unchanged on the default path.

**Architecture:** Refactor the monolithic `run_ingest_source()` into a thin orchestrator that (1) does shared setup, (2) dispatches to `_run_default_branch()` or `_run_skill_branch()`, both returning a `_IngestBranchResult`, then (3) feeds that result to a shared `_run_common_tail()` that writes the source page, resolves wikilinks, runs the (conditional) suggest phase, updates the index, and logs. The skill branch additionally writes `wiki/guidance/<topic>/<slug>.md` pages via a `SubagentPool` fan-out before handing off. Guidance pages are wired into the existing backlink index so their `## Applies to` entity links produce `## Referenced in wiki` backlinks.

**Tech Stack:** Python 3.11+, `uv` workspace monorepo, `asyncio`, `langchain-aws` Bedrock Converse via `model_adapter.make_llm(role)`, `subagent_runtime.SubagentPool`, `pytest` (per-package), `guidance-io` package, `pyyaml`.

**Spec:** `docs/superpowers/specs/2026-06-08-type-branched-ingest-design.md`
**Depends on:** `docs/superpowers/specs/2026-06-08-guidance-package-design.md` (already shipped: `guidance-io` base slice merged at `c9a92ba0`).

---

## Important design notes (read before starting)

1. **Spec gap — `guess_source_type()` must learn `skill`.** The spec's "Source Type Extension" only edits two frozensets, but `wiki_io.ingest_source.guess_source_type()` has no clause that returns `"skill"`, so `path_guess` would never be `"skill"` and the dispatch would never fire. Task 2 adds that clause. The dispatch key is `path_guess == "skill"` (a `raw/skill/`-staged file), computed deterministically before any LLM call — this is how `raw/spec/` etc. already work.

2. **Faithful extraction.** Per the approved design, the default path is extracted into `_run_default_branch()` and a shared `_run_common_tail()`. Tasks 9–10 do this refactor guarded by the existing (extensive) ingest test suite — no behavioral change to the default path.

3. **Backlink wiring is in scope.** Task 3 adds `guidance` to `backlink_index._PRESERVED_WIKI_DIRS` and `init_vault.FIXED_VAULT_DIRS` so guidance pages' `## Applies to` links surface as entity backlinks (the guidance-package spec calls this mirror "load-bearing").

4. **`guidance_pages_written` paths are workspace-relative** (e.g. `wiki/guidance/react-native/use-virtualizer.md`), unlike `IngestResult.page_path` which is wiki-relative. This matches the spec.

5. **`_resolve_wikilinks` resolves guidance links for free.** It matches by relpath OR basename via a full-vault `rglob("*.md")` (`ingest.py:426`). The skill branch writes guidance pages *before* the common tail writes the source page, so the source page's `## Generates` `[[guidance/<topic>/<slug>]]` links resolve and are not stripped.

6. **Worktree venv.** If executing in a fresh `git worktree`, run `uv sync` in it first and use `<worktree>/.venv/bin/python` for tests (bare `python` imports the parent repo's src). All `uv run --package ... pytest` commands below assume the worktree's own venv.

---

## File Structure

**New files:**
- `packages/graph-wiki-core/src/graph_wiki_core/prompts/skill_planner.py` — Pass-1 system prompt builder.
- `packages/graph-wiki-core/src/graph_wiki_core/prompts/skill_synthesizer.py` — Pass-2 system prompt builder.
- `packages/graph-wiki-core/tests/unit/test_prompts_skill.py` — prompt builder tests.

**Modified files:**
- `packages/graph-wiki-core/pyproject.toml` — add `guidance-io` dependency.
- `packages/wiki-io/src/wiki_io/ingest_source.py` — extend enums + `guess_source_type`.
- `packages/wiki-io/src/wiki_io/backlink_index.py` — add `guidance` dir + nested-slug rendering.
- `packages/wiki-io/src/wiki_io/init_vault.py` — add `guidance` to `FIXED_VAULT_DIRS`.
- `packages/model-adapter/src/model_adapter/models.toml` — add `skill_planner` + `skill_synthesizer` roles.
- `packages/graph-wiki-core/src/graph_wiki_core/commands/suggest_pages.py` — add `allowed_kinds` param.
- `packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py` — the dispatcher, branch functions, common tail, skill helpers, `IngestResult` field.
- `packages/graph-wiki-cli/src/graph_wiki_cli/wiki_cli/main.py` — render `guidance_pages_written`.
- `packages/graph-wiki-mcp/src/graph_wiki_mcp/server.py` — surface `guidance_pages_written`.

**Modified test files:**
- `packages/wiki-io/tests/test_ingest_source.py`
- `packages/wiki-io/tests/test_backlink_index.py`
- `packages/graph-wiki-core/tests/unit/test_commands_ingest.py`
- `packages/graph-wiki-cli/tests/unit/test_wiki_cli.py`
- `packages/graph-wiki-mcp/tests/unit/test_mcp_new_tools.py`

---

## Task 1: Wire `guidance-io` as a `graph-wiki-core` dependency

The skill branch imports `guidance_io.frontmatter` and `guidance_io.paths`. `graph-wiki-core` does not yet depend on `guidance-io`.

**Files:**
- Modify: `packages/graph-wiki-core/pyproject.toml:6-20` (dependencies) and `:26-32` (`[tool.uv.sources]`)

- [ ] **Step 1: Add the dependency and workspace source**

In `packages/graph-wiki-core/pyproject.toml`, add `"guidance-io"` to `dependencies` (after `"work-io",`):

```toml
dependencies = [
    "wiki-io",
    "graph-io",
    "model-adapter",
    "subagent-runtime",
    "workspace-io",
    "work-io",
    "guidance-io",
    "bm25s==0.3.8",
    "langchain-aws>=1.4.7",
    "langchain-core>=1.4.0",
    "typer>=0.25.1",
    "pydantic>=2.0",
    "python-frontmatter>=1.1.0",
    "pyyaml>=6.0",
]
```

And add the workspace pin under `[tool.uv.sources]` (after the `work-io` line):

```toml
[tool.uv.sources]
wiki-io         = { workspace = true }
graph-io        = { workspace = true }
model-adapter   = { workspace = true }
subagent-runtime = { workspace = true }
workspace-io    = { workspace = true }
work-io         = { workspace = true }
guidance-io     = { workspace = true }
```

- [ ] **Step 2: Re-sync the workspace**

Run: `uv sync`
Expected: completes without error; `guidance-io` resolves as an editable workspace member.

- [ ] **Step 3: Verify the import works from graph-wiki-core's environment**

Run: `uv run --package graph-wiki-core python -c "from guidance_io.frontmatter import parse, validate; from guidance_io.paths import page_path, slugify; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 4: Commit**

```bash
git add packages/graph-wiki-core/pyproject.toml uv.lock
git commit -m "build(graph-wiki-core): depend on guidance-io"
```

---

## Task 2: Extend source-type enums and `guess_source_type` for `skill`

**Files:**
- Modify: `packages/wiki-io/src/wiki_io/ingest_source.py:137-168`
- Test: `packages/wiki-io/tests/test_ingest_source.py`

- [ ] **Step 1: Write the failing tests**

Add to `packages/wiki-io/tests/test_ingest_source.py`:

```python
from pathlib import Path

from wiki_io.ingest_source import (
    RAW_FOLDER_TYPES,
    SOURCE_TYPE_ENUM,
    guess_source_type,
)


def test_skill_is_in_source_type_enum():
    assert "skill" in SOURCE_TYPE_ENUM


def test_skill_is_an_authoritative_raw_folder_type():
    assert "skill" in RAW_FOLDER_TYPES


def test_guess_source_type_detects_raw_skill_folder():
    # raw/ is a sibling of wiki/, so the path is workspace-relative.
    rel = Path("raw/skill/react-native/SKILL.md")
    assert guess_source_type(rel, None) == "skill"


def test_guess_source_type_unaffected_for_specs():
    rel = Path("raw/specs/x.md")
    assert guess_source_type(rel, None) == "spec"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --package wiki-io pytest tests/test_ingest_source.py -k "skill" -v`
Expected: FAIL — `skill` not in the frozensets and `guess_source_type` returns `note` for the `raw/skill/` path.

- [ ] **Step 3: Implement the enum + clause changes**

In `packages/wiki-io/src/wiki_io/ingest_source.py`, update the two frozensets (lines 137 and 140):

```python
SOURCE_TYPE_ENUM = frozenset({"spec", "article", "pr", "ticket", "transcript", "example", "doc", "note", "skill"})
# The subset a `raw/<type>/` folder produces authoritatively. The LLM cannot
# override these — see run_ingest_source / build_ingest_brief.
RAW_FOLDER_TYPES = frozenset({"spec", "article", "pr", "ticket", "transcript", "example", "skill"})
```

In `guess_source_type`, add the `skill` clause inside the `rel_to_workspace` block (after the `examples` check, before the closing of the `if rel_to_workspace is not None:` block):

```python
        if "examples" in parts:
            return "example"
        if "skill" in parts:
            return "skill"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --package wiki-io pytest tests/test_ingest_source.py -k "skill" -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Run the full wiki-io ingest_source suite (regression)**

Run: `uv run --package wiki-io pytest tests/test_ingest_source.py -v`
Expected: PASS (all existing tests still green).

- [ ] **Step 6: Commit**

```bash
git add packages/wiki-io/src/wiki_io/ingest_source.py packages/wiki-io/tests/test_ingest_source.py
git commit -m "feat(wiki-io): recognize skill as a raw-folder source type"
```

---

## Task 3: Wire `guidance` into the backlink index

Guidance pages carry `## Applies to` `[[entities/...]]` links. Adding `guidance` to `_PRESERVED_WIKI_DIRS` makes the scanner derive `## Referenced in wiki` backlinks from them. Because guidance pages are nested (`guidance/<topic>/<slug>.md`), the backlink bullet must render the topic-qualified slug so the wikilink resolves.

**Files:**
- Modify: `packages/wiki-io/src/wiki_io/backlink_index.py:36`, `:101-123`
- Modify: `packages/wiki-io/src/wiki_io/init_vault.py:33-41`
- Test: `packages/wiki-io/tests/test_backlink_index.py`

- [ ] **Step 1: Write the failing test**

Add to `packages/wiki-io/tests/test_backlink_index.py`:

```python
def test_guidance_page_applies_to_produces_entity_backlink(tmp_path):
    from wiki_io.backlink_index import regenerate_referenced_in_wiki

    wiki = tmp_path / "wiki"
    # Entity page with the scanner-owned heading.
    (wiki / "entities").mkdir(parents=True)
    (wiki / "entities" / "pkg_graph-io.md").write_text(
        "---\ntitle: graph-io\n---\n\n## Referenced in wiki\n\n_No wiki pages reference this entity yet._\n",
        encoding="utf-8",
    )
    # Guidance page (nested under a topic) linking that entity.
    (wiki / "guidance" / "react-native").mkdir(parents=True)
    (wiki / "guidance" / "react-native" / "use-virtualizer.md").write_text(
        "---\ntitle: Use a Virtualizer\ncategory: guidance\ntopic: react-native\n"
        "summary: x\napplies_when: y\nimpact: high\nupdated: 2026-06-08\ntokens: 0\n---\n\n"
        "## Guidance\nUse a virtualizer.\n\n## Applies to\n- [[entities/pkg_graph-io]]\n",
        encoding="utf-8",
    )

    updated = regenerate_referenced_in_wiki(wiki)

    assert "pkg_graph-io" in updated
    body = (wiki / "entities" / "pkg_graph-io.md").read_text(encoding="utf-8")
    # The bullet must carry the topic-qualified slug so the link resolves.
    assert "[[guidance/react-native/use-virtualizer]]" in body
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --package wiki-io pytest tests/test_backlink_index.py::test_guidance_page_applies_to_produces_entity_backlink -v`
Expected: FAIL — `guidance` is not scanned (not in `_PRESERVED_WIKI_DIRS`), so no backlink is produced.

- [ ] **Step 3: Add `guidance` to the preserved dirs and render nested slugs**

In `packages/wiki-io/src/wiki_io/backlink_index.py`, update line 36:

```python
_PRESERVED_WIKI_DIRS = ("sources", "concepts", "adrs", "architecture", "guidance")
```

Then make `build_entity_backlink_map` compute a topic-qualified slug for nested `guidance` pages. Replace `slug = page_path.stem` (line 115) with:

```python
        if category == "guidance":
            # Guidance pages are nested (guidance/<topic>/<slug>.md). Render the
            # topic-qualified slug so the [[guidance/<topic>/<slug>]] wikilink the
            # bullet emits actually resolves. Flat categories keep the bare stem.
            slug = page_path.relative_to(wiki / "guidance").with_suffix("").as_posix()
        else:
            slug = page_path.stem
```

(No change to `_format_bullet` — it already renders `[[<category>/<slug>]]`, which becomes `[[guidance/<topic>/<slug>]]`.)

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run --package wiki-io pytest tests/test_backlink_index.py::test_guidance_page_applies_to_produces_entity_backlink -v`
Expected: PASS.

- [ ] **Step 5: Add `guidance` to `FIXED_VAULT_DIRS` so bootstrap creates the dir**

In `packages/wiki-io/src/wiki_io/init_vault.py`, add `"guidance"` to `FIXED_VAULT_DIRS` (the list at lines 33-41). Append it after `"sources"`:

```python
FIXED_VAULT_DIRS = [
    "concepts",
    "architecture",
    "adrs",
    "entities",
    "sources",
    "guidance",
    "proposals",
    ".templates",
]
```

(Match the exact existing formatting/order of that list; insert the single `"guidance",` line.)

- [ ] **Step 6: Run the full wiki-io backlink + init_vault suites (regression)**

Run: `uv run --package wiki-io pytest tests/test_backlink_index.py tests/test_init_vault.py -v`
Expected: PASS. (If `test_init_vault.py` asserts the exact `FIXED_VAULT_DIRS` set or the created-dir list, update that assertion to include `guidance`.)

- [ ] **Step 7: Commit**

```bash
git add packages/wiki-io/src/wiki_io/backlink_index.py packages/wiki-io/src/wiki_io/init_vault.py packages/wiki-io/tests/test_backlink_index.py
git commit -m "feat(wiki-io): wire guidance pages into the backlink index"
```

---

## Task 4: Add `guidance_pages_written` to `IngestResult` and surface it (CLI + MCP)

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py:102-156`
- Modify: `packages/graph-wiki-cli/src/graph_wiki_cli/wiki_cli/main.py:331-352`
- Modify: `packages/graph-wiki-mcp/src/graph_wiki_mcp/server.py:317-335`, `:373-390`
- Test: `packages/graph-wiki-core/tests/unit/test_commands_ingest.py`, `packages/graph-wiki-cli/tests/unit/test_wiki_cli.py`, `packages/graph-wiki-mcp/tests/unit/test_mcp_new_tools.py`

- [ ] **Step 1: Write the failing core serialization test**

Add to `packages/graph-wiki-core/tests/unit/test_commands_ingest.py`:

```python
def test_ingest_result_has_guidance_pages_written_field():
    import dataclasses
    import json

    from graph_wiki_core.commands.ingest import IngestResult

    result = IngestResult(
        status="ok",
        page_path="sources/x.md",
        slug="x",
        title="X",
        page_type="source",
        source_path="/tmp/x.md",
        cross_refs_updated=1,
        guidance_pages_written=["wiki/guidance/t/a.md"],
    )
    parsed = json.loads(json.dumps(dataclasses.asdict(result)))
    assert parsed["guidance_pages_written"] == ["wiki/guidance/t/a.md"]


def test_ingest_result_guidance_pages_written_defaults_empty():
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
    assert result.guidance_pages_written == []
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_commands_ingest.py -k guidance_pages_written -v`
Expected: FAIL — `TypeError: ... unexpected keyword argument 'guidance_pages_written'`.

- [ ] **Step 3: Add the field**

In `packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py`, add after the `proposal_error` field (line 156) inside the `IngestResult` dataclass:

```python
    proposal_error: str | None = None
    # Type-branched ingest: workspace-relative paths of guidance pages created or
    # updated by the skill branch. Empty list for every other source type.
    guidance_pages_written: list[str] = field(default_factory=list)
```

Also add to the dataclass docstring (after the `suggestions_parsed:` entry):

```python
        guidance_pages_written: Type-branched ingest: workspace-relative paths of
                            guidance pages written by the skill branch (empty for
                            all other source types).
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_commands_ingest.py -k guidance_pages_written -v`
Expected: PASS.

- [ ] **Step 5: Write the failing CLI render test**

Add to `packages/graph-wiki-cli/tests/unit/test_wiki_cli.py` (mirror the existing `test_ingest_source_cli_prints_suggestions_and_degraded` fixture/patch style — patch `run_ingest_source` to return a fake `IngestResult`):

```python
def test_ingest_source_cli_prints_guidance_pages(monkeypatch):
    from graph_wiki_cli.wiki_cli import main as cli_main
    from graph_wiki_core.commands.ingest import IngestResult

    async def fake_ingest(path, workspace_path):
        return IngestResult(
            status="ok",
            page_path="sources/react-native-skill.md",
            slug="react-native-skill",
            title="React Native Skill",
            page_type="source",
            source_path=str(path),
            cross_refs_updated=1,
            source_type="skill",
            guidance_pages_written=[
                "wiki/guidance/react-native/use-virtualizer.md",
                "wiki/guidance/react-native/avoid-inline-styles.md",
            ],
        )

    monkeypatch.setattr(cli_main, "run_ingest_source", fake_ingest)

    from typer.testing import CliRunner

    runner = CliRunner()
    result = runner.invoke(cli_main.wiki_app, ["ingest", "/tmp/skill.md"])
    assert result.exit_code == 0
    assert "wrote 2 guidance page(s)" in result.stdout
    assert "wiki/guidance/react-native/use-virtualizer.md" in result.stdout
```

- [ ] **Step 6: Run to verify failure**

Run: `uv run --package graph-wiki-cli pytest tests/unit/test_wiki_cli.py::test_ingest_source_cli_prints_guidance_pages -v`
Expected: FAIL — no guidance output rendered.

- [ ] **Step 7: Render guidance pages in the CLI**

In `packages/graph-wiki-cli/src/graph_wiki_cli/wiki_cli/main.py`, in the `else:` (non-JSON) block, add after the `suggested_pages` block (after line 350, before the `suggestions_parsed` warning at line 351):

```python
        if result.guidance_pages_written:
            typer.echo(f"     wrote {len(result.guidance_pages_written)} guidance page(s):")
            for g in result.guidance_pages_written:
                typer.echo(f"       - {g}")
```

(JSON output needs no change — `dataclasses.asdict(result)` already includes the new field.)

- [ ] **Step 8: Run to verify pass**

Run: `uv run --package graph-wiki-cli pytest tests/unit/test_wiki_cli.py::test_ingest_source_cli_prints_guidance_pages -v`
Expected: PASS.

- [ ] **Step 9: Write the failing MCP passthrough test**

Add to `packages/graph-wiki-mcp/tests/unit/test_mcp_new_tools.py` (mirror `test_wiki_ingest_source_passes_through_suggestions`):

```python
async def test_wiki_ingest_source_passes_through_guidance_pages(monkeypatch):
    from graph_wiki_mcp import server
    from graph_wiki_core.commands.ingest import IngestResult

    async def fake_ingest(path, vault):
        return IngestResult(
            status="ok",
            page_path="sources/s.md",
            slug="s",
            title="S",
            page_type="source",
            source_path=str(path),
            cross_refs_updated=1,
            source_type="skill",
            guidance_pages_written=["wiki/guidance/t/a.md"],
        )

    monkeypatch.setattr(server, "run_ingest_source", fake_ingest)

    inp = server.WikiIngestInput(type="source", source_path="/tmp/s.md")
    out = await server.wiki_ingest(inp, _FakeCtx())
    assert out.guidance_pages_written == ["wiki/guidance/t/a.md"]
```

(`_FakeCtx` is the existing test double in that file used by the other `wiki_ingest` tests — reuse it. If the existing tests call `wiki_ingest` differently, match their exact call signature.)

- [ ] **Step 10: Run to verify failure**

Run: `uv run --package graph-wiki-mcp pytest tests/unit/test_mcp_new_tools.py::test_wiki_ingest_source_passes_through_guidance_pages -v`
Expected: FAIL — `WikiIngestOutput` has no `guidance_pages_written`.

- [ ] **Step 11: Surface the field in MCP**

In `packages/graph-wiki-mcp/src/graph_wiki_mcp/server.py`, add to the `WikiIngestOutput` model (after `proposal_error` at line 335):

```python
    proposal_error: str | None = None
    guidance_pages_written: list[str] = Field(default_factory=list)
```

And add to the `return WikiIngestOutput(...)` mapping (after `proposal_error=result.proposal_error,` at line 389):

```python
        proposal_error=result.proposal_error,
        guidance_pages_written=result.guidance_pages_written,
```

- [ ] **Step 12: Run to verify pass**

Run: `uv run --package graph-wiki-mcp pytest tests/unit/test_mcp_new_tools.py::test_wiki_ingest_source_passes_through_guidance_pages -v`
Expected: PASS.

- [ ] **Step 13: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py \
        packages/graph-wiki-core/tests/unit/test_commands_ingest.py \
        packages/graph-wiki-cli/src/graph_wiki_cli/wiki_cli/main.py \
        packages/graph-wiki-cli/tests/unit/test_wiki_cli.py \
        packages/graph-wiki-mcp/src/graph_wiki_mcp/server.py \
        packages/graph-wiki-mcp/tests/unit/test_mcp_new_tools.py
git commit -m "feat(ingest): add guidance_pages_written to IngestResult + CLI/MCP surfaces"
```

---

## Task 5: Add `allowed_kinds` parameter to `run_suggest_phase`

The common tail will call the suggest phase with a kind filter (full set for default; the skill branch skips suggest entirely). This task adds the parameter; the skip behavior is wired in Task 12.

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/suggest_pages.py:223-346`
- Test: `packages/graph-wiki-core/tests/unit/test_suggest_pages.py` (create if absent)

- [ ] **Step 1: Read the current signature and body**

Read `packages/graph-wiki-core/src/graph_wiki_core/commands/suggest_pages.py:223-346`. Confirm where `SUGGESTION_KINDS` (line 34) is referenced when building the extractor prompt / validating proposals (the kinds the extractor is told it may emit, and the set used to filter returned proposals).

- [ ] **Step 2: Write the failing test**

Add to `packages/graph-wiki-core/tests/unit/test_suggest_pages.py`:

```python
import inspect

from graph_wiki_core.commands.suggest_pages import run_suggest_phase


def test_run_suggest_phase_accepts_allowed_kinds():
    sig = inspect.signature(run_suggest_phase)
    assert "allowed_kinds" in sig.parameters
    assert sig.parameters["allowed_kinds"].default is None
```

- [ ] **Step 3: Run to verify failure**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_suggest_pages.py::test_run_suggest_phase_accepts_allowed_kinds -v`
Expected: FAIL — `allowed_kinds` not a parameter.

- [ ] **Step 4: Add the parameter**

In `run_suggest_phase`'s signature (the keyword-only block ending at line 232), add a final keyword parameter:

```python
async def run_suggest_phase(
    *,
    wiki: Path,
    page_path: Path,
    source_path: Path,
    source_text: str,
    entity_uri: str | None,
    entity_stem: str | None,
    graph_tools: list,
    allowed_kinds: frozenset[str] | None = None,
) -> tuple[list[dict], dict]:
```

At the top of the body (after the docstring), resolve the effective kinds:

```python
    kinds = allowed_kinds if allowed_kinds is not None else SUGGESTION_KINDS
```

Then use `kinds` everywhere the function currently uses `SUGGESTION_KINDS` directly to (a) tell the extractor which kinds are permitted and (b) filter/validate returned proposals. (Find each `SUGGESTION_KINDS` reference in the body and replace with `kinds`. Do NOT change the module-level `SUGGESTION_KINDS` constant — only the in-function references.) If the extractor prompt builder (`build_extract_suggestions_prompt`) hard-codes the kinds, leave its signature alone for now — the filtering on the returned proposals against `kinds` is sufficient for the default (full set) and the future `pr`/`plan` branches; add a short comment noting the prompt still advertises the full set but post-filtering enforces `kinds`.

- [ ] **Step 5: Run to verify pass**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_suggest_pages.py::test_run_suggest_phase_accepts_allowed_kinds -v`
Expected: PASS.

- [ ] **Step 6: Run the full suggest + ingest suites (regression — default path unchanged)**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_suggest_pages.py tests/unit/test_commands_ingest.py -v`
Expected: PASS. The default call site passes no `allowed_kinds`, so behavior is identical.

- [ ] **Step 7: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/suggest_pages.py packages/graph-wiki-core/tests/unit/test_suggest_pages.py
git commit -m "feat(suggest): add allowed_kinds filter to run_suggest_phase"
```

---

## Task 6: Add `skill_planner` and `skill_synthesizer` model roles

**Files:**
- Modify: `packages/model-adapter/src/model_adapter/models.toml`
- Test: `packages/model-adapter/tests/test_loader.py` (or the existing role-config test file — match the package's test layout)

- [ ] **Step 1: Write the failing test**

Add to the model-adapter test that exercises `load_role_config` (e.g. `packages/model-adapter/tests/test_loader.py`):

```python
import pytest

from model_adapter.loader import load_role_config


@pytest.mark.parametrize("role", ["skill_planner", "skill_synthesizer"])
def test_skill_roles_are_registered(role):
    cfg = load_role_config(role)
    assert cfg["model_id"]
    assert cfg["region"] == "us-east-1"
    assert cfg["max_tokens"] > 0
    assert cfg["max_concurrency"] >= 1
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run --package model-adapter pytest -k skill_roles_are_registered -v`
Expected: FAIL — `KeyError` for the unregistered roles.

- [ ] **Step 3: Add the two role stanzas**

Append to `packages/model-adapter/src/model_adapter/models.toml` (after the `[roles.extractor]` block, keeping the existing comment style):

```toml
# Type-branched ingest — Pass 1. Reads a full agent skill and emits a YAML chunk
# plan (one entry per guidance page). One call per ingest, so concurrency 1.
# Initial config mirrors `ingestor` (the closest precedent — long structured
# input, YAML output); revisit after a deepeval sweep.
[roles.skill_planner]
model_id        = "moonshotai.kimi-k2.5"
region          = "us-east-1"
max_tokens      = 4096
max_concurrency = 1
sweep_candidates = [
  "qwen.qwen3-32b-v1:0",
  "openai.gpt-oss-120b-1:0",
  "minimax.minimax-m2.5",
  "qwen.qwen3-next-80b-a3b",
  "moonshotai.kimi-k2.5",
]

# Type-branched ingest — Pass 2. Synthesizes one guidance page from one chunk
# plan entry; fanned out via SubagentPool. Mirrors `extractor` (structured
# single-purpose generation); concurrency matches the synthesis fan-out.
[roles.skill_synthesizer]
model_id        = "moonshotai.kimi-k2.5"
region          = "us-east-1"
max_tokens      = 2048
max_concurrency = 5
sweep_candidates = [
  "qwen.qwen3-32b-v1:0",
  "openai.gpt-oss-120b-1:0",
  "minimax.minimax-m2.5",
  "qwen.qwen3-next-80b-a3b",
  "moonshotai.kimi-k2.5",
]
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run --package model-adapter pytest -k skill_roles_are_registered -v`
Expected: PASS (2 parametrized cases).

- [ ] **Step 5: Commit**

```bash
git add packages/model-adapter/src/model_adapter/models.toml packages/model-adapter/tests/test_loader.py
git commit -m "feat(model-adapter): register skill_planner + skill_synthesizer roles"
```

---

## Task 7: Create the `skill_planner` system prompt

**Files:**
- Create: `packages/graph-wiki-core/src/graph_wiki_core/prompts/skill_planner.py`
- Test: `packages/graph-wiki-core/tests/unit/test_prompts_skill.py`

- [ ] **Step 1: Write the failing test**

Create `packages/graph-wiki-core/tests/unit/test_prompts_skill.py`:

```python
from graph_wiki_core.prompts.skill_planner import build_skill_planner_system


def test_skill_planner_system_is_nonempty_str():
    s = build_skill_planner_system()
    assert isinstance(s, str) and len(s) > 200


def test_skill_planner_system_mentions_chunking_and_yaml():
    s = build_skill_planner_system().lower()
    assert "guidance" in s
    assert "yaml" in s
    # One page per rule; whole-skill for instructional flows.
    assert "rule" in s
    assert "topic" in s


def test_skill_planner_system_inserts_project_context():
    s = build_skill_planner_system(project_context="PROJECT_CTX_MARKER")
    assert "PROJECT_CTX_MARKER" in s
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_prompts_skill.py -k planner -v`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Create the prompt module**

Create `packages/graph-wiki-core/src/graph_wiki_core/prompts/skill_planner.py`:

```python
"""SKILL_PLANNER_SYSTEM — Pass-1 system prompt for the type-branched ingest skill branch.

The planner reads a full agent skill and emits a YAML list of chunk-plan entries,
one per guidance page to synthesize. It decides chunking from the content: atomic
rules become one page each; a single instructional flow becomes one page.

Exports:
    build_skill_planner_system(project_context: str = "") -> str — assembles the
        planner system prompt. When `project_context` is non-empty it is inserted
        after the role intro.
    SKILL_PLANNER_SYSTEM — backward-compat constant, equals build_skill_planner_system().
"""

from __future__ import annotations

_ROLE_INTRO = (
    "You are a guidance planner. You read a single agent **skill** (behavioral guidance\n"
    "for an AI coding agent) and decide how to break its reusable technical knowledge\n"
    "into one or more **guidance pages** for a code wiki.\n\n"
    "Output ONLY a YAML list. No commentary, no prose outside the YAML, no code fence."
)

_CHUNKING = (
    "## Chunking strategy\n\n"
    "Choose the chunking from the content:\n"
    "- **Rules / atomic directives** (a skill that is a list of independent 'do X' / "
    "'never Y' rules): emit ONE entry per rule.\n"
    "- **How-to / instructional flow** (a single coherent procedure or technique): emit "
    "ONE entry for the whole skill.\n\n"
    "Never split tightly-coupled instructions across multiple entries. When in doubt, "
    "prefer fewer, larger pages over many fragments."
)

_TOPIC = (
    "## Topic\n\n"
    "Infer `topic` from the skill's DOMAIN, not its filename (e.g. a React Native skill "
    "→ `react-native`; a brainstorming skill → `brainstorming`). `topic` is a short "
    "kebab-case slug and becomes the folder under `wiki/guidance/`."
)

_SCHEMA = (
    "## Output schema (YAML list)\n\n"
    "Each entry MUST have these keys:\n"
    "```yaml\n"
    "- title: Use a List Virtualizer for Any List   # human-readable page title\n"
    "  slug: use-list-virtualizer                    # kebab-case; filename stem\n"
    "  topic: react-native                           # domain slug → folder\n"
    "  summary: One-line summary for the wiki spine.\n"
    "  applies_when: Rendering any scrollable list in React Native.\n"
    "  impact: high                                  # critical | high | medium | low\n"
    "  triggers:                                     # all keys optional\n"
    "    globs: ['**/*.tsx']\n"
    "    keywords: [FlatList, ScrollView]\n"
    "    entities: []                                # [[entities/...]] URIs, or []\n"
    "  content: |\n"
    "    Full extracted/paraphrased body for this guidance chunk — everything the\n"
    "    synthesizer needs to write the page WITHOUT re-reading the source.\n"
    "```\n\n"
    "`impact` MUST be one of: critical, high, medium, low (lowercase). Emit `triggers` "
    "with empty lists when you have no signal — do not omit the block. `content` carries "
    "the actual technical substance; make it complete and self-contained."
)

_RULES = (
    "## Rules\n\n"
    "- Treat the source as agent behavioral guidance, not generic documentation.\n"
    "- Extract reusable TECHNICAL knowledge; drop skill-harness scaffolding "
    "(activation phrases, tool-call mechanics, meta-instructions about being a skill).\n"
    "- Begin the response with `- ` (the first YAML list item). No `---`, no code fence."
)


def build_skill_planner_system(project_context: str = "") -> str:
    """Assemble the skill-planner system prompt.

    Args:
        project_context: Optional project-context block; inserted after the role
            intro when non-empty.

    Returns:
        The assembled system prompt string.
    """
    parts = [_ROLE_INTRO, _CHUNKING, _TOPIC, _SCHEMA, _RULES]
    if project_context:
        parts.insert(1, project_context)
    return "\n\n".join(parts)


SKILL_PLANNER_SYSTEM = build_skill_planner_system()
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_prompts_skill.py -k planner -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/prompts/skill_planner.py packages/graph-wiki-core/tests/unit/test_prompts_skill.py
git commit -m "feat(prompts): add skill_planner system prompt"
```

---

## Task 8: Create the `skill_synthesizer` system prompt

**Files:**
- Create: `packages/graph-wiki-core/src/graph_wiki_core/prompts/skill_synthesizer.py`
- Test: `packages/graph-wiki-core/tests/unit/test_prompts_skill.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `packages/graph-wiki-core/tests/unit/test_prompts_skill.py`:

```python
from graph_wiki_core.prompts.skill_synthesizer import build_skill_synthesizer_system


def test_skill_synthesizer_system_is_nonempty_str():
    s = build_skill_synthesizer_system()
    assert isinstance(s, str) and len(s) > 200


def test_skill_synthesizer_system_fixes_category_and_format():
    s = build_skill_synthesizer_system()
    assert "category: guidance" in s
    assert "## Guidance" in s
    assert "## Applies to" in s
    # Must begin with --- (no code fence), mirroring the ingestor contract.
    assert "---" in s


def test_skill_synthesizer_system_inserts_project_context():
    s = build_skill_synthesizer_system(project_context="SYNTH_CTX_MARKER")
    assert "SYNTH_CTX_MARKER" in s
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_prompts_skill.py -k synthesizer -v`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Create the prompt module**

Create `packages/graph-wiki-core/src/graph_wiki_core/prompts/skill_synthesizer.py`:

```python
"""SKILL_SYNTHESIZER_SYSTEM — Pass-2 system prompt for the type-branched ingest skill branch.

Given ONE chunk-plan entry (from the planner), the synthesizer emits ONE complete
guidance page: frontmatter per the guidance-io schema plus a focused `## Guidance`
body and an optional `## Applies to` section.

Exports:
    build_skill_synthesizer_system(project_context: str = "") -> str
    SKILL_SYNTHESIZER_SYSTEM — backward-compat constant.
"""

from __future__ import annotations

_ROLE_INTRO = (
    "You are a guidance-page synthesizer. You receive ONE chunk-plan entry describing a\n"
    "single piece of reusable technical guidance, and you emit ONE complete guidance\n"
    "page for a code wiki.\n\n"
    "Output ONLY the page: YAML frontmatter followed by a markdown body. No commentary."
)

_FRONTMATTER = (
    "## Frontmatter (strict)\n\n"
    "Emit exactly these keys, taking values from the chunk-plan entry:\n"
    "```yaml\n"
    "title: <entry.title>\n"
    "category: guidance          # FIXED — always this literal value\n"
    "summary: <entry.summary>\n"
    "topic: <entry.topic>\n"
    "applies_when: <entry.applies_when>\n"
    "triggers:                   # copy entry.triggers verbatim (globs/keywords/entities)\n"
    "  globs: []\n"
    "  keywords: []\n"
    "  entities: []\n"
    "tags: []                    # optional coarse tags\n"
    "impact: <entry.impact>      # critical | high | medium | low (lowercase)\n"
    "updated: <today's date, YYYY-MM-DD>\n"
    "tokens: 0\n"
    "```\n\n"
    "`category` MUST be the literal `guidance`. `impact` MUST be lowercase and one of "
    "critical/high/medium/low. Keep `topic` and `title` exactly as given so the page "
    "lands at the planned path."
)

_BODY = (
    "## Body\n\n"
    "1. `# <title>`\n"
    "2. `## Guidance` — the prescriptive content: how to do it correctly and why. "
    "Synthesize from `entry.content`. No padding, no restating the title.\n"
    "3. Optional `## Incorrect` / `## Correct` code examples when they sharpen the point.\n"
    "4. `## Applies to` — ONLY when `entry.triggers.entities` is non-empty: one "
    "`- [[entities/...]]` bullet per entity. Omit the section entirely when there are "
    "no entities.\n"
)

_FORMAT = (
    "## Output format (strict)\n\n"
    "Begin the response with `---` on its own line. Do NOT wrap the page in a markdown "
    "code fence of any kind. The first three characters MUST be `---`."
)


def build_skill_synthesizer_system(project_context: str = "") -> str:
    """Assemble the skill-synthesizer system prompt.

    Args:
        project_context: Optional project-context block; inserted after the role
            intro when non-empty.

    Returns:
        The assembled system prompt string.
    """
    parts = [_ROLE_INTRO, _FRONTMATTER, _BODY, _FORMAT]
    if project_context:
        parts.insert(1, project_context)
    return "\n\n".join(parts)


SKILL_SYNTHESIZER_SYSTEM = build_skill_synthesizer_system()
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_prompts_skill.py -v`
Expected: PASS (all 6 prompt tests).

- [ ] **Step 5: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/prompts/skill_synthesizer.py packages/graph-wiki-core/tests/unit/test_prompts_skill.py
git commit -m "feat(prompts): add skill_synthesizer system prompt"
```

---

## Task 9: Extract `_run_common_tail` (faithful refactor, no behavior change)

Pull the shared write/resolve/suggest/index/log/return logic out of `run_ingest_source` into `_run_common_tail`, driven by a `_IngestBranchResult`. `run_ingest_source` builds the branch result inline (default behavior) and calls the tail. **No behavioral change** — the existing ingest suite is the guard.

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py`
- Test: `packages/graph-wiki-core/tests/unit/test_commands_ingest.py` (existing suite is the regression guard)

- [ ] **Step 1: Add the `_IngestBranchResult` dataclass**

In `ingest.py`, after the `IngestResult` dataclass (after line 156), add:

```python
@dataclass
class _IngestBranchResult:
    """Intermediate hand-off from a source-type branch to _run_common_tail.

    Both branches produce a source-page body and the metadata the shared tail
    needs to write + finalize it. The skill branch additionally populates
    guidance_pages_written (written before the tail runs).
    """

    page_body: str
    target_slug: str
    source_type: str
    entity_uri: str | None
    entity_stem: str | None
    frontmatter_parsed: bool
    run_suggest: bool
    allowed_kinds: frozenset[str] | None = None
    guidance_pages_written: list[str] = field(default_factory=list)
```

- [ ] **Step 2: Add the `_run_common_tail` function**

Add `_run_common_tail` near `run_ingest_source` (e.g. just above it). It is the verbatim tail of the current function, parameterized by the branch result:

```python
async def _run_common_tail(
    branch: _IngestBranchResult,
    *,
    wiki: Path,
    conn,
    source_path: Path,
    source_text: str,
    title_guess: str,
) -> IngestResult:
    """Shared finalize path for every ingest branch.

    Writes the source page (stamping source_type/target_slug/entity_uri),
    resolves wikilinks, ensures the entity forward-link, optionally runs the
    suggest phase (gated by branch.run_suggest), updates the index, and logs.
    """
    # Route + write the source page (D1: always under sources/).
    target_path = _route_target_path(wiki, "source", branch.target_slug)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    canonical_slug = target_path.stem

    body = branch.page_body
    # D3 synthesize-frontmatter rule (only when the branch produced no frontmatter).
    if not branch.frontmatter_parsed and not body.lstrip().startswith("---"):
        body = _synthesize_frontmatter_block(body, branch.source_type, canonical_slug, branch.entity_uri)

    body = _rewrite_target_slug_in_body(body, canonical_slug)
    body = _set_entity_uri_in_body(body, branch.entity_uri)
    body = _set_source_type_in_body(body, branch.source_type)
    target_path.write_text(body, encoding="utf-8")

    resolved_output, stripped_wikilinks = _resolve_wikilinks(body, wiki)
    current_output = resolved_output if stripped_wikilinks else body
    if stripped_wikilinks:
        target_path.write_text(resolved_output, encoding="utf-8")

    if branch.entity_stem:
        linked_output = _ensure_entity_touch_link(current_output, branch.entity_stem)
        if linked_output != current_output:
            target_path.write_text(linked_output, encoding="utf-8")

    # Suggest phase (gated). Best-effort: a failure never fails the ingest.
    if branch.run_suggest:
        try:
            graph_tools = build_graph_tools(conn)
            suggested_pages, proposal_status = await run_suggest_phase(
                wiki=wiki,
                page_path=target_path,
                source_path=source_path,
                source_text=source_text,
                entity_uri=branch.entity_uri,
                entity_stem=branch.entity_stem,
                graph_tools=graph_tools,
                allowed_kinds=branch.allowed_kinds,
            )
        except Exception:
            logger.warning("suggest phase failed; continuing without suggestions", exc_info=True)
            suggested_pages = []
            proposal_status = {
                "reasoner": "failed",
                "extractor": "skipped",
                "proposals": 0,
                "error": "suggest phase failed",
            }
        suggestions_parsed = proposal_status["extractor"] == "ok"
        current_text = target_path.read_text(encoding="utf-8")
        stamped_text = _set_proposal_status_in_body(current_text, proposal_status)
        if stamped_text != current_text:
            target_path.write_text(stamped_text, encoding="utf-8")
    else:
        suggested_pages = []
        suggestions_parsed = True
        proposal_status = {"reasoner": "skipped", "extractor": "skipped", "proposals": 0, "error": None}

    update_index(wiki)

    detail = f"source: {source_path}"
    if stripped_wikilinks:
        detail += f"; stripped {len(stripped_wikilinks)} unresolved wikilink(s): {stripped_wikilinks[:5]}"
    append_log(wiki, "ingest", title_guess, detail=detail, silent=True, raise_exception=True)

    page_path_rel = str(target_path.relative_to(wiki))
    return IngestResult(
        status="ok",
        page_path=page_path_rel,
        slug=branch.target_slug,
        title=title_guess,
        page_type="source",
        source_path=str(source_path),
        cross_refs_updated=1,
        entity_uri=branch.entity_uri,
        source_type=branch.source_type,
        stripped_wikilinks=stripped_wikilinks,
        frontmatter_parsed=branch.frontmatter_parsed,
        suggested_pages=suggested_pages,
        suggestions_parsed=suggestions_parsed,
        proposal_reasoner_status=str(proposal_status.get("reasoner", "skipped")),
        proposal_extractor_status=str(proposal_status.get("extractor", "skipped")),
        proposal_error=proposal_status.get("error"),
        guidance_pages_written=branch.guidance_pages_written,
    )
```

- [ ] **Step 3: Rewrite the tail of `run_ingest_source` to build a branch result + call the tail**

In `run_ingest_source`, replace the body **from the start of Step 7 (line 803, the `# Step 7: write page.` comment) through the end of the `try` block's return (line 898)** with: build the `target_slug`/`source_type`/`frontmatter_parsed` exactly as before (Steps 6's results are already computed above), assemble a `_IngestBranchResult`, and delegate:

```python
        # Build the default-branch result and finalize via the shared tail.
        branch = _IngestBranchResult(
            page_body=llm_output,
            target_slug=target_slug,
            source_type=source_type,
            entity_uri=canonical_uri,
            entity_stem=entity_stem,
            frontmatter_parsed=frontmatter_parsed,
            run_suggest=True,
            allowed_kinds=None,
        )
        return await _run_common_tail(
            branch,
            wiki=wiki,
            conn=conn,
            source_path=source_path,
            source_text=text,
            title_guess=title_guess,
        )
```

Leave the `finally: conn.close()` block intact. (Everything from Step 1 through Step 6 — resolve, extract, path-guess, entity lookup, ingestor LLM call, parse, source_type/target_slug determination — stays exactly as-is above this replacement.)

- [ ] **Step 4: Run the full ingest suite (regression — this is the real test)**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_commands_ingest.py -v`
Expected: PASS — every existing test still green. If any fail, the extraction changed behavior; diff against the original tail until green. Do not modify tests to fit the refactor.

- [ ] **Step 5: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py
git commit -m "refactor(ingest): extract _run_common_tail + _IngestBranchResult"
```

---

## Task 10: Extract `_run_default_branch`

Move Steps 4–6 (build prompt, ingestor LLM call + trace, parse, source_type/target_slug determination) out of `run_ingest_source` into `_run_default_branch`, returning a `_IngestBranchResult`. `run_ingest_source` keeps Steps 1–3 (setup, extract, path-guess, entity lookup), then dispatches. Still no behavior change.

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py`
- Test: `packages/graph-wiki-core/tests/unit/test_commands_ingest.py` (regression guard)

- [ ] **Step 1: Add `_run_default_branch`**

Add the function (above `run_ingest_source`). It takes the already-computed setup values and returns a `_IngestBranchResult` with `run_suggest=True`:

```python
async def _run_default_branch(
    *,
    text: str,
    title_guess: str,
    slug: str,
    source_path: Path,
    path_guess: str,
    wiki: Path,
    project_ctx: str,
    canonical_uri: str | None,
    entity_stem: str | None,
    model_override: str | None,
) -> _IngestBranchResult:
    """The default ingest path: one ingestor LLM call → a Source page body."""
    vault_structure: list[str] = []
    try:
        vault_structure = sorted(d.name for d in wiki.iterdir() if d.is_dir() and not d.name.startswith("."))
    except OSError:
        pass

    prompt = build_ingest_source_prompt(text, source_path, path_guess, vault_structure)

    ingestor_cfg = load_role_config("ingestor")
    llm = make_llm("ingestor", model_override=model_override)
    resolved_model_id = model_override or ingestor_cfg["model_id"]
    trace_dir = graph_dir(wiki.parent) / "traces"
    trace_dir.mkdir(parents=True, exist_ok=True)
    trace_file = trace_dir / f"ingest_{int(time.time())}_{uuid.uuid4().hex[:8]}.jsonl"
    t0 = time.monotonic()
    try:
        resp = await llm.ainvoke(
            [SystemMessage(build_ingestor_system(project_context=project_ctx)), HumanMessage(prompt)]
        )
    except Exception as exc:
        latency_ms = int((time.monotonic() - t0) * 1000)
        write_trace_record(
            trace_file,
            role="ingestor",
            model_id=resolved_model_id,
            item=str(source_path),
            status="error",
            latency_ms=latency_ms,
            response=None,
            error=str(exc),
        )
        raise
    latency_ms = int((time.monotonic() - t0) * 1000)
    write_trace_record(
        trace_file,
        role="ingestor",
        model_id=resolved_model_id,
        item=str(source_path),
        status="success",
        latency_ms=latency_ms,
        response=resp,
    )
    if not isinstance(resp.content, str):
        raise RuntimeError("ingestor returned non-text content")
    llm_output = resp.content

    fm, _body = _parse_ingestor_response(llm_output)
    frontmatter_parsed = bool(fm)
    if path_guess in RAW_FOLDER_TYPES:
        source_type = path_guess
    else:
        llm_value = str(fm.get("source_type", "")).strip().lower()
        source_type = llm_value if llm_value in SOURCE_TYPE_ENUM else path_guess

    target_slug = str(fm.get("target_slug", "")).strip()
    target_slug = slugify(target_slug) if target_slug else slug

    return _IngestBranchResult(
        page_body=llm_output,
        target_slug=target_slug,
        source_type=source_type,
        entity_uri=canonical_uri,
        entity_stem=entity_stem,
        frontmatter_parsed=frontmatter_parsed,
        run_suggest=True,
        allowed_kinds=None,
    )
```

- [ ] **Step 2: Replace Steps 4–6 + the inline branch-result build in `run_ingest_source` with a dispatch**

In `run_ingest_source`, after the entity-lookup block (after `entity_stem` is computed, line 732), replace everything down to the `return await _run_common_tail(...)` added in Task 9 with:

```python
        # Dispatch on the path-guessed source_type. raw/skill/ → the skill branch
        # (writes guidance pages directly); everything else → the default branch.
        branch = await _run_default_branch(
            text=text,
            title_guess=title_guess,
            slug=slug,
            source_path=source_path,
            path_guess=path_guess,
            wiki=wiki,
            project_ctx=project_ctx,
            canonical_uri=canonical_uri,
            entity_stem=entity_stem,
            model_override=model_override,
        )
        return await _run_common_tail(
            branch,
            wiki=wiki,
            conn=conn,
            source_path=source_path,
            source_text=text,
            title_guess=title_guess,
        )
```

(The skill dispatch line is added in Task 12. The local variables `vault_structure`, `prompt`, `llm`, `resp`, `llm_output`, `fm`, `source_type`, `target_slug`, etc. that previously lived inline in `run_ingest_source` now live in `_run_default_branch` — remove them from `run_ingest_source`.)

- [ ] **Step 3: Run the full ingest suite (regression)**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_commands_ingest.py -v`
Expected: PASS — all existing tests still green.

- [ ] **Step 4: Run ruff on the changed file**

Run: `uv run ruff check packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py`
Expected: no NEW errors introduced (the file may have pre-existing findings; do not fix unrelated ones — match surrounding style).

- [ ] **Step 5: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py
git commit -m "refactor(ingest): extract _run_default_branch behind a dispatch"
```

---

## Task 11: Skill-branch helpers — plan parsing, synthesis fan-out, source-body composition

Pure-ish helpers the skill branch composes. Built and tested before the branch is wired so the LLM-touching seam (`make_llm` by role) is the only thing the integration test mocks.

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py`
- Test: `packages/graph-wiki-core/tests/unit/test_commands_ingest.py`

- [ ] **Step 1: Add imports for the skill branch**

At the top of `ingest.py`, add (grouped with the other third-party/workspace imports):

```python
from guidance_io.frontmatter import parse as parse_guidance_fm
from guidance_io.frontmatter import validate as validate_guidance_fm
from guidance_io.paths import page_path as guidance_page_path
from guidance_io.paths import slugify as guidance_slugify
from subagent_runtime.pool import SubagentPool, TaskResult
```

And with the prompt imports (near line 59):

```python
from graph_wiki_core.prompts.skill_planner import build_skill_planner_system
from graph_wiki_core.prompts.skill_synthesizer import build_skill_synthesizer_system
```

- [ ] **Step 2: Write failing tests for the helpers**

Add to `packages/graph-wiki-core/tests/unit/test_commands_ingest.py`:

```python
def test_parse_skill_plan_reads_yaml_list():
    from graph_wiki_core.commands.ingest import _parse_skill_plan

    text = (
        "- title: Use a Virtualizer\n"
        "  slug: use-virtualizer\n"
        "  topic: react-native\n"
        "  content: |\n"
        "    Use a virtualizer.\n"
    )
    plan = _parse_skill_plan(text)
    assert isinstance(plan, list)
    assert plan[0]["topic"] == "react-native"
    assert plan[0]["slug"] == "use-virtualizer"


def test_parse_skill_plan_strips_code_fence():
    from graph_wiki_core.commands.ingest import _parse_skill_plan

    text = "```yaml\n- title: A\n  topic: t\n  content: body\n```\n"
    plan = _parse_skill_plan(text)
    assert plan and plan[0]["title"] == "A"


def test_parse_skill_plan_returns_none_on_garbage():
    from graph_wiki_core.commands.ingest import _parse_skill_plan

    assert _parse_skill_plan("not yaml: [unclosed") is None
    assert _parse_skill_plan("title: not-a-list") is None  # mapping, not a list
    assert _parse_skill_plan("") is None


def test_guidance_wikilink_target_from_relpath():
    from graph_wiki_core.commands.ingest import _guidance_wikilink_target

    assert _guidance_wikilink_target("wiki/guidance/react-native/use-virtualizer.md") == (
        "guidance/react-native/use-virtualizer"
    )


def test_compose_skill_source_body_lists_generates():
    from graph_wiki_core.commands.ingest import _compose_skill_source_body

    body = _compose_skill_source_body(
        title="React Native Skill",
        written_rel_paths=[
            "wiki/guidance/react-native/use-virtualizer.md",
            "wiki/guidance/react-native/avoid-inline-styles.md",
        ],
    )
    assert body.lstrip().startswith("---")
    assert "## Generates" in body
    assert "[[guidance/react-native/use-virtualizer]]" in body
    assert "[[guidance/react-native/avoid-inline-styles]]" in body
```

- [ ] **Step 3: Run to verify failure**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_commands_ingest.py -k "skill_plan or guidance_wikilink or compose_skill" -v`
Expected: FAIL — helpers do not exist.

- [ ] **Step 4: Implement the helpers**

Add to `ingest.py` (near the other private helpers, e.g. after `build_ingest_source_prompt`):

```python
# Required keys a planner chunk-plan entry must carry to be usable.
_SKILL_PLAN_REQUIRED = ("title", "topic", "content")


def _parse_skill_plan(text: str) -> list[dict] | None:
    """Parse the planner response (a YAML list of chunk entries).

    Strips a leading ```yaml / ``` code fence defensively (same failure mode as
    the ingestor). Returns None when the text is empty, not valid YAML, not a
    list, or contains no usable entry (each usable entry has title/topic/content).
    """
    if not text or not text.strip():
        return None
    stripped = text.strip()
    if stripped.startswith("```"):
        nl = stripped.find("\n")
        if nl == -1:
            return None
        stripped = stripped[nl + 1 :]
        fence = stripped.rfind("```")
        if fence != -1:
            stripped = stripped[:fence]
        stripped = stripped.strip()
    try:
        loaded = yaml.safe_load(stripped)
    except yaml.YAMLError:
        return None
    if not isinstance(loaded, list):
        return None
    entries = [e for e in loaded if isinstance(e, dict) and all(e.get(k) for k in _SKILL_PLAN_REQUIRED)]
    return entries or None


def _guidance_wikilink_target(rel_path: str) -> str:
    """Turn a workspace-relative guidance path into a wikilink target.

    `wiki/guidance/<topic>/<slug>.md` -> `guidance/<topic>/<slug>`.
    """
    t = rel_path
    if t.startswith("wiki/"):
        t = t[len("wiki/") :]
    if t.endswith(".md"):
        t = t[: -len(".md")]
    return t


def _compose_skill_source_body(title: str, written_rel_paths: list[str]) -> str:
    """Build the Source page body for a skill ingest.

    Minimal frontmatter (title only — source_type/target_slug/entity_uri are
    stamped by the common tail) plus a `## Generates` section linking every
    guidance page the skill produced. Provenance: skill → guidance.
    """
    lines = [f"- [[{_guidance_wikilink_target(p)}]]" for p in written_rel_paths]
    generates = "\n".join(lines) if lines else "_No guidance pages were generated._"
    return (
        f"---\ntitle: {title}\n---\n\n"
        f"# {title}\n\n"
        f"## Summary\n"
        f"Agent skill ingested. Reusable guidance was synthesized into "
        f"{len(written_rel_paths)} guidance page(s) under `wiki/guidance/`.\n\n"
        f"## Generates\n{generates}\n"
    )
```

- [ ] **Step 5: Run to verify pass**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_commands_ingest.py -k "skill_plan or guidance_wikilink or compose_skill" -v`
Expected: PASS (5 tests).

- [ ] **Step 6: Write the failing synthesis-fan-out test**

The synthesis helper calls `make_llm("skill_synthesizer")` per chunk via `SubagentPool`, validates each result, and writes guidance pages. Add:

```python
async def test_synthesize_guidance_pages_writes_validated_pages(tmp_path, monkeypatch):
    from graph_wiki_core.commands import ingest as ingest_mod

    workspace_root = tmp_path
    (workspace_root / "wiki").mkdir()

    valid_page = (
        "---\ntitle: Use a Virtualizer\ncategory: guidance\ntopic: react-native\n"
        "summary: s\napplies_when: a\nimpact: high\nupdated: 2026-06-08\ntokens: 0\n---\n\n"
        "## Guidance\nUse a virtualizer.\n"
    )

    class _FakeLLM:
        async def ainvoke(self, messages):
            class _R:
                content = valid_page
                usage_metadata = None

            return _R()

    monkeypatch.setattr(ingest_mod, "make_llm", lambda role, model_override=None: _FakeLLM())

    plan = [
        {"title": "Use a Virtualizer", "slug": "use-virtualizer", "topic": "react-native", "content": "x"},
    ]
    written = await ingest_mod._synthesize_guidance_pages(
        plan,
        workspace_root=workspace_root,
        project_ctx="",
        model_override=None,
    )
    assert written == ["wiki/guidance/react-native/use-virtualizer.md"]
    page = (workspace_root / "wiki" / "guidance" / "react-native" / "use-virtualizer.md")
    assert page.is_file()
    assert "## Guidance" in page.read_text(encoding="utf-8")


async def test_synthesize_guidance_pages_skips_invalid(tmp_path, monkeypatch):
    from graph_wiki_core.commands import ingest as ingest_mod

    workspace_root = tmp_path
    (workspace_root / "wiki").mkdir()

    class _FakeLLM:
        async def ainvoke(self, messages):
            class _R:
                content = "this is not a guidance page"
                usage_metadata = None

            return _R()

    monkeypatch.setattr(ingest_mod, "make_llm", lambda role, model_override=None: _FakeLLM())

    plan = [{"title": "Bad", "slug": "bad", "topic": "t", "content": "x"}]
    written = await ingest_mod._synthesize_guidance_pages(
        plan, workspace_root=workspace_root, project_ctx="", model_override=None
    )
    assert written == []
```

- [ ] **Step 7: Run to verify failure**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_commands_ingest.py -k synthesize_guidance -v`
Expected: FAIL — `_synthesize_guidance_pages` does not exist.

- [ ] **Step 8: Implement `_synthesize_guidance_pages`**

Add to `ingest.py`:

```python
def _build_skill_synth_human(entry: dict) -> str:
    """Human message for one synthesizer call: the chunk-plan entry as YAML."""
    return "Chunk plan entry:\n```yaml\n" + yaml.safe_dump(entry, sort_keys=False, allow_unicode=True) + "```\n"


async def _synthesize_guidance_pages(
    plan: list[dict],
    *,
    workspace_root: Path,
    project_ctx: str,
    model_override: str | None,
) -> list[str]:
    """Pass 2: synthesize + write one guidance page per plan entry.

    Fans out one skill_synthesizer call per entry via SubagentPool. Each result
    is parsed + validated against the guidance-io schema; valid pages are written
    to wiki/guidance/<topic>/<slug>.md (overwriting on re-ingest). Invalid or
    failed chunks are logged and skipped (best-effort — a bad chunk never fails
    the ingest). The on-disk path is derived from the planner entry's topic/slug
    (NOT the synthesizer's frontmatter), so the path is deterministic.

    Returns workspace-relative paths of the pages written, in plan order.
    """
    synth_cfg = load_role_config("skill_synthesizer")
    system = build_skill_synthesizer_system(project_context=project_ctx)

    async def synth_one(entry: dict) -> TaskResult:
        llm = make_llm("skill_synthesizer", model_override=model_override)
        resp = await llm.ainvoke([SystemMessage(system), HumanMessage(_build_skill_synth_human(entry))])
        content = resp.content if isinstance(resp.content, str) else ""
        return TaskResult(value=content, response=resp)

    pool = SubagentPool(trace_dir=graph_dir(workspace_root) / "traces")
    fan = await pool.run_all(
        items=list(plan),
        task=synth_one,
        role="skill_synthesizer",
        model_id=synth_cfg["model_id"],
        max_concurrency=int(synth_cfg.get("max_concurrency", 5)),
    )

    # Map entries to their synthesized text (only successes).
    by_id = {id(entry): page_text for entry, page_text in fan.successes}

    written: list[str] = []
    for entry in plan:  # preserve plan order, not fan-out completion order
        page_text = by_id.get(id(entry))
        if not page_text:
            continue
        try:
            fm, _body = parse_guidance_fm(page_text)
        except ValueError:
            logger.warning("skill synthesizer produced unparseable guidance page; skipping chunk %r", entry.get("title"))
            continue
        errors = validate_guidance_fm(fm)
        if errors:
            logger.warning("skill guidance page failed validation (%s); skipping chunk %r", errors, entry.get("title"))
            continue
        topic = guidance_slugify(str(entry["topic"]))
        slug = guidance_slugify(str(entry.get("slug") or entry["title"]))
        page = guidance_page_path(workspace_root, topic, slug)
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text(page_text, encoding="utf-8")
        written.append(page.relative_to(workspace_root).as_posix())
    return written
```

- [ ] **Step 9: Run to verify pass**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_commands_ingest.py -k synthesize_guidance -v`
Expected: PASS (2 tests).

- [ ] **Step 10: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py packages/graph-wiki-core/tests/unit/test_commands_ingest.py
git commit -m "feat(ingest): skill-branch helpers (plan parse, synthesis fan-out, source body)"
```

---

## Task 12: Implement `_run_skill_branch` and wire the dispatcher

Tie the helpers together: planner call → parse → synthesize+write guidance → compose source body. Wire the dispatch in `run_ingest_source` and the planner-failure fallback to the default branch.

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py`
- Test: `packages/graph-wiki-core/tests/unit/test_commands_ingest.py`

- [ ] **Step 1: Implement `_run_skill_branch`**

Add to `ingest.py`:

```python
def _build_skill_planner_human(text: str, source_path: Path) -> str:
    """Human message for the planner: the full skill text + its path."""
    return f"Skill file: {source_path}\n\n--- Skill content ---\n{text}\n--- End skill ---\n"


async def _run_skill_branch(
    *,
    text: str,
    title_guess: str,
    slug: str,
    source_path: Path,
    workspace_root: Path,
    wiki: Path,
    project_ctx: str,
    canonical_uri: str | None,
    entity_stem: str | None,
    model_override: str | None,
) -> _IngestBranchResult | None:
    """Two-pass skill ingest. Returns None to signal fall-back to the default branch.

    Pass 1 (planner): one skill_planner call → a YAML chunk plan.
    Pass 2 (synthesizer): SubagentPool fan-out → written guidance pages.
    The Source page body lists the generated pages under `## Generates`.
    On planner failure / unparseable plan, returns None (caller falls back).
    """
    planner_cfg = load_role_config("skill_planner")
    llm = make_llm("skill_planner", model_override=model_override)
    resolved_model_id = model_override or planner_cfg["model_id"]
    trace_dir = graph_dir(wiki.parent) / "traces"
    trace_dir.mkdir(parents=True, exist_ok=True)
    trace_file = trace_dir / f"ingest_skill_{int(time.time())}_{uuid.uuid4().hex[:8]}.jsonl"
    t0 = time.monotonic()
    try:
        resp = await llm.ainvoke(
            [SystemMessage(build_skill_planner_system(project_context=project_ctx)), HumanMessage(_build_skill_planner_human(text, source_path))]
        )
    except Exception as exc:
        latency_ms = int((time.monotonic() - t0) * 1000)
        write_trace_record(
            trace_file, role="skill_planner", model_id=resolved_model_id,
            item=str(source_path), status="error", latency_ms=latency_ms, response=None, error=str(exc),
        )
        logger.warning("skill planner call failed; falling back to default ingest branch", exc_info=True)
        return None
    latency_ms = int((time.monotonic() - t0) * 1000)
    write_trace_record(
        trace_file, role="skill_planner", model_id=resolved_model_id,
        item=str(source_path), status="success", latency_ms=latency_ms, response=resp,
    )

    plan_text = resp.content if isinstance(resp.content, str) else ""
    plan = _parse_skill_plan(plan_text)
    if plan is None:
        logger.warning("skill planner produced no usable chunk plan; falling back to default ingest branch")
        return None

    written = await _synthesize_guidance_pages(
        plan, workspace_root=workspace_root, project_ctx=project_ctx, model_override=model_override
    )

    page_body = _compose_skill_source_body(title_guess, written)
    return _IngestBranchResult(
        page_body=page_body,
        target_slug=slug,
        source_type="skill",
        entity_uri=canonical_uri,
        entity_stem=entity_stem,
        frontmatter_parsed=True,
        run_suggest=False,  # guidance written directly — nothing to propose
        guidance_pages_written=written,
    )
```

- [ ] **Step 2: Wire the dispatch in `run_ingest_source`**

In `run_ingest_source`, replace the `branch = await _run_default_branch(...)` line (added in Task 10) with the dispatch:

```python
        # Dispatch on the path-guessed source_type. raw/skill/ → the skill branch
        # (writes guidance pages directly); everything else → the default branch.
        branch: _IngestBranchResult | None = None
        if path_guess == "skill":
            branch = await _run_skill_branch(
                text=text,
                title_guess=title_guess,
                slug=slug,
                source_path=source_path,
                workspace_root=workspace_root,
                wiki=wiki,
                project_ctx=project_ctx,
                canonical_uri=canonical_uri,
                entity_stem=entity_stem,
                model_override=model_override,
            )
        if branch is None:
            branch = await _run_default_branch(
                text=text,
                title_guess=title_guess,
                slug=slug,
                source_path=source_path,
                path_guess=path_guess,
                wiki=wiki,
                project_ctx=project_ctx,
                canonical_uri=canonical_uri,
                entity_stem=entity_stem,
                model_override=model_override,
            )
        return await _run_common_tail(
            branch,
            wiki=wiki,
            conn=conn,
            source_path=source_path,
            source_text=text,
            title_guess=title_guess,
        )
```

(`workspace_root` is already computed at line 686.)

- [ ] **Step 3: Write the failing end-to-end skill-branch test**

Add to `packages/graph-wiki-core/tests/unit/test_commands_ingest.py`. This is a true unit test — it mocks the graph conn + entity lookups and routes `make_llm` by role, so no real DB or Bedrock is needed:

```python
async def test_run_ingest_source_skill_writes_guidance_and_skips_suggest(tmp_path, monkeypatch):
    from graph_wiki_core.commands import ingest as ingest_mod

    # --- workspace layout: <ws>/raw/skill/<file>, <ws>/wiki/ ---
    ws = tmp_path
    (ws / "wiki").mkdir()
    skill_dir = ws / "raw" / "skill"
    skill_dir.mkdir(parents=True)
    skill_file = skill_dir / "react-native.md"
    skill_file.write_text("# RN Skill\nAlways use a virtualizer for lists.\n", encoding="utf-8")

    # resolve_wiki_and_repo -> (wiki, repo); point both into the tmp workspace.
    monkeypatch.setattr(
        ingest_mod, "resolve_wiki_and_repo", lambda wp: (ws / "wiki", ws)
    )
    monkeypatch.setattr(ingest_mod, "render_project_context", lambda wiki: "")

    # Graph conn + entity lookups: no graph, no match.
    class _Conn:
        def close(self):
            pass

    monkeypatch.setattr(ingest_mod, "read_only_connect", lambda db: _Conn())
    monkeypatch.setattr(ingest_mod, "lookup_entity_by_path", lambda conn, repo, sp: None)
    monkeypatch.setattr(ingest_mod, "lookup_entity_by_name", lambda conn, name: None)

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

    result = await ingest_mod.run_ingest_source(skill_file, workspace_path=ws)

    # Source page filed under sources/, source_type skill.
    assert result.source_type == "skill"
    assert result.page_type == "source"
    # Guidance page written (workspace-relative path).
    assert result.guidance_pages_written == ["wiki/guidance/react-native/use-virtualizer.md"]
    assert (ws / "wiki" / "guidance" / "react-native" / "use-virtualizer.md").is_file()
    # Suggest phase skipped.
    assert result.suggested_pages == []
    assert result.proposal_reasoner_status == "skipped"
    # Source page lists the generated page under ## Generates (link resolved, not stripped).
    src = (ws / "wiki" / result.page_path).read_text(encoding="utf-8")
    assert "## Generates" in src
    assert "[[guidance/react-native/use-virtualizer]]" in src
    assert result.stripped_wikilinks == []


async def test_run_ingest_source_skill_falls_back_when_plan_unparseable(tmp_path, monkeypatch):
    from graph_wiki_core.commands import ingest as ingest_mod

    ws = tmp_path
    (ws / "wiki").mkdir()
    skill_dir = ws / "raw" / "skill"
    skill_dir.mkdir(parents=True)
    skill_file = skill_dir / "x.md"
    skill_file.write_text("# X\nbody\n", encoding="utf-8")

    monkeypatch.setattr(ingest_mod, "resolve_wiki_and_repo", lambda wp: (ws / "wiki", ws))
    monkeypatch.setattr(ingest_mod, "render_project_context", lambda wiki: "")

    class _Conn:
        def close(self):
            pass

    monkeypatch.setattr(ingest_mod, "read_only_connect", lambda db: _Conn())
    monkeypatch.setattr(ingest_mod, "lookup_entity_by_path", lambda conn, repo, sp: None)
    monkeypatch.setattr(ingest_mod, "lookup_entity_by_name", lambda conn, name: None)
    # Default branch's suggest phase: stub it out so no graph tools are needed.
    monkeypatch.setattr(ingest_mod, "build_graph_tools", lambda conn: [])

    async def _fake_suggest(**kwargs):
        return [], {"reasoner": "skipped", "extractor": "skipped", "proposals": 0, "error": None}

    monkeypatch.setattr(ingest_mod, "run_suggest_phase", _fake_suggest)

    def _fake_make_llm(role, model_override=None):
        # Planner returns garbage (not a YAML list) → branch returns None → fallback.
        out = "title: not-a-list" if role == "skill_planner" else (
            "---\nsource_type: skill\ntarget_slug: x\n---\n\n## Summary\nFallback source page.\n"
        )

        class _LLM:
            async def ainvoke(self, messages):
                class _R:
                    content = out
                    usage_metadata = None

                return _R()

        return _LLM()

    monkeypatch.setattr(ingest_mod, "make_llm", _fake_make_llm)

    result = await ingest_mod.run_ingest_source(skill_file, workspace_path=ws)

    # Fell back to default branch: a Source page, no guidance pages.
    assert result.guidance_pages_written == []
    assert result.page_type == "source"
    # raw/skill/ is authoritative for source_type even on the default branch.
    assert result.source_type == "skill"
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_commands_ingest.py -k "skill_writes_guidance or falls_back_when_plan" -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Run the full ingest suite (regression)**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_commands_ingest.py -v`
Expected: PASS — all tests (existing default-path + new skill-path) green.

- [ ] **Step 6: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py packages/graph-wiki-core/tests/unit/test_commands_ingest.py
git commit -m "feat(ingest): skill branch — two-pass guidance synthesis + dispatcher"
```

---

## Task 13: Full-suite verification across affected packages

**Files:** none (verification only)

- [ ] **Step 1: Run every affected package's suite**

Run each (non-integration; integration/eval are skipped by default):

```bash
uv run --package wiki-io pytest
uv run --package guidance-io pytest
uv run --package model-adapter pytest
uv run --package graph-wiki-core pytest -m "not integration"
uv run --package graph-wiki-cli pytest -m "not integration"
uv run --package graph-wiki-mcp pytest -m "not integration"
```

Expected: all PASS.

- [ ] **Step 2: Lint + format check the changed files**

Run: `uv run ruff check packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py packages/graph-wiki-core/src/graph_wiki_core/prompts/skill_planner.py packages/graph-wiki-core/src/graph_wiki_core/prompts/skill_synthesizer.py packages/wiki-io/src/wiki_io/ingest_source.py packages/wiki-io/src/wiki_io/backlink_index.py`
Expected: no NEW findings. (Per the repo's known ruff state, do not run `ruff format` to fix unrelated pre-existing dirtiness — match surrounding style by hand.)

- [ ] **Step 3: Final commit (if any lint fixes were needed)**

```bash
git add -A
git commit -m "chore(ingest): lint pass for type-branched ingest"
```

---

## Self-Review (completed against the spec)

**Spec coverage:**
- Dispatcher (`run_ingest_source` → branch → common tail) — Tasks 9, 10, 12. ✓
- `_IngestBranchResult` intermediate — Task 9. ✓
- `IngestResult.guidance_pages_written` (+ CLI/MCP) — Task 4. ✓
- `SOURCE_TYPE_ENUM` / `RAW_FOLDER_TYPES` + `skill` — Task 2 (plus the `guess_source_type` clause the spec omitted). ✓
- Pass 1 planner (role, chunk-plan YAML, topic inference) — Tasks 6, 7, 12. ✓
- Pass 2 synthesizer (role, per-chunk LLM, SubagentPool, validate, overwrite) — Tasks 6, 8, 11. ✓
- Planner-failure fallback to default branch — Task 12 (returns `None`). ✓
- `## Generates` provenance section on the Source page — Task 11 (`_compose_skill_source_body`). ✓
- Three prompt files — Tasks 7, 8 (ingestor unchanged). ✓
- Suggestion phase skipped for skill; `allowed_kinds` param for future branches — Tasks 5, 12. ✓
- Default branch extracted unmodified — Task 10. ✓
- Backlink wiring (decided in-scope) — Task 3. ✓

**Placeholder scan:** No TBD/TODO/"add error handling"/"similar to Task N" — every code step carries full code. ✓

**Type consistency:** `_IngestBranchResult` field names and `_run_common_tail` / `_run_default_branch` / `_run_skill_branch` / `_synthesize_guidance_pages` / `_parse_skill_plan` / `_compose_skill_source_body` / `_guidance_wikilink_target` signatures are consistent across Tasks 9–12. Role names `skill_planner` / `skill_synthesizer` match between models.toml (Task 6), prompts (Tasks 7–8), and call sites (Tasks 11–12). ✓
