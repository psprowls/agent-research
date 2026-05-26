# Phase 34: Brand Sweep - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-25
**Phase:** 34-brand-sweep
**Areas discussed:** README rebrand wording, Env var rename + deprecation, Test files in scope

---

## README rebrand wording

### Q1: First-line title

| Option | Description | Selected |
|--------|-------------|----------|
| `# graph-io` | Terse, matches Python package name | ✓ |
| `# graph-wiki code graph` | Descriptive, brand-aligned | |
| `# graph-io — code graph for graph-wiki` | Two-part | |

**User's choice:** `# graph-io`.
**Notes:** D-01 in CONTEXT.md.

### Q2: Second-line tagline

| Option | Description | Selected |
|--------|-------------|----------|
| `Code-graph core for the graph-wiki ecosystem. Owns:` | Minimal change; swap link for literal | |
| `Code-graph storage and queries for graph-wiki agent. Owns:` | More descriptive | |
| `Code-graph backend for graph-wiki. Owns:` | Shortest; 'backend' conventional | ✓ |

**User's choice:** `Code-graph backend for graph-wiki. Owns:`.
**Notes:** D-02 in CONTEXT.md.

### Q3: Path reference handling

| Option | Description | Selected |
|--------|-------------|----------|
| Replace with prose: 'DB lives under workspace_io.paths.graph_dir()' | Reference the helper, not a path | ✓ |
| Hardcode a representative example | Concrete; drift risk | |
| Strip the path reference entirely | Minimal; loses signal | |

**User's choice:** Replace with prose pointing at workspace_io.paths.graph_dir().
**Notes:** D-03 in CONTEXT.md.

---

## Env var rename + deprecation

### Q1: Precedence when both set

| Option | Description | Selected |
|--------|-------------|----------|
| New (GRAPH_WIKI_*) wins; warn LATTICE_* ignored | Encourages migration | ✓ |
| Old (LATTICE_*) wins; warn migrate | Backwards-preserving | |
| Error on conflict | Disruptive | |
| Old wins silently if matching value | Most user-friendly; complex | |

**User's choice:** New (GRAPH_WIKI_*) wins; warn LATTICE_* ignored.
**Notes:** D-07 in CONTEXT.md.

### Q2: Warning detail level

| Option | Description | Selected |
|--------|-------------|----------|
| One-liner with rename guidance | Single line, var name + value | ✓ |
| Three-line context with removal timeline | More complete; chattier | |
| Minimal 'warning: deprecated' | Cleanest output | |

**User's choice:** One-liner with rename guidance.
**Notes:** D-08 in CONTEXT.md.

### Q3: Warning frequency

| Option | Description | Selected |
|--------|-------------|----------|
| Every cg invocation | Simple, predictable, short-lived processes | ✓ |
| Once per process | Module-level flag | |
| GRAPH_WIKI_SUPPRESS_DEPRECATION env var | Forward-thinking knob | |
| Test-suite suppression env var | Test-infra specific | |

**User's choice:** Every cg invocation.
**Notes:** D-08 in CONTEXT.md.

### Q4: _default_lock_timeout refactor

| Option | Description | Selected |
|--------|-------------|----------|
| Sequential: try new, then old + warn | Inline branch tree | ✓ |
| Helper dict pattern ALIASES = {new: old} | Generalised; premature | |
| Minimal additive branch | Less readable | |

**User's choice:** Sequential: try new, then old + warn.
**Notes:** D-09 in CONTEXT.md.

---

## Test files in scope

### Q1: Test rebrand scope

| Option | Description | Selected |
|--------|-------------|----------|
| Rebrand tests asserting user-facing strings; leave fixture data | Per-file decision | |
| Rebrand all four files comprehensively | Most thorough | ✓ |
| Leave tests entirely; only rebrand non-test source | Tests stay as historical | |

**User's choice:** Rebrand all four files comprehensively.
**Notes:** D-11 in CONTEXT.md (with D-12 functional carve-out per next question).

### Q2: Functional behavior carve-out

| Option | Description | Selected |
|--------|-------------|----------|
| Keep functional-behavior test data; rebrand everything else | Preserve _SKIP_REPO_PREFIXES tests | ✓ |
| Rebrand AND update _SKIP_REPO_PREFIXES | Violates BRAND-04 | |
| Add test-specific allowlist | More allowlist surface | |
| Per-file judgment by planner | Defer | |

**User's choice:** Keep functional-behavior test data; rebrand everything else.
**Notes:** D-11/D-12 in CONTEXT.md.

### Q3: Env var test refactor

| Option | Description | Selected |
|--------|-------------|----------|
| Both: keep old test as deprecation regression + add new | Three tests, best coverage | |
| Update old test to use new env var only | Loses deprecation-warning coverage | ✓ |
| Add new test, leave old as-is | Old won't catch warning regression | |

**User's choice:** Update old test to use new env var only.
**Notes:** D-13 in CONTEXT.md.

### Q4: SC#3 deprecation-warning test

| Option | Description | Selected |
|--------|-------------|----------|
| Add a dedicated deprecation-warning test | Regression-safe; verifiable | |
| Skip the deprecation test | Manual verification only | ✓ |
| Cover via CLI integration test | Realistic; slower | |

**User's choice:** Skip the deprecation test.
**Notes:** D-14 in CONTEXT.md. **Risk note**: deliberate test-coverage gap on the deprecation path. SC#3 will be verified manually at phase-verify time only.

---

## Claude's Discretion

- Exact wording of stderr deprecation warnings
- Removal of [lattice] markdown links beyond first 3 README lines
- Whether warning includes 'Removed in v1.7' timeline hint
- .brand-grep-allow entry shape (substring vs path)
- Order of edits in plan waves

## Deferred Ideas

- Removal of LATTICE_GRAPH_LOCK_TIMEOUT_MS alias (v1.7+)
- GRAPH_WIKI_SUPPRESS_DEPRECATION env var
- Generalised env-var-rename helper
- README full rewrite
- Automated deprecation-warning test (revisit alongside removal in v1.7)
- Brand sweep of plugins/graph-wiki/ or agents/graph-wiki-agent/ (out of scope per BRAND-04)
- Migration guide / CHANGELOG entry
- cg CLI version bump tied to brand sweep
