# Phase 26 Plan 02 — Deferred Items

Items discovered out of scope of Plan 02's three tasks. Each is logged here rather
than auto-fixed because it falls outside the task `<files>` lists.

## 1. `agents/graph-wiki-agent/tests/prompts/test_provenance.py`

References `packages/prompt-sources/` in `PROMPT_SOURCES_DIR` and the legacy regex.

**Handled by:** Plan 03 (test_provenance.py rewrite per D-08).

## 2. `packages/eval-harness/tests/fixtures/post-rebrand-vault/`

Vault-content fixtures simulating a "post-rebrand" snapshot for the librarian eval
harness. Contains:
- `index.md` L17 — wikilink `[[wiki/packages/prompt-sources/prompt-sources]]`
- `packages/prompt-sources/prompt-sources.md` — entire fixture page describing the
  prompt-sources package
- `packages/eval-harness/eval-harness.md` L33 — wikilink to the above

**Status:** Fixture content, not source code anchors. The vault simulates a
recorded historical wiki state. Whether to refresh the fixture (re-record vault
content) is a Plan 04 (deletion phase) concern, not an anchor-re-pointing concern.
Plan 02's task scopes (`agents/.../prompts/`, `packages/eval-harness/src/.../divergence/`,
`packages/workspace-io/.../CLAUDE.md.template`) do not include test fixtures.

**Recommendation:** evaluate at Plan 04 deletion time whether the fixture needs
re-recording or whether the wikilinks can stay as historical-vault references.
