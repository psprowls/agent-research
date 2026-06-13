# Batch ingest limit — design

**Date:** 2026-06-12
**Status:** Approved (pre-implementation)

## Problem

Batch ingest (pointing the ingest command at a top-level `raw/<kind>/` folder)
currently processes **every** unit in the folder. For large inboxes this is an
all-or-nothing fan-out with no way to take a bite-sized first pass. We want the
user to cap a batch to the first N units, defaulting to 10.

## Scope decision

Batch ingest exists **only** in the Claude-Code plugin layer today:

- `plugins/graph-wiki/commands/ingest.md` (orchestrator prose) detects a batch
  via the prep script `plugins/graph-wiki/skills/graph-wiki/scripts/ingest_source.py`,
  which calls `build_batch_ingest_brief()` in the shared `wiki-io` package.
- It then fans out one `ingestor` sub-agent per unit (≤4 concurrent).

The Bedrock surface (`gw wiki ingest <path>`, MCP `wiki_ingest`) is strictly
single-file (`run_ingest_source`) — there is **no** batch/SubagentPool ingest
orchestrator in `graph-wiki-core`.

**Decision:** put the limit in the shared `wiki-io` brief builder so it is
defined and tested once, and wire only the CC-plugin surface to expose it. The
Bedrock path inherits a limit-aware brief for free if/when batch ingest is built
there. **No new Bedrock orchestrator is built as part of this change.**

## Contract

### Shared layer (`wiki-io`)

`build_batch_ingest_brief()` gains `limit: int | None = 10`:

- `limit` is an integer cap; `None` means "no cap" (ingest all).
- `enumerate_batch_units()` is **unchanged** — it still enumerates *all* units,
  sorted by path. The brief builder slices.
- "First N" = the first N units by the existing path sort (deterministic).

Brief shape (additions marked **new**):

| key | meaning |
|---|---|
| `units` | the (possibly truncated) list to ingest — first N by path |
| `unit_count` | `len(units)` after the limit — what actually gets ingested |
| `total_count` | **new** — total discovered before limiting |
| `limited` | **new** — `bool`, `True` when `total_count > unit_count` |
| `is_batch`, `kind_folder`, `root`, `state_gate` | unchanged |

When `limit is None` or `total_count <= limit`: `unit_count == total_count` and
`limited is False`.

### CC-plugin surface

Invocation: `/graph-wiki:ingest <path> [--limit N] [--all]`

- `--limit N` — cap at N units. Default **10** when omitted.
- `--all` — ingest everything (no cap).
- **Precedence:** `--all` wins over `--limit` when both are passed (resolves to
  `limit=None`). No error; simplest, least surprising.

The prep script parses both, resolves `limit = None if args.all_units else args.limit`,
and passes it into `build_batch_ingest_brief(..., limit=limit)`.

### Confirm prompt

`ingest.md`'s one-confirm step becomes truncation-aware:

- Limited: _"raw/specs: 30 units found, ingesting first 10 (pass `--all` for
  everything). NEW concept/ADR pages become proposals in `wiki/proposals/`, not
  real pages. Proceed?"_
- Not limited (≤N, or `--all`): reads as today — _"raw/specs: N units. Will
  ingest all; …"_

The per-unit dispatch contract (one `ingestor` sub-agent per unit, ≤4
concurrent, serial commit phase, archive-on-success) is **unchanged** — it just
receives the already-sliced unit list.

## Implementation

Files touched (4):

1. **`packages/wiki-io/src/wiki_io/ingest_source.py`** — add `limit: int | None
   = 10` to `build_batch_ingest_brief()`. Enumerate all units, set
   `total_count = len(all_units)`, slice (`units = all_units[:limit]` when
   `limit` is set, else all), set `unit_count = len(units)` and
   `limited = total_count > unit_count`. `enumerate_batch_units()` untouched.

2. **`plugins/graph-wiki/skills/graph-wiki/scripts/ingest_source.py`** — argparse
   gains `--limit` (`type=int`, `default=10`) and `--all` (`store_true`). Resolve
   `limit = None if args.all_units else args.limit`; pass into
   `build_batch_ingest_brief(..., limit=limit)`. Update the batch print block to
   surface truncation, e.g. `Batch: raw/specs (10 of 30 units, --all for everything)`.

3. **`plugins/graph-wiki/commands/ingest.md`** — document `--limit N` / `--all`
   in the batch-mode section; update the one-confirm prompt prose to the
   truncation-aware wording above.

4. **`plugins/graph-wiki/agents/ingestor.md`** — **no change** (operates on
   whatever unit it is handed).

No migration, no graph/wiki schema change, no Bedrock orchestrator — consistent
with the repo's "no migrations until v2.0" convention.

## Testing

- **`packages/wiki-io/tests/test_batch_ingest_brief.py`** — new cases:
  - default limit 10 truncates a >10-unit dir → `unit_count == 10`,
    `total_count` correct, `limited is True`, `units` is first-10-by-path.
  - `limit` larger than the dir → all units, `limited is False`.
  - `limit is None` (the `--all` path) → all units, `limited is False`.
  - `limit` exactly equals the unit count → not limited.
  - assert ordering is the existing path sort.

- **`packages/graph-wiki-cli/tests/unit/test_plugin_claude_scripts.py`** —
  prep-script cases:
  - `--limit N` flows through to the brief.
  - `--all` yields `limit=None` (all units).
  - `--all` overrides `--limit` when both are passed.
  - default (no flag) caps at 10.
  - batch print shows the `total_count` / truncation form.

## Out of scope

- A Bedrock-surface batch ingest orchestrator (`gw`/MCP). The shared brief is
  made limit-aware so this is a clean future add, but it is not built here.
- Changes to the per-unit fan-out, concurrency cap (4), or commit phase.
