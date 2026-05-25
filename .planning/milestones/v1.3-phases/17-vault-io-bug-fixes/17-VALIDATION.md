---
phase: 17
slug: wiki-io-bug-fixes
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-19
---

# Phase 17 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest ≥8.3 + pytest-asyncio 1.3.0 + syrupy 5.1.0 (project standard; already in `uv.lock`) |
| **Config file** | `packages/wiki-io/pyproject.toml` (workspace-managed) |
| **Quick run command** | `uv run --package wiki-io pytest -x` |
| **Full suite command** | `uv run --package wiki-io pytest` |
| **Integration suite** | `GRAPH_WIKI_RUN_INTEGRATION=1 uv run --package wiki-io pytest -m integration` |
| **Estimated runtime** | ~10–20 seconds (unit); ~30–60 seconds (with integration) |

---

## Sampling Rate

- **After every task commit:** `uv run --package wiki-io pytest -x`
- **After every plan wave:** `uv run --package wiki-io pytest` (full suite, mock-only)
- **Before `/gsd:verify-work`:** Full unit suite green + integration suite green + TOK-03 live re-stamp transcript captured
- **Max feedback latency:** ~20 seconds

---

## Per-Task Verification Map

| Req ID | Behavior | Test Type | Automated Command | File Exists |
|--------|----------|-----------|-------------------|-------------|
| SCAN-01 | `_load_existing_pages` skips companion files in `wiki/packages/<pkg>/` | unit | `uv run --package wiki-io pytest tests/test_scan_companion_fold.py::test_load_existing_skips_companions -x` | ❌ W0 |
| SCAN-01 | Layout-pinned `package` containers also get the companion filter | unit | `uv run --package wiki-io pytest tests/test_scan_companion_fold.py::test_layout_pinned_package_skips_companions -x` | ❌ W0 |
| SCAN-01 | `wiki/apps/` is NOT filtered (negative guard) | unit | `uv run --package wiki-io pytest tests/test_scan_companion_fold.py::test_apps_not_filtered -x` | ❌ W0 |
| SCAN-02 | `compute_diff` reports 0 `deleted` for companions on a healthy fixture | unit | `uv run --package wiki-io pytest tests/test_scan_companion_fold.py::test_compute_diff_no_phantom_deletes -x` | ❌ W0 |
| TOK-01 | `count_tokens` calls Bedrock with the correct `input={"converse": ...}` request shape | unit | `uv run --package wiki-io pytest tests/test_update_tokens.py::test_count_tokens_request_shape -x` | ❌ W0 |
| TOK-01 | `count_tokens` returns `response["inputTokens"]` (not `inputTokenCount`) | unit | `uv run --package wiki-io pytest tests/test_update_tokens.py::test_count_tokens_returns_input_tokens -x` | ❌ W0 |
| TOK-02 | Real Bedrock call succeeds; returns positive int | integration (gated) | `GRAPH_WIKI_RUN_INTEGRATION=1 uv run --package wiki-io pytest tests/integration/test_count_tokens_live.py -x` | ❌ W0 |
| TOK-03 | All 35 pages with `tokens: 0` in `~/Personal/graph-wiki/agent-research` have non-zero `tokens:` after re-stamp | manual + file-state | `uv run python -m wiki_io.update_tokens`; `grep -rn "^tokens: 0" ~/Personal/graph-wiki/agent-research` returns 0 matches | manual; transcript in 17-VERIFICATION.md |
| WSRES-01 | `init_vault.py` resolves the repo correctly under v2 workspace layout | unit | `uv run --package wiki-io pytest tests/test_detect_containers.py::test_v2_layout_finds_repo_containers -x` | ❌ W0 |
| WSRES-02 | `detect()` excludes the workspace_path subdir from the layout classification | unit | `uv run --package wiki-io pytest tests/test_detect_containers.py::test_workspace_path_excluded -x` | ❌ W0 |
| WSRES-02 | v1 layout (workspace == repo) does NOT exclude (guard works) | unit | `uv run --package wiki-io pytest tests/test_detect_containers.py::test_v1_layout_guard -x` | ❌ W0 |
| WSRES-03 | Synthetic `tmp_path` fixture exercises end-to-end v2 resolution | unit | `uv run --package wiki-io pytest tests/test_detect_containers.py::test_v2_synthetic_repo -x` | ❌ W0 |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `packages/wiki-io/tests/test_scan_companion_fold.py` — new file; covers SCAN-01, SCAN-02
- [ ] `packages/wiki-io/tests/test_update_tokens.py` — new file (no existing test for `update_tokens.py`); covers TOK-01
- [ ] `packages/wiki-io/tests/integration/test_count_tokens_live.py` — new file; gated integration; covers TOK-02 (live Bedrock)
- [ ] `packages/wiki-io/tests/test_detect_containers.py` — new file; covers WSRES-01, WSRES-02, WSRES-03
- [ ] Fixture extensions in `packages/wiki-io/tests/conftest.py` (or inline) — synthetic v2 monorepo + companion-vault patterns
- [ ] No framework install needed (pytest, pytest-asyncio, syrupy already in `uv.lock`)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| TOK-03 live re-stamp transcript on `~/Personal/graph-wiki/agent-research` | TOK-03 | Writes commits to a separate wiki git repo; depends on AWS credentials; one-shot operational fix not suitable for CI | 1) Verify `~/Personal/graph-wiki/agent-research` is clean (`git status`); 2) Confirm AWS Bedrock creds are loaded; 3) Run `uv run python -m wiki_io.update_tokens` from the wiki repo; 4) Capture stdout into `17-VERIFICATION.md`; 5) Assert `grep -rn "^tokens: 0" ~/Personal/graph-wiki/agent-research` returns zero matches |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 20s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
