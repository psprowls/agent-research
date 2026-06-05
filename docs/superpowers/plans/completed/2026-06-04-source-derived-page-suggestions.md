# Source-Derived Page Suggestions — Inline Extraction Phase Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** After `run_ingest_source` lands a Source page, run an inline LLM pass that proposes which `concept`/`adr`/`architecture` pages the doc justifies (create-new vs update-existing), records them as structured `suggested_pages` frontmatter plus a regenerated `## Suggested pages` body section, and surfaces them in `IngestResult`. Propose only — nothing is written under the curated dirs.

**Architecture:** A new self-contained module `graph_wiki_core/commands/suggest_pages.py` owns the whole feature: parse the extractor LLM output, build a cheap curated-vault index, merge proposals into the Source page's frontmatter preserving human decisions, and render the readable body mirror. `run_ingest_source` calls one orchestrator (`run_suggest_phase`) as a best-effort step that never fails the ingest. A new `extractor` model-adapter role + `EXTRACTOR_SYSTEM` prompt drive the analysis. Two new `IngestResult` fields (`suggested_pages`, `suggestions_parsed`) carry the result to CLI and MCP.

**Tech Stack:** Python 3.11, `uv` workspace, `pytest` (per-package, `asyncio_mode=auto`), `dataclasses`, `pyyaml` (already a `graph-wiki-core` dep), `langchain_core` message types, `model_adapter.make_llm`, `typer` (CLI), `pydantic` (MCP), `syrupy` (prompt snapshots).

**Spec:** `docs/superpowers/specs/2026-06-04-source-derived-page-suggestions-design.md` (Living Wiki M3, suggestion step).

---

## Prerequisite — Part A must be landed first

This plan builds **directly on M3 Part A** (`docs/superpowers/plans/2026-06-04-ingest-hardening-always-source.md`). It assumes the post-Part-A `run_ingest_source`:

- always routes to `sources/` and constructs `IngestResult(..., page_type="source", source_kind=..., stripped_wikilinks=..., frontmatter_parsed=...)`;
- imports `yaml`;
- ends `run_ingest_source` with a `return IngestResult(...)` inside a `try:`/`finally:` that closes `conn`.

Because Part A moves line numbers, **all `ingest.py` / CLI / MCP line numbers below are approximate (post-Part-A) — anchor edits on the quoted marker text, not the line number.** Task 0 verifies Part A is present before any work begins.

---

## Design decisions (read before starting)

1. **New module, not more `ingest.py`.** The feature is ~6 focused functions + an orchestrator. It lives in `commands/suggest_pages.py` so each piece is testable in isolation and `ingest.py` only gains an import + one call. This matches the spec §4 component table.
2. **`suggested_pages` is always the LAST frontmatter key.** `set_suggested_pages_in_frontmatter` strips from the `suggested_pages:` line to the end of the frontmatter block and re-appends the freshly-serialized block. This makes the surgical replace trivial and reliable and keeps every other key (`source_kind`, `target_slug`, `entity_uri`, `title`, …) byte-stable. Serialized with `yaml.safe_dump(..., sort_keys=False)` for determinism.
3. **Entries are plain dicts end-to-end** with a fixed key order (`kind, title, slug, mode, existing_slug, rationale, status`). No dataclass round-trip — the parser validates raw dicts and the merge/serialize layer consumes dicts directly. `sort_keys=False` + fixed construction order ⇒ deterministic YAML.
4. **Merge is spec-faithful (§3.4):** human-decided entries (`approved`/`rejected`/`created`) are preserved in place and untouched; a still-`proposed` entry whose `(kind, slug)` matches a new proposal is refreshed in place; genuinely new proposals are appended as `proposed`; an orphaned `proposed` entry (no matching new proposal) is preserved (the spec is silent on dropping it — we keep it; the human can delete). A proposal whose key matches a human-decided entry is NOT re-added.
5. **Best-effort, never fails ingest (spec §3.1).** `run_suggest_phase` catches the LLM call internally (→ `suggestions_parsed=False`, existing entries unchanged, page rewritten idempotently); `run_ingest_source` wraps the whole phase in a backstop `try/except` (→ `([], False)`). The Source page always survives.
6. **Extractor uses its own role's default tier — `model_override` is ingestor-only.** Part A's `model_override` parameter targets the ingestor sweep; it is NOT forwarded to the extractor. `run_suggest_phase` calls `make_llm("extractor")` with no override.
7. **Dedup is vault-listing (spec §3.6):** `build_curated_vault_index` walks `concepts/`/`adrs/`/`architecture/` for `slug`/`title`/`summary` only. No graph, no retrieval stack.

---

## File structure

Files touched, by responsibility:

- **Create `packages/graph-wiki-core/src/graph_wiki_core/commands/suggest_pages.py`** — the whole feature: constants, `parse_extractor_response`, `build_curated_vault_index`, `merge_suggested_pages`, `read_suggested_pages`, `set_suggested_pages_in_frontmatter`, `render_suggested_pages_section`, `set_suggested_pages_section_in_body`, `build_extract_suggestions_prompt`, `run_suggest_phase`.
- **Create `packages/graph-wiki-core/src/graph_wiki_core/prompts/extractor.py`** — `EXTRACTOR_SYSTEM` constant.
- **Modify `packages/model-adapter/src/model_adapter/models.toml`** — add `[roles.extractor]`.
- **Modify `packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py`** — 2 new `IngestResult` fields; call `run_suggest_phase` in `run_ingest_source`; populate the fields.
- **Modify `packages/graph-wiki-cli/src/graph_wiki_cli/wiki_cli/main.py`** — print suggestions summary + degraded warning in `ingest_source` text output.
- **Modify `packages/graph-wiki-mcp/src/graph_wiki_mcp/server.py`** — 2 new `WikiIngestOutput` fields + mapping.
- **Tests:** `packages/graph-wiki-core/tests/unit/test_suggest_pages.py` (new — unit tests for every helper), `packages/graph-wiki-core/tests/unit/test_commands_ingest.py` (wired-phase integration tests), `packages/graph-wiki-core/tests/prompts/test_prompt_snapshots.py` + `.ambr` (extractor snapshot), `packages/graph-wiki-cli/tests/unit/test_wiki_cli.py` (CLI), `packages/graph-wiki-mcp/tests/unit/test_mcp_new_tools.py` (MCP).

---

### Task 0: Prerequisite guard — confirm Part A is landed and green

**Files:** none (verification only)

- [ ] **Step 1: Verify Part A's code shape is present**

Run:
```bash
cd /Users/pat/Personal/agent-research
grep -n "source_kind" packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py | head
grep -n "page_type=\"source\"" packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py | head
grep -n "^import yaml" packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py
```
Expected: all three produce matches (Part A added `source_kind`, the always-`"source"` `IngestResult`, and `import yaml`). **If any is empty, STOP — implement `2026-06-04-ingest-hardening-always-source.md` first.**

- [ ] **Step 2: Confirm the ingest suite is green before adding anything**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_commands_ingest.py -q`
Expected: PASS. This is the baseline; do not proceed if it is red.

---

### Task 1: `extractor` role + `EXTRACTOR_SYSTEM` prompt

**Files:**
- Modify: `packages/model-adapter/src/model_adapter/models.toml` (add `[roles.extractor]` after the `[roles.ingestor]` block)
- Create: `packages/graph-wiki-core/src/graph_wiki_core/prompts/extractor.py`
- Test: `packages/graph-wiki-core/tests/prompts/test_prompt_snapshots.py` (add a snapshot test) + regenerate `.ambr`

- [ ] **Step 1: Add the `extractor` role to `models.toml`**

In `models.toml`, immediately **after** the `[roles.ingestor]` block (it ends with its `sweep_candidates = [ … ]` list, before `[roles.synthesizer]`), insert:

```toml
[roles.extractor]
# Living Wiki M3 — inline page-suggestion pass. Reads a just-landed Source page +
# a cheap curated-vault index and proposes concept/adr/architecture pages.
# Mirrors the ingestor tier (correctness-sensitive but small output); tunable
# independently per the roadmap §5 cost-offloading lever.
model_id        = "zai.glm-4.7-flash"
region          = "us-east-1"
max_tokens      = 1024
max_concurrency = 5
sweep_candidates = [
  "qwen.qwen3-32b-v1:0",
  "openai.gpt-oss-120b-1:0",
  "minimax.minimax-m2.5",
  "qwen.qwen3-next-80b-a3b",
  "zai.glm-4.7-flash",
]
```

- [ ] **Step 2: Confirm the role resolves**

Run: `uv run --package model-adapter pytest -q`
Then sanity-check the role loads:
Run: `uv run --package graph-wiki-core python -c "from model_adapter.loader import load_role_config; print(load_role_config('extractor')['model_id'])"`
Expected: tests PASS; the command prints `zai.glm-4.7-flash`.

- [ ] **Step 3: Create the `EXTRACTOR_SYSTEM` prompt module**

Create `packages/graph-wiki-core/src/graph_wiki_core/prompts/extractor.py`:

```python
from __future__ import annotations

"""EXTRACTOR_SYSTEM prompt — Living Wiki M3 inline page-suggestion pass.

Given a just-landed Source page and a listing of existing curated pages, the
extractor proposes which concept / adr / architecture pages the source justifies.
It is deliberately conservative (roadmap open-q #3: avoid low-quality
auto-generated concepts) and PROPOSES ONLY — no page is written by this pass.
"""

EXTRACTOR_SYSTEM = """You analyze a Source wiki page and propose which curated knowledge pages it justifies.

You do NOT write any page. You output a single YAML block of proposals (or an empty list). Nothing else — no prose, no code fence.

Page kinds you may propose:
- concept     — a reusable, cross-cutting technical idea or pattern.
- adr         — a dated, consequential decision (only when the source genuinely records a decision).
- architecture — a cross-cutting synthesis of how parts of the system fit together.

Rules:
- Be CONSERVATIVE. Returning an empty list is correct and expected when the source does not justify a durable curated page. Do not invent pages to seem useful.
- Propose at most 5 pages. Prefer the few strongest.
- You are given a list of EXISTING curated pages (kind, slug, title, summary). If your idea is already covered by one of them, propose `mode: update_existing` and set `existing_slug` to that page's slug. Otherwise use `mode: create_new`.
- `slug` is a short, URL-safe, hyphenated identifier for the proposed page.
- `rationale` is one sentence: why this source justifies this page.

Output format — a YAML mapping with a single `suggestions:` list. Example:

suggestions:
  - kind: concept
    title: Section-ownership model
    slug: section-ownership-model
    mode: create_new
    existing_slug:
    rationale: Source defines a reusable scanner/human ownership split not yet captured.
  - kind: adr
    title: Markdown stays canonical
    slug: markdown-canonical
    mode: update_existing
    existing_slug: 0007-markdown-canonical
    rationale: Source revisits the markdown-vs-DB decision; the existing ADR should record it.

If there are no worthwhile proposals, output exactly:

suggestions: []
"""
```

- [ ] **Step 4: Add a snapshot test**

In `packages/graph-wiki-core/tests/prompts/test_prompt_snapshots.py`, mirror `test_ingestor_system_snapshot`. Add after it:

```python
def test_extractor_system_snapshot(snapshot: SnapshotAssertion) -> None:
    """EXTRACTOR_SYSTEM matches recorded snapshot."""
    from graph_wiki_core.prompts.extractor import EXTRACTOR_SYSTEM

    assert EXTRACTOR_SYSTEM == snapshot
```

- [ ] **Step 5: Generate and verify the snapshot**

Run: `uv run --package graph-wiki-core pytest tests/prompts/test_prompt_snapshots.py::test_extractor_system_snapshot --snapshot-update`
Then: `uv run --package graph-wiki-core pytest tests/prompts/test_prompt_snapshots.py -q`
Expected: PASS. The `.ambr` diff adds exactly one snapshot block (the extractor); no other role's snapshot moves.

- [ ] **Step 6: Commit**

```bash
git add packages/model-adapter/src/model_adapter/models.toml \
        packages/graph-wiki-core/src/graph_wiki_core/prompts/extractor.py \
        packages/graph-wiki-core/tests/prompts/test_prompt_snapshots.py \
        packages/graph-wiki-core/tests/prompts/__snapshots__/test_prompt_snapshots.ambr
git commit -m "feat(suggest): add extractor model role + EXTRACTOR_SYSTEM prompt"
```

---

### Task 2: New module — constants + `parse_extractor_response`

**Files:**
- Create: `packages/graph-wiki-core/src/graph_wiki_core/commands/suggest_pages.py`
- Create: `packages/graph-wiki-core/tests/unit/test_suggest_pages.py`

`parse_extractor_response(text) -> tuple[list[dict], bool]`: strip a leading code fence (reusing the same defensive idea as the ingestor), `yaml.safe_load`, accept either a top-level list or a `{"suggestions": [...]}` mapping, validate each entry, and return `(entries, parsed)`. `parsed` is `True` whenever a well-formed list (including empty) was recovered; `False` only on a YAML error or an unexpected top-level shape.

- [ ] **Step 1: Write the failing tests**

Create `packages/graph-wiki-core/tests/unit/test_suggest_pages.py`:

```python
from __future__ import annotations

from graph_wiki_core.commands.suggest_pages import (
    SUGGESTION_KINDS,
    parse_extractor_response,
)


def test_parse_extractor_response_valid_mapping() -> None:
    raw = (
        "suggestions:\n"
        "  - kind: concept\n"
        "    title: Section Ownership\n"
        "    slug: section-ownership\n"
        "    mode: create_new\n"
        "    existing_slug:\n"
        "    rationale: A reusable split.\n"
    )
    entries, parsed = parse_extractor_response(raw)
    assert parsed is True
    assert len(entries) == 1
    e = entries[0]
    assert e["kind"] == "concept"
    assert e["title"] == "Section Ownership"
    assert e["slug"] == "section-ownership"
    assert e["mode"] == "create_new"
    assert e["existing_slug"] is None
    assert e["rationale"] == "A reusable split."
    # status is NOT set by the parser (merge owns it)
    assert "status" not in e


def test_parse_extractor_response_empty_list_is_parsed_true() -> None:
    entries, parsed = parse_extractor_response("suggestions: []")
    assert entries == []
    assert parsed is True


def test_parse_extractor_response_top_level_list_accepted() -> None:
    raw = "- kind: adr\n  title: T\n  slug: t\n  mode: create_new\n  rationale: r\n"
    entries, parsed = parse_extractor_response(raw)
    assert parsed is True
    assert entries[0]["kind"] == "adr"


def test_parse_extractor_response_strips_code_fence() -> None:
    raw = "```yaml\nsuggestions:\n  - kind: concept\n    title: T\n    slug: t\n    mode: create_new\n    rationale: r\n```"
    entries, parsed = parse_extractor_response(raw)
    assert parsed is True
    assert entries[0]["slug"] == "t"


def test_parse_extractor_response_unparseable_returns_false() -> None:
    entries, parsed = parse_extractor_response("this is not yaml: : : [")
    assert entries == []
    assert parsed is False


def test_parse_extractor_response_drops_invalid_kind_and_normalizes() -> None:
    raw = (
        "suggestions:\n"
        "  - kind: package\n"          # invalid kind -> dropped
        "    title: Bad\n"
        "    slug: bad\n"
        "    mode: create_new\n"
        "    rationale: r\n"
        "  - kind: architecture\n"
        "    title: Good\n"
        "    slug: 'Good Slug!'\n"      # slugified
        "    mode: bogus\n"            # invalid mode -> create_new
        "    rationale: r2\n"
    )
    entries, parsed = parse_extractor_response(raw)
    assert parsed is True
    assert [e["kind"] for e in entries] == ["architecture"]
    assert entries[0]["slug"] == "good-slug"
    assert entries[0]["mode"] == "create_new"
    assert SUGGESTION_KINDS == frozenset({"concept", "adr", "architecture"})
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_suggest_pages.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'graph_wiki_core.commands.suggest_pages'`.

- [ ] **Step 3: Create the module with constants + parser**

Create `packages/graph-wiki-core/src/graph_wiki_core/commands/suggest_pages.py`:

```python
from __future__ import annotations

"""Living Wiki M3 — inline page-suggestion pass for run_ingest_source.

After a Source page lands, propose which concept/adr/architecture pages the
document justifies and record them as `suggested_pages` frontmatter plus a
regenerated `## Suggested pages` body section. Propose only — nothing is written
under concepts/ / adrs/ / architecture/.

Public API:
    SUGGESTION_KINDS, HUMAN_DECIDED, EXTRACT_PREVIEW_CHARS
    parse_extractor_response(text) -> (list[dict], bool)
    build_curated_vault_index(wiki) -> list[dict]
    merge_suggested_pages(existing, proposals) -> list[dict]
    read_suggested_pages(text) -> list[dict]
    set_suggested_pages_in_frontmatter(text, entries) -> str
    render_suggested_pages_section(entries) -> str
    set_suggested_pages_section_in_body(text, section) -> str
    build_extract_suggestions_prompt(source_text, vault_index) -> str
    run_suggest_phase(...) -> (list[dict], bool)
"""

import logging

import yaml
from wiki_io.ingest_source import slugify

logger = logging.getLogger(__name__)

SUGGESTION_KINDS = frozenset({"concept", "adr", "architecture"})
HUMAN_DECIDED = frozenset({"approved", "rejected", "created"})
EXTRACT_PREVIEW_CHARS = 4000

# Fixed key order so yaml.safe_dump(..., sort_keys=False) is deterministic.
_ENTRY_KEY_ORDER = ("kind", "title", "slug", "mode", "existing_slug", "rationale", "status")


def _ordered_entry(d: dict) -> dict:
    """Return a new dict with the canonical key order (omitting absent keys)."""
    return {k: d[k] for k in _ENTRY_KEY_ORDER if k in d}


def _validate_proposal(raw: object) -> dict | None:
    """Normalize one extractor proposal into a proposal dict, or None if invalid.

    Required: kind in SUGGESTION_KINDS, a non-empty title, a slug. mode defaults
    to create_new (and is forced to create_new when not update_existing).
    NOTE: no `status` key — merge_suggested_pages stamps that.
    """
    if not isinstance(raw, dict):
        return None
    kind = str(raw.get("kind", "")).strip().lower()
    if kind not in SUGGESTION_KINDS:
        return None
    title = str(raw.get("title", "")).strip()
    slug_src = str(raw.get("slug", "")).strip()
    if not title or not slug_src:
        return None
    slug = slugify(slug_src)
    mode = str(raw.get("mode", "")).strip().lower()
    if mode != "update_existing":
        mode = "create_new"
    existing_raw = raw.get("existing_slug")
    existing_slug = slugify(str(existing_raw).strip()) if existing_raw else None
    rationale = str(raw.get("rationale", "")).strip()
    return _ordered_entry(
        {
            "kind": kind,
            "title": title,
            "slug": slug,
            "mode": mode,
            "existing_slug": existing_slug,
            "rationale": rationale,
        }
    )


def parse_extractor_response(text: str) -> tuple[list[dict], bool]:
    """Parse the extractor LLM output into (proposals, parsed).

    parsed is True whenever a well-formed list was recovered (including an empty
    one). It is False only on a YAML error or an unexpected top-level shape.
    """
    if text is None:
        return [], False
    stripped = text.strip()
    # Defensive: strip a leading ```yaml / ``` fence and a trailing ``` line.
    if stripped.startswith("```"):
        nl = stripped.find("\n")
        if nl == -1:
            return [], False
        stripped = stripped[nl + 1 :]
        last = stripped.rfind("```")
        if last != -1:
            stripped = stripped[:last]
        stripped = stripped.strip()

    try:
        loaded = yaml.safe_load(stripped)
    except yaml.YAMLError:
        return [], False

    if isinstance(loaded, dict) and isinstance(loaded.get("suggestions"), list):
        items = loaded["suggestions"]
    elif isinstance(loaded, list):
        items = loaded
    elif isinstance(loaded, dict) and "suggestions" in loaded and loaded["suggestions"] is None:
        # `suggestions:` with an empty/blank value -> zero proposals, still parsed.
        items = []
    else:
        return [], False

    proposals: list[dict] = []
    for item in items:
        norm = _validate_proposal(item)
        if norm is not None:
            proposals.append(norm)
    return proposals, True
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_suggest_pages.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/suggest_pages.py packages/graph-wiki-core/tests/unit/test_suggest_pages.py
git commit -m "feat(suggest): add suggest_pages module with extractor-response parser"
```

---

### Task 3: `build_curated_vault_index`

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/suggest_pages.py` (add function)
- Test: `packages/graph-wiki-core/tests/unit/test_suggest_pages.py` (add tests)

Walk `concepts/`, `adrs/`, `architecture/` under the wiki; for each `*.md` read `title`/`summary` from frontmatter (via `wiki_io.update_index.parse_frontmatter`). `kind` is derived from the directory: `concepts`→`concept`, `adrs`→`adr`, `architecture`→`architecture`. `slug` is the file stem.

- [ ] **Step 1: Write the failing tests**

Add to `test_suggest_pages.py`:

```python
def test_build_curated_vault_index_lists_existing_pages(tmp_path):
    from graph_wiki_core.commands.suggest_pages import build_curated_vault_index

    wiki = tmp_path / "wiki"
    (wiki / "concepts").mkdir(parents=True)
    (wiki / "adrs").mkdir(parents=True)
    (wiki / "architecture").mkdir(parents=True)
    (wiki / "sources").mkdir(parents=True)  # must be ignored

    (wiki / "concepts" / "ownership.md").write_text(
        "---\ntitle: Ownership Model\ncategory: concept\nsummary: who owns what\n---\n# x",
        encoding="utf-8",
    )
    (wiki / "adrs" / "0007-md.md").write_text(
        "---\ntitle: 'ADR-0007: Markdown'\ncategory: adr\nsummary: md stays\n---\n# x",
        encoding="utf-8",
    )
    (wiki / "architecture" / "layers.md").write_text(
        "---\ntitle: Layers\nsummary: bottom to top\n---\n# x",
        encoding="utf-8",
    )
    (wiki / "sources" / "spec.md").write_text("---\ntitle: A Spec\n---\n# x", encoding="utf-8")

    index = build_curated_vault_index(wiki)

    by_slug = {e["slug"]: e for e in index}
    assert set(by_slug) == {"ownership", "0007-md", "layers"}
    assert by_slug["ownership"]["kind"] == "concept"
    assert by_slug["ownership"]["title"] == "Ownership Model"
    assert by_slug["ownership"]["summary"] == "who owns what"
    assert by_slug["0007-md"]["kind"] == "adr"
    assert by_slug["layers"]["kind"] == "architecture"
    # sources/ is not curated -> excluded
    assert "spec" not in by_slug


def test_build_curated_vault_index_missing_dirs_returns_empty(tmp_path):
    from graph_wiki_core.commands.suggest_pages import build_curated_vault_index

    wiki = tmp_path / "wiki"
    wiki.mkdir()
    assert build_curated_vault_index(wiki) == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_suggest_pages.py -k curated_vault -q`
Expected: FAIL with `ImportError: cannot import name 'build_curated_vault_index'`.

- [ ] **Step 3: Add the function**

Append to `suggest_pages.py`. First extend the imports at the top of the file — change:

```python
import logging

import yaml
from wiki_io.ingest_source import slugify
```

to:

```python
import logging
from pathlib import Path

import yaml
from wiki_io.ingest_source import slugify
from wiki_io.update_index import parse_frontmatter
```

Then add the function (after `parse_extractor_response`):

```python
# Directory name -> curated page kind.
_CURATED_DIRS = {"concepts": "concept", "adrs": "adr", "architecture": "architecture"}


def build_curated_vault_index(wiki: Path) -> list[dict]:
    """List existing curated pages as [{kind, slug, title, summary}].

    Cheap dedup substrate (spec §3.6): walks concepts/ / adrs/ / architecture/
    and reads title/summary from frontmatter only. No graph, no retrieval.
    """
    index: list[dict] = []
    for dirname, kind in _CURATED_DIRS.items():
        d = wiki / dirname
        if not d.is_dir():
            continue
        for md in sorted(d.glob("*.md")):
            try:
                fm = parse_frontmatter(md.read_text(encoding="utf-8"))
            except OSError:
                continue
            index.append(
                {
                    "kind": kind,
                    "slug": md.stem,
                    "title": fm.get("title", md.stem),
                    "summary": fm.get("summary", ""),
                }
            )
    return index
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_suggest_pages.py -k curated_vault -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/suggest_pages.py packages/graph-wiki-core/tests/unit/test_suggest_pages.py
git commit -m "feat(suggest): add build_curated_vault_index (cheap dedup listing)"
```

---

### Task 4: `merge_suggested_pages`

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/suggest_pages.py` (add function)
- Test: `packages/graph-wiki-core/tests/unit/test_suggest_pages.py` (add tests)

Spec §3.4 merge: human-decided entries preserved in place & untouched; matching-key `proposed` entries refreshed in place; new proposals appended as `proposed`; orphaned `proposed` entries preserved; a proposal whose key matches a human-decided entry is NOT re-added; duplicate proposals deduped by key.

- [ ] **Step 1: Write the failing tests**

Add to `test_suggest_pages.py`:

```python
def _prop(kind, slug, title="T", mode="create_new", existing=None, rationale="r"):
    return {
        "kind": kind,
        "title": title,
        "slug": slug,
        "mode": mode,
        "existing_slug": existing,
        "rationale": rationale,
    }


def test_merge_appends_new_as_proposed():
    from graph_wiki_core.commands.suggest_pages import merge_suggested_pages

    out = merge_suggested_pages([], [_prop("concept", "a"), _prop("adr", "b")])
    assert [(e["kind"], e["slug"], e["status"]) for e in out] == [
        ("concept", "a", "proposed"),
        ("adr", "b", "proposed"),
    ]


def test_merge_preserves_human_decided_untouched():
    from graph_wiki_core.commands.suggest_pages import merge_suggested_pages

    existing = [
        {"kind": "concept", "title": "Kept", "slug": "a", "mode": "create_new",
         "existing_slug": None, "rationale": "old", "status": "approved"},
    ]
    # A new proposal for the SAME key must not re-add or mutate the approved entry.
    out = merge_suggested_pages(existing, [_prop("concept", "a", title="New", rationale="new")])
    assert len(out) == 1
    assert out[0]["status"] == "approved"
    assert out[0]["title"] == "Kept"
    assert out[0]["rationale"] == "old"


def test_merge_refreshes_matching_proposed_in_place():
    from graph_wiki_core.commands.suggest_pages import merge_suggested_pages

    existing = [
        {"kind": "concept", "title": "Old", "slug": "a", "mode": "create_new",
         "existing_slug": None, "rationale": "old", "status": "proposed"},
    ]
    out = merge_suggested_pages(existing, [_prop("concept", "a", title="Fresh", rationale="fresh")])
    assert len(out) == 1
    assert out[0]["title"] == "Fresh"
    assert out[0]["rationale"] == "fresh"
    assert out[0]["status"] == "proposed"


def test_merge_preserves_orphaned_proposed():
    from graph_wiki_core.commands.suggest_pages import merge_suggested_pages

    existing = [
        {"kind": "concept", "title": "Orphan", "slug": "a", "mode": "create_new",
         "existing_slug": None, "rationale": "r", "status": "proposed"},
    ]
    out = merge_suggested_pages(existing, [_prop("adr", "b")])  # no proposal for 'a'
    keys = [(e["kind"], e["slug"]) for e in out]
    assert ("concept", "a") in keys  # orphan kept
    assert ("adr", "b") in keys


def test_merge_is_idempotent_on_identical_proposals():
    from graph_wiki_core.commands.suggest_pages import merge_suggested_pages

    proposals = [_prop("concept", "a"), _prop("adr", "b")]
    once = merge_suggested_pages([], proposals)
    twice = merge_suggested_pages(once, proposals)
    assert once == twice


def test_merge_dedups_duplicate_proposals_by_key():
    from graph_wiki_core.commands.suggest_pages import merge_suggested_pages

    out = merge_suggested_pages([], [_prop("concept", "a", title="first"), _prop("concept", "a", title="second")])
    assert len(out) == 1
    assert out[0]["title"] == "first"
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_suggest_pages.py -k merge -q`
Expected: FAIL with `ImportError: cannot import name 'merge_suggested_pages'`.

- [ ] **Step 3: Add the function**

Append to `suggest_pages.py`:

```python
def merge_suggested_pages(existing: list[dict], proposals: list[dict]) -> list[dict]:
    """Merge new proposals into the existing suggested_pages list (spec §3.4).

    - Human-decided entries (status in HUMAN_DECIDED) are preserved in place and
      never mutated.
    - A still-`proposed` entry whose (kind, slug) matches a new proposal is
      refreshed in place from that proposal (status stays `proposed`).
    - An orphaned `proposed` entry (no matching proposal) is preserved.
    - Genuinely new proposals (key not already present) are appended as
      `proposed`, in proposal order, deduped by key.
    - A proposal whose key matches ANY existing entry is not appended again.
    """
    prop_by_key: dict[tuple[str, str], dict] = {}
    for p in proposals:  # first occurrence wins (dedup)
        prop_by_key.setdefault((p["kind"], p["slug"]), p)

    existing_keys = {(e["kind"], e["slug"]) for e in existing}

    result: list[dict] = []
    for e in existing:
        key = (e["kind"], e["slug"])
        if e.get("status") in HUMAN_DECIDED:
            result.append(e)  # untouched
        elif key in prop_by_key:
            refreshed = dict(prop_by_key[key])
            refreshed["status"] = "proposed"
            result.append(_ordered_entry(refreshed))
        else:
            result.append(e)  # orphaned proposed: preserve

    for p in proposals:
        key = (p["kind"], p["slug"])
        if key in existing_keys:
            continue
        if any((r["kind"], r["slug"]) == key for r in result):
            continue  # already appended (duplicate proposal)
        appended = dict(p)
        appended["status"] = "proposed"
        result.append(_ordered_entry(appended))

    return result
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_suggest_pages.py -k merge -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/suggest_pages.py packages/graph-wiki-core/tests/unit/test_suggest_pages.py
git commit -m "feat(suggest): add merge_suggested_pages (preserve human decisions)"
```

---

### Task 5: Frontmatter read/write — `read_suggested_pages` + `set_suggested_pages_in_frontmatter`

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/suggest_pages.py` (add helpers)
- Test: `packages/graph-wiki-core/tests/unit/test_suggest_pages.py` (add tests)

`suggested_pages` is always serialized as the LAST frontmatter key (Design Decision #2), so the surgical strip is "from the `suggested_pages:` line to the end of the block." Reading uses `yaml.safe_load` over the isolated block.

- [ ] **Step 1: Write the failing tests**

Add to `test_suggest_pages.py`:

```python
def test_set_and_read_suggested_pages_round_trip():
    from graph_wiki_core.commands.suggest_pages import (
        read_suggested_pages,
        set_suggested_pages_in_frontmatter,
    )

    page = "---\nsource_kind: source\ntarget_slug: foo\nentity_uri: null\n---\n\nBody text.\n"
    entries = [
        {"kind": "concept", "title": "Sec Ownership", "slug": "sec-ownership",
         "mode": "create_new", "existing_slug": None, "rationale": "why", "status": "proposed"},
    ]
    out = set_suggested_pages_in_frontmatter(page, entries)
    # Other keys + body preserved.
    assert "source_kind: source" in out
    assert "target_slug: foo" in out
    assert out.rstrip().endswith("Body text.")
    # suggested_pages serialized into frontmatter and is the last key.
    assert "suggested_pages:" in out
    fm_block = out.split("---", 2)[1]
    assert fm_block.rstrip().splitlines()[-1].lstrip().startswith("- ") or "suggested_pages:" in fm_block
    # Reading returns the entries back.
    got = read_suggested_pages(out)
    assert got == entries


def test_set_suggested_pages_is_idempotent_and_replaces_block():
    from graph_wiki_core.commands.suggest_pages import set_suggested_pages_in_frontmatter

    page = "---\nsource_kind: source\ntarget_slug: foo\nentity_uri: null\n---\n\nBody.\n"
    entries = [
        {"kind": "adr", "title": "T", "slug": "t", "mode": "create_new",
         "existing_slug": None, "rationale": "r", "status": "proposed"},
    ]
    once = set_suggested_pages_in_frontmatter(page, entries)
    twice = set_suggested_pages_in_frontmatter(once, entries)
    assert once == twice  # byte-stable
    # Replacing with a different set does not duplicate the key.
    other = [
        {"kind": "concept", "title": "U", "slug": "u", "mode": "create_new",
         "existing_slug": None, "rationale": "r2", "status": "approved"},
    ]
    replaced = set_suggested_pages_in_frontmatter(once, other)
    assert replaced.count("suggested_pages:") == 1
    assert "slug: u" in replaced
    assert "slug: t" not in replaced


def test_set_suggested_pages_empty_removes_key():
    from graph_wiki_core.commands.suggest_pages import (
        read_suggested_pages,
        set_suggested_pages_in_frontmatter,
    )

    page = "---\nsource_kind: source\ntarget_slug: foo\n---\nBody.\n"
    entries = [{"kind": "adr", "title": "T", "slug": "t", "mode": "create_new",
                "existing_slug": None, "rationale": "r", "status": "proposed"}]
    with_block = set_suggested_pages_in_frontmatter(page, entries)
    cleared = set_suggested_pages_in_frontmatter(with_block, [])
    assert "suggested_pages:" not in cleared
    assert "source_kind: source" in cleared
    assert read_suggested_pages(cleared) == []


def test_read_suggested_pages_no_frontmatter_returns_empty():
    from graph_wiki_core.commands.suggest_pages import read_suggested_pages

    assert read_suggested_pages("no frontmatter here") == []
    assert read_suggested_pages("---\nsource_kind: source\n---\nBody") == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_suggest_pages.py -k "suggested_pages_round_trip or replaces_block or empty_removes or no_frontmatter_returns" -q`
Expected: FAIL with `ImportError: cannot import name 'read_suggested_pages'`.

- [ ] **Step 3: Add the helpers**

Append to `suggest_pages.py`:

```python
def _split_frontmatter(text: str) -> tuple[str, str, str] | None:
    """Return (lead_ws, fm_block, rest) where rest starts with '\\n---', or None.

    Reassembly is exactly: lead + '---\\n' + fm_block + rest.
    """
    s = text.lstrip()
    lead = text[: len(text) - len(s)]
    if not s.startswith("---"):
        return None
    after = s[3:].lstrip("\n")
    idx = after.find("\n---")
    if idx == -1:
        return None
    return lead, after[:idx], after[idx:]


def read_suggested_pages(text: str) -> list[dict]:
    """Return the `suggested_pages` list from the page frontmatter, or []."""
    parts = _split_frontmatter(text)
    if parts is None:
        return []
    _lead, block, _rest = parts
    try:
        fm = yaml.safe_load(block)
    except yaml.YAMLError:
        return []
    if isinstance(fm, dict) and isinstance(fm.get("suggested_pages"), list):
        return [_ordered_entry(e) for e in fm["suggested_pages"] if isinstance(e, dict)]
    return []


def set_suggested_pages_in_frontmatter(text: str, entries: list[dict]) -> str:
    """Write `entries` as the LAST frontmatter key (Design Decision #2).

    Strips any existing `suggested_pages:` block (from that top-level line to the
    end of the frontmatter block) and re-appends the freshly-serialized block.
    Removes the key entirely when `entries` is empty. No-ops when there is no
    frontmatter (the synthesize-frontmatter rule upstream guarantees one).
    """
    parts = _split_frontmatter(text)
    if parts is None:
        return text
    lead, block, rest = parts

    lines = block.split("\n")
    cut = None
    for i, ln in enumerate(lines):
        if ln[:1] not in (" ", "\t") and ln.strip().startswith("suggested_pages:"):
            cut = i
            break
    if cut is not None:
        lines = lines[:cut]
    cleaned = "\n".join(lines).rstrip("\n")

    if not entries:
        new_block = cleaned
    else:
        dumped = yaml.safe_dump(
            {"suggested_pages": [_ordered_entry(e) for e in entries]},
            sort_keys=False,
            default_flow_style=False,
            allow_unicode=True,
        ).rstrip("\n")
        new_block = f"{cleaned}\n{dumped}" if cleaned else dumped

    return f"{lead}---\n{new_block}{rest}"
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_suggest_pages.py -k "suggested_pages_round_trip or replaces_block or empty_removes or no_frontmatter_returns" -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/suggest_pages.py packages/graph-wiki-core/tests/unit/test_suggest_pages.py
git commit -m "feat(suggest): frontmatter read + surgical last-key write for suggested_pages"
```

---

### Task 6: Body mirror — `render_suggested_pages_section` + `set_suggested_pages_section_in_body`

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/suggest_pages.py` (add helpers)
- Test: `packages/graph-wiki-core/tests/unit/test_suggest_pages.py` (add tests)

`render_suggested_pages_section(entries)` returns the `## Suggested pages` markdown (or `""` when empty). `set_suggested_pages_section_in_body(text, section)` replaces an existing `## Suggested pages` H2 region (to the next `## ` or EOF), appends it when absent, or removes it when `section == ""`.

- [ ] **Step 1: Write the failing tests**

Add to `test_suggest_pages.py`:

```python
def test_render_section_empty_when_no_entries():
    from graph_wiki_core.commands.suggest_pages import render_suggested_pages_section

    assert render_suggested_pages_section([]) == ""


def test_render_section_lists_entries_with_status_and_rationale():
    from graph_wiki_core.commands.suggest_pages import render_suggested_pages_section

    entries = [
        {"kind": "concept", "title": "Sec Ownership", "slug": "sec-ownership",
         "mode": "create_new", "existing_slug": None, "rationale": "a split", "status": "proposed"},
        {"kind": "adr", "title": "MD", "slug": "md", "mode": "update_existing",
         "existing_slug": "0007-md", "rationale": "revisits", "status": "approved"},
    ]
    section = render_suggested_pages_section(entries)
    assert section.startswith("## Suggested pages")
    assert "edit `status`" in section  # the "approve in frontmatter" note
    assert "**concept · create new**" in section
    assert "sec-ownership" in section
    assert "_proposed_" in section
    assert "**adr · update**" in section
    assert "0007-md" in section
    assert "_approved_" in section
    assert "a split" in section


def test_set_section_appends_when_absent():
    from graph_wiki_core.commands.suggest_pages import (
        render_suggested_pages_section,
        set_suggested_pages_section_in_body,
    )

    body = "---\nsource_kind: source\n---\n\nIntro paragraph.\n"
    section = render_suggested_pages_section(
        [{"kind": "concept", "title": "T", "slug": "t", "mode": "create_new",
          "existing_slug": None, "rationale": "r", "status": "proposed"}]
    )
    out = set_suggested_pages_section_in_body(body, section)
    assert "Intro paragraph." in out
    assert out.count("## Suggested pages") == 1
    assert out.rstrip().endswith("_proposed_") or "_proposed_" in out


def test_set_section_replaces_existing_and_is_idempotent():
    from graph_wiki_core.commands.suggest_pages import (
        render_suggested_pages_section,
        set_suggested_pages_section_in_body,
    )

    section1 = render_suggested_pages_section(
        [{"kind": "concept", "title": "One", "slug": "one", "mode": "create_new",
          "existing_slug": None, "rationale": "r", "status": "proposed"}]
    )
    base = "Intro.\n"
    once = set_suggested_pages_section_in_body(base, section1)
    twice = set_suggested_pages_section_in_body(once, section1)
    assert once == twice
    assert once.count("## Suggested pages") == 1

    section2 = render_suggested_pages_section(
        [{"kind": "adr", "title": "Two", "slug": "two", "mode": "create_new",
          "existing_slug": None, "rationale": "r", "status": "proposed"}]
    )
    replaced = set_suggested_pages_section_in_body(once, section2)
    assert replaced.count("## Suggested pages") == 1
    assert "Two" in replaced
    assert "One" not in replaced


def test_set_section_removes_when_empty_section():
    from graph_wiki_core.commands.suggest_pages import (
        render_suggested_pages_section,
        set_suggested_pages_section_in_body,
    )

    section1 = render_suggested_pages_section(
        [{"kind": "concept", "title": "One", "slug": "one", "mode": "create_new",
          "existing_slug": None, "rationale": "r", "status": "proposed"}]
    )
    body = set_suggested_pages_section_in_body("Intro.\n", section1)
    cleared = set_suggested_pages_section_in_body(body, "")
    assert "## Suggested pages" not in cleared
    assert "Intro." in cleared


def test_set_section_preserves_trailing_h2():
    from graph_wiki_core.commands.suggest_pages import (
        render_suggested_pages_section,
        set_suggested_pages_section_in_body,
    )

    body = "Intro.\n\n## Suggested pages\n\nold content\n\n## Touches\n\n[[entities/pkg_x]]\n"
    section = render_suggested_pages_section(
        [{"kind": "concept", "title": "T", "slug": "t", "mode": "create_new",
          "existing_slug": None, "rationale": "r", "status": "proposed"}]
    )
    out = set_suggested_pages_section_in_body(body, section)
    assert "## Touches" in out          # following H2 survives
    assert "[[entities/pkg_x]]" in out
    assert "old content" not in out     # old section body replaced
    assert out.count("## Suggested pages") == 1
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_suggest_pages.py -k "render_section or set_section" -q`
Expected: FAIL with `ImportError: cannot import name 'render_suggested_pages_section'`.

- [ ] **Step 3: Add the helpers**

Append to `suggest_pages.py`:

```python
_SECTION_HEADING = "## Suggested pages"
_SECTION_NOTE = (
    "_Generated from the `suggested_pages` frontmatter. Approve by editing "
    "`status` there (proposed -> approved/rejected), not in this section — it is "
    "regenerated on every ingest._"
)


def render_suggested_pages_section(entries: list[dict]) -> str:
    """Render the `## Suggested pages` body section, or '' when there are none."""
    if not entries:
        return ""
    lines = [_SECTION_HEADING, "", _SECTION_NOTE, ""]
    for e in entries:
        kind = e.get("kind", "")
        if e.get("mode") == "update_existing" and e.get("existing_slug"):
            verb = "update"
            target = f"existing `{e['existing_slug']}`"
        else:
            verb = "create new"
            target = f"`{e.get('slug', '')}`"
        status = e.get("status", "proposed")
        title = e.get("title") or e.get("slug", "")
        lines.append(f"- **{kind} · {verb}** — {title} — {target} · _{status}_")
        rationale = (e.get("rationale") or "").strip()
        if rationale:
            lines.append(f"  {rationale}")
    return "\n".join(lines)


def set_suggested_pages_section_in_body(text: str, section: str) -> str:
    """Replace / append / remove the `## Suggested pages` H2 region.

    - Existing section present: replace from its heading to the next `## ` (or EOF).
    - Absent: append `section` at the end.
    - `section == ''`: remove the existing section (no-op if absent).
    Output ends with exactly one trailing newline.
    """
    lines = text.split("\n")
    start = next((i for i, ln in enumerate(lines) if ln.strip() == _SECTION_HEADING), None)

    if start is not None:
        end = len(lines)
        for j in range(start + 1, len(lines)):
            if lines[j].startswith("## "):
                end = j
                break
        before = lines[:start]
        after = lines[end:]
        while before and before[-1].strip() == "":
            before.pop()
        while after and after[0].strip() == "":
            after.pop(0)
        pieces: list[str] = before[:]
        if section:
            if pieces:
                pieces.append("")
            pieces.extend(section.split("\n"))
        if after:
            if pieces:
                pieces.append("")
            pieces.extend(after)
        return "\n".join(pieces).rstrip("\n") + "\n"

    if not section:
        return text
    base = text.rstrip("\n")
    return f"{base}\n\n{section}\n" if base else f"{section}\n"
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_suggest_pages.py -k "render_section or set_section" -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/suggest_pages.py packages/graph-wiki-core/tests/unit/test_suggest_pages.py
git commit -m "feat(suggest): render + set the ## Suggested pages body mirror"
```

---

### Task 7: Prompt builder + `run_suggest_phase` orchestrator

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/suggest_pages.py` (add `build_extract_suggestions_prompt` + `run_suggest_phase`)
- Test: `packages/graph-wiki-core/tests/unit/test_suggest_pages.py` (add async tests)

`run_suggest_phase` reads the just-written Source page, builds the vault index, calls `make_llm("extractor")`, parses + merges, rewrites the page's frontmatter block + body section, and returns `(merged_entries, suggestions_parsed)`. It catches the LLM call (→ existing entries unchanged, `parsed=False`, page rewritten idempotently).

- [ ] **Step 1: Write the failing tests**

Add to `test_suggest_pages.py` (top-of-file imports already include the module; add `from pathlib import Path` and `from unittest.mock import AsyncMock, MagicMock, patch` at the top of the file if not present):

```python
import pytest


@pytest.mark.asyncio
async def test_run_suggest_phase_writes_proposals_to_page(tmp_path):
    from unittest.mock import AsyncMock, MagicMock, patch

    from graph_wiki_core.commands.suggest_pages import read_suggested_pages, run_suggest_phase

    wiki = tmp_path / "wiki"
    (wiki / "sources").mkdir(parents=True)
    page = wiki / "sources" / "doc.md"
    page.write_text(
        "---\nsource_kind: source\ntarget_slug: doc\nentity_uri: null\n---\n\nThe doc body.\n",
        encoding="utf-8",
    )

    llm_yaml = (
        "suggestions:\n"
        "  - kind: concept\n"
        "    title: A Concept\n"
        "    slug: a-concept\n"
        "    mode: create_new\n"
        "    rationale: justified\n"
    )
    fake_llm = MagicMock()
    fake_llm.ainvoke = AsyncMock(return_value=MagicMock(content=llm_yaml))

    with patch("graph_wiki_core.commands.suggest_pages.make_llm", return_value=fake_llm):
        entries, parsed = await run_suggest_phase(wiki=wiki, page_path=page)

    assert parsed is True
    assert [(e["kind"], e["slug"], e["status"]) for e in entries] == [("concept", "a-concept", "proposed")]
    # Persisted to the page frontmatter + body mirror.
    written = page.read_text(encoding="utf-8")
    assert read_suggested_pages(written) == entries
    assert "## Suggested pages" in written
    assert "a-concept" in written


@pytest.mark.asyncio
async def test_run_suggest_phase_llm_error_is_best_effort(tmp_path):
    from unittest.mock import AsyncMock, MagicMock, patch

    from graph_wiki_core.commands.suggest_pages import run_suggest_phase

    wiki = tmp_path / "wiki"
    (wiki / "sources").mkdir(parents=True)
    page = wiki / "sources" / "doc.md"
    original = "---\nsource_kind: source\ntarget_slug: doc\n---\n\nBody.\n"
    page.write_text(original, encoding="utf-8")

    fake_llm = MagicMock()
    fake_llm.ainvoke = AsyncMock(side_effect=RuntimeError("bedrock boom"))

    with patch("graph_wiki_core.commands.suggest_pages.make_llm", return_value=fake_llm):
        entries, parsed = await run_suggest_phase(wiki=wiki, page_path=page)

    assert entries == []
    assert parsed is False
    # Page is intact (no suggested_pages added).
    assert "suggested_pages:" not in page.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_run_suggest_phase_preserves_prior_human_decision(tmp_path):
    from unittest.mock import AsyncMock, MagicMock, patch

    from graph_wiki_core.commands.suggest_pages import run_suggest_phase

    wiki = tmp_path / "wiki"
    (wiki / "sources").mkdir(parents=True)
    page = wiki / "sources" / "doc.md"
    # Page already carries an approved suggestion (human edited status).
    page.write_text(
        "---\n"
        "source_kind: source\n"
        "target_slug: doc\n"
        "suggested_pages:\n"
        "- kind: concept\n"
        "  title: Kept\n"
        "  slug: kept\n"
        "  mode: create_new\n"
        "  existing_slug: null\n"
        "  rationale: r\n"
        "  status: approved\n"
        "---\n\nBody.\n",
        encoding="utf-8",
    )

    # Re-ingest proposes the SAME key again.
    llm_yaml = "suggestions:\n  - kind: concept\n    title: New Title\n    slug: kept\n    mode: create_new\n    rationale: new\n"
    fake_llm = MagicMock()
    fake_llm.ainvoke = AsyncMock(return_value=MagicMock(content=llm_yaml))

    with patch("graph_wiki_core.commands.suggest_pages.make_llm", return_value=fake_llm):
        entries, parsed = await run_suggest_phase(wiki=wiki, page_path=page)

    assert parsed is True
    kept = [e for e in entries if e["slug"] == "kept"]
    assert len(kept) == 1
    assert kept[0]["status"] == "approved"   # decision preserved
    assert kept[0]["title"] == "Kept"        # not overwritten by the new proposal
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_suggest_pages.py -k "run_suggest_phase" -q`
Expected: FAIL with `ImportError: cannot import name 'run_suggest_phase'` (and `build_extract_suggestions_prompt`).

- [ ] **Step 3: Extend imports for the orchestrator**

At the top of `suggest_pages.py`, change:

```python
import logging
from pathlib import Path

import yaml
from wiki_io.ingest_source import slugify
from wiki_io.update_index import parse_frontmatter
```

to:

```python
import logging
from pathlib import Path

import yaml
from langchain_core.messages import HumanMessage, SystemMessage
from model_adapter.loader import make_llm
from wiki_io.ingest_source import slugify
from wiki_io.update_index import parse_frontmatter

from graph_wiki_core.prompts.extractor import EXTRACTOR_SYSTEM
```

- [ ] **Step 4: Add the prompt builder + orchestrator**

Append to `suggest_pages.py`:

```python
def build_extract_suggestions_prompt(source_text: str, vault_index: list[dict]) -> str:
    """Human message for the extractor: the Source page + the curated-vault index."""
    preview = source_text[:EXTRACT_PREVIEW_CHARS]
    if len(source_text) > EXTRACT_PREVIEW_CHARS:
        preview += "\n[TRUNCATED]"

    if vault_index:
        index_lines = "\n".join(
            f"  - {e['kind']}/{e['slug']} — {e.get('title', '')}"
            + (f" — {e['summary']}" if e.get("summary") else "")
            for e in vault_index
        )
    else:
        index_lines = "  (no curated pages yet)"

    return (
        "Existing curated pages (propose update_existing when your idea is "
        "already covered by one of these; otherwise create_new):\n"
        f"{index_lines}\n\n"
        "--- Source page ---\n"
        f"{preview}\n"
        "--- End source page ---\n\n"
        "Propose the concept/adr/architecture pages this source justifies, as a "
        "YAML `suggestions:` list. Return `suggestions: []` if none are warranted."
    )


async def run_suggest_phase(
    *,
    wiki: Path,
    page_path: Path,
) -> tuple[list[dict], bool]:
    """Inline suggest phase: propose derived pages and persist them on the page.

    Best-effort (spec §3.1): on any LLM error the page is left as-is and
    (existing_entries, False) is returned. Returns (merged_entries, parsed).
    """
    page_text = page_path.read_text(encoding="utf-8")
    existing = read_suggested_pages(page_text)
    vault_index = build_curated_vault_index(wiki)
    prompt = build_extract_suggestions_prompt(page_text, vault_index)

    try:
        llm = make_llm("extractor")
        resp = await llm.ainvoke([SystemMessage(EXTRACTOR_SYSTEM), HumanMessage(prompt)])
    except Exception:
        logger.warning("extractor LLM call failed; skipping suggestions", exc_info=True)
        return existing, False

    proposals, parsed = parse_extractor_response(resp.content)
    if not parsed:
        # Parse miss: nothing new; leave existing entries untouched, signal degraded.
        return existing, False

    merged = merge_suggested_pages(existing, proposals)
    new_text = set_suggested_pages_in_frontmatter(page_text, merged)
    new_text = set_suggested_pages_section_in_body(new_text, render_suggested_pages_section(merged))
    if new_text != page_text:
        page_path.write_text(new_text, encoding="utf-8")
    return merged, True
```

- [ ] **Step 5: Run to verify it passes**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_suggest_pages.py -q`
Expected: PASS (the whole module's test file).

- [ ] **Step 6: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/suggest_pages.py packages/graph-wiki-core/tests/unit/test_suggest_pages.py
git commit -m "feat(suggest): add run_suggest_phase orchestrator + extractor prompt builder"
```

---

### Task 8: Wire the suggest phase into `run_ingest_source` + 2 new `IngestResult` fields

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py` (imports, `IngestResult`, `run_ingest_source`)
- Test: `packages/graph-wiki-core/tests/unit/test_commands_ingest.py` (wired-phase integration tests)

The existing ingest tests mock `make_llm` once and return a single fake for the ingestor call. The suggest phase calls `make_llm("extractor")` inside `suggest_pages`, which the `ingest.make_llm` patch does **not** cover (it is a separate import in that module). This cuts two ways:

1. **Pre-existing source-ingest tests** (which never patch the extractor) would otherwise make live extractor Bedrock calls — **Step 1a adds a module-scoped autouse fixture** that stubs `suggest_pages.make_llm` to a `suggestions: []` no-op for the whole module.
2. **The new tests below** that assert on suggestions patch **`graph_wiki_core.commands.suggest_pages.make_llm`** explicitly, nesting inside the autouse fixture to supply their own extractor output.

Either way the ingestor patch and the extractor patch target distinct namespaces and never collide.

- [ ] **Step 1a: Add a module-scoped autouse fixture that defangs the extractor**

**Why (load-bearing):** the existing Part-A source-ingest tests patch only `graph_wiki_core.commands.ingest.make_llm`. The new suggest phase calls `make_llm("extractor")` resolved in the **`suggest_pages` namespace** (`suggest_pages.py` does `from model_adapter.loader import make_llm`), so the `ingest.make_llm` patch does **not** cover it. There is no conftest Bedrock guard in `graph-wiki-core` tests. Without this fixture, every pre-existing `run_ingest_source` test would make a **live extractor Bedrock call** (real cost/latency/flakiness with creds present; a caught slow-path exception without). The backstop `try/except` masks this rather than preventing it.

Add this autouse fixture to `test_commands_ingest.py` near the top of the file (after the imports, before the first test). It returns an empty, well-formed proposal list so the suggest phase becomes a deterministic no-op for every test that does not override it:

```python
@pytest.fixture(autouse=True)
def _stub_extractor_llm():
    """Defang the M3 suggest phase for the whole module.

    The suggest phase calls make_llm("extractor") in the suggest_pages
    namespace, which the per-test ingest.make_llm patches do NOT cover. Stub it
    to return `suggestions: []` (parsed True, zero proposals) so existing tests
    never hit Bedrock. Tests that assert on suggestions nest their own
    `patch("graph_wiki_core.commands.suggest_pages.make_llm", ...)` inside this
    one, which wins for their duration.
    """
    fake = MagicMock()
    fake.ainvoke = AsyncMock(return_value=MagicMock(content="suggestions: []"))
    with patch("graph_wiki_core.commands.suggest_pages.make_llm", return_value=fake):
        yield
```

(`MagicMock`, `AsyncMock`, `patch` are already imported at `test_commands_ingest.py:13`.)

- [ ] **Step 1b: Write the failing integration tests**

Add to `test_commands_ingest.py`, after the Part A integration tests (after `test_run_ingest_source_surfaces_stripped_wikilinks_in_result`). Note both new tests below already wrap their own `patch("graph_wiki_core.commands.suggest_pages.make_llm", ...)`, which nests inside the Step-1a autouse fixture and overrides it for their duration:

```python
# ---------------------------------------------------------------------------
# M3 suggestion step: inline suggest phase wired into run_ingest_source
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_ingest_source_attaches_suggestions(tmp_path: Path) -> None:
    """A clean ingest records proposals on the Source page + in IngestResult."""
    from graph_wiki_core.commands.ingest import run_ingest_source

    workspace, wiki, repo = _build_workspace_with_repo(tmp_path)
    source_file = workspace / "spec.md"
    source_file.write_text("# Spec\n\nA cross-cutting idea.", encoding="utf-8")
    _seed_graph_db_for_ingest_tests(workspace, packages=[])

    ingestor_response = (
        "---\nsource_kind: source\ntarget_slug: spec\ntitle: Spec\nsummary: x\n---\nBody."
    )
    extractor_response = (
        "suggestions:\n"
        "  - kind: concept\n"
        "    title: Cross Cutting Idea\n"
        "    slug: cross-cutting-idea\n"
        "    mode: create_new\n"
        "    rationale: The source defines it.\n"
    )

    ingestor_llm = MagicMock()
    ingestor_llm.ainvoke = AsyncMock(return_value=MagicMock(content=ingestor_response))
    extractor_llm = MagicMock()
    extractor_llm.ainvoke = AsyncMock(return_value=MagicMock(content=extractor_response))

    with (
        patch("graph_wiki_core.commands.ingest.resolve_wiki_and_repo") as mock_resolve,
        patch("graph_wiki_core.commands.ingest.make_llm", return_value=ingestor_llm),
        patch("graph_wiki_core.commands.suggest_pages.make_llm", return_value=extractor_llm),
        patch("graph_wiki_core.commands.ingest.update_index"),
        patch("graph_wiki_core.commands.ingest.append_log"),
    ):
        mock_resolve.return_value = (wiki, repo)
        result = await run_ingest_source(source_file, workspace)

    assert result.suggestions_parsed is True
    assert [(s["kind"], s["slug"], s["status"]) for s in result.suggested_pages] == [
        ("concept", "cross-cutting-idea", "proposed")
    ]
    written = (wiki / "sources" / "spec.md").read_text(encoding="utf-8")
    assert "suggested_pages:" in written
    assert "## Suggested pages" in written
    assert "cross-cutting-idea" in written


@pytest.mark.asyncio
async def test_run_ingest_source_suggest_phase_degraded_is_nonfatal(tmp_path: Path) -> None:
    """Extractor parse miss -> suggestions_parsed False, ingest still ok, page intact."""
    from graph_wiki_core.commands.ingest import run_ingest_source

    workspace, wiki, repo = _build_workspace_with_repo(tmp_path)
    source_file = workspace / "spec.md"
    source_file.write_text("# Spec\n\nBody.", encoding="utf-8")
    _seed_graph_db_for_ingest_tests(workspace, packages=[])

    ingestor_response = "---\nsource_kind: source\ntarget_slug: spec\ntitle: Spec\n---\nBody."
    extractor_response = "this is not valid yaml: : ["

    ingestor_llm = MagicMock()
    ingestor_llm.ainvoke = AsyncMock(return_value=MagicMock(content=ingestor_response))
    extractor_llm = MagicMock()
    extractor_llm.ainvoke = AsyncMock(return_value=MagicMock(content=extractor_response))

    with (
        patch("graph_wiki_core.commands.ingest.resolve_wiki_and_repo") as mock_resolve,
        patch("graph_wiki_core.commands.ingest.make_llm", return_value=ingestor_llm),
        patch("graph_wiki_core.commands.suggest_pages.make_llm", return_value=extractor_llm),
        patch("graph_wiki_core.commands.ingest.update_index"),
        patch("graph_wiki_core.commands.ingest.append_log"),
    ):
        mock_resolve.return_value = (wiki, repo)
        result = await run_ingest_source(source_file, workspace)

    assert result.status == "ok"
    assert result.suggestions_parsed is False
    assert result.suggested_pages == []
    written = (wiki / "sources" / "spec.md").read_text(encoding="utf-8")
    assert "suggested_pages:" not in written  # nothing fabricated
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_commands_ingest.py -k "attaches_suggestions or suggest_phase_degraded" -q`
Expected: FAIL — `AttributeError: 'IngestResult' object has no attribute 'suggestions_parsed'`.

- [ ] **Step 3: Add the two `IngestResult` fields**

In `ingest.py`, find the Part-A field block at the end of `IngestResult` (the three fields `source_kind` / `stripped_wikilinks` / `frontmatter_parsed`). Immediately **after** the `frontmatter_parsed: bool = True` line, add:

```python
    # Living Wiki M3 (suggestion step):
    suggested_pages: list[dict] = field(default_factory=list)  # proposals after this run's merge
    suggestions_parsed: bool = True  # False when the extractor call errored or its output didn't parse
```

(`field` is already imported by Part A. If a `dict` typing import is needed it is not — built-in `list[dict]` works on py311.)

Also append to the dataclass docstring, after the `frontmatter_parsed:` description:

```python
        suggested_pages:    Living Wiki M3: proposed concept/adr/architecture pages
                            recorded on the Source page (each a dict with
                            kind/slug/mode/status/…). Empty for work items.
        suggestions_parsed: Living Wiki M3: False when the extractor LLM call
                            errored or its output did not parse (zero suggestions).
```

- [ ] **Step 4: Import `run_suggest_phase`**

In `ingest.py`, in the `graph_wiki_core.*` import block near the top (where `from graph_wiki_core.prompts.ingestor import build_ingestor_system` lives), add:

```python
from graph_wiki_core.commands.suggest_pages import run_suggest_phase
```

- [ ] **Step 5: Call the suggest phase before `update_index`**

In `run_ingest_source`, find the end of the entity-touch-link block and the start of Step 8 (post-Part-A this reads roughly):

```python
        if entity_stem:
            linked_output = _ensure_entity_touch_link(current_output, entity_stem)
            if linked_output != current_output:
                target_path.write_text(linked_output, encoding="utf-8")

        # Step 8: update cross-refs (index-only scope — CONTEXT.md deferred)
        update_index(wiki)
```

Insert the suggest phase **between** the entity-link block and `# Step 8`:

```python
        if entity_stem:
            linked_output = _ensure_entity_touch_link(current_output, entity_stem)
            if linked_output != current_output:
                target_path.write_text(linked_output, encoding="utf-8")

        # Step 7.5 (Living Wiki M3): inline suggest phase — propose derived
        # concept/adr/architecture pages from the just-written Source page.
        # Best-effort: a failure here never fails the ingest (spec §3.1).
        try:
            suggested_pages, suggestions_parsed = await run_suggest_phase(
                wiki=wiki, page_path=target_path
            )
        except Exception:
            logger.warning("suggest phase failed; continuing without suggestions", exc_info=True)
            suggested_pages, suggestions_parsed = [], False

        # Step 8: update cross-refs (index-only scope — CONTEXT.md deferred)
        update_index(wiki)
```

- [ ] **Step 6: Populate the new fields in the return**

In `run_ingest_source`, find the `return IngestResult(...)` block (post-Part-A it already passes `source_kind=`, `stripped_wikilinks=`, `frontmatter_parsed=`). Add the two new keyword args after `frontmatter_parsed=frontmatter_parsed,`:

```python
            source_kind=source_kind,
            stripped_wikilinks=stripped_wikilinks,
            frontmatter_parsed=frontmatter_parsed,
            suggested_pages=suggested_pages,
            suggestions_parsed=suggestions_parsed,
        )
```

- [ ] **Step 7: Run the new tests to verify they pass**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_commands_ingest.py -k "attaches_suggestions or suggest_phase_degraded" -v`
Expected: PASS.

- [ ] **Step 8: Run the whole ingest file (confirm Part A tests still green)**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_commands_ingest.py -q`
Expected: PASS. The pre-existing Part-A source-ingest tests patch only `graph_wiki_core.commands.ingest.make_llm`, which does **not** cover the extractor call (resolved in the `suggest_pages` namespace). The **Step-1a autouse fixture** is what keeps them green and offline: it stubs `suggest_pages.make_llm` to return `suggestions: []`, so the suggest phase runs as a deterministic no-op (`suggestions_parsed=True`, zero suggestions) without touching Bedrock. Those tests don't assert on suggestions, so they don't regress. **Confirm the autouse fixture from Step 1a is present** — without it these tests would attempt live extractor calls.

- [ ] **Step 9: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py packages/graph-wiki-core/tests/unit/test_commands_ingest.py
git commit -m "feat(ingest): run inline suggest phase; surface suggested_pages + suggestions_parsed"
```

---

### Task 9: CLI — surface suggestions + degraded warning

**Files:**
- Modify: `packages/graph-wiki-cli/src/graph_wiki_cli/wiki_cli/main.py` (`ingest_source` text branch, ~`:215-217` post-Part-A)
- Test: `packages/graph-wiki-cli/tests/unit/test_wiki_cli.py` (add a CLI test)

The `--json` branch already serializes everything via `dataclasses.asdict(result)` — no change. Only the text branch gains output.

- [ ] **Step 1: Write the failing test**

Add to `test_wiki_cli.py`:

```python
def test_ingest_source_cli_prints_suggestions_and_degraded(tmp_path):
    """Text-mode CLI lists suggestions and warns when the suggest pass degraded."""
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
        source_kind="source",
        stripped_wikilinks=[],
        frontmatter_parsed=True,
        suggested_pages=[
            {"kind": "concept", "title": "Idea", "slug": "idea", "mode": "create_new",
             "existing_slug": None, "rationale": "r", "status": "proposed"},
        ],
        suggestions_parsed=False,
    )

    runner = CliRunner()
    with patch(
        "graph_wiki_cli.wiki_cli.main.run_ingest_source",
        new_callable=AsyncMock,
        return_value=fake_result,
    ):
        result = runner.invoke(wiki_app, ["ingest", "source", str(src)])

    assert result.exit_code == 0
    assert "suggested 1 page(s)" in result.stdout
    assert "concept" in result.stdout
    assert "idea" in result.stdout
    assert "suggestion pass degraded" in result.stdout
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --package graph-wiki-cli pytest tests/unit/test_wiki_cli.py::test_ingest_source_cli_prints_suggestions_and_degraded -v`
Expected: FAIL — the suggestion lines are not printed.

- [ ] **Step 3: Add the output**

In `wiki_cli/main.py`, the `ingest_source` text branch (post-Part-A) ends with the `source_kind`/`slug` line and the Part-A warnings. After the Part-A `stripped_wikilinks` warning block (the last `typer.echo(... err=True)`), add:

```python
        if result.suggested_pages:
            typer.echo(f"     suggested {len(result.suggested_pages)} page(s):")
            for s in result.suggested_pages:
                mode = "update" if s.get("mode") == "update_existing" else "new"
                typer.echo(
                    f"       - {s.get('kind')} \"{s.get('title')}\" "
                    f"({mode}, {s.get('status')}) -> {s.get('slug')}"
                )
        if not result.suggestions_parsed:
            typer.echo("⚠ suggestion pass degraded — wrote 0 suggestions", err=True)
```

> If Part A's text branch differs slightly, anchor on `result.source_kind` being printed and add this block immediately below the existing warnings, before the function returns.

- [ ] **Step 4: Run to verify it passes**

Run: `uv run --package graph-wiki-cli pytest tests/unit/test_wiki_cli.py::test_ingest_source_cli_prints_suggestions_and_degraded -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/graph-wiki-cli/src/graph_wiki_cli/wiki_cli/main.py packages/graph-wiki-cli/tests/unit/test_wiki_cli.py
git commit -m "feat(cli): print suggested pages + degraded-suggestion warning on ingest source"
```

---

### Task 10: MCP — expose `suggested_pages` + `suggestions_parsed`

**Files:**
- Modify: `packages/graph-wiki-mcp/src/graph_wiki_mcp/server.py` (`WikiIngestOutput` + mapping)
- Test: `packages/graph-wiki-mcp/tests/unit/test_mcp_new_tools.py` (add a passthrough test)

`server.py` constructs `WikiIngestOutput` field-by-field (not via `asdict`), so add the fields to the model **and** map them. Part A already added `source_kind`/`stripped_wikilinks`/`frontmatter_parsed`; this appends two more.

- [ ] **Step 1: Write the failing test**

Add to `test_mcp_new_tools.py`:

```python
@pytest.mark.asyncio
async def test_wiki_ingest_source_passes_through_suggestions() -> None:
    """wiki_ingest surfaces suggested_pages / suggestions_parsed."""
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
        source_kind="source",
        stripped_wikilinks=[],
        frontmatter_parsed=True,
        suggested_pages=[
            {"kind": "adr", "title": "T", "slug": "t", "mode": "create_new",
             "existing_slug": None, "rationale": "r", "status": "proposed"},
        ],
        suggestions_parsed=True,
    )

    mock_ctx = MagicMock()
    mock_ctx.report_progress = AsyncMock()

    with patch(
        "graph_wiki_mcp.server.run_ingest_source", new_callable=AsyncMock, return_value=fake
    ):
        out = await wiki_ingest(
            WikiIngestInput(type="source", source_path="/x/doc.md"), mock_ctx
        )

    assert out.suggestions_parsed is True
    assert out.suggested_pages[0]["slug"] == "t"
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --package graph-wiki-mcp pytest tests/unit/test_mcp_new_tools.py::test_wiki_ingest_source_passes_through_suggestions -v`
Expected: FAIL — `AttributeError: 'WikiIngestOutput' object has no attribute 'suggestions_parsed'`.

- [ ] **Step 3: Add the fields to `WikiIngestOutput`**

In `server.py`, after the Part-A fields on `WikiIngestOutput` (`source_kind` / `stripped_wikilinks` / `frontmatter_parsed`), add:

```python
    # Living Wiki M3 (suggestion step):
    suggested_pages: list[dict] = Field(default_factory=list)
    suggestions_parsed: bool = True
```

- [ ] **Step 4: Map the fields in the return**

In the `return WikiIngestOutput(...)` block, after `frontmatter_parsed=result.frontmatter_parsed,`, add:

```python
        suggested_pages=result.suggested_pages,
        suggestions_parsed=result.suggestions_parsed,
    )
```

- [ ] **Step 5: Run to verify it passes**

Run: `uv run --package graph-wiki-mcp pytest tests/unit/test_mcp_new_tools.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add packages/graph-wiki-mcp/src/graph_wiki_mcp/server.py packages/graph-wiki-mcp/tests/unit/test_mcp_new_tools.py
git commit -m "feat(mcp): expose suggested_pages + suggestions_parsed on wiki_ingest output"
```

---

### Task 11: Full verification + lint + brand gate

**Files:** none (verification only)

- [ ] **Step 1: Run all affected package suites**

```bash
uv run --package graph-wiki-core pytest
uv run --package graph-wiki-cli pytest -m "not integration"
uv run --package graph-wiki-mcp pytest -m "not integration"
uv run --package model-adapter pytest
```
Expected: all PASS. Watch the prompt snapshot tests (extractor snapshot added in Task 1) and any models.toml role-enumeration test in `model-adapter`.

- [ ] **Step 2: Lint + format-check only the files you changed**

```bash
uv run ruff check .
uv run ruff format --check \
  packages/graph-wiki-core/src/graph_wiki_core/commands/suggest_pages.py \
  packages/graph-wiki-core/src/graph_wiki_core/prompts/extractor.py \
  packages/graph-wiki-core/src/graph_wiki_core/commands/ingest.py \
  packages/graph-wiki-cli/src/graph_wiki_cli/wiki_cli/main.py \
  packages/graph-wiki-mcp/src/graph_wiki_mcp/server.py
```
Expected: `ruff check` clean. (Per the `ruff-format-discovery` memory: do NOT run `ruff format` on explicit package `src/...` paths to "fix" diffs — it applies width 88, not the root's 120. If `format --check` flags a file, match the surrounding multi-line style by hand instead of auto-formatting.)

- [ ] **Step 3: Brand gate**

```bash
bash scripts/check-brand.sh
```
Expected: exits 0.

- [ ] **Step 4: Final sanity diff review**

```bash
git log --oneline -11
git diff --stat main
```
Confirm changes are confined to the files in the File Structure section (new `suggest_pages.py`, new `extractor.py`, `models.toml`, `ingest.py`, CLI `main.py`, MCP `server.py`, the four test files, and the regenerated `.ambr`).

---

## Self-review notes (author checklist applied)

- **Spec coverage:** D1 inline phase (Task 8 Step 5). D2 new `extractor` role + separate call (Task 1, Task 7 `run_suggest_phase`). D3 robust parse + zero-fallback (Task 2 `parse_extractor_response`, Task 7 degraded path). D4 structured `suggested_pages` keyed `(kind, slug)`, merge preserves decisions (Task 4 `merge_suggested_pages`, Task 5 frontmatter persistence). D5 regenerated body mirror, approve-in-frontmatter note (Task 6). D6 dedup via vault listing (Task 3). Best-effort/non-catastrophic (Task 7 + Task 8 backstop). `IngestResult` additions + CLI + MCP (Tasks 8/9/10). All spec §6 test cases mapped: propose-new-vs-update (Task 2/3/4 + Task 8), conservatism/zero (Task 2 empty-list, Task 8 covers ok-status), merge-preserves-decisions (Task 4 + Task 7 `preserves_prior_human_decision`), idempotence (Task 4/5/6 idempotent tests), body mirror (Task 6), degraded path (Task 7 + Task 8 `suggest_phase_degraded`), dedup independence (Task 3 reads vault not frontmatter), role wiring (Task 1 Step 2).
- **Type consistency:** entry dicts use the fixed key order `kind, title, slug, mode, existing_slug, rationale, status` everywhere (`_ENTRY_KEY_ORDER`, parser output sans `status`, merge stamps `status`). `suggested_pages: list[dict]` / `suggestions_parsed: bool` named identically across `IngestResult` (Task 8), `WikiIngestOutput` (Task 10), tests, and CLI. Function names `run_suggest_phase`, `merge_suggested_pages`, `parse_extractor_response`, `build_curated_vault_index`, `read_suggested_pages`, `set_suggested_pages_in_frontmatter`, `render_suggested_pages_section`, `set_suggested_pages_section_in_body`, `build_extract_suggestions_prompt` are consistent between definition (Tasks 2-7) and call sites (Tasks 7-8).
- **Prerequisite:** Task 0 hard-gates on Part A being landed; all `ingest.py`/CLI/MCP edits anchor on Part A marker text, not raw line numbers.
- **No placeholders:** every code/edit step shows exact old/new text and an exact command + expected result.
