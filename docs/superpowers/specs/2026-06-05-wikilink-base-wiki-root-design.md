---
title: Standardize wikilink base on the wiki root
date: 2026-06-05
status: approved
---

# Standardize wikilink base on the wiki root

## Problem

`graph-wiki:lint` reports spurious broken wikilinks. The root cause is an
inconsistency in which directory the codebase treats as the base for
vault-relative paths and wikilink resolution:

- **Wiki root** (`<workspace>/wiki/`) — used by `query.py` and
  `backlink_index.py`. A link `[[concepts/foo]]` resolves to
  `wiki/concepts/foo.md`.
- **Workspace root** (`<workspace>/`) — used by both linters
  (`graph_wiki_core/commands/lint.py` and `wiki_io/lint_wiki.py`), which walk
  `workspace.rglob("*.md")` and key pages relative to the workspace
  (`wiki/concepts/foo`, `work/bar`).

Because the linters key pages as `wiki/concepts/foo` but wikilink targets are
written as `concepts/foo`, **every `[[concepts/…]]`, `[[entities/…]]`,
`[[adrs/…]]`, `[[sources/…]]`, `[[architecture/…]]` link is reported broken.**
Only `[[work/…]]` resolves, because `work/` is a genuine workspace-relative top.

### Why `work/` is the knot

`work/` physically sits at `<workspace>/work` — a sibling of `wiki/`, not under
it (`backlink_index.py:79`: `wiki.parent / "work"`). It is therefore the *only*
wikilink form that is legitimately workspace-relative. That single exception is
what has driven repeated back-and-forth over which base to use.

## Decision

Standardize on **the wiki root** as the one base for all vault-relative paths
and wikilink resolution. To remove the `work/` exception, **move `work/` under
the wiki** (`<workspace>/wiki/work`). With every category — `entities/`,
`concepts/`, `adrs/`, `sources/`, `architecture/`, `proposals/`, and `work/` —
under one root, `[[work/foo]]` resolves identically to `[[concepts/foo]]`.

No migration code: this is a single-developer research project with no
production workspaces (`CLAUDE.md`, `.claude/rules/backward-compatibility.md`).
The workspace is recreated when the layout changes.

### The core rule

There is exactly one base for vault-relative paths and wikilink resolution: the
wiki root (`wiki_dir(workspace)`). The literal path segment `"work"` appears in
exactly one place in code (`workspace_io/paths.py`); everything else routes
through the helper.

## Change set

### 1. Redefine the chokepoint — `workspace_io/paths.py`

```python
def work_dir(workspace: Path) -> Path:
    return wiki_dir(workspace) / "work"     # was: Path(workspace) / "work"
```

This is the single definition of where `work/` lives. Callers that hold a
`wiki` path use the existing `workspace = wiki.parent` idiom and call
`work_dir(wiki.parent)`.

### 2. Route all `work` locators through the helper (kill inline literals)

Replace `wiki.parent / "work"`:
- `wiki_io/backlink_index.py:79`
- `wiki_io/ingest_work_item.py:147`
- `wiki_io/update_index.py:313`, `:386`

Replace `workspace / "work"` (or `workspace_root / "work"`):
- `wiki_io/update_index.py:145`
- `wiki_io/update_tokens.py:214`
- `wiki_io/index_generator.py:493`
- `wiki_io/init_vault.py:131`, `:229`

All become `work_dir(<workspace>)` where `<workspace>` is the workspace path the
caller already has (or `wiki.parent`).

### 3. Rebase the vault walks from workspace root → wiki root

- `graph_wiki_core/commands/lint.py:_mechanical_pass` — both loops (lines ~143
  and ~203): walk `wiki.rglob("*.md")`, compute `rel = md.relative_to(wiki)`,
  and drop the `effective_linted_tops = LINTED_TOPS | {wiki.name}` hack.

  `LINTED_TOPS` must be re-derived as a **behavior-preserving** change, not a
  hand-picked subset. Today, walking from the workspace, every page under
  `wiki/` has top-part `"wiki"`, which `effective_linted_tops` includes via
  `| {wiki.name}` — so **every vault page is currently linted** (entities,
  concepts, adrs, architecture, sources, proposals), plus `work/`. After
  rebasing to the wiki root, page top-parts become the real dir names
  (`entities`, `concepts`, `proposals`, …). To keep the *same* pages receiving
  the *same* checks, `LINTED_TOPS` must enumerate **all** top-level vault dirs:
  `{"concepts", "adrs", "architecture", "sources", "entities", "proposals",
  "work"}` (removing only the now-meaningless `"wiki"`, and the stale
  `"packages"`, `"apps"`, `"domains"` dirs that no longer exist on disk). This
  deliberately does **not** change entity-page handling: if entity pages are
  flagged today by the `{title, category, summary}` missing-frontmatter check,
  they are flagged identically after — that question is out of scope here (see
  below).
- `wiki_io/lint_wiki.py:scan` — both loops (lines ~88 and ~150): same rebase to
  `wiki.rglob` / `relative_to(wiki)`; re-derive its `LINTED_TOPS` the same way.
- `wiki_io/update_index.py:scan_work_pages` (~line 145): compute
  `rel = md.relative_to(wiki)` so work pages key as `work/foo` (not
  `wiki/work/foo`). Update the docstring that says
  "workspace-relative … workspace-rooted wikilinks."

### 4. Directory creation

- `wiki_io/init_vault.py` creates `work_dir(workspace)` (now under the wiki).
  No standalone move script — workspaces are recreated.

## What does NOT change

- Emitted wikilink **text** is unchanged (`[[work/foo]]` stays `[[work/foo]]`);
  only the base it resolves against moves. Existing curated pages' links stay
  valid.
- `query.py` (`_discover_pages`, `_compute_unresolved_wikilinks`) and
  `backlink_index.py`'s entity-link walks are already wiki-rooted — only the
  `work` *locator* in `backlink_index.py` changes (step 2).
- `wiki_io/lint/package_sync.py` already re-walks from the wiki root
  independently (`check_package_sync_drift(repo, wiki)`) — no change.

## Verification

- **Regression test (one per linter):** a fixture vault containing
  `[[entities/x]]`, `[[concepts/y]]`, and `[[work/z]]` links → assert the linter
  reports **zero** broken links. (Today it would flag the first two.)
- **Behavior-preservation test:** assert the set of pages classified `linted`
  (and the orphan / missing-frontmatter results) is unchanged for a
  representative fixture vault before vs. after the rebase — the base-dir change
  must not alter which pages get which checks.
- **SSOT guard:** `grep -rn '"work"' packages/*/src` returns only `paths.py`
  (and the flagged-vestigial `link_rewriter.py`).
- **Suites:** `uv run --package wiki-io pytest` and
  `uv run --package graph-wiki-core pytest -m "not integration"`.
- **Manual:** rebuild the workspace, run `gw lint`, confirm the broken-link
  error is gone and `work/` pages are discovered under `wiki/work/`.

## Out of scope (flagged for later)

- **`link_rewriter.py`** — workspace-rooted migration machinery with no live
  importer (only a docstring reference). Dead given "no migrations until v2.0";
  delete in a separate change.
- **`lint/domain.py`** — keys off `domains/`/`packages/` dirs that no longer
  exist (everything is under `entities/`). Not exercised yet; on the user's
  list. Untouched here.
- **Old `[[wiki/concepts/…]]`-prefixed links** — would now be flagged broken if
  any exist. Migration territory; not handled here.
- **Entity-page missing-frontmatter noise** — entity pages use a different
  frontmatter contract (no `title`/`category`/`summary`) yet are linted by the
  generic missing-frontmatter check. This change preserves that behavior exactly
  (it neither introduces nor fixes it). Whether entity pages *should* be exempt
  is a separate question.
