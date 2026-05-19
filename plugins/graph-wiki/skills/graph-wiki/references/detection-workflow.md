# Detection workflow

How graph-wiki classifies a repo's top-level directories, prompts for ambiguity, and pins the result.

## When detection runs

- `/graph-wiki:init` — full detection on a fresh wiki. Always interactive (or `--non-interactive` to accept all defaults / skip ambiguous).
- `/graph-wiki:scan` — detection runs implicitly as a *reconcile*: comparing the current repo state against the pinned layout. Surfaces drift; never auto-applies.

## Classification rules (first match wins)

1. **`docs` container** — children are predominantly markdown files (≥70% `.md` by file count) and contain no package manifests. The container is pinned (so `/graph-wiki:scan` knows where to look) but **no vault dir is created**: each `.md` is surfaced as an ingest candidate, and accepted candidates become `category: source` summaries under `<workspace>/wiki/sources/`. Other formats (pdf/docx/etc.) are deferred — md only for auto-surface today.
2. **`domain` container** — a strict majority (>50%) of immediate children are themselves package containers (the pattern `<container>/<child>/<grandchild>/<manifest>`). Each child becomes a `domain` page; nested packages get `package`/`app` pages within the domain's vault dir.
3. **`package` container** — immediate children are folders with package manifests (`package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`). App-vs-library subclassification happens at the *page* level via `scan_monorepo`'s existing heuristics (`bin`, `scripts.start`, folder-name tiebreaker for `app`/`web`/`expo`).
4. **`package-family` container** — a directory whose immediate children carry **no top-level manifest** but whose manifests sit 2+ directory levels deeper. The package boundary is the immediate child directory; manifests deeper down are aggregated into the page's `manifests:` frontmatter. The detector recurses up to 3 levels from the repo root looking for this shape, so it can surface nested package-families (e.g. `references/hubspot/hubspot-ui-extensions`) as their own rows with a slashed `source:`. Per-row fields: `package_depth` (default 1), `manifest_glob` (default `"**/package.json"`), `slug_source` (default `dirname`), optional `domain`. See `scan-workflow.md` for a worked example.
5. **`single-package`** — repo root has a manifest and no top-level dir matches rules 1–4. Wiki collapses to one root page; no structural dirs.
6. **`ambiguous`** — manifests + docs mixed, split children, or unrecognized contents. Flagged for user decision in `/graph-wiki:init`. Choices: `package` / `app` / `domain` / `package-family` / `docs` / `skip`.

## Container types and their templates

| Classification | Vault dir contents | Per-page template | Per-page category |
|---|---|---|---|
| `app` | one page per child | `app.md` | `app` |
| `package` | one page per child | `package.md` | `package` |
| `domain` | one page per child + nested package pages | `domain.md` + `package.md`/`app.md` | `domain` (containers), `package`/`app` (nested) |
| `package-family` | one page per child directory at `package_depth` (default 1); explicit `vault_dir` controls placement | `package.md` (with `manifests:` frontmatter populated) | `package` |
| `docs` | none (no vault dir) — `.md` files become `category: source` summaries under `<workspace>/wiki/sources/` via `/graph-wiki:ingest` | `source.md` | `source` |

## Ambiguous containers

A folder is flagged ambiguous when:
- It contains both manifests and loose markdown.
- Some children have manifests and some don't (no clear majority pattern).
- It's empty or unrecognized.

The user picks one of `package` / `app` / `domain` / `package-family` / `docs` / `skip` during `/graph-wiki:init` (or accepts the default `skip` with `--non-interactive`).

## Override paths

- Edit the layout block directly in `<workspace>/wiki/CLAUDE.md` to change a `classification` or `vault_dir`.
- Re-run `/graph-wiki:init` to re-detect from scratch (will overwrite the existing block).

## Hand-edit constraints

The layout block is parsed by a hand-rolled minimal YAML reader (stdlib only). It expects the exact shape emitted by `layout_io.write_layout`:
- Two-space indent on container fields (`source`, `vault_dir`, etc.)
- `null` for missing optional values
- Quoted strings only for `note` fields

Stick to those conventions when hand-editing; the parser won't tolerate multi-line strings, comments, or tabs.

## Scripts

- `detect_containers.py` — classifier. Standalone CLI or imported by `init_vault.py` and `scan_monorepo.py`.
- `layout_io.py` — reads/writes the fenced layout block. Single owner of parse/serialize logic.
- `init_vault.py` — runs detection, prompts the user, writes the block.
- `scan_monorepo.py` — reads the block, walks pinned containers, surfaces reconcile drift, lists in-repo `.md` ingest candidates from pinned `docs` containers.
