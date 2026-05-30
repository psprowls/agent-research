---
phase: quick-260530-iqp
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - packages/wiki-io/src/wiki_io/init_vault.py
  - packages/wiki-io/tests/test_init_vault.py
autonomous: true
requirements: [quick-260530-iqp]

must_haves:
  truths:
    - "init_wiki no longer creates dependencies/ in the vault"
    - "init_wiki no longer creates apps/, packages/, or domains/ container folders in the vault"
    - "init_wiki still creates entities/ and the remaining FIXED_VAULT_DIRS (concepts, architecture, adrs, sources, .templates)"
    - "Container DETECTION metadata is preserved — the manifest 'containers' field is still written from the detector"
  artifacts:
    - path: "packages/wiki-io/src/wiki_io/init_vault.py"
      provides: "Bootstrap with legacy container folder creation removed"
      contains: "FIXED_VAULT_DIRS"
    - path: "packages/wiki-io/tests/test_init_vault.py"
      provides: "Regression test asserting legacy folders are absent and canonical dirs present"
  key_links:
    - from: "init_vault.py init_wiki"
      to: "manifest layout['containers']"
      via: "pinned = _resolve_pinned_containers(...)"
      pattern: "containers.*pinned|pinned.*containers"
---

<objective>
Remove legacy container-folder scaffolding from vault bootstrap. The `dependencies/`,
`apps/`, `packages/`, and `domains/` folders are dead remnants from before the switch
to a single canonical `entities/` folder. Bootstrap should stop materializing them
while preserving the container-DETECTION metadata that downstream consumers still read.

Purpose: Stop seeding empty/dead folders in every new vault. Aligns bootstrap with the
entities-folder model without breaking the manifest contract.
Output: Edited `init_vault.py` (no folder mkdir for legacy containers) + updated tests.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.claude/rules/backward-compatibility.md

# Scope guardrails (from quick-task constraints):
# - Edit ONLY packages/wiki-io/src/wiki_io/init_vault.py and its test file.
# - DO NOT touch update.py, upsert.py, _ignore.py, workspace-io/init.py,
#   _workspace.py, or any graph-wiki-agent file (owned by concurrent sibling tasks).
# - scan_monorepo.py / lint/container.py / templates / prompt fragments are OUT OF
#   SCOPE — note as deferred follow-up if relevant, do NOT edit.

<interfaces>
<!-- Key facts verified during planning. Executor needs no further codebase exploration. -->

From init_vault.py (current state):
- FIXED_VAULT_DIRS (line 46-54): ["concepts", "architecture", "adrs", "entities",
  "sources", "dependencies", ".templates"] — drop "dependencies".
- init_wiki (line 190-196):
    pinned = _resolve_pinned_containers(repo_path, non_interactive, workspace_path=...)
    structural_dirs = [c["vault_dir"] for c in pinned if c["vault_dir"]]   # line 191
    ...
    for d in structural_dirs + FIXED_VAULT_DIRS:                           # line 195
        (wiki_path / d).mkdir(parents=True, exist_ok=True)                 # line 196
  `structural_dirs` is consumed ONLY by this mkdir loop (verified via grep — no other
  reference in the source tree).
- `pinned` is also written to the manifest at line 270 (`"containers": pinned`) and is
  consumed downstream by scan_monorepo.py (916, 1409), lint_wiki.py (243, 335),
  lint/container.py (36). KEEP `pinned` and the manifest write intact — only remove the
  folder mkdir. Detection metadata stays.

From test_init_vault.py:
- Existing bootstrap tests monkeypatch `_workspace_init` and `_resolve_pinned_containers`
  to no-ops, then call `init_vault.init_wiki(wiki, repo, topic=..., tool="claude-code",
  force=False, non_interactive=True)`. Reuse this exact pattern.
- test_entities_in_fixed_vault_dirs and test_entities_dir_bootstrapped_after_init_wiki
  already assert the entities path — do not regress them.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Stop bootstrapping legacy container folders in init_vault</name>
  <files>packages/wiki-io/src/wiki_io/init_vault.py</files>
  <behavior>
    After init_wiki runs (with _resolve_pinned_containers stubbed to return a non-empty
    pinned list containing vault_dir values like "apps"/"packages"/"domains"):
    - wiki/dependencies/ does NOT exist
    - wiki/apps/, wiki/packages/, wiki/domains/ do NOT exist (the container vault_dirs are
      no longer materialized)
    - wiki/entities/, wiki/concepts/, wiki/architecture/, wiki/adrs/, wiki/sources/,
      wiki/.templates/ DO exist
    - The manifest layout still carries "containers" == pinned (detection metadata intact)
  </behavior>
  <action>
    In FIXED_VAULT_DIRS, remove the "dependencies" entry (currently line 52). Leave the
    remaining six entries unchanged.

    In init_wiki, remove the materialization of detected container folders: delete the
    `structural_dirs` assignment (line 191) and change the mkdir loop (line 195) to iterate
    over FIXED_VAULT_DIRS only — `for d in FIXED_VAULT_DIRS:`. This is the surgical change;
    do not restructure surrounding code.

    Keep `pinned = _resolve_pinned_containers(...)` (line 190) and the manifest write
    `"containers": pinned` (line 270) exactly as-is — detection metadata must survive for
    downstream scan/lint consumers. Per backward-compatibility.md, entity content is
    regenerable, so no migration of existing vaults is required.

    Do not touch the init success/next-steps messages that mention `wiki/packages/`
    (lines 309/327) — those are cosmetic strings flagged OUT OF SCOPE in the todo; note
    them as a deferred follow-up in the summary, do not edit.
  </action>
  <verify>
    <automated>cd /Users/pat/Personal/agent-research && uv run --package wiki-io pytest packages/wiki-io/tests/test_init_vault.py -x -q</automated>
  </verify>
  <done>
    FIXED_VAULT_DIRS no longer contains "dependencies"; the mkdir loop iterates over
    FIXED_VAULT_DIRS only; `pinned`/manifest "containers" write unchanged; existing
    init_vault tests still pass.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Regression test — legacy folders absent, canonical dirs present</name>
  <files>packages/wiki-io/tests/test_init_vault.py</files>
  <behavior>
    New test that monkeypatches _workspace_init to a no-op and _resolve_pinned_containers
    to return a NON-EMPTY list whose entries include vault_dir values "apps", "packages",
    "domains" (mimicking a multi-container repo). After init_wiki:
    - assert NOT (wiki / "dependencies").exists()
    - assert NOT (wiki / "apps").exists()
    - assert NOT (wiki / "packages").exists()
    - assert NOT (wiki / "domains").exists()
    - assert (wiki / "entities").is_dir()
    - assert (wiki / d).is_dir() for d in the remaining FIXED_VAULT_DIRS
      (concepts, architecture, adrs, sources, .templates)
    Separately assert "dependencies" not in FIXED_VAULT_DIRS (mirror the style of the
    existing test_entities_in_fixed_vault_dirs).
  </behavior>
  <action>
    Add a focused regression test to test_init_vault.py reusing the established fixture
    pattern (tmp_path repo with a pyproject.toml, workspace/wiki under tmp_path,
    monkeypatch init_vault._workspace_init and init_vault._resolve_pinned_containers).
    For this test, stub _resolve_pinned_containers to return a list of dicts shaped like
    the detector output, e.g. entries with keys source/vault_dir/classification/
    children_count where vault_dir is "apps", "packages", "domains" — this proves the
    container vault_dirs are no longer materialized even when detection returns them.
    Also add the simple FIXED_VAULT_DIRS membership assertion for "dependencies".
    Keep additions minimal and matching existing test style; do not refactor existing tests.
  </action>
  <verify>
    <automated>cd /Users/pat/Personal/agent-research && uv run --package wiki-io pytest packages/wiki-io/tests/test_init_vault.py -x -q</automated>
  </verify>
  <done>
    New regression test passes and would fail against the pre-change code (legacy folders
    created). Full test_init_vault.py suite green.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| (none new) | Pure local filesystem scaffolding; no untrusted input crosses a boundary in this change |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-iqp-01 | Tampering | init_wiki manifest "containers" write | mitigate | Leave `pinned`/manifest write untouched; verified downstream consumers (scan/lint) still read it. Tests confirm detection metadata path unchanged. |
| T-iqp-02 | Denial of Service | bootstrap dir creation | accept | Removing dirs cannot break existing vaults — entity/container content is regenerable per backward-compatibility.md; no migration burden until v2. |

No package installs in this plan — package-legitimacy gate not applicable.
</threat_model>

<verification>
- `uv run --package wiki-io pytest packages/wiki-io/tests/test_init_vault.py -q` is green.
- grep confirms `structural_dirs` no longer appears in init_vault.py and FIXED_VAULT_DIRS
  has no "dependencies" entry.
- grep confirms `"containers": pinned` still present at the manifest write.
</verification>

<success_criteria>
- Bootstrap creates exactly: concepts, architecture, adrs, entities, sources, .templates
  (plus the per-section/entities index seeding already present).
- No dependencies/apps/packages/domains folders created, even when detection pins them.
- Container detection metadata preserved in the manifest.
- Only init_vault.py and test_init_vault.py modified; no sibling-owned files touched.
</success_criteria>

<output>
Create `.planning/quick/260530-iqp-remove-legacy-container-folders-from-boo/260530-iqp-SUMMARY.md` when done.
Note any deferred follow-up (cosmetic `wiki/packages/` strings at init_vault.py:309/327;
broader scan/lint/template/prompt alignment) as out-of-scope items for a future task.
</output>
