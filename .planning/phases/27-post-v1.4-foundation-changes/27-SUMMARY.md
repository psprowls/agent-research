---
phase: 27
name: post-v1.4-foundation-changes
milestone: v1.5
status: complete
mode: retroactive
authored: 2026-05-25
git_range: 9b8ac87..f896d99
---

# Phase 27 — post-v1.4-foundation-changes (retroactive)

## Why this phase exists

Between the v1.4 milestone close (HEAD = `e0c2908`, archived 2026-05-25) and v1.5 scoping, seven commits landed directly on `main` without a tracking phase: a repo rename, an env var sweep, doc cleanup, and a package-level workspace restructure that added two new packages and renamed `vault-io → wiki-io`.

This phase is a **retroactive capture** — the work is shipped; this file is the canonical traceability record. No PLAN.md was authored; no executor ran; no VERIFICATION.md was generated. The git history *is* the evidence.

## What shipped

| Commit | Date (local) | Subject | Requirement |
|--------|--------------|---------|-------------|
| `9b8ac87` | 2026-05-24 | rename repo deep-agents to agent-research | REPO-01 |
| `ff835c4` | 2026-05-24 | cleanup un-helpful mentions of lattice-wiki | CLEANUP-01 |
| `9ab8a58` | 2026-05-24 | remove spikes and sketches | CLEANUP-02 |
| `39f1364` | 2026-05-24 | `DEEP_AGENTS_ROOT` → `AGENT_RESEARCH_ROOT` | REPO-02 |
| `1651d14` | 2026-05-24 | tweak to README | CLEANUP-02 |
| `b63bcac` | 2026-05-24 | remove old docs | CLEANUP-02 |
| `f896d99` | 2026-05-25 | bring graph-io and source-parser in, rename vault-io to wiki-io | PKG-01, PKG-02, RENAME-01 |

## Key deliverables

### REPO-01 / REPO-02 — Repo + env rename (commits `9b8ac87`, `39f1364`)

- Repo identity moved from `deep-agents` → `agent-research` (147 files touched in `9b8ac87`).
- Env var `DEEP_AGENTS_ROOT` → `AGENT_RESEARCH_ROOT` swept across all shell-out templates (`uv run --project "$AGENT_RESEARCH_ROOT" python ...`), plugin docs, and any scripts that resolve the workspace root.
- README polish (`1651d14`).

### PKG-01 — `packages/graph-io/` added (commit `f896d99`)

- New workspace package: code-graph core for the graph-wiki ecosystem.
- Surface: SQLite store, manifest scanning, queries, `cg` CLI.
- Declared workspace dependencies: `source-parser`, `workspace-io`.
- Layout: `src/graph_io/{cli/, packages.py, queries.py, resolve.py, schema.py, store.py, sync_wiki.py, update.py, upsert.py, _ignore.py, exit_codes.py}`.
- Version pinned at `0.2.1`.

### PKG-02 — `packages/source-parser/` added (commit `f896d99`)

- New workspace package: tree-sitter-backed Python package turning source files into a span-bearing `SourceTree` with a graph projection aligned to lattice-graph.
- Layout: `src/source_parser/{errors.py, grammars.py, parse.py, parsers/, projections/, tree.py}`.
- Dependencies: `tree-sitter>=0.23.0`, `tree-sitter-language-pack>=0.8.0,<=1.6.2`.
- Version pinned at `0.1.0`.

### RENAME-01 — `vault-io → wiki-io` (commit `f896d99`)

- Package directory renamed `packages/vault-io/ → packages/wiki-io/` via `git mv` (history preserved per the workspace-rename precedent from v1.3 Phase 21).
- Module name `vault_io → wiki_io`.
- Import sweep across `agents/`, `packages/`, `plugins/`, `eval-harness`, and the entire test suite.
- 663 files changed across the full `f896d99` commit (which combines this rename with the two package additions).

### CLEANUP-01 / CLEANUP-02 — Doc and tree cleanup

- `lattice-wiki` mentions purged from README and core docs (`ff835c4`) — final cleanup of brand artifacts that survived the v1.2 Phase 12 rebrand.
- `.planning/spikes/` and `.planning/sketches/` directories removed (`9ab8a58`) — these were exploratory artifacts whose findings were already promoted into CLAUDE.md / project skills.
- Old docs removed (`b63bcac`).

## Decisions captured

- **Repo rename name choice** — `agent-research` selected over alternatives (e.g., `graph-wiki-research`) to keep the door open for AI-agent research beyond the wiki workflow. The first package (`graph-wiki-agent`) remains the v1 deliverable; the repo name is intentionally broader than v1's scope.
- **Two new packages added before any consumer wiring exists** — `graph-io` and `source-parser` ship as standalone workspace members whose consumers in `agents/graph-wiki-agent/` are not yet wired up. This is intentional: v1.5 is a foundation milestone, not an integration milestone. Wiring happens in v1.6+.
- **`vault-io → wiki-io` rename closes the v1.4 nomenclature work** — v1.4 swept `vault_path → workspace_path` and `vault:` → `wiki:` across helpers and external surfaces, but the package directory itself still carried the `vault` brand. This rename completes the brand alignment.
- **No PLAN.md** — work was already shipped at retro-capture time. Future retro-capture phases should follow the same shape: SUMMARY.md + git range, no fake PLAN.md.

## Out of scope (for v1.6+)

- Wiring `graph-io` queries into the scanner/librarian for code-aware grounding.
- Wiring `source-parser` span emission into the citation/grounding pipeline.
- Whatever downstream integration story `cg` CLI implies for the `graph-wiki-agent` MCP surface.
- All carry-forward items listed in `.planning/STATE.md` `## Deferred Items`.

## Verification

| Success Criterion (from ROADMAP) | Verified Against |
|----------------------------------|-------------------|
| `git remote -v` shows `agent-research` | live repo state |
| `grep -rE "DEEP_AGENTS_ROOT" .` returns 0 substantive hits | `39f1364` diff |
| `packages/graph-io/` with workspace deps | `packages/graph-io/pyproject.toml` |
| `packages/source-parser/` with tree-sitter deps | `packages/source-parser/pyproject.toml` |
| `packages/vault-io/` removed; `wiki-io` canonical | `f896d99` git mv diff |
| 0 substantive `lattice-wiki` hits in README/core docs | `ff835c4` diff |
| `.planning/spikes/` + `.planning/sketches/` removed | `9ab8a58` diff |

All criteria satisfied at v1.5 retroactive close.

---

*Authored: 2026-05-25 — retroactive Phase 27 SUMMARY.*
