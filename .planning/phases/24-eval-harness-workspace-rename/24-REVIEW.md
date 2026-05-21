---
phase: 24-eval-harness-workspace-rename
reviewed: 2026-05-20T00:00:00Z
depth: standard
files_reviewed: 25
files_reviewed_list:
  - packages/eval-harness/src/eval_harness/sweep.py
  - packages/eval-harness/src/eval_harness/baseline.py
  - packages/eval-harness/src/eval_harness/structural.py
  - packages/eval-harness/src/eval_harness/isolation.py
  - packages/eval-harness/src/eval_harness/divergence/linter.py
  - packages/eval-harness/src/eval_harness/divergence/ingestor.py
  - packages/eval-harness/src/eval_harness/divergence/scanner.py
  - packages/eval-harness/src/eval_harness/divergence/code_reader.py
  - packages/eval-harness/src/eval_harness/divergence/synthesizer.py
  - packages/eval-harness/src/eval_harness/divergence/librarian.py
  - packages/eval-harness/src/eval_harness/divergence/metric.py
  - packages/eval-harness/tests/conftest.py
  - packages/eval-harness/tests/eval_helpers.py
  - packages/eval-harness/tests/test_sweep.py
  - packages/eval-harness/tests/test_role_sweep.py
  - packages/eval-harness/tests/test_baseline.py
  - packages/eval-harness/tests/test_structural.py
  - packages/eval-harness/tests/test_isolation.py
  - packages/eval-harness/tests/test_divergence.py
  - packages/eval-harness/tests/test_divergence_metric.py
  - packages/eval-harness/tests/test_divergence_checks.py
  - packages/eval-harness/tests/test_two_gate_scorer.py
  - packages/eval-harness/tests/eval/test_sweep_eval.py
  - eval/README.md
  - scripts/check-brand.sh
findings:
  critical: 3
  warning: 4
  info: 2
  total: 9
status: issues_found
---

# Phase 24: Code Review Report

**Reviewed:** 2026-05-20
**Depth:** standard
**Files Reviewed:** 25
**Status:** issues_found

## Summary

Phase 24 is an internal rename refactor: public eval-harness functions now take
`workspace_path: Path` and derive `wiki` internally via
`workspace_io.paths.wiki_dir(workspace_path)`. Divergence helpers retain bare
`wiki: Path`. CLI flag renamed `--vault` → `--workspace`. `EvalWorktree` ctor
arg renamed `source_vault` → `source_wiki`. Baseline JSON key renamed
`vault_content_hash` → `wiki_content_hash`.

The rename itself is mechanically consistent across the source tree (the new
BRAND-WSEVAL grep gate in `scripts/check-brand.sh` enforces this). However,
**three call sites have NOT been updated to the new D-01 contract** — they still
pass a wiki path where a workspace path is now required. The unit tests use
mocks that bypass the broken layering, so the bug survives the `165 passing`
claim. The breakage would surface as silent structural-check failures (sweep)
and outright `FileNotFoundError`s (the live sweep eval tests) once
`GRAPH_WIKI_RUN_EVAL=1` is set.

A fourth call site in `tests/eval_helpers.py` makes the same mistake across
four agent-command invocations used by every `produce_outputs(...)` consumer
under the eval gate; this directly breaks the gated divergence and full-matrix
integration paths that the phase claims are at parity.

## Critical Issues

### CR-01: `check_structural` is called with the wiki path, not the workspace path — double-`/wiki/` lookup

**File:** `packages/eval-harness/src/eval_harness/sweep.py:293` (and `:589`)
**Issue:** Per Phase 24 D-01, `check_structural(result, workspace_path)` now
expects a workspace root and internally derives the wiki via
`wiki_dir(workspace_path)` (see `structural.py:33` and `:76`). The two call
sites in `sweep.py` instead pass `wt.path / "wiki"`:

```python
# sweep.py:293 (in run_sweep._run_one)
structural = check_structural(result, wt.path / "wiki")

# sweep.py:589 (in run_role_sweep._run_role_one)
structural = check_structural(_result, wt.path / "wiki")
```

`wt.path` is the **workspace root** per `isolation.py:6-8` ("wt.path is the
workspace root; the wiki content lives at wt.path/wiki"). Passing
`wt.path / "wiki"` causes `structural._resolve_citation` to look for citations
under `wt.path/wiki/wiki/<slug>.md`, which never exists. Effect: every sweep
run silently records `citations_resolve=False`, `frontmatter_valid=False`, and
`unresolved_citations=[all citations]`, regardless of the actual answer
quality. This corrupts the `structural` field on every `SweepResult` and
poisons the Pareto-frontier downstream of `cost_frontier_table`.

Why tests miss it: `test_sweep_includes_structural` only asserts the
`has_citation` key is present in `result.structural` — it never verifies
`citations_resolve`. The mocked `run_query` returns a fabricated
`["wiki-page"]` citation that points at a slug the fixture does not contain
either, so the test would have `citations_resolve=False` whether the bug
exists or not. The bug is invisible at the unit-test layer.

**Fix:**
```python
# sweep.py:293
structural = check_structural(result, wt.path)

# sweep.py:589
structural = check_structural(_result, wt.path)
```
Add a unit test that uses `fixture_workspace_path` end-to-end with a real
resolvable citation and asserts `result.structural["citations_resolve"] is True`.

### CR-02: Live `test_sweep_eval.py` passes `FIXTURE_VAULT` (a wiki) as `workspace_path` — `EvalWorktree.copytree` cannot find `wiki/`

**File:** `packages/eval-harness/tests/eval/test_sweep_eval.py:135, 278`
**Issue:** `FIXTURE_VAULT` resolves to
`packages/vault-io/tests/fixtures/round-trip-vault/`. The directory **is** the
wiki itself (`ls` shows `index.md`, `packages/`, `adrs/`, …); it has no
`wiki/` subdir. Two test sites then pass it as `workspace_path`:

```python
# line 135 — test_query_sweep_case
results = await run_sweep(CASES_PATH, FIXTURE_VAULT, [model_id])

# line 278 — test_full_matrix_live
result = await run_full_matrix(
    role_candidates=role_candidates,
    workspace_path=FIXTURE_VAULT,
    ...
)
```

Both `run_sweep` and `run_full_matrix` derive `wiki = wiki_dir(workspace_path)`
= `FIXTURE_VAULT/"wiki"` → does not exist. `EvalWorktree(wiki)` then calls
`shutil.copytree(self._source, self.path/"wiki", dirs_exist_ok=False)`, which
raises `FileNotFoundError` because `self._source` (the supposed wiki) is
absent. The whole sweep aborts before any model is invoked.

The correct shape is what `conftest.fixture_workspace_path` already provides
(tmp_path with a `wiki` symlink). `test_sweep_eval.py` was rewritten with the
rename but the workspace/wiki layering at the call site was not corrected.

These tests are gated by `@pytest.mark.eval` + `EVAL_GATE`, so they are
skipped in normal CI; they will fail the first time anyone runs
`GRAPH_WIKI_RUN_EVAL=1 pytest --run-eval`. The phase summary's claim of
"22 skipped/gated" hides this regression — the tests do not "skip cleanly",
they will fail-on-run.

**Fix:** Build a fixture workspace shape and pass that instead:

```python
@pytest.fixture
def fixture_workspace(tmp_path: Path) -> Path:
    (tmp_path / "wiki").symlink_to(FIXTURE_VAULT, target_is_directory=True)
    return tmp_path

# ...
results = await run_sweep(CASES_PATH, fixture_workspace, [model_id])
# ...
result = await run_full_matrix(..., workspace_path=fixture_workspace, ...)
```

(Or directly reuse the existing `fixture_workspace_path` from conftest.py;
this file currently imports `EVAL_GATE` from conftest but not the workspace
fixture.)

### CR-03: `eval_helpers.produce_outputs` passes the wiki fixture as `workspace_path` to four agent commands

**File:** `packages/eval-harness/tests/eval_helpers.py:126, 165, 194, 242`
**Issue:** Every `_produce_*_outputs(...)` helper receives `wiki` (always
`fixture_wiki_path` = round-trip-vault, the wiki dir itself) and immediately
passes it as `workspace_path=wiki` to a graph-wiki-agent command:

```python
# line 126
result = asyncio.run(run_query(query, workspace_path=wiki))

# line 165
result = asyncio.run(run_ingest_source(source_path, workspace_path=wiki))

# line 194
result = asyncio.run(run_lint(workspace_path=wiki))

# line 242
result = asyncio.run(run_scan(workspace_path=wiki, repo_path=eval_harness_dir))
```

Post-Phase-22 / Phase 24, every one of these commands resolves
`wiki = wiki_dir(workspace_path) = workspace_path/"wiki"`. With
`workspace_path=fixture_wiki_path`, that becomes
`round-trip-vault/wiki/` — which does not exist. Index-build paths
(`.graph-wiki/bm25`, `.graph-wiki/search.db`) under that nonexistent dir
cannot be auto-built either. Every divergence integration test
(`test_divergence_regression` and the analogous live consumers) is in fact
broken at the live-run gate.

Because the eval gate (`GRAPH_WIKI_RUN_EVAL=1`) is not set in normal CI, this
silently passes the test suite (the tests skip), but the phase's
"165 passing, 22 skipped/gated" claim conflates "gated and not run" with
"gated and runnable". The next live-eval run on the divergence baselines
(`--accept-divergence-baseline`) will fail before producing a single output.

**Fix:** Change the `wiki: Path` parameter on `produce_outputs` (and the four
`_produce_*_outputs` helpers) into a `workspace: Path` parameter, and update
the conftest helper to construct a workspace-shaped path (mirror the existing
`fixture_workspace_path` fixture). Tests that need the wiki path explicitly
(e.g. read-back of an ingested page in `_produce_ingestor_outputs`) should
derive it via `wiki_dir(workspace)` rather than receive it directly. Replace:

```python
def produce_outputs(role: str, wiki: Path) -> ...:
    ...
    result = asyncio.run(run_query(query, workspace_path=wiki))
```

with:

```python
def produce_outputs(role: str, workspace: Path) -> ...:
    ...
    result = asyncio.run(run_query(query, workspace_path=workspace))
    # if wiki content needed:
    wiki = wiki_dir(workspace)
    written_path = wiki / result.page_path
```

Add a parallel `fixture_workspace_path`-backed parametrization to
`test_divergence.py` so the live regression test actually runs the corrected
contract.

## Warnings

### WR-01: `structural.py` advertises `wiki = wiki_dir(workspace_path)` as fail-fast, but `wiki_dir` does no I/O

**File:** `packages/eval-harness/src/eval_harness/structural.py:71-76`
**Issue:** The comment block claims:

> Derive the wiki once at the top per D-01 / D-09 (fail-fast on a malformed
> workspace_path before any check runs).

But `workspace_io.paths.wiki_dir(workspace)` is a pure path concatenation
(`return Path(workspace) / "wiki"`) — it does no `exists()`/`is_dir()`/stat
call. The binding cannot "fail-fast" on anything; it is dead code with a
`# noqa: F841` suppressing the linter. Subsequent calls to
`_resolve_citation(slug, workspace_path)` re-derive the wiki from
`workspace_path` independently. The block is misleading documentation for a
no-op.

**Fix:** Either remove the unused binding and the comment block entirely
(simpler), or add an explicit existence check:

```python
wiki = wiki_dir(workspace_path)
if not wiki.is_dir():
    raise FileNotFoundError(f"wiki dir not found: {wiki}")
```

The latter would have surfaced CR-01 immediately when the sweep call site
passed `wt.path/"wiki"` — recommend doing both: remove the dead binding and
add the runtime guard at the start of `check_structural`.

### WR-02: `_aggregate_usage` truthiness pattern coerces legitimate 0 totals to None

**File:** `packages/eval-harness/src/eval_harness/sweep.py:95-96`
**Issue:** Pre-existing pattern carried through the Phase 24 changes:

```python
total_in = sum(b["tokens_in"] for b in bucket if b["tokens_in"] is not None) or None
total_out = sum(b["tokens_out"] for b in bucket if b["tokens_out"] is not None) or None
```

If the bucket contains entries with `tokens_in=0` (rare but legitimate when
the cache hit returns a zero-input completion, or in mock runs), `sum(...) or
None` returns `None` rather than `0`, indistinguishable from the
"unavailable" sentinel. The same anti-pattern repeats at
`sweep.py:567` and `sweep.py:572` (`... ) or None`).

**Fix:**
```python
present_in = [b["tokens_in"] for b in bucket if b["tokens_in"] is not None]
total_in = sum(present_in) if present_in else None
```

Not introduced by this phase, but the Phase 24 rename touched these lines
indirectly via the same module rewrite — flag for cleanup.

### WR-03: `BaselineRecorder.record` recomputes the wiki content hash on a fresh `EvalWorktree` copy, not the real wiki

**File:** `packages/eval-harness/src/eval_harness/baseline.py:343-357`
**Issue:** The recorder's `_run` coroutine creates an `EvalWorktree` (copies
the wiki into a tmpdir) and runs `claude -p` there. After the coroutine
returns, `_make_snapshot` is invoked at line 357 and recomputes
`wiki_content_hash` from `wiki_dir(self._workspace_path)`:

```python
"wiki_content_hash": _wiki_content_hash(wiki_dir(self._workspace_path)),
```

This is the *original* workspace's wiki, not the worktree copy that was used
for the actual `claude -p` run. The hash should describe the wiki state that
produced the answer, not the state of the source path at snapshot time. If
the source wiki is mutated between `EvalWorktree.__aenter__` (copytree
snapshot) and `_make_snapshot`, the recorded hash will not match the
recording conditions.

Practically the window is tiny (single coroutine), but the field is
documented as identifying the recording conditions. The fix is cheap: hash
inside the `_run` coroutine while the worktree is still mounted and capture
the resulting digest.

**Fix:**
```python
async def _run() -> tuple[RunResult, str, str]:
    wiki = wiki_dir(self._workspace_path)
    async with EvalWorktree(wiki) as wt:
        run_result, answer = run_headless(
            prompt=case["query"],
            worktree_path=wt.path / "wiki",
            system_prompt=self._system_prompt,
            plugin_dirs=self._plugin_dirs,
            model_override=None,
        )
        wiki_hash = _wiki_content_hash(wt.path / "wiki")
        return run_result, answer, wiki_hash

run_result, answer, wiki_hash = asyncio.run(_run())
snapshot = self._make_snapshot(case, run_result, answer, wiki_hash)
```
and have `_make_snapshot` accept the precomputed hash.

### WR-04: `_wiki_content_hash` silently swallows `OSError` per-file, eroding the hash's stability claim

**File:** `packages/eval-harness/src/eval_harness/baseline.py:243-260`
**Issue:**

```python
for f in md_files:
    try:
        content = f.read_bytes()
    except OSError:
        continue
```

The docstring claims:

> Stable sha256 of all .md files in the wiki.

…but if any `.md` file is transiently unreadable (open handle, permissions
flicker, race with a write), it is silently skipped and the hash is computed
over the remainder. Two runs with the same wiki content can yield different
hashes simply because one had a transient OSError. The field is then
unreliable as a "same wiki" identifier, undermining the EVAL-08
reproducibility property the function exists to provide.

**Fix:** Re-raise (or at minimum log loudly and fold a sentinel byte into
the hash to mark the deviation):

```python
for f in md_files:
    content = f.read_bytes()
    file_hash = hashlib.sha256(content).hexdigest()
    h.update(file_hash.encode())
```

Bonus: the per-file step uses `hashlib.md5(...)` with `# noqa: S324`. MD5
is fine for the inner step in principle (the outer SHA-256 protects against
collision misuse), but switching it to SHA-256 removes the bandit suppression
and costs nothing measurable.

## Info

### IN-01: `_BARE_CODE_PATH_RE` in `divergence/librarian.py` only fires on a fixed prefix list

**File:** `packages/eval-harness/src/eval_harness/divergence/librarian.py:42-44`
**Issue:**

```python
_BARE_CODE_PATH_RE = re.compile(
    r"(?<!`)(?:src|tests|packages|agents)/[A-Za-z0-9_/.-]+\.(?:py|ts|js|go|rs):\d+"
)
```

LIB-004 ("bare code paths must be in backticks") matches only paths that
start with one of `src`, `tests`, `packages`, `agents`. The structural
counterpart (`structural._CODE_PATH_RE`) is broader (also matches bare
filenames like `foo.py`). A bare `pool.py:115` slips past LIB-004 silently
even though SYN-001 / code_reader checks elsewhere allow bare filenames as
valid `path:line` citations. Inconsistency between modules; not introduced
by Phase 24, but worth aligning in a follow-up.

**Fix:** Either widen `_BARE_CODE_PATH_RE` to match bare filenames too, or
narrow `_PATH_LINE_RE` in `code_reader.py` to require a directory prefix —
pick one convention and apply it project-wide.

### IN-02: `test_sweep_eval.py` re-implements `fixture_wiki_path` resolution rather than importing the fixture

**File:** `packages/eval-harness/tests/eval/test_sweep_eval.py:38-48`
**Issue:** The file computes `FIXTURE_VAULT` from `__file__` traversal and
imports `EVAL_GATE` from `conftest` via a hand-injected `sys.path.insert`.
The conftest already provides `fixture_wiki_path` and `fixture_workspace_path`
fixtures; reusing them would have surfaced CR-02 automatically (the workspace
fixture is shaped correctly).

Cosmetic; cleanup item for the same patch that addresses CR-02.

---

_Reviewed: 2026-05-20_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
