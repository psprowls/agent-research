---
phase: 08-host-reliability
plan: "03"
subsystem: docs
tags: [mcp, cancellation, asyncio, subagent-runtime, pool, trace, documentation]

requires:
  - phase: 08-host-reliability
    plan: "01"
    provides: SubagentPool._run_one CancelledError branch + _write_batch_terminal emitting exact trace shapes this doc captures

provides:
  - docs/cancellation.md — v1.1 cancellation contract reference: protocol, internal chain, trace shapes, known limitations, future work

affects:
  - phase-09-trace-renderer (Phase 9 renderer branches on event:batch_cancelled discriminator; shapes stabilized here)

tech-stack:
  added: []
  patterns:
    - "docs/cancellation.md style: README-style terse, code-block-heavy, no emojis, ## headers, fenced json/python/text blocks"

key-files:
  created:
    - docs/cancellation.md
  modified: []

key-decisions:
  - "Per-item trace record includes prompt_hash and item_id fields (exact pool.py shape) — not elided in doc examples"
  - "items_completed documents conservative upper-bound semantics (0 when no items completed before cancel) with note that Phase 9 can derive accurate counts from per-item records"
  - "Framing throughout: spec-conformant MCP host (not the DeepAgents CLI) per CONTEXT.md D-02"

patterns-established:
  - "docs/ directory established at repo root for OSS-release technical reference documentation"

requirements-completed:
  - MCP-09

duration: 2min
completed: 2026-05-17
---

# Phase 8 Plan 03: Cancellation Docs Summary

**210-line `docs/cancellation.md` documenting MCP cancellation protocol, FastMCP anyio-to-asyncio unwinding chain, exact pool.py trace shapes, orphan boto3 thread caveat, and v1.2+ aioboto3 future work — closes MCP-09**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-05-17T16:54:26Z
- **Completed:** 2026-05-17T16:55:51Z
- **Tasks:** 1
- **Files created:** 1

## Accomplishments

- `docs/cancellation.md` written at repo root (new `docs/` directory created).
- All five sections present in the required order: Protocol Behavior, Internal Cancellation Chain, Trace Shapes, Known Limitations (v1.1), Future Work (v1.2+).
- Trace JSON examples reflect the exact field shapes emitted by `pool.py` after Plan 01 — including `prompt_hash` (always `null`) and `item_id` fields that the CONTEXT.md examples omitted.
- Orphan-thread caveat explained with full mechanism: `BaseChatModel._agenerate` → `run_in_executor(None, self._generate, ...)` → default ThreadPoolExecutor → boto3 HTTPS continues after asyncio cancel; result silently discarded.
- MCP-09 requirement satisfied (current behavior documented).

## Section-by-Section Content

| Section | Content summary |
|---------|----------------|
| §1 Protocol Behavior | `notifications/cancelled` wire format (JSON), fire-and-forget semantics, no-response contract, race-condition tolerance, MCP spec URL |
| §2 Internal Cancellation Chain | ASCII diagram: BaseSession → anyio CancelScope → asyncio.CancelledError → wiki_query → run_all → gather → _run_one × N; explicit note that `return_exceptions=True` does NOT swallow outer cancel |
| §3 Trace Shapes | Both JSON record shapes verbatim; `event` discriminator rule; ordering invariant (batch_cancelled is last); field semantics for null tokens/cost on cancelled records; conservative items_completed count with Phase 9 note |
| §4 Known Limitations (v1.1) | Lead: "best-effort at asyncio layer, not at wire layer"; _agenerate inheritance chain; ThreadPoolExecutor mechanism; wasted call / no data loss; botocore no socket-close API; wiki_log / wiki_init immediate cancel (no fan-out) |
| §5 Future Work (v1.2+) | aioboto3/aiobotocore wire-level cancel; SIGINT/stdin-close paths; orphan-thread monitoring hooks; per-tool E2E cancel tests |

## Trace JSON Cross-Check

Per-item `cancelled` record verified against `pool.py` `_write_trace` fields:

| Doc field | pool.py source | Match? |
|-----------|---------------|--------|
| `role` | param `role` | yes |
| `model_id` | param `model_id` | yes |
| `prompt_hash` | hardcoded `None` | yes (included in doc) |
| `item_id` | `getattr(item, "id", None) or str(item)` | yes (included in doc) |
| `status` | `"cancelled"` | yes |
| `latency_ms` | `int((monotonic() - t0) * 1000)` | yes |
| `tokens_in` | `null` (response is None) | yes |
| `tokens_out` | `null` (response is None) | yes |
| `cost_usd` | `null` (`_compute_cost_usd(None, None)` → None) | yes |
| `timestamp` | `time.strftime("%Y-%m-%dT%H:%M:%SZ", gmtime())` | yes |

Batch terminal `event: batch_cancelled` record verified against `_write_batch_terminal` fields:

| Doc field | pool.py source | Match? |
|-----------|---------------|--------|
| `role` | param `role` | yes |
| `model_id` | param `model_id` | yes |
| `event` | `"batch_cancelled"` | yes |
| `items_total` | param `items_total` | yes |
| `items_completed` | param `items_completed` (0 in current call) | yes |
| `items_cancelled` | param `items_cancelled` (`len(items)` in call) | yes |
| `wall_clock_ms` | param `wall_clock_ms` | yes |
| `timestamp` | `time.strftime("%Y-%m-%dT%H:%M:%SZ", gmtime())` | yes |

## Task Commits

1. **Task 1: Write docs/cancellation.md** - `210c875` (docs)
2. **Plan metadata:** (this SUMMARY commit)

## Files Created/Modified

- `docs/cancellation.md` (210 lines) — New: v1.1 cancellation contract reference documentation

## Decisions Made

**Included `prompt_hash` and `item_id` in per-item trace example:** The CONTEXT.md interfaces block showed a simplified example without these fields. Because `_write_trace` always writes them, the doc examples match the exact schema to prevent specification drift. A reader grepping a real trace file will find the same field set.

**Documented `items_completed: 0` conservative semantics:** Current `run_all` sets `items_completed=0` in the batch terminal record (per RESEARCH.md Open Question #1 resolution). The doc notes this is a conservative upper bound and that Phase 9 can derive accurate per-status counts from per-item records.

## Deviations from Plan

None — plan executed exactly as written.

The CONTEXT.md `<interfaces>` block §3 showed simplified trace examples (omitting `prompt_hash`
and `item_id` from the per-item record). After cross-checking against `pool.py` `_write_trace`,
the doc examples include all fields. This is an accuracy improvement, not a deviation — the
plan's `must_haves.truths[3]` explicitly requires shapes that "match the exact shapes emitted by
pool.py."

## Issues Encountered

None.

## Open Questions Surfaced During Writing

**Qwen3-80B pricing for orphan-thread cost estimation:** The doc notes wasted Bedrock call cost
as the operational consequence of the orphan-thread caveat. `qwen.qwen3-next-80b-a3b` pricing is
not yet in `eval_harness/pricing.py` (per RESEARCH.md Bedrock Cost Estimate section). A future
doc update could add a concrete dollar estimate once pricing is confirmed — currently stated as
qualitative ("cost is incurred").

## Known Stubs

None — all content is factual, sourced from codebase reading and verified research.

## Threat Flags

None — documentation-only artifact; no new trust boundaries.

---
*Phase: 08-host-reliability*
*Completed: 2026-05-17*
