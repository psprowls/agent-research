---
phase: 52-wiki-filename-slimdown-core
plan: 03
subsystem: wiki-io
tags: [app-admission, template, scanner-frontmatter]
requires: [52-02]
provides:
  - app (admitted entity kind)
  - entity-app.md template
  - scanner_frontmatter_for_node app branch
affects:
  - packages/wiki-io
tech-stack:
  patterns:
    - "kind-aware page-template resource lookup via importlib.resources"
    - "AppDescription field surfacing in scanner_frontmatter_for_node"
key-files:
  created:
    - packages/wiki-io/src/wiki_io/assets/page-templates/entity-app.md
  modified:
    - packages/wiki-io/src/wiki_io/entity_writer.py
    - packages/wiki-io/tests/test_entity_writer.py
    - packages/wiki-io/tests/test_entity_templates.py
    - packages/wiki-io/tests/conftest.py
key-decisions:
  - "ADMITTED_KINDS grows to 7 kinds: { repository, domain, package, app, plugin, dependency, test_suite }. builtin remains excluded per Phase 49 D-16."
  - "_URI_PREFIX_BY_KIND['app'] = 'app' (no alias — short prefix already matches the kind name)."
  - "AppDescription surfaces all PackageDescription fields plus app_kind + app_signals. Both new keys are added to SCANNER_OWNED_KEYS so subsequent scans overwrite them coherently via merge_frontmatter."
  - "test_write_entities_renders_app_pages uses the graceful-degradation path (no describe_app fixture registered, branch returns d=None) — keeps the fixture minimal while fully exercising the short_filename + template wiring."
  - "Out-of-scope fix: MockGraphConn (in conftest.py) needed an 'app': [] slot, _wire_mock_queries needed to monkeypatch list_apps + describe_app, and test_six_entity_templates_exist had its count assertion bumped from 6 to 7. All three were necessary to keep the existing suite green and were surfaced in deviations."
requirements-completed: [WIKI-FN-01]
duration: 0h 08m
completed: 2026-05-28
---

# Phase 52 Plan 03: Admit `app` Kind in `wiki_io` Rendering Summary

The `app` graph-derived kind is now admitted into `wiki_io.entity_writer` so
scanner-classified app nodes (Phase 50) materialize as standalone entity
pages. Closes SC#1's literal `app_graph-wiki-agent.md` example output gap.

## What was built

- `packages/wiki-io/src/wiki_io/assets/page-templates/entity-app.md` (new):
  Mirrors `entity-package.md` verbatim with `title: <App Name>`, `kind: app`,
  and `[[apps/<other-app>]]` in the Related section. The `## Narrative`
  marker at column 0 is preserved (Phase 42 D-16).
- `packages/wiki-io/src/wiki_io/entity_writer.py`:
  - `ADMITTED_KINDS` gains `"app"` (7 total).
  - `_URI_PREFIX_BY_KIND` gains `"app": "app"`.
  - `_kind_list_fns()` gains `"app": lambda conn: _queries.list_apps(conn)`.
  - `scanner_frontmatter_for_node` gains an `elif kind == "app":` branch
    calling `_queries.describe_app(conn, name=node.name)` and surfacing
    `language`, `version`, `domains`, `test_suites`, `entry_points`,
    `app_kind`, `app_signals`.
  - `SCANNER_OWNED_KEYS` gains `app_kind` + `app_signals`.
- `packages/wiki-io/tests/test_entity_writer.py`:
  - `test_admitted_kinds_shape` updated to expect 7 kinds (added `app`,
    added `builtin` to the excluded set).
  - `_wire_mock_queries` monkeypatches `list_apps` + `describe_app`.
  - New: `test_entity_app_template_exists`.
  - New: `test_write_entities_renders_app_pages`.
- `packages/wiki-io/tests/test_entity_templates.py`:
  - `test_six_entity_templates_exist` count updated from 6 to 7, docstrings
    updated to reflect Phase 52 D-06.
- `packages/wiki-io/tests/conftest.py`:
  - `MockGraphConn._nodes` gains an `"app": []` slot.

Duration: 8 min. Files modified: 4 (+1 created). Tasks: 4.

Start: 2026-05-28T04:21:00Z
End:   2026-05-28T04:28:00Z

## Verification results

| Check | Command | Result |
|-------|---------|--------|
| Full wiki-io suite | `uv run --package wiki-io pytest packages/wiki-io/tests/` | 366 passed, 2 skipped, 1 xfailed |
| `app` in ADMITTED_KINDS + URI dict + list_fns | python import + assert | ok; `['app','dependency','domain','package','plugin','repository','test_suite']` |
| `app` template exists | `test -f packages/wiki-io/src/wiki_io/assets/page-templates/entity-app.md` | file present |
| `## Narrative` marker | grep | present at column 0 |
| New tests pass | `pytest ::test_entity_app_template_exists ::test_write_entities_renders_app_pages` | 2 passed |
| `builtin` not admitted | grep + assert | not in ADMITTED_KINDS |

## Deviations from Plan

### [Rule 1 — Bug] Out-of-scope test updates required to keep existing suite green

- **Found during:** Task 52-03-03 verification (`pytest test_entity_writer.py`).
- **Issue:** Adding `app` to `ADMITTED_KINDS` caused 9 existing tests to
  fail (one count assertion + 8 write_entities tests that exercised
  `_wire_mock_queries` without an `app` monkeypatch). The plan must_have
  line 23 explicitly claimed "no existing test fixture inserts `app:`
  nodes" — true for fixture data, but `write_entities` calls
  `_queries.list_apps(conn)` for every wave regardless of whether app
  nodes are present, and the real `list_apps` SQL query fails on
  `MockGraphConn` (`AttributeError: no attribute 'execute'`).
- **Fix:**
  1. Added `list_apps` + `describe_app` monkeypatch lines to
     `_wire_mock_queries` (test_entity_writer.py).
  2. Added `"app": []` to `MockGraphConn._nodes` default initialization
     (conftest.py).
  3. Updated `test_admitted_kinds_shape` to expect 7 kinds + added
     `builtin` to the excluded sanity check.
  4. Updated `test_six_entity_templates_exist` count from 6 to 7
     (test_entity_templates.py) — also a sweep-fail with the same
     root cause.
- **Files modified:** `tests/test_entity_writer.py`,
  `tests/test_entity_templates.py`, `tests/conftest.py`.
- **Verification:** Full wiki-io suite (366 tests) now green.
- **Commit hashes:** `5206c8b` (Task 52-03-03) + `e857d7f` (Task 52-03-04).

### Acceptance criterion soft-miss

- **Found during:** Task 52-03-02 acceptance check.
- **Issue:** The criterion `grep -E '^\s*"app",' packages/wiki-io/src/wiki_io/entity_writer.py | wc -l` expects at least 3. Actual: 1 — the regex `^\s*"app",` only matches the `ADMITTED_KINDS` frozenset entry; the `_URI_PREFIX_BY_KIND` and `_kind_list_fns` entries use `"app":` (colon-separated dict syntax) and don't match the literal pattern.
- **Disposition:** Substantively satisfied — all three admissions are present per the broader grep `'"app"'` (4 matches: ADMITTED_KINDS, `_URI_PREFIX_BY_KIND`, `_FILENAME_PREFIX_BY_URI_PREFIX` from 52-01, and `_kind_list_fns`).
- **No fix applied.** Regex pattern in the plan was overly narrow.

**Total deviations:** 1 auto-fixed (bug — out-of-scope test updates) + 1
acceptance soft-miss noted but not fixed.
**Impact:** Plan goals fully met; the in-scope source edits + new template
+ new tests are present and exercised by the green test suite.

## Issues Encountered

None beyond the deviations above.

## Next Phase Readiness

Phase 52 is now complete:

- WIKI-FN-01 (short filenames on disk) — closed via Plans 52-02 + 52-03.
- WIKI-FN-02 (suite_kind dispatch) — closed via Plans 52-01 + 52-02.
- WIKI-FN-03 (collision suffix on disk) — closed via Plan 52-02.
- WIKI-FN-04 (pure function + property tests) — closed via Plan 52-01.

SC#1's literal `app_graph-wiki-agent.md` output is achievable on a real
scan of this repo because:
1. Phase 50's `apps` classification pipeline emits `app:` URIs for nodes
   like `graph-wiki-agent`.
2. `short_filename("app:agent-research/agent-research/graph-wiki-agent",
   frozenset())` produces `app_graph-wiki-agent`.
3. `_template_path_for_kind("app")` resolves to the new template.
4. `write_entities` admits `app` via `_kind_list_fns["app"]` and renders
   via `_render_entity_page`.

Phase 53 (not yet planned) owns the cutover sweep — delete legacy
long-form orphan files (`dependency__pypi__boto3.md`,
`pkg__local__agent-research__graph-io.md`, etc.) on the next scan.

## Self-Check: PASSED

- All `<acceptance_criteria>` from the 4 tasks: PASS (1 soft-miss noted in
  deviations).
- All `<verification>` commands from the plan: PASS.
- `key-files.created` exist on disk: `entity-app.md` ✓.
- `git log --oneline --grep="52-03"` returns 4 commits (3 `feat(52-03)`,
  1 `test(52-03)`).
- Full wiki-io test suite green: 366 passed, 2 skipped, 1 xfailed.
