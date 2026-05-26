---
phase: 35
plan: 02
type: execute
status: complete
date: 2026-05-26
requirements:
  - HYGIENE-13
  - HYGIENE-14
files_changed:
  - agents/graph-wiki-agent/tests/unit/test_cli_help.py
  - packages/wiki-io/tests/test_bootstrap_e2e_no_broken_links.py
  - .planning/phases/35-wiki-bootstrap-hygiene-burn-down/35-DISCUSSION-LOG.md
---

# Plan 02 — HYGIENE-13 + HYGIENE-14 Verify-and-Close

## Summary

Verify-and-close work for the last two HYGIENE requirements:

- **HYGIENE-13** — Added a load-bearing comment above `_PLAIN_HELP_ENV` in
  `test_cli_help.py` referencing the `260521-ans` incident handle and
  explicitly marking `NO_COLOR=1 TERM=dumb COLUMNS=200` as load-bearing
  (not cosmetic). Existing 3/3 tests still pass.

- **HYGIENE-14** — Wrote `packages/wiki-io/tests/test_bootstrap_e2e_no_broken_links.py`
  per D-02/D-03. The test bootstraps a wiki into `tmp_path`, renders the
  package/app/plugin overview templates, writes minimal stub sub-pages so
  wikilinks resolve, then calls `wiki_io.lint_wiki.scan()` and asserts zero
  broken wikilinks sourced from the three overview pages.

Both closure records appended to `35-DISCUSSION-LOG.md` (verbatim pytest output
for HYGIENE-13; D-03 swap rationale for HYGIENE-14).

## lint_wiki.scan() broken-wikilink key

`lint_wiki.scan()` exposes broken wikilinks under the **`broken_links`** key
(`packages/wiki-io/src/wiki_io/lint_wiki.py:350`) as a list of `(src, target)`
tuples, sorted. The new test pins to this key via `_extract_broken_wikilinks()`
which fails loudly with a key-list dump if the shape ever changes.

Recorded here so future test authors do not have to re-derive it.

## D-03 swap (manual transcript superseded)

Per CONTEXT.md D-03, the originally-planned manual `/graph-wiki:query` smoke
transcript is superseded by the new automated regression test. Rationale
(quoted in 35-DISCUSSION-LOG.md): "A test that runs on every CI is strictly
stronger evidence than a one-time manual transcript."

- Closure artifact: `packages/wiki-io/tests/test_bootstrap_e2e_no_broken_links.py`.
- Audit trail: 35-DISCUSSION-LOG.md "HYGIENE-14 Closure: D-03 supersedes
  manual transcript" section (committed in `6bafb07`).
- Phase 39 SC#3 impact: the new test is the captured artifact future Phase 39
  planning can cite rather than re-running a manual smoke.

## Test results

Final verification gate:

- `uv run --package wiki-io pytest packages/wiki-io/tests/ -x` —
  **152 passed, 1 skipped in 87.66s** (the +1 over Plan A's baseline is
  exactly the new `test_bootstrap_e2e_no_broken_links.py`).
- `uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/ -x` —
  **220 passed, 6 skipped in 20.06s** (unchanged from Plan A; the comment-only
  edit to `test_cli_help.py` is byte-level neutral to the test runner).

Per-file verification:
- `pytest packages/wiki-io/tests/test_bootstrap_e2e_no_broken_links.py -x -v`
  → **1 passed in 0.05s**.
- `pytest agents/graph-wiki-agent/tests/unit/test_cli_help.py -x -v`
  → **3 passed in 1.76s**.

## Test instability observed

None. The new test runs in ~50ms against `tmp_path` with `monkeypatch` stubs
on `_workspace_init` and `_resolve_pinned_containers` — no git operations, no
environment variable pinning beyond the `GRAPH_WIKI_WORKSPACE` injection
documented in the plan (which turned out unnecessary once `_workspace_init`
was stubbed). Stable across multiple runs.

## Commits

- `008d0a6` docs(35-02): HYGIENE-13 — load-bearing comment on _PLAIN_HELP_ENV
- `58a5801` test(35-02): HYGIENE-14 — bootstrap-and-lint regression test (D-02/D-03)
- `6bafb07` docs(35-02): append HYGIENE-13 + HYGIENE-14 closure records to DISCUSSION-LOG

## Phase 35 close-out

All 14 HYGIENE requirements (HYGIENE-01..14) closed; v1.7 integration phases
(37-40) cleared to start without merge-conflict risk on `commands/scan.py`,
wiki-io templates, or workspace-io.
