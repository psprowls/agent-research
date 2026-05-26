---
phase: 260521-gc0
plan: 01
status: complete
subsystem: wiki-lint-and-config
tags: [quick, lint, workspace-io, wiki-io, tdd]
dependency_graph:
  requires: []
  provides:
    - W1-repo-discovery
    - W5-pathqual-wikilinks
    - F1-schema-file-exclusion
    - F2-tokens-null-on-unsupported
  affects:
    - packages/workspace-io/src/workspace_io/config.py
    - packages/wiki-io/src/wiki_io/lint_wiki.py
    - packages/wiki-io/src/wiki_io/update_tokens.py
    - packages/wiki-io/src/wiki_io/layout_io.py
    - packages/wiki-io/src/wiki_io/assets/page-templates/package/overview.md
    - packages/wiki-io/src/wiki_io/assets/page-templates/domain/overview.md
tech_stack:
  added: []
  patterns:
    - "ClientError narrow predicate (code + message) for distinguishing Bedrock unsupported-model errors"
    - "Workspace-manifest override of git-discovery (repo-directory: key)"
    - "Path-qualified wikilinks with display aliases ([[path|alias]])"
key_files:
  created:
    - packages/wiki-io/tests/test_overview_template_wikilinks.py
  modified:
    - packages/workspace-io/src/workspace_io/config.py
    - packages/workspace-io/tests/test_config.py
    - packages/wiki-io/src/wiki_io/lint_wiki.py
    - packages/wiki-io/src/wiki_io/update_tokens.py
    - packages/wiki-io/src/wiki_io/layout_io.py
    - packages/wiki-io/src/wiki_io/assets/page-templates/package/overview.md
    - packages/wiki-io/src/wiki_io/assets/page-templates/domain/overview.md
    - packages/wiki-io/tests/test_lint_wiki.py
    - packages/wiki-io/tests/test_update_tokens.py
decisions:
  - "F1 exclusion is any-depth (forward-compatible): SCHEMA_FILENAMES set checked against rel.name regardless of parent path"
  - "F2 unsupported-model predicate matches both the ValidationException code AND the message substring 'count tokens' — strict enough to not catch legitimate malformed-request ValidationExceptions, loose enough to survive minor wording changes by AWS"
  - "tokens: null idempotency uses key-presence check, not just `.get()` value, so 'no tokens key' still gets stamped null while 'tokens: null already set' returns unchanged"
  - "W1 layering: .graph-wiki.local.yaml overrides .graph-wiki.yaml (local wins) — same precedence pattern as the existing workspace-directory key"
metrics:
  duration: "~25 min"
  completed: "2026-05-21"
  tasks_completed: 5
  tests_added: 13
---

# Quick 260521-gc0: Tackle four lint-driven fixes (W1 repo-discovery, W5 path-qualified wikilinks, F1 schema-file exclusion, F2 tokens-null) — Summary

Four independent lint-finding defects in wiki-io/workspace-io fixed via TDD: workspace-manifest `repo-directory:` overrides git-discovery; package/domain overview templates emit path-qualified wikilinks; lint_wiki skips CLAUDE.md/AGENTS.md schema files at any depth; update_tokens writes `tokens: null` when Bedrock CountTokens rejects the model.

## What changed

| Task | Defect | Files | Tests |
|------|--------|-------|-------|
| 1 | W1: env-var and discovery branches now consult `repo-directory:` in `<workspace>/.graph-wiki.yaml` layered with `.graph-wiki.local.yaml` | `workspace_io/config.py` | 6 new |
| 2 | W5: package overview template emits `[[packages/{{PACKAGE_SLUG}}/<sub>|<sub>]]`; domain overview emits `[[domains/{{DOMAIN_SLUG}}/details|details]]` | 2 templates + `layout_io.ensure_domain_page` (substitutes `{{DOMAIN_SLUG}}` from `domain_dir.name`) | 2 new |
| 3 | F1: `lint_wiki.scan()` skips `CLAUDE.md` and `AGENTS.md` at any depth in both the page-enumeration loop and the index-link parser | `lint_wiki.py` | 3 new |
| 4 | F2: unsupported-model `ValidationException` produces `tokens: null` (idempotent on re-run); legit `0` preserved as `tokens: 0`; other errors keep existing `("skipped", 0)` | `update_tokens.py` | 4 new |
| 5 | Final verification gate — full pytest suite green | — | — |

## Verification

```bash
uv run pytest packages/wiki-io/ packages/workspace-io/ -x
# 191 passed, 1 skipped in 40.31s
# (skip = pre-existing GRAPH_WIKI_RUN_INTEGRATION-gated live-Bedrock test)
```

All plan-verification greps pass:
- `repo-directory` appears in `config.py` (constant, helper, docstring, env-var-branch comment).
- `SCHEMA_FILENAMES` defined and applied in both enumeration loops in `lint_wiki.py`.
- `tokens: null` / `count = None` / `count is None` branches present in `update_tokens.py`.
- No bare `[[api]]` / `[[patterns]]` / `[[work]]` / `[[context]]` / `[[details]]` in the two overview templates.

## Decisions

### F1: "any-depth" schema-file exclusion (recorded in must_haves)

`SCHEMA_FILENAMES = {"CLAUDE.md", "AGENTS.md"}` is matched against `rel.name` regardless of how deep the file is under the workspace. Today only `wiki/CLAUDE.md` and `wiki/AGENTS.md` exist; if a future workflow ever introduces per-package schema files (`wiki/packages/foo/CLAUDE.md`), they will be excluded too — matching the spirit of "wiki content pages only".

### F2: ValidationException predicate uses code + message conjunction

`_is_unsupported_model_error(exc)` returns True iff:
1. `isinstance(exc, ClientError)`
2. `exc.response["Error"]["Code"] == "ValidationException"`
3. `"count tokens" in exc.response["Error"]["Message"].lower()`

Code-only would be too broad (it would catch malformed-request ValidationExceptions and silently null-stamp pages). Message-only is impossible because Bedrock raises `ClientError`, not a custom subclass. The conjunction matches the literal current Bedrock message "Model does not support count tokens operation" via the substring `count tokens` (case-insensitive, robust to minor AWS rewording).

### F2: idempotency via key-presence, not `.get()` value

`post.metadata.get("tokens")` returns `None` BOTH for "key missing" AND "key present, value null". To get the right "unchanged" determination when `count is None`, we additionally check `"tokens" in post.metadata`. Result: "no tokens key" → stamp `tokens: null`; "tokens: null already set" → unchanged.

## W5 audit findings

Grep across `packages/wiki-io/src/`, `packages/workspace-io/src/`, and `agents/graph-wiki-agent/`:

- **`package/overview.md`** is *NOT* rendered to a page by any in-repo Python code path. `init_vault.py` only copies it (with sibling sub-page templates) into `<wiki>/.templates/` as a starter asset. The rendering happens externally — primarily in the upstream graph-wiki Claude Code plugin's `scan` skill, which reads `.templates/package/overview.md` and substitutes `{{PACKAGE_TITLE}}`, `{{DATE}}`, and now `{{PACKAGE_SLUG}}` when emitting `<wiki>/packages/<slug>/<slug>.md`. The template change in this plan is the source of truth; consumer-side updates to also pass `PACKAGE_SLUG` are out of scope for this quick (they live in the plugin port, not this repo).
- **`domain/overview.md`** *IS* rendered in-repo by `layout_io.ensure_domain_page` (no in-repo caller today, but production-ready). I updated that function to substitute `{{DOMAIN_SLUG}}` from `domain_dir.name` — the test exercises this path directly.
- **No call sites** emit package overviews through the existing `ensure_*` helpers; there is no `ensure_package_overview` function. If one is added later, it should mirror `ensure_domain_page` (substitute `PACKAGE_SLUG`, `PACKAGE_TITLE`, `DATE`).

### Container-path follow-up (W5 step 6)

The new wikilinks hardcode `packages/` and `domains/` prefixes. If a workspace remaps containers via the `wiki/CLAUDE.md` layout block (e.g. `vault_dir: plugins`), the rendered wikilinks would point to a non-existent path. No follow-up todo is filed here — the current in-repo emitters (`ensure_domain_page` and the external graph-wiki plugin's scan path) already write into hardcoded `domains/` / `packages/` directory trees, so the template's literal prefix and the on-disk layout stay in lockstep. If a future plan introduces container-aware emission, it should also parameterize the wikilink prefix (e.g. via `{{PACKAGE_CONTAINER}}`).

## Deviations from Plan

None. Plan executed exactly as written; the inline notes above (audit findings, container-path follow-up) match the planner's <output> section requirements.

## Self-Check: PASSED

**Files exist:**
- `packages/workspace-io/src/workspace_io/config.py` — modified (REPO_DIRECTORY_KEY, _repo_directory_override added)
- `packages/workspace-io/tests/test_config.py` — modified (6 new tests)
- `packages/wiki-io/src/wiki_io/assets/page-templates/package/overview.md` — modified (path-qualified wikilinks)
- `packages/wiki-io/src/wiki_io/assets/page-templates/domain/overview.md` — modified (path-qualified wikilink)
- `packages/wiki-io/src/wiki_io/layout_io.py` — modified (ensure_domain_page substitutes {{DOMAIN_SLUG}})
- `packages/wiki-io/src/wiki_io/lint_wiki.py` — modified (SCHEMA_FILENAMES + two skip sites)
- `packages/wiki-io/src/wiki_io/update_tokens.py` — modified (_is_unsupported_model_error + tokens: null branch)
- `packages/wiki-io/tests/test_lint_wiki.py` — modified (3 new tests)
- `packages/wiki-io/tests/test_update_tokens.py` — modified (4 new tests)
- `packages/wiki-io/tests/test_overview_template_wikilinks.py` — created (2 new tests)

**Commits exist (8 total in 260521-gc0 series):**
- `ca97368` test(260521-gc0): add failing tests for repo-directory override
- `a4c2da6` feat(260521-gc0): honor repo-directory: in workspace manifest
- `4e4c8e6` test(260521-gc0): add failing tests for path-qualified overview wikilinks
- `af02ef8` feat(260521-gc0): path-qualified wikilinks in overview templates
- `b4ddc8f` test(260521-gc0): add failing tests for schema-file lint exclusion
- `62c1de7` feat(260521-gc0): exclude CLAUDE.md and AGENTS.md from lint enumeration
- `a1ef1a7` test(260521-gc0): add failing tests for tokens: null on unsupported model
- `fbdfa20` feat(260521-gc0): write tokens: null when CountTokens is unsupported
