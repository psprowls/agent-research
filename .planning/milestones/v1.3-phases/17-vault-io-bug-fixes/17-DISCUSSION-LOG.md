# Phase 17: wiki-io Bug Fixes - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-19
**Phase:** 17-wiki-io-bug-fixes
**Areas discussed:** Companion folding placement, CountTokens input shape, Workspace self-exclusion, Plan structure & TOK-03 closure

---

## Gray-area selection

| Option | Description | Selected |
|--------|-------------|----------|
| Companion folding placement | Where in scan_monorepo.py to fold companion files; hardcoded vs layout-sourced names | ✓ |
| CountTokens input shape | converse vs invokeModel shape; test depth | ✓ |
| Workspace self-exclusion | Exclusion site (arg/caller/auto-detect); fixture shape | ✓ |
| Plan structure & TOK-03 closure | Plan split; how TOK-03 re-stamp closes | ✓ |

**User's choice:** All four areas.

---

## Companion folding placement

### Q1: Where should the companion fold happen?

| Option | Description | Selected |
|--------|-------------|----------|
| Filter inside `_collect()` | Skip companion stems inline during the existing rglob walk | ✓ |
| Post-process pages dict | Build everything, then a follow-up pass collapses companion entries | |
| Refactor to per-dir slug | Iterate `wiki/packages/<pkg>/` directories, one entry per dir | |

**User's choice:** Filter inside `_collect()` — keep diff minimal, two-line change.

### Q2: Where does the companion filename list come from?

| Option | Description | Selected |
|--------|-------------|----------|
| Hardcoded constant | `COMPANION_FILENAMES = {'api','context','patterns','work'}` in module | |
| Read from layout block | Parse `wiki/CLAUDE.md` `workflow_hints` via `layout_io.read_layout()` | ✓ |
| Both — layout w/ fallback | Try layout, fall back to hardcoded set | |

**User's choice:** Read from layout block. Schema is authoritative.

### Q3: Behavior when `workflow_hints` is absent

| Option | Description | Selected |
|--------|-------------|----------|
| Empty set — no folding | No silent fallback; vault owner controls schema | ✓ |
| Fallback to baked-in default | Use upstream graph-wiki's 4-name default | |
| Warn + empty | Empty plus stderr warning | |

**User's choice:** Empty set — no folding. Vault owner is responsible for declaring companions.

### Q4: Fold scope across container types

| Option | Description | Selected |
|--------|-------------|----------|
| Every package/app container | Apply to apps, packages, layout-pinned, domain-scoped packages | |
| Only `wiki/packages/` | Narrow to where bug was observed | |
| Apps + packages, skip domains | Both top-level, leave domains untouched | |

**User's choice (free-text):** "Just domains and packages. The app page is a single page, only package and domain have directory templates."

**Notes:** App pages are single-file by convention — no `api/context/patterns/work` companions. Domain top-level pages and domain-scoped packages both follow the package directory template.

---

## CountTokens input shape

### Q1: Which input shape should `count_tokens()` use?

| Option | Description | Selected |
|--------|-------------|----------|
| converse shape (Recommended) | `input={'converse': {'messages': [{...}]}}` | ✓ |
| invokeModel raw body | `input={'invokeModel': {'body': bytes}}` | |
| Branch on model_id | Pick shape per model family | |

**User's choice:** Converse shape. Matches `ChatBedrockConverse` usage across codebase; stable across Claude/Qwen/Cohere.

### Q2: What does the unit test assert about the boto3 call?

| Option | Description | Selected |
|--------|-------------|----------|
| Exact payload shape | Assert `count_tokens.assert_called_once_with(modelId=..., input={...})` | ✓ |
| Shape + return path | Exact-shape assertion AND assert function returns `response['inputTokenCount']` | |
| Smoke only | Mock returns 42, assert returns 42 (no shape lock) | |

**User's choice:** Exact payload shape. Locks the API shape; future regression to `content=...` fails the test.

**Notes:** Captured in CONTEXT.md D-06 to combine both — exact-shape assertion AND return-path assertion as one test (the user picked the higher-signal option; adding the return assertion is a no-cost extra).

---

## Workspace self-exclusion + WSRES fixture

### Q1: Where does workspace self-exclusion live in detect_containers?

| Option | Description | Selected |
|--------|-------------|----------|
| Optional arg to `detect()` | `detect(repo_root, workspace_path=None)` skips matching subdir | ✓ |
| Caller-side filter | `detect()` unchanged; CLI + init_vault filter post-call | |
| Auto-detect inside `detect()` | `detect()` calls `resolve_wiki_and_repo()` internally | |

**User's choice:** Optional arg to `detect()`. Pure function stays pure; library + CLI both benefit.

### Q2: What does the WSRES test fixture look like?

| Option | Description | Selected |
|--------|-------------|----------|
| Synthetic monorepo + tmp_path | pytest tmp_path with `repo/graph-wiki/wiki/` + two pyproject packages | ✓ |
| Reuse existing fixture | Extend `conftest.py` fixture if one exists | |
| Use agent-research repo itself | GRAPH_WIKI_RUN_INTEGRATION-gated against real repo | |

**User's choice:** Synthetic tmp_path monorepo. Reproducible and isolated.

**Notes:** v1-layout guard (workspace_path == repo_root case) was raised by Claude as a discretion item; user did not push back. Captured as D-11.

---

## Plan structure & TOK-03 closure

### Q1: How should Phase 17 be split into plans?

| Option | Description | Selected |
|--------|-------------|----------|
| One bundled atomic plan | Single `17-01-PLAN.md` with per-step commits | ✓ |
| Three plans by bug cluster | `17-01` SCAN, `17-02` TOK, `17-03` WSRES | |
| Two plans — code + closure | `17-01` all code; `17-02` TOK-03 operational closure | |

**User's choice:** One bundled atomic plan. Matches Phase 16 D-14 + Phase 14 D-01 pattern.

### Q2: How is TOK-03 (re-stamp 35 existing tokens:0 pages) handled?

| Option | Description | Selected |
|--------|-------------|----------|
| Final step in the plan | Run `update_tokens.py` on `~/Personal/graph-wiki/agent-research`, commit wiki-side updates, transcript into VERIFICATION.md | ✓ |
| Post-merge operational | Operator re-runs separately; transcript pasted into VERIFICATION.md | |
| Out of plan — follow-up todo | TOK-03 becomes a pending todo (risk: slips) | |

**User's choice:** Final step in the plan. Mirrors Phase 15 D-08/D-09 live-vault pattern.

---

## Claude's Discretion

- Exact home for the companion-set constant (module-level vs local) — module-level preferred.
- Exact form of layout-block lookup (extend `read_layout()` return shape vs thin `workflow_hints` accessor).
- SCAN unit-test fixture site (`conftest.py` extension vs inline in test file).
- Decorator import path for `GRAPH_WIKI_RUN_INTEGRATION` skip — follow `docs/testing.md`.
- Whether TOK gated integration test imports a shared helper or inlines the decorator.
- D-11 exclusion guard — `Path.resolve()` equality vs `samefile()`.
- WSRES tests in a new module vs extending an existing one.

## Deferred Ideas

(All rejected alternatives listed in CONTEXT.md `<deferred>` — summary:)

- Hardcoded companion-name fallback (could land if a future vault has on-disk companions without `workflow_hints`).
- `_load_existing_pages` per-directory refactor (re-visit if metadata aggregation becomes a real need).
- Layout-with-baked-in-fallback for companion names.
- Model-id branching on `count_tokens()` input shape.
- Smoke-only TOK unit test.
- Auto-detect workspace inside `detect()`.
- Caller-side workspace filter.
- Three-plan or two-plan split.
- TOK-03 as a follow-up todo.
- Real-repo integration test for WSRES.
