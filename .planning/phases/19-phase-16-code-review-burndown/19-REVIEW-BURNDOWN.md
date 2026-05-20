# Phase 19: Phase 16 Code Review Burndown — Disposition Table

**Phase:** 19-phase-16-code-review-burndown
**Compiled:** 2026-05-19

This is the canonical disposition table for every finding raised in the Phase 16 code review. Each row records how a finding was resolved (or why no action was taken) and links back to the commit that landed the fix. Future `/gsd:code-review` passes on the trace pipeline + eval-harness refactor surface area should grep `.planning/phases/19-*` and find this file.

**Source of truth (historical, not edited):** [`.planning/milestones/v1.2-phases/16-carry-forward-debt-cleanup/16-REVIEW.md`](../../milestones/v1.2-phases/16-carry-forward-debt-cleanup/16-REVIEW.md). That archived review report holds the full narrative for each finding's file:line, issue description, and proposed fix. This table records dispositions only.

**Disposition vocabulary:**
- `fixed` — finding addressed by a landed commit (see `commit SHA` column)
- `no-action` — finding self-corrected on re-scan; current code is already correct
- `dismissed` — finding intentionally not acted on (none in this phase)
- `deferred` — rolled forward to a later phase (none in this phase)

## Disposition Table

| finding id | severity | file:line | disposition | commit SHA | notes |
|------------|----------|-----------|-------------|------------|-------|
| WR-01 | warning | `packages/eval-harness/src/eval_harness/divergence/synthesizer.py:19,50-60` | fixed | `d805829` | D-01 — replaced PascalCase-only `_SLUG_ONLY_RE` with "no `/` in target" check; lowercase/hyphenated slugs (`[[bedrock]]`, `[[subagent-pool]]`) now fail SYN-002 as intended |
| WR-02 | warning | `packages/eval-harness/src/eval_harness/divergence/code_reader.py:31,71-82` | fixed | `a98ae95` | D-02 — tightened `_GRAPH_WIKI_PREFIX_RE` lookbehind to `(?<![A-Za-z0-9_-])\.graph-wiki/` so inline `vault/.graph-wiki/...` references are caught; landed together with WR-03 |
| WR-03 | warning | `packages/eval-harness/src/eval_harness/divergence/code_reader.py:21-23,39-53` | fixed | `a98ae95` | D-03 — loosened `_PATH_LINE_RE` to drop the mandatory `/`; bare-filename citations like `pool.py:115` now qualify, aligning CR-001 with synthesizer's permissive regex; landed together with WR-02 |
| WR-04 | warning | `agents/graph-wiki-agent/tests/integration/test_trace_coverage.py:88-95` | fixed | `09fa270` | D-04 — exempted the empty/empty code-fallback path (`tokens_in is None and tokens_out is None`); mirrors the existing error-record exemption |
| WR-05 | warning | `packages/subagent-runtime/src/subagent_runtime/pool.py:133-137` | fixed | `a4db4e8` | D-05 — hoisted `inspect.signature(task)` out of `_run_one` to compute once with `try/except (ValueError, TypeError)` falling back to single-arg form |
| WR-06 | warning | `agents/graph-wiki-agent/src/graph_wiki_agent/commands/ingest.py:101-106` | fixed | `3949713` | D-06 — switched `_route_target_path` containment check to `Path.is_relative_to`; codebase-idiom convergence with `query.py:356` (not a runtime bug on macOS/Linux) |
| IN-01 | info | `agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py:283-286` | fixed | `a907d1b` | D-07 — updated stale `_extract_usage_tokens` docstring to point at the canonical home `subagent_runtime.trace_io.write_trace_record:56-66`; landed together with IN-09 |
| IN-02 | info | `packages/subagent-runtime/src/subagent_runtime/trace_io.py:24` | no-action | n/a | D-08 — no-action — review self-corrected on re-scan; `Any` is used in `trace_io.py` |
| IN-03 | info | `packages/eval-harness/src/eval_harness/divergence/metric.py:31` | fixed | `85f3535` | D-09 — removed unused `from typing import Union` import; module uses PEP-604 `A \| B` syntax elsewhere |
| IN-04 | info | `packages/subagent-runtime/tests/test_trace_io.py:15,84,99-102` | fixed | `d0ae3c5` | D-10 — added `caplog`-based assertion to `test_write_trace_record_swallows_oserror` verifying the WARNING-level log promised by the docstring |
| IN-05 | info | `agents/graph-wiki-agent/tests/test_ingest_trace_unit.py:15` | no-action | n/a | D-11 — no-action — review self-corrected on re-scan; `pytest` is legitimately used by `pytest.raises(BotoCoreError)` and `@pytest.mark.asyncio` |
| IN-06 | info | `agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py:532,968` | fixed | `7122996` | D-12 — qualified synth trace filenames: `synth_librarian_{query_id}.jsonl` (regular path, line 968) and `synth_codefallback_{query_id}.jsonl` (line 532); cheap insurance against future retry-after-fallback collisions |
| IN-07 | info | `packages/eval-harness/tests/test_models_toml_sweep_candidates.py:10` | fixed | `fbe6c1d` | D-13 — updated module docstring from "3 vault-thin cases" to the asserted 5–6 range, matching `code_reader_cases.json`'s post-expansion shape |
| IN-08 | info | `docs/cancellation.md:103-115,121-131` | fixed | `a5f0760` | D-14 — added `"schema_version": 1,` to both example JSON blocks (per-item cancelled record + batch terminal summary) so doc readers produce schema-complete trace writers |
| IN-09 | info | `agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py:551-570,663-670` | fixed | `a907d1b` | D-15 — refactored `apply_guardrails` to call `_compute_unresolved_wikilinks` instead of duplicating the G1 resolution algorithm inline; drift bait removed; landed together with IN-01 |

## Counts

- **Total findings:** 15 (6 warning + 9 info; 0 critical)
- **Fixed:** 13 (all 6 warnings + 7 of 9 info)
- **No-action:** 2 (IN-02, IN-05 — review self-corrected on re-scan)
- **Dismissed / Deferred:** 0

## Test Policy

Per CONTEXT.md D-18 (fix-only test policy), no new regression tests were authored solely to demonstrate the fixed failure modes for WR-01..04. The existing divergence-eval test suite (`packages/eval-harness/tests/`) covers the regex-changed paths; WR-04's fix is itself a test edit. The per-commit regression gate is `uv sync && uv run pytest packages/eval-harness/tests/ packages/subagent-runtime/tests/ agents/graph-wiki-agent/tests/ -m "not integration"` and ran green at every plan-final commit (plans 01-04).
