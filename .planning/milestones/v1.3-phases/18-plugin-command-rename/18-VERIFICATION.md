---
phase: 18-plugin-command-rename
verified: 2026-05-19T22:00:00Z
status: human_needed
score: 7/8 must-haves verified (SC#3 requires manual UAT — cannot be verified autonomously)
overrides_applied: 0
gaps: []
human_verification:
  - test: "Install/reinstall the graph-wiki plugin in Claude Code, then type `/init` at the prompt"
    expected: "Claude Code's native `initialize CLAUDE.md` workflow fires (NOT the graph-wiki bootstrap workflow). Confirms the namespace collision is resolved by the rename."
    why_human: "Cannot install a plugin in a live Claude Code session from the verifier; requires interactive UAT in the host application. This is SC#3 of Phase 18 and is the only check D-07 explicitly marks as manual smoke."
---

# Phase 18: Plugin Command Rename — Verification Report

**Phase Goal:** Claude Code's built-in `/init` command is reachable again by renaming the conflicting plugin command to `/graph-wiki:bootstrap` with all references updated. Verb is `bootstrap` per CONTEXT.md D-01.
**Verified:** 2026-05-19T22:00:00Z
**Status:** `human_needed` — 7/8 must-haves automatically verified; SC#3 (Claude Code `/init` reachability) is a manual UAT step by design.
**Re-verification:** No — initial verification.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `plugins/graph-wiki/commands/bootstrap.md` exists; `init.md` is gone (SC#1) | VERIFIED | `ls plugins/graph-wiki/commands/bootstrap.md` → present; `ls plugins/graph-wiki/commands/init.md` → "No such file"; git log shows `R087 init.md → bootstrap.md` in commit `a9ae5af` |
| 2 | Zero stale `graph-wiki:init` references in active source (SC#2) | VERIFIED (with allowlisted self-reference) | `grep -rln 'graph-wiki:init\b' plugins/ packages/ agents/ scripts/ docs/ README.md CLAUDE.md` → only hit is `scripts/check-brand.sh` (the enforcement regex itself, properly self-allowlisted in `.brand-grep-allow` line 59). All other paths clean. |
| 3 | Zero `wiki_init` in `agents/` (SC#2) | VERIFIED | `grep -rln '\bwiki_init\b' agents/` → exit 1 (no hits) |
| 4 | No `def init` in `agents/code-wiki-agent/src/code_wiki_agent/cli.py` (SC#2) | VERIFIED | `grep -rn '\bdef init\b' agents/.../cli.py` → exit 1 (no hits) |
| 5 | `code-wiki-agent --help` lists `bootstrap`, does NOT list `init` (SC#2) | VERIFIED | Ran `uv run --package code-wiki-agent code-wiki-agent --help` — output Commands list contains `bootstrap  Bootstrap a wiki vault structure…`; no `init` row (the only `in`-prefixed row is `ingest`). |
| 6 | `wiki_bootstrap` importable; `wiki_init` raises ImportError (D-04 hard cut) | VERIFIED | `from code_wiki_mcp import server; server.wiki_bootstrap` resolves to `<function wiki_bootstrap at 0x10a1589a0>`. `from code_wiki_mcp.server import wiki_init` raises `ImportError: cannot import name 'wiki_init' from 'code_wiki_mcp.server'`. |
| 7 | Brand-gate enforcement: CHECK 2 + CHECK 3 + allowlist correctly extended (SC#2 + D-05) | VERIFIED | `scripts/check-brand.sh` contains CHECK 2 (`graph-wiki:init\b|\bwiki_init\b` over `packages/ agents/ plugins/ .planning/ scripts/ docs/ README.md CLAUDE.md`) and CHECK 3 (`^\s*def init\(` against `cli.py`). Both pass green in isolated invocation. `.brand-grep-allow` has narrow Phase 18 exemptions only (two surgical entries: `.planning/phases/18-plugin-command-rename/` and the folded-todo filename in `resolved/`). No parent-directory wildcards. |
| 8 | With graph-wiki installed, typing `/init` invokes Claude Code's native CLAUDE.md workflow (SC#3) | FLAG_FOR_UAT | Cannot be verified autonomously — requires interactive Claude Code session. See "Human Verification Required" section. |

**Score:** 7/8 truths automatically verified; 1 deferred to UAT by design (D-07 explicitly classifies SC#3 as manual smoke).

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `plugins/graph-wiki/commands/bootstrap.md` | Renamed from `init.md` via `git mv`; body uses `/graph-wiki:bootstrap` | VERIFIED | Front-matter `name: bootstrap`; 9 `/graph-wiki:bootstrap` literals in body; 0 `/graph-wiki:init` literals; `git log -1 a9ae5af --name-status` shows `R087 init.md → bootstrap.md` |
| `plugins/graph-wiki/commands/init.md` | Must NOT exist (D-04 hard cut, no stub redirector) | VERIFIED | `test ! -e plugins/graph-wiki/commands/init.md` → exit 0 |
| `agents/code-wiki-agent/src/code_wiki_agent/cli.py` | Typer `def bootstrap` present, `def init` absent | VERIFIED | `grep -cE '^\s*def bootstrap\(' cli.py` → 1; `grep -cE '^\s*def init\b' cli.py` → 0 |
| `agents/code-wiki-agent/src/code_wiki_mcp/server.py` | `wiki_bootstrap` tool registered (single registration); `WikiBootstrapInput`/`WikiBootstrapOutput` Pydantic models | VERIFIED | `@mcp.tool(name="wiki_bootstrap", …)` at line 213; `async def wiki_bootstrap(...) -> WikiBootstrapOutput` at line 214; `WikiBootstrapInput` and `WikiBootstrapOutput` classes present. No `wiki_init`/`WikiInitInput`/`WikiInitOutput` residue. |
| `agents/code-wiki-agent/tests/unit/test_commands_bootstrap.py` | Renamed via `git mv` from `test_commands_init.py` | VERIFIED | File exists; old `test_commands_init.py` absent; git log records `R068` rename in commit `5074d62` |
| `scripts/check-brand.sh` | Contains CHECK 2 (CMD-rename regex) and CHECK 3 (`def init(` in cli.py) | VERIFIED | Lines 49–63 implement CHECK 2; lines 65–75 implement CHECK 3. Tail message updated to name all three checks. |
| `.brand-grep-allow` | Phase 18 section with two narrow exemptions; no parent-directory wildcards | VERIFIED | Lines 203–212 — `.planning/phases/18-plugin-command-rename/` and `.planning/todos/resolved/2026-05-19-rename-graph-wiki-init-command-to-init-wiki.md`. Both carry `# rationale:` comments. |
| `.planning/todos/resolved/2026-05-19-rename-graph-wiki-init-command-to-init-wiki.md` | Folded into resolved/ via `git mv` | VERIFIED | File present in `resolved/`; absent from `pending/` |
| `.planning/REQUIREMENTS.md` | CMD-01/CMD-02/CMD-03 bodies rewritten to match as-built scope | VERIFIED | Lines 41–43 describe rename to `bootstrap.md`, `wiki_bootstrap`, and the brand-gate enforcement |
| `.planning/ROADMAP.md` Phase 18 section | Goal + SC text use `/graph-wiki:bootstrap` | VERIFIED | Lines 93–101 — goal names `/graph-wiki:bootstrap`; SC#1 names `bootstrap.md`; SC#2 names `/graph-wiki:bootstrap` |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `plugins/graph-wiki/commands/bootstrap.md` | `code_wiki_agent.commands.init.init_vault` (internal script) | Front-matter `name: bootstrap` + body references | WIRED | `init_vault.py` script reference left intact per D-02 (out of scope); bootstrap.md body references it for the implementation. |
| Typer CLI `bootstrap` subcommand | `code_wiki_agent.commands.init.run_init` | `from code_wiki_agent.commands.init import run_init` | WIRED | Import preserved in `cli.py` line 14 per D-02 (internal module unchanged). `--help` shows `bootstrap` row. |
| MCP `wiki_bootstrap` tool | `code_wiki_agent.commands.init.run_init` | `from code_wiki_agent.commands.init import InitResult, run_init` | WIRED | Internal import preserved per D-02. Single `@mcp.tool(name="wiki_bootstrap", ...)` registration. |
| `vault-io` user-facing error strings | New slug | Direct string literal | WIRED | `packages/vault-io/src/vault_io/lint/container.py:35` and `packages/vault-io/src/vault_io/scan_monorepo.py:1157` now reference `/graph-wiki:bootstrap`. Verified via `grep`. |
| `scripts/check-brand.sh` CHECK 2 | `.brand-grep-allow` | `grep -vF -f <(...)` allowlist filter | WIRED | Isolated CHECK 2 invocation returns `(no hits — GREEN)`. |
| `scripts/check-brand.sh` CHECK 3 | `agents/code-wiki-agent/src/code_wiki_agent/cli.py` | Direct file grep | WIRED | Isolated CHECK 3 invocation returns `(no hits — GREEN)`. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `bootstrap` Typer subcommand registered in Bedrock CLI | `uv run --package code-wiki-agent code-wiki-agent --help` | Commands list contains `bootstrap  Bootstrap a wiki vault structure (creates raw/ and work/ siblings).`; no `init` row | PASS |
| `wiki_bootstrap` symbol importable from MCP server | `python -c "from code_wiki_mcp import server; …" 2>&1` (printed to stderr to bypass MCP stdout guard) | Resolves to `<function wiki_bootstrap at 0x10a1589a0>` | PASS |
| `wiki_init` symbol gone (D-04 hard cut) | `from code_wiki_mcp.server import wiki_init` | `ImportError: cannot import name 'wiki_init' from 'code_wiki_mcp.server'` | PASS |
| Test suite green | `uv run --package code-wiki-agent pytest agents/code-wiki-agent/tests/ -m "not integration" -q` | `212 passed, 1 skipped, 5 deselected in 21.39s`. 19 snapshots passed. | PASS |
| CHECK 2 (graph-wiki:init\|wiki_init) isolated invocation | (full grep + allowlist as in script) | `(no hits — GREEN)` | PASS |
| CHECK 3 (def init\( in cli.py) isolated invocation | `grep -nE '^\s*def init\(' agents/code-wiki-agent/src/code_wiki_agent/cli.py` | `(no hits — GREEN)` | PASS |
| Full brand-gate run | `bash scripts/check-brand.sh` | Exits 1 on pre-existing BRAND-04 lattice hits (79 hits in `.planning/milestones/v1.2-phases/` + `.planning/phases/21-...`). **Out of scope for Phase 18** per verification target — those are Phase 21's responsibility. CHECK 2 + CHECK 3 proven green in isolation. | EXPECTED (gated by Phase 21 scope) |

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|-------------|---------------|-------------|--------|----------|
| CMD-01 | 18-01 | `plugins/graph-wiki/commands/init.md` renamed to `bootstrap.md` via `git mv` | SATISFIED | File at `plugins/graph-wiki/commands/bootstrap.md`; old path absent; git rename record `R087` in `a9ae5af`. |
| CMD-02 | 18-02 (MCP), 18-03 (CLI) | Bedrock CLI Typer `init → bootstrap`; MCP tool `wiki_init → wiki_bootstrap` + Pydantic model renames | SATISFIED | Typer `def bootstrap` present; MCP `@mcp.tool(name="wiki_bootstrap")` single registration; `WikiBootstrapInput`/`WikiBootstrapOutput` defined; hard-cut import verification of `wiki_init` raises ImportError. |
| CMD-03 | 18-04 (active sweep), 18-05 (historical sweep), 18-06 (brand-gate + folded todo) | Active-source + historical `.planning/` references swept; `scripts/check-brand.sh` extended with word-boundary regexes; `.brand-grep-allow` updated with narrow exemptions; folded todo moved to resolved | SATISFIED | Active sweep (10 files modified, commit `5d8160e`); historical sweep (18 files modified, commit `e7b1f1a`); brand-gate CHECK 2 + CHECK 3 added (commit `97b0b44`); todo moved to `resolved/`. CHECK 2 and CHECK 3 both green in isolation. |

No orphaned requirements — all three Phase 18 requirements (CMD-01, CMD-02, CMD-03) are claimed by Phase 18 plans and verified.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | No new TBD/FIXME/XXX/placeholder/return-null/return-empty-array patterns introduced by Phase 18 changes | — | None |

The Phase 18 commits are pure rename + body-text/sweep edits. No new code logic added, no new stubs introduced. Internal `init_vault.py` and `init_vault()` function remained unchanged by design (D-02) and continue to be the real implementation backing the renamed surfaces.

### Hard-Cut D-04 Audit

| Anti-shim Check | Status | Evidence |
|-----------------|--------|----------|
| No `init.md` stub redirector | VERIFIED | `find plugins -name 'init.md'` returns no results |
| No Typer alias `init` mapping to `bootstrap` | VERIFIED | `code-wiki-agent init --help` exits with Typer's `code=2` ("No such command 'init'. Did you mean 'lint', 'ingest'?") per 18-03 SUMMARY; cli.py contains no `init` Typer command (grep for `def init\b` returns 0 hits) |
| No dual MCP registration of `wiki_init` AND `wiki_bootstrap` | VERIFIED | Single `@mcp.tool(name="wiki_bootstrap", ...)` registration in `server.py` line 213; `wiki_init` symbol raises ImportError on import attempt |

### Folded Todo

| Check | Status | Evidence |
|-------|--------|----------|
| `.planning/todos/pending/2026-05-19-rename-graph-wiki-init-command-to-init-wiki.md` absent | VERIFIED | `test ! -e ...` exits 0 |
| `.planning/todos/resolved/2026-05-19-rename-graph-wiki-init-command-to-init-wiki.md` present | VERIFIED | `test -e ...` exits 0 |
| Allowlisted by exact path in `.brand-grep-allow` | VERIFIED | Line 212 of `.brand-grep-allow` names the resolved/ filename specifically |

### Out-of-Scope Items (Explicit, Not Gaps)

| Item | Reason out of scope |
|------|---------------------|
| `packages/vault-io/src/vault_io/init_vault.py` script + `init_vault()` function | D-02 (CONTEXT.md): internal API, machine-facing, intentionally NOT renamed. Confirmed present and unchanged. |
| BRAND-04 lattice CHECK 1 still failing (79 hits) | Verification target explicitly excludes; that is Phase 21's scope (`code-wiki-agent → graph-wiki-agent` rename). |
| 5 files with plain `init-wiki` literals (`MILESTONES.md`, `STATE.md`, `PROJECT.md`, `17-CONTEXT.md`, `21-CONTEXT.md`) | Verification target explicitly excludes. These reference the OLD planned-rename direction (`/init` → `/init-wiki`), not the actual `graph-wiki:init` slug. Not a Phase 18 success criterion. |

### Human Verification Required

#### 1. Claude Code native `/init` reachable (SC#3) — ✅ PASSED 2026-05-20

- **Test:** Install or reinstall the `graph-wiki` plugin in Claude Code (`claude plugin install graph-wiki` or follow the reinstall callout in `plugins/graph-wiki/README.md`). In a Claude Code session with the plugin loaded, type `/init` at the prompt.
- **Expected:** Claude Code's native "initialize CLAUDE.md" workflow fires (the same one that would run if no graph-wiki plugin were installed). The `graph-wiki` plugin's bootstrap workflow must NOT trigger — to invoke the graph-wiki workflow, the user must type `/graph-wiki:bootstrap`.
- **Why human:** Cannot install/load a Claude Code plugin from the verifier process. Requires an interactive Claude Code session. This is the canonical SC#3 manual smoke test per CONTEXT.md D-07 and was deferred to UAT by design.

**UAT result (2026-05-20, during quick task 260520-bgd):**
- Plugin installation state: `graph-wiki@deep-agents`, scope `local`, `projectPath: /Users/pat/Personal/deep-agents`.
- Plugin source resolution: For local-scope plugins, Claude Code reads command files from `projectPath` (post-rename: `plugins/graph-wiki/commands/bootstrap.md`), not from the `~/.claude/plugins/cache/` snapshot (which is still pre-rename from the 2026-05-18 install — pre-dates the 2026-05-19 rename commit `a9ae5af`). Available skills in the live session correctly include `graph-wiki:bootstrap` and NOT `graph-wiki:init`.
- **Test outcome:** User typed `/init` in an active Claude Code session loaded against `/Users/pat/Personal/deep-agents`. Claude Code dispatched the prompt to its **native `init` skill** — confirmed by the canonical native-init prompt text ("Please analyze this codebase and create a CLAUDE.md file…") arriving at the model layer. The graph-wiki bootstrap workflow did **not** fire.
- **Verdict:** ✅ PASS. `/init` is unshadowed by the plugin; native CLAUDE.md init workflow is reachable. `/graph-wiki:bootstrap` remains the only way to invoke the plugin's bootstrap workflow.
- **Note for fresh installs:** The cached plugin under `~/.claude/plugins/cache/deep-agents/graph-wiki/0.1.0/commands/` is stale (pre-rename `init.md` still present). This does not affect local-scope plugin resolution but means anyone using a non-local install scope MUST reinstall to pick up the rename. The reinstall callout already lives in `plugins/graph-wiki/README.md` (line ~27).

### Gaps Summary

No gaps found. All 7 autonomously-verifiable must-haves passed plus SC#3 (the deferred human UAT) closed PASS on 2026-05-20.

Status was `human_needed` at original verification time pending SC#3 UAT; closed to `passed` on 2026-05-20.

---

## PHASE COMPLETE

All success criteria achieved:

- SC#1 (file rename via `git mv R087`) — VERIFIED
- SC#2 (zero stale references; bootstrap surface end-to-end) — VERIFIED across slash command, Typer CLI, MCP tool, active-source sweep (16 references across 10 files), historical `.planning/` sweep (18 files), and brand-gate enforcement (CHECK 2 + CHECK 3 green in isolation)
- SC#3 (Claude Code native `/init` reachable) — ✅ **VERIFIED via human UAT 2026-05-20** (see Human Verification Required §1 above)

Hard-cut D-04 honored throughout: no stub `init.md`, no Typer alias, no dual MCP registration. Folded todo moved to `resolved/`. Test gate green (212 passed). Brand-gate CHECK 2 + CHECK 3 implemented and proven green in isolation; full-gate failure is pre-existing BRAND-04 lattice residue (Phase 21 scope, out of scope for Phase 18 per verification target).

---

_Verified: 2026-05-19T22:00:00Z (autonomous SC#1, SC#2)_
_Verifier: Claude (gsd-verifier)_
_SC#3 UAT closed: 2026-05-20 (human verification during quick task 260520-bgd)_
