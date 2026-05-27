# Phase 43: Entity Writer - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-26
**Phase:** 43-entity-writer
**Areas discussed:** Source-of-truth for non-graph kinds, needs_narrative + EntityWriteResult, Hard-delete + deletions.log, Frontmatter merge + write-if-changed

---

## Source-of-truth for non-graph kinds

### Q1 — Initial framing: how to source dependency/plugin/package_family

| Option | Description | Selected |
|--------|-------------|----------|
| Add the 3 kinds to graph-io in Phase 43 | Extend `_VALID_KINDS`; add ingestion. Graph stays single source of truth. ~150 LOC graph-io scope creep. | |
| Workspace-discovery helper, separate path | ARCHITECTURE.md's stated plan; helper passes wiki-only nodes alongside graph queries. Two sources of truth. | |
| Cut the 3 kinds from Phase 43, defer to v1.9 | Reduces v1.8 milestone scope. wiki/dependencies/, wiki/plugin/, wiki/package-family/ stay. | ✓ (initial) |
| Phase 43 graph-only; Phase 45 adds separate writer | Splits work but tightens phase order. | |

**User's choice (first pass):** Cut to defer to v1.9.
**Notes:** Surfaced milestone-wide ripple effects (Phase 46 cutover, Phase 42 ADMITTED_KINDS constancy). User chose to reopen and reconsider.

### Q2 — Reopened: how to source dependency/plugin/package_family (v1.8 keeps all 7)

| Option | Description | Selected |
|--------|-------------|----------|
| Add the 3 kinds to graph-io in Phase 43 | Extend _VALID_KINDS + ingestion. Single source of truth. Unlocks future graph ops. ~100–200 LOC. | ✓ |
| Workspace-discovery helper | ARCHITECTURE.md plan. graph-io untouched but creates dual ingestion paths. | |
| Hybrid: graph-io gets dependency only | dependency as graph kind; plugin + package_family from vault config. | |

**User's choice:** Add the 3 kinds to graph-io in Phase 43 (Recommended).
**Notes:** Bigger Phase 43 but cohesive deliverable.

### Q3 — Ingestion sources for the 3 new kinds

| Option | Description | Selected |
|--------|-------------|----------|
| Pyproject + .graph-wiki.yaml + curated families.yaml | All three kinds in v1.8. families.yaml as new curation surface. | |
| Pyproject + .graph-wiki.yaml + auto-derive families | dependency + plugin from manifests; package_family via import clustering. PITFALLS Pitfall 6 risk. | |
| Skip package_family for v1.8; ship only dependency + plugin | Defer package_family to v1.9. Phase 42 template stays dormant. | ✓ |

**User's choice:** Skip package_family for v1.8.
**Notes:** Scope-pragmatic. v1.8 admitted kinds for write_entities = 6 (not 7). Phase 46 cutover does NOT remove wiki/package-family/. Documented as deliberate scope reduction.

### Q4 — Phase split decision

| Option | Description | Selected |
|--------|-------------|----------|
| Keep as one Phase 43 (two waves) | Wave 1 graph-io extension; Wave 2 wiki-io write_entities. ~30–40% scope growth, cohesive ship. | ✓ |
| Insert Phase 42.5 / amend Phase 42 | New phase for graph-io extension. Disrupts roadmap. | |
| Make graph-io work a separate Phase 43; old Phase 43 → Phase 44 | All downstream phases shift +1. Cleanest concern separation, most invasive. | |

**User's choice:** Keep as one Phase 43 (Recommended).
**Notes:** —

---

## needs_narrative + EntityWriteResult

### Q5 — needs_narrative trigger conditions

| Option | Description | Selected |
|--------|-------------|----------|
| New pages + structural-key subset changes | Curated STRUCTURAL_KEYS triggers; cosmetic changes (last_scan_at etc.) do NOT. | ✓ |
| New pages only | Tightest gate. Prose drifts from reality over time. | |
| Any scanner-owned key changed | Every scan re-runs LLM. Not viable. | |

**User's choice:** New pages + structural-key subset (Recommended).
**Notes:** STRUCTURAL_KEYS ⊂ SCANNER_OWNED_KEYS; defined as a new constant in entity_writer.py.

### Q6 — EntityWriteResult shape

| Option | Description | Selected |
|--------|-------------|----------|
| Lists of URIs per state + errors | created/updated/deleted/unchanged as URI lists; needs_narrative as set; errors as list[EntityWriteError]. Partial-success semantics. | ✓ |
| Counts + needs_narrative + errors | Smaller; loses per-URI auditability. | |
| Roadmap-minimal tuple | Simplest; no errors field, exception-driven failure. | |

**User's choice:** Lists per-state + errors (Recommended).
**Notes:** —

### Q7 — Structural-change detection

| Option | Description | Selected |
|--------|-------------|----------|
| Read existing frontmatter, diff structural keys | Parse existing via python-frontmatter; Python equality on parsed YAML; collections sorted+deduped before compare. | ✓ |
| Content-hash on each page | narrative_seed_hash field. Meta-key has to round-trip. | |
| Edge-count comparison | Cheap but misses substitutions. | |

**User's choice:** Read existing frontmatter + diff (Recommended).
**Notes:** —

---

## Hard-delete + deletions.log

### Q8 — Delete policy

| Option | Description | Selected |
|--------|-------------|----------|
| Unconditional hard-delete + log | Disposable-vault stance. Recovery via git. | ✓ |
| Body-check: warn-and-stale if human content | Pitfall 3 conservative. Contradicts STATE.md lock. | |
| Two-tier: delete if untouched, stale if edited | Hybrid. Adds runtime template comparison. | |

**User's choice:** Unconditional hard-delete (Recommended).
**Notes:** body_was_empty captured in log for audit context, not as a delete gate.

### Q9 — deletions.log format + location

| Option | Description | Selected |
|--------|-------------|----------|
| JSONL at .graph-wiki/deletions.log | timestamp/uri/slug/path/kind/body_was_empty schema; machine-parseable; matches v1.7 trace convention. | ✓ |
| Markdown via append_log() to wiki/log.md | Reuses existing infra; mixes log surfaces. | |
| Both JSONL + append_log summary | Belt + suspenders. Slight redundancy. | |

**User's choice:** JSONL at .graph-wiki/deletions.log (Recommended).
**Notes:** —

### Q10 — Retention / rotation

| Option | Description | Selected |
|--------|-------------|----------|
| Unbounded append, no rotation | ~250KB lifetime. Trivial at scale. | |
| Rotate at 10MB; keep .log + .log.1 | Standard rotate pattern. ~10 LOC implementation. | ✓ |
| Per-scan log files | Easier scoping; explodes file count. | |

**User's choice:** Rotate at 10MB (kept on user pick).
**Notes:** Slight deviation from my "recommended" but reasonable.

---

## Frontmatter merge mechanics + write-if-changed + lock

### Q11 — Merge for collection-typed scanner-owned keys

| Option | Description | Selected |
|--------|-------------|----------|
| Full replacement | Scanner-owned = scanner's view. New value wins verbatim. | ✓ |
| Set-union, prune by graph membership | Equivalent in steady state, more code. | |
| Preserve human adds via mtime diff | Defeats scanner-owned invariant. | |

**User's choice:** Full replacement (Recommended).
**Notes:** Lists sorted + deduped pre-write for stable byte output.

### Q12 — Key ordering on write

| Option | Description | Selected |
|--------|-------------|----------|
| Required-first (uri, kind), scanner-owned alpha, human preserved | Deterministic + readable. | ✓ |
| Alphabetical across all keys | uri/kind buried mid-frontmatter. | |
| Preserve existing order; deterministic only for new keys | Per-page divergence. | |

**User's choice:** Required-first + scanner-owned alpha + human preserved (Recommended).
**Notes:** Custom Dumper or sort_keys + post-processing — implementer's choice.

### Q13 — Write-if-changed guard

| Option | Description | Selected |
|--------|-------------|----------|
| Read existing, render new, write only if bytes differ | Reliable; depends on deterministic ordering. | ✓ |
| Mtime-based skip | Unreliable (git checkout resets mtimes). | |
| Skip guard, write every time | Reintroduces Pitfall 5 (churn). | |

**User's choice:** Byte-equality guard (Recommended).
**Notes:** —

### Q14 — scan.lock mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| fcntl.flock LOCK_EX|LOCK_NB fail-fast | stdlib; POSIX-only. WriteLockHeldError on contention. | ✓ |
| filelock library (cross-platform) | New dep. Same semantics. | |
| O_EXCL create | Stale-lock recovery is manual. | |

**User's choice:** fcntl.flock (Recommended).
**Notes:** macOS + Linux only; stack doesn't target Windows.

---

## Claude's Discretion

- Exact dataclass field types (list vs tuple vs frozenset inside EntityWriteResult).
- EntityWriteError.exception format (repr vs full traceback).
- Whether `_acquire_scan_lock` is exposed publicly.
- Whether `cg describe dependency` / `cg describe plugin` ship in Phase 43 or slip.
- YAML emitter config for deterministic ordering (Dumper vs sort_keys + post-process).
- File mode for writes (0o644 v1.7 default).

## Deferred Ideas

- `package_family` kind ingestion / entity pages — v1.9.
- Cross-repo dependency deduplication — v1.9.
- Plugin-as-graph-edge to consumer packages — v1.9.
- `cg describe dependency|plugin` subcommands — possibly v1.8 follow-up.
- Frontmatter inline-comment preservation across merges (python-frontmatter loses these on round-trip).
- Per-kind whitelist enforcement at runtime (Phase 42 D-09's open option — not adopted in Phase 43).

## Folded Todos

- `2026-05-26-fix-scanner-treats-import-root-as-subpackage.md` (score 0.6) FOLDED into Wave 1. Wave 1 touches `structural_nodes.py` for dependency/plugin emission; bundling the import-root subpackage bug fix in the same wave batches the fixture re-baseline work. Wave 1 acceptance criterion adds: "subpackage nodes only emit for directories BELOW the import root."
