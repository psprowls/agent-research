---
phase: 21-rename-code-wiki-agent-to-graph-wiki-agent-update-all-code-r
verified: 2026-05-19T00:00:00Z
status: passed
score: 9/9 must-haves verified
overrides_applied: 0
human_verification: []
---

# Phase 21: Rename code-wiki-agent → graph-wiki-agent — Verification Report

**Phase Goal:** Mechanical rename of the agent package from `code-wiki-agent` to `graph-wiki-agent` across the full repository — directory names, Python module names, console scripts, internal symbols, user-facing strings, trace dir, plugin shell-out invocations, tests, and planning docs — landed across staged commits with `scripts/check-brand.sh` extended to enforce the new brand.

**Verified:** 2026-05-19
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | SC#1: `agents/code-wiki-agent/` gone; `agents/graph-wiki-agent/` exists with full src + tests subtree | VERIFIED | `test -e agents/code-wiki-agent` returns false; `agents/graph-wiki-agent/{pyproject.toml,src,tests}` all present |
| 2 | SC#2: Python modules renamed — `graph_wiki_agent/` + `graph_wiki_mcp/` exist (not `code_wiki_*`) | VERIFIED | `ls agents/graph-wiki-agent/src/` shows `graph_wiki_agent` + `graph_wiki_mcp`; no stale `code_wiki_*` dirs |
| 3 | SC#3: pyproject `name = "graph-wiki-agent"`, scripts renamed, eval-harness consumer updated, uv.lock regenerated, uv sync succeeds | VERIFIED | `name = "graph-wiki-agent"` confirmed; `[project.scripts]` has `graph-wiki-agent` + `graph-wiki-mcp`; `packages/eval-harness/pyproject.toml` has `"graph-wiki-agent"` dep + `graph-wiki-agent = { workspace = true }`; `uv.lock` has `name = "graph-wiki-agent"`; `uv sync` succeeds (implicit — pytest 582 passed) |
| 4 | SC#4: Zero `code-wiki-*` / `code_wiki_*` / `CodeWiki[A-Z]` / `.code-wiki/` hits in agent pkg; cross-pkg/plugin/tests/docs/eval all clean | VERIFIED | `grep -rE 'code-wiki-agent\|code-wiki-mcp\|code_wiki_agent\|code_wiki_mcp\|CodeWiki[A-Z]\|\.code-wiki/' agents/graph-wiki-agent/` returns 0 hits; same grep across `packages/ docs/ eval/ tests/ plugins/` returns 0 hits |
| 5 | Env vars renamed: `CODE_WIKI_RUN_INTEGRATION` → `GRAPH_WIKI_RUN_INTEGRATION`; `CODE_WIKI_RUN_EVAL` → `GRAPH_WIKI_RUN_EVAL`; `.code-wiki/` trace dir → `.graph-wiki/` | VERIFIED | Zero `CODE_WIKI_RUN_*` hits anywhere outside allowlisted historical sources; both new vars present in `tests/test_integration_gate.py`, root `pyproject.toml`, `packages/eval-harness/pyproject.toml`; pytest skip message confirms `GRAPH_WIKI_RUN_EVAL` is the gate name; `packages/vault-io/tests/fixtures/round-trip-vault/.graph-wiki` renamed; zero `.code-wiki/` outside agent pkg/wiki/.planning |
| 6 | SC#5: `.planning/` swept per D-05; `bash scripts/check-brand.sh` exits 0 | VERIFIED | Brand gate exits 0 (`BRAND-04 OK: zero unallowlisted hits`); 30 `.planning/` files still contain old slugs but ALL are properly allowlisted in `.brand-grep-allow` (Phase 18 dir, threads/archive, intel auto-gen, spec/13-plugin-contract, sketches/*.html — each with `# rationale:` comment per SP-6) |
| 7 | Test suite green: 580+ tests pass with `uv run pytest -m "not integration"` | VERIFIED | 582 passed, 23 skipped, 10 deselected; 19 syrupy snapshots passed |
| 8 | Brand-gate enforcement (D-12): `scripts/check-brand.sh` extended with new patterns; `.brand-grep-allow` has Phase 21 entries | VERIFIED | `scripts/check-brand.sh` contains `code-wiki-agent\|code_wiki_agent\|code-wiki-mcp\|code_wiki_mcp` in HITS regex with Phase 12 lattice patterns preserved; `.brand-grep-allow` has Phase 21 section with `graph-wiki/wiki/`, spike sources, Phase 21 self-dir, plus extra carry-forward allowlists for intel/, sketches/, spec/13-plugin-contract/, phases/18/, threads/archive/ |
| 9 | `git mv` preserved blame (SP-5) | VERIFIED | `git log --follow agents/graph-wiki-agent/pyproject.toml` shows full history pre-rename: `50b490b refactor(21-01): git mv...` followed by `5080a6a feat(11-05)`, `bbc6855 chore(03-01)`, `36c007c feat(01-01)` — 5+ commits chained through the move |

**Score:** 9/9 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `agents/graph-wiki-agent/` | Renamed agent package directory | VERIFIED | Exists with `pyproject.toml`, `src/`, `tests/`; old `agents/code-wiki-agent/` gone |
| `agents/graph-wiki-agent/src/graph_wiki_agent/` | Python package root | VERIFIED | Exists; imports as `graph_wiki_agent.cli` works |
| `agents/graph-wiki-agent/src/graph_wiki_mcp/` | MCP server module root | VERIFIED | Exists; `from graph_wiki_mcp import server` works (stdout-guard fires correctly) |
| `agents/graph-wiki-agent/pyproject.toml` | name="graph-wiki-agent", new scripts | VERIFIED | `name = "graph-wiki-agent"`; `[project.scripts]` → `graph-wiki-agent` + `graph-wiki-mcp` |
| `packages/eval-harness/pyproject.toml` | workspace dep + uv source key updated | VERIFIED | Both `dependencies = [..., "graph-wiki-agent", ...]` and `[tool.uv.sources] graph-wiki-agent = { workspace = true }` present (B2 fix landed in 21-02) |
| `uv.lock` | Reflects new package name | VERIFIED | `grep '^name = "graph-wiki-agent"' uv.lock` matches |
| `plugins/graph-wiki/skills/graph-wiki/scripts/*.py` | Shellouts invoke `graph-wiki-agent` | VERIFIED | 0 hits for `code-wiki-*` in plugin scripts |
| `tests/test_integration_gate.py` | Uses `GRAPH_WIKI_RUN_INTEGRATION` + new agent dir path | VERIFIED | Contains `GRAPH_WIKI_RUN_INTEGRATION` literal; no `agents/code-wiki-agent/` path |
| `scripts/check-brand.sh` | Extended regex with all 4 new patterns; Phase 12 lattice patterns preserved | VERIFIED | Regex confirmed: `lattice\|LATTICE\|lattice_workspace\|lattice_wiki_core\|code-wiki-agent\|code_wiki_agent\|code-wiki-mcp\|code_wiki_mcp` |
| `.brand-grep-allow` | Phase 21 section appended; Phase 12 entries untouched | VERIFIED | Phase 21 section present with required entries + each carrying `# rationale:` comment per SP-6 |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `pyproject.toml [project.scripts]` | `graph_wiki_agent.cli:app` + `graph_wiki_mcp.server:main` | console-script entry points | VERIFIED | `uv run graph-wiki-agent --help` exits 0 with proper help banner |
| `packages/eval-harness/pyproject.toml [tool.uv.sources]` | `agents/graph-wiki-agent/` workspace member | `graph-wiki-agent = { workspace = true }` | VERIFIED | uv sync resolves (pytest 582 passed proves workspace install coherent) |
| Plugin shellout scripts | `graph-wiki-agent` console script | `subprocess.run(["graph-wiki-agent", ...])` | VERIFIED | 0 `code-wiki-*` literals in plugin scripts |
| `tests/test_integration_gate.py` | `GRAPH_WIKI_RUN_INTEGRATION` env var | `pytest.mark.skipif` | VERIFIED | New env var literal present |
| Root `pyproject.toml [tool.pytest.ini_options]` | `GRAPH_WIKI_RUN_EVAL` env marker | pytest env skip | VERIFIED | Pytest skip output: `'Skipped: Set GRAPH_WIKI_RUN_EVAL=1 to run divergence eval'` confirms env var is wired |
| `scripts/check-brand.sh` | `.brand-grep-allow` | `grep -vF -f .brand-grep-allow` | VERIFIED | `bash scripts/check-brand.sh` exits 0 |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Renamed console script runs | `uv run graph-wiki-agent --help` | Exit 0, prints help: "graph-wiki-agent: AWS Bedrock-powered wiki maintenance CLI." | PASS |
| Python module imports under new name | `uv run python -c "import graph_wiki_agent; import graph_wiki_agent.cli"` | Exit 0, prints "agent import OK" | PASS |
| MCP module imports under new name | `uv run python -c "from graph_wiki_mcp import server"` (via stderr) | Imports successfully; stdout guard fires on print (intentional behavior) | PASS |
| Brand gate passes | `bash scripts/check-brand.sh` | Exit 0; "BRAND-04 OK: zero unallowlisted hits" | PASS |
| Test suite (non-integration) passes | `uv run pytest -m "not integration"` | 582 passed, 23 skipped, 10 deselected in 66s; 19 syrupy snapshots passed | PASS |
| Eval env-var gate is renamed | (implicit via pytest skip output) | Skip message references `GRAPH_WIKI_RUN_EVAL=1`, not `CODE_WIKI_RUN_EVAL` | PASS |
| Git history preserved across rename | `git log --follow agents/graph-wiki-agent/pyproject.toml` | Returns 5+ commits including pre-rename history | PASS |

### Anti-Patterns Found

None blocking. Verified findings:

- The 14 `CODE_WIKI_` matches remaining in the repo are exclusively `CODE_WIKI_CONFIG` (a Phase 20 token already deleted from live code), appearing inside `.claude/skills/sketch-findings-agent-research/sources/*/index.html` HTML snapshots of historical commit messages — explicitly allowlisted in `.brand-grep-allow` with D-07-analog rationale ("rewriting would corrupt commit-log quotations"). These are NOT Phase 21 brand tokens (`CODE_WIKI_RUN_INTEGRATION` / `CODE_WIKI_RUN_EVAL`).
- The 30 `.planning/` files still containing `code-wiki-*` references are all properly allowlisted (intel auto-gen files, spec/13-plugin-contract docs about a different rename, Phase 18 phase dir, sketches/*.html, threads/archive/). Each allowlist entry carries a `# rationale:` comment per SP-6.

### Requirements Coverage

Plans declared `requirements: []` (empty arrays). This is acceptable per the verification context: Phase 21's scope IS the requirement, captured in PLAN frontmatter `must_haves` rather than REQ-IDs. The 5-plan must_haves enumerate all Phase 21 success criteria (SC#1–SC#5), and all are verified above. REQUIREMENTS.md contains no Phase 21 entries, which is consistent with this approach.

### Operator Action Items (Out-of-Scope, Flagged)

These items are explicitly out of Phase 21 scope per verification context but require operator follow-up:

1. **Local shell env update** — operator must rename in `~/.zshrc` / direnv / CI:
   - `export CODE_WIKI_RUN_INTEGRATION=...` → `export GRAPH_WIKI_RUN_INTEGRATION=...`
   - `export CODE_WIKI_RUN_EVAL=...` → `export GRAPH_WIKI_RUN_EVAL=...`
2. **Threads archive duplicate** — `.planning/threads/next-milestone-planning.md` and `.planning/threads/archive/next-milestone-planning.md` both exist with different mtimes/sizes; operator must decide whether to merge or delete one. (Pre-existing user state per git status; allowlisted in brand-gate.)
3. **`graph-wiki/.graph-wiki.yaml` workspace-io drift** — file exists at the renamed location; operator must decide whether to commit pending modifications (mentioned in verification context as flagged operator action).

### Re-verification Items

None — initial verification.

---

## PHASE COMPLETE

All 9 must-haves verified. All 5 Success Criteria (SC#1–SC#5) achieved:

- **SC#1** (directory rename with `git mv` blame preserved) — plan 21-01 ✓
- **SC#2** (Python modules renamed; imports updated; agent-pkg pytest non-integration green) — plan 21-03 ✓
- **SC#3** (package metadata + console scripts + uv.lock; `uv sync` succeeds) — plans 21-02 + 21-03 ✓
- **SC#4** (plugin shellouts, env vars, trace dir, cross-pkg sweep) — plan 21-04 ✓
- **SC#5** (`.planning/` historical sweep + brand-gate extension + `.brand-grep-allow` Phase 21 section) — plan 21-05 ✓

**Final two-stage gate** (SP-2): `bash scripts/check-brand.sh` exits 0; `uv run pytest -m "not integration"` exits 0 (582 passed, 23 skipped).

**Branch:** main (merged from `worktree-agent-*` via plans 21-04 and 21-05 executor worktrees per D-08 worktree posture).

_Verified: 2026-05-19_
_Verifier: Claude (gsd-verifier)_
