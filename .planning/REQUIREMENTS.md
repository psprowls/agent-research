# Requirements: deep-agents / code-wiki-agent — Milestone v1.1 Quality Improvements

**Milestone:** v1.1 Quality Improvements
**Scoped:** 2026-05-15
**Status:** Active

---

## Milestone Goal

Close the output-quality gap with `lattice-wiki` by porting its prompt content into `code-wiki-agent`, then validate the cost-frontier on Bedrock and prove host-level reliability under the DeepAgents CLI.

Sequencing rule: **prompt port lands before the cost-frontier sweep** so the sweep measures the *improved* agent, not the pre-port baseline.

---

## v1.1 Requirements

### PORT — Lattice-wiki SKILL.md content port (output-quality lift)

- [x] **PORT-01**: Canonical prompt sources from `/Users/pat/Personal/lattice/plugins/lattice-wiki` are identified per agent role (librarian, ingestor, linter, scanner) — source files and section anchors pinned in a traceability table
- [x] **PORT-02**: Librarian agent prompt incorporates canonical iron rules, citation rules, and refusal patterns from the `lattice-wiki:librarian` SKILL content
- [x] **PORT-03**: Ingestor agent prompt incorporates canonical ingestion patterns (page-type routing, frontmatter rules, layout-block rules) from the `lattice-wiki:ingestor` SKILL content
- [x] **PORT-04**: Linter agent prompt incorporates canonical lint rule definitions (mechanical + semantic) from the `lattice-wiki:linter` SKILL content
- [x] **PORT-05**: Scanner agent prompt incorporates canonical package-detection and overview-generation rules from the `lattice-wiki:scanner` SKILL content
- [x] **PORT-06**: Prompt content lives in a single `prompts/` module per agent role with provenance comments referencing the canonical source path + anchor (so future drift is detectable)

### EVAL-Q — Output-quality eval (divergence detection)

- [x] **EVAL-11**: A new eval metric flags divergences between agent output and skill-content expectations (e.g. missing required citation, wrong page-type routing, broken iron rule)
- [x] **EVAL-12**: The divergence eval runs against the fixture corpus and emits per-role divergence counts + concrete examples in the report
- [x] **EVAL-13**: Regression gate — divergence rate cannot increase from a recorded baseline without explicit `--accept-divergence-baseline` acknowledgment

### SWEEP — Cost-frontier sweep execution

- [x] **SWEEP-01**: Cost-frontier sweep runs against the *post-port* agent (after PORT requirements land) across all 6 agent roles in `models.toml` (`librarian`, `code_reader`, `scanner`, `linter`, `ingestor`, `synthesizer`) (corrected 2026-05-17 per Phase 7 D-02: the v1.1 roadmap said 7 but models.toml has 6 in-scope agent roles plus 2 judges that are out of scope for this sweep)
- [x] **SWEEP-02**: BED-01 live-Bedrock gate verification passes during the sweep (`make_llm("haiku").invoke("ping")` succeeds against real Bedrock)
- [x] **SWEEP-03**: Sweep produces a cost-frontier table per role (model × quality × cost) committed under `.planning/` or `docs/`
- [x] **SWEEP-04**: `models.toml` defaults updated to the cost-optimal pick per role; previous defaults preserved as commented provenance
- [x] **SWEEP-05**: Sweep outcome summarized in a short results doc — the cost story v1.0 promised to validate

### MCP-CAN — MCP cancellation polish (MCP-06 follow-up)

- [ ] **MCP-09**: Mid-fan-out cancel from a real DeepAgents CLI host is reproduced and current behavior documented
- [ ] **MCP-10**: In-flight `SubagentPool` invocations terminate cleanly on host cancel (no orphaned Bedrock calls; traces close with a `cancelled` terminal event)
- [ ] **MCP-11**: Automated cancel test covers the cancel-mid-fan-out scenario at the MCP transport boundary (opt-in gate consistent with v1.0 integration tests)

### DA-CLI — DeepAgents CLI integration test

- [ ] **DACLI-01**: End-to-end test launches `code-wiki-mcp` as a stdio subprocess from a DeepAgents CLI host
- [ ] **DACLI-02**: Test exercises every shipped MCP tool (`wiki_init`, `wiki_scan`, `wiki_ingest`, `wiki_query`, `wiki_lint`, `wiki_log`) with realistic inputs and asserts non-error outcomes
- [ ] **DACLI-03**: Test runs in CI under an opt-in env-var gate (consistent with `CODE_WIKI_RUN_INTEGRATION=1` pattern)

### TRACE — Trace/observability polish

- [ ] **OBS-04**: `.code-wiki/traces/` JSONL schema is documented and versioned (schema-version field + breaking-change policy)
- [ ] **OBS-05**: `code-wiki-agent trace` renderer surfaces per-subagent cost (input/output tokens × model price) per trace
- [ ] **OBS-06**: Trace renderer collapses repeated subagent-role groups into a summary line by default, with `--expand` to drill in

### CTX — Subagent context completion (spike-001 follow-up)

Source: `.planning/spikes/001-subagent-context-audit/README.md`. Closes the gap between Phase 6's curated prompt fragments and the load-bearing content still missing from subagent system prompts (vault layout, root-vs-wiki `CLAUDE.md` disambiguation, project-specific style/log/layout from `wiki/CLAUDE.md`). Architectural constraint: must not require a `deepagents.SubAgentMiddleware` migration; uses the existing `SubagentPool` dispatch.

- [x] **CTX-01**: Four shared prompt fragments extracted under `agents/code-wiki-agent/src/code_wiki_agent/prompts/_fragments/` — `architecture_overview` (anchor `SKILL.md §Architecture L34-69`), `style_rules` (anchor `wiki/CLAUDE.md §Style L153-159`), `log_format` (anchor `wiki/CLAUDE.md §Log format L124-133`), `claude_md_disambiguation` (anchor `SKILL.md §Cross-tool compatibility L141`); each carries the standard `# Source: / # Anchor: / # Source-commit:` provenance header
- [x] **CTX-02**: `prompts/project_context.py::render_project_context(wiki_path: Path) -> str` reads `wiki/CLAUDE.md` (or falls back to `AGENTS.md`) and returns a compact rendered block covering parsed layout containers + style + log format; returns empty string when neither schema file is present rather than crashing
- [x] **CTX-03**: `commands/scan.py`, `commands/lint.py`, `commands/ingest.py` call `render_project_context()` once at command entry and pass the result into the relevant prompt builders for scanner / linter (3 groups) / ingestor `SystemMessage` composition
- [x] **CTX-04**: Snapshot tests (using `syrupy`, already in stack) cover assembled system-prompt strings for each subagent with and without project context, plus an explicit missing-`wiki/CLAUDE.md` degradation test verifying no crash
- [x] **CTX-05**: Added context per subagent role stays within +1,500 tokens of the pre-Phase-10 baseline (snapshot-measured) and re-running the Phase 6 divergence eval against the recorded baseline does not regress (existing `--accept-divergence-baseline` flow applies for any intentional shift)

---

## v1.2 Backlog (filed during Phase 7, 2026-05-17)

Followup requirements surfaced by the Phase 7 cost-frontier sweep. Not in scope for v1.1; carry into the v1.2 roadmap. See `.planning/sweep/STORY.md` Next Steps for context.

### TRACE-FU — Trace pipeline correctness (v1.2)

- [ ] **TRACE-FU-01**: Fix the production trace pipeline so `SubagentPool._write_trace` records `usage_metadata` for every LLM invocation, not just the sweep harness. Phase 7 found that every closure fed to `pool.run_all` (`drill_page`, `generate_stub`, `run_linter_group`, etc.) returns `resp.content` (a string with no `usage_metadata`), so every `.code-wiki/traces/*.jsonl` record carries `tokens_in=null`/`tokens_out=null`/`cost_usd=null`. Phase 7 worked around this with a contextvar wrap on `ChatBedrockConverse.ainvoke` inside `eval_harness.sweep`; the underlying production trace pipeline is still broken. Approach options: (a) extend `SubagentPool` to accept an optional usage-extractor callback; (b) refactor closures to return a `(content, ai_message)` shape; (c) port the contextvar wrap into `SubagentPool` itself.

### SWEEP-FU — Cost-frontier sweep followups (v1.2)

- [ ] **SWEEP-FU-02**: Thread `DivergenceMetric` instances through `run_full_matrix` so Gate 1 produces a real PASS/FAIL signal for roles in `ROLES_WITH_DIVERGENCE` (`librarian`, `scanner`, `linter`, `ingestor`, `code_reader`). Today Phase 7 passes `divergence_metric_or_none=None` and the scorer uniformly marks Gate 1 = FAIL — qualification status for divergence roles is therefore meaningless. Phase 6's divergence rule modules need to be loaded per-role and forwarded from the matrix driver.
- [ ] **SWEEP-FU-03**: Tune `eval/cases/code_reader_cases.json` (and/or relax the librarian short-circuit threshold during sweeps) so all 4 code_reader candidates receive non-zero call volume. In Phase 7, only `haiku-4-5` (the default) had the fallback actually fire; the other 3 candidates show cost=N/A and quality=N/A, leaving the swap decision unsupported.
- [ ] **SWEEP-FU-04**: Re-sweep the `scanner` role against a vault with new and/or changed packages. The round-trip-vault fixture used in Phase 7 had every package pinned stale, so no scanner stub-gen LLM calls fired across any candidate and the role yielded no actionable cost or quality data.

(SWEEP-FU-01 was promoted to its own series and renumbered as TRACE-FU-01.)

### MODEL-FU — Model config / test drift (v1.2)

- [ ] **MODEL-FU-01**: Update `cores/model-adapter/tests/test_loader.py::test_load_role_config_synthesizer_uses_sonnet` to match the current production config. The test was written against a Sonnet-default synthesizer (Phase 02-01), but `models.toml` was later switched to `qwen.qwen3-32b-v1:0` for the synthesizer role (per project memory: Qwen3-32B fan-out, Qwen3-80B synthesis). The test now fails on every commit. Decide whether to (a) assert the qwen ARN directly, (b) parametrize the assertion against `models.toml` content, or (c) split into two tests — one that locks the *default-overridden* shape and one that locks per-role provider expectations. Surfaced post-Phase 08 regression run (2026-05-17); pre-dates Phase 08, not caused by it.

---

## Future Requirements (deferred past v1.1)

- **Open-source release prep** — README badges, contribution guide, public install instructions, PyPI publish dry-run. Holding until the cost-frontier sweep validates the cost story.
- **Nested subagents** — explicitly out of scope for v1.x per Key Decisions.

## Out of Scope (v1.x)

- Custom TUI in v1.x
- Non-Bedrock providers in v1.x
- Vault format migration / writing back to lattice-wiki vaults
- Real-time file watchers / auto-sync

---

## Traceability

| Requirement | Phase                                    | Status      |
|-------------|------------------------------------------|-------------|
| PORT-01     | Phase 6: Prompt Content Port + Divergence Eval | Complete    |
| PORT-02     | Phase 6: Prompt Content Port + Divergence Eval | Complete    |
| PORT-03     | Phase 6: Prompt Content Port + Divergence Eval | Complete    |
| PORT-04     | Phase 6: Prompt Content Port + Divergence Eval | Complete    |
| PORT-05     | Phase 6: Prompt Content Port + Divergence Eval | Complete    |
| PORT-06     | Phase 6: Prompt Content Port + Divergence Eval | Complete    |
| EVAL-11     | Phase 6: Prompt Content Port + Divergence Eval | Complete    |
| EVAL-12     | Phase 6: Prompt Content Port + Divergence Eval | Complete    |
| EVAL-13     | Phase 6: Prompt Content Port + Divergence Eval | Complete    |
| SWEEP-01    | Phase 7: Cost-Frontier Sweep            | Complete    |
| SWEEP-02    | Phase 7: Cost-Frontier Sweep            | Complete    |
| SWEEP-03    | Phase 7: Cost-Frontier Sweep            | Complete    |
| SWEEP-04    | Phase 7: Cost-Frontier Sweep            | Complete    |
| SWEEP-05    | Phase 7: Cost-Frontier Sweep            | Complete    |
| MCP-09      | Phase 8: Host Reliability               | Pending     |
| MCP-10      | Phase 8: Host Reliability               | Pending     |
| MCP-11      | Phase 8: Host Reliability               | Pending     |
| DACLI-01    | Phase 8: Host Reliability               | Pending     |
| DACLI-02    | Phase 8: Host Reliability               | Pending     |
| DACLI-03    | Phase 8: Host Reliability               | Pending     |
| OBS-04      | Phase 9: Trace/Observability Polish     | Pending     |
| OBS-05      | Phase 9: Trace/Observability Polish     | Pending     |
| OBS-06      | Phase 9: Trace/Observability Polish     | Pending     |
| CTX-01      | Phase 10: Subagent Context Completion   | Complete |
| CTX-02      | Phase 10: Subagent Context Completion   | Complete |
| CTX-03      | Phase 10: Subagent Context Completion   | Complete |
| CTX-04      | Phase 10: Subagent Context Completion   | Complete |
| CTX-05      | Phase 10: Subagent Context Completion   | Complete |
| TRACE-FU-01 | v1.2 backlog (filed by Phase 7)         | Backlog     |
| SWEEP-FU-02 | v1.2 backlog (filed by Phase 7)         | Backlog     |
| SWEEP-FU-03 | v1.2 backlog (filed by Phase 7)         | Backlog     |
| SWEEP-FU-04 | v1.2 backlog (filed by Phase 7)         | Backlog     |
| MODEL-FU-01 | v1.2 backlog (filed by Phase 8)         | Backlog     |
