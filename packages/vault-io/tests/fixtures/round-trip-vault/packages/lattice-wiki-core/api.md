---
title: lattice-wiki-core — API
category: package
summary: Public functions, CLI flags, and key data structures exported by lattice-wiki-core.
updated: 2026-05-11
sources: 3
tokens: 5668
---

# lattice-wiki-core — API

`__init__.py` is empty (`packages/lattice-wiki-core/src/lattice_wiki_core/__init__.py:1`); modules are imported by name (`from lattice_wiki_core.scan_monorepo import discover_workspaces`). Each module is also a CLI (`python -m lattice_wiki_core.<name> --help`) and is invoked that way by [[wiki/plugins/lattice-wiki/lattice-wiki]] shims.

## Public API

### init_vault

`packages/lattice-wiki-core/src/lattice_wiki_core/init_vault.py`

- `init_wiki(wiki_path, repo_path, topic, tool, force, vault_name=None, as_json=False, non_interactive=False)` — `init_vault.py:149`. Creates `raw/`, `<vault>/`, schema files, page templates under `<vault>/.templates/`, and a `.gitignore`. Vault name defaults to `<repo>-vault`.
- `_resolve_pinned_containers(repo, non_interactive)` — `init_vault.py:93`. Calls `detect_containers.detect`; prompts when ambiguous unless `non_interactive`.

CLI: `--wiki <path> --repo <path> --topic <name> [--tool {claude-code|codex|cursor|antigravity|opencode|gemini-cli|all}] [--force] [--vault-name <name>] [--json] [--non-interactive]`. Default `--tool all` installs `CLAUDE.md` + `AGENTS.md` + `.cursorrules`.

### detect_containers

`packages/lattice-wiki-core/src/lattice_wiki_core/detect_containers.py`

- `detect(repo_root) -> list[dict]` — `detect_containers.py:144`. Returns one record per immediate subdir: `{source, classification, children_count, reason}`.

Classifications, in priority order (`detect_containers.py:78`):
1. **`docs`** — leaf dir whose files are ≥70% `.md` and have no manifests (`DOC_THRESHOLD = 0.7`)
2. **`domain`** — >50% of children are themselves package containers (`DOMAIN_THRESHOLD = 0.5`)
3. **`package`** — every child has a manifest
4. **`ambiguous`** — partial manifest coverage / mixed shape
5. **`single-package`** — repo root itself has a manifest and no structural containers

Manifests recognized (`detect_containers.py:24`): `package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, `.claude-plugin/plugin.json`. Skipped dirs (`detect_containers.py:31`): `.git`, `node_modules`, `.venv`, `dist`, `build`, `target`, `.next`, `.turbo`, etc.

CLI: `--repo <path> [--json]`.

### scan_monorepo

`packages/lattice-wiki-core/src/lattice_wiki_core/scan_monorepo.py`

#### Discovery

- `discover_workspaces(repo, pinned_containers=None) -> list[dict]` — `scan_monorepo.py:372`. Branches on `pinned_containers`: pinned → only walks declared containers; unpinned → heuristic walk (pnpm/yarn/npm globs, Python `pyproject.toml` rglob, Rust `[workspace]`, Claude plugins).
- `unscope(name) -> str` — `scan_monorepo.py:49`. `@scope/foo` → `foo`. Used everywhere wiki slugs (unscoped) compare against manifest names (scoped).

Workspace dict shape:
```
{
  "name": str,                # raw manifest name (may be scoped)
  "path": "packages/foo",     # repo-relative
  "type": "library" | "app" | "service" | "tool",
  "language": "typescript" | "python" | "rust" | "go" | "javascript" | "claude-code-plugin" | "unknown",
  "version": str | None,
  "depends_on": list[str],    # internal workspace deps (workspace:* protocol)
  "external_deps": dict,      # {name: version}, npm only
  "ecosystem": "npm" | "claude-code-plugin",
  "exports": list[str],       # package.json#exports keys, or plugin keywords
  "scripts": list[str],
  "depended_on_by": int,      # reverse dep count
  "vault_path": "packages/foo/foo.md",
  "domain": str | None,       # set for domain-scoped packages
  "file_map": str | None,     # rendered ## File map block, when --no-file-map is off
  "last_sync_commit": str | None,
  "changed_files": list[str] | None,
}
```

#### Layout-aware routing

- `_vault_path_for(pkg, vault_dir=None) -> str` — `scan_monorepo.py:387`. Routing rules: `app` → `apps/<name>/<name>.md`, with `domain:` → `domains/<d>/packages/<name>/<name>.md`, otherwise → `<vault_dir>/<name>/<name>.md` (defaults to `packages/`).
- `_discover_from_pinned(repo, containers)` — `scan_monorepo.py:412`. Honors `vault_dir` from `<wiki>/CLAUDE.md` so non-default container names (e.g. `plugins/`) map to non-default vault dirs.
- `_discover_heuristic(repo)` — `scan_monorepo.py:500`. Falls back when no layout is pinned. Filters out `tests`/`fixtures`/`samples` segments (sample manifests aren't workspaces).

#### File map rendering

- `build_file_map(pkg_path, max_depth=4, max_entries=80) -> str | None` — `scan_monorepo.py:293`. Renders the `## File map - <pkg>` block from `git ls-files --cached --others --exclude-standard` so `.gitignore` is honored. Sub-dirs deeper than `max_depth` collapse to folder bullets. Returns `None` outside git.
- `_git_ls_files(pkg_path) -> list[str] | None` — `scan_monorepo.py:272`. 10s timeout, returns `None` when git is unavailable.

#### Diff and gates

- `compute_diff(workspaces, existing) -> dict` — `scan_monorepo.py:664`. Set diff against existing vault pages with heuristic rename detection (same path, new name).
- `compute_state_gate(repo) -> dict` — `scan_monorepo.py:720`. Returns `{allowed, reason, head_commit}`. `allowed` requires clean tree on `main`.
- `attach_changed_files(workspaces, existing, repo) -> None` — `scan_monorepo.py:697`. Mutates each workspace dict to add `last_sync_commit` (from existing page frontmatter) and `changed_files` (from `git_state.changed_files_since`).
- `reconcile_layout(repo, pinned) -> dict` — `scan_monorepo.py:739`. `{new, missing, changed}` against the pinned layout block.

#### Doc surfacing

- `discover_docs(repo, wiki, pinned_containers) -> list[dict]` — `scan_monorepo.py:793`. For each `classification: docs` container, walks `.md` files recursively; emits one candidate per file with no existing summary page.

#### Dependency index regeneration

- `collect_external_dependencies(workspaces) -> list[dict]` — `scan_monorepo.py:846`. Aggregates `external_deps` keyed by `(ecosystem, name)`.
- `load_services_yaml(wiki) -> list[dict]` — `scan_monorepo.py:889`. Reads hand-maintained `<vault>/dependencies/services.yaml`.
- `regenerate_dependencies_index(wiki, workspaces) -> Path | None` — `scan_monorepo.py:1020`. Marker-bounded write to `<vault>/dependencies/index.md`; skips when body is unchanged so re-runs are byte-identical.

CLI: `--repo <path> [--wiki <path>] [--json] [--no-file-map] [--max-depth N] [--no-index-regen]`.

### lint_wiki

`packages/lattice-wiki-core/src/lattice_wiki_core/lint_wiki.py`

- `scan(wiki, stale_days, log_gap_days, repo_path=None, optional_checks=None) -> dict` — `lint_wiki.py:56`. Dispatcher: walks the vault, builds the link graph, then calls each `lint/*.check(...)` module. Code-drift checks are skipped when `repo_path` is `None`.

Returned report keys: `total_pages`, `orphans`, `broken_links`, `stale`, `missing_frontmatter`, `missing_tokens`, `duplicate_titles`, `log_gap`, `code_drift`, `container_drift`, `source_sync_drift`, `file_map_drift`, `package_sync_drift`, `domain_placement`, `dependency_layer` (optional), `workflow_hints`.

**`missing_tokens` (v0.4.0).** Soft warning, collected at `lint_wiki.py:190-202`. Walks `linted` pages (top-level `wiki/` + `work/`) and lists any whose frontmatter lacks a `tokens:` key. Reported separately from the required-fields check (`title`/`category`/`summary`) because `tokens` is computed by `update_tokens` rather than authored — absence nudges the user to re-run the stamper but does not invalidate the page. See [[wiki/sources/2026-05-lattice-wiki-core-tokens-frontmatter-field]].

**Skipped sentinel.** When `repo_path` is `None`, the five drift fields (`code_drift`, `container_drift`, `source_sync_drift`, `file_map_drift`, `package_sync_drift`) are initialized to a module-level sentinel `_SKIPPED: dict = {"skipped": True}` (`lint_wiki.py:55`) instead of `None`. This lets JSON callers distinguish "check skipped" (`{"skipped": true}`) from "check ran clean" (`[]`). Test the sentinel with `isinstance(val, dict) and val.get("skipped")`. See [[wiki/sources/2026-05-lattice-wiki-core-three-wiki-bug-fixes]].

`code_drift` shape: `{packages_on_disk, packages_in_vault, missing_in_vault, orphaned_in_vault, planned_in_vault, exports_drift}`. `status: planned` pages bypass orphan flagging (`lint_wiki.py:165`).

**Overview-only `vault_pkg_pages` filter (v0.3.2).** `vault_pkg_pages` is narrowed at `lint_wiki.py:236-239` to pages where both `fm.category in {"package", "app"}` AND `Path(k).parent.name == Path(k).name` — i.e. only the overview file `<container>/<slug>/<slug>.md`. This structural invariant excludes facet sub-pages (`api.md`, `context.md`, `patterns.md`, `work.md`) which inherit `category: package` from the overview convention. Every downstream set — `vault_names` (`lint_wiki.py:241`), `planned_names` (`lint_wiki.py:247`), and the `exports_drift` lookup key (`lint_wiki.py:261`) — uses `Path(k).name` (path-derived slug) instead of `fm.get("title")`, matching `disk_names` semantics without suffix stripping. Eliminated 47 false-positive `orphaned_in_vault` entries on a clean wiki. See [[wiki/sources/2026-05-lattice-wiki-core-lint-code-drift-slug-normalization]].

`OPTIONAL_GROUPS = {"dependency_layer"}` — gate via `--check dependency_layer`.

CLI: `--wiki <path> [--repo <path>] [--stale-days N=90] [--log-gap-days N=14] [--check <group,...>] [--json]`.

### lint sub-modules

`packages/lattice-wiki-core/src/lattice_wiki_core/lint/`

Each module: `check(...) -> list[str]` returning one human-readable issue per finding, plus a module-level `GROUP` constant.

- `lint/common.py` — `parse_frontmatter`, `strip_code`, `strip_frontmatter` (v0.3.1), `expand_braces`, `parse_inline_list`, `find_section`, `parse_markdown_table`, `parse_section_entries` (nested-bullet `dir_stack` in v0.3.1). Regex: `FRONTMATTER_RE`, `WIKILINK_RE`, `LOG_ENTRY_RE`, `FILE_MAP_SECTION_RE`, `SECTION_HEADER_RE`, `BULLET_RE` (captures indent+token groups in v0.3.1).
- `lint/container.py:check(repo, wiki)` — `container.py:30`. Pinned containers missing on disk; orphan vault dirs not pinned and not in `FIXED_DIRS`; legacy dir hints (`issues/`, `roadmap/`, etc.).
- `lint/file_map.py:check(repo, pages)` — `file_map.py:17`. `## File map - <name>` entries missing on disk. Removals only — new files aren't flagged.
- `lint/domain.py:check(pages)` — `domain.py:9`. Package page in `domains/<d>/packages/<name>/` must have `domain: <d>`; top-level `packages/<name>/` must NOT have a `domain:` value.
- `lint/source_sync.py:check(repo, wiki)` — `source_sync.py:15`. `category: source` pages with both `source_path` and `last_sync_commit` whose source has changed (in-repo docs only).
- `lint/package_sync.py:check(repo, wiki)` — `package_sync.py:15`. Package/app pages whose `package_path` (or `app_path`) has changed since `last_sync_commit`.
- `lint/workflow_hints.py:check(pages, vault)` — `workflow_hints.py:46`. `workflow_hints:` frontmatter referencing missing sub-pages.
- `lint/dependency.py:check(pages, workspaces=None)` — `dependency.py:24`. **Optional**. `category: dependency` page rules: `kind` enum, per-kind required fields, family back-pointer consistency, stub-page detection (<15 body lines), `dep-multiple-families` cross-check.

### update_index

`packages/lattice-wiki-core/src/lattice_wiki_core/update_index.py`

- `scan_vault(wiki) -> dict[str, list[dict]]` — `update_index.py:98`. Walks `<vault>/`, parses frontmatter, groups by `category`. Skips `index.md`, `log.md`, the auto-generated `*-index.md` sub-indexes, and dotfiles.
- `render_index(pages, wiki_name, vault_name) -> str` — `update_index.py:134`. Main `index.md` is **navigation-only** — only `app`, `domain`, `package` get listed; everything else lives in category sub-indexes via the `## More` block.
- `render_category_index(entries, category, label, vault_name) -> str` — `update_index.py:185`. Standalone sub-index file per category in `CATEGORY_INDEX_FILES`. **v0.3.1:** now prepends YAML frontmatter (`title`, `category: index`, `summary`, `updated`).

`MAIN_INDEX_CATEGORIES = ["app", "domain", "package"]` (`update_index.py:27`). `CATEGORY_INDEX_FILES = {concept, work, source, adr, architecture, dependency}` (`update_index.py:46`). `SUBPAGE_STEMS = {"api", "patterns", "issues", "context", "flows", "work"}` (`update_index.py:57`) — excluded from main index but still parsed; `"work"` was added so `packages/*/work.md` files don't leak into the Package nav count (see [[wiki/sources/2026-05-lattice-wiki-core-three-wiki-bug-fixes]]). `_ALWAYS_IN_MORE = {"architecture", "source", "concept", "adr", "dependency"}` (`update_index.py:174`) — those five categories render in the `## More` block even at 0 pages so they don't go invisible.

CLI: `--wiki <path> [--dry-run] [--json]`.

### ingest_source

`packages/lattice-wiki-core/src/lattice_wiki_core/ingest_source.py`

- `extract(path) -> tuple[str, str | None]` — `ingest_source.py:111`. Decoder for `.md` / `.txt` / `.html` / `.json` / `.csv`.
- `guess_source_type(rel_to_wiki, rel_to_repo) -> str` — `ingest_source.py:144`. Returns `spec` / `article` / `pr` / `ticket` / `transcript` / `example` / `doc` / `note` based on path.
- `folder_brief(root, rel_to_wiki) -> dict` — `ingest_source.py:200`. When `--source` is a directory: lists files, picks a representative, warns at >50 files, errors at >200.

The brief emitted on stdout (`ingest_source.py:331`) carries: `source_path`, `bytes`, `sha256`, `title_guess`, `source_type_guess`, `preview` (1200 chars), `existing_summary_page`, `suggested_summary_path`, `last_sync_commit`, `state_gate`, `is_folder`.

CLI: `--wiki <path> [--repo <path>] --source <path> [--json] [--pkg-dir <path>] [--pkg-title <title>]`.

### ingest_work_item

`packages/lattice-wiki-core/src/lattice_wiki_core/ingest_work_item.py`

Cross-plugin entry point; invoked by `lattice-workflows`'s `file-work-item` skill via subprocess.

- `main()` — `ingest_work_item.py:129`. Strict schema: required fields `title`, `category`, `kind`, `status`, `summary`, `opened`, `affects`. Validates `category == "work"`. Page path: `<vault>/work/<opened>-<slug>.md`.
- Side effects after write: invokes `update_index.py` and `append_log.py` via subprocess.
- `--pkg-dir` / `--pkg-title` opt-in: ensures `work.md` sub-page exists and appends a backlink bullet.

Exit codes: `0` ok / `2` invalid args or schema rejection / `3` runtime error after write.

CLI: `--wiki <path> --frontmatter <yaml> --body <md> [--slug <s>] [--force] [--json] [--pkg-dir <path>] [--pkg-title <title>]`.

### layout_io

`packages/lattice-wiki-core/src/lattice_wiki_core/layout_io.py`

The layout block is delimited by `<!-- lattice-wiki:layout:start -->` / `<!-- lattice-wiki:layout:end -->` around a YAML fenced block (`layout_io.py:36`).

- `read_layout(schema_path) -> dict | None` — `layout_io.py:45`.
- `write_layout(schema_path, layout) -> None` — `layout_io.py:71`. Replaces existing block in place, or appends.
- `resolve_vault_dir(wiki) -> Path` — `layout_io.py:56`. Reads `vault_root` from `CLAUDE.md` then `AGENTS.md`. Falls back to `<wiki>/vault`.
- `ensure_subpage(pkg_dir, subpage_name, pkg_title, templates_dir, today=None) -> tuple[Path, bool]` — `layout_io.py:156`. Renders `{{PACKAGE_TITLE}}` and `{{DATE}}`. Raises `FileNotFoundError` if template missing.
- `ensure_domain_page(domain_dir, domain_title, templates_dir, today=None) -> tuple[Path, bool]` — `layout_io.py:182`.
- `ensure_domain_details(domain_dir, domain_title, templates_dir, today=None) -> tuple[Path, bool]` — `layout_io.py:207`.

The minimal YAML emitter/parser (`layout_io.py:86-153`) is hand-rolled — no PyYAML, per the stdlib-only constraint. Schema is fixed: `version`, `detected_at`, `repo_root`, `vault_root`, `containers[{source, vault_dir, classification, children_count, note?}]`.

### git_state

`packages/lattice-wiki-core/src/lattice_wiki_core/git_state.py`

All functions: 10s subprocess timeout, return `None` when git is unavailable.

- `head_commit(repo) -> str | None` — `git_state.py:30`. Full HEAD SHA via `git rev-parse HEAD`.
- `is_clean_main(repo) -> tuple[bool, str]` — `git_state.py:39`. Returns `(True, "")` only when current branch is `main` AND `git status --porcelain` is empty.
- `changed_files_since(repo, since_sha, sub_path) -> list[str] | None` — `git_state.py:59`. `git diff --name-only <sha>..HEAD -- <sub_path>`.

### graph_analyzer

`packages/lattice-wiki-core/src/lattice_wiki_core/graph_analyzer.py`

- `build_graph(wiki) -> tuple[set, dict, dict]` — `graph_analyzer.py:61`. Walks all vault pages, resolves wikilinks (with folder-shorthand `[[wiki/packages/foo]]` → `packages/foo/foo.md`), and treats `depends_on:` frontmatter as graph edges.
- `connected_components(nodes, out, inb) -> list[set]` — `graph_analyzer.py:118`.
- `analyze(wiki, top) -> dict` — `graph_analyzer.py:142`. `{total_pages, total_edges, top_outbound_hubs, top_inbound_hubs, orphans, sinks, components, component_count}`.

CLI: `--wiki <path> [--top N=10] [--json]`.

### update_tokens

`packages/lattice-wiki-core/src/lattice_wiki_core/update_tokens.py` — new in v0.4.0. Stamps `tokens: <count>` frontmatter on every wiki and work page using `tiktoken` `cl100k_base` (GPT-4 BPE; close approximation to Claude for English prose, no API call). Counts are used by agents for context-budget planning before loading pages.

- `get_encoding() -> tiktoken.Encoding` — `update_tokens.py:37`. Loads `cl100k_base` once; reused across all files.
- `count_tokens(text, encoding) -> int` — `update_tokens.py:41`.
- `iter_pages(wiki) -> Iterator[Path]` — `update_tokens.py:45`. `rglob("*.md")` under `wiki`, skipping `SKIP_FILENAMES = {"index.md", "log.md"}` and any path whose relative parts contain a dotdir component.
- `update_page(path, encoding, dry_run=False) -> tuple[str, int]` — `update_tokens.py:56`. Returns `(status, count)` where status is `"updated"` / `"unchanged"` / `"skipped"`. Idempotency mechanic: any existing `tokens:` line is stripped from a copy of the raw YAML to form the baseline before counting (`update_tokens.py:84-100`), so the stored count is stable across re-runs (without stripping, the act of writing `tokens: N` would shift the next count). Skips files without leading `---` frontmatter and files with truncated frontmatter (no closing fence). Rewrites the YAML by line-level edit — not via `frontmatter.dumps()` — so quoting, key order, and blank lines round-trip byte-for-byte.
- `update_vault(wiki, dry_run=False) -> dict[str, list[str]]` — `update_tokens.py:135`. Processes both `wiki/` and the sibling `<workspace>/work/` directory. Returns `{updated, unchanged, skipped}` lists of workspace-relative paths.

CLI: `--dry-run` (print without writing) / `--json` (machine-readable). Dependencies: `tiktoken>=0.7`, `python-frontmatter>=1.1` (added to `pyproject.toml` in v0.4.0).

See [[wiki/sources/2026-05-lattice-wiki-core-tokens-frontmatter-field]].

### wiki_search

`packages/lattice-wiki-core/src/lattice_wiki_core/wiki_search.py`

- `tokenize(text) -> list[str]` — `wiki_search.py:86`. Lowercase, drop stopwords, drop short tokens.
- `bm25_scores(docs, query, k1=1.5, b=0.75) -> list[tuple[int, float]]` — `wiki_search.py:115`.
- `snippet(text, query, width=220) -> str` — `wiki_search.py:140`. Window around the first matching term.

CLI: `--wiki <path> --query <terms> [--limit N=10] [--json]`.

### append_log

`packages/lattice-wiki-core/src/lattice_wiki_core/append_log.py`

- `append_log(wiki, op, title, detail, as_json=False) -> dict` — `append_log.py:61`. Validates op against `VALID_OPS`; appends `## [YYYY-MM-DD] <op> | <title>` + body to `<vault>/log.md`.

`VALID_OPS = {"scan", "ingest", "query", "lint", "create", "update", "delete", "note"}` — `append_log.py:34`.

CLI: `--wiki <path> --op <op> --title <title> [--detail <text>] [--json]`.

### export_marp

`packages/lattice-wiki-core/src/lattice_wiki_core/export_marp.py`

- `to_marp(text, theme) -> str` — `export_marp.py:33`. Drops frontmatter, splits on each `## ` heading.
- `render_one(src, out_path, theme) -> Path` — `export_marp.py:52`.

CLI: `--wiki <path> --page <rel-path-or-dir> [--theme {default|gaia|uncover}] [--out <dir>=slides] [--json]`.
