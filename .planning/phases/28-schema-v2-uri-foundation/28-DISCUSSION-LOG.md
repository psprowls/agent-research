# Phase 28: Schema v2 + URI Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-25
**Phase:** 28-schema-v2-uri-foundation
**Areas discussed:** v1→v2 upgrade flow, (org, repo) derivation, URI helper API shape, Phase 28 scope discipline

---

## v1→v2 upgrade flow

### Q1: `cg update --full` against a v1 code.db

| Option | Description | Selected |
|--------|-------------|----------|
| Detect v1, unlink file, rebuild | Cleanest. `connect()` detects schema_version != 2 even in --full mode, unlinks code.db (+ wal/shm), then reopens with `create=True`. One-line log. No partial-state risk. | ✓ |
| Detect v1, DROP TABLE + reapply | Drop nodes/edges/metadata in-place, then re-run apply_schema. Avoids file delete but leaves SQLite file with bloat; WAL/shm may not be reclaimed. | |
| Defer to user: print message, exit 4 | Even `--full` on v1 exits 4 with `delete code.db and re-run cg update --full`. Most explicit but worst UX. | |

**User's choice:** Detect v1, unlink file, rebuild
**Notes:** Becomes D-01. Detection happens in `update.run()` before `store.connect(create=True)`. Stderr message: `Schema v1 detected — rebuilding code.db at schema v2.`

### Q2: `cg update` (incremental) on v1 code.db

| Option | Description | Selected |
|--------|-------------|----------|
| Friendly one-liner to stderr | Catch SchemaMismatchError in cli/main.py, print clean message, exit 4, no traceback. | ✓ |
| Raw SchemaMismatchError traceback | Let the exception propagate. Exit code is non-zero but not specifically 4. Fails SCHEMA-02 success criterion. | |

**User's choice:** Friendly one-liner to stderr
**Notes:** Becomes D-02. Wired in `cli/main.py` with `except store.SchemaMismatchError` handler.

---

## (org, repo) derivation

### Q3: Which URL shapes must `uri.py` handle?

| Option | Description | Selected |
|--------|-------------|----------|
| SSH: git@host:org/repo.git | Standard GitHub/GitLab SSH form. | ✓ |
| HTTPS: https://host/org/repo[.git] | Standard HTTPS form, with or without `.git`. | ✓ |
| GitLab subgroups: host/group/subgroup/repo | Nested groups. Adds complexity. | (deferred to v1.7) |
| git:// and file:// protocols | Less common. file:// for local clones. | (fall through to local-only fallback) |

**User's choice:** SSH + HTTPS only; others fall through to local-only fallback
**Notes:** Becomes D-03. `parse_remote_url` returns `None` for non-matches.

### Q4: Fallback chain when origin missing/unparseable

| Option | Description | Selected |
|--------|-------------|----------|
| origin → first remote (any name) → local dirname | Probe other remotes if `origin` absent. | |
| origin only → local dirname | Try `origin` only; if absent or unparseable, go straight to local fallback. Simpler. | ✓ |
| origin only → hard error | Require an origin remote. Breaks local-only / pre-publish repos. | |

**User's choice:** origin only → local dirname
**Notes:** Becomes D-04. No multi-remote probing.

### Q5: `org` value for local-only repos

| Option | Description | Selected |
|--------|-------------|----------|
| `local` | URI looks like `repo:local/myproject`. Readable. | ✓ |
| `_local` | Leading underscore signals "reserved/synthetic". Less clean in URIs. | |
| Empty string | Yields `repo:/myproject`. Ugly, breaks visual parsing. | |

**User's choice:** `local`
**Notes:** Becomes D-05. Literal string sentinel; no underscore prefix.

---

## URI helper API shape

### Q6: How do helpers receive `(org, repo)` prefix?

| Option | Description | Selected |
|--------|-------------|----------|
| Positional args on every helper | Stateless, verbose at callsites. Emitters thread `(org, repo)` through their call chain. | |
| RepoContext object passed to each helper | `RepoContext(org, repo)` dataclass; helpers take `ctx` as first arg. Ergonomic + explicit. | ✓ |
| Thread-local / context var | `set_repo_context(org, repo)` at update.run() start. Hidden global state — anti-pattern. | |

**User's choice:** RepoContext object passed to each helper
**Notes:** Becomes D-06 / D-07. Frozen dataclass for hashability. `domain_uri(name)` is the one exception — repo-agnostic in v1.6.

### Q7: SubPackage URI scheme

| Option | Description | Selected |
|--------|-------------|----------|
| `subpkg:org/repo/pkg_name/dotted.path` | Dotted Python import path. e.g., `subpkg:local/agent-research/graph-io/graph_io.cli`. | ✓ |
| `subpkg:org/repo/pkg_name/path/with/slashes` | Filesystem-style path. Loses import semantics. | |

**User's choice:** Dotted Python path
**Notes:** Part of D-07. Matches Python import semantics; FS path can always be reconstructed from `path` column.

### Q8: Ship all 7 helpers in Phase 28, or lazy by phase?

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — all 7 helpers, tested, in Phase 28 | Satisfies ROADMAP success criterion #3 explicitly. Tests ~30 LOC total. | ✓ |
| No — ship pkg_uri + repo_uri now; rest lazily | Smaller phase but violates explicit success criterion. | |

**User's choice:** All 7 helpers in Phase 28
**Notes:** Becomes D-08. `tests/test_uri.py` covers each.

---

## Phase 28 scope discipline

### Q9: Include `packages.py` `pkg_uri` write in Phase 28?

| Option | Description | Selected |
|--------|-------------|----------|
| Include packages.py pkg_uri write | Required by success criterion #1 (non-NULL `uri` for Package nodes after `--full`). Proves the column path works end-to-end. Minimum delta to satisfy stated SC. | ✓ |
| Strict schema-only — defer packages.py to Phase 29 | Cleaner separation but fails SC #1 unless packages.py moves to a Phase 29 prerequisite. | |

**User's choice:** Include packages.py pkg_uri write
**Notes:** Becomes D-09 / D-10. `_upsert_node` extended to pop `uri` from attrs → column write.

### Q10: Wire `RepoContext` derivation in `update.run()` in Phase 28?

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — wire RepoContext in update.run() in Phase 28 | Foundation work belongs in foundation phase. Phase 29 just extends signature for structural_nodes.emit(ctx, ...). | ✓ |
| No — defer to Phase 29 | Phase 28 leaves packages.py using a hardcoded stub. Smaller diff in 28 but revisits packages.py in 29. | |

**User's choice:** Wire in Phase 28
**Notes:** Becomes D-11. Phase 29 only extends ctx threading; doesn't introduce it.

---

## Claude's Discretion

- Exact wording of stderr messages (within constraints: must include `cg update --full` directive and SCHEMA_MISMATCH semantic).
- Index naming (will follow existing `idx_nodes_*` convention).
- Whether `parse_remote_url` returns `Optional[tuple]` or raises — Claude picks based on callsite readability.

## Deferred Ideas

- GitLab subgroups (multi-segment URL paths) → v1.7
- `UNIQUE NOT NULL` constraint on `uri` column → v1.7 after real-repo URI generation validated
- AST node URIs (functions, classes, methods) → out of v1.6 scope entirely
- `LATTICE_GRAPH_LOCK_TIMEOUT_MS` deprecation alias → Phase 34 (Brand Sweep)
- `UPDATE_IN_PROGRESS` exit-code wiring in `cli/main.py` — minor; flag during planning if not already covered, treat as 2-line addition alongside SchemaMismatchError handler (not its own gray area).
