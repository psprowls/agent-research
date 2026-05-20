---
phase: 06-prompt-content-port-divergence-eval
plan: 13
subsystem: ingestor
tags: [gap-closure, ingestor, routing, slug-consistency, UAT-G2, UAT-G3]
requires: [06-12]
provides:
  - page_type=source routes to wiki/sources/<slug>.md (UAT G2 closed)
  - body target_slug == on-disk filename stem for every written ingest page (UAT G3 closed)
  - INGESTOR_SYSTEM enumerates all four page_types with their target directories
affects:
  - agents/graph-wiki-agent/src/graph_wiki_agent/commands/ingest.py
  - agents/graph-wiki-agent/src/graph_wiki_agent/prompts/ingestor.py
  - agents/graph-wiki-agent/tests/unit/test_commands_ingest.py
  - agents/graph-wiki-agent/tests/prompts/__snapshots__/test_prompt_snapshots.ambr
tech-stack:
  added: []
  patterns:
    - text-based YAML frontmatter rewriting (no yaml.load) — preserves field ordering, indentation, and comments
key-files:
  created: []
  modified:
    - agents/graph-wiki-agent/src/graph_wiki_agent/commands/ingest.py
    - agents/graph-wiki-agent/src/graph_wiki_agent/prompts/ingestor.py
    - agents/graph-wiki-agent/tests/unit/test_commands_ingest.py
    - agents/graph-wiki-agent/tests/prompts/__snapshots__/test_prompt_snapshots.ambr
decisions:
  - "Slug reconciliation rewrites the file body BEFORE writing to disk so the persisted frontmatter always matches the filename — a downstream reader of just the file (no IngestResult in hand) still sees a consistent slug"
  - "_rewrite_target_slug_in_body is text-based (no yaml.load) to match the file-wide parser philosophy stated in _parse_ingestor_response's docstring (lines 102-109)"
  - "Helper injects target_slug at the top of frontmatter when missing entirely, so the LLM-omitted case (slug derived from title) also produces a body that self-declares its slug"
metrics:
  duration: "~2.5 min"
  completed: 2026-05-16T23:19:37Z
  tasks: 2
  files: 4
requirements: [PORT-03, EVAL-11]
---

# Phase 06 Plan 13: UAT G2 + G3 Gap Closure (Source Routing + Slug Consistency) Summary

UAT gaps G2 (source documents routed to `concepts/` instead of `sources/`) and G3 (frontmatter `target_slug` did not match on-disk filename slug) are closed: ingestor now routes `page_type: source` to `wiki/sources/<slug>.md`, and every written page's body declares a `target_slug:` byte-identical to its filename stem.

## What Was Built

### Task 1 — Source routing + slug-filename reconciliation

**`_PAGE_TYPE_DIRS` diff** (`agents/graph-wiki-agent/src/graph_wiki_agent/commands/ingest.py:73-78`):

```diff
 _PAGE_TYPE_DIRS: dict[str, str] = {
     "package": "packages",
     "concept": "concepts",
     "adr": "adrs",
+    "source": "sources",
 }
```

That one added line is the entire G2 fix: a frontmatter declaring `page_type: source` is now a valid member of the dict, so the `if page_type not in _PAGE_TYPE_DIRS: page_type = "concept"` fallback (line 299-300) no longer fires, and `_route_target_path` returns `wiki/sources/<slug>.md`.

**New helper** (`commands/ingest.py:96-135`):

```python
def _rewrite_target_slug_in_body(text: str, canonical_slug: str) -> str:
```

Signature: takes the raw LLM output text and the canonical slug (`target_path.stem`); returns the text with the frontmatter's `target_slug:` line rewritten to the canonical value. If `target_slug:` is absent, injects a new line at the top of the frontmatter block. Operates as pure text manipulation (no `yaml.load`), so it preserves field ordering, indentation, and inline comments of all other fields. Returns input unchanged if no `---` frontmatter is present.

**Wiring** (`commands/ingest.py:306-315`): two new lines between `target_path = _route_target_path(...)` and `target_path.write_text(...)`:

```python
canonical_slug = target_path.stem
llm_output = _rewrite_target_slug_in_body(llm_output, canonical_slug)
```

This closes G3 for every code path that reaches the write — including the LLM-omitted-slug case where the title-derived fallback now gets written into the body.

### Task 2 — INGESTOR_SYSTEM enumerates the four page_types

`_PAGE_TYPE_ROUTING` in `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/ingestor.py:24-33` now lists each page_type with its destination directory:

```
- `page_type: source` -> `sources/` (specs, PRs, articles, transcripts, in-repo docs)
- `page_type: package` -> `packages/` (a workspace member with a manifest)
- `page_type: concept` -> `concepts/` (cross-cutting technical idea, comparison page)
- `page_type: adr` -> `adrs/` (dated decision record)
```

Plus an explicit `category` ↔ `page_type` consistency reminder. The previous wording mentioned `source` only in passing without naming the `sources/` destination.

**Snapshot delta:** `tests/prompts/__snapshots__/test_prompt_snapshots.ambr` — `+7 / -2` lines, scoped entirely to the routing section (no collateral changes to other prompt fragments).

## Verification

| Suite | Result |
|-------|--------|
| `pytest agents/graph-wiki-agent/tests/unit/test_commands_ingest.py -x -q` | 13 passed |
| `pytest agents/graph-wiki-agent/tests/prompts/test_prompt_snapshots.py -x -q` | 8 snapshots passed |
| Combined plan-13 verify command | 21 passed |
| `grep -n '"source": "sources"' commands/ingest.py` | one match (line 77) |
| INGESTOR_SYSTEM substring assertions (all four page_types + directories) | OK |

### New unit tests (Plan 06-13)

| Test | Status | Asserts |
|------|--------|---------|
| `test_run_ingest_source_routes_source_to_sources_dir` | PASS | `wiki/sources/an-article.md` exists; `result.page_type == "source"`; `result.slug == "an-article"`; `concepts/` not used |
| `test_run_ingest_source_target_slug_matches_filename` | PASS | written file body contains `target_slug: <result.slug>` matching filename stem; original `weird_slug_with_underscores` does not survive verbatim |

### Regression guards (pre-existing tests still pass)

- `test_run_ingest_source_extracts_and_routes` — page_type=concept still routes to `concepts/`
- `test_run_ingest_source_default_slug_from_title` — title fallback still produces correct slug
- All three `test_parse_ingestor_response_*` fence-stripping tests
- `test_run_ingest_work_item_*` (3 tests) — work-item path untouched

## Deviations from Plan

None — both tasks executed exactly as written.

## Commits

| Hash | Type | Message |
|------|------|---------|
| `d596284` | test | add failing tests for source routing and slug-filename equality (RED) |
| `ab0bf61` | feat | route page_type=source to sources/ and reconcile target_slug with filename (GREEN) |
| `7c85281` | feat | enumerate source alongside package/concept/adr in INGESTOR_SYSTEM routing |

## TDD Gate Compliance

Plan-level gate sequence verified:
- Task 1: RED commit `d596284` (test-only, failing) → GREEN commit `ab0bf61` (implementation, all 7 selected tests pass) — compliant
- Task 2: prompt + snapshot updated atomically — the snapshot test itself is the verification gate; pre-existing snapshot's behavior change is observable in the diff

## Self-Check: PASSED

- File `agents/graph-wiki-agent/src/graph_wiki_agent/commands/ingest.py` — FOUND (verified via Edit; `"source": "sources"` present at line 77; `_rewrite_target_slug_in_body` present)
- File `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/ingestor.py` — FOUND (verified via Edit; all four page_types enumerated)
- File `agents/graph-wiki-agent/tests/unit/test_commands_ingest.py` — FOUND (13 passing tests including the two new ones)
- File `agents/graph-wiki-agent/tests/prompts/__snapshots__/test_prompt_snapshots.ambr` — FOUND (snapshot refreshed)
- Commit `d596284` — FOUND in git log
- Commit `ab0bf61` — FOUND in git log
- Commit `7c85281` — FOUND in git log
