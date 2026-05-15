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

- [ ] **PORT-01**: Canonical prompt sources from `/Users/pat/Personal/lattice/plugins/lattice-wiki` are identified per agent role (librarian, ingestor, linter, scanner) — source files and section anchors pinned in a traceability table
- [ ] **PORT-02**: Librarian agent prompt incorporates canonical iron rules, citation rules, and refusal patterns from the `lattice-wiki:librarian` SKILL content
- [ ] **PORT-03**: Ingestor agent prompt incorporates canonical ingestion patterns (page-type routing, frontmatter rules, layout-block rules) from the `lattice-wiki:ingestor` SKILL content
- [ ] **PORT-04**: Linter agent prompt incorporates canonical lint rule definitions (mechanical + semantic) from the `lattice-wiki:linter` SKILL content
- [ ] **PORT-05**: Scanner agent prompt incorporates canonical package-detection and overview-generation rules from the `lattice-wiki:scanner` SKILL content
- [ ] **PORT-06**: Prompt content lives in a single `prompts/` module per agent role with provenance comments referencing the canonical source path + anchor (so future drift is detectable)

### EVAL-Q — Output-quality eval (divergence detection)

- [ ] **EVAL-11**: A new eval metric flags divergences between agent output and skill-content expectations (e.g. missing required citation, wrong page-type routing, broken iron rule)
- [ ] **EVAL-12**: The divergence eval runs against the fixture corpus and emits per-role divergence counts + concrete examples in the report
- [ ] **EVAL-13**: Regression gate — divergence rate cannot increase from a recorded baseline without explicit `--accept-divergence-baseline` acknowledgment

### SWEEP — Cost-frontier sweep execution

- [ ] **SWEEP-01**: Cost-frontier sweep runs against the *post-port* agent (after PORT requirements land) across all 7 roles in `models.toml`
- [ ] **SWEEP-02**: BED-01 live-Bedrock gate verification passes during the sweep (`make_llm("haiku").invoke("ping")` succeeds against real Bedrock)
- [ ] **SWEEP-03**: Sweep produces a cost-frontier table per role (model × quality × cost) committed under `.planning/` or `docs/`
- [ ] **SWEEP-04**: `models.toml` defaults updated to the cost-optimal pick per role; previous defaults preserved as commented provenance
- [ ] **SWEEP-05**: Sweep outcome summarized in a short results doc — the cost story v1.0 promised to validate

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
| PORT-01     | Phase 6: Prompt Content Port + Divergence Eval | Pending |
| PORT-02     | Phase 6: Prompt Content Port + Divergence Eval | Pending |
| PORT-03     | Phase 6: Prompt Content Port + Divergence Eval | Pending |
| PORT-04     | Phase 6: Prompt Content Port + Divergence Eval | Pending |
| PORT-05     | Phase 6: Prompt Content Port + Divergence Eval | Pending |
| PORT-06     | Phase 6: Prompt Content Port + Divergence Eval | Pending |
| EVAL-11     | Phase 6: Prompt Content Port + Divergence Eval | Pending |
| EVAL-12     | Phase 6: Prompt Content Port + Divergence Eval | Pending |
| EVAL-13     | Phase 6: Prompt Content Port + Divergence Eval | Pending |
| SWEEP-01    | Phase 7: Cost-Frontier Sweep            | Pending     |
| SWEEP-02    | Phase 7: Cost-Frontier Sweep            | Pending     |
| SWEEP-03    | Phase 7: Cost-Frontier Sweep            | Pending     |
| SWEEP-04    | Phase 7: Cost-Frontier Sweep            | Pending     |
| SWEEP-05    | Phase 7: Cost-Frontier Sweep            | Pending     |
| MCP-09      | Phase 8: Host Reliability               | Pending     |
| MCP-10      | Phase 8: Host Reliability               | Pending     |
| MCP-11      | Phase 8: Host Reliability               | Pending     |
| DACLI-01    | Phase 8: Host Reliability               | Pending     |
| DACLI-02    | Phase 8: Host Reliability               | Pending     |
| DACLI-03    | Phase 8: Host Reliability               | Pending     |
| OBS-04      | Phase 9: Trace/Observability Polish     | Pending     |
| OBS-05      | Phase 9: Trace/Observability Polish     | Pending     |
| OBS-06      | Phase 9: Trace/Observability Polish     | Pending     |
