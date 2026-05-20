# Phase 9: Trace/Observability Polish - Context

**Gathered:** 2026-05-17
**Status:** Ready for planning

<domain>
## Phase Boundary

Formally document and version the JSONL trace schema written by `SubagentPool` (and the ancillary `query_summary` records emitted by `query.py`), and upgrade the `graph-wiki-agent trace <file>` CLI renderer to:
1. Surface per-subagent cost using the existing per-record `cost_usd` field (populated by `eval_harness.pricing.cost_for_usage` since Phase 4) — replaces today's `Cost USD: (Phase 4)` placeholder in `cli.py:144`.
2. Collapse runs of repeated subagent-role records into a single dense summary line by default; preserve full per-line output behind `--expand`.
3. Stamp every record with `schema_version: 1` going forward; publish a documented breaking-change policy.

**In scope:**
- Add `schema_version: 1` (integer) to every record written by `SubagentPool._write_trace` and `SubagentPool._write_batch_terminal` (`cores/subagent-runtime/src/subagent_runtime/pool.py:211-258`) — purely additive, existing readers continue to work (extends the Phase 8 D-06/D-07 rule).
- Stamp `schema_version: 1` on the `query_summary` records emitted by `query.py` (the only other producer of records in `.graph-wiki/traces/`).
- Write `docs/trace-schema.md` at repo root documenting the three record shapes (per-item, `event: batch_cancelled`, `kind: query_summary`), required vs optional fields per shape, and the breaking-change policy.
- Extend `_render_trace_record` / `_aggregate_trace` / `trace` command in `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py:48-144`:
  - Replace the placeholder cost line with a real per-`(role, model_id)` rollup table.
  - Implement consecutive-same-role collapsing with threshold N=2 and a dense one-line group summary (count, status breakdown, time range, total tokens, total cost).
  - Wire `--expand` as a boolean flag that reverts to today's one-line-per-record rendering.
- Snapshot tests (`syrupy`, already in stack) lock collapsed and `--expand` output for representative trace fixtures (fan-out of 4, mixed success/error, mixed `kind: query_summary` interleaving, `event: batch_cancelled` terminator).
- Backward-compat unit test: render an unversioned trace fixture (e.g., from `cores/vault-io/tests/fixtures/round-trip-vault/.graph-wiki/traces/`) and assert renderer emits a one-time stderr warning + best-effort render — does not refuse.

**Out of scope (explicit):**
- Migrating renderer output to `rich` / `textual` — explicit v1 stack constraint (CLAUDE.md §6: "textual / rich in v1 — explicitly out of scope").
- Backfilling `schema_version` into existing on-disk trace fixtures or rewriting historical records — they are treated as `schema_version: 0` (pre-versioned) by the renderer.
- Adding new fields to the schema beyond `schema_version` (e.g., span IDs, parent references, queue depth) — pure additions are future work; v1.1 only closes OBS-04/05/06.
- Trace upload/export to external systems (LangSmith, Honeycomb, etc.) — explicitly outside v1.1 cost-frontier scope (PROJECT.md / CLAUDE.md §5).
- Real-time / streaming trace tail — `trace <file>` is a post-hoc render; live progress already lives in the `--quiet`/progress paths added in earlier phases.
- Cost recomputation in the renderer — renderer reads `cost_usd` as-written; if the record is `null` (unknown model), it stays `n/a`. No fallback pricing lookup at render time.

</domain>

<decisions>
## Implementation Decisions

### Schema versioning shape (OBS-04)

- **D-01:** **`schema_version` is written on every record** (not as a file-header line). Both `_write_trace` and `_write_batch_terminal` in `pool.py` get the field unconditionally; `query.py`'s `query_summary` writer gets it too. Rationale: each JSONL line stays self-describing — `grep` and stream-processing both work without parsing a header; mid-process crashes can't produce headerless files. Extra bytes per line are negligible vs. the existing record size.
- **D-02:** **Integer format: `schema_version: 1`.** No semver. Bump to `2` on the next breaking change. Additive changes (new optional fields, new record kinds) DO NOT bump the integer — the Phase 8 D-06/D-07 "purely additive" rule continues to apply for non-breaking growth.
- **D-03:** **Breaking-change policy:** the integer bumps when an existing field is renamed, removed, or has its meaning/units changed; new optional fields and new record kinds are free. The renderer accepts records with `schema_version` greater than the version it knows about and emits a one-line stderr warning (`warning: trace schema_version N is newer than supported (M); rendering best-effort`) — but continues to render. This is the "lenient consumer" half of the policy; producers (pool, query) are strict.
- **D-04:** **`schema_version: 0` is reserved for the pre-Phase-9 unversioned shape** — the renderer infers it when the field is absent on a record and emits a one-time stderr warning per file (not per record). Existing fixture traces under `cores/vault-io/tests/fixtures/.../traces/` are NOT rewritten; they continue to render correctly under the v0-inference path. This is Claude's judgment call (user did not select the "backward compat" gray area to discuss, so the renderer takes the lenient route consistent with the rest of the policy).

### Schema documentation (OBS-04)

- **D-05:** **`docs/trace-schema.md` at repo root**, sibling to the Phase 8 `docs/cancellation.md`. Required sections: (1) overview of `.graph-wiki/traces/` directory layout and filename convention; (2) per-record-shape spec — per-item subagent record, `event: batch_cancelled` terminator, `kind: query_summary` — with field tables (name, type, required?, semantics); (3) `schema_version` field — what it is, lenient-consumer / strict-producer policy, when it bumps; (4) "additive-shape" rule (what doesn't bump the version) cross-referencing Phase 8 D-06/D-07; (5) v0 (unversioned) compatibility note; (6) examples copied from real fixtures. Length target: ~150–250 lines. OSS-release-friendly.
- **D-06:** **`docs/cancellation.md` cross-references `docs/trace-schema.md`** for the `event: batch_cancelled` record shape rather than duplicating field tables. Phase 9 adds a one-line link in cancellation.md back to trace-schema.md — no content rewrite.

### Cost rollup display (OBS-05)

- **D-07:** **Cost rollup is grouped by `(role, model_id)`** — one line per pair in the renderer's Summary block. Rationale: the same role can run on different models across a sweep run (Phase 7 cost-frontier sweep produced exactly this pattern); aggregating by role alone would hide model attribution which is the cost story this whole project exists to tell.
- **D-08:** **Per-item record lines DO NOT show cost.** Cost appears only in the Summary rollup. Per-item rendering remains the current shape (`[ts] role model item status latency tokens_in->tokens_out`) so existing snapshot expectations / muscle memory don't break, and the line stays scannable. If a future need to spot outlier-item cost emerges, it lands in a different phase.
- **D-09:** **Cost format: `$0.000000` (6 decimal places)** — enough precision to render sub-cent fan-out costs without scientific notation; consistent with `_compute_cost_usd` returning a `float`. `cost_usd: null` records render as `n/a` and are EXCLUDED from rollup `(role, model_id)` totals; the rollup line appends a count of excluded records when any exist, e.g. `scanner / claude-haiku-4-5: 10 items, 3450->1820 tokens, $0.001234 (+2 unknown)`.
- **D-10:** **Renderer reads `cost_usd` as-written**; it does not call `eval_harness.pricing.cost_for_usage` itself. Avoids cross-package coupling at render time (CLI lives in `agents/graph-wiki-agent`, pricing lives in `cores/eval-harness`) and keeps the renderer pure-stdlib. Pricing changes between trace-write and trace-render are out of scope.

### Collapse semantics (OBS-06)

- **D-11:** **Group definition: consecutive same-`role` per-item records.** Walk the file in order; a "group" is a maximal run of ≥ 2 records where `role` matches AND the record has NO `event` key AND no `kind` key (i.e., per-item subagent records only). Non-subagent records (`kind: query_summary`) and event records (`event: batch_cancelled`) always render full-line as themselves and break any run in progress — they cannot belong to a group.
- **D-12:** **Collapse threshold N = 2.** Any run of 2+ qualifying same-role records collapses by default. Isolated single records still render as full per-item lines. Rationale: typical scanner / linter fan-outs are 2–4 items; N≥3 would leave most fan-outs uncollapsed.
- **D-13:** **Collapsed group summary line shape** (single dense line per group):
  ```
  [<ts_first> .. <ts_last>] <role> x<N>: <K_success> success / <K_error> error[ / <K_cancelled> cancelled], <sum_tokens_in>->>sum_tokens_out> tokens, $<sum_cost> [(+<K_unknown_cost> unknown)]
  ```
  Status breakdown only includes nonzero categories. If `K_cancelled = 0`, omit the cancelled clause. If all costs are null/unknown, show `$n/a (N unknown)`. Timestamps are the actual `timestamp` field of the first and last record in the run, ISO-8601 as written.
- **D-14:** **`--expand` is a single boolean flag** on the `trace` command: `graph-wiki-agent trace <file> --expand`. When present, collapsing is disabled and every record renders as its current full per-item line (today's behavior). No per-role / per-threshold variants in v1.1 — matches the spec wording "drills into the full event stream."
- **D-15:** **Sort/ordering inside the rollup:** the per-`(role, model_id)` rollup lines are sorted by descending total cost (with `n/a` groups last), so the most expensive contributor surfaces first. Tie-breaker: ascending alphabetical role then model_id for determinism in snapshot tests.

### Claude's Discretion

- **Exact wording of the v0 (unversioned) stderr warning string** — planner picks the phrasing; just needs to be a single line, mention the file path, and emit at most once per file.
- **Whether the renderer prints the Summary block when `--expand` is set** — likely YES for parity (rollup is independent of collapsing), but planner can confirm against the snapshot fixtures.
- **Whether the new collapsed-group renderer is implemented as a new function (`_render_collapsed_group`) or refactored into a streaming generator** — pure implementation choice; planner picks the smaller diff.
- **Whether `query_summary` records get their own pretty-renderer line or render via the existing generic `_render_trace_record` fallback** — planner picks; current fallback handles them adequately, but a one-line `query_id`/`pages_drilled` summary would read better. Either way: NOT collapsed, always full-line.
- **Test layout** — likely `agents/graph-wiki-agent/tests/unit/test_trace_viewer.py` (extend existing) for the renderer changes; `cores/subagent-runtime/tests/test_pool.py` (extend existing) for the `schema_version` write path. Planner decides whether to keep extending or split into new files.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap / requirements
- `.planning/ROADMAP.md` §"Phase 9: Trace/Observability Polish" — phase goal, dependency on Phase 2 (trace infrastructure), success criteria, requirement IDs (OBS-04, OBS-05, OBS-06).
- `.planning/REQUIREMENTS.md` §"OBS" — full text for OBS-04, OBS-05, OBS-06; mapping table entries confirming Phase 9 ownership.
- `.planning/PROJECT.md` §"Active" — v1.1 milestone scope including OBS items.

### Prior-phase decisions (still binding)
- `.planning/phases/02-subagent-fan-out-runtime/02-CONTEXT.md` — original trace shape and the `SubagentPool._write_trace` contract.
- `.planning/phases/04-eval-harness/04-CONTEXT.md` — `_compute_cost_usd` + `eval_harness.pricing.cost_for_usage` integration that populates the `cost_usd` field this phase displays.
- `.planning/phases/08-host-reliability/08-CONTEXT.md` D-06, D-07, D-08 — **additive-shape rule** (existing readers ignore unknown fields), per-item `status: cancelled` shape, batch terminal `event: batch_cancelled` shape discriminator. Phase 9's `schema_version` and renderer must preserve this contract.
- `docs/cancellation.md` (written in Phase 8) — prose source-of-truth for cancellation-trace semantics; Phase 9 schema doc cross-references it rather than rewriting it.

### Reference code (read before planning)
- `cores/subagent-runtime/src/subagent_runtime/pool.py:182-263` — `_write_trace` and `_write_batch_terminal`. Both gain `schema_version: 1` in their record dicts.
- `cores/subagent-runtime/src/subagent_runtime/pool.py:266-284` — `_compute_cost_usd` (lazy import of `eval_harness.pricing.cost_for_usage`); explains why `cost_usd` may be `None`.
- `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py:48-144` — `_render_trace_record`, `_aggregate_trace`, and the `trace` Typer command. All three are extended in this phase.
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py` — emits the `kind: query_summary` JSONL record; this writer also gets `schema_version: 1`.
- `agents/graph-wiki-agent/tests/unit/test_trace_viewer.py` — current test scaffolding for the trace command; extension target for collapsed/expand snapshot tests.
- `cores/vault-io/tests/fixtures/round-trip-vault/.graph-wiki/traces/*.jsonl` — real-world unversioned trace samples used for the v0 backward-compat render test.
- `cores/eval-harness/src/eval_harness/pricing.py` — pricing source consulted only at write time; renderer does NOT call it (D-10).

### Stack / framework references
- `CLAUDE.md` §"Markdown / Frontmatter / Search" — confirms `typer.echo` (no `rich`) is the stack constraint; reinforces the out-of-scope marker for renderer-prettification.
- `CLAUDE.md` §"Testing" — `syrupy` is in the stack; this phase uses it for collapsed/expand snapshot tests.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `_render_trace_record(record: dict) -> str` (`cli.py:48-73`) — already a single-line renderer; collapsing wraps it (full-line path on `--expand`, replaced by the group summary in default mode).
- `_aggregate_trace(records: list[dict]) -> dict` (`cli.py:76-107`) — already aggregates by role; needs a second key (`model_id`) added and cost accumulation (`cost_usd`, null-tracking) bolted on.
- `SubagentPool._write_trace` / `_write_batch_terminal` (`pool.py:182-263`) — both already write a `record: dict[str, Any]` constructed inline before `json.dumps`; adding one key is a one-line diff per writer.
- `_compute_cost_usd` (`pool.py:266-284`) already populates `cost_usd` on every per-item record; the renderer only needs to read it.

### Established Patterns
- **Additive trace evolution** — Phase 8 D-06/D-07 lock in the rule: new fields are free; the discriminator for record kind is `event` presence (and now `kind` for query summaries). Phase 9 strictly extends this — `schema_version` is a new optional-on-read field that producers populate unconditionally.
- **Trace writers never raise** — both writers in `pool.py` swallow `OSError` at WARNING (AI-SPEC Failure Mode #2). New code in this phase preserves the contract.
- **Lazy import for cross-package dependency** — `_compute_cost_usd` lazy-imports `eval_harness.pricing` to avoid a hard runtime dependency. Phase 9 keeps the renderer in `agents/graph-wiki-agent` free of any `eval_harness` import (D-10).
- **Snapshot testing for stable CLI output** — `syrupy` is in the stack; existing `test_trace_viewer.py` uses subprocess-driven assertions, but new collapsed/expand tests should use `syrupy` snapshots for robustness.

### Integration Points
- **Producers:** `cores/subagent-runtime/src/subagent_runtime/pool.py` (`_write_trace`, `_write_batch_terminal`) and `agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py` (`query_summary` writer). All three add `"schema_version": 1` to the record dict before `json.dumps`.
- **Consumer:** `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py` `trace` command. All renderer changes (collapse logic, cost rollup, `--expand` flag, schema-version-aware warning emission) land here.
- **Doc:** `docs/trace-schema.md` at repo root. New file; cross-linked from `docs/cancellation.md`.

</code_context>

<specifics>
## Specific Ideas

- The cost-rollup line must show model_id (D-07) — the cost story this project is named after only reads if model attribution is visible. The Phase 7 sweep produces records with different `model_id` values per role; this is the first phase that reads them back.
- The unversioned-trace fixtures under `cores/vault-io/tests/fixtures/round-trip-vault/.graph-wiki/traces/` are the canonical v0 backward-compat test material — don't synthesize new fixtures, exercise the renderer against these directly.

</specifics>

<deferred>
## Deferred Ideas

- **Per-item cost on the rendered line** — explicitly chose Summary-only display (D-08). If a need to spot single outlier-item cost emerges later, lands in its own phase.
- **`--expand role[,role,...]` and `--expand-threshold N` variants** — rejected for v1.1; boolean `--expand` covers the spec wording. Per-role / threshold variants can land in a future phase if user-facing experience demands them.
- **Trace upload/export to LangSmith / Honeycomb / OpenTelemetry** — outside v1.1 cost-frontier scope; future work past v1.1.
- **`rich`-based renderer (color, tables, progress bars)** — explicit v1 stack constraint excludes it (CLAUDE.md §6). Revisit if the project drops Bedrock-only / one-developer constraints.
- **Backfilling `schema_version` into existing on-disk trace fixtures** — rewriting historical records is not worth it; v0 inference handles them.
- **Span IDs / parent-trace references / queue-depth fields in records** — pure additions; not required by OBS-04/05/06; can land in any future phase without bumping `schema_version`.

</deferred>

---

*Phase: 9-trace-observability-polish*
*Context gathered: 2026-05-17*
