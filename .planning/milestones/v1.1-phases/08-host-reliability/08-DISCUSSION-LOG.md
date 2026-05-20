# Phase 8: Host Reliability - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-17
**Phase:** 8-host-reliability
**Areas discussed:** Host harness choice, Cancel-induction mechanism, `cancelled` trace event shape, Test fixture/vault strategy, Slow-model strategy, MCP-09 docs surface

---

## Host harness choice

| Option | Description | Selected |
|--------|-------------|----------|
| Extend in-process JSON-RPC client (Phase 3 pattern) | `subprocess.Popen([uv, run, graph-wiki-mcp])` with hand-built JSON-RPC frames over stdin/stdout. Zero new deps, full protocol control, deterministic. Honest framing: "spec-conformant MCP host that DeepAgents CLI also implements." | ✓ |
| Real `deepagents` CLI binary as host | Install actual deepagents + CLI; configure it to launch our server. Maximally realistic, but adds heavy test dep, version-drift risk, fragile if upstream config schema changes. | |
| `langchain-mcp-adapters` in-process client | Load own MCP server as LangChain tools inside test process. Stdio becomes in-process pipes (not real subprocess); less control over cancel timing; adds a workspace dep that isn't present. | |

**User's choice:** Extend in-process JSON-RPC client (Phase 3 pattern)
**Notes:** Shaped every downstream decision — cancel test, 6-tool test, and slow-model strategy all assume direct JSON-RPC control. "Honest framing" was the user's coinage and is now a project convention surfaced in CONTEXT.md `<specifics>`.

---

## Cancel-induction mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| MCP `notifications/cancelled` JSON-RPC | Protocol-correct: `{"jsonrpc":"2.0","method":"notifications/cancelled","params":{"requestId":<id>}}` mid-flight. Spec-aligned; tests what a well-behaved host (including DeepAgents CLI) would send. | ✓ |
| SIGINT on the subprocess (Ctrl-C simulation) | `proc.send_signal(SIGINT)`. Bypasses protocol; tests cleanup-on-exit; useful as a secondary path but weaker primary coverage. | |
| Close stdin (host-disconnect simulation) | `proc.stdin.close()`. Same downsides as SIGINT — tests EOF cleanup, not in-protocol cancel. | |
| Both: notifications/cancelled primary + SIGINT smoke | Two tests; protocol cancel is the gate, SIGINT confirms no stuck procs / orphan trace files. | |

**User's choice:** MCP `notifications/cancelled` JSON-RPC
**Notes:** SIGINT / stdin-close paths captured as deferred ideas in CONTEXT.md. Surfaced during discussion: `ChatBedrockConverse` wraps sync boto3 in a worker thread, so true mid-HTTP interruption isn't available without `aioboto3` or socket-close — "clean cancel" must be defined as the asyncio task unwinding + trace closing, with the boto3 thread completing in the background and its result discarded. This caveat is now D-05 and the centerpiece of `docs/cancellation.md`.

---

## `cancelled` trace event shape

| Option | Description | Selected |
|--------|-------------|----------|
| Per-item `status: cancelled` + one batch terminal record | Two-layer: each in-flight item writes a per-item `cancelled` line; `run_all` writes one `event: batch_cancelled` summary with items_total / completed / cancelled / wall_clock_ms. Schema purely additive. | ✓ |
| Per-item `status: cancelled` only | Minimal change; no batch summary; harder to forensically reason about a whole batch. | |
| Batch terminal record only | Single line at end; loses per-item latency-at-cancel data. | |
| Per-item + synthetic record for not-yet-started items | Most complete picture; most code; overkill for v1.1. | |

**User's choice:** Per-item `status: cancelled` + one batch terminal record
**Notes:** Schema additivity matters — Phase 2 trace renderer must keep working unchanged; Phase 9 will branch on the new `event` field. `_write_trace` gains a `cancelled` branch; new `_write_batch_terminal` helper writes the summary.

---

## Test fixture/vault strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Fresh `tmp_path` per run, init + seed inline | Each run: `wiki_init` to tmp_path → write small deterministic seed (3-5 pages, 1 source, 1 work item) → drive remaining tools. Isolated, deterministic, exercises init genuinely. Requires CWD discipline so scan doesn't walk deep-agents. | ✓ |
| Copy Phase 4 eval fixture corpus | `shutil.copytree` the eval fixture; corpus is realistic + pre-indexed but designed for divergence eval, not 6-tool sweep; init has no clean target. | |
| Snapshot of live wiki (`~/Personal/wiki/deep-agents`) | Maximally realistic; host-specific, changes constantly, maintenance burden. | |

**User's choice:** Fresh `tmp_path` per run, init + seed inline
**Notes:** Drove D-13 (CWD discipline — scan target must be `tmp_path`, not the workspace) and D-14 (one sequential test function over six independent tests, given the natural state dependency chain init → scan → ingest → query → lint → log).

---

## Slow-model strategy for cancel test

| Option | Description | Selected |
|--------|-------------|----------|
| Monkeypatch `ChatBedrockConverse` via `model_adapter.factory.make_chat_model` | Fake returns `await asyncio.sleep(N)` + canned `AIMessage`. Deterministic, no Bedrock cost. Doesn't exercise real boto3 thread-wrap — orphan-thread story verified separately. | ✓ |
| Real Bedrock with a heavy fan-out query | Most realistic; non-deterministic; costs money each run; cancel timing is brittle. | |
| Inject a fake model via `SubagentPool` task closure | Surgical, no library patching; bypasses the model-adapter → ChatBedrockConverse → thread-wrap path that's the actual orphan-call risk surface. | |

**User's choice:** Monkeypatch `ChatBedrockConverse` via `model_adapter.factory.make_chat_model`
**Notes:** Enables the cancel test to run unconditionally (no `GRAPH_WIKI_RUN_INTEGRATION=1` gate) — same status as the existing JSON-RPC stdout test. The orphan-call story moves to a verification-only manual snippet referenced in `docs/cancellation.md` (D-11).

---

## MCP-09 docs surface

| Option | Description | Selected |
|--------|-------------|----------|
| Short `docs/cancellation.md` at repo root | New file, ~100-200 lines, sections for protocol behavior, internal chain, trace shapes, known limitations, future work. OSS-release-friendly; reusable past v1.1. | ✓ |
| Section in main README | Discoverable; clutters README with implementation detail; harder to expand later. | |
| RESEARCH.md only (private to .planning) | Zero docs maintenance; invisible to users / future OSS audience; loses doc value. | |

**User's choice:** Short `docs/cancellation.md` at repo root
**Notes:** Doc is OSS-release-friendly which fits the project's "open-source-ready hygiene" constraint. The orphan-thread caveat (D-05) is the centerpiece of the "known limitations" section.

---

## Claude's Discretion

- Per-tool input shapes for the 6-tool E2E test (planner derives from `tests/unit/`).
- Seed-page content (3-5 pages with deterministic frontmatter + a wikilink chain the query test can verify).
- Test file layout (likely `tests/integration/test_mcp_e2e.py` + `tests/integration/test_mcp_cancel.py`; planner decides).
- Bedrock test budget for the 6-tool test (researcher estimates one-run cost).

## Deferred Ideas

- SIGINT and stdin-close cancel paths — file as v1.2 hardening if Ctrl-C scenarios don't unwind cleanly.
- `aioboto3` / true wire-level cancel — would drop Bedrock HTTPS request mid-flight; v1.2+ if orphan-thread overhead becomes a real cost/observability issue.
- Real `deepagents` CLI binary in tests — add a smoke test if CLI behavior diverges from spec.
- Per-tool granular E2E tests — split if the single sequential test gets too tangled or expensive.
- Trace renderer enhancements for `cancelled` records — owned by Phase 9 (OBS-04/05/06).
