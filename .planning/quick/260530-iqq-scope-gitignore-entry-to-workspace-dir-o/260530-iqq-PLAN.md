---
phase: quick-260530-iqq
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - packages/workspace-io/src/workspace_io/init.py
  - packages/workspace-io/tests/test_init.py
autonomous: true
requirements: [QUICK-iqq]

must_haves:
  truths:
    - "When the workspace is contained within a distinct source git repo, the .graph-wiki.local.yaml ignore entry lands in <workspace>/.gitignore"
    - "The host repo-root .gitignore is never mutated by bootstrap"
    - "When the workspace is outside the source repo (standalone, git-init'd), no .gitignore entry is written"
    - "Repeated init() calls do not duplicate the ignore entry"
  artifacts:
    - path: "packages/workspace-io/src/workspace_io/init.py"
      provides: "Workspace-scoped gitignore entry on bootstrap"
      contains: "_ensure_gitignore_entry"
  key_links:
    - from: "init()"
      to: "_ensure_gitignore_entry"
      via: "call passing both workspace and repo_root"
      pattern: "_ensure_gitignore_entry\\("
---

<objective>
Scope the bootstrap gitignore entry to the workspace directory instead of mutating the
host repo-root `.gitignore`.

Currently `init()` calls `_ensure_gitignore_entry(repo_root)` which appends
`.graph-wiki.local.yaml` to `<repo_root>/.gitignore` — noisy and wrong when the workspace
is a subdirectory of an unrelated host repo.

New behavior:
- Workspace contained within a distinct source git repo → write/maintain the entry in
  `<workspace>/.gitignore`. Nested `.gitignore` is standard git behavior; the entry is
  relative to the workspace so no path prefix is needed.
- Workspace outside the source repo (standalone, already `git init`'d by bootstrap) → skip
  the entry entirely (per todo default).
- Never touch the repo-root `.gitignore`.

Purpose: Keep ignore rules local to the directory they govern; stop intrusive repo-root mutation.
Output: Updated `init.py` (logic + docstring/comment) and updated/extended `test_init.py`.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md

@packages/workspace-io/src/workspace_io/init.py
@packages/workspace-io/tests/test_init.py

<interfaces>
<!-- From workspace_io/init.py — current contracts the executor edits. -->

`init(repo_root, *, plugin, version, workspace=None)` — resolves `repo_root` (line 30) and
`workspace` (lines 31-33), both as resolved absolute Paths. Currently calls
`_ensure_gitignore_entry(repo_root)` at line 72.

`_is_inside_git_repo(path) -> bool` (lines 75-80) — True if `path` or any parent contains a
`.git` dir. Reusable for the contained-vs-outside decision.

`_GITIGNORE_ENTRY = ".graph-wiki.local.yaml"` (line 19).

Module docstring (lines 1-7) and the comment at line 71 describe the OLD repo-root behavior
and must be updated.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Scope gitignore entry to the workspace directory</name>
  <files>packages/workspace-io/src/workspace_io/init.py</files>
  <behavior>
    - Workspace inside a distinct source git repo → entry written to `<workspace>/.gitignore`; repo-root `.gitignore` untouched.
    - Workspace NOT contained within a distinct source repo (standalone / outside) → no `.gitignore` entry written anywhere.
    - Idempotent: second init() with the entry already present leaves a single occurrence.
    - `<workspace>/.gitignore` created when absent (in the contained case).
  </behavior>
  <action>
    Change `_ensure_gitignore_entry` to operate on the WORKSPACE rather than the repo root,
    and gate it on containment.

    1. Update the call at line 72 from `_ensure_gitignore_entry(repo_root)` to pass both the
       workspace and repo_root, e.g. `_ensure_gitignore_entry(workspace, repo_root)`.
    2. Change the `_ensure_gitignore_entry` signature to `(workspace: Path, repo_root: Path)`.
       Decide containment: the workspace is "contained within a distinct source repo" when
       `repo_root` is a real git repo AND `workspace` is under `repo_root` AND
       `workspace != repo_root`. Use `repo_root` existing `.git` (reuse the same `.git`-exists
       check style as `_is_inside_git_repo`) and `Path.is_relative_to(repo_root)` for the
       under-repo test. If NOT contained → return early without writing anything (the standalone
       workspace already got its own `git init`; per todo we default to skip).
    3. When contained, write the entry into `<workspace>/.gitignore` using the SAME
       append/create/idempotency logic currently applied to repo-root (read existing lines,
       skip if `_GITIGNORE_ENTRY` already present, otherwise append with a leading newline only
       when needed; create the file with the single entry when absent). The entry stays
       `.graph-wiki.local.yaml` with no path prefix (relative to the workspace).
    4. Update the module docstring (lines 1-7): replace "ensures `.graph-wiki.local.yaml` is
       gitignored" wording so it states the entry is written to the workspace's own `.gitignore`
       when the workspace lives inside the source repo, and skipped otherwise.
    5. Update the comment at line 71 (the `_ensure_gitignore_entry` line) to reflect the new
       workspace-scoped, containment-gated behavior. Keep the D-06 NOTE on line 71 intact.

    Follow Karpathy surgical-change guidance: do not refactor unrelated code; reuse the existing
    idempotent write logic verbatim, only retargeting the path and adding the containment gate.
    Do NOT touch wiki-io, update.py, _workspace.py, or any graph-wiki-agent file.
  </action>
  <verify>
    <automated>uv run --package workspace-io pytest packages/workspace-io/tests/test_init.py -x -q</automated>
  </verify>
  <done>`_ensure_gitignore_entry` writes only to `<workspace>/.gitignore` when contained and skips otherwise; repo-root `.gitignore` is never written; docstring + comment updated.</done>
</task>

<task type="auto">
  <name>Task 2: Update tests for workspace-scoped gitignore behavior</name>
  <files>packages/workspace-io/tests/test_init.py</files>
  <action>
    Replace the three repo-root gitignore tests (`test_appends_local_yaml_to_gitignore`,
    `test_gitignore_append_is_idempotent`, `test_gitignore_created_if_absent` — lines 83-101)
    with tests for the new behavior. Use the existing `_git_init` helper and `tmp_path`.

    Add/replace:
    1. `test_gitignore_entry_in_workspace_when_contained`: `repo = tmp_path; _git_init(repo)`;
       `init(repo, plugin=..., version="1.0.0")` (default workspace `<repo>/graph-wiki`); assert
       `(repo / "graph-wiki" / ".gitignore")` exists and contains `.graph-wiki.local.yaml`.
    2. `test_repo_root_gitignore_untouched`: same setup; assert
       `(repo / ".gitignore")` does NOT exist (or, if you prefer a stricter check, that it does
       not contain `.graph-wiki.local.yaml`). The repo-root file must not be created by bootstrap.
    3. `test_gitignore_entry_idempotent_in_workspace`: run `init` twice with the same plugin on a
       `_git_init`'d `tmp_path`; assert the `<workspace>/.gitignore` text counts
       `.graph-wiki.local.yaml` exactly once.
    4. `test_no_gitignore_entry_when_workspace_outside_repo`: build the external-workspace setup
       like `test_external_workspace_creates_dir` (`repo = tmp_path/"repo"; _git_init(repo)`;
       `workspace = tmp_path/"external"`); `init(repo, ..., workspace=workspace)`; assert
       `(workspace / ".gitignore")` does NOT contain `.graph-wiki.local.yaml` (skip case). If a
       `.gitignore` happens to be created by `git init`, assert the entry is absent rather than
       the file.

    Keep all other existing tests unchanged.
  </action>
  <verify>
    <automated>uv run --package workspace-io pytest packages/workspace-io/tests/test_init.py -q</automated>
  </verify>
  <done>New tests cover contained (entry in workspace, repo-root untouched, idempotent) and outside (no entry) cases; full test_init.py passes.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| bootstrap → host filesystem | `init()` writes files into the workspace and (previously) the host repo root |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-iqq-01 | Tampering | repo-root `.gitignore` mutation | mitigate | Stop writing to repo root; scope writes to `<workspace>/.gitignore` only when the workspace is contained in the repo |
| T-iqq-02 | Tampering | unintended write outside workspace | accept | Containment gate (`is_relative_to(repo_root)`) ensures writes stay within the workspace; standalone case writes nothing |
</threat_model>

<verification>
- `uv run --package workspace-io pytest packages/workspace-io/tests/test_init.py -q` passes.
- Manual: bootstrap into a subdir of a git repo → `<workspace>/.gitignore` has the entry, repo-root `.gitignore` unchanged.
</verification>

<success_criteria>
- Bootstrap never mutates the host repo-root `.gitignore`.
- Contained workspace gets `.graph-wiki.local.yaml` in its own `.gitignore`; outside workspace gets none.
- Idempotent across repeated `init()` calls.
- Only `init.py` and `test_init.py` modified.
</success_criteria>

<output>
Create `.planning/quick/260530-iqq-scope-gitignore-entry-to-workspace-dir-o/260530-iqq-SUMMARY.md` when done
</output>
