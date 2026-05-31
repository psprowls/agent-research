# S01 — Research

**Date:** 2026-05-31

## Summary

S01 owns active requirement R001: current GSD artifacts must become the active source of truth for future planning and execution. The main deliverable is a root-level `.gsd/PROJECT.md` project artifact that describes the current repo truth clearly enough for S02/S03 to curate legacy notes and requirements without re-reading the archive. In the current worktree, `.gsd/PROJECT.md` is not present yet; `.gsd/DECISIONS.md`, `.gsd/REQUIREMENTS.md`, and the M001 roadmap/context are available through GSD/inlined context, but the root project artifact still needs to be created.

The current project truth is well-supported by both legacy planning samples and live manifests. `.planning/PROJECT.md`, `.planning/ROADMAP.md`, `.planning/MILESTONES.md`, and `.planning/milestones/v1.11-ROADMAP.md` all agree that the product is `agent-research`, a Python 3.11+ `uv` workspace whose primary deliverable is `graph-wiki-agent`: an AWS Bedrock-backed reimplementation of the `graph-wiki` Claude Code plugin exposed as both a Typer CLI and MCP stdio server. The current repo has one agent package plus seven core packages: `graph-wiki-agent`, `eval-harness`, `graph-io`, `model-adapter`, `source-parser`, `subagent-runtime`, `wiki-io`, and `workspace-io`.

The main implementation risk is over-importing `.planning` into the new active truth. The PROJECT artifact should preserve the shipped trajectory at a high level through v1.11 and explicitly say `.planning/` is archive/reference only. It should not claim exhaustive archive conversion, active legacy phases, or that deferred sweep/debug work is part of M001.

## Recommendation

Create the root PROJECT artifact via `gsd_summary_save` with `artifact_type: "PROJECT"` rather than writing `.gsd/PROJECT.md` directly. Keep it concise and current-state oriented: product identity, core value, package layout, shipped trajectory highlights, active GSD posture, and archive boundary. Use sampled legacy files as evidence, but do not copy long milestone histories wholesale.

For the package layout section, prefer live `pyproject.toml` evidence over old planning prose. For the shipped trajectory section, summarize v1.0-v1.11 as a compact sequence and call out v1.11 as the latest shipped state: TypeScript `type` node kind across `source-parser` and `graph-io`; cost-frontier sweep run/winner selection deferred. This framing unblocks S02 by giving it stable current-truth language and archive-boundary language to build on.

## Implementation Landscape

### Key Files

- `.gsd/PROJECT.md` — target root PROJECT artifact; currently absent in the worktree and should be produced by the executor with `gsd_summary_save` using root-level `artifact_type: "PROJECT"`.
- `.planning/PROJECT.md` — best single legacy source for product identity, core value, current state through v1.11, shipped trajectory, and process caveats.
- `.planning/ROADMAP.md` — shipped milestone ledger v1.0 through v1.11; confirms there is no active legacy milestone and that v1.11 is shipped/archived.
- `.planning/MILESTONES.md` — compact shipped-history ledger; confirms latest v1.11 accomplishments and deferred cost-frontier sweep details.
- `.planning/milestones/v1.11-ROADMAP.md` — latest milestone detail; confirms TypeScript `type` node work, `DERIVER_VERSION` bump, verification, and deferred issues.
- `.planning/deferred-items.md` — contains a stale `test_graph_query_output` snapshot caveat; S01 should not promote this into active project scope, but S02/S03 should preserve it as deferred/caveat context.
- `pyproject.toml` — live workspace source: `[tool.uv.workspace] members = ["packages/*", "agents/*"]`, dev group with pytest/pytest-asyncio/ruff/pre-commit/syrupy/hypothesis, ruff target `py311`, pytest `asyncio_mode = "auto"`.
- `agents/graph-wiki-agent/pyproject.toml` — live primary product source: package description, Python `>=3.11`, dependencies on workspace packages plus `bm25s`, `mcp`, `langchain-aws`, `typer`, `pydantic`, and scripts `graph-wiki-agent` + `graph-wiki-mcp`.
- `packages/eval-harness/pyproject.toml` — deterministic eval checks, pricing, and sweep runner; important because cost-frontier sweep is deferred, not deleted.
- `packages/graph-io/pyproject.toml` — code graph core, SQLite store, manifest scanning, queries, and `cg` CLI.
- `packages/model-adapter/pyproject.toml` — AWS Bedrock model loader; should be described as the route for Bedrock model construction/guarding.
- `packages/source-parser/pyproject.toml` — tree-sitter-backed source parsing and graph projection; latest v1.11 work touched TypeScript type extraction here.
- `packages/subagent-runtime/pyproject.toml` — async fan-out primitive; supports the hand-rolled subagent runtime claim.
- `packages/wiki-io/pyproject.toml` — vault/frontmatter/index/entity IO for generated wiki artifacts.
- `packages/workspace-io/pyproject.toml` — workspace bootstrap, manifest IO, and config resolution.

### Natural Seams

- **Project identity and value:** derive from `.planning/PROJECT.md` plus `agents/graph-wiki-agent/pyproject.toml`.
- **Current package layout:** derive from root and workspace member `pyproject.toml` files; this can be written independently of shipped-history prose.
- **Shipped trajectory:** derive from `.planning/ROADMAP.md`, `.planning/MILESTONES.md`, and v1.11 roadmap; keep this as a compact historical section.
- **GSD posture and archive boundary:** derive from M001 decisions/context; explicitly state `.gsd/` is active and `.planning/` is backed-up reference/archive.

### Build Order

1. Draft `.gsd/PROJECT.md` content around current truth first: product, core value, active source-of-truth posture, and package map. This satisfies R001's core need and gives downstream slices stable language.
2. Add compact shipped trajectory through v1.11 second. Keep it as history, not a roadmap; emphasize latest shipped state and no active legacy milestone.
3. Add archive/deferred boundary last: `.planning/` remains reference-only; cost-frontier sweep debug/rerun and stale snapshot caveat are deferred future context; wholesale archive conversion and migration tooling are out of scope.
4. Save through `gsd_summary_save` (`artifact_type: "PROJECT"`) so DB and rendered disk artifact stay in sync.

### Verification Approach

Use static artifact checks, not product test suites; S01 changes planning artifacts only.

- Confirm `.gsd/PROJECT.md` exists after save.
- Confirm it names `.gsd/` as active source of truth and `.planning/` as archive/reference.
- Confirm it describes the live workspace packages from pyproject evidence: `graph-wiki-agent`, `eval-harness`, `graph-io`, `model-adapter`, `source-parser`, `subagent-runtime`, `wiki-io`, `workspace-io`.
- Confirm it says v1.11 is shipped and does not describe old `.planning` phases as active work.
- Confirm it does not claim wholesale archive conversion, reusable migration tooling, or active cost-frontier sweep execution in M001.
- Suggested shell check after implementation:
  - `test -f .gsd/PROJECT.md`
  - `rg "active source of truth|archive/reference|v1\.11|graph-wiki-agent|subagent-runtime|model-adapter|source-parser|graph-io" .gsd/PROJECT.md`
  - `! rg "wholesale conversion complete|migration tool|Phase 60 active|resume archived" .gsd/PROJECT.md`

## Constraints

- `.gsd/` is the active planning state after initialization; `.planning/` is evidence/archive only.
- The user explicitly wanted current truth, manual curation, high notes, and no wholesale `.planning` conversion.
- Root/project GSD artifacts should be saved through GSD tools so rendered files and DB state remain consistent.
- The root workspace is a `uv` workspace, not a package itself; root `pyproject.toml` has no `[project]` metadata and should not be described as an installable package.
- The current package evidence requires Python `>=3.11`; root ruff target is `py311`.
- Bedrock is v1's provider boundary; avoid language suggesting direct Anthropic API or multi-provider support is current.

## Common Pitfalls

- **Treating `.planning` as active execution state** — use it only as sampled evidence; the new PROJECT should point future agents to `.gsd` first.
- **Copying too much shipped history** — preserve the trajectory in compressed form; detailed old phase ledgers remain in `.planning`.
- **Reviving deferred sweep work** — mention cost-frontier sweep as deferred future work only. M001 does not debug, rerun, or select winners.
- **Overstating verification** — S01 can verify artifact coherence and source references, not product runtime behavior.
- **Misrepresenting package layout** — root `pyproject.toml` is workspace-only; package names/descriptions should come from member manifests.

## Skills Discovered

| Technology | Skill | Status |
|------------|-------|--------|
| uv workspace / Python packaging | `uv-package-manager` | installed |
| Documentation artifact authoring | `write-docs` | installed |

## Sources

- Current product identity and shipped state sampled from `.planning/PROJECT.md`.
- Shipped milestone sequence sampled from `.planning/ROADMAP.md`.
- Latest shipped milestone and deferred sweep context sampled from `.planning/MILESTONES.md` and `.planning/milestones/v1.11-ROADMAP.md`.
- Package layout and current dependency surface sampled from root and workspace member `pyproject.toml` files.