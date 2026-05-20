# Phase 18 — Discussion Log

**Date:** 2026-05-20
**Skill:** /gsd-discuss-phase 18
**Output:** `.planning/phases/18-plugin-command-rename/18-CONTEXT.md`

---

## Domain framing (presented to user)

Phase 18 domain: rename the wiki bootstrap verb from `init` to `bootstrap` (final pick) across all three user-facing surfaces so Claude Code's native `/init` is reachable.

Surface scan:
- 1 plugin file rename: `plugins/graph-wiki/commands/init.md` → new filename
- 11 active-source `/graph-wiki:init` references
- 19 historical `.planning/` references
- Pre-existing todo `2026-05-19-rename-graph-wiki-init-command-to-init-wiki.md` resolves_phase: 18

Carried forward (not re-asked):
- No backwards-compat shims — CLAUDE.md project rule + Phase 20 precedent
- `scripts/check-brand.sh` exists; Phase 21 also extends it for the `code-wiki-agent` rename

---

## Q1 — Agent-side `init` scope

**Question:** The agent-side `init` surface (CLI subcommand + MCP tool + `init_vault.py` script) shadows nothing in Claude Code — it's only the slash command that conflicts. What's the scope?

**Options presented:**
- Slash command only (recommended) — rename only `plugins/graph-wiki/commands/init.md`
- **Also rename CLI + MCP for consistency** (selected)

**User selection:** Also rename CLI + MCP for consistency.

**Notes:** Uniform vocabulary across surfaces; broader blast radius (call sites in tests + plugin shell-outs) accepted.

---

## Q2 — Historical `.planning/` sweep

**Question:** Scope of historical `.planning/` reference sweep — 19 stale `/graph-wiki:init` references in archived phase docs / milestones / discussion logs?

**Options presented:**
- **Sweep all 19 (matches Phase 21 norm)** (recommended; selected)
- Active docs only

**User selection:** Sweep all 19.

**Notes:** Matches the historical-consistency precedent set in Phase 21 D-05. Trade-off acknowledged: alters historical record but commit messages retain the old name immutably.

---

## Q3 — Brand-gate enforcement

**Question:** Should `scripts/check-brand.sh` carry an enforcement rule for `/graph-wiki:init` to prevent re-introduction?

**Options presented:**
- **Add enforcement rule** (recommended; selected)
- Skip
- Defer to Phase 21

**User selection:** Add enforcement rule in this phase.

**Notes:** Brand-gate is small enough to bundle here rather than coupling to Phase 21. Phase 21 still extends `check-brand.sh` for its own slugs — both phases just add separate grep patterns to the same script.

---

## Q4 — MCP naming follow-up

**Question:** MCP tool names use `wiki_<verb>` prefix. For `wiki_init` specifically, what's the rename target?

**Options presented:**
- Keep `wiki_init` (recommended) — MCP namespace already disambiguates
- Rename to `wiki_init_wiki` — strict parity, awkward
- **Pick a new verb for all surfaces** (selected)

**User selection:** Pick a new verb for all surfaces.

**Notes:** User accepted the bigger semantic shift to avoid `wiki_init_wiki`'s clunky duplication.

---

## Q5 — Verb selection

**Question:** Which verb replaces `init` across all three surfaces?

**Options presented:**
- **bootstrap** (recommended; selected)
- scaffold
- setup
- new

**User selection:** bootstrap.

**Notes:** Clear semantic match for "set up a wiki from scratch"; reads as deliberate action.

---

## Final outcome

CONTEXT.md written with 7 decisions (D-01 through D-07), full canonical refs (4 phase inputs, 17 source files, 3 cross-cutting refs), and 3 open questions deferred to the planner.

Ready for `/gsd-plan-phase 18`.
