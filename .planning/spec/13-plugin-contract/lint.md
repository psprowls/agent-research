---
command: lint
upstream_source: plugins/lattice-wiki/commands/lint.md
port_verdict: reshape
---

# /graph-wiki:lint — Port Spec

## Shell-out contract

- **Invocation:** `uv run --project "$AGENT_RESEARCH_ROOT" python3 "${CLAUDE_PLUGIN_ROOT}/skills/graph-wiki/scripts/lint_wiki.py" $ARGUMENTS`
- **Target module (claude backend, mechanical pass 1 + semantic pass 2):** `wiki_io.lint_wiki.main`
  - NOTE: this module does not exist in wiki-io as of Phase 13. It MUST be ported from `lattice_wiki_core/lint_wiki.py` (~508 LOC) into `packages/wiki-io/src/wiki_io/lint_wiki.py` as Phase 14 Plan 1 (VP-01 prerequisite) before this shim can dispatch.
- **Companion module (semantic pass 2):** `wiki_io.graph_analyzer.main`
  - This module already exists in wiki-io. `lint_wiki.main` orchestrates both passes internally; `graph_analyzer` is invoked by `lint_wiki` as part of pass 2, not as a separate shim invocation.
- **Target subprocess (bedrock backend):** `code-wiki-agent lint <args>`
- **Args pass-through (1:1 with upstream `lint_wiki.py` flags, except pass-1b/work-layer flags are omitted):**
  - `--stale-days N` (default 90) — pages older than N days flagged as stale
  - `--log-gap-days N` (default 14) — gap between log entries flagged if larger than N days
  - `--json` — emit machine-readable JSON report
  - `--check <groups>` — comma-separated optional check groups to enable beyond the default set (pass-through 1:1; any upstream check group that corresponds to work-layer only is absent from graph-wiki's `lint_wiki` because pass 1b is dropped)
  - No `--work-item` or equivalent work-layer-only flag (pass 1b dropped; see Reshape notes).
- **Pre-step:** NONE — `lint_wiki.main` orchestrates both passes (mechanical + semantic) internally. No separate pre-step script call is needed.
- **VP-01 prerequisite callout:** "Prerequisite — `lint_wiki.py` (~508 LOC) must be ported from `lattice_wiki_core` to `wiki_io` as Phase 14 Plan 1 before this shim can dispatch. Without this port, the shim's `from wiki_io.lint_wiki import main` will raise `ImportError`. Phase 14 Plan 1 follows VP-01..VP-04 contract: verbatim port with brand grep gate, same `main()` entry point shape, same CLI argparse surface."

Reference SHELL-OUT-PATTERN.md §SO-01 for the invocation shape, §SO-02 for the shim boilerplate, and CONTEXT.md §VP-01..VP-04 for the prerequisite porting contract.

## Prose-preservation map

Section-by-section verdict for the upstream `plugins/lattice-wiki/commands/lint.md` body:

| Section | Verdict |
|---------|---------|
| Frontmatter (`name`, `description`) | Verbatim except namespace rename: `lattice-wiki` → `graph-wiki` in the description string. Remove reference to work-layer lifecycle lint ("work-layer lifecycle lint (19 rules over `<workspace>/work/`)" and "## Work lint" header) from the description. |
| `# /lattice-wiki:lint` (H1 + opening paragraph) | Rename: `# /graph-wiki:lint`. Remove work-layer sentence ("Also runs **work-layer lifecycle lint**…"). Mechanical and semantic paragraphs verbatim. |
| `## Usage` | Verbatim except namespace rename (`/lattice-wiki:lint` → `/graph-wiki:lint`). `--stale-days` and `--log-gap-days` flags stay. Workspace discovery sentence: rename `lattice-workspace` → `workspace_io`. |
| `## What happens` | Reshape (partial): |
| `### Pass 1 — Mechanical (scripts)` | Verbatim except script path rename (`scripts/lint_wiki.py` stays) and module reference rename (`lattice_wiki_core` → `wiki_io`). |
| `### Pass 1b — Work lifecycle lint` | DROP — section omitted from ported command body (work-layer out of v1.2 per C-01). `scripts/lint_work.py` does not ship in graph-wiki. |
| `### Pass 2 — Semantic (LLM)` | Verbatim — all bullet points preserved. Rename `lattice-wiki` → `graph-wiki` where it appears in prose. |
| `### Pass 3 — Report` | Reshape: report is grouped under `## Wiki lint` header only. Remove `## Work lint` header from the report description (work layer dropped). |
| `## Sub-agent` | Verbatim except rename: `agents/linter.md` stays; prose inside the agent file rebranded lattice-wiki → graph-wiki (Phase 14 task). |
| `## Frequency` | Verbatim except namespace rename in the trigger column (`/lattice-wiki:scan` → `/graph-wiki:scan`). |
| `## Skill Reference` | Rename: `lattice-wiki/SKILL.md` → `graph-wiki/SKILL.md`; `lattice-wiki/references/lint-workflow.md` → `graph-wiki/references/lint-workflow.md`. |

## Agent / skill rename map

| Upstream path | graph-wiki path | Action |
|---------------|-----------------|--------|
| `agents/linter.md` | `agents/linter.md` | Name stays. Namespace prose rebranded (lattice-wiki → graph-wiki) inside the file. |
| `skills/lattice-wiki/SKILL.md` | `skills/graph-wiki/SKILL.md` | Rename directory + namespace rebrand in prose. |
| `skills/lattice-wiki/references/lint-workflow.md` | `skills/graph-wiki/references/lint-workflow.md` | Rename directory + namespace rebrand in prose. |
| `skills/lattice-wiki/scripts/lint_wiki.py` | `skills/graph-wiki/scripts/lint_wiki.py` | Rename directory; rewrite imports (`lattice_wiki_core.lint_wiki` → `wiki_io.lint_wiki`); bedrock branch shells to `code-wiki-agent lint`. |
| `skills/lattice-wiki/scripts/lint_work.py` | *(not ported)* | DROP — work-layer pass 1b out of v1.2 per C-01. File does not appear under `plugins/graph-wiki/skills/graph-wiki/scripts/`. |

## Reshape notes

This is the only `reshape` verdict in the v1.2 port. Two concrete behavior changes vs upstream:

**Behavior change #1 — Work-layer lint (upstream pass 1b) removed:**
Upstream `/lattice-wiki:lint` runs a third pass (`scripts/lint_work.py`) that enforces 19 lifecycle rules over `<workspace>/work/`. This pass is removed from `/graph-wiki:lint`. The `work/` subsystem is out of v1.2 scope per C-01 (PROJECT.md: "work/ subsystem port — GSD covers work-item lifecycle"). The `## Work lint` section of the upstream report output is also absent. Users running `/graph-wiki:lint` receive mechanical (pass 1) and semantic (pass 2) results only; pass 1b is silently absent (not an error — the command completes successfully without it).

**Behavior change #2 — `wiki_io.lint_wiki` prerequisite port:**
As of Phase 13, `wiki_io.lint_wiki` does not exist in this repo. The upstream module `lattice_wiki_core/lint_wiki.py` (~508 LOC) must be ported into `packages/wiki-io/src/wiki_io/lint_wiki.py` as Phase 14 Plan 1 before the shim can be activated. This follows VP-01..VP-04: verbatim port with brand rename (`lattice_wiki_core` → `wiki_io`, `lattice-wiki` → `graph-wiki` in prose), same `main()` entry point and CLI argparse shape, same test surface (mirror upstream test structure), cleared by Phase 12's `scripts/check-brand.sh` grep gate (VP-03). No other behavior changes: mechanical pass 1 (existing `wiki_io.lint/` rule modules) and semantic pass 2 (`wiki_io.graph_analyzer`) are already present in wiki-io and preserved.

## Verification gate

**Positive test (mechanical pass 1):** Run `/graph-wiki:lint` against a known-dirty wiki vault (e.g., a page with a broken wikilink and a stale timestamp). Mechanical pass 1 issues should match upstream `/lattice-wiki:lint` output for the same vault modulo brand strings. No `## Work lint` section appears in the report.

**Positive test (semantic pass 2):** Run `/graph-wiki:lint` on a vault with a known contradiction between two pages. Semantic pass 2 output should match upstream modulo brand strings.

**Negative test (pass 1b absent):** Confirm that no `lint_work.py` script exists under `plugins/graph-wiki/skills/graph-wiki/scripts/`. Confirm the report output contains no `## Work lint` header.

**VP-01 gate:** Before running any functional test, confirm `wiki_io.lint_wiki` exists (Phase 14 Plan 1 must have run). If it is absent, the shim exits with `ImportError`; this is the expected signal that VP-01 has not yet been executed.

**Smoke check:** `uv run --project "$AGENT_RESEARCH_ROOT" python3 "<plugin>/skills/graph-wiki/scripts/lint_wiki.py"` against a clean vault exits 0 and emits a `## Wiki lint` section. No `ModuleNotFoundError` for `wiki_io.lint_wiki` or `wiki_io.graph_analyzer`.
