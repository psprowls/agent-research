---
title: Shape A vs Shape B (parallel-plan team layouts)
category: concept
summary: Two team-layout choices for `launching-plan-teams` — Shape A spawns 2 teammates per plan (implementer + collapsed reviewer), Shape B spawns 3 (implementer + spec-reviewer + code-quality-reviewer with 2-deep dep chain). Shape B preserves SDD's spec/quality review separation; Shape A is the trivial-plan escape hatch.
tags: [agent-teams, lattice-workflows, parallel-plans, review, sdd]
sources: 0
updated: 2026-05-09
tokens: 1488
---

# Shape A vs Shape B (parallel-plan team layouts)

## Definition

`launching-plan-teams` (see 2026-05-04-promote-launching-plan-teams) has two viable team layouts:

- **Shape A** — 2 teammates per plan: `implementer-<slug>` and `reviewer-<slug>` (a single combined reviewer that applies both spec compliance and code quality lenses). Task chain: `implement → review` (1-deep).
- **Shape B** — 3 teammates per plan: `implementer-<slug>`, `spec-reviewer-<slug>`, `code-quality-reviewer-<slug>`. Task chain: `implement → review-spec → review-quality` (2-deep).

For N plans, Shape A spawns 2N teammates and 2N tasks; Shape B spawns 3N teammates and 3N tasks.

## Motivation

The original [[wiki/plugins/lattice-workflows/lattice-workflows]]:`subagent-driven-development` skill separates spec compliance from code quality at the per-task level — a deliberate choice to prevent blurred verdicts ("looks fine I guess") that emerge when a single reviewer applies all lenses simultaneously. `launching-plan-teams` carries that ethos to the per-plan level.

But the spec/quality split has a cost: 50% more reviewer teammates, more `SendMessage` traffic, and more lead bookkeeping. For a substantive plan (real feature, real refactor), the cost is worth it — review fidelity directly affects what merges. For a trivial plan (fixture file, version bump, doc tweak), the cost is overkill — there's no quality bar that benefits from the split.

Shape A and Shape B exist because the right answer depends on the work, not the skill.

## Shape

| Aspect | Shape A | Shape B |
|---|---|---|
| Teammates per plan | 2 | 3 |
| Task-chain depth | 1 (`impl → review`) | 2 (`impl → review-spec → review-quality`) |
| Lead nudges per plan | 1 (impl→review) | 2 (impl→spec, spec→quality) |
| Reviewer subagent_type | `lattice-workflows:code-reviewer` (rubric pre-loaded) | spec: `general-purpose`; quality: `lattice-workflows:code-reviewer` (see adrs/0014-spec-reviewer-uses-general-purpose-not-code-reviewer) |
| Token cost (vs Shape A) | baseline | +50% per plan |
| Review fidelity | combined verdict per branch | independent spec / quality verdicts per branch |
| Smoke-tested | smoke test 3 (2026-05-04 AM) + production run (2026-05-04 PM, Plans B+C) | smoke test 4 (2026-05-04 AM) |

The two shapes share most of the skill's machinery: pre-flight, independence check, dispatch confirmation, lead-nudge protocol, auto-shutdown. They differ only in the team-population step (2N vs 3N tasks/teammates) and the number of phases monitored.

## Decision criteria

Pick **Shape B** when:
- Plans are substantive (feature work, refactors, code that survives merge)
- Spec drift is plausible (plans with multiple acceptance criteria, multiple files, or any room for the implementer to misinterpret intent)
- Code quality matters at merge time (production code paths, security-sensitive areas)

Pick **Shape A** when:
- Plans are trivial (fixture files, doc tweaks, version bumps, single-line config edits)
- The implementer can't realistically miss the spec (one acceptance criterion, one file, deterministic verify command)
- The token cost of three teammates per plan dwarfs the value of the split

The default in `launching-plan-teams` SKILL.md is Shape B; Shape A is documented as the `## Single-Reviewer Variant` escape hatch and the lead announces which one is being used at the dispatch-confirmation step.

## Used in

- `.claude/skills/launching-plan-teams/` — both shapes documented; SKILL.md walks the lead through which to pick at confirmation time.
- 2026-05-03-enable-agent-teams — spike narrative covering both shapes' empirical validation.
- 2026-05-04-promote-launching-plan-teams — promotion plan preserves both.

## Related patterns

- [[wiki/concepts/subagent-vs-teammate]] — the underlying agent-teams primitive both shapes build on.
- [[wiki/concepts/lead-nudge-protocol]] — both shapes require it; Shape B requires it twice per plan.
- knowledge-skills-pattern — Shape B's spec-vs-quality split echoes that pattern's role × tech separation.

## Open questions / gotchas

- **Shape C? (5+ teammates per plan)** — N reviewers covering distinct lenses (security, perf, accessibility) is conceivable but speculative; not implemented and not currently planned. The token cost grows linearly per plan and the coordination overhead grows roughly quadratically (more SendMessages between roles); requires a real second consumer before being worth designing.
- **Mixed shapes per run.** Could a single dispatch use Shape A for trivial plans and Shape B for substantive ones in the same team? Possible but not currently supported — the skill picks one shape per dispatch. Filing for a second-consumer use case if/when it arrives.
- **Empirical limits.** Smoke tests covered N=2 plans (4 teammates Shape A, 6 teammates Shape B). Doc recommends 3–5 teammates as the practical sweet spot; Shape B at N=2 hits 6, the top end. N=3 plans Shape B would mean 9 teammates — past the recommendation. Real-world parallel runs should validate the upper bound.
- **Shape A handles substantive plans, not just trivial ones.** The 2026-05-04 PM production run (2026-05-04-real-world-parallel-plan-team-run) approved Plan B (9 tasks, ~564 LOC across two plugins, real TDD on `ingest_work_item.py`) under one combined reviewer with only `nit`-severity findings. The current "Shape A is for trivial plans" framing is too restrictive — when the plan provides verbatim content, Shape A's combined reviewer is sufficient regardless of plan size. Suggest reframing: "Shape A when verbatim content; Shape B when judgment latitude". Tracked in 2026-05-04-promote-launching-plan-teams log.
