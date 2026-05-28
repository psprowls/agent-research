---
phase: 53
slug: wiki-filename-cutover
status: draft
nyquist_compliant: false
wave_0_complete: true
created: 2026-05-28
---

# Phase 53 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (existing) |
| **Config file** | `packages/wiki-io/pyproject.toml` (pytest section) |
| **Quick run command** | `uv run --package wiki-io pytest packages/wiki-io/tests/ -x` |
| **Full suite command** | `uv run pytest` (workspace-wide) |
| **Estimated runtime** | ~15s (quick), ~90s (full workspace) |

---

## Sampling Rate

- **After every task commit:** Run quick command
- **After every plan wave:** Run full workspace test command
- **Before `/gsd:verify-work`:** Full workspace suite green + manual UAT recorded in `53-UAT.md`
- **Max feedback latency:** 90 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 53-01-01 | 01 | 1 | WIKI-FN-05, WIKI-FN-06 | — | N/A (markdown edit) | doc-diff | `grep -F "encode_slug" .planning/REQUIREMENTS.md` returns at least one hit (the new verification text); `grep -F "migrate-vault\` (or equivalent one-shot" .planning/REQUIREMENTS.md` returns zero hits (old text gone) | ✅ existing | ⬜ pending |
| 53-01-02 | 01 | 1 | WIKI-FN-05, WIKI-FN-06 | — | N/A (markdown edit) | doc-diff | `grep -F "migrate-vault" .planning/ROADMAP.md` (in §Phase 53) returns zero hits; `grep -F "regenerated" .planning/ROADMAP.md` returns at least one hit in §Phase 53 | ✅ existing | ⬜ pending |
| 53-02-01 | 02 | 2 | WIKI-FN-05 | — | Import-time signature shrink (negative test) | unit | `python -c "from wiki_io.entity_writer import encode_slug" 2>&1 \| grep -q ImportError` exits 0 | ✅ existing | ⬜ pending |
| 53-02-02 | 02 | 2 | WIKI-FN-05 | — | Call-site rewrites (link_rewriter, index_generator, scanner) | integration | `grep -rn "encode_slug\|decode_slug" packages/ agents/ --include="*.py"` returns 0 hits | ✅ existing | ⬜ pending |
| 53-02-03 | 02 | 2 | WIKI-FN-06 | — | N/A (test fixture) | integration | `uv run --package wiki-io pytest packages/wiki-io/tests/ -v` exits 0; round-trip fixture filenames match short-form pattern | ✅ existing | ⬜ pending |
| 53-02-04 | 02 | 2 | WIKI-FN-05, WIKI-FN-06 | — | N/A | integration | `uv run pytest` (workspace) exits 0 | ✅ existing | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Wave 0 is empty for Phase 53 — all required test infrastructure exists (pytest, hypothesis from
Phase 52, the wiki-io test directory). No new framework or scaffolding required.

Existing infrastructure covers all phase requirements.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Vault regeneration produces short-form filenames in `wiki/index.md` and entity directories | WIKI-FN-06 | Crosses repo boundary (`~/Personal/graph-wiki/agent-research` is a separate vault, not part of `agent-research` repo). Single-user gating decision recorded in CONTEXT D-08. | After plan 53-02 merges: 1) `rm -rf ~/Personal/graph-wiki/agent-research/wiki/{packages,dependencies,domain,plugin,test-suites,app}/`. 2) `uv run cg update --full`. 3) `uv run graph-wiki-agent scan`. 4) Inspect `~/Personal/graph-wiki/agent-research/wiki/index.md` — confirm entries like `pkg_eval-harness`, `app_graph-wiki-agent`, `dep_langchain-aws`. 5) Spot-check 2-3 entity files under `wiki/entities/`. 6) Record findings in `.planning/phases/53-wiki-filename-cutover/53-UAT.md`. |
| Spot-check no `pkg__org__repo__name`-style orphan files remain | WIKI-FN-05 | Same as above. | Step 5 above includes: `find ~/Personal/graph-wiki/agent-research/wiki/entities -name "*__*__*__*.md"` returns zero results (long-form filenames are gone after manual delete + regen). |

All phase behaviors that block automated verification are covered by `grep` + pytest. The
vault regen is the only manual gate and is the explicit UAT contract from CONTEXT D-08/D-09.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (none required)
- [x] No watch-mode flags
- [x] Feedback latency < 90s
- [ ] `nyquist_compliant: true` set in frontmatter (flipped after plans finalized + reviewed)

**Approval:** pending
