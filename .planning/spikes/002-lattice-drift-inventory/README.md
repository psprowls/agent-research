---
spike: 002
name: lattice-drift-inventory
type: standard
validates: "Given the three lattice source packages (lattice-workspace, lattice-wiki-core, lattice-wiki plugin) and the current agent-research packages (vault-io, graph-wiki-agent), when we walk public modules/functions on each side, then we can issue an actionable port verdict (PORT-ALL / PORT-DELTAS-ONLY / PORT-NONE) per source package with module-level rationale"
verdict: VALIDATED ✓
related: [001-subagent-context-audit]
tags: [drift, inventory, port-planning, lattice, refactor]
---

# Spike 002: Lattice Drift Inventory

## What This Validates

**Given** the three lattice source packages and the current agent-research packages, **when** we walk public modules/functions on each side, **then** we can issue an actionable port verdict per source package with module-level rationale — so the next milestone can decide what (if anything) to migrate.

User insight that reshaped the spike: the original framing assumed `lattice-workspace` had drift with `vault-io`. It does not — `vault-io` deliberately replaced the workspace abstraction with a simpler explicit-path model. The real drift lives between **`lattice-wiki-core` and `vault-io`** (plus `graph-wiki-agent`). The plugin pairing was scoped out as T4 territory.

## Investigations

- **A.** `lattice-wiki-core` ↔ `vault-io` (+ overlap with `graph-wiki-agent`) — drift map
- **B.** `lattice-workspace` — import-or-skip (no current target)
- ~~C. `lattice-wiki` plugin~~ — deferred to T4 scoping

## Research

No external libraries researched; this is a code-archaeology spike. Read directly:

- `/Users/pat/Personal/lattice/packages/lattice-workspace/src/` (10 files)
- `/Users/pat/Personal/lattice/packages/lattice-wiki-core/src/` (36 files)
- `/Users/pat/Personal/agent-research/packages/vault-io/src/` (22 files)
- `/Users/pat/Personal/agent-research/agents/graph-wiki-agent/src/` (incl. `commands/`, `prompts/`)

Method: `grep -E '^(def|class|async def)' file.py` per module to extract public surface, then `diff -q` + LOC delta per overlapping module, then targeted body-diff on the most-changed files to confirm pattern (refactor vs feature delta).

## How to Run

Pure analysis spike — no runnable code. To reproduce the inventory:

```bash
# Public-symbol extraction (per source tree)
cd <src-root> && for f in $(find . -name '*.py' -not -name '__init__.py'); do
  echo "=== $f ==="
  grep -E '^(def |class |async def )[A-Za-z_]' "$f"
done

# Per-module LOC delta + byte-identity check
diff -q <lattice-file> <vault-file>
wc -l <lattice-file> <vault-file>
```

Findings below.

## Investigation Trail

### A — lattice-wiki-core ↔ vault-io drift map

**Overlapping modules (vault-io is a strict subset of lattice-wiki-core's file set):**

| Module | LOC (lattice → vault) | Δ | Verdict | Notes |
|---|---|---|---|---|
| `git_state.py` | 72 → 72 | 0 | **IDENTICAL** (byte-equal) | `diff -q` reports no difference. |
| `append_log.py` | 120 → 150 | +30 | DRIFTED-COMPATIBLE | vault-io adds `raise_exception=True` for MCP-boundary error handling (WR-01); pushes errors to stderr-JSON instead of `sys.exit` (WR-02). Pure library-fication. |
| `update_index.py` | 393 → 422 | +29 | DRIFTED-COMPATIBLE | vault-io exposes `update_index(wiki)` as a public library function (lattice has only `main()`). Same lib-ification pattern. |
| `update_tokens.py` | 184 → 190 | +6 | DRIFTED-COMPATIBLE | vault-io drops `get_encoding()`. Consistent with project rule "no tiktoken — use Bedrock CountTokens" (CLAUDE.md §3). |
| `ingest_work_item.py` | 191 → 190 | -1 | DRIFTED-INCOMPATIBLE-API | vault-io exposes `file_work_item(...)` lib function + `_parse_frontmatter`; lattice has `_run_helper(name, ...)` shell-out dispatcher + `main()` only. Different API surface for the same job. |
| `init_vault.py` | 334 → 319 | -15 | DRIFTED-COMPATIBLE | Same surface. Body diff likely cosmetic / template substitutions. |
| `lint/*` (8 files) | (various) | (small) | DRIFTED-COMPATIBLE | Same public `check(...)` per checker. vault-io's `lint/common.py` adds `_is_placeholder_target` (lifted up from lattice's `lint_wiki.py`). Identical checker contracts. |
| `layout_io.py` | 309 → 211 | **-98** | DRIFTED-FEATURE-LOSS | vault-io drops `ensure_package_pages(...)`. Part of the package-family-support strip-down (see below). |
| `detect_containers.py` | 325 → 196 | **-129** | DRIFTED-FEATURE-LOSS | vault-io drops `_has_descendant_manifest`, `_is_package_family_shape`, `_find_package_families`. Package-family detection is **gone**. |
| `scan_monorepo.py` | 1338 → 1187 | **-151** | DRIFTED-FEATURE-LOSS | vault-io drops `_iter_package_family_dirs`, `_find_manifests`, `_collect_package_family_member`. Same package-family strip. |
| `ingest_source.py` | 392 → 211 | **-181** | DRIFTED-CLI-STRIPPED | vault-io drops `main()` + helpers. Library-only; CLI is now `graph-wiki-agent/commands/ingest.py` which imports from `vault_io.ingest_source`. |

**Source-only modules (in `lattice-wiki-core`, missing from `vault-io`):**

| Module | Surface | Reimplemented in graph-wiki-agent? |
|---|---|---|
| `archive_work.py` | Archive command + sidecar regen | ❌ No (no `archive` command in agent-research) |
| `export_marp.py` | Marp slide export | ❌ No |
| `lint_wiki.py` | Wiki-layer lint orchestrator | ✅ Yes — re-implemented in `commands/lint.py::_mechanical_pass` + `_module_pass` using vault_io.lint.* |
| `lint_work.py` | Work-layer lint orchestrator | ❌ No (work-layer lifecycle absent) |
| `regenerate_work_index.py` | Regen work-index.json | ❌ No |
| `wiki_search.py` | BM25 search (load_docs, bm25_scores, snippet, tokenize) | ✅ Yes — re-implemented in `commands/query.py` with comments "copied verbatim from lattice-wiki-core wiki_search.py" + upgraded with embeddings + RRF fusion |
| `work_status.py` | Work-item status report | ❌ No |
| `work/archive.py` | Archive planning (ArchiveAction, ArchivePlan, plan_archive) | ❌ No |
| `work/frontmatter.py` | Work-item frontmatter parser | ❌ No |
| `work/lifecycle_lint.py` | 20+ work-item lint rules | ❌ No |
| `work/plan_table.py` | Plan-table parsing (PlanRow, PlanResult) | ❌ No |
| `work/sidecar.py` | Sidecar build/load (build_sidecar, load_sidecar) | ❌ No |

**Target-only modules (in `vault-io`, not in `lattice-wiki-core`):** None. vault-io's file set is a strict subset.

**Pattern, in one sentence:** `vault-io` is a forked, library-fied, slimmer subset of `lattice-wiki-core` that (1) stripped the entire work-layer lifecycle subsystem, (2) stripped package-family monorepo support, (3) removed CLI `main()` entry points in favor of importable library functions consumed by `graph-wiki-agent/commands/*`, and (4) hardened error handling for MCP boundaries (WR-01 / WR-02 rules).

### B — lattice-workspace import-or-skip

**What it provides:**

| Module | Purpose |
|---|---|
| `config.LatticeConfig` + `resolve(cwd)` | Auto-discover workspace from cwd; walk up to find `.lattice.yaml` |
| `init.init(...)` | Bootstrap workspace: git init + `.lattice.yaml` + `.gitignore` entries |
| `manifest.read/write` | `.lattice.yaml` parse/serialize |
| `paths.{wiki_dir,raw_dir,work_dir,knowledge_dir,graph_dir}` | Path composition over resolved workspace |
| `render.render_workspace_claude_md` | Generate workspace `CLAUDE.md` from template |
| `schema.write_schema` | Write work-item schema |
| `versions.warn_if_stale + pending_updates` | Asset-template drift warnings |
| `assets/CLAUDE.md.template` | Workspace bootstrap template |

**What agent-research has instead:**

`vault-io/_workspace.py::resolve_wiki_and_repo(vault_path)` — 30-line module. Takes an explicit `Path`, falls back to `GRAPH_WIKI_REAL_VAULT_PATH` env var, raises `RuntimeError` otherwise. The docstring is explicit: *"There is no lattice-workspace discovery in this codebase."*

This is a **deliberate architectural rejection**, not a gap. The agent-research v1 model is: caller (CLI / MCP) supplies the vault path; no auto-discovery, no manifest, no workspace bootstrap.

**The decision hinges on a value judgment:**

- **PORT** if you want: run `graph-wiki-agent` from any subdirectory and have it find the wiki, manifest-driven config (`.graph-wiki.yaml`), and a real `init` workflow that creates a workspace shell (not just the wiki tree).
- **SKIP** if you want: stay aligned with the "single-developer velocity" + "cost optimization" constraints in `CLAUDE.md`. The explicit-path model is already working through Phase 9.
- **DEFER** if you want: wait until a concrete user pain point surfaces. Adding the abstraction speculatively contradicts the project's no-feature-flags / no-speculative-flexibility posture.

## Results

### Per-source PORT verdicts

| Source | Verdict | Confidence | Rationale |
|---|---|---|---|
| `lattice-wiki-core` | **PORT-DELTAS-ONLY** (selective) | High | Most overlapping modules already in vault-io and intentionally diverged. The interesting question is: which of the **8 source-only modules** (work-layer + archive + export_marp + work_status + regenerate_work_index) do we want? Almost all are about **work-item lifecycle management** — a subsystem agent-research currently doesn't have. Decide work-layer scope first, then port the matching modules. |
| `lattice-workspace` | **DEFER** (recommended) — or SKIP | Medium | agent-research explicitly rejected the workspace abstraction. Porting it now would reverse that design decision speculatively. Defer until a concrete need (e.g., "I want to run the agent from a subdirectory") surfaces. |
| `lattice-wiki` plugin | (deferred to T4 scoping) | — | Scoped out of this spike. T4 will need its own inventory. |

### Key Discoveries

1. **`vault-io` is a deliberate fork, not a parallel implementation.** Same filenames, same lint/* checker shapes, same `git_state.py` byte-for-byte. The deltas are surgical (lib-ification for MCP, package-family strip, CLI removal). Future graph-wiki-agent work should *update* vault-io from lattice-wiki-core selectively, not re-port wholesale.

2. **The whole `work/` subsystem is missing from agent-research.** `work/archive.py`, `work/lifecycle_lint.py`, `work/plan_table.py`, `work/sidecar.py`, `archive_work.py`, `work_status.py`, `lint_work.py`, `regenerate_work_index.py` — none of these exist in agent-research. If the project wants work-item lifecycle (and per the lattice plugin's `commands/archive.md` + `commands/status.md`, the user surface for it does exist there), this is the single biggest port candidate.

3. **`wiki_search.py` is already covered.** `graph-wiki-agent/commands/query.py` explicitly says "Tokenizer matching lattice-wiki-core behavior" and "stopword set copied verbatim from lattice-wiki-core wiki_search.py" — and then *adds* embeddings + RRF fusion on top. Do not re-port `wiki_search.py`. (Could note this in the wiki itself.)

4. **`lint_wiki.py` is also already covered.** `commands/lint.py::_mechanical_pass` + `_module_pass` reimplement the orchestration using vault_io.lint.* checkers. Do not re-port.

5. **Package-family monorepo support was stripped.** Three modules (`detect_containers.py`, `scan_monorepo.py`, `layout_io.py`) lost their package-family helpers. If a future agent-research user has a monorepo with package families (e.g., `packages/cli/*`, `packages/sdk/*`), the current vault-io will miss them. This is a regression vs. lattice but may be intentional (YAGNI for Pat's projects).

6. **`lattice-workspace` is wholly absent by design.** Don't treat it as a gap; treat it as a rejected concept that may be revisited.

### Investigation surprises

- Found this only by checking: I initially miscategorized `lattice-workspace` ↔ `vault-io` as a drift pair. User correctly identified it as an import-or-skip pair. The spike scope was tightened after that pivot — saved building a useless side-by-side comparison.
- Comments in `graph-wiki-agent/commands/query.py` are unusually load-bearing — they document *exactly* what was copied from lattice-wiki-core. Worth preserving this provenance pattern in any future ports.

### Signal for the build (next-milestone planning)

For the migration themes captured in `.planning/threads/next-milestone-planning.md`:

- **T1 (rename `vault-io` → `workspace-io`)** — still mechanical, no change. But the name `workspace-io` is now slightly misleading since agent-research has explicitly rejected the workspace abstraction. Consider `wiki-io` as an alternative name (matches what the package actually does: wiki-vault I/O).
- **T2 (merge `lattice-workspace` into target package)** — **drop this from T2.** lattice-workspace is a DEFER verdict, not a port. T2 reduces to "rebrand lattice → graph-wiki" only.
- **T3 (migrate lattice-wiki-core into graph-wiki-agent + workspace-io)** — **reframe.** This is not a wholesale port. It is: (a) decide whether to add the work-layer subsystem (~8 modules); (b) selectively bring drift fixes back from lattice into vault-io's overlapping modules (e.g., does the package-family support belong back?); (c) leave already-covered modules (wiki_search, lint_wiki) alone.
- **T5 (plugin as first-class Python package)** — unchanged; out of scope here.

### Open Questions for the Next Milestone

- **Do we want the work-layer lifecycle subsystem** (archive, status, sidecar, lifecycle_lint, plan_table)? This is the dominant porting decision. The lattice plugin's `commands/archive.md` and `commands/status.md` imply user surface exists for it.
- **Do we want to restore package-family monorepo support?** Useful if any target codebase has `packages/cli/*`-style families.
- **Should `vault-io` get renamed to `wiki-io` instead of `workspace-io`?** Matches what it actually is post-strip.
- **Should we adopt a `.graph-wiki.yaml` manifest** (porting just `lattice_workspace.manifest`), without the rest of the workspace discovery? Lighter than the full port, gives config-driven behavior.

## Verdict

**VALIDATED ✓** — the drift map is in hand, with per-module classification and per-source PORT verdicts. The next milestone can plan ports against this evidence instead of guessing. Two of the original five migration themes (T2 merge, T3 wholesale port) are reframed; one (T1 rename) is unaffected; one (T5 plugin packaging) was scoped out.
