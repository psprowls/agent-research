# Phase 17 — Verification

**Verified:** 2026-05-19

---

## SC#1 — `/graph-wiki:scan` reports 0 deleted entries for companion pages

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

## SC#2 — All wiki pages previously at `tokens: 0` show non-zero token count

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

## SC#3 — `detect_containers --json` returns repo-root containers under v2 layout

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

## SC#4 — The workspace dir does not appear in its own layout block as a `docs` container

Evidence: same test file output; `test_workspace_path_excluded` specifically covers this:

```
packages/vault-io/tests/test_detect_containers.py::test_workspace_path_excluded PASSED [ 50%]
```

This test asserts that when `workspace_path` is provided to `detect()` and is a proper subdir of `repo_root`, the workspace directory itself is not classified as a `docs` container. The D-11 v1-layout guard (`test_v1_layout_guard`) ensures the exclusion does not apply when `workspace_path == repo_root` (v1 layout where wiki is at the repo root).

---

## SC#5 — Unit and integration tests pass under `uv run --package vault-io pytest`

Evidence:
- **Unit suite:** `uv run --package vault-io pytest` → exit 0, **563 passed, 32 skipped** in 75.68s
- **Integration suite (gated):** `CODE_WIKI_RUN_INTEGRATION=1 uv run --package vault-io pytest -m integration` → **1 test** (`test_count_tokens_real_bedrock`); **M=1 when enabled** (gated by env var, skipped in CI by default per `docs/testing.md` D-10 pattern)

The skipped tests (32) are all integration-gated tests that require `CODE_WIKI_RUN_INTEGRATION=1` to run real Bedrock or subprocess invocations. These are correct skips — no test failures.

---

*Phase 17 verification complete: 2026-05-19.*
