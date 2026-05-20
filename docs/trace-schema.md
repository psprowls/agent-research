# Trace Schema for `graph-wiki-agent`

This document is the authoritative reference for the JSONL records written by
`graph-wiki-agent` into `.code-wiki/traces/` under any wiki root. It is intended
for operators reading raw trace files with `grep` / `jq`, for downstream tooling
that parses those files, and for future maintainers extending the schema. It
covers the directory layout, the three record shapes that appear in those
files, the `schema_version` field and the rules for evolving it, the
additive-shape contract inherited from Phase 8, the v0 (pre-versioned)
compatibility note, and a fully-worked example for each shape.

**v1.1 scope:** `schema_version: 1` is the first formal version of the trace
schema. Records written before Phase 9 carry no `schema_version` field and are
treated as v0 — rendered best-effort by the `graph-wiki-agent trace` CLI, never
rewritten on disk. Producers (`SubagentPool`, the `query` command) always stamp
`schema_version: 1` on every record going forward.

---

## 1. Directory Layout and Filename Convention

Trace files live under `<wiki_root>/.code-wiki/traces/`. The directory is
created on demand by the writer the first time a fan-out batch or a query
summary needs to be persisted.

Two filename patterns appear in that directory:

| Pattern                              | Writer                                           | Open mode | Contents                                                                                 |
| ------------------------------------ | ------------------------------------------------ | --------- | ---------------------------------------------------------------------------------------- |
| `{int_timestamp}_{uuid8}.jsonl`      | `SubagentPool` (per-batch fan-out trace)         | append    | Zero or more per-item subagent records, optionally terminated by one batch event record. |
| `query_{query_id}.jsonl`             | `graph-wiki-agent query` (per-query summary)      | write     | Exactly one `kind: query_summary` record, one line.                                      |

`{int_timestamp}` is a Unix-epoch integer captured when the batch starts.
`{uuid8}` is an 8-character random suffix that disambiguates concurrent batches
started in the same second. `{query_id}` is the 12-character hexadecimal id
generated when the `query` command starts.

Each file is JSONL — one independent JSON object per line, UTF-8, terminated by
`\n`. Lines are appended atomically per write call; readers MAY assume that any
fully-terminated line is a complete record.

---

## 2. Per-Record Shapes

`graph-wiki-agent` writes three record shapes into `.code-wiki/traces/`. Readers
distinguish them by the presence of two discriminator keys: a record with an
`event` key is a batch event record; a record with a `kind` key is a query
summary record; a record with neither is a per-item subagent record.

### 2.1 Per-Item Subagent Record

Written by `SubagentPool._write_trace` once per item processed by a fan-out
batch. One record is appended whether the item succeeded, errored, or was
cancelled. The record carries no `event` and no `kind` key.

| Field          | Type                       | Required | Semantics                                                                                                         |
| -------------- | -------------------------- | -------- | ----------------------------------------------------------------------------------------------------------------- |
| `schema_version` | integer                  | yes      | Always `1` going forward — see §3. Absent on v0 records.                                                          |
| `role`         | string                     | yes      | Subagent role name — e.g. `librarian`, `scanner`. Used as the rollup key in the trace renderer.                   |
| `model_id`     | string                     | yes      | Bedrock model identifier — e.g. `us.anthropic.claude-haiku-4-5-20251001-v1:0`. Used with `role` for cost rollups. |
| `prompt_hash` | string \| null              | yes      | Stable hash of the rendered prompt; reserved for future use, `null` until populated upstream.                     |
| `item_id`      | string                     | yes      | Identifier of the input item — page path, source path, or `str(item)` fallback.                                   |
| `status`       | string                     | yes      | One of `success`, `error`, `cancelled`. Discriminator for outcome.                                                |
| `latency_ms`   | integer                    | yes      | Wall-clock duration from item dispatch to terminal state, milliseconds.                                           |
| `tokens_in`    | integer \| null            | yes      | Input token count from Bedrock `usage_metadata`. `null` if the Bedrock response was discarded (error / cancel).   |
| `tokens_out`   | integer \| null            | yes      | Output token count from Bedrock `usage_metadata`. `null` under the same conditions as `tokens_in`.                |
| `cost_usd`     | number \| null             | yes      | USD cost computed at write time from `eval_harness.pricing`. `null` if tokens are unknown or model is unpriced.   |
| `timestamp`    | string                     | yes      | ISO-8601 UTC timestamp in seconds precision — `YYYY-MM-DDTHH:MM:SSZ`.                                             |
| `error`        | string                     | optional | Present only when `status == "error"`. Short error description (stringified exception).                           |

`cost_usd` is read by the renderer as-written — there is no fallback pricing
lookup at render time, so a `null` value stays `null` (rendered as `n/a`).

Example (the leading `schema_version: 1` shown here is what v1 producers emit):

```json
{
  "schema_version": 1,
  "role": "librarian",
  "model_id": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
  "prompt_hash": null,
  "item_id": "packages/lattice-curator-core/context.md",
  "status": "success",
  "latency_ms": 4921,
  "tokens_in": null,
  "tokens_out": null,
  "cost_usd": null,
  "timestamp": "2026-05-14T13:53:00Z"
}
```

### 2.2 Batch Event Record (`event: batch_cancelled`)

Written by `SubagentPool._write_batch_terminal` exactly once when an in-flight
fan-out is cancelled mid-flight by a `notifications/cancelled` notification
from the MCP host. It is appended after all per-item `cancelled` records for
the same batch — it is always the last line in the file.

| Field            | Type    | Required | Semantics                                                                                              |
| ---------------- | ------- | -------- | ------------------------------------------------------------------------------------------------------ |
| `schema_version` | integer | yes      | Always `1` going forward — see §3.                                                                     |
| `role`           | string  | yes      | Subagent role of the cancelled batch.                                                                  |
| `model_id`       | string  | yes      | Bedrock model identifier of the cancelled batch.                                                       |
| `event`          | string  | yes      | Always `batch_cancelled` for this shape. Discriminator: per-item records never carry `event`.          |
| `items_total`    | integer | yes      | Total number of items the batch was started with.                                                      |
| `items_completed`| integer | yes      | Items that reached `status: success` before the cancel arrived. Conservative count: `0` if unknown.    |
| `items_cancelled`| integer | yes      | Items that received `CancelledError`. Upper bound: equals `items_total` when no items completed.       |
| `wall_clock_ms`  | integer | yes      | Wall-clock duration from batch start to the moment `run_all` caught the outer cancel, milliseconds.    |
| `timestamp`      | string  | yes      | ISO-8601 UTC timestamp in seconds precision.                                                           |

See also `docs/cancellation.md` for the cancellation propagation chain that
produces this record — the internal handler unwinding, the `asyncio.gather`
re-raise semantics, and the v1.1 orphan-thread limitation are documented there
and are not repeated here. This document defines only the on-disk shape.

Example:

```json
{
  "schema_version": 1,
  "role": "librarian",
  "model_id": "qwen.qwen3-next-80b-a3b",
  "event": "batch_cancelled",
  "items_total": 5,
  "items_completed": 0,
  "items_cancelled": 5,
  "wall_clock_ms": 1243,
  "timestamp": "2026-05-17T14:23:01Z"
}
```

### 2.3 Query Summary Record (`kind: query_summary`)

Written by `graph-wiki-agent query` exactly once per query, into a dedicated
`query_{query_id}.jsonl` file containing a single line. The discriminator key
is `kind` — per-item and batch-event records never carry a `kind` key.

| Field            | Type    | Required | Semantics                                                                                       |
| ---------------- | ------- | -------- | ----------------------------------------------------------------------------------------------- |
| `schema_version` | integer | yes      | Always `1` going forward — see §3.                                                              |
| `kind`           | string  | yes      | Always `query_summary` for this shape.                                                          |
| `query_id`       | string  | yes      | 12-character hexadecimal id matching the filename.                                              |
| `query`          | string  | yes      | The verbatim query string the user passed.                                                      |
| `top_k`          | integer | yes      | Requested top-K page count for the initial retrieval.                                           |
| `pages_retrieved`| integer | yes      | Number of pages actually returned by retrieval (may be `< top_k` on a small vault).             |
| `pages_drilled`  | integer | yes      | Number of pages the librarian drilled into during synthesis.                                    |
| `code_fallback`  | boolean | optional | `true` when retrieval fell back to source-code search because the wiki had no matches.          |
| `started_at`     | string  | yes      | ISO-8601 UTC timestamp with microsecond precision, captured at query start.                     |
| `ended_at`       | string  | yes      | ISO-8601 UTC timestamp with microsecond precision, captured after guardrails resolve.           |

Example:

```json
{
  "schema_version": 1,
  "kind": "query_summary",
  "query_id": "07ae8b630300",
  "query": "What concepts are documented in the wiki?",
  "top_k": 3,
  "pages_retrieved": 3,
  "pages_drilled": 3,
  "code_fallback": false,
  "started_at": "2026-05-15T01:43:28.152734Z",
  "ended_at": "2026-05-15T01:43:42.817040Z"
}
```

---

## 3. The `schema_version` Field

`schema_version` is an integer stamped on every record by every producer. It is
written as the first key of the record so that `head -c 64 file.jsonl` is
enough to identify the version on a partial line. There is no separate file
header — each line is self-describing, which keeps `grep` and stream-processing
pipelines working without parsing a preamble.

**Format:** positive integer. No semver, no dotted form, no leading zero.
`schema_version: 1` is the first formal version. The next breaking change bumps
to `schema_version: 2`.

**Producer policy (strict):** every record written by an in-repo producer MUST
carry `schema_version`. Forgetting it on a new writer is a bug; the Phase 9 unit
tests pin the field on each known writer.

**Consumer policy (lenient):** the `graph-wiki-agent trace` renderer accepts any
`schema_version` value and renders best-effort. When it encounters a value
higher than the highest version it knows about, it emits a single stderr line
of the form:

```
warning: trace schema_version N is newer than supported (M); rendering best-effort
```

— and proceeds with rendering. This lenient-consumer / strict-producer split
keeps older renderers usable against newer trace files for as long as the new
fields are additive.

**Bump rules:** `schema_version` bumps when an existing field is **renamed**,
**removed**, or has its **meaning or units changed**. It does NOT bump when a
new optional field is added, when a new record kind (new `event` or `kind`
value) is introduced, or when an existing optional field becomes populated where
it previously stayed `null`. Those evolutions are governed by the additive-shape
rule in §4.

---

## 4. The Additive-Shape Rule

The trace schema evolves additively by default. New optional fields and new
record kinds are free — they do not bump `schema_version`. This is the contract
established in Phase 8 and recorded in
`.planning/phases/08-host-reliability/08-CONTEXT.md` (decisions D-06 and D-07):
existing readers ignore unknown keys, and new record kinds are distinguished by
a new value of the `event` or `kind` discriminator rather than a wholesale shape
change.

That rule is why the `event: batch_cancelled` record (added in Phase 8) and the
`kind: query_summary` record (also added in Phase 8) could be introduced
without bumping any version — the `schema_version: 1` integer was added on top
of that already-stable additive layout.

Concrete consequences:

- A future field like `prompt_hash` becoming populated where it is `null` today
  does NOT bump `schema_version`.
- A new record kind like `kind: scan_summary` could land in a future phase
  without bumping `schema_version`.
- Removing the `prompt_hash` field, renaming `cost_usd` to `cost_cents`, or
  changing `latency_ms` to seconds WOULD bump `schema_version` to `2`.

When a bump becomes necessary, downstream renderers continue to render older
files at their stamped version — the consumer policy in §3 governs forward
compatibility.

---

## 5. v0 (Unversioned) Compatibility

Records written before Phase 9 have no `schema_version` key. They are treated
as `schema_version: 0` — the pre-versioned shape — by the renderer. Two rules
apply:

1. **No on-disk rewrite.** Existing trace fixtures under
   `packages/vault-io/tests/fixtures/round-trip-vault/.code-wiki/traces/` and any
   real trace file produced by an earlier `graph-wiki-agent` build are NOT
   rewritten. They stay v0 on disk forever.
2. **Best-effort render with a one-time warning.** When the renderer reads a
   file in which ANY record lacks `schema_version`, it emits a single stderr
   line naming that file and then renders normally. Per-record warnings are
   suppressed — exactly one warning per file, regardless of how many records
   are missing the field.

Producers — `SubagentPool._write_trace`, `SubagentPool._write_batch_terminal`,
and the `query` command's summary writer — always emit `schema_version: 1`
going forward. v0 is a read-side compatibility shim, not a producer-side
fallback.

---

## 6. Examples

Each example below is a self-contained one-line record (linebreaks added only for readability — on disk each is a single line terminated by `\n`).

**Per-item subagent record, success path:**

```json
{
  "schema_version": 1,
  "role": "scanner",
  "model_id": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
  "prompt_hash": null,
  "item_id": "concepts/code-wiki-pattern.md",
  "status": "success",
  "latency_ms": 6935,
  "tokens_in": 1820,
  "tokens_out": 410,
  "cost_usd": 0.000412,
  "timestamp": "2026-05-14T13:53:02Z"
}
```

**Batch event record, fan-out cancelled mid-flight:**

```json
{
  "schema_version": 1,
  "role": "librarian",
  "model_id": "qwen.qwen3-next-80b-a3b",
  "event": "batch_cancelled",
  "items_total": 4,
  "items_completed": 1,
  "items_cancelled": 3,
  "wall_clock_ms": 2104,
  "timestamp": "2026-05-17T14:23:01Z"
}
```

**Query summary record, single-line file:**

```json
{
  "schema_version": 1,
  "kind": "query_summary",
  "query_id": "07ae8b630300",
  "query": "What concepts are documented in the wiki?",
  "top_k": 3,
  "pages_retrieved": 3,
  "pages_drilled": 3,
  "code_fallback": false,
  "started_at": "2026-05-15T01:43:28.152734Z",
  "ended_at": "2026-05-15T01:43:42.817040Z"
}
```

---

*Source: Phase 9 (Trace/Observability Polish) — see .planning/phases/09-trace-observability-polish/09-CONTEXT.md for the design record.*
