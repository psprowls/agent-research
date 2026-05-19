---
phase: 17-vault-io-bug-fixes
verified: 2026-05-19T00:00:00Z
status: gaps_found
score: 4/5 must-haves verified
overrides_applied: 0
gaps:
  - truth: "WSRES-02 fully satisfied: workspace dir excluded from detection across ALL call paths (detect_containers.main, init_vault._resolve_pinned_containers, scan_monorepo._discover_heuristic)"
    status: partial
    reason: "workspace_path exclusion is wired only through detect_containers.main() (the CLI entry point). init_vault._resolve_pinned_containers calls _detect_containers(repo) with no workspace_path argument (line 86), so in v2 layout the workspace dir can still leak into the layout block written by /graph-wiki:init. scan_monorepo._discover_heuristic has no workspace_dir filter on its rglob('pyproject.toml') walk. The roadmap SC#4 wording ('does not appear in its own layout block as a docs container') is satisfied at the CLI entry point only."
    artifacts:
      - path: "packages/vault-io/src/vault_io/init_vault.py"
        issue: "_resolve_pinned_containers calls _detect_containers(repo) at line 86 without workspace_path; workspace dir not excluded during init_wiki"
      - path: "packages/vault-io/src/vault_io/scan_monorepo.py"
        issue: "_discover_heuristic rglob walk has no workspace segment filter; descends into graph-wiki/ if present"
    missing:
      - "Plumb workspace_path through _resolve_pinned_containers and its call site in init_wiki"
      - "Add workspace segment skip to _discover_heuristic rglob loop (analogous to node_modules / .venv filter)"
---

# Phase 17 — Verification Report

**Phase Goal:** All three vault-io behavioral bugs are fixed so scan reports accurate diffs, token counts are stamped correctly, and repo/container resolution works at the v2 workspace layout
**Verified:** 2026-05-19
**Status:** gaps_found — 4/5 roadmap success criteria verified; SC#4 partially satisfied (CLI path only; init and scan call paths unguarded)
**Re-verification:** No — initial verification (enhancing the executor-drafted 17-VERIFICATION.md)

---

## Goal Achievement

### Observable Truths (Roadmap Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `/graph-wiki:scan` on a healthy 7-package vault reports 0 deleted entries for the four companion pages per package (was 28) | VERIFIED | 4/4 tests in test_scan_companion_fold.py pass; `test_compute_diff_no_phantom_deletes` asserts 0 phantom deletes against round-trip-vault fixture |
| 2 | After scan, all wiki pages previously without tokens show a non-zero token count in their frontmatter | VERIFIED | Live re-stamp committed to wiki repo at 80a4739; grep of real pages returns 0 at `tokens: 0` |
| 3 | `detect_containers --json` returns the repo-root containers (not an empty list) when the wiki lives at `<workspace>/wiki/` | VERIFIED | 4/4 tests in test_detect_containers.py pass; test_v2_layout_finds_repo_containers asserts `packages` in results; detect_containers.main() uses `wiki, repo = resolve_wiki_and_repo()` |
| 4 | The workspace directory itself does not appear in its own layout block as a `docs` container | PARTIAL | test_workspace_path_excluded passes for the detect() function called directly; BUT _resolve_pinned_containers (line 86 init_vault.py) calls _detect_containers(repo) without workspace_path — workspace dir not excluded during /graph-wiki:init; _discover_heuristic has no workspace segment filter |
| 5 | Unit and integration tests for scan companion folding and CountTokens API shape pass under `uv run --package vault-io pytest` | VERIFIED | 86 passed, 0 failed (full unit suite); integration test exists and skips by default |

**Score:** 4/5 truths verified (SC#4 is PARTIAL — BLOCKER)

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `packages/vault-io/src/vault_io/scan_monorepo.py` | Companion-fold filter via `_parse_workflow_hints` | VERIFIED | fold_companions parameter at 4 call sites; imports `_parse_workflow_hints` from lint module |
| `packages/vault-io/tests/test_scan_companion_fold.py` | 4 unit tests covering companion fold | VERIFIED | 4 tests, all pass: test_load_existing_skips_companions, test_layout_pinned_package_skips_companions, test_apps_not_filtered, test_compute_diff_no_phantom_deletes |
| `packages/vault-io/src/vault_io/update_tokens.py` | Fixed count_tokens using converse shape and inputTokens | VERIFIED | input={"converse":{...}} at line 42; response["inputTokens"] at line 50; no inputTokenCount, no content=[{...}] |
| `packages/vault-io/tests/test_update_tokens.py` | 2 mocked unit tests locking request shape and response key | VERIFIED | test_count_tokens_request_shape, test_count_tokens_returns_input_tokens; assert_called_once_with with full converse payload |
| `packages/vault-io/tests/integration/__init__.py` | Empty package marker | VERIFIED | File exists |
| `packages/vault-io/tests/integration/test_count_tokens_live.py` | Gated integration test | VERIFIED | CODE_WIKI_RUN_INTEGRATION gate; @pytest.mark.integration; test_count_tokens_real_bedrock; skipped by default |
| `packages/vault-io/src/vault_io/init_vault.py` | WSRES-01: uses resolve_wiki_and_repo() second return value | VERIFIED | Line 305: `wiki, repo = resolve_wiki_and_repo()` — wiki.parent is gone |
| `packages/vault-io/src/vault_io/detect_containers.py` | WSRES-01+02: workspace-aware repo resolution + workspace_path exclusion | PARTIAL | main() is correct (line 182, 187); detect() has workspace_path param with D-11 guard; BUT _resolve_pinned_containers bypass not addressed |
| `packages/vault-io/tests/test_detect_containers.py` | 4 synthetic-fixture tests for v2 layout and v1 guard | VERIFIED | test_v2_layout_finds_repo_containers, test_workspace_path_excluded, test_v1_layout_guard, test_v2_synthetic_repo all pass |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| scan_monorepo._collect | lint/workflow_hints._parse_workflow_hints | `from vault_io.lint.workflow_hints import _parse_workflow_hints` | WIRED | Line 47 of scan_monorepo.py; used at lines 640, 689 |
| detect_containers.main() | resolve_wiki_and_repo() | tuple unpack `wiki, repo = resolve_wiki_and_repo()` | WIRED | Line 182 detect_containers.py |
| detect_containers.main() | detect(repo, workspace_path=wiki.parent) | positional + kwarg call | WIRED | Line 187 detect_containers.py |
| init_vault.main() | resolve_wiki_and_repo() | tuple unpack `wiki, repo = resolve_wiki_and_repo()` | WIRED | Line 305 init_vault.py |
| init_vault._resolve_pinned_containers | detect(repo, workspace_path=?) | _detect_containers(repo) — workspace_path MISSING | NOT_WIRED | Line 86 init_vault.py: `records = _detect_containers(repo)` — no workspace_path passed; WSRES-02 exclusion bypassed for init path |
| update_tokens.count_tokens | boto3 bedrock-runtime.count_tokens | input={"converse":{...}} | WIRED | Lines 40-49 update_tokens.py |
| update_tokens.count_tokens response | inputTokens field | `response["inputTokens"]` | WIRED | Line 50 update_tokens.py |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| SCAN-01 | 17-01-PLAN.md | _load_existing_pages folds companion files into parent slug | SATISFIED | fold_companions=True at package call sites; _parse_workflow_hints import confirmed |
| SCAN-02 | 17-01-PLAN.md | Unit test against fixture asserts 0 deleted for companions | SATISFIED | test_compute_diff_no_phantom_deletes PASSED |
| TOK-01 | 17-02-PLAN.md | count_tokens() uses correct boto3 bedrock-runtime.count_tokens parameter shape | SATISFIED | input={"converse":{...}}; no content=[{...}]; no inputTokenCount |
| TOK-02 | 17-02-PLAN.md | Unit test mocks boto3 client, asserts request payload + response key; gated integration test | SATISFIED | test_count_tokens_request_shape and test_count_tokens_returns_input_tokens pass; integration test gated by CODE_WIKI_RUN_INTEGRATION |
| TOK-03 | 17-04-PLAN.md | Existing wiki pages with tokens: 0 are re-stamped | SATISFIED | grep of real wiki returns 0 at `tokens: 0`; wiki commit 80a4739 exists |
| WSRES-01 | 17-03-PLAN.md | init_vault.py and detect_containers.py use resolve_wiki_and_repo() second return value | SATISFIED | Both files confirmed: wiki, repo = resolve_wiki_and_repo() |
| WSRES-02 | 17-03-PLAN.md | detect_containers.detect() excludes resolved workspace path from classification | PARTIAL — BLOCKER | detect() function itself is correct with D-11 guard; BUT init_vault._resolve_pinned_containers calls _detect_containers(repo) without workspace_path (line 86); scan_monorepo._discover_heuristic rglob has no workspace filter |
| WSRES-03 | 17-03-PLAN.md | Test runs detector against fixture repo, asserts correct results | SATISFIED | 4 tests in test_detect_containers.py pass |

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| update_tokens.py | 107 | Baseline construction uses extra `\n` vs on-disk content | Warning | Token count inflated marginally; idempotency holds but count != disk text with tokens stripped (per WR-01 in 17-REVIEW.md) |
| update_tokens.py | 103,121 | parts[1].strip().split("\n") computed twice | Info | Minor redundancy (IN-02 in 17-REVIEW.md) |
| update_tokens.py | 104 | tokens: line filter doesn't handle `tokens:42` (no space) | Warning | Duplicate tokens key on non-canonical YAML variant; idempotency break (WR-03 in 17-REVIEW.md) |
| init_vault.py | 86 | _detect_containers(repo) called without workspace_path | BLOCKER | WSRES-02 exclusion bypassed for /graph-wiki:init path; workspace dir can pollute layout block |
| scan_monorepo.py | 550 | _discover_heuristic rglob has no workspace segment filter | Warning | workspace dir can yield spurious pyproject.toml in v2 layout heuristic scan (CR-01 second half per 17-REVIEW.md) |

No TBD, FIXME, or XXX markers found in any phase-17-modified source file.

---

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| update_tokens.py uses converse shape | `grep -n "input=" packages/vault-io/src/vault_io/update_tokens.py` | line 42: `input={` | PASS |
| update_tokens.py reads inputTokens | `grep -n "inputTokens\|inputTokenCount" packages/vault-io/src/vault_io/update_tokens.py` | inputTokens at line 50; 0 inputTokenCount matches | PASS |
| detect() has workspace_path param | Python introspection | signature confirmed | PASS |
| init_vault._resolve_pinned_containers passes workspace_path | `grep -n "_detect_containers" init_vault.py` | line 86: `_detect_containers(repo)` — no workspace_path | FAIL |
| Real wiki has no pages stuck at tokens: 0 (non-template) | `grep -rn "^tokens: 0" ~/Personal/wiki/deep-agents \| grep -v ".templates" \| wc -l` | 0 | PASS |
| Full unit suite passes | `uv run --package vault-io pytest -q (unit only)` | 86 passed | PASS |

---

## Human Verification Required

None — all verifiable items resolved programmatically.

---

## Gaps Summary

**One BLOCKER gap (CR-01 from 17-REVIEW.md):**

SC#4 ("The workspace directory itself does not appear in its own layout block as a `docs` container") is achieved **at the CLI detection entry point** (`detect_containers.main()` → `detect(repo, workspace_path=wiki.parent)`). The four tests in `test_detect_containers.py` exercise this path and pass.

However, WSRES-02 is **not fully wired** through two additional call paths that matter in practice:

1. **`init_vault._resolve_pinned_containers` (line 86):** Calls `_detect_containers(repo)` without `workspace_path`. When `/graph-wiki:init` runs against a v2-layout repo, the workspace dir (`graph-wiki/`) will still appear in the detection records (classified as `ambiguous` or `docs`) and may pollute the layout block written to `wiki/CLAUDE.md`. The SC says "does not appear in its own layout block" — this path can produce exactly that failure.

2. **`scan_monorepo._discover_heuristic`:** The `rglob("pyproject.toml")` walk at line 550 has no workspace segment filter. If the workspace dir (`graph-wiki/`) contains a `pyproject.toml`, it will be picked up as a spurious Python package during heuristic scan. This affects `/graph-wiki:scan` when no pinned layout is found.

**Verdict:** `gaps_found`. The phase goal states "repo/container resolution works at the v2 workspace layout" — the fix is structurally present in `detect()` but not propagated to the two callers that drive actual wiki bootstrap and scan. The roadmap SC#4 is satisfiable via the unit tests only because they call `detect()` directly; the production code paths that emit the layout block remain unguarded.

**Recommendation:** The gap is actionable with a small follow-up. It does NOT require re-doing the current plans — the fix in `detect()` is correct and just needs to be plumbed through `_resolve_pinned_containers` and `_discover_heuristic`. This can be a targeted patch in a follow-up plan or as part of Phase 19 debt cleanup. If the developer accepts that the CLI-level exclusion is sufficient for the current milestone scope (the layout block is written interactively and the user can skip the workspace dir when prompted), an override can be applied.

---

## Original Executor Evidence (SC Sections — Preserved from 17-04 Draft)

### SC#1 — `/graph-wiki:scan` reports 0 deleted entries for companion pages

Evidence: `uv run --package vault-io pytest packages/vault-io/tests/test_scan_companion_fold.py -v`

```
packages/vault-io/tests/test_scan_companion_fold.py::test_load_existing_skips_companions PASSED [ 25%]
packages/vault-io/tests/test_scan_companion_fold.py::test_layout_pinned_package_skips_companions PASSED [ 50%]
packages/vault-io/tests/test_scan_companion_fold.py::test_apps_not_filtered PASSED [ 75%]
packages/vault-io/tests/test_scan_companion_fold.py::test_compute_diff_no_phantom_deletes PASSED [100%]

4 passed in 0.06s
```

All 4 tests pass. `test_compute_diff_no_phantom_deletes` specifically asserts that `compute_diff()` returns 0 `deleted` entries when a fixture vault contains valid companion pages (`api`, `context`, `patterns`, `work`) for a package slug. The two-pass companion-fold filter in `_load_existing_pages._collect()` prevents 28+ phantom deleted entries from appearing in scan diffs on a healthy vault.

---

### SC#2 — All wiki pages previously at `tokens: 0` show non-zero token count

**Discovery during execution:** The BEFORE count of 17 (recorded at preflight, Task 1) represents files entirely within the `.templates/` dotdir (`~/Personal/wiki/deep-agents/.templates/`). The `update_tokens.iter_pages()` function skips dotdir paths by design (any path component starting with `.`), so template files are intentionally excluded from re-stamping. Template files contain placeholder content and `tokens: 0` is their correct long-term value.

The 8 real wiki pages (non-dotdir) had **no `tokens:` field at all** (not `tokens: 0`) because the CountTokens API was broken before phase 17's TOK-01/02 fix. These are the pages that required stamping.

**BEFORE:** `grep -rn "^tokens: 0" ~/Personal/wiki/deep-agents | wc -l` → **17** (all in `.templates/`, excluded from processing by `iter_pages()`)

**Real pages needing stamps:** 8 pages with no `tokens:` field (confirmed by dry-run before execution).

**Re-stamp transcript (`/tmp/17-tok03-restamp.log`):**

```
Target wiki: /Users/pat/Personal/wiki/deep-agents
Model: anthropic.claude-3-5-haiku-20241022-v1:0
Region: us-east-1

Updated 8 pages • Unchanged 0 pages • Skipped 2 pages

  [updated] deep-agents/agents/code-wiki-agent/code-wiki-agent.md
  [updated] deep-agents/packages/eval-harness/eval-harness.md
  [updated] deep-agents/packages/model-adapter/model-adapter.md
  [updated] deep-agents/packages/subagent-runtime/subagent-runtime.md
  [updated] deep-agents/packages/vault-io/vault-io.md
  [updated] deep-agents/packages/workspace-io/workspace-io.md
  [updated] deep-agents/plugins/graph-wiki/graph-wiki.md
  [updated] deep-agents/sources/otel-story-observability.md
  [skipped] deep-agents/CLAUDE.md
  [skipped] deep-agents/concepts/otel-story-of-observability.md
```

**Note on model ID:** The plan's default model `us.anthropic.claude-haiku-4-5-20251001-v1:0` (cross-region inference profile) does not support the Bedrock CountTokens API — it returns `ValidationException: The provided model doesn't support counting tokens`. The non-prefixed model `anthropic.claude-3-5-haiku-20241022-v1:0` was used instead (confirmed working via API test before execution). The TOK-01/02 fix in plan 17-02 corrected the request *shape*; this execution also resolved the model ID mismatch.

**AFTER:** `grep -rn "^tokens: 0" ~/Personal/wiki/deep-agents | wc -l` → **17** (same `.templates/` files, unchanged — intentionally at 0)

**AFTER for real pages:** `grep -rn "^tokens: 0" ~/Personal/wiki/deep-agents | grep -v ".templates" | wc -l` → **0** (all real wiki pages now have non-zero token counts)

**Sample of re-stamped pages** (from `git diff HEAD~1 -- '*.md'` in the wiki repo):

```diff
 language: python
 updated: 2024-03-28
+tokens: 1076

 ---

+tokens: 809

 ---

 exports: []
 updated: 2024-03-13
+tokens: 468

 ---

 language: python
 updated: 2024-05-16
+tokens: 447

 ---

+tokens: 863

 ---

   - pending_updates
   - warn_if_stale
+tokens: 650
```

**Wiki-side commit SHA:** `80a4739b198419b9080601d5818e938734f3e7a9`

Commit subject: `chore(tokens): re-stamp pages after Bedrock CountTokens fix`

---

### SC#3 — `detect_containers --json` returns repo-root containers under v2 layout

Evidence: `uv run --package vault-io pytest packages/vault-io/tests/test_detect_containers.py -v`

```
packages/vault-io/tests/test_detect_containers.py::test_v2_layout_finds_repo_containers PASSED [ 25%]
packages/vault-io/tests/test_detect_containers.py::test_workspace_path_excluded PASSED [ 50%]
packages/vault-io/tests/test_detect_containers.py::test_v1_layout_guard PASSED [ 75%]
packages/vault-io/tests/test_detect_containers.py::test_v2_synthetic_repo PASSED [100%]

4 passed in 0.03s
```

`test_v2_layout_finds_repo_containers` and `test_v2_synthetic_repo` specifically verify that `detect()` correctly identifies `packages/` as a container under v2 workspace layout (`<repo>/graph-wiki/wiki/` structure), using the `resolve_wiki_and_repo()` second return value for `repo_root` (WSRES-01 fix).

---

### SC#4 — The workspace dir does not appear in its own layout block as a `docs` container

Evidence: same test file output; `test_workspace_path_excluded` specifically covers this:

```
packages/vault-io/tests/test_detect_containers.py::test_workspace_path_excluded PASSED [ 50%]
```

This test asserts that when `workspace_path` is provided to `detect()` and is a proper subdir of `repo_root`, the workspace directory itself is not classified as a `docs` container. The D-11 v1-layout guard (`test_v1_layout_guard`) ensures the exclusion does not apply when `workspace_path == repo_root` (v1 layout where wiki is at the repo root).

**Verifier note (CR-01):** The test and the `detect()` function are correct. However, `init_vault._resolve_pinned_containers` at line 86 calls `_detect_containers(repo)` without `workspace_path`, bypassing this exclusion for the `/graph-wiki:init` production path. The SC is satisfied at the `detect_containers.main()` CLI entry point and via direct `detect()` calls, but not via `init_wiki`. See Gaps Summary.

---

### SC#5 — Unit and integration tests pass under `uv run --package vault-io pytest`

Evidence:
- **Unit suite:** `uv run --package vault-io pytest` (unit only, ignoring integration/) → exit 0, **86 passed** in 39.25s (verified by this verifier run)
- **Integration suite (gated):** `CODE_WIKI_RUN_INTEGRATION=1 uv run --package vault-io pytest -m integration` → **1 test** (`test_count_tokens_real_bedrock`); skipped by default per `docs/testing.md` D-10 pattern

The executor's report of 563 passed / 32 skipped reflects the full workspace suite including other packages; the vault-io package suite is 86 unit tests.

---

*Phase 17 verification enhanced: 2026-05-19.*
*Verifier: Claude (gsd-verifier)*
*Note: Enhanced from executor-drafted 17-VERIFICATION.md; frontmatter and gap analysis added; SC sections preserved verbatim from draft with one verifier note added to SC#4.*
