# Design: graph-wiki plugin → `entities/` parity with `gw`

**Date:** 2026-06-02
**Status:** Approved — ready for implementation planning (Slice 1)
**Topic:** Update the `plugins/graph-wiki` Claude Code plugin so its mechanical scan produces the new graph-based, single-`entities/`-folder wiki layout — structural parity with the wiki `gw` produces — running entirely without AWS Bedrock. Bring the rest of the plugin's commands and reference docs to the same layout in sequenced follow-on slices.

## Goal

The plugin's scan is stale: its `scan_monorepo.py` shim calls the **old** `wiki_io.scan_monorepo` writer, which emits the legacy `apps/` + `packages/` + `domains/<d>/packages/` folder tree with `overview.md` + sub-pages. The `gw` CLI has since moved to a graph-based scan that writes a **single `entities/` folder** with URI-based filenames across 7 admitted kinds. We want the plugin to produce the same wiki *structure* as `gw`, using the graph, without any Bedrock dependency, and to update every plugin reference/skill/command/agent that still describes the old layout.

## Background (current state)

**The plugin is a thin shim layer.** `plugins/graph-wiki/skills/graph-wiki/scripts/*.py` each import `main()` from `wiki_io.<name>` (the Claude branch) or shell out to `gw` (the opt-in Bedrock branch, selected by `_config.backend_for`). The plugin's Claude branch is wired to **`wiki-io` only** today.

**Two scan implementations exist:**
- **Old:** `wiki_io.scan_monorepo.main()` — manifest-walking, writes the legacy layout (`apps/<name>/overview.md`, `domains/<d>/packages/<name>/overview.md`, default `packages/<name>/overview.md`). This is what the plugin shim calls today. It already *reads* `wiki/entities/` for diffing (Phase 45 dual-view) but still *writes* the old layout.
- **New:** `graph_wiki_core.commands.scan.run_scan()` — graph-based, writes the single `entities/` folder. This is what `gw scan` calls. It interleaves *mechanical* steps with *Bedrock* fan-out.

**`run_scan` mechanical vs. Bedrock steps** (`graph_wiki_core/commands/scan.py`):
- Mechanical (no LLM): `cg` graph build (`_cg_run_build`), `write_entities(conn, wiki, ADMITTED_KINDS)` (~L837), deterministic file-map injection (~L942–1029, leaves `— TODO` descriptions), `regenerate_dependencies_index` / `generate_index` / `update_index`, `append_log`.
- Bedrock (the only LLM call sites): **narrator** fan-out (~L852–910, gated on `entity_write_result.needs_narrative`) which fills each page's `## Narrative` section; **file-describer** fan-out (~L1051–1130) which fills `— TODO` file-map descriptions.
- `scan.py` imports the Bedrock stack **eagerly** at module top (`model_adapter.loader`, `subagent_runtime.pool` — L24–25).

**The new mechanical pieces already live in `wiki-io`** (`entity_writer.write_entities`, `index_generator`, `update_index`, `append_log`, `layout_io`, `link_rewriter`, file-map injection), and `graph-io` (graph build + queries) is itself Bedrock-free. Only the two fan-out steps need Bedrock.

**`entities/` layout (target structure, produced by `gw`):**
- Single `wiki/entities/` folder; bootstrap seeds `entities/.gitkeep` (self-healing — deleted once real pages exist, restored when all are swept).
- Filenames: `<prefix>_<name>[__<6hex>].md` via `wiki_io.entity_writer.short_filename(...)` (collision-disambiguated by a SHA suffix).
- 7 admitted kinds (`ADMITTED_KINDS`): `repository`, `domain`, `package`, `app`, `agent_plugin`, `dependency`, `test_suite`. Prefixes: `repo_`, `domain_`, `pkg_`, `app_`, `agent-plugin_`, `dep_`, and suite-kind-aware (`unit_tests_`, `int_tests_`, …).
- Frontmatter: scanner-owned keys (`SCANNER_OWNED_KEYS` — `uri`, `kind`, `graph_name`, `last_scan_at`, plus per-kind edge-derived keys) fully replaced each scan; human keys (`status`, `last_reviewed`, `owner`, `notes`, …) preserved verbatim; `summary` fill-when-empty.
- Per-kind templates each carry a scanner-owned `## Narrative\n_(scanner will populate on next scan)_` section (the only H2 the scanner rewrites) and, for package/app, a `## File map` section.

**Per-command status vs. `entities/`** (informs the slicing):

| Command | `gw` today | Plugin work |
|---|---|---|
| bootstrap | Already emits `entities/.gitkeep` + `concepts`/`sources`/`adrs`/`architecture` + `.templates` (no apps/packages/domains); shared `wiki_io.init_vault`. | Mechanics already correct — docs only. |
| scan | Graph-based `entities/`, mandatory narration in `graph_wiki_core.run_scan`. Plugin shim still calls old `wiki_io.scan_monorepo`. | **Slice 1 — the core effort.** |
| query | Layout-agnostic (indexes all `.md`). | Docs only. |
| log | Layout-agnostic (append-only). | Docs only. |
| lint | Mostly agnostic; code-drift check assumes old `packages/<name>/<name>.md` → undercounts entity pages. | Fix code-drift + docs. |
| ingest | Still writes `packages/<slug>.md` — `gw` itself hasn't moved ingest to `entities/`. | Net-new on both sides; separate brainstorm. |

## Decisions

- **Scope:** full parity across all commands, decomposed into 4 sequenced slices. This spec details **Slice 1**; Slices 2–4 are a roadmap.
- **Scan prose:** **structural-only.** The plugin scan writes structural entity pages with `## Narrative` placeholders and `— TODO` file-map rows left intact. No harness-LLM prose-filling during scan. (Prose can be filled later by ingest/query/a future pass.)
- **Code organization:** **Approach B** — add a `narrate` flag to `run_scan`; the plugin calls `run_scan(narrate=False)`. (Approaches considered and rejected below.)
- **Lazy Bedrock imports:** **yes** — move `model_adapter`/`subagent_runtime` imports out of `scan.py` module top into the fan-out code paths, so `narrate=False` requires neither installed. Bedrock becomes a genuine opt-in.
- **Plugin caller style:** **direct in-process** — the shim imports and calls `run_scan(...)`; it does **not** shell out to `gw`.
- **Ingest (Slice 4):** deferred to its own brainstorm — it's a feature, not a port.

### Approaches considered and rejected (code organization)

- **A — Extract a Bedrock-free `wiki_io.scan_core.run_mechanical_scan()` shared by both `run_scan` and the plugin.** Cleanest single-source-of-truth and honors the wiki-io/graph-wiki-core split, but refactors more of the working `gw` path. Rejected in favor of B's smaller blast radius given B + lazy imports already removes the Bedrock coupling.
- **C — Rewrite `wiki_io.scan_monorepo` in place, leave `run_scan` alone.** Smallest plugin change but leaves two independent graph-scan implementations that drift — fights the parity goal. Rejected.

## Slice 1 — Scan → `entities/` structural parity (this spec)

### 1. `graph_wiki_core.commands.scan.run_scan` — add `narrate`

- New parameter `narrate: bool = True`. When `False`:
  - **Skip** the narrator fan-out block (~L852–910) and the file-describer fan-out block (~L1051–1130).
  - **Keep** all deterministic steps: graph build, `write_entities`, file-map injection (with `— TODO` descriptions preserved), dependency/index/sub-index regeneration, `append_log`.
- Result: entity pages with the template `## Narrative\n_(scanner will populate on next scan)_` placeholder and `— TODO` file-map rows untouched — structural parity, no prose.
- **Lazy imports:** move `from model_adapter.loader import ...` and `from subagent_runtime.pool import ...` (scan.py L24–25, plus `FILE_DESCRIBER_SYSTEM`/`file_describer`/narrator prompt imports as needed) into the narrator/file-describer code paths so they load only when `narrate=True`. After this, `run_scan(narrate=False)` imports neither package.
- **CLI:** expose `gw scan --no-narrate` wired to `narrate=False`, so CLI and plugin exercise the same flag. (`gw scan` default stays narrated.)

### 2. Plugin shim `scan_monorepo.py` — repoint to the new core (direct call)

- Replace `from wiki_io.scan_monorepo import main` with a direct import of `run_scan` and an in-process invocation `run_scan(..., narrate=False)`, parsing the same argv the old `main` accepted (`--workspace`, `--no-file-map`, `--max-depth`, `--json`). No subprocess, no `gw`.
- The Bedrock branch is unchanged: when `backend_for("scan") == "bedrock"`, still `subprocess.run(["gw", "scan", *argv])` (narrated).
- Retire the **old-layout writer** path in `wiki_io.scan_monorepo`. Shared diff/dual-view read helpers that `run_scan` still depends on stay; only the legacy apps/packages/domains *page-writing* routing is removed.

### 3. Scan markdown — rewrite to the `entities/` model

- `agents/scanner.md` + `commands/scan.md`: replace the old "create `<container>/<name>/overview.md` + sub-pages, route by app/domain" workflow with the thin new flow — run the mechanical script → report added/updated/deleted **entities** (by URI/filename) → confirm deletions (never silently delete; flag large deletion counts). No prose-filling step (structural-only).
- `references/scan-workflow.md` + `references/detection-workflow.md`: rewrite around graph build + `write_entities` + the 7 admitted kinds. Container *detection* still feeds the pinned layout block, but page *routing* collapses to the single `entities/` folder.

### 4. Foundational schema docs — `entities/` vocabulary

- `references/wiki-schema.md`, `references/page-formats.md`, `references/monorepo-principles.md`: replace the apps/packages/domains folder spec and per-category frontmatter with the `entities/` layout — single folder, `<prefix>_<name>[__hex].md` filenames, 7 kinds, `SCANNER_OWNED_KEYS` vs. human-preserved keys, `summary` fill-when-empty, per-kind templates with the scanner-owned `## Narrative` section and `## File map` sections.
- Plugin `CLAUDE.md` "Wiki layout invariants" (L62–73) — update the vault-subdirs list (currently `apps/`, `packages/`, `domains/`, …) to the `entities/` + `concepts`/`sources`/`adrs`/`architecture`/`.templates` layout, and the "when changing layout, update these refs" list.

### Verification / success criteria

- **New package tests** (`graph-wiki-core`, and/or `wiki-io`): `run_scan(narrate=False)` against a fixture repo produces the same `entities/*.md` set, filenames, and frontmatter as a narrated run — only `## Narrative` body and file-map descriptions differ. Assert **zero** narrator/file-describer (Bedrock/subagent) invocation when `narrate=False`.
- **Lazy-import test:** with `model_adapter` / `subagent_runtime` un-importable (e.g. monkeypatched to raise on import), `run_scan(narrate=False)` still completes; `gw scan --no-narrate` runs.
- **Existing Bedrock-shim argv contract test** (`packages/graph-wiki-cli/tests/unit/test_plugin_bedrock_shims.py`) still passes.
- **Manual parity check:** plugin scan vs. `gw scan --no-narrate` on a fixture repo → identical `entities/` trees (diff clean).

### Out of scope (Slice 1)

- Narrative / file-map prose generation by any LLM (structural-only decision).
- ingest, lint code-drift, and the non-scan reference docs (later slices).
- Any change to the `entities/` schema, `short_filename`, `ADMITTED_KINDS`, or templates themselves — Slice 1 consumes them as-is.

## Roadmap — Slices 2–4 (separate specs/plans)

- **Slice 2 — Bootstrap + query + log + reference sweep + `obsidian-markdown` skill.** Bootstrap mechanics already emit `entities/` (shared `wiki_io.init_vault`), so mostly doc work: update `bootstrap`/`query`/`log` command + agent markdown, remaining references, and the `obsidian-markdown` skill's frontmatter schema to the entity kinds/keys. Depends on Slice 1's vocabulary.
- **Slice 3 — Lint → `entities/`.** Fix the code-drift check so it recognizes entity-page filenames (currently assumes legacy `packages/<name>/<name>.md`) in whichever module the plugin's `lint_wiki` shim invokes; update the `linter` agent + `lint-workflow.md`.
- **Slice 4 — Ingest → `entities/` (separate brainstorm).** Net-new: `gw`'s own ingest still writes `packages/<slug>.md`, so this is a feature on both sides, not a port.

## Sources

- `plugins/graph-wiki/CLAUDE.md` — shim architecture, layout invariants, source-of-truth split.
- `plugins/graph-wiki/skills/graph-wiki/scripts/scan_monorepo.py`, `_config.py` — current shim + backend selector.
- `packages/wiki-io/src/wiki_io/scan_monorepo.py` — old-layout writer (routing L657–673).
- `packages/wiki-io/src/wiki_io/entity_writer.py` — `write_entities`, `short_filename`, `ADMITTED_KINDS`, `SCANNER_OWNED_KEYS`, `merge_frontmatter`.
- `packages/wiki-io/src/wiki_io/init_vault.py` — `FIXED_VAULT_DIRS` (entities/ + concepts/architecture/adrs/sources/.templates).
- `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py` — `run_scan` mechanical vs. fan-out steps; eager Bedrock imports L24–25.
- `packages/graph-wiki-cli/src/graph_wiki_cli/cli.py` — `gw scan` (L569–596), bootstrap (L530–567).
- `packages/wiki-io/src/wiki_io/assets/page-templates/` — per-kind entity templates.
