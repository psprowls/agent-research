---
phase: 4
slug: eval-harness
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-14
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >= 8.3 + pytest-asyncio 1.3.0 + pytest-evals 0.3.4 |
| **Config file** | `cores/eval-harness/pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run --package eval-harness pytest cores/eval-harness/tests/ -m "not eval" -x` |
| **Full suite command** | `CODE_WIKI_RUN_EVAL=1 uv run --package eval-harness pytest --run-eval --run-eval-analysis` |
| **Estimated runtime** | ~30 seconds (unit); ~5-10 min (eval suite with Bedrock) |

---

## Sampling Rate

- **After every task commit:** Run `uv run --package eval-harness pytest cores/eval-harness/tests/ -m "not eval" -x`
- **After every plan wave:** Full unit suite clean; manually run eval suite with `CODE_WIKI_RUN_EVAL=1`
- **Before `/gsd-verify-work`:** All unit tests green; at least one full sweep run (3 models × 3 cases) completes
- **Max feedback latency:** ~30 seconds (unit suite)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| package-init | 04-01 | 0 | EVAL-01 | — | N/A | unit | `uv run --package eval-harness python -c "import eval_harness"` | ❌ W0 | ⬜ pending |
| fixture-cases | 04-01 | 0 | EVAL-02 | — | JSON schema validated | unit | `pytest cores/eval-harness/tests/test_structural.py::test_fixture_vault_has_pages` | ❌ W0 | ⬜ pending |
| baseline-cmd | 04-01 | 1 | EVAL-03 | T-4-03 | No shell=True; cmd list | unit | `pytest cores/eval-harness/tests/test_baseline.py::test_build_cmd` | ❌ W0 | ⬜ pending |
| baseline-schema | 04-01 | 1 | EVAL-08 | — | Includes model_id, hash, ts | unit | `pytest cores/eval-harness/tests/test_baseline.py::test_baseline_schema` | ❌ W0 | ⬜ pending |
| sweep-runner | 04-02 | 1 | EVAL-04 | T-4-02 | model_id sanitized in filename | unit (mock) | `pytest cores/eval-harness/tests/test_sweep.py::test_sweep_collects_results` | ❌ W0 | ⬜ pending |
| judge-panel | 04-03 | 2 | EVAL-05 | — | N/A | integration | `CODE_WIKI_RUN_EVAL=1 pytest --run-eval -k judge_panel` | ❌ W0 | ⬜ pending |
| structural-metrics | 04-02 | 1 | EVAL-06 | T-4-01 | JSON schema validated | unit | `pytest cores/eval-harness/tests/test_structural.py::test_known_good` | ❌ W0 | ⬜ pending |
| cost-frontier | 04-03 | 2 | EVAL-07 | — | N/A | unit | `pytest cores/eval-harness/tests/test_pricing.py` | ❌ W0 | ⬜ pending |
| regression-check | 04-03 | 2 | EVAL-09 | — | N/A | unit | `pytest cores/eval-harness/tests/test_report.py::test_regression_check_fails` | ❌ W0 | ⬜ pending |
| eval-mark | 04-01 | 0 | EVAL-10 | — | N/A | unit | `pytest cores/eval-harness/tests/ -v --co \| grep eval` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `cores/eval-harness/src/eval_harness/__init__.py` — package init
- [ ] `cores/eval-harness/pyproject.toml` — package declaration with workspace deps (deepeval>=4.0.0, pytest-evals>=0.3.4)
- [ ] `cores/eval-harness/tests/conftest.py` — `EVAL_GATE` skip marker, `fixture_vault_path` fixture
- [ ] `cores/eval-harness/tests/test_structural.py` — stub for EVAL-02, EVAL-06
- [ ] `cores/eval-harness/tests/test_pricing.py` — stub for EVAL-07
- [ ] `cores/eval-harness/tests/test_baseline.py` — stub for EVAL-03, EVAL-08
- [ ] `cores/eval-harness/tests/test_sweep.py` — stub for EVAL-04
- [ ] `cores/eval-harness/tests/test_report.py` — stub for EVAL-09
- [ ] `eval/cases/query_cases.json` — 3-5 cases from fixture vault (EVAL-02)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Baseline recorder runs `claude -p` against lattice-wiki and snapshots output | EVAL-03 | Requires Claude Code CLI + lattice-wiki plugin installed; one-time setup | Run `uv run --package eval-harness python -m eval_harness.record --vault-path cores/vault-io/tests/fixtures/round-trip-vault`; confirm JSON created in `eval/baselines/` |
| Position-bias: swap answer position, confirm score delta < 5% | EVAL-05 | Requires two full Bedrock judge runs | Run sweep with `--swap-positions`, compare mean scores; assert delta < 0.05 |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s (unit suite)
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
