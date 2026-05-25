# Phase 25: packages-dir-misclassification-fix - Context

**Gathered:** 2026-05-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Fix the `_classify_dir` heuristic in `packages/wiki-io/src/wiki_io/detect_containers.py` so a top-level directory containing a mix of manifested package children and one or more non-manifested siblings (or loose `.md` files) is classified as `package` — not `ambiguous`. Update the plugin-side reference doc that describes the heuristic. Add unit tests pinning the new behavior. Resolve the pending todo.

The `--interactive` CLI flag is **out of scope** for this phase and deferred to a follow-up (see Deferred Ideas).

</domain>

<decisions>
## Implementation Decisions

### Classifier Rule (`_classify_dir`)
- **D-01:** Rule 3 ("package container") becomes permissive: **if ≥1 immediate child has a manifest, classify the directory as `package`.** Non-manifested siblings and any loose `.md` files at the container root are silently excluded from the wiki layout — they no longer flip the classification.
- **D-02:** When classified as `package`, `children_count` reports `len(manifest_kids)` (the number of actual packages that will get wiki pages), not `len(children)`. The `reason` string should be honest about what was skipped, e.g. `"5/6 children have manifests; 1 skipped"`.
- **D-03:** The all-or-nothing gate (`len(manifest_kids) == len(children) and not md_files`) is removed. The "mixed" branch that returned `ambiguous` is removed.

### `ambiguous` retention
- **D-04:** The `ambiguous` classification value is **kept** — but only for the fallback branches at `detect_containers.py:132-145` (dirs that match no rule: no manifested children, not predominantly `.md`, empty/unrecognized shape). The mixed-manifest case no longer produces `ambiguous`.
- **D-05:** `_resolve_pinned_containers` in `init_vault.py` keeps its `if cls == "ambiguous"` branch. Under `non_interactive=True`, those fallback-ambiguous rows continue to become `skip` (existing behavior — correct for diagnostic visibility).

### Plugin shim
- **D-06:** `plugins/graph-wiki/skills/graph-wiki/scripts/detect_containers.py` is already a 9-line passthrough (`from wiki_io.detect_containers import main`). Success criterion 3 ("plugin-side classifier matches the updated heuristic") is **auto-satisfied** by the wiki-io change. No separate plugin port.

### Docs sync (lockstep with code change)
- **D-07:** Update `plugins/graph-wiki/skills/graph-wiki/references/detection-workflow.md` in the **same commit/phase** as the classifier change to describe the new rule. The plugin CLAUDE.md (§"When changing how layout is detected, classified, or written…") makes this mandatory.
- **D-08:** If `detection-workflow.md` does not currently describe the heuristic rule explicitly, add a short "Rules" subsection so future readers know how `package` is decided.

### Test coverage (`packages/wiki-io/tests/test_detect_containers.py`)
- **D-09:** Add three new unit tests pinning the new contract:
  1. **5/6 manifested → `package`** — bug repro fixture: 6 child dirs, 5 with `pyproject.toml`, 1 without (`prompt_sources/` shape).
  2. **Manifested kids + loose `README.md` at container root → `package`** — proves the loose-.md gate is gone.
  3. **Truly unrecognized fallback → `ambiguous`** — empty container, or a container with non-manifested kids and no `.md` predominance. Locks the boundary between "has manifests" and "no rule matches".
- **D-10:** Existing tests in `test_detect_containers.py` (currently 4: `test_v2_layout_finds_repo_containers`, `test_workspace_path_excluded`, `test_v1_layout_guard`, `test_v2_synthetic_repo`) must continue to pass without modification — if any depend on the old all-or-nothing rule, the rule change has broken downstream expectations that need separate investigation.

### Pending todo resolution
- **D-11:** Move `.planning/todos/pending/2026-05-20-fix-packages-dir-misclassification.md` → `.planning/todos/resolved/` in the same phase, with a short note referencing the phase SUMMARY.

### Roadmap mutation (Phase 25 SPEC adjustment)
- **D-12:** Success criterion 4 in ROADMAP.md (`graph-wiki-agent bootstrap --interactive prompts the user on any remaining ambiguous classifications instead of silently skipping them`) is **removed** from Phase 25's success criteria. The `--interactive` work is deferred (see Deferred Ideas). The planner should propose this edit to ROADMAP.md as part of the plan.
- **D-13:** Success criterion 5 in ROADMAP.md becomes `.planning/todos/pending/...` is moved to `resolved/` (without the `--interactive` flag clause).

### Folded Todos
- **`2026-05-20-fix-packages-dir-misclassification.md`** (`area: graph-wiki`, score 0.9) — the originating bug report. Phase 25 implements the fix; todo moves to `resolved/` on phase completion.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope & requirements
- `.planning/ROADMAP.md` §"Phase 25: packages-dir-misclassification-fix" — phase goal, requirements, success criteria (note D-12/D-13: criteria 4 changes scope as part of this phase)
- `.planning/REQUIREMENTS.md` — PKGCLS-01 through PKGCLS-05 (verify they don't bind us to `--interactive`; if PKGCLS-04 mandates it, planner needs to adjust)
- `.planning/todos/pending/2026-05-20-fix-packages-dir-misclassification.md` — original bug report with reproduction details

### Code (primary)
- `packages/wiki-io/src/wiki_io/detect_containers.py` — the file Phase 25 edits; classifier logic in `_classify_dir` (lines 80-145)
- `packages/wiki-io/src/wiki_io/init_vault.py` §`_resolve_pinned_containers` (lines 84-133) — consumer of classifier output; `if cls == "ambiguous"` branch stays
- `packages/wiki-io/tests/test_detect_containers.py` — where new unit tests land
- `plugins/graph-wiki/skills/graph-wiki/scripts/detect_containers.py` — thin shim; **read but do not edit** (auto-inherits the wiki-io change per D-06)

### Code (read-only context)
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/init.py` §`run_init` line 88 — hardcoded `non_interactive=True`; **do NOT** thread `--interactive` through here in this phase (deferred)

### Docs (lockstep update)
- `plugins/graph-wiki/skills/graph-wiki/references/detection-workflow.md` — describes the classifier; **must be updated in the same commit** per plugin CLAUDE.md invariant (§"When changing how layout is detected, classified, or written…")
- `plugins/graph-wiki/CLAUDE.md` §"Wiki layout invariants" — describes how `detect_containers` runs interactively for ambiguous rows. After D-12 lands, the "interactive" framing may need a small edit. Re-read before drafting.

### Iron rules (must be preserved)
- `plugins/graph-wiki/CLAUDE.md` §"Iron rules the skill enforces" — Rule 1 ("code is source of truth") and Rule 4 ("every ingest/scan touches ≥3 files: page, index.md, log.md") apply to this phase's wiki-write effects when bootstrap is later run on this repo.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `packages/wiki-io/tests/helpers.py` — provides `tmp_repo`, `write_pkg`, `write_file`, `write_claude_plugin` for inline throwaway repos. The new unit tests should use these helpers — do NOT reach into the repo-root `fixtures/` directory (those are for layout-level tests).
- `_has_manifest(d)` and `_immediate_subdirs(d)` — the existing helpers in `detect_containers.py` are correct and stay unchanged; only `_classify_dir`'s Rule 3 branch needs surgery.

### Established Patterns
- `MANIFEST_FILES` set (`detect_containers.py:26-32`) is the source of truth for what "manifested" means: `package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, `.claude-plugin/plugin.json`. The new rule keeps this definition.
- `SKIP_DIRS` set already filters `.venv`, `node_modules`, etc. — non-manifested children that get silently skipped under the new rule are a different concept (legitimate sub-dirs without manifests, e.g. `prompt_sources/`).
- Plugin-side scripts are thin shims importing from `wiki_io.<name>` — this phase preserves that pattern; no behavior in the plugin shim itself changes.

### Integration Points
- Bootstrap path: `graph-wiki-agent bootstrap` → `cli.py:bootstrap()` → `run_init()` → `init_wiki()` → `_resolve_pinned_containers()` → `_detect_containers()` → `_classify_dir()`. Phase 25 only touches the leaf (`_classify_dir`) and the leaf's test file.
- The bug surfaced under `non_interactive=True` (which is the only mode `run_init` calls today). The fix removes the conditions under which the bug-causing `ambiguous` row was returned in the first place — no change to the interactive vs non-interactive dispatch is needed in this phase.

</code_context>

<specifics>
## Specific Ideas

- The bug was reproduced on this repo on 2026-05-20. `packages/` has 6 children — 5 with `pyproject.toml` (`core-bedrock`, `eval-harness`, `model-adapter`, `subagent-runtime`, `wiki-io`, `workspace-io`) and 1 without (`prompt_sources/`). The new rule must classify this case as `package`, with `prompt_sources/` silently excluded.
- Pat's framing for the new rule, verbatim: *"get rid of the ambiguous classification altogether. If there are packages in the directory, create package pages for them and skip the rest."* The implementation honors this for the Rule 3 branch (the bug path); the fallback branches keep `ambiguous` purely for diagnostic visibility on genuinely broken/empty dirs.
- Verification: after the fix, running `python -m wiki_io.detect_containers --json` on this repo should emit `"packages"` with `"classification": "package"` and `"children_count": 5`.

</specifics>

<deferred>
## Deferred Ideas

- **`--interactive` flag on `graph-wiki-agent bootstrap`** — originally the todo's "bonus consideration" and ROADMAP Phase 25 success criterion 4. With `ambiguous` no longer produced by the mixed-manifest case, the only `ambiguous` rows left are genuine fallback edge cases (empty/broken top-level dirs). Interactive prompting on those is a real UX feature, not a one-liner. Open a backlog item: *"`graph-wiki-agent bootstrap --interactive`: prompt user on fallback-ambiguous rows; thread `non_interactive` parameter through `run_init`; consider what interactive UX looks like for the broader detected layout."*
- **`--non-interactive` parity for MCP tool path** — the MCP `bootstrap` tool inherits the CLI's `non_interactive=True` hardcoding via `run_init`. Decision about whether MCP should ever surface interactive prompts (probably never — MCP is non-tty) belongs with the deferred `--interactive` work.

### Reviewed Todos (not folded)
None — only the one matching todo, and it was folded.

</deferred>

---

*Phase: 25-packages-dir-misclassification-fix*
*Context gathered: 2026-05-21*
