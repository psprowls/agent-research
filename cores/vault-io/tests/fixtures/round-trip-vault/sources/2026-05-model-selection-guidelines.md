---
title: "Model Selection Guidelines"
category: source
summary: Three-tier rubric (Opus / Sonnet / Haiku) for choosing a Claude model per task, with a per-skill mapping for lattice-workflows and an implementation approach that adds a `model:` field to each skill's YAML frontmatter.
source_path: raw/articles/model-selection-guidelines.md
source_type: article
source_date: 2026-05
authors: []
ingested: 2026-05-10
updated: 2026-05-10
tags: [models, claude, opus, sonnet, haiku, lattice-workflows, skills, cost]
tokens: 1126
---

# Model Selection Guidelines

## TL;DR

A short rubric for matching a Claude model (Opus 4.7 / Sonnet 4.6 / Haiku 4.5) to a task based on ambiguity, stakes, and shape. Proposes adding a `model:` field to each skill's YAML frontmatter in [[wiki/plugins/lattice-workflows/lattice-workflows]] so the dispatch layer can honor per-skill model choices, complementing the existing `subagent_type` dimension.

## Key claims

- **Three tiers, three shapes.** Opus = deep reasoning / open-ended / high-stakes; Sonnet = balanced default for well-scoped reasoning (coding, debugging, tests); Haiku = mechanical extract/classify/transform/route.
- **Failure cost drives the tier.** Security review and final pre-ship code review go Opus because the cost of a miss is high; mechanical dispatchers go Haiku because misclassification is cheap and recoverable.
- **Sonnet is the default for skill execution.** Most lattice-workflows skills do well-scoped reasoning and should default to Sonnet unless they are clearly exploratory (→ Opus) or clearly mechanical (→ Haiku).
- **Per-skill model mapping for lattice-workflows:** `brainstorming` → Opus, `systematic-debugging` → Sonnet, `write-plan` / `writing-plans` → Sonnet/Opus (depending on ambiguity), `pre-explore` → Haiku, `prefer-graph-over-grep` → Haiku, `code-scanner` → Haiku, `code-reviewer` → Opus, `verification-before-completion` → Sonnet.
- **Implementation:** add `model: opus|sonnet|haiku` to each skill's frontmatter; dispatch layer honors it when spawning agents.

## Proposed changes

- Each `plugins/lattice-workflows/skills/<skill>/SKILL.md` grows a `model:` frontmatter field.
- Each `plugins/lattice-workflows/agents/<agent>.md` likewise grows a `model:` frontmatter field (the article maps both kinds even if it labels them all "skills" — see contradiction below).
- A dispatch layer (currently implicit in Claude Code's Skill / subagent invocation) honors the field. The article doesn't specify where this code lives.

## Synthesis

Canonical concept page: [[wiki/concepts/model-selection-per-skill]]. The lattice-workflows pattern bullet "Per-skill model selection" on [[wiki/plugins/lattice-workflows/patterns]] captures the rule for the plugin.

## Notes on the source's mapping

The source's "Applied to lattice-workflows Skills" table calls everything a "skill", but in the lattice ecosystem the same rubric applies to two parallel surfaces — `skills/` and `agents/` — and some units have migrated from one to the other for finer model control:

- **`code-reviewer`** is an *agent*, not a skill: `plugins/lattice-workflows/agents/code-reviewer.md` (model: opus). Sibling agents `implementer` and `spec-reviewer` also live in `agents/` with their own `model:` declarations and were not in the article's rubric.
- **`code-scanner`** maps to the `lattice-wiki:scanner` agent: `plugins/lattice-wiki/agents/scanner.md` (model: sonnet). The repo-walk / vault-diff work is owned by `lattice-wiki`, not `lattice-workflows`. "code-scanner" was a generic name in the source.
- **`using-workflows`** intentionally omits `model:` — it runs inside the caller's main loop, so declaring a model would override the loop's choice. The "every skill carries `model:`" framing is therefore not literally universal; the bootstrap skill is the deliberate exception.

The reshaped table lives on [[wiki/concepts/model-selection-per-skill]]. No further contradictions with other vault pages.

## Touches

- [[wiki/plugins/lattice-workflows/lattice-workflows]]
- [[wiki/plugins/lattice-workflows/patterns]]
- [[wiki/plugins/lattice-workflows/api]]
- [[wiki/concepts/model-selection-per-skill]]

## Decisions triggered

- None. Captured as a pattern bullet on [[wiki/plugins/lattice-workflows/patterns]] rather than an ADR (per ingest decision 2026-05-10).

## Where it's cited in this wiki

- [[wiki/concepts/model-selection-per-skill]]
- [[wiki/plugins/lattice-workflows/patterns]]
- [[wiki/plugins/lattice-workflows/api]]
- [[wiki/plugins/lattice-workflows/lattice-workflows]]
