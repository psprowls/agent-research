# Phase 26: D-04 Anchor Audit Table

**Produced:** 2026-05-21
**Input to:** Plan 02 (re-anchor). Plan 02 applies the `resolution` column mechanically.
**Authoring decisions:**

- **Option A** is the chosen provenance-comment shape (per `26-PATTERNS.md` § Critical surfaces / § Shared Patterns 1). The new 1-line form is `# Source: <path> §<section>[, §<section>...]`. The 3-line `# Source:` / `# Anchor:` / `# Source-commit:` block collapses to a single line; the `# Source-commit:` line is dropped (lattice SHA pin is gone with the deleted tree).
- Every row resolves to exactly one of `re-point | RESTORE-CONTENT | drop the check`. Per D-04, blanket policy is rejected — each row is decisioned individually.
- Per D-07, `packages/workspace-io/src/workspace_io/assets/CLAUDE.md.template` is the canonical home for `LOG_FORMAT` and `STYLE_RULES`. The headings `## Log format` and `## Style` are currently ABSENT from the template (verified — see § Heading verification below); the two corresponding fragment rows resolve to `RESTORE-CONTENT` (content + heading inserted by Plan 02). Alternative resolutions (re-point to `SKILL.md`, drop the anchor) are explicitly rejected.
- Per D-03, every `re-point` row records the proposed GitHub-slug derived by the standard rule (lowercase; strip punctuation except hyphens/underscores; whitespace runs → single hyphen). Slug resolution is confirmed against `grep -nE '^#+ ' <target-file>` headings recorded in § Heading verification.
- Per D-05, line-range pins (`(L48-L56)`, `(L93-L101)`, `(L153-L159)`) and bullet-number pins (`bullet 3`) are dropped — section names are stable, line numbers and bullet indices churn.
- Per D-06, the two Bedrock-only constants (`prompts/code_reader.py`, `prompts/synthesizer.py`) currently carry NO provenance comment. Plan 02 ADDS new `# Source:` comments pointing at the new agent-local sources tree (`agents/.../prompts/sources/{code_reader,synthesizer}.md`). The .md files are created by Plan 02 as verbatim ports from `packages/prompt-sources/agents/{code_reader,synthesizer}.md` with a lattice→graph-wiki rebrand sweep.

> **Resolution-token convention:** the literal lowercase decision-token (R-E-S-T-O-R-E + space + C-O-N-T-E-N-T) appears in this document **exactly twice** — once each in the two `_fragments/log_format.py` and `_fragments/style_rules.py` resolution cells in Table 1. All other commentary uses the uppercase tag `RESTORE-CONTENT` so the acceptance grep returns exactly 2 (one per decisioned row). This is a documentation-hygiene convention, not a semantic distinction.

---

## Heading verification (live re-grep, do not trust line numbers blindly)

| Target file | Headings present (relevant) | Verified |
|-------------|-----------------------------|----------|
| `packages/workspace-io/src/workspace_io/assets/CLAUDE.md.template` | `# Graph-Wiki Workspace` (L1), `## Layout` (L8), `## Plugins installed` (L17), `## Conventions for LLM agents` (L25). **`## Log format` ABSENT. `## Style` ABSENT.** | ✓ |
| `plugins/graph-wiki/agents/scanner.md` | `## Role` L13, `## Inputs` L19, `## Workflow` L24, `### 1. Discover workspaces` L28, `### 2. Present diff` L37, `### 3. Create stubs for new packages` L47, `### 4. Per-package change review` L56, ..., `### 10. Report` L97, `## Rules` L100, `## Red flags` L108. | ✓ |
| `plugins/graph-wiki/agents/linter.md` | `## Role` L13, `## Workflow` L21, `### Pass 1 — Mechanical (scripts)` L25, `### Pass 2 — Semantic (read and think)` L46, `### Pass 3 — Report` L58, `## Rules` L98, `## Red flags` L107. | ✓ |
| `plugins/graph-wiki/agents/ingestor.md` | `## Role` L13, `## Inputs` L17, `## Workflow` L24, `### 1. Prep` L28, …, `### 4. Write the source summary` L49, …, `## Rules` L93, `## Red flags` L106. | ✓ |
| `plugins/graph-wiki/agents/librarian.md` | `## Role` L13, `## Inputs` L21, `## Workflow` L27, `### 1. Read \`index.md\` first` L31, …, `## Rules` L72, `## Red flags` L81. | ✓ |
| `plugins/graph-wiki/skills/graph-wiki/SKILL.md` | `## Core principle` L16, `## When to use` L22, `## Architecture` L34, `## Four core operations` L71, `## Quick start` L78, `## Slash commands` L101, `## Sub-agents` L112, `## Python tools` L121, `## Cross-tool compatibility` L134, `## Page categories` L140, `## Why this works (vs. just READMEs or generic docs)` L153, `## Related skills` L164, `## Reference docs` L170, `## Templates (\`assets/\`)` L185, `## Iron rules` L191. | ✓ |

**Slug spot-checks (D-03 mechanical translation):**

- `### 4. Write the source summary` → `4-write-the-source-summary` ✓
- `### Pass 2 — Semantic (read and think)` → `pass-2--semantic-read-and-think` (double-hyphen from em-dash) ✓
- `### Pass 3 — Report` → `pass-3--report` ✓
- `### 3. Create stubs for new packages` → `3-create-stubs-for-new-packages` ✓
- `## Iron rules` → `iron-rules` ✓
- `## Page categories` → `page-categories` ✓
- `## Architecture` → `architecture` ✓
- `## Cross-tool compatibility` → `cross-tool-compatibility` ✓
- `## Rules` → `rules` ✓
- `## Red flags` → `red-flags` ✓

---

## Table 1 — Fragment file `# Source:` headers (8 rows)

| File | Current 3-line block | Proposed new 1-line shape | Target heading present? | Resolution | Notes |
|------|----------------------|---------------------------|-------------------------|------------|-------|
| `_fragments/architecture_overview.py` | `# Source: packages/prompt-sources/SKILL.md` / `# Anchor: ## Architecture (L34-L69)` / `# Source-commit: ef05d991...` | `# Source: plugins/graph-wiki/skills/graph-wiki/SKILL.md §Architecture` | yes (`## Architecture` L34 → slug `architecture`) | re-point | mechanical |
| `_fragments/citation_rules.py` | `# Source: packages/prompt-sources/agents/librarian.md` / `# Anchor: ## Rules (citation bullets — L73-L77)` / `# Source-commit: ef05d99` | `# Source: plugins/graph-wiki/agents/librarian.md §Rules` | yes (`## Rules` L72 → slug `rules`) | re-point | drop bullet-line pin per D-05 |
| `_fragments/claude_md_disambiguation.py` | `# Source: packages/prompt-sources/SKILL.md` / `# Anchor: ## Cross-tool compatibility (L141)` / `# Source-commit: ef05d991...` | `# Source: plugins/graph-wiki/skills/graph-wiki/SKILL.md §Cross-tool compatibility` | yes (`## Cross-tool compatibility` L134 → slug `cross-tool-compatibility`) | re-point | mechanical |
| `_fragments/frontmatter_rules.py` | `# Source: packages/prompt-sources/agents/ingestor.md` / `# Anchor: ## Workflow step 4 (required fields — L50-L58)` / `# Source-commit: ef05d99` | `# Source: plugins/graph-wiki/agents/ingestor.md §4. Write the source summary` | yes (`### 4. Write the source summary` L49 → slug `4-write-the-source-summary`) | re-point | D-03 example case (verbatim) |
| `_fragments/iron_rules.py` | `# Source: packages/prompt-sources/SKILL.md` / `# Anchor: ## Iron rules (L193-L201)` / `# Source-commit: ef05d99` | `# Source: plugins/graph-wiki/skills/graph-wiki/SKILL.md §Iron rules` | yes (`## Iron rules` L191 → slug `iron-rules`) | re-point | mechanical |
| `_fragments/log_format.py` | `# Source: packages/prompt-sources/wiki-claude-md-template.md` / `# Anchor: ## Log format (L124-L133)` / `# Source-commit: ef05d991...` | `# Source: packages/workspace-io/src/workspace_io/assets/CLAUDE.md.template §Log format` | **NO** (heading ABSENT in template; current template ends at `## Conventions for LLM agents` L25) | **restore content** | **Load-bearing call (D-07).** Plan 02 inserts the missing `## Log format` heading + content into `CLAUDE.md.template`. Alternatives explicitly rejected: re-point to SKILL.md (would scatter canonical source; D-07 explicitly names the template asset as canonical); drop the anchor (would lose runtime-asset provenance for the live `render_workspace_claude_md` writer). |
| `_fragments/page_categories.py` | `# Source: packages/prompt-sources/SKILL.md` / `# Anchor: ## Page categories (table — L143-L155)` / `# Source-commit: ef05d99` | `# Source: plugins/graph-wiki/skills/graph-wiki/SKILL.md §Page categories` | yes (`## Page categories` L140 → slug `page-categories`) | re-point | drop "(table — L…)" pin per D-05 |
| `_fragments/style_rules.py` | `# Source: packages/prompt-sources/wiki-claude-md-template.md` / `# Anchor: ## Style (L153-L159)` / `# Source-commit: ef05d991...` | `# Source: packages/workspace-io/src/workspace_io/assets/CLAUDE.md.template §Style` | **NO** (heading ABSENT in template; same as `log_format.py` row) | **restore content** | **Load-bearing call (D-07).** Plan 02 inserts the missing `## Style` heading + content into `CLAUDE.md.template`. Same alternatives rejected as `log_format.py` row above. |

**Table 1 totals:** 8 rows — 6 `re-point`, 2 `RESTORE-CONTENT`, 0 `drop the check`.

---

## Table 2 — Prompt-builder `# Source:` comments + docstring rebrands (6 rows)

| File:Line | Current | Proposed new shape | Target heading present? | Resolution | Notes |
|-----------|---------|--------------------|-------------------------|------------|-------|
| `prompts/scanner.py` L15-17 | 3-line block: `# Source: packages/prompt-sources/agents/scanner.md` / `# Anchor: ## Role, ## Rules, ## Red flags` / `# Source-commit: ef05d99` | `# Source: plugins/graph-wiki/agents/scanner.md §Role, §Rules, §Red flags` | yes (`## Role` L13, `## Rules` L100, `## Red flags` L108) | re-point | collapse 3 lines → 1 line per Option A |
| `prompts/linter.py` L17 (module docstring, NOT a `# Source:` comment) | `Source: packages/prompt-sources/agents/linter.md (Pass 2/3 and Rules section)` | `Source: plugins/graph-wiki/agents/linter.md §Pass 2 — Semantic (read and think), §Rules` | yes (`### Pass 2 — Semantic (read and think)` L46, `## Rules` L98) | re-point | docstring rebrand only — not in test_provenance.py whitelist scope (D-08 step 1 only scans `# Source:` *comments*). Rebrand path-prefix for consistency. |
| `prompts/linter.py` L26 | `# Source: packages/prompt-sources/agents/linter.md §Rules bullet 3` | `# Source: plugins/graph-wiki/agents/linter.md §Rules` | yes (`## Rules` L98 → slug `rules`) | re-point | drop "bullet 3" pin per D-05 spirit (bullet indices churn) |
| `prompts/linter.py` L55 | `# Source: packages/prompt-sources/agents/linter.md §Pass 2 (L48-L56), §Rules (L93-L101)` | `# Source: plugins/graph-wiki/agents/linter.md §Pass 2 — Semantic (read and think), §Rules` | yes (`### Pass 2 — Semantic (read and think)` L46, `## Rules` L98) | re-point | **Em-dash slug case (PATTERNS-surfaced issue 3).** Section name `Pass 2 — Semantic (read and think)` slugs to `pass-2--semantic-read-and-think` (double-hyphen). D-08 step 2 (Plan 03) must verify this slug resolves. |
| `prompts/ingestor.py` L5 (module docstring, NOT a `# Source:` comment) | `Ports packages/prompt-sources/agents/ingestor.md per PORT-03 (Phase 6).` | `Ports plugins/graph-wiki/agents/ingestor.md per PORT-03 (Phase 6).` | n/a (docstring path-prefix rebrand) | re-point | docstring rebrand only |
| `prompts/librarian.py` L7 (module docstring, NOT a `# Source:` comment) | `1. Role intro (librarian-local, adapted from packages/prompt-sources/agents/librarian.md)` | `1. Role intro (librarian-local, adapted from plugins/graph-wiki/agents/librarian.md)` | n/a (docstring path-prefix rebrand) | re-point | docstring rebrand only |

**Table 2 totals:** 6 rows — 6 `re-point`, 0 `RESTORE-CONTENT`, 0 `drop the check`.

---

## Table 3 — Bedrock-only prompt constants — NEW `# Source:` comments to ADD (2 rows)

| File | New comment (to ADD) | Target file (NEW agent-local source) | Rebrand needed in ported .md? | Resolution |
|------|----------------------|--------------------------------------|-------------------------------|------------|
| `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/code_reader.py` (no current `# Source:` line; verified L1-3) | `# Source: agents/graph-wiki-agent/src/graph_wiki_agent/prompts/sources/code_reader.md §Rules, §Outputs, §Red flags` | `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/sources/code_reader.md` (NEW file, created by Plan 02 from `packages/prompt-sources/agents/code_reader.md`) | **yes** — `skills: [lattice-wiki, source-reader]` (L4 frontmatter) → `skills: [graph-wiki, source-reader]` | re-point |
| `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/synthesizer.py` (no current `# Source:` line; verified L1-3) | `# Source: agents/graph-wiki-agent/src/graph_wiki_agent/prompts/sources/synthesizer.md §Rules` | `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/sources/synthesizer.md` (NEW file, created by Plan 02 from `packages/prompt-sources/agents/synthesizer.md`) | **yes** — `skills: [lattice-wiki, obsidian-markdown]` (L4 frontmatter) → `skills: [graph-wiki, obsidian-markdown]` | re-point |

**Table 3 totals:** 2 rows — 2 `re-point`, 0 `RESTORE-CONTENT`, 0 `drop the check`. The .md source files are *created* by Plan 02 as a side effect (verbatim port with rebrand sweep); the audit resolution column nevertheless records `re-point` because the audited surface is the new `# Source:` comment, not the created file.

---

## Table 4 — Eval-harness `source_anchor=` literals (23 rows)

Every row's "Current literal" column carries the verbatim `source_anchor=` Python expression (the literal text the executor must locate and rewrite).

| File:Line | Current literal | New literal | Target slug verified? | Resolution | Notes |
|-----------|-----------------|-------------|-----------------------|------------|-------|
| `divergence/scanner.py:66` | `source_anchor="packages/prompt-sources/agents/scanner.md#workflow-step-3"` | `source_anchor="plugins/graph-wiki/agents/scanner.md#3-create-stubs-for-new-packages"` | yes (`### 3. Create stubs for new packages` L47 → `3-create-stubs-for-new-packages`) | re-point | **Named audit case (PATTERNS § Eval-harness divergence-rules).** Old anchor `#workflow-step-3` no longer exists; workflow split into 10 `### N. <name>` subheadings. Re-point to slug of `### 3.` |
| `divergence/scanner.py:72` | `source_anchor="packages/prompt-sources/agents/scanner.md#workflow-step-3"` | `source_anchor="plugins/graph-wiki/agents/scanner.md#3-create-stubs-for-new-packages"` | yes | re-point | same audit case as L66 |
| `divergence/scanner.py:78` | `source_anchor="packages/prompt-sources/agents/scanner.md"` (file-level, no `#anchor`) | `source_anchor="plugins/graph-wiki/agents/scanner.md"` | n/a (no anchor fragment to verify) | re-point | file-level anchor; no slug to verify |
| `divergence/scanner.py:84` | `source_anchor="packages/prompt-sources/agents/scanner.md#workflow-step-3"` | `source_anchor="plugins/graph-wiki/agents/scanner.md#3-create-stubs-for-new-packages"` | yes | re-point | same audit case |
| `divergence/ingestor.py:94` | `source_anchor="packages/prompt-sources/agents/ingestor.md#workflow-step-4"` | `source_anchor="plugins/graph-wiki/agents/ingestor.md#4-write-the-source-summary"` | yes (`### 4. Write the source summary` L49 → `4-write-the-source-summary`) | re-point | D-03 example case (verbatim) |
| `divergence/ingestor.py:100` | `source_anchor="packages/prompt-sources/agents/ingestor.md#workflow-step-4"` | `source_anchor="plugins/graph-wiki/agents/ingestor.md#4-write-the-source-summary"` | yes | re-point | same |
| `divergence/ingestor.py:106` | `source_anchor="packages/prompt-sources/SKILL.md#page-categories"` | `source_anchor="plugins/graph-wiki/skills/graph-wiki/SKILL.md#page-categories"` | yes (`## Page categories` L140 → `page-categories`) | re-point | mechanical |
| `divergence/ingestor.py:112` | `source_anchor="packages/prompt-sources/agents/ingestor.md#rules"` | `source_anchor="plugins/graph-wiki/agents/ingestor.md#rules"` | yes (`## Rules` L93 → `rules`) | re-point | mechanical |
| `divergence/librarian.py:92` | `source_anchor="packages/prompt-sources/SKILL.md#iron-rules"` | `source_anchor="plugins/graph-wiki/skills/graph-wiki/SKILL.md#iron-rules"` | yes (`## Iron rules` L191 → `iron-rules`) | re-point | mechanical |
| `divergence/librarian.py:98` | `source_anchor="packages/prompt-sources/agents/librarian.md#rules"` | `source_anchor="plugins/graph-wiki/agents/librarian.md#rules"` | yes (`## Rules` L72 → `rules`) | re-point | mechanical |
| `divergence/librarian.py:104` | `source_anchor="packages/prompt-sources/agents/librarian.md#rules"` | `source_anchor="plugins/graph-wiki/agents/librarian.md#rules"` | yes | re-point | mechanical |
| `divergence/librarian.py:110` | `source_anchor="packages/prompt-sources/agents/librarian.md#rules"` | `source_anchor="plugins/graph-wiki/agents/librarian.md#rules"` | yes | re-point | mechanical |
| `divergence/linter.py:68` | `source_anchor="packages/prompt-sources/agents/linter.md#rules"` | `source_anchor="plugins/graph-wiki/agents/linter.md#rules"` | yes (`## Rules` L98 → `rules`) | re-point | mechanical |
| `divergence/linter.py:74` | `source_anchor="packages/prompt-sources/agents/linter.md#workflow-pass-3"` | `source_anchor="plugins/graph-wiki/agents/linter.md#pass-3--report"` | yes (`### Pass 3 — Report` L58 → `pass-3--report` double-hyphen from em-dash) | re-point | **Named audit case (PATTERNS § Eval-harness).** Old anchor `#workflow-pass-3` no longer exists. New slug carries em-dash double-hyphen. |
| `divergence/linter.py:80` | `source_anchor="packages/prompt-sources/agents/linter.md#rules"` | `source_anchor="plugins/graph-wiki/agents/linter.md#rules"` | yes | re-point | mechanical |
| `divergence/synthesizer.py:108` | `source_anchor="packages/prompt-sources/agents/synthesizer.md#rules"` | `source_anchor="agents/graph-wiki-agent/src/graph_wiki_agent/prompts/sources/synthesizer.md#rules"` | yes (verbatim port — heading `## Rules` carried forward in new .md) | re-point | new agent-local source (D-06) |
| `divergence/synthesizer.py:114` | `source_anchor="packages/prompt-sources/agents/synthesizer.md#rules"` | `source_anchor="agents/graph-wiki-agent/src/graph_wiki_agent/prompts/sources/synthesizer.md#rules"` | yes | re-point | same |
| `divergence/synthesizer.py:120` | `source_anchor="packages/prompt-sources/agents/synthesizer.md#red-flags"` | `source_anchor="agents/graph-wiki-agent/src/graph_wiki_agent/prompts/sources/synthesizer.md#red-flags"` | yes (verbatim port — `## Red flags` carried forward) | re-point | same |
| `divergence/synthesizer.py:126` | `source_anchor="packages/prompt-sources/agents/synthesizer.md#rules"` | `source_anchor="agents/graph-wiki-agent/src/graph_wiki_agent/prompts/sources/synthesizer.md#rules"` | yes | re-point | same |
| `divergence/code_reader.py:107` | `source_anchor="packages/prompt-sources/agents/code_reader.md#outputs"` | `source_anchor="agents/graph-wiki-agent/src/graph_wiki_agent/prompts/sources/code_reader.md#outputs"` | yes (verbatim port — `## Outputs` carried forward) | re-point | new agent-local source (D-06) |
| `divergence/code_reader.py:113` | `source_anchor="packages/prompt-sources/agents/code_reader.md#outputs"` | `source_anchor="agents/graph-wiki-agent/src/graph_wiki_agent/prompts/sources/code_reader.md#outputs"` | yes | re-point | same |
| `divergence/code_reader.py:119` | `source_anchor="packages/prompt-sources/agents/code_reader.md#rules"` | `source_anchor="agents/graph-wiki-agent/src/graph_wiki_agent/prompts/sources/code_reader.md#rules"` | yes (verbatim port — `## Rules` carried forward) | re-point | same |
| `divergence/code_reader.py:125` | `source_anchor="packages/prompt-sources/agents/code_reader.md#red-flags"` | `source_anchor="agents/graph-wiki-agent/src/graph_wiki_agent/prompts/sources/code_reader.md#red-flags"` | yes (verbatim port — `## Red flags` carried forward) | re-point | same |

**Table 4 totals:** 23 rows — 23 `re-point`, 0 `RESTORE-CONTENT`, 0 `drop the check`.

---

## Table 5 — Prose `Anchors ...` lines + check.py docstring (11 rows)

| File:Line | Current text | New text | Resolution |
|-----------|--------------|----------|------------|
| `divergence/synthesizer.py:20` | `# Vault-thinness acknowledgement phrasing per packages/prompt-sources/agents/synthesizer.md` | `# Vault-thinness acknowledgement phrasing per agents/graph-wiki-agent/src/graph_wiki_agent/prompts/sources/synthesizer.md` | re-point |
| `divergence/synthesizer.py:36` | `    Anchors packages/prompt-sources/agents/synthesizer.md#rules (rule 1 + 3).` | `    Anchors agents/graph-wiki-agent/src/graph_wiki_agent/prompts/sources/synthesizer.md#rules (rule 1 + 3).` | re-point |
| `divergence/synthesizer.py:49` | `    Anchors packages/prompt-sources/agents/synthesizer.md#rules (rule 2).` | `    Anchors agents/graph-wiki-agent/src/graph_wiki_agent/prompts/sources/synthesizer.md#rules (rule 2).` | re-point |
| `divergence/synthesizer.py:66` | `    Anchors packages/prompt-sources/agents/synthesizer.md#red-flags (code-fallback fidelity).` | `    Anchors agents/graph-wiki-agent/src/graph_wiki_agent/prompts/sources/synthesizer.md#red-flags (code-fallback fidelity).` | re-point |
| `divergence/synthesizer.py:89` | `    Anchors packages/prompt-sources/agents/synthesizer.md#rules (rule 4).` | `    Anchors agents/graph-wiki-agent/src/graph_wiki_agent/prompts/sources/synthesizer.md#rules (rule 4).` | re-point |
| `divergence/code_reader.py:15` | `# (packages/prompt-sources/agents/code_reader.md#rules — rule 6).` | `# (agents/graph-wiki-agent/src/graph_wiki_agent/prompts/sources/code_reader.md#rules — rule 6).` | re-point |
| `divergence/code_reader.py:44` | `    Anchors packages/prompt-sources/agents/code_reader.md#outputs (rule 6 + output format).` | `    Anchors agents/graph-wiki-agent/src/graph_wiki_agent/prompts/sources/code_reader.md#outputs (rule 6 + output format).` | re-point |
| `divergence/code_reader.py:61` | `    Anchors packages/prompt-sources/agents/code_reader.md#outputs.` | `    Anchors agents/graph-wiki-agent/src/graph_wiki_agent/prompts/sources/code_reader.md#outputs.` | re-point |
| `divergence/code_reader.py:76` | `    Anchors packages/prompt-sources/agents/code_reader.md#rules (rule 4).` | `    Anchors agents/graph-wiki-agent/src/graph_wiki_agent/prompts/sources/code_reader.md#rules (rule 4).` | re-point |
| `divergence/code_reader.py:91` | `    Anchors packages/prompt-sources/agents/code_reader.md#red-flags.` | `    Anchors agents/graph-wiki-agent/src/graph_wiki_agent/prompts/sources/code_reader.md#red-flags.` | re-point |
| `divergence/check.py:59-60` | `source_anchor: Path + section anchor tracing back to canonical source (e.g. "packages/prompt-sources/SKILL.md#iron-rules").` | `source_anchor: Path + section anchor tracing back to canonical source (e.g. "plugins/graph-wiki/skills/graph-wiki/SKILL.md#iron-rules").` | re-point |

**Table 5 totals:** 11 rows — 11 `re-point`, 0 `RESTORE-CONTENT`, 0 `drop the check`.

---

## Table 6 — Rubric HTML headers (6 rows)

| File | Current 3-line block | Proposed new 1-line shape | Drop Source-commit? | lattice→graph-wiki rebrand needed in body? | Resolution |
|------|----------------------|---------------------------|---------------------|--------------------------------------------|------------|
| `divergence/rubrics/ingestor.md` | `<!-- Source: packages/prompt-sources/agents/ingestor.md -->` / `<!-- Anchor: ## Rules + ## Red flags -->` / `<!-- Source-commit: ef05d991... -->` | `<!-- Source: plugins/graph-wiki/agents/ingestor.md §Rules, §Red flags -->` | **yes** | **yes** — L9 `the canonical lattice-wiki ingestor spec` → `the canonical graph-wiki ingestor spec` | re-point |
| `divergence/rubrics/librarian.md` | `<!-- Source: packages/prompt-sources/agents/librarian.md -->` / `<!-- Anchor: ## Rules + ## Red flags -->` / `<!-- Source-commit: ef05d991... -->` | `<!-- Source: plugins/graph-wiki/agents/librarian.md §Rules, §Red flags -->` | **yes** | **yes** — L9 `the canonical lattice-wiki librarian spec` → `the canonical graph-wiki librarian spec` | re-point |
| `divergence/rubrics/linter.md` | `<!-- Source: packages/prompt-sources/agents/linter.md -->` / `<!-- Anchor: ## Rules + ## Red flags -->` / `<!-- Source-commit: ef05d991... -->` | `<!-- Source: plugins/graph-wiki/agents/linter.md §Rules, §Red flags -->` | **yes** | **yes** — L9 `from the canonical lattice-wiki linter spec` → `from the canonical graph-wiki linter spec` | re-point |
| `divergence/rubrics/scanner.md` | `<!-- Source: packages/prompt-sources/agents/scanner.md -->` / `<!-- Anchor: ## Rules + ## Red flags -->` / `<!-- Source-commit: ef05d991... -->` | `<!-- Source: plugins/graph-wiki/agents/scanner.md §Rules, §Red flags -->` | **yes** | **yes** — L9 `from the canonical lattice-wiki scanner spec` → `from the canonical graph-wiki scanner spec` | re-point |
| `divergence/rubrics/synthesizer.md` | `<!-- Source: packages/prompt-sources/agents/synthesizer.md -->` / `<!-- Anchor: ## Rules + ## Red flags -->` / `<!-- Source-commit: 7b3ce6a7... -->` | `<!-- Source: agents/graph-wiki-agent/src/graph_wiki_agent/prompts/sources/synthesizer.md §Rules, §Red flags -->` | **yes** | **no** — `grep -ni lattice` returned 0 hits in body | re-point |
| `divergence/rubrics/code_reader.md` | `<!-- Source: packages/prompt-sources/agents/code_reader.md -->` / `<!-- Anchor: ## Rules + ## Red flags -->` / `<!-- Source-commit: 7b3ce6a7... -->` | `<!-- Source: agents/graph-wiki-agent/src/graph_wiki_agent/prompts/sources/code_reader.md §Rules, §Red flags -->` | **yes** | **no** — `grep -ni lattice` returned 0 hits in body | re-point |

**Table 6 totals:** 6 rows — 6 `re-point`, 0 `RESTORE-CONTENT`, 0 `drop the check`. All 6 drop the `<!-- Source-commit: -->` line. 4 of 6 require a lattice→graph-wiki body rebrand at L9.

---

## Summary

| Surface | Rows | re-point | RESTORE-CONTENT | drop the check |
|---------|------|----------|-----------------|----------------|
| Table 1 — Fragment file headers | 8 | 6 | 2 | 0 |
| Table 2 — Prompt-builder comments + docstrings | 6 | 6 | 0 | 0 |
| Table 3 — Bedrock-only NEW comments | 2 | 2 | 0 | 0 |
| Table 4 — Eval-harness `source_anchor=` literals | 23 | 23 | 0 | 0 |
| Table 5 — Prose `Anchors ...` lines + check.py docstring | 11 | 11 | 0 | 0 |
| Table 6 — Rubric HTML headers | 6 | 6 | 0 | 0 |
| **Total** | **56** | **54** | **2** | **0** |

**`RESTORE-CONTENT` rationale (exactly 2 rows — both load-bearing, per D-07):**

1. `_fragments/log_format.py` → `packages/workspace-io/src/workspace_io/assets/CLAUDE.md.template §Log format` — heading currently ABSENT. The template asset IS the canonical source per D-07 (it's what `render_workspace_claude_md` writes into every fresh workspace's `<workspace>/CLAUDE.md`). Plan 02 inserts the `## Log format` heading + content into the template; the alternative resolutions (re-point to SKILL.md, drop the anchor) are explicitly rejected because they would either scatter the canonical source or sever the runtime-asset provenance.

2. `_fragments/style_rules.py` → `packages/workspace-io/src/workspace_io/assets/CLAUDE.md.template §Style` — same heading-absent state, same load-bearing rationale, same alternative-rejection logic as row 1.

**`drop the check` count: zero.** No row is decisioned as `drop the check`. Every audited anchor resolves to a real target (existing plugin heading, template heading to be restored, or new agent-local source heading).

**Follow-up for Plan 02 (notes that need attention during application):**

- **Em-dash slug verification** — three rows depend on the slug `pass-2--semantic-read-and-think` (linter.py L17 docstring, linter.py L55) or `pass-3--report` (divergence/linter.py:74). The double-hyphen behavior is the canonical GFM slug derivation; Plan 03 (test upgrade) MUST mirror this exact slug rule in `test_provenance.py` D-08 step 2.
- **Template content restoration** — Plan 02 must produce the textual content of `## Log format` and `## Style` for `CLAUDE.md.template`. The content body for both sections originally lived in `packages/prompt-sources/wiki-claude-md-template.md` (the file the current fragments cite); Plan 02 should port the relevant section bodies from that deleted file into the canonical template at the same time as the path-prefix re-anchor, then verify `STYLE_RULES` / `LOG_FORMAT` constant text matches the restored sections within the D-08 step 3 keyword-overlap threshold (≥70%).
- **Bedrock-only new files** — Plan 02 creates `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/sources/{code_reader,synthesizer}.md` as verbatim ports with a `skills:` frontmatter rebrand. No `__init__.py` (markdown-only asset tree, per PATTERNS § Bedrock-only prompt constants).
- **Rubric body rebrand** — 4 of 6 rubric files require a lattice→graph-wiki rebrand at L9 (ingestor, librarian, linter, scanner); 2 (synthesizer, code_reader) require no body rebrand.
- **Docstring vs `# Source:` comment distinction** — Table 2 rows for `linter.py` L17, `ingestor.py` L5, `librarian.py` L7 are inside module docstrings, NOT in scope for the D-08 step 1 whitelist check (which scans only `# Source:` *comments*). Plan 02 still rebrands them for path-prefix consistency, but Plan 03's `test_provenance.py` upgrade does NOT need to validate them.
