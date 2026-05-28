---
phase: 51
slug: package-family-removal-divergence-rule-cleanup
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-28
---

# Phase 51 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest ≥8.3 (project standard per `CLAUDE.md`) |
| **Config files** | `packages/{graph-io,wiki-io,eval-harness}/pyproject.toml` + `packages/eval-harness/tests/conftest.py` |
| **Quick run command** | `pytest packages/graph-io/tests/test_uri.py packages/wiki-io/tests/test_entity_writer.py -x` |
| **Full suite command** | `pytest packages/graph-io/tests/ packages/wiki-io/tests/ packages/eval-harness/tests/ -x` |
| **Workspace-scoped** | `uv run --package <pkg> pytest` |
| **Estimated runtime** | ~30–60s per package quick run; ~3 min full suite |

---

## Sampling Rate

- **After every task commit:** Run `uv run --package <touched-pkg> pytest -x`
- **After every plan wave:** Run full suite (3 packages)
- **Before `/gsd:verify-work`:** Full suite green + both grep gates pass
- **Max feedback latency:** ~60s per task

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 51-01-01 | 01 | 1 | PKGFAM-01 | — | N/A | unit | `pytest packages/graph-io/tests/test_uri.py -x` + new assertion `assert "package_family" not in _VALID_KINDS` | ✅ + 1 new assertion | ⬜ pending |
| 51-01-02 | 01 | 1 | PKGFAM-02 | — | N/A | unit | `pytest packages/graph-io/tests/test_uri.py -x` (delete `test_package_family_uri`) | ✅ delete test | ⬜ pending |
| 51-01-03 | 01 | 1 | PKGFAM-04 | — | N/A | grep + optional unit | `pytest packages/graph-io/tests/test_cli_main.py -k "no_package_family_subcommand"` (optional) + grep gate | ❌ W0 (optional) | ⬜ pending |
| 51-02-01 | 02 | 2 | PKGFAM-03 (alias) | — | N/A | unit | `pytest packages/wiki-io/tests/test_entity_writer.py::test_admitted_kinds_shape -x` (update to 6-kind expectation) | ✅ existing | ⬜ pending |
| 51-02-02 | 02 | 2 | PKGFAM-03 (templates) | — | N/A | unit | `assert not (importlib.resources.files("wiki_io.assets.page-templates") / "entity-package-family.md").exists()` | ❌ W0 | ⬜ pending |
| 51-02-03 | 02 | 2 | PKGFAM-03 (link_rewriter + lint) | — | N/A | unit + regression | `pytest packages/wiki-io/tests/test_link_rewriter*.py -x` + `pytest packages/wiki-io/tests/test_lint_dependency.py -x` | ✅ existing — update fixtures | ⬜ pending |
| 51-03-01 | 03 | 3 | CLEANUP-01 (code) | — | N/A | unit | `pytest packages/eval-harness/tests/test_divergence_checks.py -x` (delete LIB-003 cases) | ✅ existing — drop LIB-003 cases | ⬜ pending |
| 51-03-02 | 03 | 3 | CLEANUP-01 (baseline) | — | N/A | integration | `pytest packages/eval-harness/tests/test_divergence_baseline.py packages/eval-harness/tests/test_two_gate_scorer.py -x` | ✅ existing — edit fixture JSON or live-regen | ⬜ pending |
| 51-04-01 | 04 | 3 | PKGFAM-03 (fixture) | — | N/A | unit | `pytest packages/wiki-io/tests/test_round_trip.py -x` | ✅ existing | ⬜ pending |
| 51-04-02 | 04 | 3 | PKGFAM-03 (bm25 regen) | — | N/A | integration | BM25-only inline script (no Bedrock); fixture parses cleanly | ❌ W0 — script lives in plan | ⬜ pending |
| 51-G1 | exit | gate | PKGFAM-01..05 | — | N/A | grep gate | `! grep -rE "package_family\|package-family\|PKGFAM\|package_family_uri" packages/ --include="*.py" --include="*.md" --include="*.json" --include="*.toml" \| grep -v ".planning/" \| grep -v "migration.log" \| grep -q .` | new — verification step | ⬜ pending |
| 51-G2 | exit | gate | CLEANUP-01 | — | N/A | grep gate | `! grep -rn "_SLUG_ONLY_RE\|LIB-003" packages/eval-harness/ \| grep -q .` AND `! grep -n "_check_no_slug_only_wikilinks" packages/eval-harness/src/eval_harness/divergence/librarian.py \| grep -q .` (SYN-002 in synthesizer.py is OUT of scope per Pitfall 1) | new — verification step | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Add `assert "package_family" not in _VALID_KINDS` to `packages/graph-io/tests/test_uri.py` (or new `test_queries.py` if module-level test absent).
- [ ] Optional: `packages/graph-io/tests/test_cli_main.py::test_no_package_family_subcommand` asserting subcommands absent (grep already covers).
- [ ] Add `packages/wiki-io/tests/test_assets.py::test_no_package_family_template` (importlib.resources existence check) — small, fast, belt-and-suspenders.
- [ ] BM25-only inline regen script for `vocab.index.json` / `vocab.tokenizer.json` (script body in plan 04).
- [ ] No framework install — pytest + bm25s already vendored.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live Bedrock baseline regen (D-05 preferred path) | CLEANUP-01 baseline shape | Requires `GRAPH_WIKI_RUN_EVAL=1` + AWS creds (~$2 cost) | `GRAPH_WIKI_RUN_EVAL=1 pytest packages/eval-harness/tests/test_divergence.py -k librarian --accept-divergence-baseline`; if creds absent, fallback to hand-edit baseline JSON (documented in plan 03) |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter (set after Wave 0 lands)

**Approval:** pending
