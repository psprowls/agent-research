---
phase: 6
slug: prompt-content-port-divergence-eval
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-15
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest ≥8.3 + pytest-asyncio 1.3.0 + syrupy 5.1.0 |
| **Config file** | workspace root `pyproject.toml` (`asyncio_mode = "auto"`) |
| **Quick run command** | `uv run pytest agents/code-wiki-agent/tests/prompts/ cores/eval-harness/tests/test_divergence_checks.py cores/eval-harness/tests/test_divergence_baseline.py -x -q` |
| **Full suite command** | `CODE_WIKI_RUN_EVAL=1 uv run pytest cores/eval-harness/tests/ agents/code-wiki-agent/tests/ -x -q` |
| **Estimated runtime** | ~10 seconds (quick), ~5–10 minutes (full with eval gate) |

---

## Sampling Rate

- **After every task commit:** Run quick run command
- **After every plan wave:** Run quick run + `uv run pytest agents/code-wiki-agent/tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite (with `CODE_WIKI_RUN_EVAL=1`) must be green
- **Max feedback latency:** ~10 seconds for quick run

---

## Per-Task Verification Map

> Filled in by the planner per task. Status legend: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD by planner — every task must point at one of the commands below OR a Wave 0 stub | | | | | | | | | ⬜ pending |

**Standard commands available to plans:**

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PORT-01 | Traceability table exists (provenance headers in every fragment) | unit | `uv run pytest agents/code-wiki-agent/tests/prompts/test_provenance.py -x` | ❌ Wave 0 |
| PORT-02 | LIBRARIAN_SYSTEM contains iron rules and citation rules | snapshot | `uv run pytest agents/code-wiki-agent/tests/prompts/test_prompt_snapshots.py::test_librarian_system_snapshot -x` | ❌ Wave 0 |
| PORT-03 | INGESTOR_SYSTEM contains page-type routing | snapshot | `uv run pytest agents/code-wiki-agent/tests/prompts/test_prompt_snapshots.py::test_ingestor_system_snapshot -x` | ❌ Wave 0 |
| PORT-04 | LINTER_*_SYSTEM prompts contain canonical lint categories | snapshot | `uv run pytest 'agents/code-wiki-agent/tests/prompts/test_prompt_snapshots.py::test_linter_*' -x` | ❌ Wave 0 |
| PORT-05 | SCANNER_SYSTEM contains package-detection rules | snapshot | `uv run pytest agents/code-wiki-agent/tests/prompts/test_prompt_snapshots.py::test_scanner_system_snapshot -x` | ❌ Wave 0 |
| PORT-06 | Every fragment file has 3-line provenance header; Source: path resolves to `cores/prompt-sources/` | unit | `uv run pytest agents/code-wiki-agent/tests/prompts/test_provenance.py -x` | ❌ Wave 0 |
| EVAL-11 | DivergenceCheck.check callables pass on valid output, fail on violations | unit per check | `uv run pytest cores/eval-harness/tests/test_divergence_checks.py -x` | ❌ Wave 0 |
| EVAL-12 | Divergence eval emits per-role counts + accepted_failures | integration (CODE_WIKI_RUN_EVAL) | `CODE_WIKI_RUN_EVAL=1 uv run pytest cores/eval-harness/tests/test_divergence.py -x` | ❌ Wave 0 |
| EVAL-13 | `--accept-divergence-baseline` rewrites baseline; default run gates hard-severity failures | unit | `uv run pytest cores/eval-harness/tests/test_divergence_baseline.py -x` | ❌ Wave 0 |

---

## Wave 0 Requirements

- [ ] `agents/code-wiki-agent/tests/prompts/__init__.py` — test package
- [ ] `agents/code-wiki-agent/tests/prompts/test_prompt_snapshots.py` — syrupy snapshot tests for librarian, ingestor, linter (3 groups), scanner, synthesizer, code_reader
- [ ] `agents/code-wiki-agent/tests/prompts/test_provenance.py` — every `_fragments/*.py` file has 3-line `# Source: / # Anchor: / # Source-commit:` header; Source paths resolve within `cores/prompt-sources/`
- [ ] `cores/eval-harness/tests/test_divergence_checks.py` — unit tests for each `DivergenceCheck.check` callable against synthetic in-memory `AgentOutput` + tiny `Vault` fixtures (no Bedrock)
- [ ] `cores/eval-harness/tests/test_divergence_baseline.py` — unit tests for `load_baseline`, `write_baseline`, `check_regression`, `--accept-divergence-baseline` flag behavior (no Bedrock)
- [ ] `cores/eval-harness/tests/test_divergence.py` — integration test gated behind `CODE_WIKI_RUN_EVAL=1`; exercises full `DivergenceMetric` (programmatic + judge) against fixture vault

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Provenance Source-commit SHAs honestly point at the upstream `lattice` repo commit at time of vendoring | PORT-06 | Cross-repo SHA correctness cannot be enforced in this repo without coupling to the sibling lattice checkout | After re-vendoring, manually run `git -C /Users/pat/Personal/lattice log -1 --format=%H -- plugins/lattice-wiki` and confirm the SHA matches the `# Source-commit:` headers in `cores/prompt-sources/` |
| Semantic faithfulness of port (rules ported preserve canonical meaning, not just superficial keyword matches) | PORT-02..05 | Snapshot tests freeze byte equality, not semantic equivalence; only a human can confirm "this paraphrase says the same thing" | One-time human read of every `prompts/_fragments/*.py` vs. the source anchor it points at; record sign-off in PR description |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (provenance, snapshot, divergence check, baseline tests)
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s for quick run
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
