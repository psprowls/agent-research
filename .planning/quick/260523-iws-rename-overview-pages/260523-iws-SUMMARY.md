---
quick_id: 260523-iws
type: quick-task-summary
status: complete
date: 2026-05-23
tags: [wiki-io, scanner, overview-pages, wiki-rename, refactor]
key_files:
  modified:
    - packages/wiki-io/src/wiki_io/scan_monorepo.py
    - packages/wiki-io/src/wiki_io/layout_io.py
    - packages/wiki-io/src/wiki_io/lint_wiki.py
    - packages/wiki-io/tests/test_scan_companion_fold.py
    - packages/wiki-io/tests/test_overview_template_wikilinks.py
    - packages/eval-harness/src/eval_harness/divergence/librarian.py
    - packages/eval-harness/src/eval_harness/structural.py
    - agents/graph-wiki-agent/src/graph_wiki_agent/commands/lint.py
    - agents/graph-wiki-agent/src/graph_wiki_agent/prompts/_fragments/architecture_overview.py
    - agents/graph-wiki-agent/src/graph_wiki_agent/prompts/_fragments/page_categories.py
    - agents/graph-wiki-agent/tests/prompts/__snapshots__/test_prompt_snapshots.ambr
    - plugins/graph-wiki/agents/scanner.md
    - plugins/graph-wiki/agents/linter.md
    - plugins/graph-wiki/skills/graph-wiki/SKILL.md
    - plugins/graph-wiki/skills/graph-wiki/README.md
    - plugins/graph-wiki/skills/graph-wiki/references/scan-workflow.md
    - plugins/graph-wiki/skills/graph-wiki/references/wiki-schema.md
    - plugins/graph-wiki/skills/graph-wiki/references/lint-workflow.md
  renamed_fixtures:
    - packages/wiki-io/tests/fixtures/round-trip-vault/packages/*/overview.md (12 files)
  wiki_repo:
    - wiki/packages/wiki-io/overview.md (renamed from wiki-io.md)
    - wiki/packages/model-adapter/overview.md (renamed from model-adapter.md)
    - wiki/packages/eval-harness/overview.md (renamed from eval-harness.md)
    - wiki/packages/subagent-runtime/overview.md (renamed from subagent-runtime.md)
    - wiki/packages/workspace-io/overview.md (renamed from workspace-io.md)
    - wiki/agents/graph-wiki-agent/overview.md (renamed from graph-wiki-agent.md)
    - wiki/plugins/graph-wiki/overview.md (renamed from graph-wiki.md)
    - wiki/index.md (wikilinks rewritten)
    - 28 additional files (concept pages + sources) with wikilink rewrites
decisions:
  - "Detection uses overview.md ONLY — no backwards-compatible fallback for <dir>/<dir>.md (locked decision)"
---

# Quick Task 260523-iws: Rename Wiki Overview Pages to overview.md

**One-liner:** Reversed the `<dir-name>.md` overview page convention to `overview.md` throughout wiki-io scanner/detector code, plugin instruction markdown, agent prompt fragments, and the live agent-research wiki (7 pages renamed via `git mv`).

## What Was Done

### Code Changes (agent-research repo — commit `176cb2c`)

**`packages/wiki-io/src/wiki_io/scan_monorepo.py`**
- `_wiki_relative_path_for()`: all three return branches now emit `overview.md` instead of `<name>.md`
  - `f"apps/{name}/overview.md"`, `f"domains/{domain}/packages/{name}/overview.md"`, `f"{base}/{name}/overview.md"`
- `_load_existing_pages()` `_collect` helper first pass: `md.stem != md.parent.name` → `md.name != "overview.md"`
- `_load_existing_pages()` domains first pass: same replacement
- Updated docstring comments describing the overview detection idiom

**`packages/wiki-io/src/wiki_io/layout_io.py`**
- `ensure_domain_page()`: `dest = domain_dir / f"{domain_dir.name}.md"` → `dest = domain_dir / "overview.md"`
- Updated docstring from `<domain>/<domain>.md` to `<domain>/overview.md`

**`packages/wiki-io/src/wiki_io/lint_wiki.py`** (auto-fixed, Rule 1)
- Overview page detection in lint: `Path(k).parent.name == Path(k).name` → `Path(k).name == "overview.md"`

**`packages/wiki-io/tests/test_scan_companion_fold.py`**
- `pkg_dir / "pkg-x.md"` → `pkg_dir / "overview.md"`
- `app_dir / "foo.md"` → `app_dir / "overview.md"`

**`packages/wiki-io/tests/test_overview_template_wikilinks.py`**
- Docstring example updated: `packages/foo/foo.md` → `packages/foo/overview.md`

**`packages/wiki-io/tests/fixtures/round-trip-vault/`** (auto-fixed, Rule 3)
- 12 fixture overview files renamed: `<name>.md` → `overview.md` in all packages/ and plugins/ directories

**`packages/eval-harness/src/eval_harness/divergence/librarian.py`** (auto-fixed, Rule 1)
- `_resolve_in_wiki()`: added overview-aware resolution before stem-glob fallback
  - Tries `wiki/<slug>/overview.md` and `**/<base>/overview.md` before `**/<base>.md`

**`packages/eval-harness/src/eval_harness/structural.py`** (auto-fixed, Rule 1)
- `_resolve_citation()`: same overview-aware resolution added

**`agents/graph-wiki-agent/src/graph_wiki_agent/commands/lint.py`** (auto-fixed, Rule 1)
- Wikilink resolver now tries `<slug>/overview` before legacy `<slug>/<name>` pattern

**`agents/graph-wiki-agent/src/graph_wiki_agent/prompts/_fragments/page_categories.py`**
- All three Directory cells updated to `overview.md` form

**`agents/graph-wiki-agent/src/graph_wiki_agent/prompts/_fragments/architecture_overview.py`**
- Vault layout comment tree updated to `overview.md` form

**`agents/graph-wiki-agent/tests/prompts/__snapshots__/test_prompt_snapshots.ambr`**
- 5 snapshots updated (system prompts now reflect `overview.md` naming)

**Plugin instruction markdown**
- `plugins/graph-wiki/agents/scanner.md`: Sections 3 and 6 rewritten to `overview.md` form; `ensure_domain_pages` reference updated
- `plugins/graph-wiki/agents/linter.md`: Section B "Contradictions (vault↔code)" updated
- `plugins/graph-wiki/skills/graph-wiki/SKILL.md`: vault layout tree + page categories table updated
- `plugins/graph-wiki/skills/graph-wiki/README.md`: vault layout tree updated
- `plugins/graph-wiki/skills/graph-wiki/references/scan-workflow.md`: Purpose section, routing rules table, package-family domain path, rename procedure, archived path, After-scan tips all updated
- `plugins/graph-wiki/skills/graph-wiki/references/wiki-schema.md`: domain slug path updated
- `plugins/graph-wiki/skills/graph-wiki/references/lint-workflow.md`: Section B updated

### Live Wiki Changes (wikis/agent-research repo — commit `c86dbbb`)

7 pages renamed via `git mv` (history preserved):
- `wiki/packages/wiki-io/wiki-io.md` → `wiki/packages/wiki-io/overview.md`
- `wiki/packages/model-adapter/model-adapter.md` → `wiki/packages/model-adapter/overview.md`
- `wiki/packages/eval-harness/eval-harness.md` → `wiki/packages/eval-harness/overview.md`
- `wiki/packages/subagent-runtime/subagent-runtime.md` → `wiki/packages/subagent-runtime/overview.md`
- `wiki/packages/workspace-io/workspace-io.md` → `wiki/packages/workspace-io/overview.md`
- `wiki/agents/graph-wiki-agent/graph-wiki-agent.md` → `wiki/agents/graph-wiki-agent/overview.md`
- `wiki/plugins/graph-wiki/graph-wiki.md` → `wiki/plugins/graph-wiki/overview.md`

`wiki/index.md` wikilinks rewritten (all 7 package/plugin links to `/overview|...` form).

Additional wikilink rewrites: 29 files total contained explicit `[[wiki/<container>/<name>/<name>...]]` wikilinks. All rewritten via Python replacement script. The wiki commit also included pre-existing pending wiki content updates (new concept pages, index refreshes) that were ready in the working tree.

## Test Results

| Suite | Result | Count |
|-------|--------|-------|
| `uv run --package wiki-io pytest` | PASSED | 142 passed, 1 skipped |
| `uv run --package graph-wiki-agent pytest` | PASSED | 650 passed, 32 skipped |

## Locked Decision

Detection uses `overview.md` ONLY. No backwards-compatible fallback for the old `<dir>/<dir>.md` pattern. Other vaults predating this change need manual migration.

## iCloud Obsidian Mirror Status

Mirror present at `/Users/pat/Library/Mobile Documents/iCloud~md~obsidian/Documents/agent-research/wiki`.

Actions taken:
- Removed 7 stale `<name>.md` overview files
- Copied 7 new `overview.md` files
- Copied updated `index.md`
- Copied 21 updated concept pages (wikilink rewrites + content updates)

## Commit SHAs

| Repo | Hash | Description |
|------|------|-------------|
| agent-research | `176cb2c` | refactor(quick-260523-iws): rename wiki overview pages to overview.md |
| wikis/agent-research | `c86dbbb` | refactor: rename package/app/plugin overview pages to overview.md |
| agent-research (docs) | (this commit) | docs(quick-260523-iws): record overview-rename quick task in SUMMARY + STATE |

## Deviations from Plan

**1. [Rule 1 - Bug] Fixed overview detection in lint_wiki.py**
- Found during: Task 1 verification (grep of production code for `parent.name`)
- Issue: `lint_wiki.py:251` used `Path(k).parent.name == Path(k).name` as overview detection — old pattern
- Fix: changed to `Path(k).name == "overview.md"`
- Files: `packages/wiki-io/src/wiki_io/lint_wiki.py`
- Commit: `176cb2c` (included in main task commit via amend)

**2. [Rule 1 - Bug] Fixed round-trip vault fixture overview files**
- Found during: Task 1 test run (test_scan_companion_fold.py failure)
- Issue: 12 fixture files named `<name>.md` caused companion-fold detection to fail under new `overview.md`-only logic
- Fix: renamed 12 fixture files from `<name>.md` to `overview.md`
- Files: 12 files in `packages/wiki-io/tests/fixtures/round-trip-vault/`
- Commit: `176cb2c`

**3. [Rule 1 - Bug] Fixed eval-harness citation resolvers**
- Found during: Task 2 test run (eval-harness tests failing)
- Issue: `_resolve_in_wiki()` in `librarian.py` and `_resolve_citation()` in `structural.py` resolved `[[packages/lattice-wiki-core]]` via glob `**/lattice-wiki-core.md` — no longer valid after rename
- Fix: added `<slug>/overview.md` and `**/<base>/overview.md` resolution steps before stem-glob fallback
- Files: `packages/eval-harness/src/eval_harness/divergence/librarian.py`, `packages/eval-harness/src/eval_harness/structural.py`
- Commit: `176cb2c`

**4. [Rule 1 - Bug] Fixed lint.py wikilink resolver**
- Found during: Task 2 grep sweep
- Issue: `lint.py` resolved `[[packages/wiki-io]]` style links to `packages/wiki-io/wiki-io` (old stem-match pattern)
- Fix: added `<slug>/overview` check before the legacy `<slug>/<name>` fallback (backwards-compat preserved for old-form links)
- Files: `agents/graph-wiki-agent/src/graph_wiki_agent/commands/lint.py`
- Commit: `176cb2c`

**5. Additional doc files updated beyond plan scope**
- Found during: grep sweep per plan step
- Files updated: `linter.md`, `SKILL.md`, `README.md`, `lint-workflow.md`, `wiki-schema.md`, `architecture_overview.py` — all contained old `<name>/<name>.md` patterns
- These were in scope per Task 2 Step 4 (broad grep + rewrite)

**6. Wiki commit included pre-existing uncommitted changes**
- Found during: Task 4 (git status showed pre-existing changes in wiki working tree)
- Decision: included per `git add -A wiki/` in the plan — all are valid wiki content updates (new concept pages, index refreshes from recent ingests) that were pending commit in the wiki repo

## Follow-up

- Out-of-scope `.claude/worktrees/agent-*` fixtures are transient and will regenerate on next scan
- Other vaults (if any) predating this change need manual `git mv` migration — no compat shim per locked decision
