# Phase 9: Trace/Observability Polish - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-17
**Phase:** 09-trace-observability-polish
**Areas discussed:** Schema version shape, Cost rollup display, Collapse semantics
**Areas presented but skipped:** Backward compat for existing traces (Claude exercised discretion — see CONTEXT.md D-04)

---

## Schema version shape

### Question 1 — How should `schema_version` be written into trace files?

| Option | Description | Selected |
|--------|-------------|----------|
| On every record | `"schema_version": 1` on every JSONL line written by `_write_trace` / `_write_batch_terminal`. Self-describing per line; matches Phase 8 additive-shape rule. | ✓ |
| Once as a file-header record | First line is a `kind: trace_header` record. Smaller per-record but headerless-file risk on crashes. | |
| Both | Header line AND per-record field. Maximum safety, slight redundancy. | |

### Question 2 — What format should the version itself take?

| Option | Description | Selected |
|--------|-------------|----------|
| Integer | `schema_version: 1`. Bump to 2 on breaking change. Simple compare; no minor/patch ambiguity. | ✓ |
| Semver string | `schema_version: "1.0.0"`. More expressive but requires parsing; additive vs breaking already encoded in policy. | |

### Question 3 — Where should the trace schema be documented?

| Option | Description | Selected |
|--------|-------------|----------|
| `docs/trace-schema.md` at repo root | Sibling to Phase 8 `docs/cancellation.md`. OSS-release-friendly. | ✓ |
| Extend `docs/cancellation.md` with a schema section | One less file but conflates a feature doc with the canonical schema reference. | |
| Inline in `cores/subagent-runtime/README.md` | Co-located with producer but harder to point external consumers at. | |

### Question 4 — What is the breaking-change policy?

| Option | Description | Selected |
|--------|-------------|----------|
| Bump on rename/remove/semantic-shift; additions free | Renderer accepts unknown future versions with a warning. Preserves Phase 8 additive-shape rule. | ✓ |
| Bump on ANY shape change, including additions | Strict but defeats additive rule; bumps constantly during normal feature work. | |

**Notes:** All four decisions stack cleanly with Phase 8 D-06/D-07 (additive-shape rule, `event`/`kind` discriminators).

---

## Cost rollup display

### Question 1 — At what granularity should the cost rollup be shown?

| Option | Description | Selected |
|--------|-------------|----------|
| Per role + per `model_id` | One line per `(role, model_id)` pair. Preserves model attribution across sweep runs — the cost story this project is named after. | ✓ |
| Per role only, with a separate per-model breakdown below | Two sections; redundant. | |
| Per role only | Simplest; loses model attribution. | |

### Question 2 — Should per-item lines also show cost?

| Option | Description | Selected |
|--------|-------------|----------|
| Per-item line includes cost | Appends `$0.000123` to each rendered record line. Catches outlier items. | |
| Only in the rollup; per-item lines unchanged | Keeps current per-line shape; less visual noise. Cost only in Summary block. | ✓ |

### Question 3 — How to format cost numbers and handle unknown-model records?

| Option | Description | Selected |
|--------|-------------|----------|
| `$0.000000` (6dp); `n/a` when `cost_usd` is null | 6dp covers sub-cent fan-out without scientific notation; nulls excluded from totals and flagged in rollup line. | ✓ |
| `$0.0000` (4dp); `n/a` for null | Less precision; rounds to $0.0000 for cheap models. | |
| Scientific notation for tiny values, fixed for >= $0.01 | Smarter format, harder to scan. | |

**Notes:** Rollup line example pattern: `scanner / claude-haiku-4-5: 10 items, 3450->1820 tokens, $0.001234 (+2 unknown)`.

---

## Collapse semantics

### Question 1 — What defines a "group" that gets collapsed by default?

| Option | Description | Selected |
|--------|-------------|----------|
| Consecutive same-role records | Walk in file order; runs of ≥N same-role per-item records collapse. Non-subagent records (`kind: query_summary`) and `event` records always full-line. Preserves chronological context. | ✓ |
| All same-role records anywhere in file | Bucket by role; discards interleaving. | |
| Consecutive same-(role, model_id) | Stricter; model switch breaks a group. | |

### Question 2 — Threshold N for collapsing

| Option | Description | Selected |
|--------|-------------|----------|
| N = 2 | Any run of 2+ same-role records collapses. Matches typical scanner/linter fan-outs of 2–4. | ✓ |
| N = 3 | Small fan-outs stay visible; risk: typical fan-outs are 2–4. | |
| N = 5 | Renderer output stays close to today's by default; collapse becomes rare. | |

### Question 3 — What the collapsed group line shows

| Option | Description | Selected |
|--------|-------------|----------|
| Role, count, status breakdown, time range, total tokens, total cost | Dense single line: counts, K_success/K_error[/K_cancelled], time range, tokens, cost. | ✓ |
| Role, count, total tokens, total cost only | Shorter; drops time range and status breakdown. | |
| Role, count, only | Minimal; forces `--expand` for any detail. | |

### Question 4 — What does `--expand` do?

| Option | Description | Selected |
|--------|-------------|----------|
| Boolean: `--expand` expands ALL groups | Reverts to today's behavior. Simplest flag; matches spec wording. | ✓ |
| Per-role: `--expand role[,role,...]` | Surgical, more plumbing. | |
| Count threshold: `--expand-threshold N` | More dials; less discoverable. | |

**Notes:** Status clauses only include nonzero categories (`K_cancelled` clause omitted if zero). Rollup lines sorted by descending total cost (D-15) so the most expensive contributor surfaces first.

---

## Claude's Discretion

- **Backward compat for existing traces** — Presented as a fourth gray area but not selected by the user. Claude took the lenient route consistent with the rest of the schema-version policy: unversioned records are inferred as `schema_version: 0`, renderer emits a one-time stderr warning per file, and renders best-effort. Captured as CONTEXT.md D-04.
- **Exact phrasing of stderr warnings** for v0 records and for future `schema_version > N` records — planner picks.
- **Whether the Summary block prints when `--expand` is set** — likely yes for parity; planner confirms.
- **Implementation shape** of the new collapsed-group renderer (new function vs streaming generator) — planner picks.
- **`query_summary` records** — whether they get a custom pretty-renderer line or use the generic `_render_trace_record` fallback. They are NOT collapsed either way.
- **Test layout** — extend existing `test_trace_viewer.py` / `test_pool.py` vs split into new files. Planner decides.

## Deferred Ideas

- Per-item cost on the rendered line (rejected in favor of rollup-only).
- `--expand role[,role,...]` and `--expand-threshold N` variants (future phase if needed).
- Trace upload/export to LangSmith / Honeycomb / OpenTelemetry (post-v1.1).
- `rich`-based renderer (excluded by CLAUDE.md §6 v1 stack constraint).
- Backfilling `schema_version` into existing on-disk fixtures (v0 inference handles them).
- Span IDs / parent-trace references / queue-depth fields (free additions; not required by OBS-04/05/06).
