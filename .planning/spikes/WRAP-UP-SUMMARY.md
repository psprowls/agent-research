# Spike Wrap-Up Summary

**Date:** 2026-05-17
**Spikes processed:** 1
**Feature areas:** Subagent context injection
**Skill output:** `./.claude/skills/spike-findings-deep-agents/`

## Processed Spikes

| # | Name | Type | Verdict | Feature Area |
|---|------|------|---------|--------------|
| 001 | subagent-context-audit | standard | VALIDATED ✓ | Subagent context injection |

## Key Findings

- **Two `cores/prompt-sources/SKILL.md` sections were dropped from the Python port's subagent prompts:** Architecture / vault layout (L34-69) and the root-vs-wiki `CLAUDE.md` disambiguation note (L141).
- **Four `lattice/wiki/CLAUDE.md` sections never reach subagent context today:** Style rules (L153-159), Log format (L124-133), per-category frontmatter required fields, and most critically the parsed `<!-- lattice-wiki:layout:start -->` block — which is read as data in `scan.py:282` and `lint.py:324` but never injected into any `SystemMessage`.
- **Architectural surprise:** `deepagents` is not imported anywhere in `agents/` or `cores/`. Subagent dispatch goes through a custom `SubagentPool` in `cores/subagent-runtime/pool.py` using raw `llm.ainvoke([SystemMessage, HumanMessage])`. This rules out "deepagents virtual filesystem read-on-demand" as a fix path without a separate migration decision.
- **Cost is not the constraint.** Full injection of both files adds ~6,140 tokens per call (~$0.003–$0.013 per pass on Bedrock Qwen3-32B). The real problem is signal-to-noise: roughly half of `SKILL.md` is user-facing or meta content that dilutes the load-bearing rules.
- **Recommended fix:** combine (C) extending `prompts/_fragments/` with four new curated extracts and (D) injecting a small rendered project-context block from `wiki/CLAUDE.md` at command entry. Total added tokens per role land in the 800–1,200 range, well under the 1,500 ceiling. Next step is `/gsd-plan-phase wire-curated-context-into-subagents`.
