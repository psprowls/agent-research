---
quick_id: 260523-iws
type: execute
wave: 1
depends_on: []
files_modified:
  - packages/vault-io/src/vault_io/scan_monorepo.py
  - packages/vault-io/src/vault_io/layout_io.py
  - packages/vault-io/tests/test_scan_companion_fold.py
  - packages/vault-io/tests/test_overview_template_wikilinks.py
  - plugins/graph-wiki/agents/scanner.md
  - plugins/graph-wiki/skills/graph-wiki/references/scan-workflow.md
  - agents/graph-wiki-agent/src/graph_wiki_agent/prompts/_fragments/page_categories.py
autonomous: true
requirements: []

must_haves:
  truths:
    - "vault-io scanner emits `overview.md` (not `<dir>/<dir>.md`) for apps, top-level packages, and domain-scoped packages."
    - "vault-io `_load_existing_pages` detects parent overviews by filename == `overview.md` only — no `stem == parent.name` fallback."
    - "`ensure_domain_page` in layout_io writes `<domain>/overview.md` (not `<domain>/<domain>.md`)."
    - "`uv run --package vault-io pytest` passes."
    - "`uv run --package graph-wiki-agent pytest` passes."
    - "Plugin scanner.md, scan-workflow.md, and page_categories.py describe the `overview.md` naming everywhere."
    - "The live wiki at `/Users/pat/Personal/graph-wiki/agent-research/wiki/` has 7 renamed pages now named `overview.md` and an updated `index.md` whose package wikilinks point at `…/overview|…` form."
    - "No `[[wiki/.../<name>/<name>…]]` explicit wikilink to the 7 renamed pages remains anywhere in the vault."
    - "iCloud Obsidian mirror reflects the rename (or the executor reports the mirror path was not found and skipped, per scope §5)."
  artifacts:
    - path: "packages/vault-io/src/vault_io/scan_monorepo.py"
      provides: "Routing emits `overview.md` for all three branches in `_wiki_relative_path_for`; detection uses `md.name == 'overview.md'` in `_load_existing_pages`."
      contains: "overview.md"
    - path: "packages/vault-io/src/vault_io/layout_io.py"
      provides: "`ensure_domain_page` writes `domain_dir / 'overview.md'`."
      contains: "overview.md"
    - path: ".planning/quick/260523-iws-rename-overview-pages/260523-iws-SUMMARY.md"
      provides: "Quick-task summary recording the rename, test results, vault diff stats, and iCloud sync status."
  key_links:
    - from: "packages/vault-io/src/vault_io/scan_monorepo.py"
      to: "packages/vault-io/src/vault_io/layout_io.py"
      via: "shared filename convention (`overview.md`) — routing and write paths must agree"
      pattern: "overview\\.md"
    - from: "plugins/graph-wiki/agents/scanner.md"
      to: "packages/vault-io/src/vault_io/scan_monorepo.py"
      via: "instruction markdown describes the same naming convention the scanner emits"
      pattern: "overview\\.md"
    - from: "/Users/pat/Personal/graph-wiki/agent-research/wiki/index.md"
      to: "renamed package pages"
      via: "wikilinks of the form `[[wiki/<container>/<name>/overview|<name>]]`"
      pattern: "/overview\\|"
---

<objective>
Reverse the prior decision to name wiki overview pages `<dir-name>.md`. Going forward, every app/package/domain overview page is named `overview.md`. Update the vault-io scanner code + tests, the graph-wiki plugin instruction markdown + the agent prompt fragment, rename the 7 live pages in the agent-research wiki, rewrite explicit wikilinks in `index.md` (and anywhere else), and sync the iCloud Obsidian mirror.

Purpose: Cleaner, more predictable file naming (`overview.md` is self-describing; doesn't require knowing the parent dir name to find the entry page). Locked decision — no backwards-compatible fallback.

Output:
- Code/tests/docs in main repo updated and committed in one atomic commit.
- 7 live wiki pages renamed via `git mv` (wiki is its own git repo) + `index.md` wikilinks updated + any other explicit `[[…/<name>/<name>…]]` wikilinks rewritten, committed in the wiki repo.
- iCloud mirror cp'd or explicitly reported as skipped.
- SUMMARY.md written.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@./CLAUDE.md
@./plugins/graph-wiki/CLAUDE.md

# Files this plan modifies (read first):
@packages/vault-io/src/vault_io/scan_monorepo.py
@packages/vault-io/src/vault_io/layout_io.py
@packages/vault-io/tests/test_scan_companion_fold.py
@packages/vault-io/tests/test_overview_template_wikilinks.py
@plugins/graph-wiki/agents/scanner.md
@plugins/graph-wiki/skills/graph-wiki/references/scan-workflow.md
@agents/graph-wiki-agent/src/graph_wiki_agent/prompts/_fragments/page_categories.py

# Live wiki (separate git repo) — read before renaming:
@/Users/pat/Personal/graph-wiki/agent-research/wiki/index.md

# iCloud mirror path reference:
@/Users/pat/.claude/projects/-Users-pat-Personal-agent-research/memory/reference_icloud_obsidian_mirror.md

<interfaces>
Routing function signature (unchanged), only the return strings change:

From packages/vault-io/src/vault_io/scan_monorepo.py:
```python
def _wiki_relative_path_for(pkg: dict, vault_dir: str | None = None) -> str:
    # Currently returns:
    #   apps:                      f"apps/{name}/{name}.md"
    #   domain-scoped:             f"domains/{domain}/packages/{name}/{name}.md"
    #   default (or pinned dir):   f"{base}/{name}/{name}.md"
    # New behavior: replace the trailing `{name}.md` with `overview.md` in all three return statements.
```

Detection pattern (currently `md.stem != md.parent.name`) appears in two locations inside `_load_existing_pages`:
- inside the `_collect` helper's first pass (~line 800)
- inside the domains sweep first pass (~line 846)
Replace with `md.name != "overview.md"` (and the matching `==` variant if present). Update the comment block around line 794–797 that says "A parent overview is the .md whose stem matches its parent directory name".

Write helper signature (unchanged), only the dest path changes:
```python
def ensure_domain_page(domain_dir: Path, domain_title: str, templates_dir: Path, today: Optional[str] = None) -> tuple[Path, bool]:
    # was: dest = domain_dir / f"{domain_dir.name}.md"
    # new: dest = domain_dir / "overview.md"
```
</interfaces>

<locked_decision>
Detection uses `overview.md` ONLY. No backwards-compatible fallback for `<dir>/<dir>.md`. Other vaults predating this change need manual migration. Do not add any compatibility shim.
</locked_decision>
</context>

<tasks>

<task type="auto" tdd="false">
  <name>Task 1: Rename in vault-io code + tests, run vault-io test suite</name>
  <files>
    packages/vault-io/src/vault_io/scan_monorepo.py,
    packages/vault-io/src/vault_io/layout_io.py,
    packages/vault-io/tests/test_scan_companion_fold.py,
    packages/vault-io/tests/test_overview_template_wikilinks.py
  </files>
  <action>
Update vault-io to emit and detect `overview.md` instead of `<dir>/<dir>.md`. Locked decision: detection uses `overview.md` ONLY — do NOT introduce any fallback to the old `stem == parent.name` form.

1. `packages/vault-io/src/vault_io/scan_monorepo.py` — `_wiki_relative_path_for()` (around lines 551–573):
   - Change `f"apps/{name}/{name}.md"` → `f"apps/{name}/overview.md"`.
   - Change `f"domains/{domain}/packages/{name}/{name}.md"` → `f"domains/{domain}/packages/{name}/overview.md"`.
   - Change `f"{base}/{name}/{name}.md"` → `f"{base}/{name}/overview.md"`.
   - Update the docstring routing lines (lines 555–557) to use `overview.md` instead of `<name>/<name>.md`.

2. `packages/vault-io/src/vault_io/scan_monorepo.py` — `_load_existing_pages()` (around lines 767–880):
   - In the `_collect` helper first pass (around line 794), replace `if md.stem != md.parent.name:` with `if md.name != "overview.md":`. Update the surrounding comment "A parent overview is the .md whose stem matches its parent directory name (e.g. packages/vault-io/vault-io.md). Its workflow_hints frontmatter…" to "A parent overview is the file named `overview.md` (e.g. packages/vault-io/overview.md). Its workflow_hints frontmatter…".
   - In the domains first-pass (around line 847), replace `if md.stem != md.parent.name:` with `if md.name != "overview.md":`.
   - Scan the rest of the function for any other site that uses `stem == parent.name` / `stem != parent.name` as an overview-detection idiom and rewrite the same way. (Grep the file for `md.parent.name` to be sure none are missed.)

3. `packages/vault-io/src/vault_io/layout_io.py` — `ensure_domain_page()` (around line 174–199):
   - Change `dest = domain_dir / f"{domain_dir.name}.md"` to `dest = domain_dir / "overview.md"`.
   - Update the docstring at line 180 from "Create <domain>/<domain>.md from the overview template if it doesn't exist." to "Create <domain>/overview.md from the overview template if it doesn't exist.".
   - Scan the rest of `layout_io.py` for any other `f"{...dir.name}.md"` pattern used for overview writes and rewrite to `"overview.md"`. (Grep for `.name}.md"`.)

4. `packages/vault-io/tests/test_scan_companion_fold.py`:
   - Line ~131: change `(pkg_dir / "pkg-x.md").write_text(...)` → `(pkg_dir / "overview.md").write_text(...)`.
   - Line ~162: change `(app_dir / "foo.md").write_text(...)` → `(app_dir / "overview.md").write_text(...)`.

5. `packages/vault-io/tests/test_overview_template_wikilinks.py`:
   - Line 5 docstring: change `packages/foo/foo.md` → `packages/foo/overview.md`.
   - Lines 32 and 83 already use generic stems via `tmp_path / "myslug.md"` and `tmp_path / f"{container}.md"` — they are template-render destinations, not overview-detection paths, so leave them. (The tests run `render_template`, not `_load_existing_pages`, so the dest filename is incidental.) Confirm by re-reading and noting in the task summary.

6. Run the vault-io test suite from the repo root:
   ```
   uv run --package vault-io pytest
   ```
   Fix anything else that breaks. Most likely additional fixture-creation sites in other test files use the old `<dir>.md` convention; grep `packages/vault-io/tests/` for `parent.name`, `pkg-x.md`, `foo.md`, `{name}.md` write_text sites and rewrite the same way. If a test asserts on the old return-path string (`apps/foo/foo.md` etc.), update the expected string to `apps/foo/overview.md`.
  </action>
  <verify>
    <automated>uv run --package vault-io pytest</automated>
  </verify>
  <done>
    All vault-io code emits and detects `overview.md`. `uv run --package vault-io pytest` passes (~127+ tests). Grep `packages/vault-io/src/` for `parent.name` confirms no remaining `stem == parent.name` overview-detection sites. Grep `packages/vault-io/` for `{name}.md"` and `{domain_dir.name}.md"` returns no matches in production code paths.
  </done>
</task>

<task type="auto" tdd="false">
  <name>Task 2: Update plugin instruction markdown + agent prompt fragment, run graph-wiki-agent tests</name>
  <files>
    plugins/graph-wiki/agents/scanner.md,
    plugins/graph-wiki/skills/graph-wiki/references/scan-workflow.md,
    agents/graph-wiki-agent/src/graph_wiki_agent/prompts/_fragments/page_categories.py
  </files>
  <action>
Rewrite every doc/prompt site that describes the old `<dir>/<dir>.md` overview naming.

1. `plugins/graph-wiki/agents/scanner.md`:
   - Line 15: rewrite "the overview file inside is named to match (e.g. `<workspace>/wiki/packages/foo/foo.md`)" → "the overview file inside is always named `overview.md` (e.g. `<workspace>/wiki/packages/foo/overview.md`)".
   - Lines 48–52 (Section 3 "Create stubs for new packages") and line 58: replace every `<workspace>/wiki/packages/<name>/<name>.md`, `<workspace>/wiki/domains/<d>/packages/<name>/<name>.md`, `<workspace>/wiki/apps/<name>/<name>.md`, and `<workspace>/wiki/<container>/<name>/<name>.md` with the `…/<name>/overview.md` form. The `[[wiki/<container>/<slug>/api|api]]` example wikilinks stay as-is — they point to sub-pages, not the overview.
   - Section 6 (Renames, lines 82–83): rewrite "rename the overview file inside to match (`<new>.md`)" → "the overview file inside stays named `overview.md` (only the parent folder rename + frontmatter+wikilink updates are needed)".

2. `plugins/graph-wiki/skills/graph-wiki/references/scan-workflow.md`:
   - Line 7: rewrite "with the overview file inside named to match the folder (e.g. `<workspace>/wiki/apps/web-next-ts/web-next-ts.md`, `<workspace>/wiki/packages/common-aws-node-ts/common-aws-node-ts.md`)" → "with the overview file inside always named `overview.md` (e.g. `<workspace>/wiki/apps/web-next-ts/overview.md`, `<workspace>/wiki/packages/common-aws-node-ts/overview.md`)".
   - Lines 68–72 (routing rules table): replace the three `…/<name>/<name>.md` destinations with `…/<name>/overview.md`.
   - Lines 102–117 (rename procedure): rewrite "git mv <workspace>/wiki/packages/<old>/ <workspace>/wiki/packages/<new>/ then git mv <workspace>/wiki/packages/<new>/<old>.md <workspace>/wiki/packages/<new>/<new>.md" → "git mv <workspace>/wiki/packages/<old>/ <workspace>/wiki/packages/<new>/ (the overview file inside is always `overview.md`, so no inner rename is needed)".
   - Section 205 (After-scan tips): rewrite "Domain pages (`<d>.md` plus `details.md` …)" → "Domain pages (`overview.md` plus `details.md` …)".
   - Anywhere else in this file referencing `<name>/<name>.md` / `<d>/<d>.md` style overview paths, rewrite to `overview.md`. Grep for `name>.md` and `d>.md` to be thorough.

3. `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/_fragments/page_categories.py`:
   - Lines 8–10: change three Directory cells:
     - `vault_path/apps/<app>/<app>.md` → `vault_path/apps/<app>/overview.md`
     - `vault_path/packages/<pkg>/<pkg>.md` → `vault_path/packages/<pkg>/overview.md`
     - `vault_path/domains/<domain>/<domain>.md` → `vault_path/domains/<domain>/overview.md`
   - Line 1 source-of-truth comment notes the SKILL.md page-categories block. If `plugins/graph-wiki/skills/graph-wiki/SKILL.md` contains the same table, update it for consistency (grep for `vault_path/apps/` in the SKILL.md to confirm).

4. Grep the broader plugin tree for any other `<name>/<name>.md` / `<d>/<d>.md` references that drifted in: `grep -rn -E '<(name|app|pkg|d|domain|slug)>/<(\1)>\.md' plugins/ agents/graph-wiki-agent/src/`. Rewrite each match to `overview.md`.

5. Run the graph-wiki-agent test suite:
   ```
   uv run --package graph-wiki-agent pytest
   ```
   Fix anything that breaks (most likely a snapshot or string assertion that compared exact prompt text).
  </action>
  <verify>
    <automated>uv run --package graph-wiki-agent pytest && grep -rn -E '<(name|app|pkg|d|domain|slug)>/<(name|app|pkg|d|domain|slug)>\.md' plugins/graph-wiki/agents plugins/graph-wiki/skills agents/graph-wiki-agent/src | grep -v 'overview\.md' || echo "no drift remaining"</automated>
  </verify>
  <done>
    All three doc/prompt files describe `overview.md` naming. `uv run --package graph-wiki-agent pytest` passes. Grep across `plugins/graph-wiki/` and `agents/graph-wiki-agent/src/` shows no remaining `<name>/<name>.md` style references for overview pages.
  </done>
</task>

<task type="auto" tdd="false">
  <name>Task 3: Commit code/test/doc changes to agent-research repo</name>
  <files>
    packages/vault-io/src/vault_io/scan_monorepo.py,
    packages/vault-io/src/vault_io/layout_io.py,
    packages/vault-io/tests/test_scan_companion_fold.py,
    packages/vault-io/tests/test_overview_template_wikilinks.py,
    plugins/graph-wiki/agents/scanner.md,
    plugins/graph-wiki/skills/graph-wiki/references/scan-workflow.md,
    agents/graph-wiki-agent/src/graph_wiki_agent/prompts/_fragments/page_categories.py
  </files>
  <action>
One atomic commit covering Tasks 1 and 2. Stage only the files listed in `<files>` (plus any additional vault-io test files or SKILL.md edited during fix-ups in Tasks 1/2). Use `git status` to confirm before staging — do NOT use `git add -A`.

Commit message (HEREDOC):

```
refactor(quick-260523-iws): rename wiki overview pages to overview.md

Reverse the prior `<dir-name>.md` convention. Overview pages now stay
named `overview.md` everywhere — cleaner, self-describing, and removes
the implicit "filename mirrors parent dir name" coupling.

- vault-io scanner routing (`_wiki_relative_path_for`) emits
  `overview.md` for apps, top-level packages, and domain-scoped packages
- vault-io detection (`_load_existing_pages`) matches `overview.md`
  filename only; no `stem == parent.name` fallback (locked decision —
  other vaults predating this change need manual migration)
- `ensure_domain_page` writes `<domain>/overview.md`
- Plugin scanner.md, scan-workflow.md, and the graph-wiki-agent
  page_categories prompt fragment describe the new naming
- Fixture overview writes in test_scan_companion_fold.py updated
- vault-io + graph-wiki-agent test suites pass

Live wiki rename + iCloud mirror sync handled in the wiki repo
(separate commit at /Users/pat/Personal/graph-wiki/agent-research/).
```

Run `git status` afterward to confirm a clean working tree (the wiki rename happens in Task 4 in a different repo).
  </action>
  <verify>
    <automated>git log -1 --pretty=format:'%s' | grep -q 'quick-260523-iws.*overview' &amp;&amp; git status --short</automated>
  </verify>
  <done>
    One commit lands on `main` with the scope described above. `git status` in the agent-research repo shows a clean tree.
  </done>
</task>

<task type="auto" tdd="false">
  <name>Task 4: Rename 7 wiki pages + rewrite explicit wikilinks + commit in wiki repo</name>
  <files>
    /Users/pat/Personal/graph-wiki/agent-research/wiki/packages/vault-io/overview.md,
    /Users/pat/Personal/graph-wiki/agent-research/wiki/packages/model-adapter/overview.md,
    /Users/pat/Personal/graph-wiki/agent-research/wiki/packages/eval-harness/overview.md,
    /Users/pat/Personal/graph-wiki/agent-research/wiki/packages/subagent-runtime/overview.md,
    /Users/pat/Personal/graph-wiki/agent-research/wiki/packages/workspace-io/overview.md,
    /Users/pat/Personal/graph-wiki/agent-research/wiki/agents/graph-wiki-agent/overview.md,
    /Users/pat/Personal/graph-wiki/agent-research/wiki/plugins/graph-wiki/overview.md,
    /Users/pat/Personal/graph-wiki/agent-research/wiki/index.md
  </files>
  <action>
The wiki at `/Users/pat/Personal/graph-wiki/agent-research/` is its own git repo (confirmed during planning: `git -C ... rev-parse --git-dir` → `.git`). Use `git mv` to preserve history.

1. Rename 7 pages (run from the wiki repo root):
   ```
   cd /Users/pat/Personal/graph-wiki/agent-research
   git mv wiki/packages/vault-io/vault-io.md         wiki/packages/vault-io/overview.md
   git mv wiki/packages/model-adapter/model-adapter.md wiki/packages/model-adapter/overview.md
   git mv wiki/packages/eval-harness/eval-harness.md   wiki/packages/eval-harness/overview.md
   git mv wiki/packages/subagent-runtime/subagent-runtime.md wiki/packages/subagent-runtime/overview.md
   git mv wiki/packages/workspace-io/workspace-io.md   wiki/packages/workspace-io/overview.md
   git mv wiki/agents/graph-wiki-agent/graph-wiki-agent.md wiki/agents/graph-wiki-agent/overview.md
   git mv wiki/plugins/graph-wiki/graph-wiki.md        wiki/plugins/graph-wiki/overview.md
   ```

2. Update `wiki/index.md` lines 11–17. The current form is `[[wiki/<container>/<name>/<name>|<name>]]`; rewrite each of the 7 to `[[wiki/<container>/<name>/overview|<name>]]`:
   - `[[wiki/packages/eval-harness/eval-harness|eval-harness]]` → `[[wiki/packages/eval-harness/overview|eval-harness]]`
   - `[[wiki/plugins/graph-wiki/graph-wiki|graph-wiki]]` → `[[wiki/plugins/graph-wiki/overview|graph-wiki]]`
   - `[[wiki/agents/graph-wiki-agent/graph-wiki-agent|graph-wiki-agent]]` → `[[wiki/agents/graph-wiki-agent/overview|graph-wiki-agent]]`
   - `[[wiki/packages/model-adapter/model-adapter|model-adapter]]` → `[[wiki/packages/model-adapter/overview|model-adapter]]`
   - `[[wiki/packages/subagent-runtime/subagent-runtime|subagent-runtime]]` → `[[wiki/packages/subagent-runtime/overview|subagent-runtime]]`
   - `[[wiki/packages/vault-io/vault-io|vault-io]]` → `[[wiki/packages/vault-io/overview|vault-io]]`
   - `[[wiki/packages/workspace-io/workspace-io|workspace-io]]` → `[[wiki/packages/workspace-io/overview|workspace-io]]`

3. Grep the entire wiki for any other explicit wikilinks pointing to the 7 renamed pages. Naked `[[X]]` links resolve via glob fallback and stay valid — only path-qualified forms need rewriting:
   ```
   cd /Users/pat/Personal/graph-wiki/agent-research
   grep -rn -E '\[\[[^]]*/(vault-io/vault-io|model-adapter/model-adapter|eval-harness/eval-harness|subagent-runtime/subagent-runtime|workspace-io/workspace-io|graph-wiki-agent/graph-wiki-agent|graph-wiki/graph-wiki)(\||\]\])' wiki/
   ```
   For every match, rewrite the path segment from `<name>/<name>` to `<name>/overview`. Preserve the display alias after `|`. If a match has no alias (`[[…/vault-io/vault-io]]`), add one to keep the readable label: `[[…/vault-io/overview|vault-io]]`.

4. Stage and commit in the wiki repo:
   ```
   cd /Users/pat/Personal/graph-wiki/agent-research
   git add -A wiki/
   git status   # confirm only the 7 renames + index.md + any wikilink rewrites
   git commit -m "$(cat <<'EOF'
   refactor: rename package/app/plugin overview pages to overview.md

   Match the scanner's new convention (agent-research quick-260523-iws):
   overview pages are now always named overview.md, not <dir>/<dir>.md.

   - Renamed 7 overview files via git mv (history preserved)
   - Updated index.md wikilinks to the new path form
   - Rewrote any explicit path-qualified wikilinks pointing to the
     renamed pages; naked [[X]] links continue to resolve via glob

   EOF
   )"
   ```
  </action>
  <verify>
    <automated>cd /Users/pat/Personal/graph-wiki/agent-research &amp;&amp; ls wiki/packages/vault-io/overview.md wiki/packages/model-adapter/overview.md wiki/packages/eval-harness/overview.md wiki/packages/subagent-runtime/overview.md wiki/packages/workspace-io/overview.md wiki/agents/graph-wiki-agent/overview.md wiki/plugins/graph-wiki/overview.md &amp;&amp; ! grep -rn -E '\[\[[^]]*/(vault-io/vault-io|model-adapter/model-adapter|eval-harness/eval-harness|subagent-runtime/subagent-runtime|workspace-io/workspace-io|graph-wiki-agent/graph-wiki-agent|graph-wiki/graph-wiki)(\||\]\])' wiki/ &amp;&amp; git log -1 --pretty=format:'%s' | grep -q overview</automated>
  </verify>
  <done>
    All 7 renamed files exist at their new paths in the wiki repo. `index.md` and any other explicit wikilinks point at the `…/overview|…` form. One commit lands in the wiki repo. `git status` in the wiki repo is clean.
  </done>
</task>

<task type="auto" tdd="false">
  <name>Task 5: Sync iCloud Obsidian mirror</name>
  <files>
    /Users/pat/Library/Mobile Documents/iCloud~md~obsidian/Documents/agent-research/wiki/
  </files>
  <action>
Per the memory note at `/Users/pat/.claude/projects/-Users-pat-Personal-agent-research/memory/reference_icloud_obsidian_mirror.md`, the mirror destination is:

`/Users/pat/Library/Mobile Documents/iCloud~md~obsidian/Documents/agent-research/`

(The wiki repo is `/Users/pat/Personal/graph-wiki/agent-research/` and the iCloud mirror is a manual `cp`-based copy of its `wiki/` tree.)

1. Confirm the destination exists:
   ```
   test -d "/Users/pat/Library/Mobile Documents/iCloud~md~obsidian/Documents/agent-research/wiki" && echo "mirror present" || echo "MIRROR MISSING — skip and report"
   ```

2. If present, mirror the 7 renamed overviews + the rewritten `index.md` (and any other files touched in Task 4):
   - Remove stale `<name>/<name>.md` overview copies first so the mirror doesn't carry both forms:
     ```
     rm "/Users/pat/Library/Mobile Documents/iCloud~md~obsidian/Documents/agent-research/wiki/packages/vault-io/vault-io.md" 2>/dev/null
     rm "/Users/pat/Library/Mobile Documents/iCloud~md~obsidian/Documents/agent-research/wiki/packages/model-adapter/model-adapter.md" 2>/dev/null
     rm "/Users/pat/Library/Mobile Documents/iCloud~md~obsidian/Documents/agent-research/wiki/packages/eval-harness/eval-harness.md" 2>/dev/null
     rm "/Users/pat/Library/Mobile Documents/iCloud~md~obsidian/Documents/agent-research/wiki/packages/subagent-runtime/subagent-runtime.md" 2>/dev/null
     rm "/Users/pat/Library/Mobile Documents/iCloud~md~obsidian/Documents/agent-research/wiki/packages/workspace-io/workspace-io.md" 2>/dev/null
     rm "/Users/pat/Library/Mobile Documents/iCloud~md~obsidian/Documents/agent-research/wiki/agents/graph-wiki-agent/graph-wiki-agent.md" 2>/dev/null
     rm "/Users/pat/Library/Mobile Documents/iCloud~md~obsidian/Documents/agent-research/wiki/plugins/graph-wiki/graph-wiki.md" 2>/dev/null
     ```
   - Then copy each new `overview.md` + the updated `index.md`:
     ```
     SRC=/Users/pat/Personal/graph-wiki/agent-research/wiki
     DST="/Users/pat/Library/Mobile Documents/iCloud~md~obsidian/Documents/agent-research/wiki"
     cp "$SRC/packages/vault-io/overview.md"          "$DST/packages/vault-io/overview.md"
     cp "$SRC/packages/model-adapter/overview.md"     "$DST/packages/model-adapter/overview.md"
     cp "$SRC/packages/eval-harness/overview.md"      "$DST/packages/eval-harness/overview.md"
     cp "$SRC/packages/subagent-runtime/overview.md"  "$DST/packages/subagent-runtime/overview.md"
     cp "$SRC/packages/workspace-io/overview.md"      "$DST/packages/workspace-io/overview.md"
     cp "$SRC/agents/graph-wiki-agent/overview.md"    "$DST/agents/graph-wiki-agent/overview.md"
     cp "$SRC/plugins/graph-wiki/overview.md"         "$DST/plugins/graph-wiki/overview.md"
     cp "$SRC/index.md"                                "$DST/index.md"
     ```
   - If Task 4 rewrote any additional files (extra explicit-wikilink files surfaced by the grep), `cp` each of those across to its mirror path too.

3. If the destination does NOT exist, do NOT guess an alternate path. Report in the SUMMARY: "iCloud mirror path `/Users/pat/.../agent-research/wiki` not present — skipped per scope §5 (executor should not guess)."
  </action>
  <verify>
    <automated>if [ -d "/Users/pat/Library/Mobile Documents/iCloud~md~obsidian/Documents/agent-research/wiki" ]; then ls "/Users/pat/Library/Mobile Documents/iCloud~md~obsidian/Documents/agent-research/wiki/packages/vault-io/overview.md" "/Users/pat/Library/Mobile Documents/iCloud~md~obsidian/Documents/agent-research/wiki/packages/model-adapter/overview.md" "/Users/pat/Library/Mobile Documents/iCloud~md~obsidian/Documents/agent-research/wiki/packages/eval-harness/overview.md" "/Users/pat/Library/Mobile Documents/iCloud~md~obsidian/Documents/agent-research/wiki/packages/subagent-runtime/overview.md" "/Users/pat/Library/Mobile Documents/iCloud~md~obsidian/Documents/agent-research/wiki/packages/workspace-io/overview.md" "/Users/pat/Library/Mobile Documents/iCloud~md~obsidian/Documents/agent-research/wiki/agents/graph-wiki-agent/overview.md" "/Users/pat/Library/Mobile Documents/iCloud~md~obsidian/Documents/agent-research/wiki/plugins/graph-wiki/overview.md"; else echo "mirror skipped — destination not present"; fi</automated>
  </verify>
  <done>
    Either all 7 `overview.md` files plus `index.md` exist at the iCloud mirror paths AND the 7 stale `<name>/<name>.md` siblings are removed, OR the mirror was not present and the skip is documented in SUMMARY.md.
  </done>
</task>

<task type="auto" tdd="false">
  <name>Task 6: Write SUMMARY.md and update STATE.md Quick Tasks Completed row</name>
  <files>
    .planning/quick/260523-iws-rename-overview-pages/260523-iws-SUMMARY.md,
    .planning/STATE.md
  </files>
  <action>
1. Write `.planning/quick/260523-iws-rename-overview-pages/260523-iws-SUMMARY.md` covering:
   - Quick ID: 260523-iws
   - Description: Rename wiki overview pages from `<dir-name>.md` to `overview.md` everywhere.
   - Files changed (split by repo: agent-research vs. wiki).
   - Test results: vault-io test count and result, graph-wiki-agent test count and result.
   - Locked decision noted: detection uses `overview.md` ONLY, no backwards-compatible fallback.
   - Vault diff: 7 pages renamed via `git mv` in the wiki repo, `index.md` updated, count of additional explicit-wikilink rewrites if any.
   - iCloud mirror status (synced N files / skipped because path not present).
   - Commit SHAs: one in agent-research, one in wikis/agent-research.
   - Follow-up: none in scope. Out-of-scope `.claude/worktrees/agent-*` fixtures are transient and will regenerate on next scan.

2. Append a new row to STATE.md's "Quick Tasks Completed" table:
   ```
   | 260523-iws-rename-overview-pages | Rename wiki overview pages from `<dir-name>.md` to `overview.md` everywhere; vault-io scanner + detection (`_wiki_relative_path_for`, `_load_existing_pages`), `ensure_domain_page` write path, plugin scanner.md + scan-workflow.md + page_categories prompt fragment, 7 live wiki pages via `git mv` in separate wiki repo, index.md wikilinks rewritten, iCloud Obsidian mirror sync (or skip note); locked decision: no `<dir>/<dir>.md` fallback. | (this commit) |
   ```
   Update `last_activity` line and the top-of-file `last_updated` timestamp to today (2026-05-23).

3. Commit:
   ```
   git add .planning/quick/260523-iws-rename-overview-pages/260523-iws-SUMMARY.md .planning/STATE.md
   git commit -m "$(cat <<'EOF'
   docs(quick-260523-iws): record overview-rename quick task in SUMMARY + STATE
   EOF
   )"
   ```
  </action>
  <verify>
    <automated>test -f .planning/quick/260523-iws-rename-overview-pages/260523-iws-SUMMARY.md &amp;&amp; grep -q '260523-iws-rename-overview-pages' .planning/STATE.md &amp;&amp; git log -1 --pretty=format:'%s' | grep -q '260523-iws'</automated>
  </verify>
  <done>
    SUMMARY.md exists with the sections listed above. STATE.md has the new row + updated `last_activity` + `last_updated`. One commit lands recording both files.
  </done>
</task>

</tasks>

<verification>
End-of-plan checks (after all 6 tasks):

1. `uv run --package vault-io pytest` — all tests pass.
2. `uv run --package graph-wiki-agent pytest` — all tests pass.
3. `grep -rn 'parent\.name' packages/vault-io/src/` returns no overview-detection use (only legitimate uses like fixture/segment matching).
4. `grep -rn -E '<(name|app|pkg|d|domain|slug)>/<(name|app|pkg|d|domain|slug)>\.md' plugins/graph-wiki/ agents/graph-wiki-agent/src/` returns nothing (or only `overview.md` matches).
5. In `/Users/pat/Personal/graph-wiki/agent-research/wiki/`: 7 `overview.md` pages exist; 0 stale `<dir>/<dir>.md` overview siblings remain in the 7 renamed dirs; `index.md` lines 11–17 link to `…/overview|…` form.
6. agent-research repo: one new commit on `main` for code/tests/docs, one for SUMMARY+STATE. `git status` clean.
7. wikis/agent-research repo: one new commit for the rename + wikilink rewrites. `git status` clean.
8. iCloud mirror: either updated or skip explicitly recorded in SUMMARY.
</verification>

<success_criteria>
- vault-io and graph-wiki-agent test suites pass.
- Scanner code, detection code, write helper, plugin instruction markdown, and agent prompt fragment all describe the `overview.md` convention with no `<dir>/<dir>.md` remnants.
- 7 live wiki overview pages renamed via `git mv` (history preserved).
- `index.md` and any other explicit path-qualified wikilinks to those pages updated to `…/overview|…` form. Naked `[[X]]` links left as-is (resolve via glob).
- iCloud Obsidian mirror synced (or explicit skip note recorded in SUMMARY).
- Three commits land: (1) agent-research code/tests/docs, (2) wikis/agent-research rename + wikilink rewrites, (3) agent-research SUMMARY + STATE.
- STATE.md "Quick Tasks Completed" table has the new row.
</success_criteria>

<output>
After all tasks complete, the following artifacts exist:

- `.planning/quick/260523-iws-rename-overview-pages/260523-iws-SUMMARY.md` (committed in agent-research)
- Updated row in `.planning/STATE.md` "Quick Tasks Completed" table
- Three commits (two in agent-research, one in wikis/agent-research)
- 7 renamed `overview.md` files in the wiki repo and (if mirror present) iCloud
</output>
