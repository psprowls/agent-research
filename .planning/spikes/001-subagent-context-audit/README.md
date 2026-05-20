---
spike: 001
name: subagent-context-audit
type: standard
validates: "Given current prompts/*.py and cores/prompt-sources/SKILL.md + lattice/wiki/CLAUDE.md, when compared side-by-side and weighed against Bedrock fan-out cost, then we can identify dropped load-bearing chunks, confirm wiki CLAUDE.md handling, and recommend an injection strategy"
verdict: VALIDATED
related: []
tags: [context, prompts, audit, subagents, bedrock]
---

# Spike 001: Subagent Context Audit

## What This Validates

**Given** the current Python port's subagent system prompts (`agents/graph-wiki-agent/src/graph_wiki_agent/prompts/*.py`) and the original sources (`cores/prompt-sources/SKILL.md`, `lattice/wiki/CLAUDE.md`),
**When** they are inventoried side-by-side and the cost of injecting missing context is estimated against Bedrock fan-out,
**Then** we can name the load-bearing chunks that were dropped, confirm whether `wiki/CLAUDE.md` reaches subagent context, and recommend an injection strategy with a clear next step.

This is an analytical spike — no code changes, deliverable is this report.

## Research

### Architectural finding (critical)

Before scoring strategies, one architectural fact reshapes the option space:

```
$ grep -rln "from deepagents\|import deepagents\|create_deep_agent" agents/ cores/
cores/subagent-runtime/src/subagent_runtime/pool.py  (comments only — bug references)
```

**`deepagents` is not imported anywhere in agent or core code.** Subagent dispatch is done by a custom `SubagentPool` (`cores/subagent-runtime/src/subagent_runtime/pool.py`) — an async semaphore-bound fan-out that calls `llm.ainvoke([SystemMessage(...), HumanMessage(...)])` directly. There is no `SubAgentMiddleware`, no virtual filesystem, no tool-loop ReAct wrapper around each subagent.

Consequence: the strategy initially floated as "deepagents virtual FS read-on-demand" is **not available** in the current architecture. A read-on-demand option would require a separate architectural decision to migrate from the custom pool to `create_async_deep_agent`. That is a much larger discussion than fixing context loading.

### Inventory: cores/prompt-sources/SKILL.md (201 lines)

Section map and what is extracted into `prompts/_fragments/`:

| SKILL.md section | Lines | Extracted into fragments? | Load-bearing for subagents? |
|---|---|---|---|
| Core principle | 16-20 | No | Marginal — motivational |
| When to use | 22-32 | No | No (user-facing) |
| Architecture (vault layout + conditional containers) | 34-69 | **No** | **Yes** — scanner/linter/ingestor decisions all hinge on layout |
| Four core operations | 71-76 | No | No (orchestrator-level) |
| Quick start (CLI usage) | 78-99 | No | No (user-facing) |
| Slash commands | 101-110 | No | No (host-facing) |
| Sub-agents (the list) | 112-119 | No | No (meta) |
| Python tools (scripts/) | 121-135 | No | Partial — scanner/linter call out to scripts; references already inline in `cores/prompt-sources/agents/*.md` |
| Cross-tool compatibility (incl. "root CLAUDE.md ≠ wiki CLAUDE.md" note) | 137-141 | **No** | **Yes** — disambiguates the two CLAUDE.md files; subagents that read either need to know which is which |
| Page categories table | 143-155 | **Yes** → `page_categories.py` ✓ | Yes |
| Why this works | 157-166 | No | No |
| Related skills | 168-172 | No | No |
| Reference docs | 174-185 | No | Partial — but those docs aren't shipped in our port |
| Templates | 187-191 | No | No (assets not ported) |
| Iron rules | 193-201 | **Yes** → `iron_rules.py` ✓ | Yes |

**Verdict: two load-bearing chunks were dropped.** Architecture / vault layout (L34-69) and the cross-tool note disambiguating root vs. wiki `CLAUDE.md` (L141).

### Inventory: lattice/wiki/CLAUDE.md (192 lines)

This is the *project-specific* wiki schema. Sections:

| wiki/CLAUDE.md section | Lines | Reaches subagents today? | Load-bearing? |
|---|---|---|---|
| Where the wiki sits + Wiki structure (full tree) | 11-66 | No | **Yes** — duplicates SKILL.md Architecture but project-pinned |
| Page frontmatter (required fields) | 56-67 | Partial — `frontmatter_rules.py` covers required fields from ingestor.md, not from here | Yes |
| The four operations (project view) | 69-111 | Partial — agent-local rules approximate this | Yes |
| Iron rules | 113-122 | Yes — via `iron_rules.py` (slightly different wording but same intent) | Yes |
| Log format | 124-133 | **No** | **Yes** — every scan/ingest/lint appends to `log.md` |
| Tools | 135-147 | No | Partial — duplicates SKILL.md |
| Obsidian | 149-151 | No | No |
| Style (concise, cite, update `updated:`) | 153-159 | **No** | **Yes** — load-bearing for librarian and ingestor output quality |
| `<!-- lattice-wiki:layout:start -->` block | 161-191 | **No, but parsed as data** | **Yes — critical** — project-specific containers, classifications, vault dirs |

The layout block is the single most important piece of project-specific context the subagents currently *don't* see. It's parsed in `commands/scan.py:282-283` and `commands/lint.py:324` via `vault_io.layout_io.read_layout`, but the parsed result is used as *control flow data* (which directories to walk), never injected into a subagent `SystemMessage`.

### Confirmation: wiki/CLAUDE.md is data-only

Grep across `agents/` and `cores/`:

```
agents/graph-wiki-agent/src/graph_wiki_agent/commands/lint.py:324: layout = read_layout(wiki / "CLAUDE.md")
agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py:282-283: read_layout(wiki / schema_name)  # CLAUDE.md or AGENTS.md
```

No other reference. `prompts/*.py` files never read `CLAUDE.md` — confirmed data-only. Subagent system prompts cannot see the project's container pins, vault dirs, or `classification: skip` entries.

### Subagent prompt assemblies

How each subagent's `SystemMessage` is composed today:

| Subagent | Fragments used | Local rules source | Approx size |
|---|---|---|---|
| `ingestor` | IRON_RULES, PAGE_CATEGORIES, FRONTMATTER_RULES, CITATION_RULES | `cores/prompt-sources/agents/ingestor.md` (112 lines) | ~1,800 tokens |
| `librarian` | IRON_RULES, PAGE_CATEGORIES, CITATION_RULES | `librarian.md` (86 lines) | ~1,500 tokens |
| `linter` (×3 groups: page-quality, ADR-chain, stale-claims) | IRON_RULES only | `linter.md` (109 lines) plus per-group enumerations inline in `prompts/linter.py` | ~1,200 tokens each |
| `scanner` | IRON_RULES, FRONTMATTER_RULES | `scanner.md` (113 lines) | ~1,500 tokens |
| `synthesizer` / `code_reader` | imported into `query.py` but no fragments declared | various | ~1,000 tokens |

Dispatch path: each is passed to `llm.ainvoke([SystemMessage(content=…), HumanMessage(…)])` either directly or through `SubagentPool.run_all(...)`. No tool-loop, no FS, no on-demand reads.

### Token cost estimate (rule of thumb: 4 chars ≈ 1 token for English markdown)

Raw sizes:

```
SKILL.md            15,580 B → ~3,900 tokens
wiki/CLAUDE.md       8,961 B → ~2,240 tokens
lattice/CLAUDE.md    ~1,700 B → ~430 tokens (workspace-level, low value for subagents)
fragments combined   ~4,255 B → ~1,060 tokens (current baseline)
```

Per-invocation cost of injecting **full SKILL.md + full wiki/CLAUDE.md** beyond current baseline:

- **+6,140 tokens** per subagent system prompt.

Fan-out multipliers:

| Operation | Subagent calls per pass | Added tokens per pass |
|---|---|---|
| Lint | 3 (page-quality + ADR + stale-claims) × N batches. For one batch: 3 | +18,420 |
| Ingest | 1 ingestor + 5-15 page-update fan-outs (per ingestor.md workflow) | +30,700 to +98,240 |
| Scan | 1 scanner pass + per-package updates | +18,420 to +60,000 |
| Query (librarian) | 1 librarian + optional synthesizer/code-reader | +12,280 |

Cost on Bedrock. Per project memory ([[user_cost_optimization]] and [[project_wiki_setup]]) the fan-out tier is Qwen3-32B, synthesis tier Qwen3-80B. Using a representative Bedrock Qwen3-32B input rate of ≈ $0.00015–0.00020 per 1K input tokens:

| Op | Added tokens / pass | Added input cost / pass |
|---|---|---|
| Lint (1 batch) | 18,420 | ~$0.003 |
| Ingest (mid-range, 10 pages) | ~67K | ~$0.013 |
| Scan (10 packages) | ~40K | ~$0.008 |
| Query | ~12K | ~$0.002 |

**Verdict on cost: marginal in absolute dollars.** A lint pass adds about a third of a cent. The bigger penalty is *signal-to-noise* — half of SKILL.md (When to use, Quick start, Slash commands, Why this works, Related skills, Templates) is user-facing or meta and not useful in a subagent system prompt. Dumping it in dilutes the load-bearing rules.

## Strategy Comparison

| # | Strategy | What it does | Pros | Cons | Verdict |
|---|---|---|---|---|---|
| A | Full SKILL.md + full wiki/CLAUDE.md in every system prompt | Concat both files into every `SystemMessage` | Zero risk of missing context; closest to Claude Code behavior | ~6K tokens of which ~half is noise per call; dilutes attention; layered duplication across fan-out | Rejected — wasteful |
| B | deepagents virtual filesystem (read-on-demand) | Subagents call `read_file('SKILL.md')` when stuck | Pay tokens only when needed | **Not available** — current architecture uses custom `SubagentPool`, not deepagents `SubAgentMiddleware`. Migration is a separate decision. | Out of scope |
| C | Curated additions to `prompts/_fragments/` | Extract 2-3 more fragments: `ARCHITECTURE_OVERVIEW` (L34-69), `STYLE_RULES` (wiki/CLAUDE.md §Style), `LOG_FORMAT` (wiki/CLAUDE.md §Log format), `CLAUDE_MD_DISAMBIGUATION` (root vs wiki note) | Preserves curation discipline; per-role inclusion; provenance comments protect against drift | Hand-curation burden; static — does not capture *project-specific* layout pins | Necessary, not sufficient |
| D | Inject project-specific layout block + style as parsed data | At command entry, parse `wiki/CLAUDE.md`, render layout block + style section as ~30-line compact text, prepend to relevant subagents' `SystemMessage` | Project-specific layout reaches scanner/linter/ingestor (the ones who care); ~300-500 tokens; cheap | New boilerplate at each command entry; needs a small renderer | Necessary for scan/lint/ingest |
| E | Tool-call read on demand (`read_skill_doc(section)` tool) | Give each subagent a tool to fetch sections | Pays tokens only when needed | Current fan-out is single-turn `ainvoke` — no tool loop. Would need ReAct wrapper around each subagent → architectural change with marginal value over (C+D) | Wrong fit for this architecture |

**Recommendation: C + D combined.**

1. Extract these new shared fragments (each with the existing `# Source:` / `# Anchor:` / `# Source-commit:` header):
   - `architecture_overview.py` — anchor `SKILL.md §Architecture L34-69` (the vault layout tree + conditional-containers note). ~600 tokens.
   - `style_rules.py` — anchor `wiki/CLAUDE.md §Style L153-159`. ~150 tokens. Wire into ingestor and librarian.
   - `log_format.py` — anchor `wiki/CLAUDE.md §Log format L124-133`. ~120 tokens. Wire into scanner, ingestor, linter (anyone who appends to `log.md`).
   - `claude_md_disambiguation.py` — anchor `SKILL.md §Cross-tool compatibility L141`. ~80 tokens. Wire into linter and ingestor where vault↔code reasoning matters.

2. Add a helper, e.g. `prompts/project_context.py::render_project_context(wiki_path: Path) -> str`, that reads `wiki/CLAUDE.md` once at command entry and emits a compact block:
   ```
   ## Project layout (parsed from wiki/CLAUDE.md)
   - containers (vault_dir → classification):
     - agents → package (1 child)
     - cores → package (4 children)
     - eval, lattice, scripts, test-out → skip
   - workspace-level style: concise; cite [[wikilinks]] and `code-paths:line`; update `updated:` on touch.
   ```
   Inject as the first block of `SystemMessage.content` for scanner, linter, and ingestor (`librarian` benefits less — its context comes from pages it actually reads).

3. Token budget — keep added content under ~1,500 tokens per role versus current baseline. Combined C + D lands around +800-1,200 tokens, well within tolerance.

## Investigation Trail

1. Started by grepping for `SKILL.md` / `CLAUDE.md` references across `agents/` and `cores/` — confirmed only `iron_rules.py` and `page_categories.py` cite `SKILL.md` as their source, and only `lint.py` / `scan.py` read `wiki/CLAUDE.md` (as data).
2. Mapped each subagent's fragment imports and confirmed all dispatch through plain `llm.ainvoke([SystemMessage, HumanMessage])` patterns in `commands/*.py`.
3. **Surprise:** searched for `deepagents` imports — found none. The "virtual filesystem" strategy I'd originally floated (in the chat that triggered this spike) is not actionable without a separate migration. This reshaped the strategy table — option B was demoted from "complex but real" to "out of scope".
4. Sectioned both `SKILL.md` and `lattice/wiki/CLAUDE.md` by heading and scored each section's load-bearing status for subagents.
5. Computed byte sizes and converted to rough tokens (4 chars/token); estimated per-pass added cost for each operation; sanity-checked against Bedrock Qwen3-32B input pricing per project memory.
6. Compared five strategies (A through E) and converged on C + D as the natural extension of the existing curation pattern.

## Results

**Verdict: VALIDATED ✓**

- (1) Two load-bearing SKILL.md chunks dropped: **Architecture/vault-layout (L34-69)** and **root-vs-wiki CLAUDE.md disambiguation (L141)**. Additional gaps from `wiki/CLAUDE.md`: **Style rules**, **Log format**, and the **parsed layout block** (project-specific container pins).
- (2) `wiki/CLAUDE.md` is confirmed data-only — `read_layout()` consumers in `scan.py:282` and `lint.py:324`; never injected into any `SystemMessage`.
- (3) Bedrock cost of full injection is marginal (~$0.003-$0.013 per pass) but signal-to-noise is poor — half of `SKILL.md` is user-facing/meta and dilutes the load-bearing content.
- (4) Strategy comparison rules out (A) wasteful, (B) requires a separate deepagents migration decision, (E) wrong-shape for current single-turn dispatch. Recommendation is (C) + (D): extend the existing fragment curation **and** inject a small rendered project-context block from `wiki/CLAUDE.md` at command entry.
- (5) Next-step recommendation below.

### Surprises

- The agent dispatch primitive is custom (`SubagentPool`), not `deepagents`. The project's README and CLAUDE.md frame the stack as "deepagents + LangChain", but in practice only the `langchain` parts are used. Worth flagging — possibly relevant to other planning decisions.
- The `wiki/CLAUDE.md` style section ("be concise, cite aggressively, update `updated:` whenever you touch a page") is a high-signal-density chunk that's completely absent from subagent context. Cheap to add.

## Signal for the Build

Use:
- Continue the `prompts/_fragments/` pattern with provenance headers — it scales cleanly.
- Add a tiny `render_project_context()` renderer; keep it pure (no LLM calls).
- Wire the new context block only into subagents that need it (scanner, linter, ingestor). Librarian and synthesizer are fine as-is.

Avoid:
- Don't dump full `SKILL.md` — half is noise.
- Don't migrate to deepagents `SubAgentMiddleware` for this fix — it's a much larger decision.
- Don't add a `read_skill_doc()` tool — doesn't fit single-turn fan-out.

Watch out for:
- When `wiki/CLAUDE.md` is *missing* (or `AGENTS.md` is used instead in another tool host), the project-context renderer must degrade gracefully — emit a minimal block from defaults rather than crashing the command.
- Fragment provenance must stay current. If `cores/prompt-sources/SOURCE-COMMIT` advances, the new fragments need a re-anchor sweep.

## Recommended Next Step

**Phase: `wire-curated-context-into-subagents`** — small, well-scoped, no architectural change.

Scope (estimated 4-6 atomic commits):
1. New fragments under `prompts/_fragments/`: `architecture_overview.py`, `style_rules.py`, `log_format.py`, `claude_md_disambiguation.py` (with provenance headers).
2. New module `prompts/project_context.py` exporting `render_project_context(wiki_path: Path) -> str` that reads `wiki/CLAUDE.md` via existing `vault_io.layout_io.read_layout` plus a simple style/log section grabber.
3. Wire updates in `prompts/scanner.py`, `prompts/linter.py`, `prompts/ingestor.py`: include the new fragments where appropriate; accept an optional injected project-context string at prompt-build time.
4. Update `commands/scan.py`, `commands/lint.py`, `commands/ingest.py` to call `render_project_context()` once at entry and pass the result into the relevant prompt builders.
5. Tests: snapshot tests on assembled `SystemMessage` strings (using `syrupy`) plus a missing-`CLAUDE.md` degradation test.
6. Optional: a tiny eval check that compares a recorded librarian/linter output before and after — the project's `cores/eval-harness` already supports this pattern.

Suggested route: `/gsd-plan-phase` with the spike as input. Findings here are enough to skip ahead from `/gsd-discuss-phase`.
