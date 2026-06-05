# Ingest Hardening — Always-Source + Loud Fallbacks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `run_ingest_source` robust and honest — every ingested doc lands as a `sources/` page, parse failures surface a loud `source_kind: unknown` instead of silently becoming a `concept` page, and stripped wikilinks + degraded parses are reported in `IngestResult` and CLI output.

**Architecture:** Decouple classification from routing. `run_ingest_source` always writes to `sources/`; the LLM's descriptive kind is read from a new `source_kind` frontmatter key (default `unknown` on parse miss). Frontmatter parsing tries `yaml.safe_load` first, falls back to the existing hand-rolled parser, and synthesizes a minimal block when the LLM emits no frontmatter at all. Three new `IngestResult` fields (`source_kind`, `stripped_wikilinks`, `frontmatter_parsed`) carry the honest signals out to CLI and MCP.

**Tech Stack:** Python 3.11, `uv` workspace, `pytest` (per-package), `dataclasses`, `pyyaml` (already a `graph-wiki-core` dep), `typer` (CLI), `pydantic` (MCP), `syrupy` (prompt snapshots).

**Spec:** `docs/superpowers/specs/2026-06-04-ingest-hardening-always-source-design.md` (Living Wiki M3 Part A).

---

## Design decisions (read before starting)

These are deliberate calls where faithful implementation goes slightly beyond the spec's literal line-cites. They are baked into the tasks below.

1. **Prompt coherence — edit `FRONTMATTER_RULES` too (user-confirmed).** The spec scopes the prompt change to `_PAGE_TYPE_ROUTING` in `prompts/ingestor.py`, but the shared `FRONTMATTER_RULES` fragment still lists `page_type` as a required ingestor field. We replace that line with `source_kind` so the prompt is internally coherent. `FRONTMATTER_RULES` is also embedded in the **scanner** prompt, so **both** the scanner and ingestor snapshots regenerate (benign — the scanner's own instructions are unchanged in meaning). See Task 5.
2. **MCP surfaces new fields via explicit mapping.** The spec says MCP gets the new fields "for free through `asdict`," but `server.py` constructs `WikiIngestOutput` field-by-field (it does **not** use `asdict`). We add the fields to `WikiIngestOutput` and map them explicitly. See Task 7.
3. **`build_ingest_source_prompt` human message updated too.** The page-type-choosing instruction also lives in the runtime human message (`ingest.py:478-483`), not only in the system prompt. We reword it. See Task 5.
4. **Degenerate empty `---\n---` block is out of scope.** The synthesize-frontmatter rule fires only when `fm == {}` **and** the raw output has no leading `---` (exactly the spec's condition). A truly empty `---\n---` block (leading `---` present, zero field lines) is vanishingly rare, falls outside that condition, and the page still lands — we accept it as a known limitation rather than over-engineer.

---

## File structure

Files touched, by responsibility:

- **`packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py`** — the ingest path. Gets: 3 new `IngestResult` fields; `yaml.safe_load` fallback in `_parse_ingestor_response`; two new body helpers (`_set_source_kind_in_body`, `_synthesize_frontmatter_block`); always-`sources/` routing + `source_kind` + `frontmatter_parsed` wiring in `run_ingest_source`; reworded `build_ingest_source_prompt`.
- **`packages/graph-wiki-core/src/graph_wiki_core/prompts/ingestor.py`** — replace `_PAGE_TYPE_ROUTING` with `_SOURCE_LANDING`.
- **`packages/graph-wiki-core/src/graph_wiki_core/prompts/_fragments/frontmatter_rules.py`** — swap the ingestor `page_type` field line for `source_kind`.
- **`packages/graph-wiki-cli/src/graph_wiki_cli/wiki_cli/main.py`** — loud CLI warnings for degraded parse + stripped wikilinks.
- **`packages/graph-wiki-mcp/src/graph_wiki_mcp/server.py`** — 3 new `WikiIngestOutput` fields + mapping.
- **Tests:** `packages/graph-wiki-core/tests/unit/test_commands_ingest.py` (new behaviors + migrate concept/adr-routing tests), `packages/graph-wiki-core/tests/prompts/__snapshots__/test_prompt_snapshots.ambr` (regenerate), `packages/graph-wiki-cli/tests/unit/test_wiki_cli.py` (CLI warnings — only if an ingest CLI test is added).

---

### Task 1: `IngestResult` — three new fields

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py:27` (import), `:89-119` (dataclass)
- Test: `packages/graph-wiki-core/tests/unit/test_commands_ingest.py:319-340` (round-trip test)

Dataclass field-ordering note: every field after the first defaulted one (`entity_uri: str | None = None`) **must** also have a default. So the new fields are appended **after** `entity_uri`, not inserted next to `page_type`. The spec's §4 ordering is conceptual, not literal field order.

- [ ] **Step 1: Write the failing test**

Replace the body of `test_ingest_result_round_trips_to_json` (currently `:319-340`) with a version that also exercises the new defaults:

```python
def test_ingest_result_round_trips_to_json() -> None:
    """IngestResult serializes to JSON without error; new fields have honest defaults."""
    from graph_wiki_core.commands.ingest import IngestResult

    result = IngestResult(
        status="ok",
        page_path="sources/foo.md",
        slug="foo",
        title="Foo",
        page_type="source",
        source_path="/some/path/foo.md",
        cross_refs_updated=1,
    )

    # Defaults for the M3 fields
    assert result.source_kind is None
    assert result.stripped_wikilinks == []
    assert result.frontmatter_parsed is True

    # Should not raise; new fields serialize cleanly
    serialized = json.dumps(dataclasses.asdict(result))
    parsed = json.loads(serialized)

    assert parsed["status"] == "ok"
    assert parsed["slug"] == "foo"
    assert parsed["page_type"] == "source"
    assert parsed["cross_refs_updated"] == 1
    assert parsed["source_kind"] is None
    assert parsed["stripped_wikilinks"] == []
    assert parsed["frontmatter_parsed"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_commands_ingest.py::test_ingest_result_round_trips_to_json -v`
Expected: FAIL with `AttributeError: 'IngestResult' object has no attribute 'source_kind'`.

- [ ] **Step 3: Add the import**

In `ingest.py:27`, change:

```python
from dataclasses import dataclass
```

to:

```python
from dataclasses import dataclass, field
```

- [ ] **Step 4: Add the three fields**

In `ingest.py`, replace the single line `:119`:

```python
    entity_uri: str | None = None  # Phase 40: canonical entity URI; None for free-form sources
```

with:

```python
    entity_uri: str | None = None  # Phase 40: canonical entity URI; None for free-form sources
    # Living Wiki M3 Part A (ingest hardening):
    source_kind: str | None = None  # descriptive kind on Source pages; "unknown" on parse miss; None for work items
    stripped_wikilinks: list[str] = field(default_factory=list)  # unresolved [[links]] stripped from the body
    frontmatter_parsed: bool = True  # False when we fell through to source_kind: unknown via a parse miss
```

Also update the dataclass docstring (`:93-110`) by appending these lines after the `entity_uri:` description (before the closing `"""`):

```python
        source_kind:        Living Wiki M3: descriptive kind on Source pages
                            (run_ingest_source). "unknown" on a parse miss; None
                            for work items.
        stripped_wikilinks: Living Wiki M3: unresolved [[wikilinks]] removed from
                            the body (empty when none were stripped).
        frontmatter_parsed: Living Wiki M3: False when the ingestor frontmatter
                            failed to parse and we fell through to
                            source_kind: unknown.
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_commands_ingest.py::test_ingest_result_round_trips_to_json -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py packages/graph-wiki-core/tests/unit/test_commands_ingest.py
git commit -m "feat(ingest): add source_kind/stripped_wikilinks/frontmatter_parsed to IngestResult"
```

---

### Task 2: `yaml.safe_load` with graceful fallback in `_parse_ingestor_response`

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py:23` (import), `:416-449` (parser)
- Test: `packages/graph-wiki-core/tests/unit/test_commands_ingest.py` (add near the existing `_parse_ingestor_response` tests, after `:398`)

Behavior contract (spec §3.3): after isolating the frontmatter block, try `yaml.safe_load`. If it returns a `dict`, use it. If it raises `yaml.YAMLError` **or** returns a non-dict, fall back to the existing hand-rolled parser verbatim. If both miss, return `({}, body)`. The fence-strip pre-pass (`:379-403`) is unchanged.

- [ ] **Step 1: Write the failing tests**

Add these three tests after `test_parse_ingestor_response_fence_without_dashes_returns_empty` (`:398`):

```python
def test_parse_ingestor_response_uses_safe_load_for_valid_yaml() -> None:
    """Clean YAML is parsed (typed) via yaml.safe_load."""
    from graph_wiki_core.commands.ingest import _parse_ingestor_response

    raw = "---\nsource_kind: source\ntarget_slug: foo\ntags:\n  - a\n  - b\n---\nBody."
    fm, body = _parse_ingestor_response(raw)
    assert fm["source_kind"] == "source"
    assert fm["target_slug"] == "foo"
    assert fm["tags"] == ["a", "b"]  # safe_load yields a real list
    assert body.strip() == "Body."


def test_parse_ingestor_response_falls_back_to_handrolled_on_yaml_error() -> None:
    """An unquoted colon in a value makes safe_load raise; the hand-rolled
    parser recovers the value verbatim."""
    from graph_wiki_core.commands.ingest import _parse_ingestor_response

    # `summary: foo: bar baz` -> safe_load raises ScannerError (a YAMLError);
    # hand-rolled partition-on-first-colon recovers val="foo: bar baz".
    raw = (
        "---\n"
        "source_kind: source\n"
        "target_slug: foo\n"
        "summary: foo: bar baz\n"
        "---\n"
        "Body."
    )
    fm, body = _parse_ingestor_response(raw)
    assert fm["source_kind"] == "source"
    assert fm["target_slug"] == "foo"
    assert fm["summary"] == "foo: bar baz"
    assert body.strip() == "Body."


def test_parse_ingestor_response_empty_block_returns_empty_dict() -> None:
    """A frontmatter block with no parseable keys returns ({}, body)."""
    from graph_wiki_core.commands.ingest import _parse_ingestor_response

    raw = "---\n# only a comment\n---\nBody."
    fm, body = _parse_ingestor_response(raw)
    assert fm == {}
    assert body.strip() == "Body."
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_commands_ingest.py -k "safe_load or falls_back or empty_block_returns" -v`
Expected: `test_parse_ingestor_response_uses_safe_load_for_valid_yaml` FAILS on `fm["tags"] == ["a", "b"]` (hand-rolled returns the list, so this may pass — but `falls_back` FAILS: the hand-rolled parser already recovers it, so this one passes too). The genuinely failing assertion is the typed-list one only if hand-rolled differs. **If all three pass before implementation**, that is acceptable — they pin the post-change contract; proceed to Step 3 and confirm they stay green. (The `safe_load` path is an internal robustness upgrade; its observable contract overlaps the hand-rolled parser by design.)

- [ ] **Step 3: Add the `yaml` import**

In `ingest.py:23`, the imports begin with `import logging`. Add `import yaml` in alphabetical position among the stdlib/third-party block — place it after `import uuid` (`:26`) is fine since `yaml` is third-party; to match the existing grouping, add it on its own line immediately after the `from pathlib import Path` line (`:28`):

```python
from pathlib import Path

import yaml
```

- [ ] **Step 4: Insert the `safe_load` attempt before the hand-rolled loop**

In `_parse_ingestor_response`, find (`:416-420`):

```python
    yaml_block = rest[:closing_idx].strip()
    body = rest[closing_idx + 4:].lstrip("\n")

    # Parse YAML block (simple key: value + list items)
    fm: dict = {}
```

Replace with:

```python
    yaml_block = rest[:closing_idx].strip()
    body = rest[closing_idx + 4:].lstrip("\n")

    # D3 (spec §3.3): prefer yaml.safe_load. If it raises YAMLError or returns
    # a non-dict, fall back to the hand-rolled scalar/list parser below — it
    # tolerates LLM quirks safe_load rejects (e.g. an unquoted ':' in a value).
    try:
        loaded = yaml.safe_load(yaml_block)
    except yaml.YAMLError:
        loaded = None
    if isinstance(loaded, dict):
        return loaded, body

    # Fallback: hand-rolled scalar/list parser (kept verbatim).
    fm: dict = {}
```

The rest of the function (the `for raw in yaml_block.splitlines()` loop through `return fm, body`) is unchanged.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_commands_ingest.py -k "safe_load or falls_back or empty_block_returns or fenced_and_unfenced or no_frontmatter or fence_without_dashes" -v`
Expected: PASS (all parser tests, including the pre-existing fence tests, stay green).

- [ ] **Step 6: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py packages/graph-wiki-core/tests/unit/test_commands_ingest.py
git commit -m "feat(ingest): parse ingestor frontmatter with yaml.safe_load, hand-rolled fallback"
```

---

### Task 3: Body helpers — `_set_source_kind_in_body` + `_synthesize_frontmatter_block`

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py` (add both helpers after `_set_entity_uri_in_body`, i.e. after `:247`)
- Test: `packages/graph-wiki-core/tests/unit/test_commands_ingest.py` (add after the `_set_entity_uri_in_body` test at `:973`)

These mirror the existing `_set_entity_uri_in_body` contract: operate on raw text (preserve comments/order), idempotent, no-op when there is no `---` block.

- [ ] **Step 1: Write the failing tests**

Add after `test_set_entity_uri_in_body_inserts_after_target_slug` (`:973`):

```python
def test_set_source_kind_in_body_inserts_and_is_idempotent() -> None:
    from graph_wiki_core.commands.ingest import _set_source_kind_in_body

    text = "---\ntarget_slug: foo\ntitle: Foo\n---\n\nBody"
    out = _set_source_kind_in_body(text, "unknown")
    # Inserted as the first frontmatter field.
    lines = out.splitlines()
    assert lines[0] == "---"
    assert lines[1] == "source_kind: unknown"
    # Idempotence: calling twice yields exactly one source_kind: line.
    twice = _set_source_kind_in_body(out, "source")
    assert twice.count("source_kind:") == 1
    assert "source_kind: source" in twice

    # No frontmatter -> unchanged.
    assert _set_source_kind_in_body("no frontmatter here", "unknown") == "no frontmatter here"


def test_synthesize_frontmatter_block_prepends_all_fields() -> None:
    from graph_wiki_core.commands.ingest import (
        _rewrite_target_slug_in_body,
        _set_entity_uri_in_body,
        _synthesize_frontmatter_block,
    )

    body = "Just a body, no frontmatter.\n"
    out = _synthesize_frontmatter_block(body, "unknown", "my-slug", None)
    assert out.startswith("---\n")
    assert "source_kind: unknown" in out
    assert "target_slug: my-slug" in out
    assert "entity_uri: null" in out
    assert out.rstrip().endswith("Just a body, no frontmatter.")

    # The downstream body helpers now function on the synthesized block and are
    # idempotent against it (proves synthesis produces a valid --- block).
    out2 = _rewrite_target_slug_in_body(out, "my-slug")
    out2 = _set_entity_uri_in_body(out2, None)
    assert out2.count("target_slug:") == 1
    assert out2.count("entity_uri:") == 1

    # entity_uri carried through when present.
    out_uri = _synthesize_frontmatter_block(body, "source", "s", "pkg:x/y/z")
    assert "entity_uri: pkg:x/y/z" in out_uri
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_commands_ingest.py -k "set_source_kind or synthesize_frontmatter" -v`
Expected: FAIL with `ImportError: cannot import name '_set_source_kind_in_body'`.

- [ ] **Step 3: Add both helpers**

In `ingest.py`, immediately after the end of `_set_entity_uri_in_body` (after `:247`, the line `    return f"{leading_ws}---\n{new_fm}{body_and_close}"`), add:

```python


# ---------------------------------------------------------------------------
# Living Wiki M3 Part A — source_kind frontmatter + synthesize-frontmatter rule
# ---------------------------------------------------------------------------


def _set_source_kind_in_body(text: str, source_kind: str) -> str:
    """Insert or replace the `source_kind:` line in the YAML frontmatter of `text`.

    Placement: inserted as the FIRST field of the frontmatter block. Idempotent
    — any existing `source_kind:` line is dropped first, so only one ever
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
        if line.lstrip().startswith("source_kind:"):
            continue  # drop existing line (idempotence)
        new_lines.append(line)
    new_lines.insert(0, f"source_kind: {source_kind}")
    new_fm = "\n".join(new_lines)
    return f"{leading_ws}---\n{new_fm}{body_and_close}"


def _synthesize_frontmatter_block(
    body: str, source_kind: str, target_slug: str, entity_uri: str | None
) -> str:
    """Prepend a minimal YAML frontmatter block to a body that has none.

    D3 synthesize-frontmatter rule (spec §3.3): the body-mutation helpers
    (_rewrite_target_slug_in_body / _set_entity_uri_in_body /
    _set_source_kind_in_body) no-op when there is no `---` block. When the
    ingestor LLM emits a body with no frontmatter at all, this guarantees the
    unknown-kind Source page still lands with its metadata. The block carries
    all three fields so the downstream setters become idempotent no-ops.
    `entity_uri=None` is written as the literal `null` (mirrors
    _set_entity_uri_in_body).
    """
    uri_val = "null" if entity_uri is None else entity_uri
    return (
        "---\n"
        f"source_kind: {source_kind}\n"
        f"target_slug: {target_slug}\n"
        f"entity_uri: {uri_val}\n"
        "---\n\n"
        f"{body}"
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_commands_ingest.py -k "set_source_kind or synthesize_frontmatter" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py packages/graph-wiki-core/tests/unit/test_commands_ingest.py
git commit -m "feat(ingest): add _set_source_kind_in_body + _synthesize_frontmatter_block helpers"
```

---

### Task 4: `run_ingest_source` — always-`sources/`, `source_kind`, synthesis, loud fields

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py:626-691` (steps 6-10 of `run_ingest_source`)
- Test: `packages/graph-wiki-core/tests/unit/test_commands_ingest.py` (add new tests; migrate existing concept/adr-routing tests)

This is the core behavior change. Implement the new integration tests first (they fail), wire the change, then migrate the existing routing tests that now assert the wrong directory.

- [ ] **Step 1: Write the new failing integration tests**

Add these to `test_commands_ingest.py`, after the existing `test_run_ingest_source_no_match_writes_null_entity_uri` (`:848`):

```python
# ---------------------------------------------------------------------------
# M3: always-Source routing even when the LLM claims adr/concept
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_ingest_source_always_routes_to_sources_even_if_llm_says_adr(
    tmp_path: Path,
) -> None:
    """An LLM response claiming page_type: adr still lands under sources/."""
    from graph_wiki_core.commands.ingest import run_ingest_source

    workspace, wiki, repo = _build_workspace_with_repo(tmp_path)
    source_file = workspace / "src.md"
    source_file.write_text("# A Decision\n\nBody.", encoding="utf-8")
    _seed_graph_db_for_ingest_tests(workspace, packages=[])

    # LLM claims adr AND emits a descriptive source_kind.
    fake_llm_response = (
        "---\n"
        "title: A Decision\n"
        "page_type: adr\n"
        "source_kind: source\n"
        "target_slug: a-decision\n"
        "summary: x\n"
        "---\n"
        "Body."
    )

    with (
        patch("graph_wiki_core.commands.ingest.resolve_wiki_and_repo") as mock_resolve,
        patch("graph_wiki_core.commands.ingest.make_llm") as mock_make_llm,
        patch("graph_wiki_core.commands.ingest.update_index"),
        patch("graph_wiki_core.commands.ingest.append_log"),
    ):
        mock_resolve.return_value = (wiki, repo)
        fake_llm = MagicMock()
        fake_llm.ainvoke = AsyncMock(return_value=MagicMock(content=fake_llm_response))
        mock_make_llm.return_value = fake_llm

        result = await run_ingest_source(source_file, workspace)

    assert (wiki / "sources" / "a-decision.md").exists()
    assert not (wiki / "adrs").exists() or not any((wiki / "adrs").iterdir())
    assert result.page_type == "source"
    assert result.source_kind == "source"
    assert result.frontmatter_parsed is True
    assert "sources/a-decision.md" in result.page_path


@pytest.mark.asyncio
async def test_run_ingest_source_no_frontmatter_synthesizes_unknown(
    tmp_path: Path,
) -> None:
    """LLM emits a body with NO frontmatter -> synthesized block lands with
    source_kind: unknown, target_slug + entity_uri present, frontmatter_parsed False."""
    from graph_wiki_core.commands.ingest import run_ingest_source

    workspace, wiki, repo = _build_workspace_with_repo(tmp_path)
    source_file = workspace / "raw-notes.md"
    source_file.write_text("# Raw Notes\n\nBody.", encoding="utf-8")
    _seed_graph_db_for_ingest_tests(workspace, packages=[])

    # No --- block at all.
    fake_llm_response = "Just some prose the model emitted, no frontmatter whatsoever."

    with (
        patch("graph_wiki_core.commands.ingest.resolve_wiki_and_repo") as mock_resolve,
        patch("graph_wiki_core.commands.ingest.make_llm") as mock_make_llm,
        patch("graph_wiki_core.commands.ingest.update_index"),
        patch("graph_wiki_core.commands.ingest.append_log"),
    ):
        mock_resolve.return_value = (wiki, repo)
        fake_llm = MagicMock()
        fake_llm.ainvoke = AsyncMock(return_value=MagicMock(content=fake_llm_response))
        mock_make_llm.return_value = fake_llm

        result = await run_ingest_source(source_file, workspace)

    # Slug falls back to slugify(title) == "raw-notes".
    written = (wiki / "sources" / "raw-notes.md").read_text(encoding="utf-8")
    assert "source_kind: unknown" in written
    assert "target_slug: raw-notes" in written  # synthesis ran BEFORE the body helpers
    assert "entity_uri: null" in written
    assert "Just some prose" in written
    assert result.page_type == "source"
    assert result.source_kind == "unknown"
    assert result.frontmatter_parsed is False
    assert "sources/raw-notes.md" in result.page_path


@pytest.mark.asyncio
async def test_run_ingest_source_surfaces_stripped_wikilinks_in_result(
    tmp_path: Path,
) -> None:
    """Hallucinated [[links]] are reported in IngestResult.stripped_wikilinks."""
    from graph_wiki_core.commands.ingest import run_ingest_source

    workspace, wiki, repo = _build_workspace_with_repo(tmp_path)
    (wiki / "concepts").mkdir(parents=True)
    (wiki / "concepts" / "real-thing.md").write_text("# Real", encoding="utf-8")
    source_file = workspace / "src.md"
    source_file.write_text("# Src\n\nBody.", encoding="utf-8")
    _seed_graph_db_for_ingest_tests(workspace, packages=[])

    fake_llm_response = (
        "---\n"
        "title: My Page\n"
        "source_kind: source\n"
        "target_slug: my-page\n"
        "summary: x\n"
        "---\n"
        "Refers to [[real-thing]] and to [[Hallucinated Person]]."
    )

    with (
        patch("graph_wiki_core.commands.ingest.resolve_wiki_and_repo") as mock_resolve,
        patch("graph_wiki_core.commands.ingest.make_llm") as mock_make_llm,
        patch("graph_wiki_core.commands.ingest.update_index"),
        patch("graph_wiki_core.commands.ingest.append_log"),
    ):
        mock_resolve.return_value = (wiki, repo)
        fake_llm = MagicMock()
        fake_llm.ainvoke = AsyncMock(return_value=MagicMock(content=fake_llm_response))
        mock_make_llm.return_value = fake_llm

        result = await run_ingest_source(source_file, workspace)

    assert result.stripped_wikilinks == ["Hallucinated Person"]
    assert result.frontmatter_parsed is True
    assert result.source_kind == "source"
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_commands_ingest.py -k "always_routes_to_sources or no_frontmatter_synthesizes or surfaces_stripped_wikilinks" -v`
Expected: FAIL — `always_routes_to_sources` fails because the page lands under `adrs/`; `no_frontmatter_synthesizes` fails because no `sources/` page is written / no synthesized metadata; `surfaces_stripped_wikilinks` fails on `AttributeError`/empty list.

- [ ] **Step 3: Rewrite steps 6-7 of `run_ingest_source`**

In `ingest.py`, find the block `:626-666` (from `# Step 6:` through the `_ensure_entity_touch_link` block):

```python
        # Step 6: parse response to get page_type and target_slug
        fm, _body = _parse_ingestor_response(llm_output)
        page_type = str(fm.get("page_type", "concept")).lower()
        if page_type not in _PAGE_TYPE_DIRS:
            page_type = "concept"

        target_slug = str(fm.get("target_slug", "")).strip()
        # Sanitize slug: re-slugify whatever the LLM provided (T-05-05-02)
        target_slug = slugify(target_slug) if target_slug else slug

        # Step 7: write page
        target_path = _route_target_path(wiki, page_type, target_slug)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        # Reconcile target_slug in the body with the on-disk filename slug.
        # _route_target_path uses slugify(target_slug); if that differs from
        # what the LLM wrote, rewrite the body's `target_slug:` line to match.
        # Also handles the case where the LLM omitted target_slug entirely
        # (we fell back to slugify(title)) — write that fallback into the body.
        canonical_slug = target_path.stem
        llm_output = _rewrite_target_slug_in_body(llm_output, canonical_slug)
        # D-05/D-06: write entity_uri frontmatter on every successful ingest.
        # null when no graph match; full URI when matched.
        llm_output = _set_entity_uri_in_body(llm_output, canonical_uri)
```

Replace it with:

```python
        # Step 6: parse response to get source_kind and target_slug.
        # M3 Part A: classification is DECOUPLED from routing. Every ingested
        # doc becomes a Source page; `source_kind` is descriptive only and
        # defaults to "unknown" on a parse miss (empty fm).
        fm, _body = _parse_ingestor_response(llm_output)
        frontmatter_parsed = bool(fm)  # False ⟺ parse miss (spec §3.5)
        source_kind = str(fm.get("source_kind", "")).strip().lower() or "unknown"

        target_slug = str(fm.get("target_slug", "")).strip()
        # Sanitize slug: re-slugify whatever the LLM provided (T-05-05-02)
        target_slug = slugify(target_slug) if target_slug else slug

        # Step 7: write page. D1 — always route to sources/ (page_type fixed to
        # "source"; _route_target_path keeps the path-traversal safety check).
        target_path = _route_target_path(wiki, "source", target_slug)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        canonical_slug = target_path.stem

        # D3 synthesize-frontmatter rule: when the LLM emitted NO frontmatter at
        # all, the body-mutation helpers below would no-op — prepend a minimal
        # block so the unknown-kind Source page lands with its metadata.
        if not frontmatter_parsed and not llm_output.lstrip().startswith("---"):
            llm_output = _synthesize_frontmatter_block(
                llm_output, source_kind, canonical_slug, canonical_uri
            )

        # Reconcile target_slug in the body with the on-disk filename slug, write
        # entity_uri (null when no graph match), and stamp source_kind. All three
        # helpers are idempotent and preserve comments/order.
        llm_output = _rewrite_target_slug_in_body(llm_output, canonical_slug)
        llm_output = _set_entity_uri_in_body(llm_output, canonical_uri)
        llm_output = _set_source_kind_in_body(llm_output, source_kind)
```

The lines that follow (`# Write the file first…` through the `_ensure_entity_touch_link` block, `:649-666`) are unchanged.

- [ ] **Step 4: Update the `IngestResult` construction (step 10)**

In `ingest.py`, find the return block `:682-691`:

```python
        return IngestResult(
            status="ok",
            page_path=page_path_rel,
            slug=target_slug,
            title=title_guess,
            page_type=page_type,
            source_path=str(source_path),
            cross_refs_updated=1,
            entity_uri=canonical_uri,
        )
```

Replace with:

```python
        return IngestResult(
            status="ok",
            page_path=page_path_rel,
            slug=target_slug,
            title=title_guess,
            page_type="source",  # D1: run_ingest_source always files under sources/
            source_path=str(source_path),
            cross_refs_updated=1,
            entity_uri=canonical_uri,
            source_kind=source_kind,
            stripped_wikilinks=stripped_wikilinks,
            frontmatter_parsed=frontmatter_parsed,
        )
```

- [ ] **Step 5: Run the new tests to verify they pass**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_commands_ingest.py -k "always_routes_to_sources or no_frontmatter_synthesizes or surfaces_stripped_wikilinks" -v`
Expected: PASS

- [ ] **Step 6: Migrate the existing concept/adr-routing tests**

Run the full file to see which existing tests now fail:

Run: `uv run --package graph-wiki-core pytest tests/unit/test_commands_ingest.py -v`
Expected failures (they assert the old `concepts/` routing or `page_type` result):
`test_run_ingest_source_extracts_and_routes`, `test_run_ingest_source_target_slug_matches_filename`, `test_run_ingest_source_strips_unresolved_wikilinks`, `test_run_ingest_source_name_match_sets_uri_without_entity_link`, `test_run_ingest_source_no_match_writes_null_entity_uri`, `test_run_ingest_source_multi_match_warns_and_falls_back`.

Apply these exact edits:

**(a) `test_run_ingest_source_extracts_and_routes`** — change the fake response to carry `source_kind`, and flip the expected directory + result assertions. Replace the fake response line (`:101`):

```python
    fake_llm_response = "---\npage_type: concept\ntarget_slug: foo\ntitle: My Source\ncategory: concept\nsummary: A test concept\n---\n\nBody text here."
```

with:

```python
    fake_llm_response = "---\nsource_kind: source\ntarget_slug: foo\ntitle: My Source\nsummary: A test concept\n---\n\nBody text here."
```

Replace the page-location + body assertions (`:120-129`):

```python
    # Page should be written under concepts/foo.md
    expected_page = wiki / "concepts" / "foo.md"
    assert expected_page.exists(), f"Expected page at {expected_page}"
    # Phase 40: body now also contains an entity_uri: null line (no graph match);
    # use substring assertions rather than strict equality.
    written_body = expected_page.read_text(encoding="utf-8")
    assert "page_type: concept" in written_body
    assert "target_slug: foo" in written_body
    assert "entity_uri: null" in written_body
    assert "Body text here." in written_body
```

with:

```python
    # M3: every ingested doc lands under sources/.
    expected_page = wiki / "sources" / "foo.md"
    assert expected_page.exists(), f"Expected page at {expected_page}"
    written_body = expected_page.read_text(encoding="utf-8")
    assert "source_kind: source" in written_body
    assert "target_slug: foo" in written_body
    assert "entity_uri: null" in written_body
    assert "Body text here." in written_body
```

Replace the result assertions (`:139-140`):

```python
    assert result.page_type == "concept"
    assert "concepts/foo.md" in result.page_path
```

with:

```python
    assert result.page_type == "source"
    assert result.source_kind == "source"
    assert result.frontmatter_parsed is True
    assert "sources/foo.md" in result.page_path
```

**(b) `test_run_ingest_source_target_slug_matches_filename`** — replace the written-path line (`:498`):

```python
    written_path = wiki / "concepts" / f"{result.slug}.md"
```

with:

```python
    written_path = wiki / "sources" / f"{result.slug}.md"
```

**(c) `test_run_ingest_source_strips_unresolved_wikilinks`** — replace the written-file read (`:605`):

```python
    written = (wiki / "concepts" / "my-page.md").read_text(encoding="utf-8")
```

with:

```python
    written = (wiki / "sources" / "my-page.md").read_text(encoding="utf-8")
```

and replace the final result assertion (`:613`):

```python
    assert result.page_type == "concept"
```

with:

```python
    assert result.page_type == "source"
    assert result.stripped_wikilinks == ["Hallucinated Person"]
```

**(d) `test_run_ingest_source_name_match_sets_uri_without_entity_link`** — replace the written-file read (`:802`):

```python
    written = (wiki / "concepts" / "some-other-thing.md").read_text(encoding="utf-8")
```

with:

```python
    written = (wiki / "sources" / "some-other-thing.md").read_text(encoding="utf-8")
```

**(e) `test_run_ingest_source_no_match_writes_null_entity_uri`** — replace the written-file read (`:847`):

```python
    written = (wiki / "concepts" / "my-thing.md").read_text(encoding="utf-8")
```

with:

```python
    written = (wiki / "sources" / "my-thing.md").read_text(encoding="utf-8")
```

**(f) `test_run_ingest_source_multi_match_warns_and_falls_back`** — replace the written-file read (`:899`):

```python
    written = (wiki / "concepts" / "helper.md").read_text(encoding="utf-8")
```

with:

```python
    written = (wiki / "sources" / "helper.md").read_text(encoding="utf-8")
```

> Note: `test_run_ingest_source_routes_source_to_sources_dir` and `test_run_ingest_source_path_match_links_entity_never_packages` already assert `sources/` and `page_type == "source"`; they need no change. `test_run_ingest_source_default_slug_from_title` asserts only the slug (no path), so it stays green unchanged.

- [ ] **Step 7: Run the whole ingest test file to verify it is green**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_commands_ingest.py -v`
Expected: PASS (all tests).

- [ ] **Step 8: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py packages/graph-wiki-core/tests/unit/test_commands_ingest.py
git commit -m "feat(ingest): run_ingest_source always files Source pages with source_kind + loud fields"
```

---

### Task 5: Ingestor prompt — drop page-type routing, introduce `source_kind`

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/prompts/ingestor.py:34-49` (`_PAGE_TYPE_ROUTING`), `:123` (parts list)
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/prompts/_fragments/frontmatter_rules.py` (ingestor field line)
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py:473-483` (`build_ingest_source_prompt` human message)
- Regenerate: `packages/graph-wiki-core/tests/prompts/__snapshots__/test_prompt_snapshots.ambr`
- Test: `packages/graph-wiki-core/tests/prompts/test_ingestor_prompt.py` (existing — must still pass), `test_token_budget.py` (existing — must still pass)

Per Design Decision #1, both the scanner and ingestor snapshots regenerate (shared fragment edit).

- [ ] **Step 1: Replace the ingestor `page_type` field line in `FRONTMATTER_RULES`**

In `_fragments/frontmatter_rules.py`, find:

```python
**Ingestor source-summary pages** require:
- `title`: descriptive title for the page
- `category`: one of the page category values (`source`, `concept`, `adr`, …)
- `page_type`: one of `concept`, `adr`, `source`
- `target_slug`: URL-safe slug for the output filename (e.g. `auth-design`)
```

Replace the `page_type` line so the block reads:

```python
**Ingestor source-summary pages** require:
- `title`: descriptive title for the page
- `category`: one of the page category values (`source`, `concept`, `adr`, …)
- `source_kind`: optional descriptive kind (e.g. `source`); does NOT control routing — every ingested doc lands under `sources/`
- `target_slug`: URL-safe slug for the output filename (e.g. `auth-design`)
```

- [ ] **Step 2: Replace `_PAGE_TYPE_ROUTING` with `_SOURCE_LANDING` in `ingestor.py`**

In `prompts/ingestor.py`, replace the whole `_PAGE_TYPE_ROUTING = (…)` constant (`:34-49`):

```python
_PAGE_TYPE_ROUTING = (
    "## Page-type routing\n\n"
    "Choose exactly one `page_type`. The on-disk destination is determined by `page_type`:\n\n"
    "- `page_type: source` -> `sources/` (specs, PRs, articles, transcripts, in-repo docs)\n"
    "- `page_type: concept` -> `concepts/` (cross-cutting technical idea, comparison page)\n"
    "- `page_type: adr` -> `adrs/` (dated decision record)\n\n"
    "Do NOT author a package page. Code entities (packages, apps, domains, "
    "dependencies, test suites) are scanner-owned and live under `entities/`. "
    "To associate this source with a code entity, reference it from the body with "
    "a `[[entities/<prefix>_<name>]]` wikilink (e.g. `[[entities/pkg_graph-io]]`) "
    "under a `## Touches` section — the scanner derives the backlink onto the "
    "entity page. Never write into `entities/` pages.\n\n"
    "`category` should agree with `page_type` (`source` -> `source`, "
    "`concept` -> `concept`, `adr` -> `adr`).\n"
    "`update_index()` and `append_log()` run automatically — omit those steps."
)
```

with:

```python
_SOURCE_LANDING = (
    "## Source landing\n\n"
    "Every ingested document becomes a **Source page** under `sources/`. You do "
    "NOT choose the destination — routing is fixed. Do NOT emit a `page_type` "
    "field; it is ignored, and this rule supersedes any `page_type` mentioned "
    "elsewhere in these instructions.\n\n"
    "Optionally emit a descriptive `source_kind` field — use `source` for a "
    "document you can cleanly summarize. It is purely descriptive and does NOT "
    "control where the page is written.\n\n"
    "Do NOT author a package page. Code entities (packages, apps, domains, "
    "dependencies, test suites) are scanner-owned and live under `entities/`. "
    "To associate this source with a code entity, reference it from the body with "
    "a `[[entities/<prefix>_<name>]]` wikilink (e.g. `[[entities/pkg_graph-io]]`) "
    "under a `## Touches` section — the scanner derives the backlink onto the "
    "entity page. Never write into `entities/` pages.\n\n"
    "`update_index()` and `append_log()` run automatically — omit those steps."
)
```

- [ ] **Step 3: Update the parts list in `build_ingestor_system`**

In `prompts/ingestor.py`, in the `parts = [ … ]` list (`:113-128`), replace the line:

```python
        _PAGE_TYPE_ROUTING,
```

with:

```python
        _SOURCE_LANDING,
```

- [ ] **Step 4: Reword the `build_ingest_source_prompt` human message**

In `commands/ingest.py`, replace the trailing instruction in `build_ingest_source_prompt` (`:478-483`):

```python
        f"\nWrite a vault wiki page for this source. "
        f"Choose the most appropriate page_type (source, concept, or adr) "
        f"and a target_slug based on the content. To associate this source with "
        f"a code entity, reference it with a [[entities/...]] wikilink in the "
        f"body — do not create a package page."
```

with:

```python
        f"\nWrite a Source page for this document. It will be filed under "
        f"sources/. Provide a target_slug based on the content, and optionally a "
        f"descriptive source_kind. To associate this source with a code entity, "
        f"reference it with a [[entities/...]] wikilink in the body — do not "
        f"create a package page."
```

- [ ] **Step 5: Confirm the prompt-content tests still pass**

Run: `uv run --package graph-wiki-core pytest tests/prompts/test_ingestor_prompt.py tests/prompts/test_token_budget.py -v`
Expected: PASS (`test_ingestor_prompt_has_no_package_page_type` still holds — `[[entities/` is retained, no `page_type: package` / `-> packages/`; the token budget only enforces a ceiling, and the prompt shrank).

- [ ] **Step 6: Regenerate the prompt snapshots**

Run: `uv run --package graph-wiki-core pytest tests/prompts/test_prompt_snapshots.py --snapshot-update`
Then verify clean:
Run: `uv run --package graph-wiki-core pytest tests/prompts/test_prompt_snapshots.py -v`
Expected: PASS. The diff in `__snapshots__/test_prompt_snapshots.ambr` should touch the **scanner** snapshots (embedded `FRONTMATTER_RULES` line changed) and the **ingestor** snapshots (routing block + frontmatter line). Sanity-check the diff with `git diff -- packages/graph-wiki-core/tests/prompts/__snapshots__/test_prompt_snapshots.ambr` — only those two roles' blocks should change; no other role's snapshot should move.

- [ ] **Step 7: Run the brand gate** (renames/string churn can trip it)

Run: `bash scripts/check-brand.sh`
Expected: exits 0 (no stray upstream names introduced).

- [ ] **Step 8: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/prompts/ingestor.py \
        packages/graph-wiki-core/src/graph_wiki_core/prompts/_fragments/frontmatter_rules.py \
        packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py \
        packages/graph-wiki-core/tests/prompts/__snapshots__/test_prompt_snapshots.ambr
git commit -m "feat(ingest): drop page-type routing from ingestor prompt; introduce descriptive source_kind"
```

---

### Task 6: CLI — loud warnings for degraded parse + stripped wikilinks

**Files:**
- Modify: `packages/graph-wiki-cli/src/graph_wiki_cli/wiki_cli/main.py:213-217` (`ingest_source` text output)
- Test: `packages/graph-wiki-cli/tests/unit/test_wiki_cli.py` (add a CLI ingest test)

The `--json` branch already serializes all fields via `dataclasses.asdict(result)` — no change needed there. Only the human-readable text branch gains warnings. We mock `run_ingest_source` so the test stays a unit test (no Bedrock).

- [ ] **Step 1: Write the failing test**

First check how the CLI runner is invoked elsewhere in the file (it uses `typer.testing.CliRunner` against `wiki_app`). Add this test to `test_wiki_cli.py` (match the existing import style at the top of that file — it already imports `from typer.testing import CliRunner` and `wiki_app`; if not, add `from graph_wiki_cli.wiki_cli.main import wiki_app` and `from typer.testing import CliRunner`):

```python
def test_ingest_source_cli_warns_on_degraded_and_stripped(tmp_path):
    """Text-mode CLI prints loud warnings when frontmatter didn't parse and
    when wikilinks were stripped."""
    from unittest.mock import AsyncMock, patch

    from typer.testing import CliRunner

    from graph_wiki_core.commands.ingest import IngestResult
    from graph_wiki_cli.wiki_cli.main import wiki_app

    src = tmp_path / "doc.md"
    src.write_text("# Doc\n\nBody.", encoding="utf-8")

    fake_result = IngestResult(
        status="ok",
        page_path="sources/doc.md",
        slug="doc",
        title="Doc",
        page_type="source",
        source_path=str(src),
        cross_refs_updated=1,
        source_kind="unknown",
        stripped_wikilinks=["Made Up Person", "fake/page"],
        frontmatter_parsed=False,
    )

    runner = CliRunner()
    with patch(
        "graph_wiki_cli.wiki_cli.main.run_ingest_source",
        new_callable=AsyncMock,
        return_value=fake_result,
    ):
        result = runner.invoke(wiki_app, ["ingest", "source", str(src)])

    assert result.exit_code == 0
    assert "source_kind: unknown" in result.stdout
    assert "frontmatter did not parse" in result.stdout
    assert "stripped 2 unresolved wikilink(s)" in result.stdout
    assert "Made Up Person" in result.stdout
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --package graph-wiki-cli pytest tests/unit/test_wiki_cli.py::test_ingest_source_cli_warns_on_degraded_and_stripped -v`
Expected: FAIL — the warning strings are not yet printed.

- [ ] **Step 3: Add the warnings to the text-output branch**

In `wiki_cli/main.py`, replace the `else` branch of `ingest_source` (`:215-217`):

```python
    else:
        typer.echo(f"[ok] Ingested: {result.page_path}")
        typer.echo(f"     page_type: {result.page_type}, slug: {result.slug}")
```

with:

```python
    else:
        typer.echo(f"[ok] Ingested: {result.page_path}")
        typer.echo(f"     source_kind: {result.source_kind}, slug: {result.slug}")
        if not result.frontmatter_parsed:
            typer.echo(
                "⚠ frontmatter did not parse — wrote Source page with "
                "source_kind: unknown",
                err=True,
            )
        if result.stripped_wikilinks:
            typer.echo(
                f"⚠ stripped {len(result.stripped_wikilinks)} unresolved "
                f"wikilink(s): {result.stripped_wikilinks}",
                err=True,
            )
```

> Note: warnings go to stderr (`err=True`). `CliRunner` by default mixes stderr into `result.stdout` (it does not separate streams unless `mix_stderr=False`), so the test's `result.stdout` assertions hold. If the repo's `CliRunner` is constructed with `mix_stderr=False` elsewhere, change the test assertions to read `result.output`.

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run --package graph-wiki-cli pytest tests/unit/test_wiki_cli.py::test_ingest_source_cli_warns_on_degraded_and_stripped -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/graph-wiki-cli/src/graph_wiki_cli/wiki_cli/main.py packages/graph-wiki-cli/tests/unit/test_wiki_cli.py
git commit -m "feat(cli): surface degraded-parse + stripped-wikilink warnings on ingest source"
```

---

### Task 7: MCP — expose new fields on `WikiIngestOutput`

**Files:**
- Modify: `packages/graph-wiki-mcp/src/graph_wiki_mcp/server.py:314-322` (`WikiIngestOutput`), `:360-369` (mapping)
- Test: `packages/graph-wiki-mcp/tests/unit/test_mcp_new_tools.py` (add a field-passthrough test)

Per Design Decision #2, the server constructs `WikiIngestOutput` explicitly (not via `asdict`), so the fields must be added to the model **and** mapped. `Field(default_factory=list)` is required for the mutable list default under pydantic.

- [ ] **Step 1: Write the failing test**

Add to `test_mcp_new_tools.py` (it already imports `AsyncMock`, `patch`, `IngestResult`, `WikiIngestInput`, `wiki_ingest`, and a `mock_ctx` pattern — mirror `test_wiki_ingest_dispatches_to_source`):

```python
@pytest.mark.asyncio
async def test_wiki_ingest_source_passes_through_m3_fields() -> None:
    """wiki_ingest surfaces source_kind / stripped_wikilinks / frontmatter_parsed."""
    from unittest.mock import AsyncMock, MagicMock, patch

    from graph_wiki_core.commands.ingest import IngestResult
    from graph_wiki_mcp.server import WikiIngestInput, wiki_ingest

    fake = IngestResult(
        status="ok",
        page_path="sources/doc.md",
        slug="doc",
        title="Doc",
        page_type="source",
        source_path="/x/doc.md",
        cross_refs_updated=1,
        source_kind="unknown",
        stripped_wikilinks=["ghost"],
        frontmatter_parsed=False,
    )

    mock_ctx = MagicMock()
    mock_ctx.report_progress = AsyncMock()

    with patch(
        "graph_wiki_mcp.server.run_ingest_source", new_callable=AsyncMock, return_value=fake
    ):
        out = await wiki_ingest(
            WikiIngestInput(type="source", source_path="/x/doc.md"), mock_ctx
        )

    assert out.source_kind == "unknown"
    assert out.stripped_wikilinks == ["ghost"]
    assert out.frontmatter_parsed is False
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --package graph-wiki-mcp pytest tests/unit/test_mcp_new_tools.py::test_wiki_ingest_source_passes_through_m3_fields -v`
Expected: FAIL with `AttributeError: 'WikiIngestOutput' object has no attribute 'source_kind'`.

- [ ] **Step 3: Add the fields to `WikiIngestOutput`**

In `server.py`, replace the `WikiIngestOutput` class (`:314-322`):

```python
class WikiIngestOutput(BaseModel):
    status: str
    page_path: str
    slug: str
    title: str
    page_type: str
    source_path: str
    cross_refs_updated: int
    entity_uri: str | None = None  # Phase 40: canonical entity URI (None for free-form sources)
```

with:

```python
class WikiIngestOutput(BaseModel):
    status: str
    page_path: str
    slug: str
    title: str
    page_type: str
    source_path: str
    cross_refs_updated: int
    entity_uri: str | None = None  # Phase 40: canonical entity URI (None for free-form sources)
    # Living Wiki M3 Part A (ingest hardening):
    source_kind: str | None = None
    stripped_wikilinks: list[str] = Field(default_factory=list)
    frontmatter_parsed: bool = True
```

- [ ] **Step 4: Map the fields in the return**

In `server.py`, replace the `return WikiIngestOutput(…)` block (`:360-369`):

```python
    return WikiIngestOutput(
        status=result.status,
        page_path=result.page_path,
        slug=result.slug,
        title=result.title,
        page_type=result.page_type,
        source_path=result.source_path,
        cross_refs_updated=result.cross_refs_updated,
        entity_uri=result.entity_uri,
    )
```

with:

```python
    return WikiIngestOutput(
        status=result.status,
        page_path=result.page_path,
        slug=result.slug,
        title=result.title,
        page_type=result.page_type,
        source_path=result.source_path,
        cross_refs_updated=result.cross_refs_updated,
        entity_uri=result.entity_uri,
        source_kind=result.source_kind,
        stripped_wikilinks=result.stripped_wikilinks,
        frontmatter_parsed=result.frontmatter_parsed,
    )
```

- [ ] **Step 5: Run the MCP test to verify it passes**

Run: `uv run --package graph-wiki-mcp pytest tests/unit/test_mcp_new_tools.py -v`
Expected: PASS (new test + existing `wiki_ingest` registration/dispatch tests).

- [ ] **Step 6: Commit**

```bash
git add packages/graph-wiki-mcp/src/graph_wiki_mcp/server.py packages/graph-wiki-mcp/tests/unit/test_mcp_new_tools.py
git commit -m "feat(mcp): expose source_kind/stripped_wikilinks/frontmatter_parsed on wiki_ingest output"
```

---

### Task 8: Full verification + lint

**Files:** none (verification only)

- [ ] **Step 1: Run all three affected package test suites**

```bash
uv run --package graph-wiki-core pytest
uv run --package graph-wiki-cli pytest -m "not integration"
uv run --package graph-wiki-mcp pytest -m "not integration"
```

Expected: all PASS. Pay attention to `test_provenance.py` (it only checks the `# Source:` header on `frontmatter_rules.py`, which is unchanged) and the prompt snapshot tests (regenerated in Task 5).

- [ ] **Step 2: Lint + format**

```bash
uv run ruff check .
uv run ruff format --check packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py packages/graph-wiki-core/src/graph_wiki_core/prompts/ingestor.py packages/graph-wiki-cli/src/graph_wiki_cli/wiki_cli/main.py packages/graph-wiki-mcp/src/graph_wiki_mcp/server.py
```

Expected: clean. (Per `ruff-format-discovery` memory: do not run `ruff format` on explicit package `src/...` paths to "fix" diffs — it would reformat to width 88, not the root's 120. Only format files you actually changed and match the surrounding multi-line style.)

- [ ] **Step 3: Brand gate**

```bash
bash scripts/check-brand.sh
```

Expected: exits 0.

- [ ] **Step 4: Final sanity diff review**

```bash
git log --oneline -8
git diff --stat main
```

Confirm the changes are confined to the seven files in the File Structure section plus the regenerated snapshot.

---

## Self-review notes (author checklist applied)

- **Spec coverage:** D1 always-`sources/` (Task 4 Step 3), D2 `source_kind`/default `unknown` (Tasks 1, 4), D3 `safe_load` + synthesize (Tasks 2, 3, 4), D4 stripped wikilinks surfaced (Tasks 1, 4, 6, 7), D5 `frontmatter_parsed` loud signal (Tasks 1, 4, 6), D6 graph-not-init unchanged (no task — existing `test_run_ingest_source_not_initialized_raises_typed_exception` stays green, verified in Task 8). All spec §5 test cases mapped: parse-robustness (Task 2 + Task 4 `no_frontmatter_synthesizes`), always-Source routing (Task 4 `always_routes_to_sources`), loud surfacing (Task 6), degraded signal (Task 4 + Task 6), graph-not-init (Task 8), idempotence (Task 3).
- **Migration enumerated (spec §5 "Known migration"):** six tests in `test_commands_ingest.py` move from `concepts/` to `sources/` (Task 4 Step 6) — listed by name with exact edits.
- **Type consistency:** `source_kind: str | None`, `stripped_wikilinks: list[str]`, `frontmatter_parsed: bool` are named identically across `IngestResult` (Task 1), `WikiIngestOutput` (Task 7), tests, and CLI. Helper names `_set_source_kind_in_body` / `_synthesize_frontmatter_block` are consistent between Task 3 (definition) and Task 4 (call sites).
- **No placeholders:** every code/edit step shows the exact old and new text and the exact run command + expected result.
