# Requirements — Milestone v1.3 Tooling Cleanup

**Defined:** 2026-05-19
**Core Value:** Faithfully reproduce the upstream `graph-wiki` wiki-maintenance workflows while running entirely on AWS Bedrock with parallel subagents, so the same outcomes can be achieved at meaningfully lower cost than the current Claude-Code-hosted plugin.

**Milestone goal:** Burn down the v1.2 carry-forward bug list in `vault-io` (`scan_monorepo`, `update_tokens`, `init_vault` / `detect_containers`) and the `/init` plugin command shadow, and address the Phase 16 code review findings so the trace pipeline + eval harness refactor lands clean.

**Scoped:** 2026-05-19 via `/gsd:new-milestone`. Phase numbering continues from Phase 17 (v1.2 ended at Phase 16).

---

## Active Requirements

### Scan Companion-Page Diff (SCAN)

Source: `graph-wiki/work/2026-05-19-scan-diff-treats-companion-pages-as-orphans.md`. On a healthy 7-package vault `/graph-wiki:scan` currently reports `0 new, 0 renamed, 28 deleted, 7 unchanged` — all 28 "deletions" are the four-per-package companions (`api`, `context`, `patterns`, `work`) declared in `wiki/CLAUDE.md` under `workflow_hints`.

- [ ] **SCAN-01**: `packages/vault-io/src/vault_io/scan_monorepo.py::_load_existing_pages` folds package companion files (`api.md`, `context.md`, `patterns.md`, `work.md`) inside `wiki/packages/<pkg>/` into the parent slug `<pkg>` instead of treating each filename as a separate slug (Option A from the work item).
- [ ] **SCAN-02**: Unit test against a fixture vault with one or more `wiki/packages/<pkg>/` directories containing the four companion files asserts the diff reports 0 `deleted` entries for those companions and reports the package slug once.

### Bedrock CountTokens API Fix (TOK)

Source: `.planning/todos/pending/2026-05-19-fix-bedrock-count-tokens-api-shape-in-update-tokens.md`. Current `vault_io.update_tokens.count_tokens()` calls `client.count_tokens(modelId=..., content=[{"text": text}])` — boto3 rejects `content` and requires `input` per current `bedrock-runtime.count_tokens` API. Every page fails to be stamped during `/graph-wiki:scan`; 35 newly-stubbed pages in `~/Personal/wiki/deep-agents` are at `tokens: 0` as a result.

- [ ] **TOK-01**: `vault_io.update_tokens.count_tokens()` uses the correct current boto3 `bedrock-runtime.count_tokens` parameter shape (`input=...`); shape verified against installed boto3 introspection and AWS docs (https://docs.aws.amazon.com/bedrock/latest/userguide/count-tokens.html).
- [ ] **TOK-02**: Unit test in `packages/vault-io/tests/test_update_tokens.py` mocks the boto3 client and asserts the request payload matches the expected shape; gated integration test (`CODE_WIKI_RUN_INTEGRATION=1`) exercises a real `count_tokens` call against Bedrock.
- [x] **TOK-03**: Existing wiki pages with `tokens: 0` are re-stamped after the fix (operational closure — re-run `/graph-wiki:scan` or `update_tokens.py` against `~/Personal/wiki/deep-agents`).

### Workspace / Repo Resolution (WSRES)

Source: `.planning/todos/pending/2026-05-19-fix-workspace-repo-resolution-in-init-vault-and-detect-conta.md`. Both `init_vault.py:305-306` and `detect_containers.py:174-175` resolve the repo root incorrectly when the wiki lives at `<workspace>/wiki/` (the v2 layout) — they take `wiki.parent` (the empty workspace dir) instead of using `resolve_wiki_and_repo()`'s second return value. `detect_containers.py --json` returns `[]` and `init_vault.py` fails to detect any containers when run from the repo. Secondary bug: the detector self-classifies the workspace dir itself (`graph-wiki/`) as a `docs` container.

- [ ] **WSRES-01**: `init_vault.py:305` and `detect_containers.py:174` use `_, repo = resolve_wiki_and_repo()` (second return value) so the repo root resolves correctly at the v2 workspace layout.
- [ ] **WSRES-02**: `detect_containers.detect()` (or its caller) excludes the resolved workspace path from classification so the workspace dir doesn't appear in its own layout block.
- [ ] **WSRES-03**: Test in `packages/vault-io/tests/` runs the detector against a fixture repo with wiki at `<repo>/graph-wiki/wiki/` and asserts it finds repo-root containers (not workspace-root contents).

### Plugin Command Rename (CMD)

Source: `.planning/todos/pending/2026-05-19-rename-graph-wiki-init-command-to-init-wiki.md`. The `graph-wiki` plugin ships a `/init` command (`plugins/graph-wiki/commands/init.md`) that shadows Claude Code's built-in `/init`. With the plugin installed, the native "initialize CLAUDE.md" workflow is unreachable.

- [ ] **CMD-01**: `plugins/graph-wiki/commands/init.md` renamed to `plugins/graph-wiki/commands/init-wiki.md`.
- [ ] **CMD-02**: Internal references to `/init` or `graph-wiki:init` updated to `/init-wiki` / `graph-wiki:init-wiki` across `marketplace.json` (if present), `plugins/graph-wiki/skills/graph-wiki/SKILL.md`, READMEs, other slash command bodies, and any prompt text. Underlying `init_vault.py` script name unchanged (per the todo's explicit guidance).
- [ ] **CMD-03**: Verified that Claude Code's built-in `/init` is reachable again with the plugin installed (manual smoke documented in the phase's UAT).

### Phase 16 Code Review Burndown (REVIEW)

Source: v1.2 close — Phase 16 code review on trace pipeline + eval harness refactor surfaced 6 warnings + 9 info findings (0 critical). Not blocking but rolled forward to v1.3 per the v1.2 retrospective.

- [ ] **REVIEW-01**: All 6 Phase 16 code review **warnings** triaged — for each: fix, dismiss with documented rationale, or convert to follow-up todo. Outcome captured in the phase's REVIEW.md / SUMMARY.md.
- [ ] **REVIEW-02**: All 9 Phase 16 code review **info** findings triaged with the same fix / dismiss / follow-up disposition.

---

## Future Requirements (deferred past v1.3)

Tracked but not in current roadmap.

- **Nyquist compliance retro decision** — 0/5 v1.1 + 0/6 v1.2 phases reached `nyquist_compliant: true` despite the toggle being enabled. Decide: retro-validate the 11 phases or disable the toggle. Carried forward to a later milestone.
- **Phase 14 SC#4 plugin smoke transcript** — manual `/graph-wiki:query` transcript not captured at v1.2 close (accepted on structural evidence). Capture as regression artifact in a later milestone.
- **`next-milestone-planning` thread closure** — carried forward through v1.0 → v1.1 → v1.2 → v1.3. Close at v1.3 close or convert to requirements at v1.4 scoping.
- **Open-source release prep** — README badges, contribution guide, PyPI publish dry-run. Deferred to **v2.0 GA** (per PROJECT.md Out of Scope).

---

## Out of Scope

Explicitly excluded from v1.3.

| Feature | Reason |
|---------|--------|
| New `vault-io` modules / commands | v1.3 is a bug-fix milestone; no new surface area. |
| Backporting more upstream `graph-wiki` modules | v1.2 spike 002 closed the drift inventory; no PORT verdicts remain. |
| MCP wire-level cancel work | Re-anchored to event-driven trigger (`langchain-aws#663` merged OR aioboto3 GA/1.0); not a calendar item. |
| Custom TUI / non-Bedrock providers / nested subagents | Out of v1.x per PROJECT.md. |

---

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| SCAN-01     | Phase 17 | Pending |
| SCAN-02     | Phase 17 | Pending |
| TOK-01      | Phase 17 | Pending |
| TOK-02      | Phase 17 | Pending |
| TOK-03      | Phase 17 | Complete |
| WSRES-01    | Phase 17 | Pending |
| WSRES-02    | Phase 17 | Pending |
| WSRES-03    | Phase 17 | Pending |
| CMD-01      | Phase 18 | Pending |
| CMD-02      | Phase 18 | Pending |
| CMD-03      | Phase 18 | Pending |
| REVIEW-01   | Phase 19 | Pending |
| REVIEW-02   | Phase 19 | Pending |

**Coverage:**
- v1.3 requirements: 13 total
- Mapped to phases: 13
- Unmapped: 0 ✓

---

*Requirements defined: 2026-05-19*
*Last updated: 2026-05-19 — traceability populated by gsd-roadmapper (Phase 17-19)*
