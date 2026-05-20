---
phase: 13-plugin-spec-m3a
plan: 01
subsystem: planning
tags: [plugin-spec, graph-wiki, vault-io, port-spec, spec-artifacts]

# Dependency graph
requires:
  - phase: 13-plugin-spec-m3a/13-CONTEXT.md
    provides: locked port verdicts (rename for init and scan), SP-02 template, SO-01..SO-04 shell-out shape, P-01..P-03 inference path decisions
provides:
  - .planning/spec/13-plugin-contract/init.md — per-command port spec for /graph-wiki:bootstrap (port_verdict=rename)
  - .planning/spec/13-plugin-contract/scan.md — per-command port spec for /graph-wiki:scan (port_verdict=rename)
affects:
  - 13-02-PLAN (ingest + lint specs — peer plans sharing the spec directory)
  - 13-03-PLAN (query + log specs)
  - 13-04-PLAN (SHELL-OUT-PATTERN.md + CONTRACT-INDEX.md)
  - 14-plugin-port (executes these specs)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "SP-02 per-command spec template: frontmatter + Shell-out contract + Prose-preservation map + Agent/skill rename map + Reshape notes + Verification gate"
    - "Prose-preservation map: H2-by-H2 table with verbatim/reshape verdict per section"

key-files:
  created:
    - .planning/spec/13-plugin-contract/init.md
    - .planning/spec/13-plugin-contract/scan.md
  modified: []

key-decisions:
  - "init.md has no named sub-agent (detection + init run inline in the Claude session, not dispatched through scanner/librarian agent docs)"
  - "detect_containers.py gets its own shim script (separate from init_vault.py) because the upstream prose invokes it as a subprocess before init_vault.py runs"
  - "scan_monorepo.py has no --repo flag; workspace discovery is implicit via workspace_io.config.resolve()"
  - "clean-tree-on-main gate lives inside vault_io.scan_monorepo.main — no shim-layer enforcement needed for scan"

patterns-established:
  - "Spec file: one markdown file per ported command, SP-02 mandatory sections, port_verdict in frontmatter"
  - "Prose-preservation map: markdown table, one row per upstream H2, verdict column (verbatim except rename | reshape: <what changed>)"
  - "Reshape notes section is one line for rename verdicts: confirms no behavior change"

requirements-completed:
  - PLUGIN-01

# Metrics
duration: 15min
completed: 2026-05-18
---

# Phase 13 Plan 01: Plugin Spec — init + scan

**Per-command port specs for /graph-wiki:bootstrap and /graph-wiki:scan authored using SP-02 template, locking rename verdicts, vault_io module targets, and prose-preservation maps for Phase 14 consumption**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-05-18T23:10:00Z
- **Completed:** 2026-05-18T23:25:00Z
- **Tasks:** 2
- **Files modified:** 2 created

## Accomplishments

- Authored `.planning/spec/13-plugin-contract/init.md` with all 6 SP-02 mandatory sections, covering the `/graph-wiki:bootstrap` port: vault_io.init_vault.main target, detect_containers pre-step, full args map (--topic, --tool, --force, --json, --non-interactive), H2-by-H2 prose-preservation verdict for all 8 sections in upstream init.md, agent/skill/script rename map, and end-to-end verification gate.
- Authored `.planning/spec/13-plugin-contract/scan.md` with all 6 SP-02 mandatory sections, covering the `/graph-wiki:scan` port: vault_io.scan_monorepo.main target, full args map (--json, --no-file-map, --max-depth, --no-index-regen), clean-tree-on-main gate preservation callout, H2-by-H2 prose-preservation verdict for all 8 sections in upstream scan.md, agent/skill/script rename map, and dirty-tree verification gate.
- Both files pass all automated grep gates defined in the plan.

## Task Commits

1. **Task 1: Author init.md (per-command spec for /graph-wiki:bootstrap)** - `47cd5b1` (docs)
2. **Task 2: Author scan.md (per-command spec for /graph-wiki:scan)** - `d08fc7e` (docs)

**Plan metadata:** (committed as part of this SUMMARY commit)

## Files Created/Modified

- `.planning/spec/13-plugin-contract/init.md` — SP-02 port spec for /graph-wiki:bootstrap; port_verdict=rename; targets vault_io.init_vault.main + vault_io.detect_containers.main pre-step
- `.planning/spec/13-plugin-contract/scan.md` — SP-02 port spec for /graph-wiki:scan; port_verdict=rename; targets vault_io.scan_monorepo.main; documents clean-tree-on-main gate preservation

## Decisions Made

- **init.md has no named sub-agent:** `/graph-wiki:bootstrap` runs inline in the Claude session (container detection + init_vault invocation) without dispatching through a named agent document. Upstream init.md confirms this — no "Sub-agent" section exists in the upstream file.
- **detect_containers.py gets its own shim script:** The upstream prose invokes detect_containers as a subprocess before init_vault.py runs. Phase 14 therefore needs a separate `detect_containers.py` shim alongside `init_vault.py` in `skills/graph-wiki/scripts/`.
- **scan_monorepo.py args map excludes --repo:** Workspace and repo are discovered automatically via `workspace_io.config.resolve()`; no `--repo` flag exists in `vault_io.scan_monorepo.main`. The upstream command description "Workspace and repo discovered automatically" is preserved verbatim.
- **Clean-tree gate stays inside vault_io.scan_monorepo.main:** The upstream behavior (read-only mode when tree is dirty or HEAD is not on main) is already implemented in the target Python module; the shim adds no gate logic.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `.planning/spec/13-plugin-contract/` directory exists with init.md and scan.md; Plan 02 (ingest + lint) can write peer files into the same directory immediately.
- Both spec files establish the SP-02 file format that Plans 02 and 03 will follow.
- Phase 14 plugin port executor can now consume init.md and scan.md without additional design questions for these two commands.

## Known Stubs

None — these are specification documents, not executable code. No data source wiring or UI rendering involved.

## Threat Flags

None — spec/planning artifacts only; no new network endpoints, auth paths, or schema changes introduced.

## Self-Check: PASSED

- `.planning/spec/13-plugin-contract/init.md` exists: FOUND
- `.planning/spec/13-plugin-contract/scan.md` exists: FOUND
- Commit `47cd5b1` exists: FOUND
- Commit `d08fc7e` exists: FOUND

---
*Phase: 13-plugin-spec-m3a*
*Completed: 2026-05-18*
