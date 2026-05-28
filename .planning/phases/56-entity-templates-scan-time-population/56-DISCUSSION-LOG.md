# Phase 56: Entity Templates & Scan-Time Population - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-28
**Phase:** 56-entity-templates-scan-time-population
**Areas discussed:** Placeholder & substitution convention, summary: field source, Migration mapping & TODO convention, Legacy deletion & init_vault

---

## Placeholder & substitution convention

| Option | Description | Selected |
|--------|-------------|----------|
| {{var}} for data, <...> for TODOs | Convert data placeholders to `{{var}}`, reuse init_vault `.replace()`; reserve `<...>` for TODO instructions | ✓ |
| Keep <...>, allowlist substitution | Angle-bracket data tokens, substitute against an explicit allowlist | |
| Replace all <...>, no brackets in TODOs | Substitute every `<...>` and drop brackets from TODO markers | |

**User's choice:** {{var}} for data, <...> for TODOs
**Notes:** Resolves the literal SCAN-01 ↔ ENTITY-02 contradiction. SCAN-01 verify reinterpreted as "no unsubstituted `{{...}}` survives." `# <Package Name>` example becomes `# {{package_name}}`. Substitution runs in `_render_entity_page()` reusing the existing `init_vault` mechanism.

### Unfilled-placeholder sub-decision
| Option | Description | Selected |
|--------|-------------|----------|
| Substitute a TODO instruction | Unfilled `{{var}}` → `TODO: <add ...>` marker | ✓ |
| Substitute empty string | Render blank | |
| Omit the line/section | Drop the line driven by the missing var | |

---

## summary: field source

| Option | Description | Selected |
|--------|-------------|----------|
| Uniform attrs[description] + populate it | Read `attrs['description']` uniformly; extend graph-io to store pyproject `[project].description`; empty → TODO | ✓ |
| Read-only attrs[description], TODO fallback | Don't touch graph-io; most kinds get TODO summaries | |
| Per-kind explicit sources | Tailored source per kind | |

**User's choice:** Uniform attrs[description] + populate it
**Notes:** Makes Phase 56 cross-package (graph-io + wiki-io). Small in-scope graph-io change to populate descriptions from pyproject for packages/apps; domains already have one.

### Ownership sub-decision
| Option | Description | Selected |
|--------|-------------|----------|
| Scanner-owned (overwrite) | Add `summary` to SCANNER_OWNED_KEYS, overwrite every scan | |
| Fill-when-empty (preserve human edits) | Scanner writes only if page has no summary | ✓ |

**Notes:** Introduces a third frontmatter category (neither scanner-owned-overwrite nor human-only). Special-case in `merge_frontmatter`, NOT a plain SCANNER_OWNED_KEYS add. Verify: re-scan preserves human summary, fills empty one.

---

## Migration mapping & TODO convention

| Option | Description | Selected |
|--------|-------------|----------|
| Curated per-kind, dedup messes | Migrate meaningful sections per kind, collapse plugin/app duplication, testing → entity-test-suite | ✓ |
| Verbatim copy then prune | Copy wholesale, then remove dead links | |
| You decide during planning | Defer mapping to planner | |

**User's choice:** Curated per-kind, dedup messes
**Notes:** All testing-derived content routes to entity-test-suite.md per ENTITY-01. Drop the plugin/overview Purpose+testing duplication.

### TODO format sub-decision
| Option | Description | Selected |
|--------|-------------|----------|
| Visible line: TODO: <instructions> | Plain visible markdown line | |
| Blockquote: > TODO: <instructions> | Visible blockquote, stands out | ✓ |
| HTML comment: <!-- TODO: ... --> | Invisible in rendered page | |

**Notes:** `<...>` inside the TODO is authoring-instruction text, never scanner-substituted (only `{{...}}` is).

---

## Legacy deletion & init_vault

| Option | Description | Selected |
|--------|-------------|----------|
| Delete the obsolete tests | Remove the 4 test_overview_template_wikilinks.py tests | ✓ |
| Rewrite against entity templates | Repoint assertions at new entity templates | |
| You decide during planning | Case-by-case | |

**User's choice:** Delete the obsolete tests
**Notes:** These are the 4 pre-existing failures the Phase 54 executor flagged (FileNotFoundError), explicitly slated for removal in Phase 56.

### Dead-link verification sub-decision
| Option | Description | Selected |
|--------|-------------|----------|
| New test + repo grep | Permanent dead-link test plus execution grep | |
| Repo grep only (no new test) | Grep during execution, no standing test | ✓ |
| You decide during planning | Defer to planner | |

**Notes:** Deleting source dirs means init_vault rglob stops seeding them — no init_vault code change expected beyond confirming no other references.

---

## Claude's Discretion

- Exact `{{var}}` variable set and per-kind section lists (grounded in node data + scout analysis).
- How the graph-io description-population wires into `packages.refresh()` (coordinate with Phase 55's edits to the same function).
- Shape of optional SCAN-01 / SCAN-02 tests.

## Deferred Ideas

- Richer per-kind summary sources (deps, test-suites) — rejected for uniform attrs[description].
- Permanent dead-link regression test — deferred (grep only this phase).
- Dependency-family clustering — already in Future Requirements.
