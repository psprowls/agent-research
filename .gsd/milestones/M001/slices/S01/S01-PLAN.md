# S01: Establish current project truth

**Goal:** Produce the root PROJECT artifact that establishes current project truth: agent-research identity, live uv workspace/package layout, shipped trajectory through v1.11, and the boundary that .gsd is active while .planning is archive/reference only.
**Demo:** PROJECT artifact accurately describes the current repo, shipped trajectory, package layout, and active GSD posture.

## Must-Haves

- R001 is covered by a root PROJECT artifact saved through `gsd_summary_save` with `artifact_type: "PROJECT"`.
- The rendered `.gsd/PROJECT.md` names `.gsd/` as the active source of truth and `.planning/` as archive/reference evidence only.
- The artifact describes the live workspace packages: `graph-wiki-agent`, `eval-harness`, `graph-io`, `model-adapter`, `source-parser`, `subagent-runtime`, `wiki-io`, and `workspace-io`.
- The artifact summarizes shipped legacy trajectory through v1.11 without reviving old phases as active work.
- The artifact does not claim wholesale archive conversion, reusable migration tooling, or active cost-frontier sweep execution in M001.
- Static artifact verification commands pass.

## Proof Level

- This slice proves: Static planning-artifact proof. No product runtime behavior is changed or exercised; proof is by artifact existence, content checks, and traceability to sampled legacy and live manifest inputs.

## Integration Closure

This slice creates the first root-level GSD project truth artifact and unblocks S02/S03 with stable project/truth/archive-boundary language. It consumes `.planning/PROJECT.md`, `.planning/ROADMAP.md`, `.planning/MILESTONES.md`, `.planning/milestones/v1.11-ROADMAP.md`, root `pyproject.toml`, `agents/graph-wiki-agent/pyproject.toml`, and all workspace package `pyproject.toml` manifests. Remaining milestone work: S02 curates high notes/caveats, S03 normalizes requirements, and S04 verifies the initialized GSD state end-to-end.

## Verification

- No runtime observability impact. Diagnostics are planning-artifact oriented: the generated PROJECT artifact is the inspection surface for future planning agents.

## Tasks

- [x] **T01: Created and verified the root PROJECT artifact for current GSD truth.** `est:45m`
  Expected executor skills: `write-docs`, `verify-before-complete`.
  - Verify: test -s .gsd/PROJECT.md

- [x] **T02: Verified the PROJECT artifact’s current-truth claims and archive-boundary exclusions without product runtime changes.** `est:20m`
  Expected executor skills: `verify-before-complete`.
  - Verify: test -s .gsd/PROJECT.md && rg "active source of truth" .gsd/PROJECT.md && rg "archive/reference" .gsd/PROJECT.md && rg "v1.11" .gsd/PROJECT.md && rg "graph-wiki-agent" .gsd/PROJECT.md && rg "subagent-runtime" .gsd/PROJECT.md && rg "model-adapter" .gsd/PROJECT.md && rg "source-parser" .gsd/PROJECT.md && rg "graph-io" .gsd/PROJECT.md
