# Phase 34: Brand Sweep — Research

**Researched:** 2026-05-25
**Status:** Research complete

## Research scope

CONTEXT.md is unusually concrete for this phase (18 locked decisions with diffs, exact strings, allowlist content, and verification commands). Research is therefore narrow: verify the assumptions in CONTEXT.md against the current tree, identify any references CONTEXT.md missed, and confirm the brand-grep gate's invocation contract.

## Findings

### F-01: `.brand-grep-allow` does NOT exist at repo root

CONTEXT.md D-15 / D-16 assume the file exists and the phase only ADDS entries. Reality: `bash scripts/check-brand.sh` currently exits 2 with `BRAND-04 FAIL: .brand-grep-allow not found at repo root`. The phase must CREATE `.brand-grep-allow` (not just append to it).

**Impact:** D-15 / D-16 are still correct content-wise, but the plan must produce the full file (with the deprecated env var substring + the packages.py path substring), not append to a missing file.

### F-02: `sys` is already imported in `update.py`

CONTEXT.md D-09 notes "`sys` import needs to be added at the top of `update.py` if not already imported". Reality: `update.py` line 9 already has `import sys`. The D-09 refactor needs no import edit.

### F-03: Full lattice/LATTICE inventory in `packages/graph-io/`

```
README.md:1                              # lattice-graph-core
README.md:3                              Code-graph core for the [lattice](../../README.md) ecosystem.
README.md:5                              SQLite schema + store at `<repo>/.lattice/graph/code.db`
README.md:12                             The Claude Code plugin shell lives separately at `plugins/lattice-graph/`.
src/graph_io/cli/main.py:45              description="lattice code graph CLI"
src/graph_io/packages.py:17              _SKIP_REPO_PREFIXES = ("lattice/",)        ← FUNCTIONAL, KEEP
src/graph_io/update.py:154               os.environ.get("LATTICE_GRAPH_LOCK_TIMEOUT_MS")
tests/test_sync_wiki.py:15               ws = tmp_path / "lattice"
tests/test_sync_wiki.py:17               (ws / ".lattice.yaml").write_text(...)
tests/test_cli_exit_codes.py:130         env = {**os.environ, "LATTICE_GRAPH_LOCK_TIMEOUT_MS": "200"}
tests/test_cli_sync_wiki.py:29           "lattice/.lattice.yaml": "registered_plugins: []\n"
tests/test_cli_sync_wiki.py:64           "lattice/.lattice.yaml": "registered_plugins: []\n"
tests/test_packages.py:112-115           test_refresh_skips_lattice_dir_manifests  ← FUNCTIONAL, KEEP
```

11 brand hits total. 2 are FUNCTIONAL (BRAND-04 carve-outs); 9 are brand text to rewrite.

### F-04: README has 4 lattice refs, not 3

CONTEXT.md §domain item 1 references 3 README changes (title, tagline, path). Line 12 (`plugins/lattice-graph/`) is a 4th brand ref and is covered under D-04 ("Claude's Discretion"). Path `plugins/lattice-graph/` doesn't exist in this monorepo (actual path is `plugins/graph-wiki/`). The plan should rebrand line 12 to point at the real path:

```diff
-The Claude Code plugin shell lives separately at `plugins/lattice-graph/`.
+The Claude Code plugin shell lives separately at `plugins/graph-wiki/`.
```

### F-05: `.lattice.yaml` in tests is stale fixture data, NOT functional

`test_sync_wiki.py` and `test_cli_sync_wiki.py` create `.lattice.yaml` workspace marker files in test fixtures. The functional workspace marker is `.graph-wiki.yaml` (verified in `packages/workspace-io/src/workspace_io/paths.py:12` — `Path(workspace) / ".graph-wiki.yaml"`). The tests pass anyway because `sync_wiki.run()` does not read the manifest file (it reads from the SQLite graph + wiki directory listings).

**Implication:** `.lattice.yaml` strings in test fixtures are pure brand text — rebrand to `.graph-wiki.yaml` per D-11. Tests will continue to pass (the fixture file existence matters only as a marker that the tests aren't asserting against).

### F-06: `test_refresh_skips_lattice_dir_manifests` is the functional carve-out

Per D-12 (test_packages.py): the test name `test_refresh_skips_lattice_dir_manifests` and its fixture `tmp_path / "lattice" / "some-tool"` MUST stay literal — they exercise `_SKIP_REPO_PREFIXES = ("lattice/",)` (a functional skip filter, not brand text). Verified: the test creates a `lattice/some-tool/pyproject.toml`, calls `packages.refresh()`, and asserts the `"tool"` package is NOT picked up — proving the skip filter works.

This is the ONLY test method that must preserve `lattice/` literals.

### F-07: env-var-test in test_cli_exit_codes.py is a single subprocess call

`tests/test_cli_exit_codes.py:130` sets `LATTICE_GRAPH_LOCK_TIMEOUT_MS=200` to exercise the lock-timeout-honored behavior (asserts `elapsed_ms < 5000`). Per D-13: rename to `GRAPH_WIKI_LOCK_TIMEOUT_MS=200`. The test continues to assert the timeout behavior. Pure string replacement.

### F-08: `scripts/check-brand.sh` allowlist semantics

Reading the script carefully:

```bash
HITS=$(grep -rEl ... packages/ agents/ plugins/ .planning/ CLAUDE.md 2>/dev/null \
    | grep -vF -f <(grep -vE '^[[:space:]]*(#|$)' "$ALLOWLIST") || true)
```

The first `grep -rEl` returns a list of **file paths** that contain brand-trigger strings. The second `grep -vF -f <allowlist>` removes paths matching any allowlist substring. So allowlist entries are tested as substrings against **file paths only**, NOT against file content.

**Implication for D-15:** `LATTICE_GRAPH_LOCK_TIMEOUT_MS` as a substring will only match if it appears in a file PATH (it won't — no file is named that). To allowlist the `update.py` hit, the entry must be a **path substring** like `packages/graph-io/src/graph_io/update.py`. D-15's recommended literal `LATTICE_GRAPH_LOCK_TIMEOUT_MS` as a content substring **will not work**.

This contradicts D-15's stated content but matches D-16's path-based form. The plan must use path-based entries for both. CONTEXT.md §Claude's Discretion (item 4) explicitly anticipates this — "Planner verifies which form check-brand.sh actually filters on... entries should be file-path substrings primarily."

**Resolved allowlist content:**

```
# Phase 34 BRAND-03: deprecated env var alias kept for one-milestone backward compat (D-10, D-15)
packages/graph-io/src/graph_io/update.py

# BRAND-04 carve-out: functional _SKIP_REPO_PREFIXES filter (per PITFALLS.md, D-16)
packages/graph-io/src/graph_io/packages.py

# BRAND-04 carve-out: functional test of the lattice/ skip filter (D-12)
packages/graph-io/tests/test_packages.py
```

Three path-substring entries. (test_packages.py needs an entry because the surviving `test_refresh_skips_lattice_dir_manifests` test method keeps literal `lattice/` references that will be flagged by check-brand.sh.)

### F-09: pre-flight baseline

`bash scripts/check-brand.sh > /tmp/preflight.txt 2>&1` currently exits 2 (missing allowlist), so the planner cannot get a clean baseline-hit count BEFORE creating `.brand-grep-allow`. The "create allowlist first, then sweep" wave ordering from D-Discretion item 5 still applies, but the planner should verify by inspection (the 11 hits from F-03), not by running the script pre-sweep.

After creating `.brand-grep-allow` with just the 3 carve-out entries and BEFORE editing any source files, `check-brand.sh` should report ~6 unallowlisted hits (the 9 brand-text hits MINUS the 2 carve-outs covered by the new entries; plus 1 in `update.py` covered by the env-var entry). Post-sweep, those 9 hits become 3 (the carve-outs only), all of which are allowlisted → exit 0.

### F-10: Phase 33 disjointness confirmed

CONTEXT.md §code_context notes Phase 34 cli/main.py line 45 is disjoint from Phase 33's `_SUBCOMMANDS` dict edits (line 28-42). Verified: `_SUBCOMMANDS` ends at line 42 (`}`), blank line 43-44, parser construction starts line 45. Phase 34's edit to the single string `description="..."` will not collide with Phase 33 regardless of execution order.

## Validation Architecture

Per CONTEXT.md D-18, the four success criteria map to deterministic shell checks plus three manual env-var scenarios. The plan must produce VERIFICATION.md with these scenarios. No new test files are introduced; existing tests are amended per D-11/D-13.

### Test coverage gap (accepted)

Per D-14: the SC#3 deprecation-warning behavior (stderr message contents) has no automated test. The planner accepts this gap and routes verification through manual scenarios in VERIFICATION.md.

### Functional regression risk

Three areas to watch:
1. `_default_lock_timeout()` refactor (D-09) — existing `test_cli_exit_codes.py:130` test exercises the timeout-honored path with the deprecated env var. Renaming to `GRAPH_WIKI_LOCK_TIMEOUT_MS` per D-13 keeps coverage for the new-var-only path; the both-set + old-only-set branches are uncovered by automated tests.
2. `packages.refresh()` skip filter — `test_refresh_skips_lattice_dir_manifests` covers the `lattice/` carve-out. Keep this test verbatim.
3. README `~/.lattice/graph/code.db` reference is prose only; no runtime code reads from that path (the actual DB path comes from `workspace_io.paths.graph_dir()`). README rewrite is purely documentation.

## Open questions

None — CONTEXT.md and the findings above cover the full decision space. The planner has unambiguous diffs for every edit, an explicit allowlist body, and a closed verification flow.

## RESEARCH COMPLETE
