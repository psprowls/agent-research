# Phase 26: plugin-prompt-source-mirror-sync - Context

**Gathered:** 2026-05-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Eliminate `packages/prompt-sources/` from the repository — re-point every
`Source:` provenance comment and every divergence-rubric `source_anchor=` to
the canonical surface (`plugins/graph-wiki/...`, the `workspace_io` runtime
template, or a new agent-local sources tree for Bedrock-only roles), then
delete the `packages/prompt-sources/` tree. The mirror invariant from Phase 23
PATTERNS.md D-08 ("whenever `plugins/graph-wiki/.../<X>.md` changes, the
`packages/prompt-sources/...` mirror must change in the same commit") becomes
moot — the duplicate is removed rather than kept in sync.

Out-of-scope for v1.4 (deferred to v1.5+):
- Rewriting `prompts/*.py` / `_fragments/*.py` to runtime-load markdown from
  plugin files. The static-string port stays; only its provenance anchors move.
- Eliminating the adaptive port between `plugins/graph-wiki/agents/*.md` and
  `agents/.../prompts/*.py`. That asymmetric port is the eval-harness's
  divergence eval problem; this phase only changes the anchor *target*, not
  the porting mechanism.
- Retroactive lattice-wiki upstream tracking — lattice is deprecated; the
  `SOURCE-COMMIT` file (the pinned upstream SHA) is deleted alongside the tree.

</domain>

<decisions>
## Implementation Decisions

### Direction (locked)
- **D-01:** `packages/prompt-sources/` is deleted at phase close. `plugins/graph-wiki/`
  is the canonical surface for everything the plugin already covers
  (`agents/{ingestor,librarian,linter,scanner}.md`, `skills/graph-wiki/SKILL.md`,
  `skills/graph-wiki/references/*.md`).
- **D-02:** The `exclude = ["packages/prompt-sources"]` entry in root `pyproject.toml`
  is removed in the same commit that deletes the directory. No workspace-state
  remnants.

### Anchor reconciliation
- **D-03:** Anchor slug rule — re-point every `#section` anchor to the GitHub-slug
  of the current plugin heading. No custom slugs. No HTML `<a id=…>` markers
  added to plugin .md to preserve old slug strings. Mechanical translation
  only.
  - Example: `agents/ingestor.md#workflow-step-4` →
    `plugins/graph-wiki/agents/ingestor.md#4-write-the-source-summary`
    (slug of `### 4. Write the source summary`).
- **D-04:** Missing-content policy — when a current `source_anchor=` refers to a
  section that no longer exists in the plugin .md (genuine content removal, not
  a heading rename), the planner produces an audit table in PLAN.md listing each
  unresolvable anchor with three columns: `current anchor`, `plugin file state`,
  `proposed resolution` (one of: re-point to a different section, restore the
  dropped section to plugin .md, or drop the check). Each row is decided
  individually. Blanket policy rejected because some rubric anchors may be
  load-bearing semantic checks worth preserving by restoring content to plugin.
- **D-05:** Line-range pins (`(L48-L56)`, `(L93-L101)`) in `Source:` comments are
  **dropped**. Section names are stable; line numbers churn on every plugin
  edit. New comment shape:
  `# Source: plugins/graph-wiki/agents/linter.md §Pass 2, §Rules`.

### Agent-only prompt sources (no plugin counterpart)
- **D-06:** New agent-local sources tree created at
  `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/sources/`. It mirrors
  the plugin/agents/ shape and houses role specs for Bedrock-only roles that
  Claude Code does not dispatch.
  - `agents/.../prompts/sources/code_reader.md` ← content of
    `packages/prompt-sources/agents/code_reader.md` (verbatim, with rebrand
    sweep if any `lattice` strings remain).
  - `agents/.../prompts/sources/synthesizer.md` ← content of
    `packages/prompt-sources/agents/synthesizer.md` (verbatim, with rebrand
    sweep).
- **D-07:** `LOG_FORMAT` and `STYLE_RULES` in `_fragments/{log_format,style_rules}.py`
  re-anchor to `packages/workspace-io/src/workspace_io/assets/CLAUDE.md.template`.
  That asset IS the canonical source — it's what `render_workspace_claude_md`
  writes into every fresh workspace's `<workspace>/CLAUDE.md`. The new comment
  shape:
  `# Source: packages/workspace-io/src/workspace_io/assets/CLAUDE.md.template §Log format`.
  If the template asset's heading structure differs from the cited sections,
  the planner reconciles via D-04 (audit row per discrepancy).

### Test-provenance strength
- **D-08:** `agents/graph-wiki-agent/tests/prompts/test_provenance.py` is upgraded
  in this phase, not just migrated. After the migration, three checks per
  `Source:` comment:
  1. **Whitelist:** path starts with exactly one of:
     - `plugins/graph-wiki/`
     - `packages/workspace-io/src/workspace_io/assets/CLAUDE.md.template`
       (the only file allowed under `packages/workspace-io/` as a source)
     - `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/sources/`
     Any other prefix fails.
  2. **Resolution:** the referenced file exists; the cited section heading
     exists (GitHub-slug match against `^#+ ` headings in the file).
  3. **Semantic drift:** keyword-overlap threshold check. Extract code
     identifiers + capitalized noun phrases from the cited section; assert
     ≥70% of those tokens appear (case-insensitive) somewhere in the
     Python string constant that the `Source:` comment belongs to.
     Starting threshold 70% — tune-down allowed in the implementing plan if
     false-positives surface; tune-up not in this phase.
- **D-09:** When `test_provenance.py` runs against the migrated tree, no new
  failures may be silently downgraded. If the semantic check trips on a
  fragment that's a faithful port, the fix is to widen the fragment's keyword
  pool (the canonical citation), not to relax the threshold.

### Brand-gate
- **D-10:** New CHECK block added to `scripts/check-brand.sh` (numbered
  sequentially after the highest existing CHECK — `CHECK 5` if 4 is the
  current ceiling; planner verifies at planning time). Block shape mirrors
  Phase 18's CHECK 2 — a standalone block with its own grep + comment header.
  No extension of CHECK 1's alternation regex.
- **D-11:** Pattern blocked: literal string `packages/prompt-sources` anywhere
  under `agents/`, `packages/`, `plugins/`, `scripts/`, and `tests/` paths.
  `.planning/` archived docs (milestones/, retrospectives/, phase histories)
  are NOT swept — those are historical record. Allowlist entries added to
  `.brand-grep-allow` if any in-scope file legitimately needs to mention the
  string (e.g., the brand-gate itself, a release-notes entry explaining the
  rename).
- **D-12:** No extra coverage for the Python module name `prompt_sources` (the
  dir was excluded from the uv workspace; no `prompt_sources` import path ever
  existed). If a future module accidentally introduces one, the path-level
  block in D-11 catches it via file location.

### Sequencing and commit shape
- **D-13:** The phase splits into ordered milestones the planner is free to
  shape into one or more plans, but the ordering is locked:
  1. **Audit** — produce the unresolvable-anchor table (D-04) by walking every
     current `source_anchor=` and `Source:` comment, attempting GitHub-slug
     resolution against the proposed new target, and listing every miss.
     This audit becomes the planning input for milestones 2-3.
  2. **Re-anchor** — apply the audit decisions; re-point every comment and
     `source_anchor=` literal; rebrand any `lattice` strings encountered in
     the content being migrated to `agents/.../prompts/sources/`.
  3. **Test upgrade** — update `test_provenance.py` to D-08 semantics; iterate
     until green against the re-anchored tree.
  4. **Delete + gate** — `git rm -r packages/prompt-sources/`; remove the
     `exclude` line from root `pyproject.toml`; add the brand-gate CHECK block;
     run the full test suite + brand-gate against the resulting tree.

### Claude's Discretion
- Where to place the agent-local sources tree's `__init__.py` (if any) — this
  is a markdown-only tree; the planner may decide whether to add an empty
  `__init__.py` for tooling reasons or leave it as pure assets.
- Exact wording of CHECK 5's grep header comment and the `.brand-grep-allow`
  entry rationale strings.
- Whether to compute the unresolvable-anchor audit (D-04) as a one-off
  scratchpad in the phase dir, or commit the table into PLAN.md / a
  PATTERNS.md companion. Either works; the planner picks.
- Specific keyword-extraction heuristic for the semantic check (D-08 step 3) —
  regex set + stoplist. Pin to "code identifiers + capitalized phrases ≥3
  chars" as the working definition; planner may refine if a more accurate
  signal is needed.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### v1.4 milestone integration audit (the trigger for this phase)
- `.planning/v1.4-MILESTONE-INTEGRATION.md` §"BLOCKER: detection-workflow.md
  prompt-source mirror not updated (Phase 25)" — the audit that named the
  specific drift this phase resolves; documents the original mirror invariant
  from Phase 23 PATTERNS D-08.

### Phase 23 / Phase 25 — prior mirror-pattern context
- `.planning/phases/23-workspace-api-external-rename/23-PATTERNS.md`
  §"Plugin-doc ↔ Prompt-source mirror pattern" — original invariant
  statement ("whenever a `plugins/graph-wiki/skills/graph-wiki/references/<X>.md`
  file changes, the corresponding `packages/prompt-sources/references/<X>.md`
  mirror must change in the same commit"). This phase deletes the invariant
  by removing the second tree.
- `.planning/phases/25-packages-dir-misclassification-fix/25-CONTEXT.md` — the
  phase whose `detection-workflow.md` edit violated the invariant.

### Current anchor inventory (must read before audit)
- `agents/graph-wiki-agent/tests/prompts/test_provenance.py` — current test
  shape; defines what `Source:` comment formats are recognized today.
- `packages/eval-harness/src/eval_harness/divergence/{ingestor,librarian,linter,
  scanner,synthesizer,code_reader}.py` — every `source_anchor=` literal that
  must be re-pointed.
- `packages/eval-harness/src/eval_harness/divergence/rubrics/{ingestor,librarian,
  linter,scanner,synthesizer,code_reader}.md` — `<!-- Source: -->` and
  `<!-- Anchor: -->` headers also need migration. These rubrics also carry
  `<!-- Source-commit: -->` lines with the lattice SHA — those drop too.
- `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/*.py` and
  `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/_fragments/*.py` —
  every `# Source:` comment.

### Re-point destinations
- `plugins/graph-wiki/agents/{ingestor,librarian,linter,scanner}.md` — plugin
  sub-agent role specs. Re-point target for `agents/<role>.md` anchors
  (excluding code_reader and synthesizer).
- `plugins/graph-wiki/skills/graph-wiki/SKILL.md` — plugin skill spec. Re-point
  target for `SKILL.md` anchors (`#iron-rules`, `#page-categories`).
- `plugins/graph-wiki/skills/graph-wiki/references/*.md` — plugin reference
  workflows. Currently no `source_anchor=` references these, but the test
  whitelist must permit them in case future fragments anchor here.
- `packages/workspace-io/src/workspace_io/assets/CLAUDE.md.template` — re-point
  target for `wiki-claude-md-template.md` anchors (`#log-format`, `#style`).
- `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/sources/{code_reader,
  synthesizer}.md` — NEW files; created in this phase by porting content from
  the deleted prompt-sources copies.

### Brand-gate prior art
- `scripts/check-brand.sh` — existing CHECK 1-4 structure; D-10 adds CHECK 5
  modeled on Phase 18's CHECK 2 block shape.
- `.brand-grep-allow` — existing allowlist with per-entry rationale comments
  (Phase 21 pattern).

### Workflow rules
- `CLAUDE.md` §Conventions — no specific rules apply yet (Conventions section
  is empty); the planner follows established v1.4 patterns from Phases 22-25.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`scripts/check-brand.sh` CHECK 2/3/4 pattern** — each prior phase that
  added a brand-gate did so as a self-contained block with a header comment,
  a grep invocation, and an exit-on-match. CHECK 5 follows the same shape.
- **`.brand-grep-allow` entry pattern** — Phase 21 introduced per-entry
  rationale comments; reuse that convention for any allowlisted
  `packages/prompt-sources` mention.
- **`test_provenance.py` heading-extraction logic** — already parses
  markdown headings from a file and matches `#section` slugs. The semantic
  upgrade (D-08 step 3) extends this with a keyword-extraction pass.
- **`render_workspace_claude_md` template-driven render** — confirms that
  `CLAUDE.md.template` is the live runtime artifact, not a static doc;
  re-anchoring `LOG_FORMAT`/`STYLE_RULES` to it preserves the "Source: points
  at the runtime asset" property.

### Established Patterns
- **Mechanical-sweep phase shape (Phases 22-25)** — discovery → uniform
  rename across all sites → test update → brand-gate addition → verification.
  Phase 26 follows this shape; only the discovery substep (audit table)
  has phase-specific shape.
- **Hard cut, no compat** — every v1.4 phase removed the old surface in the
  same commit that added the new one. Phase 26 deletes `prompt-sources/`
  in the same commit that re-anchors. No deprecation period.
- **Audit table → decisions → execute** — Phase 23 used PATTERNS.md tables
  to map every file by role and analog. The unresolvable-anchor audit (D-04)
  is the same pattern.

### Integration Points
- Test suite — `agents/graph-wiki-agent/tests/prompts/test_provenance.py` is
  the primary verification gate. Must be green before the deletion step.
- Eval harness — divergence rubrics live in `packages/eval-harness/`. Their
  `source_anchor=` strings are passive metadata (judge LLM context), not
  runtime references; re-pointing is safe but warrants a `uv run --package
  eval-harness pytest` pass for confidence.
- Brand-gate — `scripts/check-brand.sh` runs in CI (per prior phase
  conventions); CHECK 5 must pass against the post-migration tree.
- Root `pyproject.toml` — `exclude = ["packages/prompt-sources"]` removal
  is a uv-workspace boundary change; `uv sync` must remain green after
  deletion.

</code_context>

<specifics>
## Specific Ideas

- Pat is the lattice-wiki author and made the strategic call to delete
  `prompt-sources/` outright on the grounds that "lattice-wiki is fully
  deprecated and all new development will happen in this repo" — the
  upstream-snapshot role is gone, and the tree's remaining role
  (test-time + eval-time anchor) can be served by pointing at the plugin
  directly.
- The detection-workflow.md drift named in `.planning/v1.4-MILESTONE-INTEGRATION.md`
  is automatically resolved by deletion — there's no second copy to fall
  out of sync with.
- 14 of 15 mirror pairs were already drifted at phase start (`scan-workflow.md`
  was the only IDENTICAL pair). Repairing in place would have been a
  multi-commit sweep against a brittle invariant. Deletion is the smaller
  change in lines-touched and the larger change in maintainability.

</specifics>

<deferred>
## Deferred Ideas

- **Runtime-load of plugin markdown by `prompts/*.py`** (option C from the
  scope discussion). Would eliminate the static Python port as a drift
  source, but requires designing the "adaptation layer" that today is
  expressed as hand-edited Python prose. Defer to v1.5+.
- **Buffer/sync enforcement** (option B from the scope discussion). If the
  collapse direction turns out to be wrong (e.g., plugin layout churns hard
  in v1.5+), reintroducing a generated mirror remains an option. Not in
  scope for this phase.
- **Plugin-side content audit** — some `plugins/graph-wiki/skills/graph-wiki/
  references/*.md` files have likely accumulated edits since the original
  port (the diff sweep showed 9/10 references files drifted). After Phase 26
  the plugin is canonical, so the planner does NOT audit plugin content;
  whatever's in plugin is the spec. A separate v1.5+ phase could review
  plugin content for correctness if Pat decides it's worth the effort.
- **Eval-harness regression coverage for the semantic drift check (D-08
  step 3)** — once the keyword-overlap heuristic ships, a benchmark dataset
  showing it catches real drift (and doesn't false-positive on faithful
  ports) would harden the gate. Out of scope here; ships its own phase if
  Pat wants the measurement.

</deferred>

---

*Phase: 26-plugin-prompt-source-mirror-sync*
*Context gathered: 2026-05-21*
</content>
</invoke>