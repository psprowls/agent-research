---
phase: 46
slug: inbound-link-migration-cutover
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-27
---

# Phase 46 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + syrupy 5.x (snapshot for `--dry-run` output) |
| **Config file** | `pyproject.toml` per package (existing) |
| **Quick run command** | `uv run --package wiki-io pytest packages/wiki-io/tests -x -k link_rewriter` |
| **Full suite command** | `uv run pytest` (root, all workspace members) |
| **Estimated runtime** | ~10 seconds quick, ~3 minutes full |

---

## Sampling Rate

- **After every task commit:** Run `uv run --package <pkg> pytest <focused_test_file> -x`
- **After every plan wave:** Run quick suite for the changed packages
- **Before `/gsd:verify-work`:** Full suite green, including the plugin smoke regression
- **Max feedback latency:** ~10 seconds for a focused unit test, ~45 seconds for the integration suite

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------------|-----------|-------------------|-------------|--------|
| 46-01-01 | 01 | 1 | MIGRATION-01 | `indented_code_spans` helper detects 4-space/tab indented blocks preceded by a blank line | unit | `uv run --package wiki-io pytest packages/wiki-io/tests/test_lint_common_indented_code.py -x` | ❌ W0 | ⬜ pending |
| 46-01-02 | 01 | 1 | MIGRATION-01, MIGRATION-04 | `rewrite_text` skips wikilinks inside fenced/inline/indented code regions (byte-identical) | unit | `uv run --package wiki-io pytest packages/wiki-io/tests/test_link_rewriter.py -x -k skips_` | ❌ W0 | ⬜ pending |
| 46-01-03 | 01 | 1 | MIGRATION-01 | `rewrite_text` preserves alias and anchor suffixes when rewriting non-code wikilinks | unit | `uv run --package wiki-io pytest packages/wiki-io/tests/test_link_rewriter.py -x -k alias_or_anchor` | ❌ W0 | ⬜ pending |
| 46-01-04 | 01 | 1 | MIGRATION-01 | `rewrite_text` skips unresolvable targets (`table[t]=None`) and unknown targets (not in table) | unit | `uv run --package wiki-io pytest packages/wiki-io/tests/test_link_rewriter.py -x -k unresolvable_or_unknown` | ❌ W0 | ⬜ pending |
| 46-01-05 | 01 | 1 | MIGRATION-01 | `rewrite_text` is idempotent: second call rewrites 0 (already-rewritten text is stable) | unit | `uv run --package wiki-io pytest packages/wiki-io/tests/test_link_rewriter.py -x -k idempotent` | ❌ W0 | ⬜ pending |
| 46-02-01 | 02 | 2 | MIGRATION-02 | `build_rewrite_table` Source 1 emits convention-template entries for all 5 admitted kinds (no package_family) | unit | `uv run --package wiki-io pytest packages/wiki-io/tests/test_link_rewriter_build_table.py -x -k source1` | ❌ W0 | ⬜ pending |
| 46-02-02 | 02 | 2 | MIGRATION-02 | `build_rewrite_table` Source 2 matches `wiki/<kind>/*.md` files to graph entities by name | unit | `uv run --package wiki-io pytest packages/wiki-io/tests/test_link_rewriter_build_table.py -x -k source2` | ❌ W0 | ⬜ pending |
| 46-02-03 | 02 | 2 | MIGRATION-02 | `build_rewrite_table` Source 3 grep-finds inbound links in curated lanes; unresolvable targets logged to migration.log AND added to table with value None | unit | `uv run --package wiki-io pytest packages/wiki-io/tests/test_link_rewriter_build_table.py -x -k source3` | ❌ W0 | ⬜ pending |
| 46-02-04 | 02 | 2 | MIGRATION-01, MIGRATION-02 | `rewrite_vault` walks all 5 curated lanes (concepts/adrs/architecture/sources/work) and applies rewrites in-place atomically | integration | `uv run --package wiki-io pytest packages/wiki-io/tests/integration/test_link_rewriter_integration.py -x -k full_rewrite_vault` | ❌ W0 | ⬜ pending |
| 46-02-05 | 02 | 2 | MIGRATION-01 | `rewrite_vault` returns `RewriteResult` with correct files_scanned/files_modified/rewrites_total/unresolved_total fields | integration | `uv run --package wiki-io pytest packages/wiki-io/tests/integration/test_link_rewriter_integration.py -x -k RewriteResult` | ❌ W0 | ⬜ pending |
| 46-02-06 | 02 | 2 | MIGRATION-05 | REQUIREMENTS.md MIGRATION-05 bullet rewritten per Research §1.5 + ROADMAP.md SC#1 expanded to 5 lanes per CONTEXT D-13 | grep | `grep -q "all 5 curated lanes" .planning/REQUIREMENTS.md && grep -q "/sources/" .planning/ROADMAP.md` | N/A | ⬜ pending |
| 46-03-01 | 03 | 3 | MIGRATION-03 | Idempotency check is the FIRST step of `run_migrate_vault`; re-running prints "already migrated" and exits 0 with no file changes | integration | `uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/test_migrate_vault.py -x -k second_run_no_op` | ❌ W0 | ⬜ pending |
| 46-03-02 | 03 | 3 | MIGRATION-05 | Full cutover composition: write_entities + link_rewriter + git rm + generate_index + update_index + manifest marker + git commit (7 steps, in order) | integration | `uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/test_migrate_vault.py -x -k full_cutover` | ❌ W0 | ⬜ pending |
| 46-03-03 | 03 | 3 | MIGRATION-05 | Full cutover produces exactly one new git commit with the expected title and the staged tree contains entities/, removed dirs, and updated indexes | integration | `uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/test_migrate_vault.py -x -k single_commit` | ❌ W0 | ⬜ pending |
| 46-03-04 | 03 | 3 | MIGRATION-03 | `--force` flag bypasses idempotency check; partial-cutover recovery scenario completes cleanup | integration | `uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/test_migrate_vault.py -x -k force_recovery` | ❌ W0 | ⬜ pending |
| 46-03-05 | 03 | 3 | MIGRATION-05 | `--dry-run` produces expected output sections (entities, rewrites, unresolvable, dirs-to-remove, marker note) and touches no files | snapshot | `uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/test_migrate_vault.py -x -k dry_run` | ❌ W0 | ⬜ pending |
| 46-03-06 | 03 | 3 | MIGRATION-05 | Cutover aborts before commit on any step failure (D-07); exit code 2; no commit created | integration | `uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/test_migrate_vault.py -x -k aborts_before_commit` | ❌ W0 | ⬜ pending |
| 46-03-07 | 03 | 3 | MIGRATION-05 | `--no-write-marker` runs full cutover but does NOT write `.graph-wiki/manifest.json` (testing affordance) | integration | `uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/test_migrate_vault.py -x -k no_write_marker` | ❌ W0 | ⬜ pending |
| 46-03-08 | 03 | 3 | MIGRATION-05 | `cg migrate-vault --help` exits 0 and lists `--dry-run`, `--force`, `--no-write-marker` flags | unit | `uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/test_migrate_vault.py -x -k help_exits_zero` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Each plan creates its own Wave 0 test file (no pre-plan Wave 0 wave needed — pytest is already present and configured). The files listed below as `❌ W0` are created in the same task that adds the production code; the executor writes them empty/failing first, then makes them pass.

- [ ] `packages/wiki-io/tests/test_lint_common_indented_code.py` — Plan 01
- [ ] `packages/wiki-io/tests/test_link_rewriter.py` — Plan 01
- [ ] `packages/wiki-io/tests/test_link_rewriter_build_table.py` — Plan 02
- [ ] `packages/wiki-io/tests/integration/test_link_rewriter_integration.py` — Plan 02
- [ ] `agents/graph-wiki-agent/tests/test_migrate_vault.py` — Plan 03

*Existing infrastructure (`pytest`, `syrupy`) covers all framework needs — no new dev dependencies. No `pytest-asyncio` use in this phase (all SUT is sync).*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Dry-run preview against live `agent-research` vault is sensible | MIGRATION-05 (qualitative) | Visual gate before the actual cutover; the output IS the user-facing acceptance gate per CONTEXT §specifics | Run `cg migrate-vault --dry-run` in `agent-research` root; verify rewrite table covers expected entities (~14 packages, ~9 deps, ~3 domains, ~1 plugin, ~7 suites); confirm 1 package-family file flagged with `⚠ human content detected` warning if present |
| Real cutover ships in a single atomic commit | MIGRATION-05 | The cutover IS the user's commit; cannot automate "did this commit ship in the live repo" in CI | Run `cg migrate-vault` (no `--dry-run`); inspect `git log -1 --stat`; verify single commit titled `feat(46): v1.8 entity restructure cutover` |
| Nested-fence edge case behavior matches documented v1.8 limitation | MIGRATION-04 (qualitative) | The known limitation cannot be automatically asserted as "correct" — it's documented, not solved | Read `packages/wiki-io/tests/test_link_rewriter.py::test_rewrite_text_nested_fence_known_limitation`; confirm the test is either `xfail` or documents the actual v1.8 behavior in an assertion comment |

*All structural / contract behaviors have automated verification.*

---

## Validation Sign-Off

- [x] All tasks have automated verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 60s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
