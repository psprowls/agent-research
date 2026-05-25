---
title: lattice-workflows (plugin) — Context
category: package
summary: Concepts, decisions, and ingested sources for lattice-workflows
updated: 2026-05-10
tokens: 1307
---

# lattice-workflows (plugin) — Context

## Concepts

- [[wiki/concepts/lattice-naming-convention]]
- [[wiki/concepts/lattice-workflows-consumption-seam]] — the five integration patterns and the consumer-not-writer principle (note: workflow now also writes the workspace-sibling `specs/` and `plans/` trees per [[wiki/adrs/0013-plans-and-specs-in-lattice-workspace]])
- [[wiki/concepts/lattice-cross-plugin-contract]] — env-var discovery and subprocess invocation used by the v1 cross-plugin scripts
- [[wiki/concepts/lattice-workflows-observability-gate]] — `LATTICE_WORKFLOWS_OBSERVABILITY` opt-out category gate + fail-open invariant for hooks under `plugins/lattice-workflows/hooks/`
- [[wiki/concepts/superpowers-fork-vs-upstream]] — lineage diagram (obra → pcvelz → lattice-workflows), comparison table, and decision rubric for which upstream to track

## Decisions

- [[wiki/adrs/0003-observability-as-category-gate]] — single opt-out env var `LATTICE_WORKFLOWS_OBSERVABILITY` gates every observability hook in this plugin; fail-open invariant
- [[wiki/adrs/0013-plans-and-specs-in-lattice-workspace]] — relocate brainstorming specs and implementation plans from `docs/lattice-workflows/{specs,plans}/` to `<workspace>/{specs,plans}/`; prefix filenames by package/plugin; hard-fail on missing `.lattice.yaml`
- [[wiki/adrs/0016-track-pcvelz-superpowers-fork]] — track `pcvelz/superpowers` as upstream rather than `obra/superpowers`; accepts CC-only portability in exchange for native `TaskCreate`/`blockedBy`/`.tasks.json` and plan-mode hard-gate

## Sources

- [[wiki/sources/2026-05-plans-specs-path-redesign]] — design behind ADR-0013; specifies workspace-resolution helper, prefix inference rules, error-on-missing-manifest behavior, and the brainstorming + writing-plans skill files that change
- 2026-05-lattice-ecosystem-review — proposes pre-explore hook, issue/plan filing, agent-facing API doc; first two became §3.9 patterns, third still open
- 2026-05-lattice-ecosystem-architecture-refinements — establishes the `lattice-` prefix and the consumption-seam patterns (§3.9)
- 2026-05-architecture-3.1-plugin-topology — global tooling tier classification; consumer of all per-repo data plugins
- 2026-05-architecture-3.8-contracts-between-layers — soft-deps on wiki + graph + work-tracker; `${LATTICE_WORKFLOWS_ROOT}` env-var convention; subprocess-not-import for cross-plugin invocation
- 2026-05-architecture-3.9-lattice-workflows-seam — five integration patterns; three v1 slash commands; consumer-not-writer principle; graceful degradation matrix
- 2026-05-architecture-3.10-lattice-experts-design — `writing-plans` and `subagent-driven-development` consumer-side lookup change to bare-name-first; plans record bare name, dispatch resolves to fully-qualified
- 2026-05-lattice-workflows-enable-agent-teams — process change enabling parallel plan execution via Claude Code Agent Teams; orchestrator/teammate prompt templates that may eventually crystallize as `:parallel-plan-execution` skill
- 2026-05-skill-invocation-logging-design — design for the first observability hook (`log-skill-invocation`); establishes the `LATTICE_WORKFLOWS_OBSERVABILITY` opt-out category gate and fail-open invariant
- 2026-05-wiki-workflows-seam-parity — workflows-side of the wiki/workflows seam: three parallel plans landing the §3.9 patterns (Plan A pre-explore + grep skills, Plan B file-work-item end-to-end with `lib/lattice_invoke.py`, Plan C `:next`/`:status` lite stubs); vault discovery via glob
- [[wiki/sources/2026-05-superpower-fork-selection]] — comparison of `pcvelz/superpowers` vs `obra/superpowers`; backs [[wiki/concepts/superpowers-fork-vs-upstream]] and [[wiki/adrs/0016-track-pcvelz-superpowers-fork]]

## Belongs to domain

(none)

## Used by

- [[wiki/plugins/lattice-curator/lattice-curator]] — the curator's `PreToolUse:Skill` hook (`stage-tracker.mjs`) records whenever any Skill tool is invoked, including `lattice-workflows:*` skills. The recorded `lastSkill` drives stage routing in the curator's gate. No contract change to lattice-workflows — purely passive observation.

## Related dependencies

- `obra/superpowers` (original upstream, MIT) — engineering-discipline framework; cross-CLI portable (Claude Code, Codex, Gemini, OpenCode); markdown-checklist task tracking. Lattice-workflows is **not** tracked directly against it. `LICENSE` and `README` preserve attribution per MIT.
- `pcvelz/superpowers` (tracked upstream) — Claude-Code-native fork of `obra/superpowers`; introduces native `TaskCreate`/`TaskUpdate`/`TaskList` with `blockedBy` + `.tasks.json` resume, the `EnterPlanMode`/`ExitPlanMode` hard-gate, opt-in pre-commit / stop-deflection hooks, and the `superpowers-extended-cc:*` namespace rename. See [[wiki/concepts/superpowers-fork-vs-upstream]] for the full lineage and [[wiki/adrs/0016-track-pcvelz-superpowers-fork]] for the decision.
- Zero runtime dependencies — zero-dependency plugin by design
