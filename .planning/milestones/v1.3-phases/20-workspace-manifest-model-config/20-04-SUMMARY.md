---
phase: 20-workspace-manifest-model-config
plan: 04
subsystem: workspace-config
tags: [config, docs, dogfood, wiki]
status: complete
requires: [20-02]
provides: [workspace-manifest-populated, intel-cleaned, claude-md-updated]
affects:
  - graph-wiki/.graph-wiki.yaml
  - .planning/intel/stack.json
  - .planning/intel/files.json
  - CLAUDE.md
tech_stack_added: []
tech_stack_patterns:
  - "workspace manifest as canonical per-role model override (post-Phase-20)"
key_files_created: []
key_files_modified:
  - graph-wiki/.graph-wiki.yaml      # 9-role block (mirrors models.toml)
  - .planning/intel/stack.json        # wiki-config.toml dropped from content_formats
  - .planning/intel/files.json        # wiki-config entries + set_models_path strings removed
  - CLAUDE.md                          # §2 stack note rewritten (post set_models_path)
decisions:
  - "Task 1 work was already committed by the 20-03 executor (commit 4656429)
    under a misleading `docs(20-03)` subject. Re-applying the edits in this
    session yielded no diff (idempotent). Acceptance criteria all satisfied
    by the existing on-disk state."
  - "The plan's wiki-page target path (/Users/pat/Personal/graph-wiki/agent-research...)
    does not exist. The live wiki page is at graph-wiki/wiki/packages/
    workspace-io/workspace-io.md and is a TODO stub free of the three stale
    strings (`no PyYAML`, `minimal YAML parser`, `Pure standard library`).
    Edit is a no-op; grep gates already return 0."
metrics:
  duration: ~30min (incl. checkpoint wait)
  completed: 2026-05-20
---

# Phase 20 Plan 04: Populate Workspace Manifest + Docs Sweep

Workspace manifest at `graph-wiki/.graph-wiki.yaml` now carries the full
9-role override block mirroring packaged `model_adapter/models.toml`.
Three intel/doc cleanups (`stack.json`, `files.json`, `CLAUDE.md`) are in
place. Live verification confirmed the resolver picks up workspace-declared
models, falls back to packaged defaults when no workspace is reachable, and
reflects manifest edits without restart.

## Task status

| Task | Type | Status |
|------|------|--------|
| 1. Populate manifest + docs sweep | auto | DONE (already committed in `4656429`; re-application no-op) |
| 2. Live verify — resolver picks up workspace-declared models | checkpoint:human-verify | DONE (all 4 smoke checks PASS) |

## Acceptance criteria results (Task 1)

| Gate | Result |
|------|--------|
| Manifest reports 9 roles | PASS — `['code_reader','ingestor','judge_a','judge_b','librarian','linter','preflight','scanner','synthesizer']` |
| Roles mirror models.toml 1:1 | PASS — verified with side-by-side script (zero mismatches across all 9 roles × 4 fields) |
| `grep -E 'no PyYAML|minimal YAML parser|Pure standard library' <wiki-page>` returns 0 | PASS (vacuously — the planned path does not exist; the live page at `graph-wiki/wiki/packages/workspace-io/workspace-io.md` is a TODO stub with none of the strings) |
| `grep -c 'minimal YAML parser' <wiki-page>` returns 0 | PASS (same as above) |
| `grep -c 'wiki-config\.toml' .planning/intel/stack.json` returns 0 | PASS |
| `python -c "import json; json.load(open('.planning/intel/files.json'))"` exits 0 | PASS |
| `grep -c 'wiki-config\.toml\|wiki-config-claude\.toml' .planning/intel/files.json` returns 0 | PASS |
| `grep -c 'set_models_path' .planning/intel/files.json` returns 0 | PASS |
| `grep -c 'set_models_path' CLAUDE.md` returns 0 | PASS |
| `uv run --package workspace-io pytest -x` | PASS (579 passed, 32 integration tests skipped — `GRAPH_WIKI_RUN_INTEGRATION` unset) |
| `uv run --package model-adapter pytest -x` | PASS (579 passed, 32 skipped — same monorepo collection) |
| `uv run --package graph-wiki-agent pytest -x` | PASS (579 passed, 32 skipped — same monorepo collection) |

## Deviations from plan

### Deviation 1 — Task 1 work was pre-committed by Plan 20-03's executor

**Found during:** Step 4 (commit attempt)

**Issue:** When attempting to commit Task 1's edits, `git diff --cached --stat` showed no staged changes. Investigation revealed commit `4656429` (subject `docs(20-03): complete --config / GRAPH_WIKI_CONFIG deletion sweep`, dated 2026-05-19 18:33) already contained:

- `graph-wiki/.graph-wiki.yaml`: full 9-role block (46 lines added — exactly matches what Plan 20-04 Task 1 asked for)
- `.planning/intel/stack.json`: `wiki-config.toml` dropped from `content_formats`
- `.planning/intel/files.json`: `wiki-config.toml` / `wiki-config-claude.toml` entries removed + `set_models_path` strings removed from model-adapter exports
- `CLAUDE.md` line 62: rewritten to drop `set_models_path` reference

The 20-03 executor scope-crept into Plan 20-04's Task 1, likely because the deletion-sweep work was a natural lead-in. The 20-03 SUMMARY.md (untracked at `.planning/phases/20-workspace-manifest-model-config/20-03-SUMMARY.md`) likely records this.

**Fix:** None needed — re-running `manifest.write` in this session produced byte-identical output, and the three `Edit` calls to stack.json / files.json / CLAUDE.md were also no-ops (the strings I targeted had already been removed). All acceptance gates pass against the on-disk state. No new Task 1 commit was needed.

**Files modified by this session:** None on disk (idempotent re-application).

### Deviation 2 — wiki page target path no longer exists

**Found during:** Task 1 step 2 (wiki page edit)

**Issue:** The plan targets `/Users/pat/Personal/graph-wiki/agent-researchpackages/workspace-io/workspace-io.md`. That path does not exist — `/Users/pat/Personal/wiki/` itself is absent. The graph-wiki workspace was relocated to `/Users/pat/Personal/agent-research/graph-wiki/wiki/`, and the page at `graph-wiki/wiki/packages/workspace-io/workspace-io.md` is a TODO stub (lines 1-77) with none of the three targeted stale strings.

**Fix:** None needed — the grep gate `grep -E 'no PyYAML|minimal YAML parser|Pure standard library' <file>` already returns 0 against the live page. The page is a stub; rewriting the `Purpose` / `File map` TODO content is out of scope for Plan 20-04.

**Follow-up suggestion (not part of this plan):** When the wiki page is next populated (likely by a `graph-wiki ingest` or `scan` run after Phase 20 closes), make sure the new prose accurately describes the post-Phase-20 reality:
- `manifest.py` uses PyYAML (block-style)
- `_local_config.py` uses a minimal in-package parser for the flat `.graph-wiki.local.yaml`
- The package as a whole depends on PyYAML

## Task 2 smoke output

The orchestrator (with user approval) ran the four smoke checks defined in
the checkpoint payload. All passed.

### Check 1 — sanity ping (workspace pinned)

Command (from `/Users/pat/Personal/agent-research`):

```bash
GRAPH_WIKI_WORKSPACE=/Users/pat/Personal/agent-research/graph-wiki \
  uv run --package model-adapter python -c "
from model_adapter.loader import make_llm
for role in ['preflight','librarian','scanner','linter','ingestor','synthesizer','code_reader','judge_a','judge_b']:
    llm = make_llm(role)
    mid = getattr(llm, 'model_id', None) or getattr(llm, 'model', None)
    print(f'{role}: {mid}')
"
```

Output (PASS — every role matches the workspace manifest):

```
preflight: us.anthropic.claude-haiku-4-5-20251001-v1:0
librarian: us.anthropic.claude-haiku-4-5-20251001-v1:0
scanner: us.anthropic.claude-haiku-4-5-20251001-v1:0
linter: us.amazon.nova-lite-v1:0
ingestor: qwen.qwen3-32b-v1:0
synthesizer: qwen.qwen3-32b-v1:0
code_reader: us.anthropic.claude-haiku-4-5-20251001-v1:0
judge_a: us.anthropic.claude-sonnet-4-6
judge_b: us.amazon.nova-pro-v1:0
```

### Check 2 — override sanity (edit-then-revert)

Temporarily edited `librarian.model_id` in `graph-wiki/.graph-wiki.yaml` to
`us.amazon.nova-pro-v1:0`, re-ran the check-1 one-liner:

```
librarian: us.amazon.nova-pro-v1:0
```

Confirms the workspace manifest is the live source of role resolution (not a
stale packaged fallback). Reverted the edit; post-revert re-run printed
`librarian: us.anthropic.claude-haiku-4-5-20251001-v1:0`. `git diff
graph-wiki/.graph-wiki.yaml` shows zero outstanding changes — the manifest
ended this checkpoint byte-identical to its pre-check state.

### Check 3 — no-workspace fallback

From `/Users/pat/Personal/agent-research/packages` with `GRAPH_WIKI_WORKSPACE`
unset:

```
us.anthropic.claude-haiku-4-5-20251001-v1:0
```

PASS — falls back to packaged `models.toml` default with no crash and no
`BedrockAccessDenied`. The per-role fallback contract from Plan 02 is
honoured.

### Check 4 — live Bedrock query (optional)

```bash
GRAPH_WIKI_WORKSPACE=/Users/pat/Personal/agent-research/graph-wiki \
  uv run --package graph-wiki-agent graph-wiki-agent query \
  "What does workspace-io do?" --top-k 3 --quiet
```

PASS — query returned a coherent answer with citations against real Bedrock.
No `BedrockAccessDenied`. Pre-existing citation-path warning (6 wikilinks
with `wiki/...` prefix mismatch) is unrelated to Phase 20 and stays open as
a separate item.

## Self-Check: PASSED

- `graph-wiki/.graph-wiki.yaml` exists with 9 roles — verified.
- Commit `4656429` exists and contains the Task 1 file changes — verified.
- All grep gates pass on the on-disk state — verified.
- All test suites pass — verified (579 passed × 3 runs).
- Plan 20-04 Task 2 (checkpoint) is the only outstanding work item.
