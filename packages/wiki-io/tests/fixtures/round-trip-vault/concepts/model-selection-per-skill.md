---
title: Model selection per skill
category: concept
summary: Three-tier rubric (Opus / Sonnet / Haiku) for matching a Claude model to a task by ambiguity, stakes, and shape, declared per-skill (and per-agent) via a `model:` frontmatter field.
tags: [models, claude, opus, sonnet, haiku, lattice-workflows, skills, agents, cost]
sources: 1
updated: 2026-05-10
tokens: 1625
---

# Model selection per skill

## Definition

A rubric for choosing a Claude model per dispatched unit of work (a skill or a subagent), based on the **shape** of the task rather than the size of the codebase. Each skill or agent declares its preferred model in YAML frontmatter (`model: opus | sonnet | haiku`); the dispatch layer honors that declaration when spawning the work. Default tier is **Sonnet**; tasks shift up to **Opus** when they are open-ended or high-stakes, and down to **Haiku** when they are purely mechanical.

## Motivation

A single global model choice over-pays on mechanical sub-steps and under-delivers on ambiguous synthesis. Per-skill selection lets the cheap, routable tasks (pre-explore, grep replacement, file-walk-and-classify) run on Haiku while the genuinely hard ones (brainstorming, final code review) get Opus. Most skill execution stays on Sonnet — the balanced default — without paying Opus prices everywhere.

## The three tiers

| Model | ID | Strength | Cost / Speed |
|---|---|---|---|
| **Opus 4.7** | `claude-opus-4-7` | Deep reasoning, ambiguous problems, novel synthesis | Slowest / most expensive |
| **Sonnet 4.6** | `claude-sonnet-4-6` | Balanced — strong coding, good reasoning | Mid |
| **Haiku 4.5** | `claude-haiku-4-5-20251001` | Fast, cheap, reliable on well-defined tasks | Fastest / cheapest |

## Decision rules

**Use Opus when:**
- The task is genuinely open-ended or ambiguous (brainstorming, architectural decisions).
- Failure is expensive (security review, final code review before shipping).
- The agent must synthesize across many inputs without a clear template.
- The agent is in "exploration" mode — not yet sure what it's looking for.

**Use Sonnet when:**
- The task is well-scoped but requires real reasoning (implementing a feature, debugging, writing tests).
- You want Opus-tier quality on most coding tasks at lower cost.
- ==This is the default for skill execution.==

**Use Haiku when:**
- The task is purely mechanical: extract, classify, transform, summarize to a template.
- The skill is a dispatcher or router (deciding which agent to call next).
- High-frequency, low-stakes sub-tasks within a larger pipeline.

## Applied to lattice-workflows (and sibling plugins)

The original article framed every entry as a "skill". In practice the lattice ecosystem has progressively moved repo-walking and review work into **agents** rather than skills, because agents carry their own `model:` field and dispatch independently of the caller's loop — giving finer model control.

| Unit | Where | Model | Rationale |
|---|---|---|---|
| `brainstorming` | skill | Opus | Open-ended, requires genuine creativity |
| `systematic-debugging` | skill | Sonnet | Structured reasoning, well-defined |
| `writing-plans` / `write-plan` | skill | Sonnet (Opus when the task is ambiguous) | Plan shape varies with task ambiguity |
| `pre-explore` | skill | Haiku | Lookup / routing step |
| `prefer-graph-over-grep` | skill | Haiku | Mechanical decision |
| `code-reviewer` | agent (`plugins/lattice-workflows/agents/code-reviewer.md`) | Opus | Nuanced judgment, high stakes |
| `verification-before-completion` | skill | Sonnet | Structured checklist execution |
| `scanner` (the article's "code-scanner") | agent (`plugins/lattice-wiki/agents/scanner.md`) | Sonnet | Repo walk + diff against vault; lives in `lattice-wiki`, not `lattice-workflows` |
| `using-workflows` | skill | *(intentionally unset)* | Bootstrap skill that runs in the caller's main loop; declaring a model here would override the loop's model |

## Shape

The selection is encoded per-unit in YAML frontmatter:

```yaml
---
name: brainstorming
model: opus
---
```

For skills: `plugins/lattice-workflows/skills/<skill>/SKILL.md`.
For agents: `plugins/lattice-workflows/agents/<agent>.md`.

The dispatch layer (Claude Code's Skill / subagent invocation) reads `model:` when spawning the work; absence falls back to the session default.

## Used in

- [[wiki/plugins/lattice-workflows/lattice-workflows]] — applies the rubric across its skills and agents
- [[wiki/plugins/lattice-workflows/patterns]] — "Per-skill model selection" pattern bullet
- [[wiki/plugins/lattice-workflows/api]] — notes the `model:` frontmatter field on each skill

## Related patterns

- [[wiki/concepts/lattice-workflows-consumption-seam]] — workflow as a consumer; per-skill model choice is independent of which surface (vault, graph, sidecar) the skill reads
- [[wiki/concepts/execution-skills-comparison]] — chooses *which* execution skill to run; this concept chooses *which model* runs the chosen skill
- [[wiki/concepts/subagent-vs-teammate]] — dispatched units that also benefit from per-unit `model:` declarations

## Sources

- [[wiki/sources/2026-05-model-selection-guidelines]]

## Open questions / gotchas

- The article speaks only of **skills**, but lattice splits dispatched work across `skills/` and `agents/`. Both surfaces carry `model:` frontmatter; some work (notably code review and repo scanning) has migrated from skills into agents specifically so each unit can pin its own model independent of the caller's loop.
- The `using-workflows` bootstrap skill intentionally has no `model:` — it runs in the caller's main loop, so declaring a model would override the loop's choice. The article's "every skill carries `model:`" claim is therefore softened in this wiki.
- Sonnet / Opus is a sliding scale on `writing-plans`. No precise rule yet for when an ambiguous plan crosses into Opus territory.

## Notes on the source's mapping

- **`code-reviewer`** is an *agent*, not a skill — it lives at `plugins/lattice-workflows/agents/code-reviewer.md` (model: opus). Sibling agents `implementer` and `spec-reviewer` were not in the article's rubric but exist in `agents/` and carry their own `model:` declarations. The skill-only framing in the source is a simplification — the same rubric applies to both surfaces.
- **`code-scanner`** in the source maps to the `lattice-wiki:scanner` agent at `plugins/lattice-wiki/agents/scanner.md` (model: sonnet) — repo walking and vault diffing is owned by `lattice-wiki`, not `lattice-workflows`. The "code-scanner" label was a generic placeholder; the actual implementation is the scanner agent in the wiki plugin.
