---
title: "ADR-0010: lattice-curator as fifth ecosystem plugin"
category: adr
summary: Add a fifth lattice-* plugin that curates task-specific knowledge briefs from the wiki and expert rules into Claude Code via a UserPromptSubmit hook, split as a pure Python package + thin Claude Code plugin per the lattice-source-parser precedent.
adr_id: "0010"
status: accepted
decision_date: 2026-05-07
deciders:
  - Patrick Sprowls
supersedes:
superseded_by:
tags: [adr, lattice-curator, ecosystem, plugin-topology, hooks, rag]
updated: 2026-05-09
tokens: 1565
---

# ADR-0010: lattice-curator as fifth ecosystem plugin

**Status:** accepted (2026-05-07; promoted 2026-05-09 — `lattice-curator` shipped)

> [!warning] Stack decision superseded — implementation is Python
> The "pure TypeScript" package described in the Decision section below was never built. The TypeScript stack decision (ADR-0025, superseded by [[wiki/adrs/0012-python-bedrock-stack-for-curator]]) was superseded before implementation began. The on-disk package (`packages/lattice-curator-core/`) is Python (langchain-aws + langgraph + pydantic). The placement decision, hook posture, and package+plugin split recorded here remain valid.

## Context

Eval runs in `evals/reports/` show two recurring failure modes when Claude Code operates inside this ecosystem:

1. **Context bloat from the wiki.** [[wiki/plugins/lattice-wiki/lattice-wiki]] retrieval pulls long narrative pages with broad wikilink fan-out. The `2026-05-07-scenarios-v1-no-wiki` runset improved several scenarios just by removing the wiki entirely — evidence that much of what gets injected is irrelevant to the specific task.
2. **Knowledge skills carry irrelevant rules.** The lattice-experts plugin compiles role-tagged skills with coarse `{domain, impact}` filters; a single skill loads many rules unrelated to the actual prompt.

Layered on top: Claude Code does not always invoke the workflow skill it should (e.g., starts implementing without `writing-plans`). Any system that fires only *inside* skills would miss the cases that need help most.

Full design: the context curation agent design spec.

## Decision

Ship `lattice-curator` as the **fifth lattice-\* plugin**, with the same package-vs-plugin split that [[wiki/packages/lattice-source-parser/lattice-source-parser]] uses:

- **`packages/lattice-curator-core/`** — pure Python curator logic. Given `(prompt, transcriptTail, stage, sources, config)`, returns a `Brief` or a no-op decision. No awareness of Claude Code, hooks, or MCP; unit-testable in isolation; reusable from CI, evals, future plugins.
- **`plugins/lattice-curator/`** — thin Claude Code surface. Owns `hooks/` (`UserPromptSubmit` + `PreToolUse:Skill`) and `mcp/server.py`. This is the only piece that touches Claude Code surfaces.

The plugin runs **outside Claude's decision loop** — `UserPromptSubmit` fires before Claude processes the prompt, so the curator catches turns where Claude *should* but doesn't invoke a workflow skill. A `PreToolUse:Skill` hook writes `{lastSkill, lastSkillAt}` to `~/.cache/lattice-curator/state.json`, giving the gate a recent stage signal that falls back to keyword heuristics when stale.

The curator is **never the bottleneck of a turn**: every failure path bails silently with a JSONL fire-log entry. A hard `minuteBudgetSeconds` cap and `LATTICE_CURATOR_DISABLE=1` env-var provide safety hatches.

## Consequences

**Positive:**
- Claude Code receives task-specific context on every meaningful turn without any cooperation from the model itself — no reliance on Claude remembering to invoke the right skill.
- Wiki and experts rule libraries become high-recall stores; relevance is filtered at read time by the curator rather than at write time by hand-tuned skill compilation.
- Pure-package boundary keeps the curator testable in isolation and reusable from `evals/scenarios/curator-*` without spinning up Claude Code.
- The package + plugin split mirrors an existing precedent ([[wiki/packages/lattice-source-parser/lattice-source-parser]] + its consumer plugins), so the ecosystem doesn't grow a new shape.
- MCP `context.fetch` provides an explicit escape hatch: when Claude *does* know what it wants, it can ask for a brief without going through the gate.

**Negative:**
- Fifth plugin = more surface area to keep coherent.
- `UserPromptSubmit` is `async: false`; the curator blocks every turn. Bedrock latency budget (~1–3s) is non-trivial and forces careful gating (target: only 10–30% of turns reach Pass 1).
- Adds a Bedrock dependency to the per-repo data tier — see [[wiki/adrs/0012-python-bedrock-stack-for-curator]].
- Per-project `.lattice-curator.json` is yet another config file at the repo root.
- The curator overlaps in mission with `/lattice-wiki:query` from [[wiki/plugins/lattice-wiki/lattice-wiki]]; eventual deprecation/rewire is plausible but explicitly not a v1 decision.

## Alternatives considered

- **Fix the wiki and experts query paths in place.** Rejected — both surfaces are high-recall by design. Filtering at write time (more selective skill compilation, smaller wiki pages) trades off discoverability for relevance. A read-time filter sidesteps the tradeoff.
- **Fire only inside workflow skills (e.g., a `writing-plans` extension).** Rejected — misses the cases that matter most: Claude skipping the skill it should have invoked. The whole motivation is to operate when Claude doesn't self-direct.
- **MCP-only (no hook).** Rejected for v1 — relies on Claude remembering to call `context.fetch`, which is exactly the behavior we can't depend on. MCP ships *alongside* the hook as an escape hatch, not the primary path.
- **Bundle into [[wiki/plugins/lattice-wiki/lattice-wiki]].** Rejected — the curator consumes both the wiki and experts; bundling into either creates an asymmetric dependency. A separate plugin keeps both knowledge surfaces equal peers.

## Impact

- [[wiki/packages/lattice-curator-core/lattice-curator-core]] — primary subject (package side).
- [[wiki/plugins/lattice-curator/lattice-curator]] — primary subject (plugin side).
- [[wiki/plugins/lattice-wiki/lattice-wiki]] — becomes a knowledge surface consumed by the curator.
- [[wiki/plugins/lattice-workflows/lattice-workflows]] — its skills' invocation is what the `PreToolUse:Skill` hook tracks; no contract change.
- [[wiki/packages/lattice-evals/lattice-evals]] — gains the `curator-*` scenario family as a planned eval consumer.

## Follow-ups

- Default Bedrock model id — benchmark Haiku / DeepSeek / Kimi-class against recorded fixtures and pin in plan-writing.
- Consider a v2 telemetry consumer that surfaces curator effectiveness in [[wiki/packages/lattice-evals/lattice-evals]] reports.
- Revisit the `/lattice-wiki:query` overlap once curator data exists.
