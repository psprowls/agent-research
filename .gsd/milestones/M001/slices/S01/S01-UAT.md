# S01: Establish current project truth — UAT

**Milestone:** M001
**Written:** 2026-05-31T03:57:38.604Z

# S01: Establish current project truth — UAT

**Milestone:** M001
**Written:** 2026-05-31

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: S01 ships planning/current-truth artifacts only; no product runtime behavior changed or needs live service validation.

## Preconditions

- The tester is in the M001 GSD worktree.
- `.gsd/PROJECT.md`, `.gsd/REQUIREMENTS.md`, `.gsd/milestones/M001/M001-ROADMAP.md`, and S01 task summaries are present.

## Smoke Test

Open `.gsd/PROJECT.md` and confirm it says `.gsd/` is the active source of truth while `.planning/` is archive/reference evidence only.

## Test Cases

### 1. Current project truth is discoverable

1. Read `.gsd/PROJECT.md`.
2. Confirm it identifies `agent-research` as a Python 3.11+ uv workspace for Bedrock-backed graph-wiki tooling.
3. Confirm it names `graph-wiki-agent`, `subagent-runtime`, `model-adapter`, `source-parser`, and `graph-io`.
4. **Expected:** A future agent can understand the current repo identity and package layout without reading the old `.planning/` archive first.

### 2. Legacy archive boundary is explicit

1. Read the `Active Source of Truth` and `Current Known Boundaries` sections of `.gsd/PROJECT.md`.
2. Confirm `.planning/` is described as historical reference only.
3. Confirm the artifact does not claim wholesale `.planning/` conversion, reusable migration tooling, active cost-frontier sweep execution, or Phase 60 reactivation.
4. **Expected:** Historical planning remains available as evidence, but old archive work is not accidentally reactivated as M001 scope.

### 3. S01 task evidence supports the slice outcome

1. Read `.gsd/milestones/M001/slices/S01/tasks/T01-SUMMARY.md`.
2. Read `.gsd/milestones/M001/slices/S01/tasks/T02-SUMMARY.md`.
3. Confirm both summaries record `verification_result: passed` and `blocker_discovered: false`.
4. **Expected:** The slice has two completed task records supporting the PROJECT artifact and no remaining task blocker.

## Edge Cases

### Negated historical claims are allowed

1. Search `.gsd/PROJECT.md` for `migration tooling`, `wholesale conversion`, `cost-frontier`, and `Phase 60`.
2. Confirm any matches appear as explicit exclusions or historical context, not as active work claims.
3. **Expected:** The document may mention deferred/historical topics only to prevent scope confusion.

## Failure Signals

- `.gsd/PROJECT.md` is missing or omits active-source-of-truth language.
- `.planning/` is described as active planning state rather than archive/reference evidence.
- Live workspace package names are absent from the project truth artifact.
- S01 task summaries show failed verification or a discovered blocker.

## Not Proven By This UAT

- It does not prove product runtime behavior, MCP execution, Bedrock credentials, or graph-wiki workflow correctness.
- It does not prove S02/S03/S04 content is complete.
- It does not convert or validate the entire `.planning/` archive.

## Notes for Tester

This is an artifact-only initialization slice. Treat broad legacy planning details as reference unless a later GSD artifact explicitly adopts them.
