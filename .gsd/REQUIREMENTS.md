# Requirements

This file is the explicit capability and coverage contract for the project.

## Active

## Validated

### R005 — M001 must produce an execution-ready roadmap for completing GSD initialization as demoable planning and curation slices.
- Class: launchability
- Status: validated
- Description: M001 must produce an execution-ready roadmap for completing GSD initialization as demoable planning and curation slices.
- Why it matters: After initialization, future `/gsd auto` work needs concrete, artifact-focused units with dependencies and verification expectations.
- Source: .gsd/milestones/M001/M001-ROADMAP.md; .gsd/milestones/M001/M001-CONTEXT.md
- Primary owning slice: M001/S04
- Supporting slices: M001/S01, M001/S02, M001/S03
- Validation: Validated by S04 verifier: `python3 .gsd/milestones/M001/slices/S04/verify_s04_readiness.py` passes, confirming roadmap dependencies, required artifacts, D001-D003 decision concepts, source traceability, and prohibited-overclaim checks across the initialized GSD state.
- Notes: Roadmap work is artifact-focused and does not imply product runtime code changes in M001.

### R001 — Current GSD artifacts must be the active source of truth for future planning and execution in this repo.
- Class: continuity
- Status: validated
- Description: Current GSD artifacts must be the active source of truth for future planning and execution in this repo.
- Why it matters: Future agents need one current planning state instead of rediscovering or accidentally activating archived pre-fork planning records every session.
- Source: .gsd/PROJECT.md; .gsd/milestones/M001/M001-CONTEXT.md; .gsd/milestones/M001/slices/S01/S01-SUMMARY.md
- Primary owning slice: M001/S01
- Supporting slices: M001/S02, M001/S03, M001/S04
- Validation: Validated by S01: `.gsd/PROJECT.md` exists, names `.gsd/` as the active source of truth, keeps `.planning/` as archive/reference evidence, reflects current package layout and shipped trajectory, and avoids legacy conversion overclaims.
- Notes: Active truth belongs in `.gsd/`; `.planning/` remains historical evidence only.

### R002 — Selected legacy `.planning` high notes must be preserved in current GSD context without copying the archive wholesale.
- Class: continuity
- Status: validated
- Description: Selected legacy `.planning` high notes must be preserved in current GSD context without copying the archive wholesale.
- Why it matters: The old archive contains important project memory, but wholesale import would make active GSD artifacts noisy, stale, and misleading.
- Source: .gsd/PROJECT.md; .gsd/milestones/M001/M001-CONTEXT.md; .planning/PROJECT.md; .planning/MILESTONES.md; .gsd/milestones/M001/slices/S02/S02-SUMMARY.md
- Primary owning slice: M001/S02
- Supporting slices: M001/S01, M001/S03, M001/S04
- Validation: Validated by S02 verifier: `.gsd/milestones/M001/M001-CONTEXT.md` preserves selected v1.1 through v1.11 high notes with source-path references and explicit selective/non-wholesale boundary language.
- Notes: Preservation is selective and contextual; it is not a wholesale `.planning` conversion.

### R003 — Deferred work and caveats from the legacy archive must be explicitly labeled so future agents do not mistake them for completed or active commitments.
- Class: failure-visibility
- Status: validated
- Description: Deferred work and caveats from the legacy archive must be explicitly labeled so future agents do not mistake them for completed or active commitments.
- Why it matters: The main migration risk is flattening archived state into current truth and causing future agents to resume or rely on stale claims.
- Source: .gsd/milestones/M001/M001-CONTEXT.md; .planning/CONTINUE-sweep-harness-fixes-3.md; .planning/deferred-items.md; .gsd/milestones/M001/slices/S02/S02-SUMMARY.md
- Primary owning slice: M001/S02
- Supporting slices: M001/S03, M001/S04
- Validation: Validated by S02 verifier: deferred sweep handoff, stale snapshot caveat, process-debt notes, and archive/reference boundary are labeled in `.gsd/milestones/M001/M001-CONTEXT.md` without treating them as active or completed M001 commitments.
- Notes: Includes cost-frontier rerun/winner-selection handoff and stale snapshot/process-debt caveats as future context only.

### R004 — Initialized GSD artifacts must be internally consistent, traceable to sampled legacy sources, and honest about omissions.
- Class: quality-attribute
- Status: validated
- Description: Initialized GSD artifacts must be internally consistent, traceable to sampled legacy sources, and honest about omissions.
- Why it matters: The initialized project state will guide downstream automated execution; contradictions, missing ownership, or overclaims would cause wasted work.
- Source: .gsd/PROJECT.md; .gsd/milestones/M001/M001-CONTEXT.md; .gsd/milestones/M001/M001-ROADMAP.md; .planning/CONTINUE-sweep-harness-fixes-3.md; .planning/deferred-items.md; .planning/PROJECT.md; .planning/MILESTONES.md
- Primary owning slice: M001/S03
- Supporting slices: M001/S04
- Validation: Validated by S03 verifier: `python3 .gsd/milestones/M001/slices/S03/verify_s03_requirements.py` passes, confirming requirements buckets, M001 owner mappings, deferred future labels, out-of-scope anti-feature exclusions, required source references, and inline negative checks for missing mappings/labels/sources plus prohibited overclaims.
- Notes: S03 executable requirements verification passed; keep `.gsd/milestones/M001/slices/S03/verify_s03_requirements.py` as the diagnostic surface for future contract drift.

## Deferred

### R006 — Cost-frontier sweep debug, authoritative rerun, and per-role winner selection should be handled in a future milestone, not this initialization milestone.
- Class: differentiator
- Status: deferred
- Description: Cost-frontier sweep debug, authoritative rerun, and per-role winner selection should be handled in a future milestone, not this initialization milestone.
- Why it matters: The work matters to the project’s cost/value promise, but it requires debugging and likely paid Bedrock eval runs outside the bootstrap scope.
- Source: .gsd/milestones/M001/M001-CONTEXT.md; .planning/CONTINUE-sweep-harness-fixes-3.md; .planning/MILESTONES.md
- Primary owning slice: none
- Supporting slices: none
- Validation: Deferred/future-only: reference-only context for a future debug/eval milestone; no active M001 execution owner.
- Notes: Future/deferred. The `$3.46` sweep rerun and stale `.planning/sweep/*.md` diagnostics are not authoritative; future work must debug answer degradation, run a clean sweep, and ask the human to select per-role winners before changing model defaults.

### R007 — A broader structured index of legacy `.planning` artifacts may be created later if archive archaeology becomes frequent.
- Class: admin/support
- Status: deferred
- Description: A broader structured index of legacy `.planning` artifacts may be created later if archive archaeology becomes frequent.
- Why it matters: It could make future archaeology easier, but it is not necessary to initialize current GSD state.
- Source: .gsd/milestones/M001/M001-CONTEXT.md; .planning/PROJECT.md; .planning/MILESTONES.md
- Primary owning slice: none
- Supporting slices: none
- Validation: Deferred/future-only: optional archive-navigation support if archive archaeology becomes frequent; no active M001 execution owner.
- Notes: Future/deferred. M001 intentionally preserves selected high notes only; a structured archive index/backlog can be scoped later if repeated `.planning` archaeology proves valuable.

## Out of Scope

### R008 — Do not wholesale-convert every `.planning` artifact into `.gsd`.
- Class: anti-feature
- Status: out-of-scope
- Description: Do not wholesale-convert every `.planning` artifact into `.gsd`.
- Why it matters: Wholesale conversion would create noisy active artifacts and increase the chance that stale archived plans are treated as current commitments.
- Source: .gsd/milestones/M001/M001-CONTEXT.md; .planning/PROJECT.md; .planning/MILESTONES.md
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: Explicit exclusion. The legacy archive includes many phase contexts, summaries, quick tasks, sketches, spikes, and archived requirements; M001 curates high notes and caveats only, not a comprehensive conversion.

### R009 — Do not build reusable `.planning` migration/backfill tooling or perform legacy audit/verification backfill as part of M001.
- Class: anti-feature
- Status: out-of-scope
- Description: Do not build reusable `.planning` migration/backfill tooling or perform legacy audit/verification backfill as part of M001.
- Why it matters: Automation would add implementation work without clear future reuse, and the archive is already backed up.
- Source: .gsd/milestones/M001/M001-CONTEXT.md; .planning/PROJECT.md; .planning/MILESTONES.md
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: Explicit exclusion. Manual curation is sufficient for initialization; skipped historical audits, missing validation artifacts, and legacy verification gaps remain process-debt context unless freshly scoped later.

### R010 — Do not blindly resume archived plans or perform exhaustive archive audits as active GSD work without fresh scoping and current-source verification.
- Class: anti-feature
- Status: out-of-scope
- Description: Do not blindly resume archived plans or perform exhaustive archive audits as active GSD work without fresh scoping and current-source verification.
- Why it matters: Archived plans are historical evidence, not proof that the next action remains valid.
- Source: .gsd/milestones/M001/M001-CONTEXT.md; .planning/PROJECT.md; .planning/MILESTONES.md
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: Explicit exclusion. Old plans may reflect shipped, superseded, or partially deferred work; future milestones should verify against current source and create fresh `.gsd/` requirements before execution.

### R011 — Do not execute the cost-frontier sweep, spend Bedrock eval budget, select authoritative winners, or update model defaults as part of M001.
- Class: anti-feature
- Status: out-of-scope
- Description: Do not execute the cost-frontier sweep, spend Bedrock eval budget, select authoritative winners, or update model defaults as part of M001.
- Why it matters: The sweep handoff documents a non-authoritative run and unresolved answer-quality regression; treating it as initialization work would create cost, risk, and misleading model-selection claims.
- Source: .gsd/milestones/M001/M001-CONTEXT.md; .planning/CONTINUE-sweep-harness-fixes-3.md; .planning/MILESTONES.md
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: Explicit exclusion. M001 records the deferred handoff only; future work must debug answer degradation, run a clean sweep with approval, and have the human choose per-role winners.

## Traceability

| ID | Class | Status | Primary owner | Supporting | Proof |
|---|---|---|---|---|---|
| R001 | continuity | validated | M001/S01 | M001/S02, M001/S03, M001/S04 | Validated by S01: `.gsd/PROJECT.md` exists, names `.gsd/` as the active source of truth, keeps `.planning/` as archive/reference evidence, reflects current package layout and shipped trajectory, and avoids legacy conversion overclaims. |
| R002 | continuity | validated | M001/S02 | M001/S01, M001/S03, M001/S04 | Validated by S02 verifier: `.gsd/milestones/M001/M001-CONTEXT.md` preserves selected v1.1 through v1.11 high notes with source-path references and explicit selective/non-wholesale boundary language. |
| R003 | failure-visibility | validated | M001/S02 | M001/S03, M001/S04 | Validated by S02 verifier: deferred sweep handoff, stale snapshot caveat, process-debt notes, and archive/reference boundary are labeled in `.gsd/milestones/M001/M001-CONTEXT.md` without treating them as active or completed M001 commitments. |
| R004 | quality-attribute | validated | M001/S03 | M001/S04 | Validated by S03 verifier: `python3 .gsd/milestones/M001/slices/S03/verify_s03_requirements.py` passes, confirming requirements buckets, M001 owner mappings, deferred future labels, out-of-scope anti-feature exclusions, required source references, and inline negative checks for missing mappings/labels/sources plus prohibited overclaims. |
| R005 | launchability | validated | M001/S04 | M001/S01, M001/S02, M001/S03 | Validated by S04 verifier: `python3 .gsd/milestones/M001/slices/S04/verify_s04_readiness.py` passes, confirming roadmap dependencies, required artifacts, D001-D003 decision concepts, source traceability, and prohibited-overclaim checks across the initialized GSD state. |
| R006 | differentiator | deferred | none | none | Deferred/future-only: reference-only context for a future debug/eval milestone; no active M001 execution owner. |
| R007 | admin/support | deferred | none | none | Deferred/future-only: optional archive-navigation support if archive archaeology becomes frequent; no active M001 execution owner. |
| R008 | anti-feature | out-of-scope | none | none | n/a |
| R009 | anti-feature | out-of-scope | none | none | n/a |
| R010 | anti-feature | out-of-scope | none | none | n/a |
| R011 | anti-feature | out-of-scope | none | none | n/a |

## Coverage Summary

- Active requirements: 0
- Mapped to slices: 0
- Validated: 5 (R001, R002, R003, R004, R005)
- Unmapped active requirements: 0
