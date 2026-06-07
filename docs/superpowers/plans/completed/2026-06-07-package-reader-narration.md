# Package-Reader Narration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the tool-grounded `package_reader` author the `## Narrative` for the four entity kinds it already reads (`package`, `app`, `agent_plugin`, `test_suite`), so those narratives stop hallucinating dependencies; harden the narrator's prompt against invention for the kinds it still owns (`repository`, `domain`, `dependency`).

**Architecture:** Today the blind `narrator` role (kimi-k2.5, graph-relations only) writes `## Narrative` for *all* kinds — and because the graph carries **zero `depends_on` edges**, it confabulates dependencies. The tool-using `package_reader` role (gpt-oss-120b, reads `pyproject.toml` + source) already runs after the narrator over those four kinds and produces faithful `## Purpose`/`## Public API`. This plan adds an **optional `narrative` output** to `package_reader` and has the scan pass `inject_narrative()` it (overwriting the narrator's first pass) for narrated reader-kind pages — "option B" (post-correct), the minimal change that leaves the Living-Wiki commit-gate intact. The narrator is unchanged except for a Phase-2 anti-invention guardrail.

**Tech Stack:** Python 3.11, `uv` workspace, pytest (per-package `testpaths`), langchain-core message/tool primitives, Bedrock Converse via `model_adapter`.

**Ownership note (read `.claude/rules/backward-compatibility.md` first):** `## Narrative` is a **scanner-owned** section written via `inject_narrative`; `## Purpose`/`## Public API` are **human-owned**. `package_reader` already writes human sections via `replace_todo_human_sections`. This plan additionally lets it write the scanner-owned narrative — the anchor-stamp seam (`scan.py:1494`) already unions `package_reader_filled_uris`, so a narrative-injected page is stamped correctly with no gate change.

**Scope guard — this branch also has in-flight integration-test work.** All Phase-1/2 *test* edits are **unit** tests under `packages/graph-wiki-core/tests/unit/`. The only shared production file is `scan.py` (Task 4, Task 7). Do this work in an isolated worktree (`superpowers:using-git-worktrees`) and rebase/merge `scan.py` carefully; see "Merge-overlap watch" at the foot of the plan.

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `packages/graph-wiki-core/src/graph_wiki_core/prompts/package_reader.py` | package_reader system prompt | Add optional `narrative` output rule |
| `packages/graph-wiki-core/src/graph_wiki_core/commands/package_reader.py` | reader item/result/parse/prompt/run | Add `narrative` field end-to-end; conditional prompt line |
| `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py` | scan orchestration | Thread `narrative_uris` into the reader pass; `inject_narrative` for narrated reader pages; Phase-2 narrator guardrail |
| `packages/graph-wiki-core/tests/unit/test_package_reader.py` | reader unit tests | New tests for narrative parse/prompt/run |
| `packages/graph-wiki-core/tests/unit/test_scan_narration.py` (new) | scan-pass unit test | Reader-narrative injection wiring |
| `packages/graph-wiki-core/tests/unit/test_scan_narrate.py` (existing) | narrator prompt tests | Phase-2 guardrail assertion |

---

## Phase 1 — package_reader authors the narrative

### Task 1: `narrative` field through the parse layer

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/package_reader.py:44-115`
- Test: `packages/graph-wiki-core/tests/unit/test_package_reader.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/unit/test_package_reader.py`:

```python
def test_parse_package_reader_output_extracts_narrative():
    from graph_wiki_core.commands.package_reader import _parse_package_reader_output

    raw = '{"sections": [], "narrative": "Reads the vault. Depends on `pkg:foo`."}'
    result = _parse_package_reader_output(raw, requested_headings=[])

    assert result.error is None
    assert result.narrative == "Reads the vault. Depends on `pkg:foo`."


def test_parse_package_reader_output_drops_todo_like_narrative():
    from graph_wiki_core.commands.package_reader import _parse_package_reader_output

    raw = '{"sections": [], "narrative": "TODO — describe this package."}'
    result = _parse_package_reader_output(raw, requested_headings=[])

    assert result.narrative == ""


def test_parse_package_reader_output_narrative_absent_defaults_empty():
    from graph_wiki_core.commands.package_reader import _parse_package_reader_output

    raw = '{"sections": []}'
    result = _parse_package_reader_output(raw, requested_headings=[])

    assert result.narrative == ""
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd packages/graph-wiki-core && uv run pytest tests/unit/test_package_reader.py -k narrative -v`
Expected: FAIL — `_PackageReaderParseResult` has no attribute `narrative`.

- [ ] **Step 3: Implement**

In `package_reader.py`, add the field to the parse dataclass (line ~51):

```python
@dataclass(frozen=True)
class _PackageReaderParseResult:
    replacements: dict[str, str]
    narrative: str = ""
    error: str | None = None
```

At the end of `_parse_package_reader_output` (replace the final `return`):

```python
    narrative_raw = payload.get("narrative", "")
    narrative = narrative_raw.strip() if isinstance(narrative_raw, str) else ""
    if narrative and is_todo_like_body(narrative):
        narrative = ""
    return _PackageReaderParseResult(replacements=parsed, narrative=narrative, error=None)
```

(`is_todo_like_body` is already imported at line 11. The early error-path returns keep `replacements={}` and now default `narrative=""` — no change needed there.)

- [ ] **Step 4: Run to verify it passes**

Run: `cd packages/graph-wiki-core && uv run pytest tests/unit/test_package_reader.py -k narrative -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/package_reader.py packages/graph-wiki-core/tests/unit/test_package_reader.py
git commit -m "feat: parse optional narrative from package_reader output"
```

---

### Task 2: Surface `narrative` on `PackageReaderResult` + `run_package_reader`

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/package_reader.py:44-48, 212-241`
- Test: `packages/graph-wiki-core/tests/unit/test_package_reader.py`

- [ ] **Step 1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_run_package_reader_returns_narrative(tmp_path):
    from graph_wiki_core.commands import package_reader as pr_mod
    from graph_wiki_core.commands.package_reader import PackageReaderItem, run_package_reader

    item = PackageReaderItem(
        uri="pkg:org/repo/pkg-a", kind="package", name="pkg-a", graph_path="packages/pkg-a",
        language="python", frontmatter={}, page_content="# pkg-a\n", requested_sections={},
        narrative="", file_map="", graph_context="", entity_root="packages/pkg-a",
        narrative_requested=True,
    )

    async def fake_loop(**kwargs):
        from graph_wiki_core.agent_loop import ToolLoopResult
        return ToolLoopResult(status="ok", final_text='{"sections": [], "narrative": "Owns vault IO."}', error=None)

    pr_mod.run_tool_loop = fake_loop  # type: ignore[assignment]
    result = await run_package_reader(llm=object(), item=item, repo=tmp_path, wiki=tmp_path, graph_tools=[])

    assert result.narrative == "Owns vault IO."
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd packages/graph-wiki-core && uv run pytest tests/unit/test_package_reader.py::test_run_package_reader_returns_narrative -v`
Expected: FAIL — `PackageReaderItem` has no `narrative_requested` / `PackageReaderResult` has no `narrative`.

- [ ] **Step 3: Implement**

Add the field to `PackageReaderItem` (after `entity_root`, line ~41):

```python
    entity_root: str
    narrative_requested: bool = False
```

Add the field to `PackageReaderResult` (line ~44):

```python
@dataclass(frozen=True)
class PackageReaderResult:
    status: str
    replacements: dict[str, str]
    narrative: str = ""
    error: str | None = None
```

In `run_package_reader`, thread it through the final return (line ~237):

```python
    return PackageReaderResult(
        status=loop_result.status,
        replacements=parse_result.replacements,
        narrative=parse_result.narrative,
        error=parse_result.error or loop_result.error,
    )
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd packages/graph-wiki-core && uv run pytest tests/unit/test_package_reader.py -v`
Expected: PASS (all, including prior reader tests — defaulted fields keep them green).

- [ ] **Step 5: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/package_reader.py packages/graph-wiki-core/tests/unit/test_package_reader.py
git commit -m "feat: surface narrative on PackageReaderResult"
```

---

### Task 3: Conditionally request the narrative in the prompt

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/prompts/package_reader.py`
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/package_reader.py:187-209`
- Test: `packages/graph-wiki-core/tests/unit/test_package_reader.py`

- [ ] **Step 1: Write the failing test**

```python
def test_build_package_reader_prompt_requests_narrative_when_flagged():
    from graph_wiki_core.commands.package_reader import PackageReaderItem, build_package_reader_prompt

    base = dict(
        uri="pkg:org/repo/pkg-a", kind="package", name="pkg-a", graph_path="packages/pkg-a",
        language="python", frontmatter={}, page_content="# pkg-a\n", requested_sections={},
        narrative="", file_map="", graph_context="", entity_root="packages/pkg-a",
    )
    on = build_package_reader_prompt(PackageReaderItem(**base, narrative_requested=True))
    off = build_package_reader_prompt(PackageReaderItem(**base, narrative_requested=False))

    assert '"narrative"' in on
    assert "do not invent" in on.lower()
    assert '"narrative"' not in off
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd packages/graph-wiki-core && uv run pytest tests/unit/test_package_reader.py::test_build_package_reader_prompt_requests_narrative_when_flagged -v`
Expected: FAIL — the prompt has no narrative clause.

- [ ] **Step 3: Implement**

In `prompts/package_reader.py`, append one rule to `PACKAGE_READER_SYSTEM` (before the closing `"""`):

```
- When the request asks for it, also return a top-level "narrative" string: 2-4 short factual paragraphs for the page's ## Narrative section, grounded ONLY in files you actually read. Ground every dependency claim in pyproject/imports; never invent package or dependency names.
```

In `package_reader.py`, restructure `build_package_reader_prompt` to append conditionally (replace the single `return (...)` with an assignment + conditional):

```python
def build_package_reader_prompt(item: PackageReaderItem) -> str:
    requested = "\n".join(f"- {heading}: {body}" for heading, body in item.requested_sections.items())
    frontmatter_json = json.dumps(item.frontmatter, sort_keys=True)
    prompt = (
        f"Entity URI: {item.uri}\n"
        f"Kind: {item.kind}\n"
        f"Name: {item.name}\n"
        f"Graph path: {item.graph_path}\n"
        f"Language: {item.language}\n"
        f"Entity root: {item.entity_root}\n\n"
        "Frontmatter JSON:\n"
        f"{frontmatter_json}\n\n"
        "Requested H2 sections:\n"
        f"{requested or '(none)'}\n\n"
        "Scanner narrative:\n"
        f"{item.narrative or '(none)'}\n\n"
        "Scanner file map:\n"
        f"{item.file_map or '(none)'}\n\n"
        "Graph context:\n"
        f"{item.graph_context or '(none)'}\n\n"
        "Current page content:\n"
        f"{truncate_text(item.page_content, MAX_WIKI_PAGE_CHARS)}"
    )
    if item.narrative_requested:
        prompt += (
            '\n\nAlso write an improved ## Narrative body and return it as a top-level '
            '"narrative" string alongside "sections". Ground it in the files you read; '
            "do not invent dependencies or sibling package names."
        )
    return prompt
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd packages/graph-wiki-core && uv run pytest tests/unit/test_package_reader.py -v`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/prompts/package_reader.py packages/graph-wiki-core/src/graph_wiki_core/commands/package_reader.py packages/graph-wiki-core/tests/unit/test_package_reader.py
git commit -m "feat: request grounded narrative in package_reader prompt when flagged"
```

---

### Task 4: Inject the reader narrative in the scan pass

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py:178-268` (`_run_package_reader_pass`), `:1459-1465` (call site)
- Test: `packages/graph-wiki-core/tests/unit/test_scan_narration.py` (new)

- [ ] **Step 1: Write the failing test**

Create `packages/graph-wiki-core/tests/unit/test_scan_narration.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.asyncio
async def test_reader_pass_injects_narrative_for_narrative_uris(tmp_path, monkeypatch):
    from graph_wiki_core.commands import scan as scan_mod
    from graph_wiki_core.commands.package_reader import PackageReaderResult
    from graph_wiki_core.commands.scan import _PackageReaderCandidate, _run_package_reader_pass

    # One package entity page with a fillable human TODO section + a file map (no TODO rows).
    page = tmp_path / "pkg_pkg-a.md"
    page.write_text(
        "---\nuri: pkg:org/repo/pkg-a\nkind: package\n---\n"
        "# pkg-a\n\n## Narrative\n\nOld blind narrative.\n\n"
        "## Purpose\n> TODO: explain.\n",
        encoding="utf-8",
    )

    # Stub the Bedrock stack + the reader call; capture inject_narrative.
    monkeypatch.setattr(scan_mod, "_bedrock_stack", lambda: (lambda r: {"model_id": "m", "max_concurrency": 1},
                                                              lambda *a, **k: object(), _FakePool, _FakeTaskResult))

    async def fake_run_package_reader(**kwargs):
        return PackageReaderResult(status="ok", replacements={"Purpose": "Owns pkg-a."},
                                   narrative="Grounded prose. Depends on `pkg:real`.")

    monkeypatch.setattr(scan_mod, "run_package_reader", fake_run_package_reader)

    injected: dict[Path, str] = {}
    monkeypatch.setattr(scan_mod, "inject_narrative", lambda p, prose: injected.__setitem__(Path(p), prose))
    monkeypatch.setattr(scan_mod, "file_map_todo_paths", lambda p: [])

    candidates = {
        "pkg:org/repo/pkg-a": _PackageReaderCandidate(
            page_path=page, graph_path="packages/pkg-a", kind="package", name="pkg-a", language="python",
        )
    }
    filled, errors = await _run_package_reader_pass(
        wiki=tmp_path / "wiki", repo=tmp_path, conn=None, model_override=None,
        candidate_pages=candidates, narrative_uris={"pkg:org/repo/pkg-a"},
    )

    assert "pkg:org/repo/pkg-a" in filled
    assert injected[page] == "Grounded prose. Depends on `pkg:real`."
    assert errors == []


class _FakeTaskResult:
    def __init__(self, value=None, response=None):
        self.value = value
        self.response = response


class _FakePool:
    def __init__(self, *a, **k):
        pass

    async def run_all(self, *, items, task, role, model_id, max_concurrency):
        successes = [(it, (await task(it)).value) for it in items]
        return _FakeFanout(successes)


class _FakeFanout:
    def __init__(self, successes):
        self.successes = successes
        self.errors = []
```

> Note: `_run_package_reader_pass` builds `graph_tools` from `conn`; with `conn=None` it passes `graph_tools=[]` (see scan.py:191). The fake pool runs the task inline so `fake_run_package_reader` drives the result. If `_bedrock_stack`'s real tuple shape differs at execution time, copy the exact 4-tuple from `scan.py:189` and adapt the lambda.

- [ ] **Step 2: Run to verify it fails**

Run: `cd packages/graph-wiki-core && uv run pytest tests/unit/test_scan_narration.py -v`
Expected: FAIL — `_run_package_reader_pass()` got an unexpected keyword argument `narrative_uris`.

- [ ] **Step 3: Implement**

In `scan.py`, change the `_run_package_reader_pass` signature (line ~178) to add the param:

```python
async def _run_package_reader_pass(
    *,
    wiki: Path,
    repo: Path,
    conn: Any | None,
    model_override: str | None,
    candidate_pages: dict[str, _PackageReaderCandidate],
    narrative_uris: set[str] | None = None,
) -> tuple[set[str], list[str]]:
    narrative_uris = narrative_uris or set()
```

Relax the TODO-only skip (line ~209-211) so narrative-wanted pages still run:

```python
        todo_sections = find_todo_human_sections(page_text, entity_kind=kind)
        wants_narrative = uri in narrative_uris
        if not todo_sections and not wants_narrative:
            continue
```

Set the request flag when building the item (line ~216, add the kwarg):

```python
        item = PackageReaderItem(
            ...
            entity_root=graph_path,
            narrative_requested=wants_narrative,
        )
```

In the success loop (line ~252-264), inject the narrative before the section replace:

```python
    for item_tuple, result in fanout.successes:
        uri, page_path, _reader_item = item_tuple
        if result.error:
            errors.append(f"{uri}: {result.error}")
        if uri in narrative_uris and result.narrative:
            try:
                inject_narrative(page_path, result.narrative)
                filled.add(uri)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{uri}: inject_narrative (package_reader) failed: {exc!r}")
        if not result.replacements:
            continue
        try:
            changed = replace_todo_human_sections(page_path, result.replacements)
        ...
```

(`inject_narrative` is already imported in scan.py from `wiki_io.entity_writer`.)

At the call site (line ~1459), pass the narrated reader-kind uris:

```python
                package_reader_filled_uris, package_reader_errors = await _run_package_reader_pass(
                    wiki=wiki,
                    repo=repo,
                    conn=conn,
                    model_override=model_override,
                    candidate_pages=package_reader_candidates,
                    narrative_uris=set(narrated_page_candidates),
                )
```

(`narrated_page_candidates` only holds entities the narrator wrote this run; non-reader kinds among them are dropped by the existing `kind not in PACKAGE_READER_TARGET_KINDS` guard at scan.py:202, so passing the whole set is safe.)

- [ ] **Step 4: Run to verify it passes**

Run: `cd packages/graph-wiki-core && uv run pytest tests/unit/test_scan_narration.py -v`
Expected: PASS.

- [ ] **Step 5: Run the broader scan + reader suites for regressions**

Run: `cd packages/graph-wiki-core && uv run pytest tests/unit/test_package_reader.py tests/unit/test_commands_scan.py tests/unit/test_scan_narrate.py -q`
Expected: PASS (no regressions; the defaulted `narrative_uris=None` keeps any other callers working).

- [ ] **Step 6: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py packages/graph-wiki-core/tests/unit/test_scan_narration.py
git commit -m "feat: package_reader authors narrative for narrated reader-kind pages"
```

---

## Phase 2 — narrator anti-invention guardrail (repository/domain/dependency)

### Task 5: Forbid invented references in the narrator prompt

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py:490-499` (`build_entity_narrative_prompt` system string)
- Test: `packages/graph-wiki-core/tests/unit/test_scan_narrate.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/unit/test_scan_narrate.py`:

```python
def test_narrator_prompt_forbids_invented_references():
    from types import SimpleNamespace

    from graph_wiki_core.commands.scan import build_entity_narrative_prompt

    node = SimpleNamespace(name="graph-io", attrs={"uri": "pkg:org/repo/graph-io"})
    system, _human = build_entity_narrative_prompt(node, "package", "", {"depends_on": ["pkg:a"]})

    assert "never invent" in system.lower()
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd packages/graph-wiki-core && uv run pytest tests/unit/test_scan_narrate.py::test_narrator_prompt_forbids_invented_references -v`
Expected: FAIL — guardrail text absent.

- [ ] **Step 3: Implement**

In `build_entity_narrative_prompt` (scan.py ~490), extend the `system` string with one sentence:

```python
    system = (
        "You write the narrative body of a graph-derived wiki entity page. "
        "Output ONLY prose: no YAML frontmatter, no H1, no H2 headings, no fenced "
        "code blocks unless the prose specifically describes code. Your output "
        "will be injected between the page's `## Narrative` heading and the next "
        "H2 — write only what belongs there.\n\n"
        "Tone: factual, concise, technical. Length: 2-4 short paragraphs. Cite "
        "the entity's relations naturally (e.g. 'It depends on `pkg:foo`...'); "
        "do not enumerate them in a list.\n\n"
        "Reference ONLY the relations and entities explicitly listed in the input "
        "below; never invent, infer, or guess package, dependency, or module names "
        "that are not provided."
    )
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd packages/graph-wiki-core && uv run pytest tests/unit/test_scan_narrate.py -v`
Expected: PASS (new test + existing narrator-prompt tests).

- [ ] **Step 5: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py packages/graph-wiki-core/tests/unit/test_scan_narrate.py
git commit -m "feat: forbid invented references in narrator prompt"
```

---

## Final verification

### Task 6: Full suite + real scan smoke

- [ ] **Step 1: Full graph-wiki-core suite**

Run: `cd packages/graph-wiki-core && uv run pytest -q`
Expected: PASS (was 527 passed / 7 skipped before this work; new tests add to the pass count, skips unchanged).

- [ ] **Step 2: Lint**

Run (from repo root): `uv run ruff check packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py packages/graph-wiki-core/src/graph_wiki_core/commands/package_reader.py packages/graph-wiki-core/src/graph_wiki_core/prompts/package_reader.py`
Expected: no new errors on the changed files.

- [ ] **Step 3: Real scan + eyeball the previously-hallucinating pages**

Reinstall the editable tool only if the worktree has its own venv (see CLAUDE.md "Worktrees need their own venv"). Then:

```bash
rm /Users/pat/Personal/workspaces/agent-research/combined/wiki/entities/*.md
gw -vv scan
```

Verify on `pkg_eval-harness.md`, `unit_tests_graph-wiki-cli.md`, `app_graph-wiki-cli.md`:
- `## Narrative` no longer cites nonexistent packages (`graph-core`, `wiki-renderer`, `agent-core`, `task-bench`, `faiss`, `chromadb`, …).
- Real deps appear where applicable (e.g. eval-harness narrative mentions `deepeval`, not invented ML libs).
- No `ERROR:` / `ValidationException` lines in scan output.

Cross-check: `grep -rlE "graph-core|wiki-renderer|agent-core|task-bench|faiss|chromadb" <workspace>/wiki/entities` should return nothing for the four reader kinds.

---

## Self-Review notes

- **Spec coverage:** Phase 1 (Tasks 1-4) = "use package_reader where it works as-is" for narration on its 4 kinds. Phase 2 (Task 5) = "grounding fix" for the 3 narrator-only kinds. Apps are covered automatically — they're in `PACKAGE_READER_TARGET_KINDS` and `_run_package_reader_pass` already iterates them; the only app-specific behavior is that they have different human sections, which `find_todo_human_sections(entity_kind=...)` already handles.
- **Type consistency:** `narrative` is a `str` (default `""`) on `_PackageReaderParseResult`, `PackageReaderResult`; `narrative_requested` is a `bool` (default `False`) on `PackageReaderItem`; `narrative_uris` is `set[str] | None` on the pass. Names match across Tasks 1-4.
- **No new fan-out / cost note:** Phase 1 does **not** add a second LLM pass — `_run_package_reader_pass` already runs over these candidates; it now *also* requests narrative in the same tool loop. The redundant call is the *narrator's* first pass over reader kinds (accepted cost of option B). If that cost matters later, "option A" (skip narrator for reader kinds) collapses it — out of scope here.

## Merge-overlap watch (in-flight integration-test work on this branch)

- **Production overlap is limited to `scan.py`.** Tasks 4 and 5 edit `scan.py` at lines ~178-268, ~490-499, and ~1459. If the integration-test work also touches `scan.py` orchestration (it likely touches `tests/integration/test_scan_entity_integration.py`, not `scan.py` itself), reconcile by hand — the edits here are additive (new param with a default, one injected block, one prompt sentence) and should rebase cleanly.
- **Test files do not overlap:** all new/changed tests are under `tests/unit/`. The integration suite under `tests/integration/` is untouched by this plan.
- **Run the integration suite once before merging** to confirm no behavioral drift: `cd packages/graph-wiki-core && uv run pytest -m integration` (needs Bedrock; opt-in).
