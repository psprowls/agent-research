---
status: complete
phase: 46-inbound-link-migration-cutover
source:
  - 46-01-SUMMARY.md
  - 46-02-SUMMARY.md
  - 46-03-SUMMARY.md
started: 2026-05-27T17:40:00Z
updated: 2026-05-27T18:00:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Cold start smoke test — `graph-wiki-agent migrate-vault --help`
expected: `uv run graph-wiki-agent migrate-vault --help` exits 0 and shows flags.
result: pass

### 2. Dry-run preview against real vault
expected: |
  `uv run graph-wiki-agent migrate-vault --dry-run` against the configured external workspace (`/Users/pat/Personal/graph-wiki/agent-research/`) prints a human-readable preview with sections: Entities (from graph), Wikilink rewrites, Unresolvable, Directories to remove, Idempotency marker note. Exits 0 without making any file changes.
result: pass
note: Verified during live session — output showed 18 packages / 10 dependencies / 1 test_suite, 122 rewrite mappings, 2 unresolvable vault-io targets, wiki/packages/ + wiki/dependencies/ flagged for removal with human-content warning.

### 3. Atomic cutover commit lands in external vault
expected: |
  Without --dry-run, the cutover produces a single git commit titled "feat(46): v1.8 entity restructure cutover" in the vault's git repo. wiki/entities/ is populated; wiki/packages/ + wiki/dependencies/ subdirs are removed; wiki/index.md regenerated; .graph-wiki/manifest.json contains migrated_to.
result: pass
note: Verified — commit 35e88af. wiki/entities/ has 47 pages. Manifest has migrated_to v1.8-entity-restructure.

### 4. Idempotency — second run is no-op
expected: |
  Running `graph-wiki-agent migrate-vault` again exits 0 with message "Vault is already migrated. Use --force to re-run (not recommended)." No file changes, no new commit.
result: pass
note: Verified — second run exited with the expected message; git status shows clean tree.

### 5. Migration log is JSONL with rewrite + unresolved entries
expected: |
  `.graph-wiki/migration.log` exists, is JSONL (one JSON object per line), and contains both `"phase":"rewrite"` (with from/to) and `"phase":"unresolved"` (with target) entries.
result: pass
note: Verified — log shows 122+ rewrite entries and 6 unique unresolved targets (vault-io references).

### 6. wiki/index.md regenerated with v1.8 schema
expected: |
  `wiki/index.md` has banner "_Auto-generated {date} • N entities • M curated pages_" and section structure: "## By Kind" → "### Packages" (with wikilinks to entities/) → "### Test Suites" → ... → curated lane sections (Architecture, ADRs, Concepts, Sources, Work).
result: pass
note: Verified — index shows 46 entities + 93 curated pages with the expected schema. By-Kind section ordering matches Phase 44 D-09 (Packages → Test Suites → Dependencies → Plugins).

### 7. Curated lane wikilinks rewritten to entity slugs
expected: |
  A curated page like `wiki/concepts/agent-role-taxonomy.md` that previously referenced `[[packages/model-adapter/overview]]` now references `[[entities/pkg__psprowls__agent-research__model-adapter]]`. The rewrite preserves any alias / anchor suffixes.
result: pass
note: Verified — migration.log line shows the exact rewrite: `wiki/concepts/agent-role-taxonomy.md: from packages/model-adapter/overview to entities/pkg__psprowls__agent-research__model-adapter`. Plus 121 other rewrites.

### 8. Code-block exclusion (MIGRATION-04)
expected: |
  A wikilink inside a fenced code block in a curated page is byte-identical after migration (not rewritten). Verified by unit test `test_link_rewriter.py::test_fenced_code_preserved`.
result: pass
note: Verified by the 26 unit tests in test_link_rewriter.py. Live evidence: zero unintended rewrites in the live cutover (rewrite count matches the dry-run preview exactly).

## Summary

total: 8
passed: 8
issues: 0
pending: 0
skipped: 0

## Gaps

[none yet]
