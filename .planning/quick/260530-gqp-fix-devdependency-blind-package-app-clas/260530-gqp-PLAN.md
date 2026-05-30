---
phase: quick-260530-gqp
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - packages/graph-io/src/graph_io/packages.py
  - packages/graph-io/src/graph_io/classification.py
  - packages/graph-io/src/graph_io/queries.py
  - packages/graph-io/tests/test_classification.py
  - packages/graph-io/tests/test_packages.py
  - packages/graph-io/tests/integration/test_e2e_apps.py
autonomous: true
requirements: [QUICK-GQP-01]

must_haves:
  truths:
    - "A package.json whose electron+vite live under devDependencies classifies as kind='app', app_kind='electron'"
    - "An Electron+Vite app classifies as electron, not spa (precedence)"
    - "devDependencies names are merged into the single sorted/deduped dependencies list classify() reads"
    - "The runtime-vs-dev origin survives on the package node attrs_json (dev_dependencies list)"
    - "Pure libraries and runtime-framework apps (next/expo) classify exactly as before"
    - "`uv run --package graph-io pytest` passes"
  artifacts:
    - path: "packages/graph-io/src/graph_io/packages.py"
      provides: "_read_package_json merges devDependencies + captures dev set; node attrs carry dev_dependencies"
    - path: "packages/graph-io/src/graph_io/classification.py"
      provides: "electron signal + electron-before-spa precedence"
    - path: "packages/graph-io/src/graph_io/queries.py"
      provides: "'electron' in _VALID_APP_KINDS"
  key_links:
    - from: "classification._FRAMEWORK_PRECEDENCE"
      to: "queries._VALID_APP_KINDS"
      via: "write-time gate validates app_kind against the set"
      pattern: "electron"
---

<objective>
Fix devDependency-blind package/app classification in graph-io. Electron apps
declare `electron` and `vite` under `devDependencies`, which `_read_package_json`
never reads — so the existing `spa` signal can't fire and there is no `electron`
signal, causing `apps/app-electron-ts` to misclassify as a `pkg:` entity.

Purpose: re-running `graph-wiki-agent scan` against a real monorepo must classify
Electron apps as `app:` with `app_kind='electron'`, while leaving Python packages
and runtime-framework apps (next/expo) untouched.

Output: merged dev+runtime dependency list for classification, a new `electron`
signal/kind, and a dev-vs-runtime split surfaced on the package node's attrs_json.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@./CLAUDE.md
@packages/graph-io/CLAUDE.md

<interfaces>
<!-- Current contracts the executor must preserve. Extracted from codebase. -->

graph_io/packages.py — _read_package_json returns an info dict consumed by
classify() and the emit loop in refresh(). Current shape (JS branch):
  {
    "name": str,
    "version": str,
    "description": str,
    "dependencies": sorted(deps.keys()),   # list[str], runtime deps only today
    "language": "javascript",
    "bin_present": bool,
  }
- The node attrs in refresh() copy `info["dependencies"]` verbatim into
  attrs["dependencies"] (packages.py ~line 215).
- The Python-dependency ingestion loop (`if info["language"] == "python":`,
  ~line 272) is the ONLY path that emits `dependency` nodes + `used_by` edges.
  JS deps are NOT ingested as dependency nodes/edges in v1 — confirmed. So there
  is no current JS used_by/dependency edge path to tag; the achievable dev marker
  is the package-node attr (scope item 5) plus the captured set (scope item 1).

graph_io/classification.py — classify(info, pkg_dir) JS branch:
  deps = info.get("dependencies") or []
  if "next" in deps: signals.append("nextjs")
  if "expo" in deps: signals.append("expo")
  if "vite" in deps and (pkg_dir / "index.html").exists(): signals.append("spa")
  _FRAMEWORK_PRECEDENCE = ("nextjs", "expo", "spa")  # first match wins
  Write-time gate: app_kind must be in queries._VALID_APP_KINDS.

graph_io/queries.py line 34:
  _VALID_APP_KINDS = frozenset({"cli", "expo", "nextjs", "spa"})
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Merge devDependencies + add electron signal/kind</name>
  <files>
    packages/graph-io/src/graph_io/packages.py,
    packages/graph-io/src/graph_io/classification.py,
    packages/graph-io/src/graph_io/queries.py
  </files>
  <behavior>
    - _read_package_json: when package.json has only `electron` and `vite` under
      devDependencies (dependencies empty), info["dependencies"] == ["electron", "vite"]
      (sorted, deduped against any runtime dep of the same name), AND
      info["dev_dependencies"] == sorted-list containing both names.
    - classify(): info with "electron" in deps → ("app", "electron", signals incl "electron").
    - classify(): info with both "electron" and "vite" + index.html present →
      app_kind == "electron" (NOT "spa") — precedence proven.
    - classify(): info with "vite" + index.html but NO electron → still "spa" (unchanged).
    - classify(): "next"/"expo" inputs unchanged → "nextjs"/"expo".
    - "electron" is a member of queries._VALID_APP_KINDS (gate does not raise).
  </behavior>
  <action>
    Per the locked user decision: merge devDependencies INTO the single
    `dependencies` list classify() reads, and additionally carry the dev-origin
    names through as a separate marker set.

    In `_read_package_json` (packages.py ~line 105/118): read `devDependencies`
    alongside `dependencies`. Guard both with the existing `isinstance(.., dict)`
    pattern already used for `deps`. Build the merged list as the sorted union of
    runtime + dev dependency keys (dedupe across both — a name in both keeps one
    entry). Set `info["dependencies"]` to that merged sorted list. Add a new key
    `info["dev_dependencies"]` = sorted list of the names that came from
    devDependencies (the dev-origin marker). Do NOT introduce a hidden separate
    field that classify reads instead — classify keeps reading `dependencies`.

    In `classify()` (classification.py) JS branch: add an `electron` signal —
    `if "electron" in deps: signals.append("electron")`. Place it adjacent to the
    other framework checks, matching existing style. Add `"electron"` to
    `_FRAMEWORK_PRECEDENCE` ORDERED BEFORE `"spa"` so an Electron+Vite app resolves
    to electron, not spa: `("nextjs", "expo", "electron", "spa")`. Keep nextjs/expo
    ahead. Update the precedence docstring note that points at _VALID_APP_KINDS.

    In `queries.py` line 34: add `"electron"` to `_VALID_APP_KINDS`. The classify()
    write-time gate validates against this set, so both MUST stay in sync — mirror
    the existing inline comment that already documents this coupling.

    No `derived_edges.py` change: that file enumerates no app kinds / framework
    precedence (verified via grep). Do not touch it.

    Surgical only — match existing comment/citation style; every changed line
    traces to this fix.
  </action>
  <verify>
    <automated>uv run --package graph-io pytest packages/graph-io/tests/test_classification.py -x -q</automated>
  </verify>
  <done>
    devDependencies merge present in _read_package_json with a dev_dependencies
    marker set; electron signal + electron-before-spa precedence in classify();
    "electron" in _VALID_APP_KINDS; classification unit tests pass.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Surface dev/runtime split on package node + tests/e2e</name>
  <files>
    packages/graph-io/src/graph_io/packages.py,
    packages/graph-io/tests/test_classification.py,
    packages/graph-io/tests/test_packages.py,
    packages/graph-io/tests/integration/test_e2e_apps.py
  </files>
  <behavior>
    - After refresh() on a JS package whose package.json has electron+vite under
      devDependencies and an index.html at root: the node row is kind='app',
      attrs["app_kind"] == "electron", attrs["dependencies"] == ["electron","vite"]
      (merged sorted), and attrs["dev_dependencies"] == ["electron","vite"].
    - A JS package with a runtime dep + a dev-only dep: attrs["dependencies"]
      contains both (merged); attrs["dev_dependencies"] contains only the dev one.
    - e2e: `cg update --full` on a repo with an Electron+Vite app (electron+vite in
      devDependencies, index.html at root) → describe-app --fmt json reports
      app_kind == "electron".
  </behavior>
  <action>
    In `refresh()` (packages.py, the attrs dict ~line 208-218): add
    `"dev_dependencies": info.get("dev_dependencies", [])` to the package node
    `attrs` so wiki-io narratives can separate dev vs runtime (scope item 5).
    Python manifests have no dev_dependencies key, so the `.get(..., [])` default
    keeps Python package attrs as an empty list — confirm that does not perturb
    existing Python attr assertions (test_refresh_pyproject asserts specific keys
    by name, not the full dict, so an added key is safe; verify in the run).

    Do NOT add a JS dependency-ingestion / used_by edge path — none exists in v1
    (the ingestion loop is Python-only). The locked-decision dev marker for JS is
    delivered via the merged list + dev_dependencies attr above; there are no JS
    `dependency:` nodes/edges to tag. If a reviewer expects edge tagging, that is
    only reachable for the existing Python dependency-groups path and is out of
    scope for this Electron fix.

    Tests:
    - test_classification.py: add a test for the electron signal
      (electron in deps → app_kind 'electron') and a precedence test
      (electron+vite+index.html → 'electron', not 'spa'). Mirror the existing
      test_classify_js_* style (build an info dict, call classify(info, tmp_path),
      assert kind/app_kind/signals). Keep the existing vite-only spa test intact.
    - test_packages.py: add a refresh-level test that writes a package.json with
      electron+vite under devDependencies + an index.html at the package dir,
      runs packages.refresh, and asserts the node is kind='app', app_kind='electron',
      attrs['dependencies']==['electron','vite'], attrs['dev_dependencies']==
      ['electron','vite']. Reuse the _seed_file_node / _CTX helpers already in the
      file. Also extend or add a small assertion that a JS dev-only dep appears in
      dev_dependencies but a runtime dep does not.
    - test_e2e_apps.py: add an end-to-end test mirroring
      test_e2e_js_multi_signal_precedence but for Electron — package.json with
      electron+vite in devDependencies, an index.html at repo root, git init/commit,
      update.run(full=True), then q_describe_app --fmt json asserts
      app_kind=='electron'.

    Do not weaken or delete existing assertions; only add cases and the one new
    attr key.
  </action>
  <verify>
    <automated>uv run --package graph-io pytest packages/graph-io/tests/test_classification.py packages/graph-io/tests/test_packages.py packages/graph-io/tests/integration/test_e2e_apps.py -q</automated>
  </verify>
  <done>
    Package node attrs carry dev_dependencies; new electron unit/refresh/e2e tests
    pass; existing classification/packages/e2e assertions unchanged and passing.
  </done>
</task>

<task type="auto">
  <name>Task 3: Full graph-io suite regression sweep</name>
  <files>packages/graph-io/tests</files>
  <action>
    Run the full graph-io test suite to catch any snapshot/golden or queries/
    plugins/derived_edges assertion that the new attr key or the electron kind
    perturbs. (.ambr snapshots under agents/graph-wiki-agent were verified NOT to
    encode JS dependency lists, electron, vite, or app_kinds — they should be
    unaffected. If any unexpected failure surfaces here, fix it surgically in the
    test that encodes the now-stale expectation, never by reverting source intent.)

    If a snapshot legitimately needs the new dev_dependencies key, re-run with the
    snapshot-update flag for that single test only, then inspect the diff to
    confirm it is exactly the added key / electron value and nothing else.
  </action>
  <verify>
    <automated>uv run --package graph-io pytest -q</automated>
  </verify>
  <done>
    Full `uv run --package graph-io pytest` passes; any updated snapshot diff is
    limited to the dev_dependencies key / electron classification.
  </done>
</task>

</tasks>

<verification>
- `uv run --package graph-io pytest -q` passes.
- A package.json with electron+vite under devDependencies + index.html classifies
  as app_kind='electron'; vite-only-with-index.html still classifies as 'spa'.
- Python packages and next/expo apps classify exactly as before.
- Package node attrs_json carries a dev_dependencies list.
- classification._FRAMEWORK_PRECEDENCE and queries._VALID_APP_KINDS both contain
  'electron'.
</verification>

<success_criteria>
- Electron apps (electron+vite in devDependencies) classify as kind='app',
  app_kind='electron'.
- devDependencies are merged into the single sorted/deduped dependencies list that
  classify() reads; dev-origin names are tracked and surfaced on the node attrs.
- No regression to Python packages, next/expo apps, or existing tests/snapshots.
- Full graph-io suite green.
</success_criteria>

<output>
Create `.planning/quick/260530-gqp-fix-devdependency-blind-package-app-clas/260530-gqp-SUMMARY.md` when done.
</output>
