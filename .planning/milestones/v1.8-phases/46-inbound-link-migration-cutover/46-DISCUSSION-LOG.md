# Phase 46: Inbound-Link Migration + Cutover - Discussion Log

**Date:** 2026-05-27
**Phase:** 46 — Inbound-Link Migration + Cutover

This log captures the conversation that produced `46-CONTEXT.md`. For audit / retrospective use only — not consumed by downstream agents.

---

## Pre-discussion analysis surfaced a conflict

Phase 43 CONTEXT.md states: "the cutover phase will NOT remove `wiki/package-family/` in v1.8 (no entity pages exist to replace it)."

ROADMAP Phase 46 SC#4 explicitly lists `wiki/package-family/` among directories removed.

These are mutually incompatible. Elevated to the user as Area 3.

## Gray Area Selection

User selected all four offered areas:

1. Rewriter strategy: regex-with-code-mask vs Markdown tokenizer
2. Old-layout → new-slug mapping derivation
3. Phase 43/46 conflict: `wiki/package-family/` removal
4. Cutover scope + curated lanes covered + idempotency marker

---

## Area 1: Rewriter strategy

**Question:** How does `link_rewriter.py` skip wikilinks inside code regions?

**Options presented:**
1. Regex with position-aware code-region masking  ← chosen
2. markdown-it-py tokenizer
3. Hand-rolled line-by-line tokenizer

**User chose:** Option 1 — regex with position-aware code-region masking. Reuses tested `FENCED_CODE_RE`/`INLINE_CODE_RE`/`WIKILINK_RE` from `lint/common.py`. No new deps.

→ Captured as D-01, D-02 (edge-case fixture suite).

---

## Area 2: Old-layout → new-slug mapping derivation

**Question:** How is each entity's 'old layout path' determined for the rewrite mapping?

**Options presented:**
1. Convention-only: kind → path template
2. Scan-and-match: walk old dirs, match to graph by name
3. Both — convention + scan + grep over curated lanes  ← chosen (recommended)

**User chose:** Option 3 — three-source pipeline. Unresolvable targets logged but not silently dropped.

→ Captured as D-03 (three-source build_rewrite_table), D-04 (package_family handling in mapping).

---

## Area 3: `wiki/package-family/` removal conflict

**Question:** What happens to `wiki/package-family/` in the Phase 46 cutover?

**Options presented:**
1. Don't remove in v1.8; update ROADMAP SC#4
2. Remove only if empty / scanner-generated-only
3. Remove unconditionally per ROADMAP  ← chosen

**User chose:** Option 3 — unconditional removal per ROADMAP SC#4. Phase 43's "do not remove" note is overridden. Recoverable via git history if curated content existed.

→ Captured as D-05 in `<decisions>`; explicitly noted in `<domain>` as "Phase 43 override" and in `<canonical_refs>` as "Phase 43 D-07 is OVERRIDDEN by Phase 46 D-05."

Side benefit: D-12's dry-run output explicitly surfaces "human content detected" warnings on `wiki/package-family/` files so the user sees what they're losing before the commit lands.

---

## Area 4: Cutover scope (3 sub-questions)

**Q1 — Which curated lanes get wikilink rewrites?**

Options:
1. All five: concepts, adrs, architecture, sources, work  ← chosen
2. Only the three named in ROADMAP: concepts, adrs, architecture
3. Three named + sources (skip work)

**User chose:** Option 1 — all 5 curated lanes. ROADMAP SC#1's omission of sources/work treated as oversight. Phase 46 plan includes a ROADMAP edit task.

→ Captured as D-13.

**Q2 — Where does the idempotency marker live?**

Options:
1. `.graph-wiki/manifest.json`  ← chosen
2. Top of `wiki/index.md` frontmatter
3. Dedicated `.graph-wiki/migrations.json` log

**User chose:** Option 1 — `.graph-wiki/manifest.json`. JSON, hidden state directory alongside `scan.lock` + `deletions.log`.

→ Captured as D-08, D-09, D-10 (idempotency check, --force semantics).

**Q3 — Dry-run / preview mode?**

Options:
1. Yes — `--dry-run` shows planned changes, no writes  ← chosen
2. No dry-run; atomic commit only

**User chose:** Option 1. Dry-run REQUIRED before the destructive cutover.

→ Captured as D-11, D-12 (output format).

---

## Notable Cross-Phase Consequences

- **Phase 43 D-07 override.** Phase 43 CONTEXT.md's "Phase 46 will NOT remove wiki/package-family/" is reversed by Phase 46 D-05. Phase 43 CONTEXT.md is not edited (immutable history); the override is recorded in Phase 46 `<domain>` and `<canonical_refs>`.
- **Phase 45 D-02 still binds.** Phase 45's "update_index.py survives, per-folder sub-indexes survive" remains the policy. Phase 46 does NOT delete `update_index.py`. Phase 46's cutover commit calls `update_index.update_index(wiki_root)` (post-Phase-45 surgical form) to regenerate per-folder sub-indexes.
- **ROADMAP edits in Phase 46 plan.** SC#1 needs amendment (add sources/work). SC#4 stays as-is (lists wiki/package-family/ — kept per D-05). REQUIREMENTS MIGRATION-05 cutover composition may need a small clarification per D-06.

---

## Deferred Ideas

Captured in `46-CONTEXT.md` `<deferred>` section. Key items:

- markdown-it-py tokenizer — re-evaluate if regex hits a regression.
- Package-family v1.9 ingestion (with potential re-creation of curated content from git history).
- Plugin (`plugins/graph-wiki/`) migration to entity layout — post-v1.8.
- `--dry-run --verbose` per-file diff mode — v1.9 polish.
- Atomic rollback wrapper (`cg migrate-vault --rollback`) — git revert suffices in v1.8.

---

## Claude's Discretion

Items left to the planner's judgment (documented in `<decisions>` Claude's discretion block):

- Exact CLI command name (`cg migrate-vault` vs alternatives).
- Cutover script location (lean: `agents/graph-wiki-agent/commands/migrate_vault.py`).
- `--dry-run` output formatting / coloration (lean: plain text).
- Whether to subprocess `git rm -r` or use a wrapper (lean: subprocess).
- Indented-code-block detection regex specifics (lean: CommonMark 4-space rule).
- `--no-write-marker` test-only flag (lean: yes).
- Whether to expose a public `rewrite_text(text, table) -> text` helper alongside `rewrite_vault` (lean: yes).

---

*Discussion concluded: 2026-05-27*
