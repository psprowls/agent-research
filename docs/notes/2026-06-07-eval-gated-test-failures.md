# Eval-Gated Test Failures Handoff

Date: 2026-06-07

## Context

After updating eval-harness fixtures from the old `post-rebrand-vault/packages/...` layout to the current workspace-shaped `post-rebrand-workspace/wiki/entities/...` layout, the normal non-eval suite passed and the change was committed as:

```text
accd0b75 Update eval fixtures for entity wiki layout
```

The user then asked to run tests requiring `GRAPH_WIKI_RUN_EVAL=1`. These tests exposed follow-up failures that should be debugged in a fresh worktree.

## Commands Run

Plain eval-gated tests:

```bash
GRAPH_WIKI_RUN_EVAL=1 uv run --package eval-harness pytest \
  tests/test_divergence.py \
  tests/test_sweep.py::test_run_query_accepts_tmpdir_workspace
```

Result:

```text
3 failed, 2 passed in 114.31s
```

Pytest-evals sweep tests:

```bash
GRAPH_WIKI_RUN_EVAL=1 uv run --package eval-harness pytest tests/eval --run-eval
```

Partial result before termination:

```text
tests/eval/test_sweep_dry_run.py ...                                     [ 16%]
tests/eval/test_sweep_eval.py ... .. ... ..sF
```

The second command stopped producing output for several minutes after the first `F`, so I terminated the long-running eval process with SIGTERM. It exited with code `143`. The full traceback for that pytest-evals failure was not captured because the process had not reached final reporting before termination.

## Failure 1: Librarian Divergence Citation Regression

Test:

```text
tests/test_divergence.py::test_divergence_regression[librarian]
```

Failure:

```text
AssertionError: [librarian] LIB-002-citation-present: failure rate 1.000 (4/4) > baseline 0.000 (0/4). Run with --accept-divergence-baseline to accept.
```

Captured divergence report:

```text
=== Divergence report: librarian ===
  LIB-001-wikilink-resolves: runs=4 failures=0
  LIB-002-citation-present: runs=4 failures=4
    - [pkg-lookup-01] No citation in answer
    - [concept-01] No citation in answer
    - [cross-ref-01] No citation in answer
  LIB-004-code-path-format: runs=4 failures=0
  LIB-JUDGE: runs=4 failures=3
```

Notable stderr/log context:

```text
[graph unavailable: run 'cg update' to enable code-graph grounding tools]
```

Initial hypothesis to verify:

The new fixture layout may resolve page links structurally (`LIB-001` passes) but the live librarian answers are no longer producing citation-bearing prose under the current corpus/query setup. The graph is also unavailable for the fixture workspace, which may degrade query behavior.

Debug next steps:

1. Re-run only the librarian case with `-s` to inspect the actual answers.
2. Check `eval/cases/query_cases.json` against the new fixture entity names.
3. Verify whether query retrieval finds `entities/pkg_eval-harness` and related pages.
4. Decide whether the fixture corpus needs richer content, a graph DB, updated query cases, or a baseline refresh.

## Failure 2: Ingestor Fixture Missing Graph DB

Test:

```text
tests/test_divergence.py::test_divergence_regression[ingestor]
```

Failure:

```text
graph_wiki_core.commands.ingest.IngestorGraphNotInitializedError:
error: graph-io not initialized for this workspace. Run 'gw graph build' (or 'cg update') to initialize, then retry.
```

Underlying path:

```text
packages/eval-harness/tests/fixtures/post-rebrand-workspace/.graph-wiki/code.db
```

Initial hypothesis to verify:

The committed fixture includes `.graph-wiki/bm25/.gitkeep` only. It does not include a schema-valid `code.db`. `EvalWorktree` provisions an empty graph DB when it wraps a wiki, but `test_divergence.py` passes the committed fixture workspace directly into `run_ingest_source`, so no DB is provisioned.

Debug next steps:

1. Decide whether `fixture_workspace_path` should create a temporary workspace copy instead of returning the committed fixture path directly.
2. Alternatively, add a test helper that provisions an empty graph DB before live ingestor divergence runs.
3. Avoid committing generated BM25/search/traces artifacts while doing this.

## Failure 3: Scanner Fixture Missing `log.md`

Test:

```text
tests/test_divergence.py::test_divergence_regression[scanner]
```

Failure:

```text
ValueError: packages/eval-harness/tests/fixtures/post-rebrand-workspace/wiki/log.md does not exist - is this a wiki?
```

Initial hypothesis to verify:

`run_scan` appends to `wiki/log.md`, but the new fixture has `wiki/index.md` and `wiki/entities/...` only. The non-eval fixture tests did not require a full bootstrapped wiki surface.

Debug next steps:

1. Add a minimal `wiki/log.md` to a temporary eval workspace, or make `fixture_workspace_path` copy and bootstrap runtime-only files.
2. Check whether `run_scan` also writes additional mutable outputs into the committed fixture when passed directly.
3. Prefer running live evals against a temp workspace copy so success and failure artifacts do not dirty the committed fixture.

## Artifact Behavior Observed

Running eval-gated tests against the committed fixture workspace generated untracked files under:

```text
packages/eval-harness/tests/fixtures/post-rebrand-workspace/.graph-wiki/bm25/
packages/eval-harness/tests/fixtures/post-rebrand-workspace/.graph-wiki/search.db
packages/eval-harness/tests/fixtures/post-rebrand-workspace/.graph-wiki/traces/
```

Those generated fixture artifacts were removed after the run. Only `.graph-wiki/bm25/.gitkeep` remained in the committed fixture.

Important observation:

The artifacts appeared during a failing eval run, but some were likely created by successful setup/indexing before later assertions failed. In particular, the librarian run built BM25/search state before the citation regression assertion. Do not assume artifact creation means the test as a whole succeeded.

Debug question for the next session:

Should eval-gated tests ever run directly against the committed fixture workspace, or should all eval roles use `EvalWorktree` or another temp-copy fixture that isolates generated `bm25`, `search.db`, `traces`, `code.db`, `log.md`, and mutated wiki pages?

## Pytest-Evals Partial Failure

Command:

```bash
GRAPH_WIKI_RUN_EVAL=1 uv run --package eval-harness pytest tests/eval --run-eval
```

Observed progress:

```text
tests/eval/test_sweep_dry_run.py ...                                     [ 16%]
tests/eval/test_sweep_eval.py ... .. ... ..sF
```

Then the process produced no additional output for several minutes and was terminated with SIGTERM. Because final pytest reporting did not print, the exact failing test and traceback are unknown.

Debug next steps:

1. Re-run `tests/eval/test_sweep_eval.py` with `-vv -s` and possibly one selected test at a time.
2. Consider setting shorter model/request timeouts if available.
3. Watch whether failures leave files under `eval/runs/` or fixture `.graph-wiki/`.
4. Determine whether the `F` was from fixture layout, model behavior, or pytest-evals analysis state.

## Recommended Isolation Plan

1. Create a fresh worktree from commit `accd0b75`.
2. Do not use the main checkout’s current untracked files as signal.
3. Start with the three plain eval-gated failures:

```bash
GRAPH_WIKI_RUN_EVAL=1 uv run --package eval-harness pytest \
  tests/test_divergence.py::test_divergence_regression[librarian] -vv -s

GRAPH_WIKI_RUN_EVAL=1 uv run --package eval-harness pytest \
  tests/test_divergence.py::test_divergence_regression[ingestor] -vv -s

GRAPH_WIKI_RUN_EVAL=1 uv run --package eval-harness pytest \
  tests/test_divergence.py::test_divergence_regression[scanner] -vv -s
```

4. Track filesystem changes after each single test:

```bash
git status --short
find packages/eval-harness/tests/fixtures/post-rebrand-workspace/.graph-wiki -maxdepth 3 -type f | sort
find eval/runs -maxdepth 3 -type f | sort
```

5. Decide whether to fix by adding missing fixture files, changing fixtures to use temp workspaces, or updating eval cases/baselines.

## Do Not

- Do not accept divergence baselines until the missing `code.db` and `log.md` fixture issues are understood.
- Do not commit generated BM25/search/traces artifacts unless there is an explicit decision that these belong in fixtures.
- Do not treat `LIB-001` passing as proof librarian behavior is correct; `LIB-002` failed on every librarian output.
