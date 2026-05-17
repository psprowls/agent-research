---
phase: 7
slug: cost-frontier-sweep
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-16
---

# Phase 7 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x with `pytest-evals` two-phase pattern |
| **Config file** | `cores/eval-harness/pyproject.toml`, `cores/eval-harness/tests/conftest.py` |
| **Quick run command** | `uv run --package eval-harness pytest -q -m "not eval"` |
| **Full suite command** | `CODE_WIKI_RUN_EVAL=1 uv run --package eval-harness pytest -q` |
| **Estimated runtime** | ~30s quick (no live Bedrock); 10–20 min full matrix (live Bedrock) |

---

## Sampling Rate

- **After every task commit:** Run `uv run --package eval-harness pytest -q -m "not eval"` (offline unit + mocked-LLM tests; no Bedrock spend)
- **After every plan wave:** Run the same quick suite plus `uv run --package eval-harness pytest -q tests/eval/test_sweep_eval.py --dry-run` (validates plumbing without spend)
- **Before `/gsd:verify-work`:** Full suite must be green (live Bedrock matrix gated on `CODE_WIKI_RUN_EVAL=1`)
- **Max feedback latency:** 30s for quick suite; live-Bedrock run runs once per phase

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | TBD | TBD | SWEEP-01..05 | — | N/A | unit/integration/eval | TBD by planner | ⬜ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

*Populated by the planner against the per-plan task list. Every task must map to either an automated verify command or a Wave 0 dependency.*

---

## Wave 0 Requirements

- [ ] `cores/eval-harness/tests/test_pricing.py` — extend with cost estimator unit tests (SWEEP-02)
- [ ] `cores/eval-harness/tests/test_sweep_role_rotation.py` — new test file for per-role rotation logic
- [ ] `cores/eval-harness/tests/test_two_gate_scoring.py` — new test file for two-gate scoring (SWEEP-03)
- [ ] `cores/eval-harness/tests/test_dry_run.py` — new test file for `--dry-run` mode plumbing
- [ ] `eval/cases/code_reader_cases.json` — new vault-thin fixture file for code_reader (D-09)

*If existing test infrastructure (pytest-evals + EVAL_GATE) covers other requirements, planner skips those Wave 0 entries.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Frontier-pick edit to `models.toml` defaults | SWEEP-04 | Per D-10/D-11, the swap is a human edit guided by recommendation comments — automating it is explicitly out of scope | After the sweep run, review `.planning/sweep/{role}.md` per-role docs, then edit `cores/model-adapter/src/model_adapter/models.toml` to set the new `model_id` for each role, preserving `# Previous default:` provenance |
| BED-01 live-Bedrock gate pass | SWEEP-02 | Requires real AWS creds and Bedrock access — cannot be mocked | Confirm `make_llm("haiku").invoke("ping")` succeeds against real Bedrock during pre-flight pass before the matrix runs |
| Cost-story doc readability | SWEEP-05 | Narrative quality is a human judgment | Read `.planning/sweep/STORY.md` (or chosen path) and confirm it tells the v1.0 cost-savings story coherently |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s for quick suite
- [ ] `nyquist_compliant: true` set in frontmatter
- [ ] Per-task verification map populated by planner

**Approval:** pending
