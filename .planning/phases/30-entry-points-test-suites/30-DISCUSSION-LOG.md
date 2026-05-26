# Phase 30: Entry Points + Test Suites - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-25
**Phase:** 30-entry-points-test-suites
**Areas discussed:** Orphan test files, EntryPoint implemented_by, tests edge precision (TEST-06), Call-order enforcement (SC#3)

---

## Orphan test files

### Q1: Where should `packages/foo/src/foo/test_helpers.py` live in the containment tree?

| Option | Description | Selected |
|--------|-------------|----------|
| Synthetic suite per package | Emit a synthetic `TestSuite('inline-tests')` contained by Package for every package that has orphan test files | |
| Leave under Package | Don't re-parent — test files inside src/ stay under their SubPackage | |
| Hoist to Repository | Re-parent orphans to Repository directly | |
| Treat is_test heuristic as wrong here | If the file is inside src/ rather than tests/, override Phase 29's is_test=true and treat as production code | ✓ |

**User's choice:** Treat is_test heuristic as wrong here.
**Notes:** Captured as D-01 in CONTEXT.md.

### Q2: Where should the src/-override apply?

| Option | Description | Selected |
|--------|-------------|----------|
| Inside any Python package's import root | If File.path is inside `<pkg.path>/src/<importable>/` OR `<pkg.path>/<importable>/`, force is_test=false regardless of filename. JS/TS: inside the Package dir but outside any tests/ subdir | ✓ |
| Anywhere outside a tests/ ancestor | Only directory-traversal counts — dirname is king, filename is decorative | |
| Override only when filename is `*_helpers.py` / `*_utils.py` | Narrow override — keep test_*.py/*_test.py as test markers | |

**User's choice:** Inside any Python package's import root.
**Notes:** Captured as D-01 in CONTEXT.md.

### Q3: Where to fix it — Phase 29 amendment or Phase 30-only rule?

| Option | Description | Selected |
|--------|-------------|----------|
| Amend D-09 in Phase 29 | Edit Phase 29 D-09 to add the src/-override clause before Phase 29 ships | ✓ |
| Override in test_suites.emit | Phase 30 reads File.is_test from DB but applies the src/-override during suite assignment — drift between attr and membership | |
| Add an is_test_override step before test_suites.emit | New step: UPDATE File.is_test=false for src/-resident files, then assign the rest | |

**User's choice:** Amend D-09 in Phase 29.
**Notes:** Captured as D-01 with risk note D-02 (Phase 29 is actively executing in background — amendment may need to land as Phase 30 hotfix to structural_nodes.py if Phase 29 ships first).

---

## EntryPoint implemented_by

### Q1: What should `EntryPoint.implemented_by` point at for `pkg.cli:main`?

| Option | Description | Selected |
|--------|-------------|----------|
| Polymorphic, Function preferred | Function if available, fallback to File | |
| Always File | implemented_by → File only; callable name stored as attr on EntryPoint | ✓ |
| Always Function (fallback to File on miss) | Force Function when source-parser has one | |

**User's choice:** Always File.
**Notes:** D-03/D-04 in CONTEXT.md. `EntryPoint.callable` attr stores the callable name.

### Q2: How strict should path-qualified resolution be (SC#4)?

| Option | Description | Selected |
|--------|-------------|----------|
| Strict: walk dotted_path from declaring package's import root | Reuse Phase 29 D-06 layout discovery, exact path, no fallback | ✓ |
| Strict + warn on miss | Same strict + warning + implemented_by=NULL | |
| Best-effort: glob *.py for the callable name | Lenient — search File nodes by basename | |

**User's choice:** Strict.
**Notes:** D-05 in CONTEXT.md.

### Q3: What if strict resolution misses?

| Option | Description | Selected |
|--------|-------------|----------|
| Emit EntryPoint with implemented_by=NULL + warning | Captures broken declarations in the graph | ✓ |
| Skip the EntryPoint entirely | Loses signal about broken manifests | |
| Fail loud — exit 4 | Treat as manifest schema violation | |

**User's choice:** Emit EntryPoint with implemented_by=NULL + warning.
**Notes:** D-06 in CONTEXT.md.

### Q4: What does ENTRY-02's recursive walk over conditional exports emit?

| Option | Description | Selected |
|--------|-------------|----------|
| One EntryPoint per leaf path, kind=library | Walk recursively; every string-valued leaf produces an EntryPoint. Conditionals → multiple EntryPoints sharing export key, different files. Wildcards → is_wildcard=true, implemented_by=NULL | ✓ |
| One EntryPoint per top-level export key | Pick a single canonical file per key | |
| You decide | Claude's discretion | |

**User's choice:** One EntryPoint per leaf path.
**Notes:** D-07 in CONTEXT.md.

---

## tests edge precision (TEST-06)

### Q1: If a suite imports from 5 packages, how to emit `TestSuite → Package` edges?

| Option | Description | Selected |
|--------|-------------|----------|
| Emit every imported package | Simple, predictable, no threshold tuning | ✓ |
| Top-N by import frequency | Count imports, emit top 2-3 | |
| Threshold-filtered | Emit only if suite imports from a package in >=N test files | |
| Primary package only (suite-name match) + warn | Match suite name vs package names | |

**User's choice:** Emit every imported package.
**Notes:** D-09 in CONTEXT.md.

### Q2: Should `TestSuite → Repository` edges be emitted in Phase 30?

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, when suite imports from >= K packages | K=5 default, captures e2e/system suites | ✓ |
| Yes, by directory name signal only (e2e/, system/) | Pure naming heuristic | |
| Defer all non-Package targets to Phase 31 | Cleaner phase boundaries | |

**User's choice:** Yes, when suite imports from >= K packages.
**Notes:** D-12 in CONTEXT.md.

### Q3: When suite hits the K=5 threshold, do per-Package + Repository edges coexist?

| Option | Description | Selected |
|--------|-------------|----------|
| Both coexist | Per-package edges + Repository edge both fire | ✓ |
| Repository edge replaces Package edges | Cleaner graph but loses package-level queries | |
| K=5 threshold only triggers Repository edge; Package edges keep firing | Same as 'Both coexist' reframed | |

**User's choice:** Both coexist.
**Notes:** D-12 in CONTEXT.md.

### Q4: How to map dotted imports → Package nodes (Python)?

| Option | Description | Selected |
|--------|-------------|----------|
| Match against existing Package importable names | Build {importable_name: Package} map; unknown names silently skipped | ✓ |
| Match + warn on unknown top-level imports | Same map-driven approach, warn on miss | |
| Resolve through PyPI metadata | Heavyweight; requires new deps | |

**User's choice:** Match against existing Package importable names.
**Notes:** D-10 in CONTEXT.md.

### Q5: JS/TS import resolution strategy?

| Option | Description | Selected |
|--------|-------------|----------|
| Match bare specifiers against Package.name | Bare specifiers → Package.name; relative imports resolve to File then bubble up | ✓ |
| Defer JS import resolution to v1.7 | Python-only in Phase 30 | |
| Only handle direct package imports (no relative) | Skip relative-import bubbling | |

**User's choice:** Match bare specifiers against Package.name.
**Notes:** D-11 in CONTEXT.md.

---

## Call-order enforcement (SC#3)

### Q1: How to enforce the call-order pitfall (SC#3)?

| Option | Description | Selected |
|--------|-------------|----------|
| Both: fixture test + runtime debug assertion | Fixture regression test + always-on invariant check in update.run | ✓ |
| Fixture test only | Just the regression test | |
| Runtime assertion only | Always-on check in update.run, no dedicated test | |

**User's choice:** Both: fixture test + runtime debug assertion.
**Notes:** D-19 in CONTEXT.md.

### Q2: Where should the runtime invariant assertion live?

| Option | Description | Selected |
|--------|-------------|----------|
| End of update.run, always-on, raise on violation | StrictTreeInvariantError; cg update exits non-zero | ✓ |
| End of update.run, env-gated, warn on violation | GRAPH_WIKI_INVARIANT_CHECK=1 to enable | |
| Inside test_suites.emit | Local check — narrower scope | |

**User's choice:** End of update.run, always-on, raise on violation.
**Notes:** D-19(b) + D-20 in CONTEXT.md.

### Q3: How to do the actual re-parenting?

| Option | Description | Selected |
|--------|-------------|----------|
| Delete-then-insert in one transaction per file | Atomic per file; idempotent on re-runs | ✓ |
| Bulk re-parent: delete all 'Repository→File where File.is_test=true' edges, then insert | Faster on large repos; less granular failure | |
| INSERT first, then DELETE | Mid-transaction violates invariant | |

**User's choice:** Delete-then-insert in one transaction per file.
**Notes:** D-14 in CONTEXT.md.

### Q4: Where do entry_points.emit and test_suites.emit slot into update.run?

| Option | Description | Selected |
|--------|-------------|----------|
| After structural_nodes.emit, before resolve.sweep | packages.refresh → structural_nodes → entry_points → test_suites → resolve.sweep → invariant_check | ✓ |
| test_suites.emit BEFORE entry_points.emit | Interchangeable; no inter-dep | |
| Run both in parallel after structural_nodes.emit | SQLite single-writer makes this awkward | |

**User's choice:** After structural_nodes.emit, before resolve.sweep.
**Notes:** D-21 in CONTEXT.md.

---

## Claude's Discretion

- TestSuite node naming convention (`tests/integration` vs `integration` vs `repo:tests:integration`) — planner picks consistent with Phase 29's URI naming.
- Framework config parser depth — only `testpaths` discovery needed; other config keys ignored.
- `EntryPoint.name` shape for `[project.entry-points."console_scripts"]` vs `[project.scripts]` — both `kind: executable`, `source` distinguishes.
- Per-Package vs Repository structural parent for package-local TestSuites — strict-tree invariant decides.

## Deferred Ideas

- Function/Class as `implemented_by` target (D-03 locked File-only) — revisit if callable-level navigation queries land
- Wildcard `exports` expansion — defer to v1.7
- Top-N filtering / threshold tuning on `tests` edges — revisit if query surface gets noisy
- `TestSuite → Domain` edges — Phase 31's responsibility
- PyPI metadata resolution for first-party vs third-party
- Stale entry-point query (`cg find-stale-entry-points`) — Phase 33 or v1.7
- Function-level `tests` edges — deferred to later phase or v1.7
- Framework-config-driven kind override — currently config only contributes additional test roots
