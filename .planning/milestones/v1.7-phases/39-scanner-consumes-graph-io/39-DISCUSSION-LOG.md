# Phase 39: Scanner Consumes graph-io - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-26
**Phase:** 39-scanner-consumes-graph-io
**Areas discussed:** How to invoke `cg update` pre-scan, URI → slug mapping, Where the lookup happens, Fallback strategy & log line shape

---

## How to invoke `cg update` pre-scan

### Q1: Invocation mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| In-process: `graph_io.cli.ops_update.run` directly | Phase 37/38 in-process pattern; Phase 39 doesn't depend on Phase 38. | |
| Via Phase 38's `graph build` pathway | Single agent-side surface for "invoke graph update." Creates hard dep on Phase 38. | ✓ |
| Subprocess `cg update` | Zero coupling; PATH dep; doesn't match Phase 37/38 in-process precedent. | |

**User's choice:** Via Phase 38's `graph build` pathway
**Notes:** Hard dependency on Phase 38 merging first. Worth the cost for surface consistency.

### Q2: Pass-through flags

| Option | Description | Selected |
|--------|-------------|----------|
| Incremental only, no --trace, no --model | Scanner shouldn't auto-trace; users opt in via `graph build --trace` separately. | ✓ |
| Forward `scan --trace` and `scan --model` if set | More control; doubles surface; potential trace-flag confusion. | |
| Always full + traced (debug default) | Heavy; wrong default. | |

**User's choice:** Incremental only, no flags (Recommended)
**Notes:** Avoids cluttering `.graph-wiki/traces/`.

---

## URI → slug mapping

### Q1: Slug derivation algorithm

| Option | Description | Selected |
|--------|-------------|----------|
| Last URI segment + node attrs for routing | Preserves apps/ vs domains/ vs packages/ layout. | (walked back to this) |
| Last URI segment only (flat layout) | Always `packages/<n>/`; orphans existing apps/ and domains/ pages. | (initial pick) |
| Full URI 1:1 | `pkg:org/repo/<n>` → `pkg/org/repo/<n>.md`. Requires vault migration. | |

**User's choice (final):** Last URI segment + graph node attrs for routing
**Notes:** Initial pick was "flat" — walked back after considering orphan implications. Today's vault layout preserved.

### Q2: Orphan handling (asked to confirm Q1's revision)

| Option | Description | Selected |
|--------|-------------|----------|
| Leave orphans; v1.8 reconciliation | Scanner writes new pages flat; old pages stay (stale). | |
| Migrate in this phase | Move old paths to flat layout; breaks existing wiki links. | |
| Keep both layouts — use graph attrs | Walks back the flat decision. | ✓ |

**User's choice:** Keep both layouts via graph attrs
**Notes:** Reverts Q1 to the original recommended option. Existing layout preserved.

---

## Where the lookup happens

### Q1: Code location for graph lookup

| Option | Description | Selected |
|--------|-------------|----------|
| Agent-side decoration in `run_scan()` | Decorate `pkg` dicts; wiki-io stays graph-unaware. | ✓ |
| Deep change to `_wiki_relative_path_for` | wiki-io gains graph-io dep. Bigger blast radius. | |
| New helper module `scan_uri_helpers.py` | Same outcome as (a) in a separate module. | |

**User's choice:** Agent-side decoration in `run_scan()` (Recommended)
**Notes:** Minimal blast radius; wiki-io stays graph-unaware.

### Q2: Connection lifetime

| Option | Description | Selected |
|--------|-------------|----------|
| Open once at scan entry, close in `finally` | Phase 37 D-03 pattern. Honors Pitfall 4. | ✓ |
| Per-workspace open/close | Symmetric with parallel scanner fan-out. Violates Pitfall 4. | |
| Module-level cached singleton | Test pollution risk. Discouraged. | |

**User's choice:** Open once at scan entry, close in `finally` (Recommended)
**Notes:** Symmetric with Phase 37 connection lifetime.

---

## Fallback strategy & log line shape

### Q1: Behavior when graph DB doesn't exist on fresh workspace

| Option | Description | Selected |
|--------|-------------|----------|
| Pre-scan `cg update` creates it | Normal flow; graph follows the wiki on demand. | ✓ |
| Skip update; fall back immediately | Pushes manual `cg update` on the user. | |
| Refuse to run; error message | Hard fail; regression from today's no-graph behavior. | |

**User's choice:** Pre-scan `cg update` creates it (Recommended)
**Notes:** First-time scanner users don't need a manual bootstrap step.

### Q2: Behavior when `cg update` ITSELF fails (general runtime failure)

| Option | Description | Selected |
|--------|-------------|----------|
| Fall back + log line, continue scan | Matches SC#2 literal "graceful fallback" wording. | |
| Hard abort the scan | Stricter; consistent with Phase 37 D-04. Scanner is a heavy op; bad graph is worse than no graph. | ✓ |
| Retry once then fall back | Complexity for marginal benefit. | |

**User's choice:** Hard abort the scan
**Notes:** Tighter than SC#2's literal wording; Q3 narrows the SC#2 graceful-fallback case explicitly.

### Q3: What scenario specifically triggers the SC#2 graceful fallback path

| Option | Description | Selected |
|--------|-------------|----------|
| Only when graph CAN'T be initialized (permission/disk-full) | Narrow SC#2 reading; preserves Q2's hard-abort. | ✓ |
| When `cg update` ran but a workspace has no graph node | Per-workspace fallback. | |
| Both (a) AND (b) | Both cases trigger fallback. | |

**User's choice:** Only when graph CAN'T be initialized (Recommended)
**Notes:** SC#2 satisfied via the narrow "init failure" interpretation.

---

## Claude's Discretion

- Exact graph node attribute names (`is_app` boolean vs `kind=app` enum)
- Batch query vs per-workspace lookup for the decoration step
- Plugin / non-`packages/` container slug fallback details
- Where the `[NOT_INITIALIZED fallback: …]` line is written (stderr suggested)
- Whether to add a `--no-graph-update` flag to `graph-wiki-agent scan`

## Deferred Ideas

- In-process direct `ops_update.run` (bypassing Phase 38) — rejected for surface consistency
- Subprocess `cg update` — rejected; same reasons as Phase 38 D-06
- Deep wiki-io refactor — rejected; wiki-io stays graph-unaware
- Per-workspace fallback for missing graph node — out of scope unless test coverage exists
- Retry on transient `cg update` failure — rejected for simplicity
- `--no-graph-update` flag — planner's discretion
- URI-keyed flat wiki redesign — v1.8 Future Requirement
- Migration of `apps/`/`domains/` pages to flat layout — dedicated future phase
- Orphaned-page reconciliation on package rename — v1.8 per Phase 40 INGESTOR-03
- Plugin (`plugins/graph-wiki/`) wiring to graph-io — v1.8 Future Requirement
