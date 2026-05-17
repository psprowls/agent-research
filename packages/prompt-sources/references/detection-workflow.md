# Detection workflow

How lattice-wiki classifies a repo's top-level directories, prompts for ambiguity, and pins the result.

## When detection runs

- `/lattice-wiki:init` — full detection on a fresh wiki. Always interactive (or `--non-interactive` to accept all defaults / skip ambiguous).
- `/lattice-wiki:scan` — detection runs implicitly as a *reconcile*: comparing the current repo state against the pinned layout. Surfaces drift; never auto-applies.

## Classification rules (first match wins)

1. **`docs` container** — children are predominantly markdown files (≥70% `.md` by file count) and contain no package manifests. The container is pinned (so `/lattice-wiki:scan` knows where to look) but **no vault dir is created**: each `.md` is surfaced as an ingest candidate, and accepted candidates become `category: source` summaries under `<workspace>/wiki/sources/`. Other formats (pdf/docx/etc.) are deferred — md only for auto-surface today.
2. **`domain` container** — a strict majority (>50%) of immediate children are themselves package containers (the pattern `<container>/<child>/<grandchild>/<manifest>`). Each child becomes a `domain` page; nested packages get `package`/`app` pages within the domain's vault dir.
3. **`package` container** — immediate children are folders with package manifests (`package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`). App-vs-library subclassification happens at the *page* level via `scan_monorepo`'s existing heuristics (`bin`, `scripts.start`, folder-name tiebreaker for `app`/`web`/`expo`).
4. **`single-package`** — repo root has a manifest and no top-level dir matches rules 1–3. Wiki collapses to one root page; no structural dirs.
5. **`ambiguous`** — manifests + docs mixed, split children, or unrecognized contents. Flagged for user decision in `/lattice-wiki:init`. Choices: `package` / `app` / `domain` / `docs` / `skip`.

## Container types and their templates

| Classification | Vault dir contents | Per-page template | Per-page category |
|---|---|---|---|
| `app` | one page per child | `app.md` | `app` |
| `package` | one page per child | `package.md` | `package` |
| `domain` | one page per child + nested package pages | `domain.md` + `package.md`/`app.md` | `domain` (containers), `package`/`app` (nested) |
| `docs` | none (no vault dir) — `.md` files become `category: source` summaries under `<workspace>/wiki/sources/` via `/lattice-wiki:ingest` | `source.md` | `source` |

## Ambiguous containers

A folder is flagged ambiguous when:
- It contains both manifests and loose markdown.
- Some children have manifests and some don't (no clear majority pattern).
- It's empty or unrecognized.

The user picks one of `package` / `app` / `domain` / `docs` / `skip` during `/lattice-wiki:init` (or accepts the default `skip` with `--non-interactive`).

## Override paths

- Edit the layout block directly in `<workspace>/wiki/CLAUDE.md` to change a `classification` or `vault_dir`.
- Re-run `/lattice-wiki:init` to re-detect from scratch (will overwrite the existing block).

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
