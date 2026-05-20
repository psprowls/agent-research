# Phase 10: Subagent Context Completion — Context

**Gathered:** 2026-05-17
**Status:** Ready for planning
**Source:** Synthesized from spike 001 (`.planning/spikes/001-subagent-context-audit/README.md`, verdict VALIDATED) and spike-findings skill (`.claude/skills/spike-findings-deep-agents/references/subagent-context-injection.md`)

<domain>
## Phase Boundary

This phase closes the spike-001 gap between Phase 6's curated prompt fragments and the load-bearing context still missing from subagent `SystemMessage` composition.

**In scope:**
- Vendoring upstream `CLAUDE.md.template` (from `/Users/pat/Personal/lattice/dist/lattice-wiki/skills/lattice-wiki/scripts/vendor/assets/CLAUDE.md.template`) into `cores/prompt-sources/wiki-claude-md-template.md` so style/log fragment provenance resolves under the existing `test_provenance.py` invariant.
- Extracting four additional shared prompt fragments under `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/_fragments/`: `architecture_overview`, `style_rules`, `log_format`, `claude_md_disambiguation`.
- Adding `prompts/project_context.py::render_project_context(wiki_path)` that reads `wiki/CLAUDE.md` (or `AGENTS.md`) once at command entry and emits a compact rendered block covering the parsed `<!-- lattice-wiki:layout:start -->` block, style rules, and log format.
- Wiring the new fragments + the project-context block into `commands/scan.py`, `commands/lint.py`, and `commands/ingest.py` for the scanner / linter-3-group / ingestor subagents.
- Snapshot tests (syrupy) on assembled system-prompt strings, including a missing-`CLAUDE.md` degradation case.
- Re-running the Phase 6 divergence eval against the recorded baseline to confirm no regression.

**Out of scope:**
- Migrating subagent dispatch from the custom `cores/subagent-runtime/pool.py::SubagentPool` to `deepagents.SubAgentMiddleware` (any virtual-filesystem / read-on-demand approach). That is a separate architectural decision.
- Adding a `read_skill_doc()` or similar on-demand tool to subagents (wrong fit for the current single-turn `ainvoke` dispatch).
- Updating the librarian or synthesizer prompts beyond adding `style_rules` to the librarian (their context comes from the pages they read; layout injection adds noise without value).
- Re-anchoring `frontmatter_rules.py` to `wiki/CLAUDE.md` (it stays anchored to `cores/prompt-sources/agents/ingestor.md`; the wiki-side frontmatter list is delivered through `render_project_context()`).
- Bumping `cores/prompt-sources/SOURCE-COMMIT`; new fragments anchor to the current value of that file.

</domain>

<decisions>
## Implementation Decisions

### Architecture (LOCKED)

- Dispatch primitive stays as `cores/subagent-runtime/pool.py::SubagentPool` with raw `llm.ainvoke([SystemMessage, HumanMessage])`. **Do not introduce `deepagents.SubAgentMiddleware`** or any tool-loop wrapping. Reason: spike 001 confirmed `deepagents` is not imported anywhere in `agents/` or `cores/`; a migration is its own decision.
- Subagent context is delivered through (a) static curated fragments in `prompts/_fragments/` and (b) a project-context block rendered from `wiki/CLAUDE.md` at command entry — **not** through full SKILL.md injection (signal-to-noise is poor, ~half is user-facing/meta).

### Fragment curation (LOCKED)

- Every new fragment carries the standard 3-line provenance header: `# Source:`, `# Anchor:`, `# Source-commit:`. The `# Source:` path must start with `cores/prompt-sources/` and resolve on disk (enforced by `agents/graph-wiki-agent/tests/prompts/test_provenance.py`). Anchor format matches existing fragments (e.g. `## Architecture (L34-L69)`). Source-commit = current value of `cores/prompt-sources/SOURCE-COMMIT` (= `ef05d991a9ab1ea12b1bc7ebc1fb20ba70074030` as of 2026-05-17).
- **Vendoring decision (LOCKED):** The upstream lattice-wiki ships a `CLAUDE.md.template` (159 lines, source: `/Users/pat/Personal/lattice/dist/lattice-wiki/skills/lattice-wiki/scripts/vendor/assets/CLAUDE.md.template`) that is the canonical source for the project-pinned `lattice/wiki/CLAUDE.md`. Vendor it into `cores/prompt-sources/wiki-claude-md-template.md` (matching the existing SKILL.md vendoring pattern). Anchor `style_rules.py` and `log_format.py` to the vendored file. This preserves the `test_provenance.py` invariant without test changes.
- Four fragments are extracted:
  - `architecture_overview.py` ← `cores/prompt-sources/SKILL.md §Architecture L34-69` (~600 tokens, compact rewrite — keep the vault tree + conditional-containers note + "code is source of truth"; drop user-facing prose).
  - `style_rules.py` ← `cores/prompt-sources/wiki-claude-md-template.md §Style L153-159` (after vendoring) (~150 tokens).
  - `log_format.py` ← `cores/prompt-sources/wiki-claude-md-template.md §Log format L124-133` (after vendoring) (~120 tokens).
  - `claude_md_disambiguation.py` ← `cores/prompt-sources/SKILL.md §Cross-tool compatibility L141` (~80 tokens).

### Project-context renderer (LOCKED)

- New module: `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/project_context.py`.
- Function signature: `render_project_context(wiki_path: Path) -> str`. Pure — no LLM calls, no network, no mutation.
- Reads `wiki/CLAUDE.md` if present; falls back to `AGENTS.md`; returns `""` if neither exists. Caller passes the empty string through to prompt builders unchanged.
- Uses existing `vault_io.layout_io.read_layout()` for the layout block (do not write a bespoke YAML parser). Style and log-format sections are grabbed by markdown section walk (simple heading-based extraction).
- Output is deterministic (stable container ordering) so snapshot tests are stable.

### Wiring (LOCKED)

- `commands/scan.py`, `commands/lint.py`, `commands/ingest.py` each call `render_project_context(wiki)` once at command entry (where `wiki` is already resolved by existing setup code) and pass the result as a `project_context: str = ""` kwarg into the relevant prompt-builder functions.
- Prompt-builder functions in `prompts/scanner.py`, `prompts/linter.py`, `prompts/ingestor.py` accept the optional `project_context` and prepend it to their composed system-prompt string (after the role line, before `IRON_RULES`).
- Librarian gets `STYLE_RULES` only; it does **not** receive the project-context block.
- Synthesizer and code-reader prompts are unchanged in this phase.

### Testing (LOCKED)

- Use `syrupy` (already in the stack) for snapshot tests on assembled system-prompt strings.
- Snapshot coverage per subagent: (a) prompt with project context present, (b) prompt without project context. Plus one explicit fixture test: missing `wiki/CLAUDE.md` returns empty string and the prompt builder still produces a valid non-empty prompt without crashing.
- Re-run the Phase 6 divergence eval (`cores/eval-harness` baseline) before and after wiring; no regression allowed without explicit `--accept-divergence-baseline`.

### Token budget (LOCKED)

- Added context per subagent role stays within +1,500 tokens above the pre-Phase-10 baseline. Measured via syrupy snapshot string length / 4 (the project's rule-of-thumb tokenizer; same as used elsewhere). Combined target lands in the 800-1,200 range.

### Claude's Discretion

- Exact wording of the four extracted fragments (compact rewrites versus verbatim copies). Constraint: preserve all load-bearing rules from the anchored source range; trim prose without changing meaning.
- Exact layout of the rendered project-context block (heading levels, bullet style). Constraint: deterministic ordering, ~30 lines or less.
- Test file placement (per-subagent vs. one combined test module) and snapshot naming. Constraint: snapshot files live alongside their test module per syrupy convention.
- Whether to inject `project_context` as a keyword argument on the prompt builders versus a thread-local / context-var. Recommendation in spike report: keyword argument (explicit beats implicit here).
- How to detect / report the size delta as part of the test suite — could be a separate assertion or a derived snapshot. Constraint: the +1,500-token ceiling must be enforced *somewhere* in CI.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Spike report (authoritative source for this phase)

- `.planning/spikes/001-subagent-context-audit/README.md` — spike report (VALIDATED). Full inventory, token cost estimates, strategy comparison, recommended next-step scope.
- `.claude/skills/spike-findings-deep-agents/references/subagent-context-injection.md` — implementation blueprint distilled from the spike. Step-by-step build recipe; this is the spec for the work.
- `.planning/spikes/MANIFEST.md` — spike manifest with phase requirements.
- `.planning/spikes/CONVENTIONS.md` — spike-derived conventions (provenance headers, degrade gracefully, syrupy for prompt snapshots).

### Original prompt sources (anchors)

- `cores/prompt-sources/SKILL.md` — canonical lattice-wiki SKILL.md. Anchors for `architecture_overview` (L34-69), `claude_md_disambiguation` (L141), `iron_rules` (already extracted, L193-201), `page_categories` (already extracted, L143-155).
- `cores/prompt-sources/wiki-claude-md-template.md` — **vendored in this phase** from `/Users/pat/Personal/lattice/dist/lattice-wiki/skills/lattice-wiki/scripts/vendor/assets/CLAUDE.md.template`. Canonical upstream template for project-pinned `wiki/CLAUDE.md` files. Anchors for `style_rules` (L153-159) and `log_format` (L124-133).
- `lattice/wiki/CLAUDE.md` — this repo's *project-pinned* wiki schema (rendered from the upstream template plus the layout block). Read at runtime by `render_project_context()` for project-specific layout + style + log delivery to subagents. **Not** a fragment provenance anchor (the canonical source lives in the vendored template above).
- `cores/prompt-sources/SOURCE-COMMIT` — upstream commit hash (currently `ef05d991a9ab1ea12b1bc7ebc1fb20ba70074030`); new fragments record this in their provenance header.

### Existing port code (extends these patterns)

- `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/_fragments/iron_rules.py` — provenance-header pattern to copy.
- `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/_fragments/page_categories.py` — second example of the same pattern.
- `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/scanner.py`, `linter.py`, `ingestor.py`, `librarian.py` — current prompt-builder structure; new fragments slot into these.
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py`, `commands/lint.py`, `commands/ingest.py` — command entry points where `render_project_context()` will be called and threaded into prompt construction.
- `cores/vault-io/src/vault_io/layout_io.py::read_layout` — existing parser for the layout block; `render_project_context()` consumes its output.
- `cores/subagent-runtime/src/subagent_runtime/pool.py::SubagentPool` — the dispatch primitive (read-only for this phase; not modified).
- `cores/eval-harness/src/eval_harness/divergence/` — divergence eval modules invoked for the regression gate.

### Phase 6 baseline (the work this extends)

- `.planning/phases/06-prompt-content-port-divergence-eval/` — Phase 6 directory; the divergence baselines and the existing fragment provenance live here. Don't regenerate baselines unless the divergence eval intentionally shifts.

</canonical_refs>

<specifics>
## Specific Ideas

- Order of fragment extraction during execution: `architecture_overview` first (largest, drives the token-budget math), then `style_rules` + `log_format` + `claude_md_disambiguation` together (all small, share similar provenance shape), then `project_context.py` (depends on `style_rules` + `log_format` being defined for cross-references in its rendered output), then command wiring, then tests.
- Suggested commit shape (5-7 atomic commits, matching the existing Phase 6 cadence):
  0. **Vendor `CLAUDE.md.template` into `cores/prompt-sources/wiki-claude-md-template.md`** (one commit). Must land before style_rules / log_format fragments so their provenance resolves.
  1. Add `architecture_overview.py` + matching test snapshot update for any subagent that imports it.
  2. Add `style_rules.py`, `log_format.py`, `claude_md_disambiguation.py` (one commit; small fragments).
  3. Add `prompts/project_context.py` + unit tests (renderer with and without `wiki/CLAUDE.md`).
  4. Wire fragments into `prompts/scanner.py`, `prompts/linter.py`, `prompts/ingestor.py`, `prompts/librarian.py` (one commit; mechanical).
  5. Wire `render_project_context()` into `commands/scan.py`, `commands/lint.py`, `commands/ingest.py` (one commit).
  6. Snapshot tests + divergence-eval baseline re-run (one commit; or split if syrupy update is large).
- Token-budget enforcement: a single `test_token_budget.py` that loads the assembled prompt for each subagent and asserts `len(prompt) / 4 <= PRE_PHASE_10_BASELINE + 1500` is sufficient; record the baseline at test setup.
- Missing-`CLAUDE.md` test: create a tmp_path with no schema file, assert `render_project_context(tmp_path) == ""`, then assemble each subagent's prompt with `project_context=""` and assert it's a non-empty string (no crash).

</specifics>

<deferred>
## Deferred Ideas

- **Migrating to `deepagents.SubAgentMiddleware`** — would enable read-on-demand context via virtual filesystem. Spike 001 ruled this out for Phase 10. File as a follow-up only if the cost or signal-to-noise of Phase 10's solution turns out to be inadequate; v1.2+ at earliest.
- **`read_skill_doc(section)` tool** — wrong fit for single-turn `ainvoke`. Would require a ReAct loop wrap around every subagent. Reconsider only if dispatch migrates to deepagents.
- **Auto-bumping `cores/prompt-sources/SOURCE-COMMIT` and re-anchoring all fragments** — separate hygiene phase. Phase 10 anchors to the current value and leaves the bump for later.
- **Extracting the librarian's `STYLE_RULES` from the wiki-side `frontmatter` rules** — frontmatter required-fields-by-category are partially in `wiki/CLAUDE.md §Page frontmatter`; rendering those into `project_context` is deferred (the existing `frontmatter_rules.py` covers the ingest path).
- **Synthesizer / code_reader prompt updates** — those agents work from page content, not project layout; deferred until evidence shows otherwise.
- **Eval improvement: a dedicated "subagent-receives-context" metric** — beyond divergence-regression gating; track as v1.2 SWEEP-FU candidate.

</deferred>

<scope_fence>
## Scope Fence

**Locked decisions that constrain plan generation:**

1. **No deepagents migration.** Any plan that adds `from deepagents import …` or `SubAgentMiddleware` is out of scope and must be rejected by plan-checker.
2. **No new top-level dependencies.** All four new fragments live under `prompts/_fragments/`; `project_context.py` is a new module within the existing `prompts/` package. No `pyproject.toml` changes.
3. **Snapshot baselines are additive.** Phase 6's divergence baselines stay; new syrupy snapshots are new. Any plan that proposes regenerating Phase 6 baselines is out of scope.
4. **Token-budget ceiling is `+1,500 tokens per role`.** Plans that propose injecting larger blocks (e.g., full SKILL.md) are out of scope.
5. **Frontmatter rules stay anchored to ingestor.md.** Plans that re-anchor `frontmatter_rules.py` to `wiki/CLAUDE.md` are out of scope (deferred).
6. **No changes to `cores/subagent-runtime/pool.py`.** Read-only dependency for this phase.

</scope_fence>

---

*Phase: 10-subagent-context-completion*
*Context synthesized: 2026-05-17 from spike-001 (VALIDATED). Discuss-phase skipped — spike captured equivalent output.*
