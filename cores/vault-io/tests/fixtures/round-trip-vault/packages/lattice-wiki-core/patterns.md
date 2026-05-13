---
title: lattice-wiki-core — Patterns
category: package
summary: How the modules chain, how the JSON/CLI conventions work, and how shared state (layout, git gate, last_sync_commit) flows between scripts.
updated: 2026-05-09
sources: 1
tokens: 2919
---

# lattice-wiki-core — Patterns

## Key patterns

### CLI + library, every module

Every `lattice_wiki_core/*.py` module exposes both a `main()` argparse CLI and importable functions. The plugin shims (`plugins/lattice-wiki/skills/lattice-wiki/scripts/*.py`) call `main()` of the corresponding core module after an optional Bedrock dispatch. Tests import the functions directly.

This dual surface is why each script's docstring contains a `Usage:` block — both the LLM (running `python -m`) and humans (running `python script.py`) need it.

### `--json` is universal

Every CLI accepts `--json`. The LLM uses this output to drive next steps deterministically. Examples: `scan_monorepo.py:1057`, `lint_wiki.py:382`, `update_index.py:219`, `ingest_source.py:234`, `append_log.py:104`.

Counter-pattern (intentional): some CLIs also emit a human-readable report when `--json` is omitted (`lint_wiki.py:print_report` at `lint_wiki.py:255`, `scan_monorepo.py:1139`).

### Skipped-vs-clean sentinel in JSON output

`lint_wiki.scan` distinguishes "check skipped because we have no `repo_path`" from "check ran and found nothing". Skipped fields are initialized to a module-level `_SKIPPED: dict = {"skipped": True}` (`lint_wiki.py:55`) instead of `None` — `json.dumps(..., default=list)` does NOT coerce `None` to `[]`, so a `None` field would serialize as `null` and lose the distinction. Clean checks return `[]` from their `lint/*.check(...)` modules. Callers test `isinstance(val, dict) and val.get("skipped")` (see `lint_wiki.py:315-365` for the print-report guards). Documented in [[wiki/sources/2026-05-lattice-wiki-core-three-wiki-bug-fixes]].

### Pipeline: scan → update_index → append_log

The canonical sequence after any vault mutation:

1. **Mutate** — write/edit one or more vault pages
2. **`update_index.py --wiki <path>`** — regenerate `index.md` and the five category sub-indexes (`update_index.py:215`)
3. **`append_log.py --wiki <path> --op <op> --title <…> --detail <…>`** — append a timeline entry (`append_log.py:98`)

`ingest_work_item.py:181` shells out to `update_index.py` and `append_log.py` after every successful work-page write — this is the reference implementation of the pipeline.

### Layout block as IPC

`<wiki>/CLAUDE.md` and `<wiki>/AGENTS.md` carry a YAML block delimited by `<!-- lattice-wiki:layout:start -->` / `:end -->` (`layout_io.py:36`). It pins:

- `vault_root` — name of the inner Obsidian vault dir
- `containers` — list of `{source, vault_dir, classification, children_count}` records, one per top-level repo container

Every script that needs to find the vault calls `layout_io.resolve_vault_dir(wiki)` (`layout_io.py:56`). **Never hardcode** the inner vault dir name; that's what this contract is for.

`scan_monorepo.discover_workspaces` reads the `containers` list to scope the walk and route packages to per-container vault dirs (`scan_monorepo.py:412`). `lint/container.py:check` validates that the pinned shape still matches disk (`lint/container.py:30`).

### State gate (clean main)

`git_state.is_clean_main(repo)` (`git_state.py:39`) is the single predicate that controls whether the scripts may write `last_sync_commit` values into vault frontmatter. Returns `(True, "")` only when:

1. Current branch is `main`
2. `git status --porcelain` is empty

`scan_monorepo.compute_state_gate(repo)` (`scan_monorepo.py:720`) wraps this and surfaces it on every scan:
```
{"allowed": bool, "reason": str, "head_commit": str | None}
```

The gate is reported in scan/ingest output but the LLM applies it — the scripts just record it. When the gate is `False`, the scan still runs (read-only) and reports drift, but `last_sync_commit` is not written.

### `last_sync_commit` tracking

Three places write a SHA into vault frontmatter:

1. `category: package` / `category: app` pages — set by the agent when `/lattice-wiki:scan` reviews a package and the state gate is open. `lint/package_sync.py:check` (`lint/package_sync.py:15`) flags pages whose `package_path` has changed since the recorded SHA.
2. `category: source` pages for **in-repo docs** — set by ingest when the source lives outside `<wiki>/raw/` and the state gate is open (`ingest_source.py:316`). `lint/source_sync.py:check` flags drift.
3. `raw/`-staged sources never carry `last_sync_commit` (filtered out by the empty-SHA check in `lint/source_sync.py:38`).

The pattern: SHA at sync time → diff at lint time. The scan never writes the SHA itself; it supplies `state_gate.head_commit` to the agent.

### Folder-shorthand wikilink resolution

A wikilink like `[[wiki/packages/foo]]` resolves to `packages/foo/foo.md`. This shorthand is implemented twice (deliberately — both modules do their own walks):

- `lint_wiki.scan` (`lint_wiki.py:91-100`)
- `graph_analyzer.build_graph` (`graph_analyzer.py:93-102`)

Both also fall back to **stem matching**: `[[wiki/lattice-wiki]]` resolves if any page anywhere has that filename. This is what makes inter-package cross-links work without forcing the writer to know each page's full path.

### Container detection algorithm

`detect_containers.detect(repo_root)` (`detect_containers.py:144`) classifies each immediate subdir using a priority cascade:

```
1. docs        → leaf dir, ≥70% .md files, no manifests           (DOC_THRESHOLD = 0.7)
2. domain      → >50% of children are themselves package          (DOMAIN_THRESHOLD = 0.5)
                 containers AND no child has its own manifest
3. package     → all children have a manifest, no loose .md
4. ambiguous   → mixed shape (some kids with manifests, some not)
5. single-package → repo root itself has a manifest, no structural
                    containers found in any subdir
```

Manifests = `package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, `.claude-plugin/plugin.json`. When all subdirs come back ambiguous and the repo root has a manifest, the entire repo is treated as one workspace.

The algorithm is heuristic and explicit — `init_vault.py:_resolve_pinned_containers` prompts for any `ambiguous` rows at init time. After init, the layout block is the source of truth; re-runs of `detect()` only feed `reconcile_layout` for drift reporting.

### File map rendering (git-driven)

`scan_monorepo.build_file_map` (`scan_monorepo.py:293`) renders the `## File map - <pkg>` block from `git ls-files --cached --others --exclude-standard`. Two consequences:

1. `.gitignore` is honored automatically — vendored / built / cached files don't pollute the map.
2. The map silently disappears for packages outside git (returns `None`).

The renderer emits one section per directory (H3 = first level, H6 = fourth level). Sub-dirs deeper than `--max-depth` (default 4) collapse to a folder-bullet rather than getting their own header. `--max-entries` (default 80) caps total bullets and emits a `> Truncated at N files.` note.

`lint/file_map.py:check` validates only **removals** — entries that exist in the map but not on disk. New files aren't flagged because folder-bullet summarization is allowed.

### Index regeneration is content-driven

`update_index.py` walks the vault, parses every page's frontmatter, and emits:

- `<vault>/index.md` — only the navigation backbone (`MAIN_INDEX_CATEGORIES = ["app", "domain", "package"]`)
- `<vault>/concepts/index.md`, `sources/index.md`, `adrs/index.md`, `architecture/index.md`, `dependencies/index.md` — one per category in `CATEGORY_INDEX_FILES` (folder-scoped sub-indexes)
- `<workspace>/work/index.md` — work items live at `<workspace>/work/` (sibling of the wiki), so their index is written outside the vault

Sub-pages (filenames matching `SUBPAGE_STEMS = {"api", "patterns", "issues", "context", "flows", "work"}`) are excluded from the main index but still parsed. `"work"` was added so `packages/*/work.md` files don't double-count in the Package nav.

The `## More` block always renders five categories (`_ALWAYS_IN_MORE = {"architecture", "source", "concept", "adr", "dependency"}`) even at 0 pages so they don't go invisible to first-time readers. `work` stays conditional — it's a workspace namespace, not a browsing entrypoint. See [[wiki/sources/2026-05-lattice-wiki-core-three-wiki-bug-fixes]].

### Marker-bounded auto-blocks

The dependencies index uses HTML-comment markers around the regenerated content (`scan_monorepo.py:840`):

```markdown
<!-- auto:dependencies-index generated:<ISO> -->
| Name | Kind | Ecosystem | … |
<!-- /auto:dependencies-index -->
```

`regenerate_dependencies_index` (`scan_monorepo.py:1020`) replaces the bounded block in place; manual notes outside the markers are preserved. Crucially, the regen is content-comparison: if the rendered table body matches what's already in the file, the write is skipped entirely (`scan_monorepo.py:1033`). This keeps re-runs byte-identical so `compute_state_gate` doesn't trip itself by dirtying the working tree.

### Plugin shim dispatch

The plugin's `scripts/<name>.py` files are thin shims. Each shim:

1. Adds `vendor/` to `sys.path` (build step copies `packages/lattice-wiki-core/src/` there — see `scripts/build.sh:60-69` and `scripts/plugins.json`)
2. Reads `.lattice-wiki.json` via `_config.backend_for(command, repo)` to pick `claude` (default) or `bedrock`
3. Calls `lattice_wiki_core.<module>.main()` for `claude`, or instantiates a `lattice_wiki_agent.agents.<X>Agent` for `bedrock`

The source of truth is `packages/lattice-wiki-core/` — the vendored copy under `plugins/` is generated and overwritten by the build.

### Cross-plugin subprocess invocation

Other plugins call `lattice-wiki-core` scripts as subprocesses, not as imports. `ingest_work_item.py` is the canonical example: `lattice-workflows`'s `file-work-item` skill spawns it with `--frontmatter`, `--body`, `--wiki` and parses the JSON result. Exit codes (`ingest_work_item.py:14`):

- `0` success
- `2` invalid args / schema validation failed
- `3` runtime error after partial write

This contract — `--json`, exit codes, no shared Python imports — is what lets plugins evolve independently while still cooperating around the same vault.

## Conventions

### Stdlib-only constraint

`pyproject.toml:10` declares `dependencies = []` and `requires-python = ">=3.11"`. Consequences:

- YAML parsed by hand (`layout_io.py:114`, `update_index.py:80`, `graph_analyzer.py:32`, `ingest_work_item.py:60`) — different parsers tuned to each module's exact shape
- TOML parsed by hand (`scan_monorepo._parse_pyproject` at `scan_monorepo.py:75`, `_parse_cargo_toml` at `scan_monorepo.py:92`) — minimal, just enough to extract `name` and `members`
- BM25 search hand-rolled (`wiki_search.py:115`) instead of `rank-bm25`
- Subprocess calls to `git` instead of `pygit2`/`GitPython` (`git_state.py:16`, `scan_monorepo.py:272`)
- HTML extraction uses `html.parser` (`ingest_source.py:77`)

The package trades more code for zero install friction.

### Test layout

Tests live at `packages/lattice-wiki-core/tests/`. They are stdlib `unittest` + pytest-discoverable. Fixtures are built inline using `helpers.py` (`tmp_repo`, `write_pkg`, `write_file`, `write_claude_plugin`) rather than referencing files under `fixtures/`. One test file per concern.

Run from repo root: `uv run pytest packages/lattice-wiki-core/tests/`.
