---
title: Lattice skill resolution order
category: concept
summary: How lattice-workflows' writing-plans and subagent-driven-development resolve `<role>-<tech>` skill names — bare match first (catches user/project overrides), then `lattice-experts:<role>-<tech>` namespaced default, then any other plugin, then nothing. Plans record bare; dispatch resolves to fully-qualified.
tags: [experts, workflows, knowledge-skills, resolution, override]
sources: 1
updated: 2026-05-09
tokens: 1744
---

# Lattice skill resolution order

## Definition
The four-step lookup that [[wiki/plugins/lattice-workflows/lattice-workflows]]'s `writing-plans` (recommend time) and `subagent-driven-development` / `systematic-debugging` (dispatch time) use to resolve `<role>-<tech>` knowledge skill names. ==Bare match wins so user-level and project-level skills can override lattice-experts defaults without forking.==

## Resolution order

1. **Bare-name match in available-skills reminder.** If any installed skill appears in the reminder under the exact bare name `<role>-<tech>`, use that. This catches `~/.claude/skills/<role>-<tech>/SKILL.md` (user-level) and `.claude/skills/<role>-<tech>/SKILL.md` (project-level).
2. **`lattice-experts:<role>-<tech>` namespaced default.** If no bare match, fall back to the plugin-shipped skill.
3. **Any other plugin shipping `<role>-<tech>`.** If experts doesn't ship the combo but a third-party plugin does, use it. **Warn at recommend time** so the user knows a non-canonical source is in play.
4. **No match.** Fill the slot as `None — proceed to Task Description.` (current behavior — unchanged.)

**Precedence inside step 1:** project-level (`.claude/skills/`) beats user-level (`~/.claude/skills/`). ==Repo-specific overrides win over user-wide overrides win over plugin defaults.==

## Plan records bare; dispatch resolves to fully-qualified

| Phase | Behavior |
|---|---|
| **Recommend** (`writing-plans`) | Records the **bare name** (`implementer-expo`) in the plan's `Knowledge Skills:` field and `knowledgeSkills` metadata array — NOT the resolved fully-qualified name. |
| **Dispatch** (`subagent-driven-development`, `systematic-debugging`) | Resolves bare → fully-qualified per the four-step order, writes the **resolved fully-qualified name** into the dispatch prompt's slot. |

Recording the resolved name would freeze the plan to a specific source and break the override (a plan written when only the plugin default existed would skip a user-level skill added later). ==The plan is intent (`I want the implementer-expo expertise applied`); resolution is policy (`which copy of that expertise wins right now`).==

User-level skills appear bare in the reminder; "fully-qualified" for those just means the bare name. The Skill tool needs the namespaced form for plugin-shipped skills.

## Validation

Before dispatching, the slot-filler confirms the resolved name appears in the current available-skills reminder. If a plan-supplied bare name resolves to nothing (plugin uninstalled, user-level file deleted), **strip the entry** from the slot rather than dispatching with a broken name.

## Conflict warning

| Situation | Behavior |
|---|---|
| User/project skill + plugin-shipped skill, same `<role>-<tech>` | Bare-name match wins silently (override semantics) |
| Two plugins ship the same combo | No clear winner — **warn at recommend time** in the plan itself (warning travels with the artifact) |

## Override patterns this enables

- **Whole-skill replacement.** User creates `~/.claude/skills/implementer-expo/SKILL.md` with their own rules. `lattice-experts:implementer-expo` becomes shadowed without being uninstalled — bring-back is reverting one file.
- **Stack experts doesn't cover.** User creates `~/.claude/skills/implementer-svelte/SKILL.md`. `writing-plans`'s recommender sees `implementer-svelte` in the reminder and can suggest it for Svelte tasks; the plugin doesn't need a Svelte skill for this to work.
- **Per-repo overrides.** Project-level `.claude/skills/<role>-<tech>/SKILL.md` lets a single repo override the plugin default without affecting other projects on the same machine.
- **Forking the rule pool.** Power user who wants a different rule library installs experts for the build pipeline, then points `compose:` blocks at their own `rules/` tree under their fork — without affecting the canonical plugin.

## Why this works without new override machinery

Claude Code's available-skills reminder already surfaces:
- User-level skills (`~/.claude/skills/<name>/SKILL.md`) under the **bare name**
- Project-level skills (`.claude/skills/<name>/SKILL.md`) under the **bare name**
- Plugin-shipped skills under the **namespaced form** (`<plugin>:<name>`)

==A lookup that prefers bare-name matches naturally picks up user/project overrides before plugin defaults.== No separate override registry needed.

## What changes from the precursor plugin

| Before | After |
|---|---|
| `writing-plans` looked up `claude-superpowers-knowledge:<role>-<tech>` (fully-qualified, plugin-only) | `writing-plans` looks up bare `<role>-<tech>` first, then `lattice-experts:<role>-<tech>`, then any other plugin |
| Override required forking the plugin | User creates `~/.claude/skills/<role>-<tech>/SKILL.md`; bare-name match wins |
| Plan recorded the fully-qualified name | Plan records the bare name; dispatch resolves to the fully-qualified |

This change lands with the rename sweep (`claude-superpowers-knowledge` → `lattice-experts`).

## Empirical driver

The 38/0 finding from `claude-superpowers/docs/subagent-knowledge-skills.md`: subagents invoked the `Skill` tool zero times across 38 real-world dispatches. ==Knowledge has to be named explicitly in the dispatch prompt — subagents don't reach for skills voluntarily.== This is what forces the consumer-side plumbing (recommender, slot-filler, dispatch templates) to live in `lattice-workflows`, while `lattice-experts` is the content side of the contract.

## Used in
- [[wiki/plugins/lattice-workflows/lattice-workflows]] — the consumer (`writing-plans` + `subagent-driven-development`)
- lattice-experts — the content provider (the namespaced default)

## Related patterns
- [[wiki/concepts/lattice-workflows-consumption-seam]] — knowledge skills participate in the seam by filling subagent dispatch slots
- [[wiki/concepts/lattice-naming-convention]] — the namespacing convention this resolution depends on

## Sources
- 2026-05-architecture-3.10-lattice-experts-design

## Decisions
- adrs/0007-bare-name-first-skill-resolution

## Open questions / deferred to v2
- **Sub-skill rule overlays.** Today the override granularity is whole-skill — replacement of the entire compiled `implementer-expo`, not individual rules within it. A v2 form might let `~/.lattice-experts/rules/<domain>/<rule-id>.md` override or extend a single rule.
- **Automatic routing** of which `<role>-<tech>` to suggest based on richer signals (graph queries, file diffs, task semantics) — speculative.
- **Cross-tool reach** — knowledge skills are SKILL.md files; harnesses without a skill loader (Codex, generic LLM apps) don't see them.
- **Subagent-shaped experts** — a "code-graph-expert" subagent that owns the MCP server (so the parent's context isn't polluted) is a v2 consideration. Per §3.1's rejected-shape (E).
