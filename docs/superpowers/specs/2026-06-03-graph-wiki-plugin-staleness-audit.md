# Findings Report: graph-wiki plugin staleness audit

**Date:** 2026-06-03
**Status:** Findings only — no design committed. Review gate before specing fixes.
**Scope:** `plugins/graph-wiki/` scripts + markdown, audited against the current target state (graph-driven, single `entities/` folder, **no container concept, no layout block**). Shared-core (`packages/`) blast radius included because the agreed direction removes containers from the shared code both `gw` and the plugin depend on.

## Executive summary

The `entities/` parity work (4 slices, 2026-06-02) already moved scan/ingest/lint/query and most docs to the single-`entities/` model. What it **deliberately left in place** was container detection + the pinned layout block — the 2026-06-02 spec explicitly preserved them ("Container detection still feeds the pinned layout block"). 

This audit confirms that decision is now obsolete: **the layout block is functionally vestigial.** The graph (`cg build`, filesystem-driven, takes no container input) is the sole source of truth for entity pages via `write_entities(conn, ...)`. The layout block's only live consumer is the legacy `discover_workspaces` walk, whose output now feeds (a) file-map *text* — re-sourceable from graph node paths, the pattern the `test_suite` branch already uses (`scan.py:1014-1045`) — and (b) a diff the code itself marks "legacy view only." Everything else exists only to maintain or validate the block.

**Therefore the bulk of remaining plugin staleness IS the container/layout-block language.** It is not scattered rot; it is one coherent removable concept threaded through the docs. A smaller set of unrelated drift items exists alongside it.

Decisions already locked (this session): remove containers from **shared core** (lands on `gw` too); **re-source file maps from graph node paths**; deliver this **findings report first**.

---

## Category A — Container / layout-block staleness (the spine)

All of the following describe a concept that should cease to exist. Listed by file.

### Plugin scripts
| File | Finding | Action |
|---|---|---|
| `skills/graph-wiki/scripts/detect_containers.py` | Thin shim delegating to `wiki_io.detect_containers`. Classifier whose output no longer changes any page. | **Delete** (with shared-core deletion). |

### Plugin command markdown
| File:line | Finding |
|---|---|
| `commands/bootstrap.md:28-42` | Entire "## Container detection" section — runs `detect_containers.py`, shows classification table, prompts for ambiguous rows, describes pinning the layout block. **Delete the whole section.** Bootstrap becomes: create vault tree → run scan. |
| `commands/scan.md:39-49` | "re-detects containers and compares to pinned layout", "Layout drift detected" handling, "Re-run bootstrap / Edit the layout block", "When a `docs` container is pinned…". **Delete drift/reconcile flow.** (Docs-container ingest-candidate surfacing is a separate question — see Open Items.) |
| `commands/ingest.md:28,38,60` | "resolves under the repo's pinned `docs` container", `<docs-container>/*.md` row, "in-repo `.md` under the pinned `docs` container". Tied to docs-container detection — see Open Items. |

### Plugin agent markdown
| File:line | Finding |
|---|---|
| `agents/scanner.md:39` | "**Layout-aware:** when the wiki's `CLAUDE.md` pins a `graph-wiki:layout` block, discovery scopes to those containers." **Delete** — discovery is always graph-driven. |
| `agents/linter.md:39` | `check_container_drift` described as a lint check ("re-run bootstrap, edit the layout block, or ignore"). **Remove container-drift**; keep source-sync drift. |

### Plugin skill + reference markdown
| File:line | Finding |
|---|---|
| `skills/graph-wiki/SKILL.md:3` | Description: "detects app, package, domain, package-family, and docs containers and pins the layout in CLAUDE.md/AGENTS.md." Rewrite to entities/graph framing. |
| `SKILL.md:65` | "Container *detection* still pins the layout block (used to scope the graph build)…" — **delete the clause**. |
| `SKILL.md:130` | Script table row for `detect_containers.py`. Delete row. |
| `SKILL.md:171` | "`references/detection-workflow.md` — how containers are classified and pinned" — delete ref (file is being removed). |
| `SKILL.md:186` | Template list names `app, package, domain, … package-family` page templates — verify against actual `entity-*.md` template names (see Category B drift). |
| `skills/graph-wiki/references/detection-workflow.md` (whole file) | Entirely about container classification rules, ambiguity prompts, layout-block hand-edit constraints, `reconcile`. **Delete the file**; fold any still-true scoping note into `scan-workflow.md`. |
| `references/scan-workflow.md:10` | "The pinned `graph-wiki:layout` block in `wiki/CLAUDE.md` (scopes graph build + discovery to pinned containers…)". **Delete** — graph build takes no layout input. |
| `references/lint-workflow.md:30` | `container_drift` check description. Remove. |
| `skills/graph-wiki/README.md:7,27,29` | "detects the repo's top-level shape … pinned to CLAUDE.md/AGENTS.md so the LLM knows what containers exist"; tool table lists `detect_containers`; template list. Rewrite. |
| `CLAUDE.md:68` | Layout-invariants bullet: "pinned by `init_vault` and record the detected container layout (apps/packages/domains/docs/package-family…). Container detection runs through `detect_containers`…". **Delete.** |
| `CLAUDE.md:72` | "When changing how layout is detected, classified, or written, update `init_vault`…" + the cross-ref list that includes `detection-workflow.md`. Rewrite (drop detection-workflow.md). |
| `.claude-plugin/plugin.json:description` | "classifies top-level dirs as apps, packages, domains, or docs containers, and pins the layout in CLAUDE.md/AGENTS.md." Rewrite to entities/graph framing. |

---

## Category B — Genuine drift, unrelated to containers

These are stale regardless of the container decision and should be fixed in the same sweep.

| File:line | Finding | Note |
|---|---|---|
| `references/detection-workflow.md:19-29` | "Container types and their templates" table lists per-page templates `app.md` / `package.md` / `domain.md` and "Vault dir contents: one page per child". The actual templates are `entity-app.md` / `entity-package.md` / `entity-domain.md` (per `bootstrap.md:73`), and there are no per-container vault dirs. (Moot if the file is deleted per Category A, but flag the template-name drift wherever it recurs.) |
| `SKILL.md:186`, `README.md:29` | Template lists say `app, package, domain, … work, source, architecture, adr`. Real per-entity-kind templates are `entity-repository.md`, `entity-domain.md`, `entity-package.md`, `entity-app.md`, `entity-agent-plugin.md`, `entity-dependency.md`, `entity-test-suite.md` (+ curated `concept.md`, `source.md`, `adr.md`, `architecture.md`, `dependency.md`, `work.md`). **Update template inventories.** |
| `page-formats.md:17` | "the overview page's File map" + companion "`testing.md` sub-page" — describes the **old per-package `overview.md` + `testing.md` sub-page** model. Entity pages are single `entities/<prefix>_<name>.md` with a `## File map` section; test suites are their own entity pages. **Rewrite the prod-vs-test File-map section** to the entity model. |
| `page-formats.md:45` | "via testcontainers" — false-positive on the `container` grep, **not stale** (it's a real tool name in example prose). No action. |
| `README.md:27` | "**7 Python tools** … `detect_containers`" — count + list. After deletion this is 6 tools. Update. |
| `agents/linter.md:100`, `agents/ingestor.md:95` | "Obsidian syntax / wikilinks" guidance — **legitimate**, not stale (see Category C). Listed only to preempt a false grep hit. |

---

## Category C — NOT stale (false positives to avoid over-deleting)

Calling these out explicitly so the eventual fix doesn't break working content.

- **Obsidian references** (README, SKILL.md, agents, `obsidian-setup.md`, wiki-schema.md, ingest-workflow.md): the wiki *is* an Obsidian vault. `obsidian-setup.md` is a valid, current reference. The thing removed in the parity work was a separate **`obsidian-markdown` skill dependency**, not Obsidian. **Keep all of these.**
- **Dependency `kind: package-family`** (`wiki-schema.md:150-204`, `lint-workflow.md:48-51`, `page-formats.md:442`): this is a **dependency-page frontmatter enum value** (`package | package-family | service`) describing an external dependency that ships as a family of packages. It is unrelated to the *container* classification `package-family` being removed. **Keep the dependency kind; remove only the container classification.** This is the single easiest thing to get wrong.
- **Code-path citations** like `packages/foo/src/bar.ts:42` (query-workflow, page-formats, monorepo-principles, wiki-schema examples): legitimate illustrative code references, not folder routing. **Keep.**
- **`graph_analyzer.py`**: live shim → `wiki_io.graph_analyzer`, used by the lint flow (`commands/lint.md`, `lint-workflow.md`, `ingestor`/`linter`). **Not stale.**
- **`_config.py` / `_uv_reexec.py`**: support modules, not referenced in markdown by design (0 md refs is expected). **Not stale.**

---

## Shared-core blast radius (packages/) — context for the fix spec

Removing containers is a shared-core change. The layout-block/container consumers outside the plugin:

| Location | Current role | Disposition |
|---|---|---|
| `wiki_io/detect_containers.py` | the classifier | delete |
| `wiki_io/layout_io.py` | read/write the fenced layout block | delete |
| `wiki_io/lint/container.py` | container-drift lint check | delete |
| `wiki_io/init_vault.py:96-118,189,260-270` | `_detect_containers` + `_write_layout` — pins layout block (used by **both** `gw bootstrap` and the plugin) | strip layout-pinning |
| `wiki_io/scan_monorepo.py` | `discover_workspaces` (pinned + heuristic), `reconcile_layout`, `_wiki_relative_path_for` (legacy apps/domains/packages routing — likely already dead) | collapse to graph-sourced file maps; remove `reconcile_layout`, pinned path, legacy routing |
| `graph_wiki_core/commands/scan.py:50,759-775,824-828` | reads layout → `pinned_containers`; legacy diff (Steps 6-7) | always-unpinned (or drop discover entirely); re-source file maps from graph node paths like `test_suite` branch |
| `graph_wiki_core/commands/lint.py`, `prompts/project_context.py` | consume layout block | drop layout injection / container-drift |

**`gw` user-facing change:** `gw bootstrap` stops pinning a layout block; `gw scan` is always graph-scoped. Consistent with "we have no need for containers." Tests referencing `layout_io`, `reconcile_layout`, container-drift, and `detect_containers` will need removal/rewrite.

---

## Open items — RESOLVED (2026-06-03)

1. **`docs` container → ingest candidates.** **Resolved: drop in-repo-doc auto-surfacing entirely.** No replacement trigger. Remove docs-container support and the source-sync drift check (`lint/source_sync.py`) that existed only to track it.
2. **Drift surfacing.** **Resolved via the four-check decomposition:**
   - **Remove** container/layout drift (`lint/container.py` + scan `reconcile_layout`) — dies with the block.
   - **Remove** source-sync drift (`lint/source_sync.py`) — tied to docs-container ingest.
   - **Keep** package-sync drift (`lint/package_sync.py`, layout-independent freshness).
   - **Keep** structural code-drift (graph entities ↔ vault pages, layout-independent — the headline feature).
   - Scan continues to report `entities +N ~M -D` and confirm deletions, so structural-change visibility is retained without the block.
3. **`detection-workflow.md`.** **Resolved: delete the file;** fold the one still-true sentence (scan discovers entities from the graph) into `scan-workflow.md`.
4. **`package-family`.** **Resolved: remove everywhere** — including the dependency `kind` enum. Zero production-code references confirmed; lives only in docs + a few tests.

→ Fix design: `2026-06-03-graph-wiki-decontainerize-design.md`.

---

## Suggested remediation shape (for the follow-on spec, not committed here)

- **Slice A — shared-core removal:** delete `detect_containers`/`layout_io`/`lint/container`; strip `init_vault` pinning; `run_scan` graph-only + file maps from node paths; drop layout from `lint`/`project_context`; update/remove tests. Verify `gw bootstrap`/`gw scan` + plugin scan produce identical container-free `entities/` trees.
- **Slice B — plugin markdown sweep:** apply Category A + B edits; delete `detection-workflow.md`; delete `detect_containers.py` shim; fix template inventories and `page-formats.md` File-map section; update `plugin.json` description.
- **Open-items decision** (docs-container ingest) resolved before/within Slice A, since it changes scan behavior.
