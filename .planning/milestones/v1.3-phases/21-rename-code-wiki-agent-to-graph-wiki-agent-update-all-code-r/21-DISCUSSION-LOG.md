# Phase 21: Rename code-wiki-agent to graph-wiki-agent - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-19
**Phase:** 21-rename-code-wiki-agent-to-graph-wiki-agent-update-all-code-r
**Areas discussed:** Rename surface, Boundary: what counts as 'code', Cutover strategy, Enforcement gate

---

## Rename surface

### Q1: How deep does the rename go?

| Option | Description | Selected |
|--------|-------------|----------|
| Full rename: dir + Python pkgs + console scripts | agents/, src/code_wiki_agent/, src/code_wiki_mcp/, console scripts all renamed | ✓ |
| Pkg name + console scripts only (keep dirs) | Minimal churn, ugly mismatch | |
| Dir + Python pkgs only (keep console scripts) | Avoids breaking plugin shell-out; confusing brand split | |

**User's choice:** Full rename.

### Q2: How should the test directory be handled?

| Option | Description | Selected |
|--------|-------------|----------|
| Move with package + update imports | Tests move to graph-wiki-agent/tests/, imports updated; filenames likely don't embed old slug | |
| Move + rename test files referencing old pkg in name | Same plus rename any test files literally embedding old slug | ✓ |

**User's choice:** Move + rename test files referencing old pkg in name (planner verifies via find before locking).

### Q3: How should internal symbols/identifiers be handled?

| Option | Description | Selected |
|--------|-------------|----------|
| Rename only what the package rename forces | Module-qualified imports + `CodeWiki`-prefixed classes; leave unrelated strings | |
| Full sweep including strings + log messages | Update all string literals in prints/logs/help text/errors | ✓ |
| Imports + user-facing strings, leave class names alone | Compromise; keeps internal class names | |

**User's choice:** Full sweep including strings + log messages.

### Q4: Trace directory `.code-wiki/traces/` — rename?

| Option | Description | Selected |
|--------|-------------|----------|
| Rename to `.graph-wiki/traces/` | Consistent with package brand; existing local traces orphan (ephemeral) | ✓ |
| Keep `.code-wiki/traces/` | Avoids invalidating local history; brand inconsistency | |
| You decide | Defer to planner | |

**User's choice:** Rename to `.graph-wiki/traces/`.

---

## Boundary: what counts as 'code'

### Q1: `.planning/` docs — which get touched?

| Option | Description | Selected |
|--------|-------------|----------|
| Active docs only | STATE.md, PROJECT.md current state, ROADMAP.md, REQUIREMENTS.md, CLAUDE.md, intel/stack.json | |
| Everything in .planning/ | Sweep all 188 files including historical phase docs / archives | ✓ |
| Nothing in .planning/ | Code-only sweep; PROJECT.md ends up inconsistent | |

**User's choice:** Everything in .planning/ — full historical consistency over preserved historical record. User overrode the default recommendation.

### Q2: Wiki content scope — confirm phase boundary

| Option | Description | Selected |
|--------|-------------|----------|
| Skip wiki content entirely | Don't touch `graph-wiki/wiki/agents/code-wiki-agent/*.md`; refresh via `/graph-wiki:scan` later | ✓ |
| Also rename wiki dir + scrub companion pages | Larger blast radius; risks divergence with future scans | |
| Rename dir only, leave .md contents | Compromise | |

**User's choice:** Skip wiki content entirely.

### Q3: Spike findings skill — update?

| Option | Description | Selected |
|--------|-------------|----------|
| Update SKILL.md + active refs; leave raw spike sources | Active index updated; historical spike sources preserved | ✓ |
| Update everything in spike-findings/ | Full sweep erases historical context of spike runs | |
| Leave spike-findings/ untouched | Active SKILL.md becomes out of sync | |

**User's choice:** Update SKILL.md + active references; leave raw spike sources.

---

## Cutover strategy

### Q1: Commit shape for the rename?

| Option | Description | Selected |
|--------|-------------|----------|
| Staged commits per layer | 5 commits: `git mv` → pkg name/scripts → import sweep → plugin/tests → docs/planning | ✓ |
| Single atomic commit | One giant commit; harder to review; pre-commit risks | |
| Two commits: code + docs | Compromise granularity | |

**User's choice:** Staged commits + work in a git worktree (notes added directly by user).

### Q2: Backwards-compat shim for the old console script?

| Option | Description | Selected |
|--------|-------------|----------|
| Hard cut, no shim | Aligns with CLAUDE.md anti-backwards-compat guideline + Phase 20 precedent | ✓ |
| Console-script alias kept for one milestone | Adds deprecation print, removed at v1.4 | |
| Print-and-exit stub | Discoverable error without aliasing behavior | |

**User's choice:** Hard cut, no shim.

### Q3: Per-commit gate?

| Option | Description | Selected |
|--------|-------------|----------|
| `uv sync` + pytest unit on each commit | Cheap, fast; catches import errors and gross breakage | ✓ |
| Full pytest including integration on final commit only | Cheaper intermediate; one live-Bedrock smoke at end | |
| `uv sync` only on intermediate, pytest on final | Fastest; risks broken intermediate in history | |

**User's choice:** `uv sync` + pytest unit on each commit.

---

## Enforcement gate

### Q1: Add an enforcement gate to prevent regression?

| Option | Description | Selected |
|--------|-------------|----------|
| Add gate, mirror Phase 12 brand pattern | New `scripts/check-old-name.sh` + own allowlist | |
| Extend existing `check-brand.sh`, share `.brand-grep-allow` | Single gate, single allowlist file — cleaner | ✓ |
| No ongoing gate | One-time rename; rely on review | |

**User's choice:** Extend existing `check-brand.sh`, share `.brand-grep-allow`.

### Q2: Allowlist entries — what historical references stay grep-allowed?

| Option | Description | Selected |
|--------|-------------|----------|
| Historical .planning archives + git commit refs | Tight allowlist because the full `.planning/` sweep eliminates most refs | ✓ |
| All .planning/milestones/ archives + spike sources | Grandfather everything pre-rename | |
| You decide | Planner picks after running grep | |

**User's choice:** Historical .planning archives + git commit refs only — keep allowlist tight.

---

## Claude's Discretion

- Concrete commit messages and SHA-stable ordering inside the 5 staged-commit layers.
- Whether to add a temporary `conftest.py` adjustment if test discovery breaks mid-rename.
- Exact word-boundary regex for the `check-brand.sh` extension.

## Deferred Ideas

- Wiki vault rescan post-rename (`/graph-wiki:scan` to refresh companion pages) — follow-up task or v1.4 wiki refresh.
- MCP host configuration updates outside the repo (DA-CLI / Claude Code configs) — user manages own host configs.
- Backwards-compat console-script alias as deprecation aid — explicitly rejected; revisit only if external consumers found (unlikely).
