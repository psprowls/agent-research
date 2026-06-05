# Design: `gw --verbose` (`-v` / `-vv`)

**Date:** 2026-06-01
**Status:** Approved — ready for implementation planning
**Topic:** Add a global verbose flag to the `gw` CLI that streams a live, step-by-step log of execution (fan-out start/completion, per-item progress, and existing module logs) to stderr.

## Goal

Give the operator real-time visibility into what `gw` is doing behind the scenes — most importantly every subagent fan-out start and completion — without polluting `stdout` or changing the post-hoc `gw trace` workflow.

## Background (current state)

- **Logging is wired but dark in the CLI.** Almost every module already owns a `logging.getLogger(__name__)` (`graph_wiki_core/commands/*.py`, `subagent_runtime/pool.py`, `subagent_runtime/trace_io.py`, `wiki_io/*`, `graph_io/domains.py`, `eval_harness/*`). The MCP server configures logging at `graph_wiki_mcp/server.py:65` (`basicConfig(stream=sys.stderr, level=WARNING)` plus boto3/botocore pinned to WARNING at `server.py:74-75`). **The `gw` CLI configures no logging at all**, so those existing log calls currently surface nothing.
- **A post-hoc trace system already exists.** `SubagentPool.run_all()` (`subagent_runtime/pool.py`) writes a JSONL record per fan-out item (success/error/cancelled) via `write_trace_record` (`subagent_runtime/trace_io.py`), plus a `batch_cancelled` terminal record. `gw trace <file>` (`graph_wiki_cli/cli.py:386`) renders that JSONL as a timeline with per-`(role, model_id)` cost rollups, using the local `_render_trace_record` helper (`cli.py:197`). The pool does **not** currently emit live human-readable progress.

A `--verbose` flag is therefore largely about (a) turning on the instrumentation that already exists, and (b) adding fan-out lifecycle emissions to the pool.

## Chosen approach: logging-based, decoupled

The pool and command modules emit fan-out lifecycle and per-item lines **unconditionally** through the `logging` module. A new root `--verbose/-v/-vv` callback installs a stderr handler at INFO (`-v`) or DEBUG (`-vv`). The pool never learns about "verbose" — the entry point decides what surfaces.

Per-item completion lines are rendered with the existing record renderer, moved into `subagent_runtime/trace_io.py` so it is the single source of truth shared by both the pool (live) and `gw trace` (post-hoc).

### Approaches considered and rejected

- **Explicit event callback** threaded through `run_all` and every `run_*` command. Rejected: invasive signature changes across the pool and every command, reinvents logging, and does not surface the existing module logs.
- **Live-tail the JSONL trace file.** Rejected: file-polling races with buffered writes, cannot show fan-out start/summary or non-fan-out steps, breaks across multiple trace files, and misses module logs entirely.

## CLI surface

A new **root Typer callback** on `app` (none exists today) adds the global flag, parsed before the subcommand:

```
gw -v query "..."      # INFO  tier
gw -vv scan            # DEBUG tier
gw query "..."         # silent (today's behavior, unchanged)
```

- `-v` is a counted flag (`-v`, `-vv`); `--verbose` is an alias for a single `-v`. A count `>= 2` selects the DEBUG tier.
- All verbose output goes to **stderr**. `stdout` stays clean, so `gw -v query ... --json | jq` still works.
- **Interaction with the existing per-command `--quiet`** (on `query`): `--quiet` only governs that command's own progress/meta line on `stdout`; it does **not** silence `-v` (different stream, different purpose). Documented in help text.
- Absent the flag: no handler is installed and there is no new stderr output (today's behavior preserved exactly).

## What gets emitted at each tier

| Event | `-v` (INFO) | `-vv` (DEBUG) |
|---|---|---|
| Fan-out **start** (role, model, item count, concurrency) | yes | yes |
| Per-item **completion** line (trace format) | yes | yes |
| Fan-out **summary** (n ok / n err, wall-clock) | yes | yes |
| Per-item **start** line (after semaphore acquire) | no | yes |
| Existing module logs (lint/query/scan/ingest `getLogger`) | INFO+ | DEBUG+ |
| boto3 / botocore noise | suppressed | suppressed |

- **Per-item completion lines reuse `gw trace`'s exact format** via the shared renderer. Live output is inherently *expanded* (one line per item); the consecutive-same-role collapsing that `gw trace` does by default is impossible on a live stream because it needs future records.
- **Fan-out start/summary** lines are aggregate (no per-item record exists yet), so they use a simple consistent shape:
  - `-> fan-out start: role=librarian model=...haiku-4-5 items=8 concurrency=5`
  - `ok fan-out done: 8 ok / 0 err in 3.42s`
- **Per-item start** (`-vv` only) is emitted *inside the semaphore* so it reflects real dispatch order under concurrency — useful for spotting a hung item.

## Components and changes

1. **`subagent_runtime/trace_io.py`**
   - Move the record renderer here as a public `render_trace_record(record: dict) -> str` (currently `_render_trace_record` at `graph_wiki_cli/cli.py:197`). Single source of truth for the per-record line format.
   - Change `write_trace_record(...)` to **return the record dict** it builds. Backward compatible — current callers ignore the return value.

2. **`graph_wiki_cli/cli.py`**
   - The `trace` command imports `render_trace_record` from `trace_io` instead of defining its own; drop the local `_render_trace_record`. The collapsing/aggregation helpers (`_render_collapsed_group`, `_aggregate_trace`, `_is_groupable`) stay in `cli.py` — they are post-hoc-only.
   - Add the root callback wiring `-v/-vv/--verbose` to `configure_verbose_logging`.

3. **New `graph_wiki_cli/logging_config.py`** — `configure_verbose_logging(verbosity: int) -> None`:
   - `verbosity == 0`: no-op (no handler installed).
   - Installs a stderr `StreamHandler` on the root logger at INFO (`1`) / DEBUG (`>= 2`), with a `%(levelname)s %(name)s: %(message)s` formatter for general module logs.
   - Installs a **dedicated handler** on the fan-out trace logger with a bare `%(message)s` formatter and `propagate=False`, so per-item trace lines stay byte-identical to `gw trace`.
   - Pins `boto3`/`botocore`/`urllib3` to WARNING (mirrors `graph_wiki_mcp/server.py:74-75`).
   - Idempotent: safe to call once per process; does not duplicate handlers.

4. **`subagent_runtime/pool.py`**
   - `run_all`: log a fan-out **start** line (INFO) before dispatch and a **summary** line (INFO) after `gather`.
   - `_run_one`: log a per-item **start** line (DEBUG) after acquiring the semaphore; on each `_write_trace`, log `render_trace_record(record)` at INFO through a dedicated logger (e.g. `subagent_runtime.pool.trace`).
   - The pool stays ignorant of verbosity — it always logs; the installed handler (or its absence) decides what shows.

## Testing

- **Pool `caplog` tests:** `run_all` over a fake task emits exactly one start record, N completion records in trace format, and one summary; per-item-start lines appear only at DEBUG level.
- **Renderer parity test:** the live-emitted string equals what `gw trace --expand` produces for the same record (guards the shared-renderer refactor — both call the same `render_trace_record`).
- **CLI tests:** `gw -v` / `gw -vv` set the handler level correctly; absent flag installs no handler and produces no stderr noise; `--json` stdout stays uncontaminated when `-v` is on.
- **Backward-compat test:** `write_trace_record` still writes the same JSONL record after gaining a return value.

## Out of scope

- MCP server logging — already configured at `graph_wiki_mcp/server.py:65`; unchanged.
- No env-var control (`GW_VERBOSE`) — YAGNI for now.
- No change to the JSONL trace schema or to `gw trace` post-hoc behavior.
- No new per-command `--verbose` flags (global-only, per the scope decision).
