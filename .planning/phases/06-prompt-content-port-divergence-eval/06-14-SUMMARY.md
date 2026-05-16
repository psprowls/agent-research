---
phase: 06-prompt-content-port-divergence-eval
plan: 14
subsystem: code-wiki-agent / commands+prompts
tags: [gap-closure, ingestor, wikilinks, hallucination-guard, UAT-G4]
requires: [06-13]
provides:
  - "_resolve_wikilinks(text, wiki) helper that strips wikilinks unresolved against the vault"
  - "two-pass write in run_ingest_source: write -> resolve -> rewrite if any stripped"
  - "append_log detail records stripped-wikilink count + first 5 targets"
  - "INGESTOR_SYSTEM named anti-patterns + honest disclosure of post-hoc stripping"
affects:
  - "vault hallucination audit (log.md now records strip counts per ingest)"
  - "ingestor prompt is ~11 lines longer (additive only; no shared fragment touched)"
tech-stack:
  added: []
  patterns:
    - "line-by-line fence-state walk to avoid eating wikilinks in fenced example blocks"
    - "two-write strategy keeps the resolver free of pre-registration coupling"
    - "ingestor-local prompt strengthening (shared CITATION_RULES untouched per programmatic-check separation)"
key-files:
  created:
    - .planning/phases/06-prompt-content-port-divergence-eval/06-14-SUMMARY.md
  modified:
    - agents/code-wiki-agent/src/code_wiki_agent/commands/ingest.py
    - agents/code-wiki-agent/src/code_wiki_agent/prompts/ingestor.py
    - agents/code-wiki-agent/tests/unit/test_commands_ingest.py
    - agents/code-wiki-agent/tests/prompts/__snapshots__/test_prompt_snapshots.ambr
decisions:
  - "Strengthen ingestor prompt locally rather than editing _fragments/citation_rules.py — librarian has its own programmatic validate_wikilinks check and shouldn't inherit prose intended for the ingestor's specific failure modes"
  - "Two writes (initial + post-resolve) instead of pre-registering the new file in the resolver's known-pages set — simpler, faster than the alternative, and writes are sub-millisecond on local disk"
  - "Fence state machine on lines instead of multiline regex — easier to reason about, handles ``` markers anywhere on a line including indented fences in lists"
metrics:
  duration_minutes: 8
  completed: 2026-05-16
---

# Phase 06 Plan 14: UAT-G4 Hallucinated-Wikilink Strip Summary

One-liner: Closes UAT gap G4 by adding `_resolve_wikilinks()` to `commands/ingest.py` (deterministic post-LLM stripper for fabricated `[[wikilink]]` targets) and naming the two observed anti-patterns (`[[Person Name]]`, `[[subdir/missing-slug]]`) explicitly in the ingestor prompt.

## What Was Built

**Task 1 — `_resolve_wikilinks` helper + integration (commit `2c243c2`)**
- Added private helper `_resolve_wikilinks(text: str, wiki: Path) -> tuple[str, list[str]]` next to `_rewrite_target_slug_in_body`.
- Helper enumerates vault pages once via `wiki.rglob("*.md")`, building two index sets: full relative paths (without `.md`) and bare basenames.
- For every `[[…]]` outside fenced code blocks: keep verbatim if either an exact relpath match (`[[sources/otel-story]]` → `sources/otel-story.md`) or a basename match (`[[otel-story]]` → any `otel-story.md` anywhere) hits; otherwise replace with the bare label text.
- Wired into `run_ingest_source` between `_rewrite_target_slug_in_body` and the final write — two-write pattern so the newly created file is part of the "known pages" set during resolution.
- Extended the `append_log` `detail` argument: when any wikilinks are stripped, the log entry now includes `; stripped N unresolved wikilink(s): [first 5 targets]`.

**Task 2 — Ingestor prompt strengthening (commit `f34c45b`)**
- Extended `_INGESTOR_RULES` in `agents/code-wiki-agent/src/code_wiki_agent/prompts/ingestor.py` with a new `## Wikilink discipline (named anti-patterns)` subsection.
- Names the two UAT-observed shapes by example: `[[Person Name]]` and `[[subdir/some-slug]]`.
- Honestly tells the LLM the command layer STRIPS unresolved wikilinks, so the model can adjust without surprise.
- Shared `_fragments/citation_rules.py` was NOT modified — `git diff --stat` confirms zero changes to that file. Librarian keeps its own programmatic `validate_wikilinks` check unchanged.
- Snapshot at `tests/prompts/__snapshots__/test_prompt_snapshots.ambr` refreshed; the diff is purely additive (8 added lines, 0 deleted).

## Tests

| Test                                                              | Result | Notes                                                                                  |
| ----------------------------------------------------------------- | ------ | -------------------------------------------------------------------------------------- |
| `test_resolve_wikilinks_strips_unresolved`                         | PASS   | `[[fake-person]]` stripped; reported in the return list                                |
| `test_resolve_wikilinks_resolves_subdir_qualified`                 | PASS   | `[[sources/otel-story]]` preserved when `sources/otel-story.md` exists                 |
| `test_resolve_wikilinks_preserves_fenced_code`                     | PASS   | Two unfenced occurrences stripped; one fenced occurrence kept verbatim                 |
| `test_run_ingest_source_strips_unresolved_wikilinks`               | PASS   | End-to-end: hallucinated `[[Hallucinated Person]]` stripped from disk; log records `stripped 1` |
| `test_ingestor_system_snapshot`                                    | PASS   | Snapshot refreshed (additive) — `Wikilink discipline`, `[[Person Name]]`, `subdir/some-slug`, `STRIPS any`, and `Never fabricate` all present |
| Pre-existing 17 tests in `test_commands_ingest.py`                 | PASS   | No regression — full file 25/25 green                                                  |
| Pre-existing 7 snapshot tests                                      | PASS   | All other agent prompt snapshots unchanged                                             |

Run summary: `uv run --package code-wiki-agent pytest tests/unit/test_commands_ingest.py tests/prompts/test_prompt_snapshots.py -x -q` → **25 passed**.

## Required Output Items (per plan `<output>`)

- **Stripped count in test fixtures (sanity check resolver fires):**
  - `test_resolve_wikilinks_strips_unresolved` asserts `stripped == ["fake-person"]` → 1 strip.
  - `test_resolve_wikilinks_preserves_fenced_code` asserts `sorted(stripped) == ["also-fake", "fake-page"]` → 2 strips.
  - `test_run_ingest_source_strips_unresolved_wikilinks` asserts `stripped 1` in the `append_log` detail → 1 strip, end-to-end.
  - **Total: resolver fires 4 strip operations across the unit test fixtures — confirming non-trivial coverage.**
- **`_fragments/citation_rules.py` modification check:** `git diff --stat` against this plan's branch shows ZERO changes to `agents/code-wiki-agent/src/code_wiki_agent/prompts/_fragments/citation_rules.py`. The shared fragment is intentionally untouched (programmatic-check separation for librarian).
- **Line count of new prompt section:** the `## Wikilink discipline (named anti-patterns)` block in `_INGESTOR_RULES` adds **11 source lines** to `prompts/ingestor.py` (a 2-line heading + blank + 2 bullets + blank + a 4-line warning paragraph). The rendered snapshot diff adds 8 lines of prose (paragraphs collapsed).

## Deviations from Plan

**1. [defensive] Guarded `wiki.exists()` in `_resolve_wikilinks`**
- **Found during:** GREEN-phase implementation.
- **Why:** The unit tests construct `wiki` paths that may or may not exist on disk (e.g., `test_resolve_wikilinks_preserves_fenced_code` does create the dir, but the helper's contract should not assume the vault root is always present — calling `rglob` on a non-existent Path raises `FileNotFoundError`).
- **Fix:** Wrapped the enumeration in `if wiki.exists():`. When the vault root is absent, `known_relpaths` / `known_basenames` stay empty and every wikilink is stripped, which matches the spec ("no known pages → everything is unresolved").
- **Files modified:** `commands/ingest.py` (3-line guard).
- **Classification:** Rule 2 (auto-add missing critical functionality — robustness against absent vault root). No prompt or test signature change.

No other deviations.

## Auth Gates

None. Plan was fully autonomous.

## Known Stubs

None. The resolver and the prompt strengthening are both production code paths used by every `run_ingest_source` call.

## TDD Gate Compliance

| Gate     | Commit    | Notes                                                                      |
| -------- | --------- | -------------------------------------------------------------------------- |
| RED      | `66616ae` | 4 new tests added; all failed initially (ImportError on `_resolve_wikilinks`) |
| GREEN    | `2c243c2` | Helper + wiring implemented; all 4 new tests + 13 pre-existing tests pass     |
| REFACTOR | (skipped) | No clean-up needed; helper is a single small function with a focused contract |

Plan-level type is `execute` (not plan-level `tdd`), but both auto tasks have `tdd="true"` and followed RED-then-GREEN ordering verifiable in git log.

## Self-Check: PASSED

- `commands/ingest.py` modified: FOUND (90 insertions, 2 deletions).
- `prompts/ingestor.py` modified: FOUND (16 insertions, 1 deletion).
- `tests/unit/test_commands_ingest.py` modified: FOUND (105 insertions).
- `tests/prompts/__snapshots__/test_prompt_snapshots.ambr` modified: FOUND (8 insertions).
- `_fragments/citation_rules.py` unmodified: CONFIRMED (`git diff --stat` empty for this file).
- Commit `66616ae` (RED): FOUND in git log.
- Commit `2c243c2` (GREEN): FOUND in git log.
- Commit `f34c45b` (prompt + snapshot): FOUND in git log.
- All 25 tests in scope: PASS.
