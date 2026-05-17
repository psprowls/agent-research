---
title: Experimental skills at .claude/skills/
category: concept
summary: Pattern for incubating new behavior-shaping skills at project-scoped `.claude/skills/<name>/SKILL.md` for fast iteration, then promoting to `plugins/<plugin>/skills/<name>/` once the skill is stable. Project-scoped skills auto-discover (after a session refresh) and need no plugin manifest changes during iteration.
tags: [skills, lattice-workflows, lattice-experts, lattice-wiki, iteration, promotion, plugins]
sources: 0
updated: 2026-05-09
tokens: 1314
---

# Experimental skills at .claude/skills/

## Definition

The Lattice ecosystem has two skill homes: **plugin-scoped** (`plugins/<plugin>/skills/<name>/SKILL.md`, namespaced as `<plugin>:<name>`) and **project-scoped** (`.claude/skills/<name>/SKILL.md`, bare-named). The "experimental skills at .claude/skills/" pattern uses the project-scoped path as an incubator — write the skill there first, iterate against real use, and promote to plugin-scoped once the contract stabilizes.

Project-scoped skills:
- Are auto-discovered by Claude Code (after a session refresh)
- Need no plugin-manifest changes during iteration
- Can be edited freely without affecting users who don't share `.claude/`
- Don't carry plugin-level conventions like baseline tests or version bumps yet

When the skill stabilizes (consistent contract, validated through use, ready for users beyond the author), it graduates to a plugin.

## Motivation

Plugin promotion isn't free: writing baseline pressure tests, wiring `commands/<name>.md`, deciding final frontmatter, and making sure the skill works for users who don't share the author's `.claude/`. Doing all of that *before* the skill's contract is stable wastes effort because the contract changes as you use it.

But starting in `~/.claude/skills/` (user-scoped) has a different problem: the user-scoped path is shared across every project on the machine, which means experimental friction or half-baked behavior leaks into unrelated work.

`.claude/skills/<name>/` is the sweet spot: project-local (only this repo's sessions see it), no plugin overhead, auto-discovered, and trivial to delete or move once the skill is ready.

## Shape

The promotion path:

```
1. Write SKILL.md at .claude/skills/<name>/SKILL.md
   - Frontmatter: name, description (focus on triggers, not workflow summary)
   - Body: process, red flags, integration
   - Auxiliary files (prompt templates, reference material) live alongside

2. Iterate against real use
   - Run smoke tests
   - Capture failures in the SKILL.md as Red Flags / process tightening
   - Hook log helps verify the right skills are being invoked

3. Promote to plugins/<plugin>/skills/<name>/
   - Copy files
   - Add baseline pressure tests under tests/<name>/
   - Author commands/<name>.md if a slash command makes sense
   - Update the plugin's CLAUDE.md / README to reference the skill
   - Delete the .claude/skills/<name>/ source — one source of truth
```

What changes during promotion:
- **Frontmatter rigor** — plugin skills are user-facing; the description must be tuned for retrieval, not just for the author
- **Tests** — plugins demand baseline RED-GREEN tests via [[wiki/plugins/lattice-workflows/lattice-workflows]]:`writing-skills`; project skills can skip this during incubation
- **Slash command** — plugin skills often have a slash command at `commands/<name>.md`; project skills don't need one
- **Cross-references** — `[[wiki/wikilinks]]` and `lattice-workflows:` namespacing assume the plugin shape; the project version may use shorter forms
- **Knowledge Skills slot** — if the skill dispatches subagents and the plan supplies `knowledge_skills`, the dispatch templates need to reference the lattice-experts entries by their fully-qualified names

## Used in

- `.claude/skills/launching-plan-teams/` — current example. Born during the 2026-05-03-enable-agent-teams spike, validated through 4 smoke tests, promotion tracked at 2026-05-04-promote-launching-plan-teams.
- Any future skill that's not yet ready for the plugin commitment should default to this incubator pattern rather than going straight to `plugins/`.

## Related patterns

- knowledge-skills-pattern — knowledge skills follow a similar bare-name-first resolution that lets project/user skills shadow plugin defaults.
- adrs/0007-bare-name-first-skill-resolution — the resolution policy that makes project-scoped skills first-class.
- [[wiki/concepts/subagent-vs-teammate]] — context for why iteration speed matters: agent-teams skills involve multiple roles, multiple prompts, multiple smoke tests; the iteration cost amplifies the value of an incubator path.

## Open questions / gotchas

- **Session refresh required for new project skills to appear in the available-skills list.** During the 2026-05-03-enable-agent-teams spike, `launching-plan-teams` was added mid-session and wasn't visible to the Skill tool until the next session-start hook fired. The author can still drive the skill manually by reading SKILL.md, but auto-discovery requires a refresh.
- **`.claude/skills/` collides with `.claude/settings.local.json` in some workflows** — both are project-scoped. Take care when committing: the skill files probably want to be checked in; settings.local.json typically should not.
- **Incubator skills should avoid hard dependencies on user-private skills** — if the skill assumes a `~/.claude/skills/<helper>/` exists, promotion breaks for users who don't have it. Use plugin-namespaced references when possible during the incubator phase, even before promotion.
- **No automated promotion checklist exists yet.** The work item per skill captures the steps; if promotion becomes routine, a `lattice-workflows:promote-skill` skill might be worth filing.
