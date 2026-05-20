# Phase 6: Prompt Content Port + Divergence Eval - Context

**Gathered:** 2026-05-15
**Status:** Ready for planning

<domain>
## Phase Boundary

Port `lattice-wiki`'s canonical SKILL.md + per-role agent prompts into `graph-wiki-agent`'s agent system prompts (librarian, ingestor, linter, scanner) under a new `prompts/` module with provenance comments, and add a divergence-detection eval metric (hybrid programmatic + LLM-judge) that runs against the Phase 4 fixture corpus and gates regressions against a recorded baseline.

In scope:
- Vendoring the canonical source files into the deep-agents repo
- Refactoring inline `*_SYSTEM` constants out of `commands/*.py` into a uniform `prompts/` module
- Adapting source content to this codebase's tool surface while preserving semantic rules
- Per-role divergence checks (hybrid: rules + judge) wired into the Phase 4 eval harness
- Per-role JSON baseline + `--accept-divergence-baseline` flag (EVAL-13 regression gate)

Out of scope (explicit):
- Cost-frontier sweep (Phase 7)
- MCP cancellation polish, DeepAgents CLI integration test (Phase 8)
- Trace renderer / schema versioning (Phase 9)
- Content-port for synthesizer/code_reader prompts — they get refactored into `prompts/` for uniformity, but no canonical source exists to port from yet
- Open-source release prep (deferred past v1.1)

</domain>

<decisions>
## Implementation Decisions

### Prompt module layout
- **D-01:** Use **composable fragments** under `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/`. Shared blocks (iron rules, citation rules, page categories, refusal patterns) live in `prompts/_fragments/*.py`; per-role files (`librarian.py`, `ingestor.py`, `linter.py`, `scanner.py`) compose them. This trades a small indirection for de-duplication across roles, which matters because the iron rules and page-category content are shared verbatim across all four lattice-wiki agent files.
- **D-02:** Each role file exports a single `*_SYSTEM` string built at import time from the imported fragments — downstream call sites (`commands/{query,ingest,lint,scan}.py`) just `from graph_wiki_agent.prompts.librarian import LIBRARIAN_SYSTEM` and pass it to `SystemMessage(...)`. No runtime templating or lazy assembly.

### Provenance comments (PORT-06)
- **D-03:** Each fragment file carries an **inline header comment** at the top with three fields:
  - `# Source: <vendored path>` — the in-repo canonical file
  - `# Anchor: <section heading or line range>` — the specific block ported
  - `# Source-commit: <upstream lattice SHA at last sync>` — the lattice-repo commit the vendored copy was taken from
  Example shape locked in the discussion preview (see DISCUSSION-LOG.md).

### Canonical-source provenance / drift detection
- **D-04:** Vendor canonical sources into the deep-agents repo under **`cores/prompt-sources/`** (verbatim copy of `SKILL.md` + `agents/{librarian,ingestor,linter,scanner}.md` from `/Users/pat/Personal/lattice/plugins/lattice-wiki/`). Provenance comments in fragments point to the **vendored** path (not the sibling-repo path) plus the upstream `Source-commit`. Re-vendoring is a manual step. Drift detection becomes a trivial in-repo diff plus an SHA comparison if/when re-vendored. This decouples the agent package from the sibling lattice repo and is OSS-release-friendly.

### Port fidelity
- **D-05:** **Adapt the port** — rewrite host-specific references (slash commands like `/lattice-wiki:ingest`, Claude Code SDK tool surface, human-driven discussion patterns) to match `graph-wiki-agent`'s actual tool surface (vault IO via the `vault_io` core, BM25 search, deepagents loop). **Preserve semantic content verbatim**: iron rules, citation rules, page-type routing, refusal patterns, lint rule definitions, package-detection rules. Provenance still points to the source anchor so a reviewer can compare.
- **D-06:** Adaptations are local to the per-role files (the composition layer), not the shared fragments. Shared fragments stay closer to canonical wording; per-role files apply tool/host translation in role-specific prose.

### Divergence metric mechanism (EVAL-11)
- **D-07:** **Hybrid** detection. Programmatic rule-checkers for deterministic items (wikilink resolves against vault, citation present, frontmatter passes mechanical lint, page-type routing matches expected, iron-rule violations catchable by structure). LLM-judge (deepeval `GEval` with the Phase 4 heterogeneous panel: `claude-sonnet-4-6` + `nova-pro-v1:0`) for semantic items (refusal-pattern appropriateness, iron-rule violations not catchable by rules).

### Divergence rule definitions
- **D-08:** Per-role rule modules under **`cores/eval-harness/src/eval_harness/divergence/{librarian,ingestor,linter,scanner}.py`**, each exporting a list of `DivergenceCheck` dataclass instances. Schema (locked):
  ```python
  @dataclass
  class DivergenceCheck:
      id: str           # "LIB-001-wikilink-resolves" — role prefix + sequential ID + slug
      source_anchor: str  # "cores/prompt-sources/SKILL.md#iron-rules" — back-traces to canonical source
      severity: str       # "hard" | "soft"
      check: Callable[[AgentOutput, Vault], Verdict]
  ```
- **D-09:** Rule IDs are stable and human-meaningful so baseline JSON and CI failure output reference them directly.

### LLM-judge rubric input
- **D-10:** Judge prompts consume a **curated per-role rubric file** under `cores/eval-harness/src/eval_harness/divergence/rubrics/{librarian,ingestor,linter,scanner}.md`. Each rubric distills the canonical rules into binary pass/fail scoring criteria phrased for an LLM judge. Rubric files carry provenance comments at the top pointing to the source anchors in `cores/prompt-sources/`. Rubrics are not the same as agent prompts: agent prompts tell the agent *how to behave*; rubrics tell the judge *what counts as a violation*.

### Baseline storage + acceptance flow (EVAL-13)
- **D-11:** **Single JSON snapshot per role** at `cores/eval-harness/baselines/divergence-{role}.json`. Schema (locked, follows the preview shown in discussion):
  ```json
  {
    "role": "librarian",
    "recorded_at": "<ISO date>",
    "agent_commit": "<git SHA>",
    "checks": {
      "<rule_id>": {
        "runs": <int>,
        "failures": <int>,
        "accepted_failures": [{"fixture": "<id>", "excerpt": "<str>"}]
      }
    }
  }
  ```
- **D-12:** `--accept-divergence-baseline` flag rewrites the relevant baseline file(s). Default eval run loads baseline, computes deltas, fails the gate if any `failures` count exceeds baseline for a hard-severity check (soft-severity is reported but does not fail).
- **D-13:** EVAL-12 ("concrete examples in the report") is satisfied by the `accepted_failures` array carrying excerpts; the eval report renders these alongside per-role counts.

### Synthesizer + code-reader scope
- **D-14:** Refactor `SYNTHESIZER_SYSTEM` and `CODE_READER_SYSTEM` out of `commands/query.py` into `prompts/synthesizer.py` and `prompts/code_reader.py` for uniformity. **No content port and no divergence checks** for these roles in Phase 6 (no lattice-wiki canonical source exists for them). This avoids leaving prompt code split across two locations.

### Claude's Discretion
- Detailed file/module names within `prompts/_fragments/` (e.g., whether to split `citation_rules.py` from `iron_rules.py` or keep them in one file) — left to the planner based on actual content overlap once the source files are read end-to-end.
- Specific fixture additions needed for divergence checks (e.g., a "no-evidence question" fixture to exercise the librarian refusal check) — research/planner identifies the gaps against the existing Phase 4 fixture corpus.
- Whether to add a re-vendor helper script (e.g., `scripts/re-vendor-prompt-sources.py`) — nice-to-have; planner decides if it pays back in this phase or gets deferred.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project + milestone
- `.planning/PROJECT.md` — Core value, milestone v1.1 framing, prior-work context
- `.planning/REQUIREMENTS.md` §PORT, §EVAL-Q — The 9 requirements this phase delivers (PORT-01..06, EVAL-11..13)
- `.planning/ROADMAP.md` §"Phase 6" — Phase goal + 5 success criteria locked at roadmap time

### Lattice-wiki source-of-truth (to be vendored, then read from `cores/prompt-sources/` after port)
- `/Users/pat/Personal/lattice/plugins/lattice-wiki/skills/lattice-wiki/SKILL.md` — Iron rules, page categories, sub-agents overview, architecture (201 lines; canonical shared content)
- `/Users/pat/Personal/lattice/plugins/lattice-wiki/agents/librarian.md` — Librarian role spec (86 lines): workflow, rules, red flags
- `/Users/pat/Personal/lattice/plugins/lattice-wiki/agents/ingestor.md` — Ingestor role spec (112 lines)
- `/Users/pat/Personal/lattice/plugins/lattice-wiki/agents/linter.md` — Linter role spec (109 lines): mechanical + semantic rule definitions
- `/Users/pat/Personal/lattice/plugins/lattice-wiki/agents/scanner.md` — Scanner role spec (113 lines): package-detection + overview-generation rules
- `/Users/pat/Personal/lattice/plugins/lattice-wiki/skills/lattice-wiki/references/` — Supporting references for SKILL.md (reviewer should read end-to-end during port to catch anchors)

### Existing code (refactor targets)
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py` §137 (`LIBRARIAN_SYSTEM`), §150 (`SYNTHESIZER_SYSTEM`), §165 (`CODE_READER_SYSTEM`) — current inline librarian/synth/code-reader prompts
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/ingest.py` (`INGESTOR_SYSTEM` referenced at line 285) — current inline ingestor prompt
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py` (`SCANNER_SYSTEM` at line 329) — current inline scanner prompt
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/lint.py` (per-group prompts at line 460) — current inline linter prompts (3-group fan-out from Phase 5)

### Eval harness integration points
- `cores/eval-harness/` — Phase 4 harness, fixture corpus (3 repos), heterogeneous two-judge panel, `pytest-evals` sweep runner, regression-check AssertionError gate. Divergence metric plugs in here.
- `models.toml` — model picks per role (frozen for Phase 6; Phase 7 sweep updates these).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `cores/eval-harness` (Phase 4): `AmazonBedrockModel`-backed `GEval` metric class, fixture loader, regression-check gate, JSONL trace integration. Divergence metric class can inherit/compose with these rather than building from scratch.
- `cores/vault-io`: `Vault` reader is what the programmatic checks (e.g., `LIB-001-wikilink-resolves`) call to validate wikilink targets. Already exercises read-compatibility with existing vaults.
- Phase 5's lint command lives in `commands/lint.py` with a 3-group system-prompt fan-out (mechanical / semantic / coverage groupings). The linter's prompt port preserves this 3-group split — each group's system prompt composes from `_fragments/lint_*` blocks.

### Established Patterns
- All current agent prompts are inline `*_SYSTEM = """..."""` constants in `commands/*.py`, passed via `SystemMessage(content=...)`. Refactor target: extract to `prompts/` with no behavior change, then port content.
- Phase 4 eval harness uses deepeval's `assert_test` inside pytest with cost tracking per model via `cost_per_input_token`. The divergence metric is one more metric class in that harness.
- Existing baselines/snapshots format precedent: Phase 4 baseline recorder (EVAL-08 schema). Per-role divergence baseline mirrors this style so eval reports compose uniformly.

### Integration Points
- `commands/query.py`, `commands/ingest.py`, `commands/lint.py`, `commands/scan.py` — replace inline `*_SYSTEM` strings with imports from `graph_wiki_agent.prompts.{role}`.
- `cores/eval-harness/src/eval_harness/` — add `divergence/` subpackage (per-role rule modules + rubrics) and `baselines/` directory.
- `cores/prompt-sources/` — new vendoring location; planner decides on `pyproject.toml` packaging (likely a non-installable directory, just versioned content; verify it doesn't get picked up as a workspace member).

</code_context>

<specifics>
## Specific Ideas

- Provenance comment shape (locked example from discussion):
  ```python
  # Source: cores/prompt-sources/SKILL.md
  # Anchor: ## Iron rules (L193-L201)
  # Source-commit: <SHA at last sync>
  IRON_RULES = """..."""
  ```
- DivergenceCheck rule-ID convention: `<ROLE>-<NNN>-<slug>` (e.g., `LIB-001-wikilink-resolves`, `ING-004-page-type-routing`).
- Severity model is binary: `hard` (gates regression) vs `soft` (reported only). Soft is for noisier semantic checks the judge can return false-positives on.
- Baseline JSON snapshot location: `cores/eval-harness/baselines/divergence-{role}.json` (one file per role to keep diffs reviewable).
- Judge rubrics live next to rule code at `cores/eval-harness/src/eval_harness/divergence/rubrics/{role}.md` so changes to scoring criteria sit next to the checks they back.

</specifics>

<deferred>
## Deferred Ideas

- **Synthesizer + code-reader content port** — defer to a future phase if/when a canonical source for them is authored. Phase 6 only relocates these prompts for uniformity.
- **Re-vendor automation** — if the manual `cores/prompt-sources/` re-vendor proves painful in practice, add a `scripts/re-vendor-prompt-sources.py` helper in a future quality phase.
- **CI pre-commit hook for source-SHA drift** — out of scope here; baseline regression-gate already catches semantic drift. Add later if vendored sources start drifting silently.
- **Per-fixture pinned expectations** (alternative to aggregate per-role baseline) — declined as too heavy for v1.1; revisit if aggregate baselines miss localized regressions.
- **Divergence dashboard / trend report** — Phase 9 (trace/observability polish) is the natural home if surfacing per-role divergence-rate over time becomes desired.

</deferred>

---

*Phase: 6-Prompt Content Port + Divergence Eval*
*Context gathered: 2026-05-15*
</content>
</invoke>