# Phase 25: packages-dir-misclassification-fix — Research

**Researched:** 2026-05-21
**Domain:** vault-io classifier heuristic (Python, stdlib only)
**Confidence:** HIGH — all claims verified against the worktree as of this date

## Summary

This phase is a tightly scoped bug fix to `_classify_dir` in `packages/vault-io/src/vault_io/detect_containers.py` plus a lockstep update to the matching plugin reference doc, three new unit tests, ROADMAP success-criteria edits, and a todo move. All design decisions are locked in `25-CONTEXT.md` (D-01..D-13). The role of this research is to give the planner accurate file:line targets and to flag two CONTEXT.md inaccuracies the planner needs to know about before writing PLAN.md.

**Primary recommendation:** The planner should produce a **single PLAN** (this is ~50 LOC in one file plus 3 small unit tests). No need to split into waves or multi-plan. The planner must, however, correct two CONTEXT.md claims before drafting tasks (see "User Constraints" deltas below).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Classifier Rule (`_classify_dir`)**
- **D-01:** Rule 3 ("package container") becomes permissive: if ≥1 immediate child has a manifest, classify the directory as `package`. Non-manifested siblings and any loose `.md` files at the container root are silently excluded from the wiki layout — they no longer flip the classification.
- **D-02:** When classified as `package`, `children_count` reports `len(manifest_kids)`, not `len(children)`. The `reason` string should be honest about what was skipped, e.g. `"5/6 children have manifests; 1 skipped"`.
- **D-03:** The all-or-nothing gate (`len(manifest_kids) == len(children) and not md_files`) is removed. The "mixed" branch that returned `ambiguous` is removed.

**`ambiguous` retention**
- **D-04:** `ambiguous` value kept, but only for fallback branches (`detect_containers.py:132-145`) — dirs that match no rule (no manifested children, not predominantly `.md`, empty/unrecognized shape).
- **D-05:** `_resolve_pinned_containers` in `init_vault.py` keeps its `if cls == "ambiguous"` branch. Under `non_interactive=True`, fallback-ambiguous rows continue to become `skip`.

**Plugin shim**
- **D-06:** `plugins/graph-wiki/skills/graph-wiki/scripts/detect_containers.py` is already a 9-line passthrough. Success criterion 3 (plugin classifier matches) is **auto-satisfied** by the vault-io change. No separate plugin port.

**Docs sync (lockstep)**
- **D-07:** Update `plugins/graph-wiki/skills/graph-wiki/references/detection-workflow.md` in the same commit as the code change.
- **D-08:** If detection-workflow.md does not currently describe the heuristic rule explicitly, add a short "Rules" subsection.

**Test coverage**
- **D-09:** Add three new unit tests pinning the new contract (5/6 manifested → `package`; manifested kids + loose `README.md` → `package`; truly unrecognized fallback → `ambiguous`).
- **D-10:** Existing 4 tests must continue to pass without modification.

**Pending todo resolution**
- **D-11:** Move `.planning/todos/pending/2026-05-20-fix-packages-dir-misclassification.md` → `.planning/todos/resolved/` in the same phase.

**Roadmap mutation**
- **D-12:** Remove ROADMAP Phase 25 success criterion 4 (the `--interactive` clause).
- **D-13:** ROADMAP Phase 25 success criterion 5 becomes just the todo-move clause (without the `--interactive` flag visibility test).

### Claude's Discretion
- Exact wording of the new `reason` string and the new "Rules" subsection in `detection-workflow.md` (the user has not specified phrasing).
- Internal helper extraction inside `_classify_dir` (e.g. naming a small `_format_skipped_reason()` helper). Keep it minimal.
- Order of `<= 50 LOC` edits within `_classify_dir` — surgical, in place.

### Deferred Ideas (OUT OF SCOPE)
- `--interactive` flag on `graph-wiki-agent bootstrap` (originally PKGCLS-03 / ROADMAP SC#4). Open a backlog item.
- `--non-interactive` parity for the MCP `bootstrap` tool path.
- Renaming `vault-io` / `vault_io` module (separate sweep, milestone-level decision).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| **PKGCLS-01** | `_classify_dir` loosens `package` rule so a strong majority of manifested children still counts as `package`; `ambiguous` reserved for genuinely mixed dirs. | D-01..D-03 reshape this — the new rule is more permissive than PKGCLS-01's literal text (`≥80%`). PKGCLS-01 says "strong majority (≥80%, or equivalently `manifested >= children - 1`)"; D-01 says **`≥1 manifest`** is sufficient. **PKGCLS-01's `≥80%` wording is superseded by D-01.** The implementation must follow D-01 (the user's locked decision). |
| **PKGCLS-02** | Plugin-side classifier updated to match. | D-06: shim is already a 9-line passthrough — auto-satisfied. No edits to the shim. |
| **PKGCLS-03** | `graph-wiki-agent bootstrap` exposes `--interactive` flag; `run_init` no longer hardcodes `non_interactive=True`. | **DEFERRED out of Phase 25** by D-12. PKGCLS-03 is moved to a future backlog item. The planner must call this out explicitly in PLAN.md (this requirement is **not** addressed in this phase). |
| **PKGCLS-04** | Unit test against a fixture repo with one packages dir (5/6 manifested) asserts `_classify_dir` returns `package`. Operational verification: bootstrap on this repo creates `wiki/packages/` without `--interactive`. | D-09 covers the unit test. The operational verification clause does **not** mention `--interactive` — PKGCLS-04 does **not** bind us to it. **CONTEXT.md's worry about PKGCLS-04 mandating `--interactive` is resolved: it does not.** |
| **PKGCLS-05** | Pending todo moved to resolved. | D-11 covers this exactly. |
</phase_requirements>

## CONTEXT.md Inaccuracies the Planner Must Correct

Two factual claims in `25-CONTEXT.md` are wrong against the worktree as of 2026-05-21. The planner must work around these.

### Inaccuracy 1: `tests/helpers.py` does NOT exist [VERIFIED: filesystem]

CONTEXT.md `<code_context>` says:

> `packages/vault-io/tests/helpers.py` — provides `tmp_repo`, `write_pkg`, `write_file`, `write_claude_plugin` for inline throwaway repos. The new unit tests should use these helpers …

**Reality:** There is no `packages/vault-io/tests/helpers.py`. The helpers actually live in `packages/vault-io/tests/conftest.py`:

- `tmp_repo` — pytest fixture (lines 11-14 of conftest.py). Just returns `tmp_path`.
- `write_file` — module-level helper (lines 17-21). Writes content to a path, creating parents.
- `write_pkg` — **does not exist** anywhere in the repo (verified by grep across `packages/` and `plugins/`).
- `write_claude_plugin` — **does not exist** anywhere in the repo.

**Implication for planner:** The new unit tests can use `tmp_repo` (auto-imported via conftest.py — no import statement needed in test files) and `write_file` (must be imported: `from tests.conftest import write_file` or duplicated inline). For "write a `pyproject.toml` into a subdir" the test needs ~2 lines of `Path.write_text` directly; do **not** plan tasks that assume `write_pkg`/`write_claude_plugin` exist.

**Recommended pattern for the new tests** — match the existing `test_detect_containers.py` style which inlines the fixture construction:

```python
def test_mixed_manifest_dirs_classify_as_package(tmp_path: Path) -> None:
    from vault_io.detect_containers import _classify_dir

    container = tmp_path / "packages"
    for name in ("a", "b", "c", "d", "e"):
        (container / name).mkdir(parents=True)
        (container / name / "pyproject.toml").write_text('[project]\nname="x"\n', encoding="utf-8")
    (container / "prompt_sources").mkdir()  # no manifest

    rec = _classify_dir(container)
    assert rec["classification"] == "package"
    assert rec["children_count"] == 5
```

This is consistent with how the existing 4 tests build their inputs (verified — see "Existing Tests Pass Under New Rule" below).

### Inaccuracy 2: PKGCLS-04 does NOT bind us to `--interactive` [VERIFIED: REQUIREMENTS.md]

CONTEXT.md says: *"verify they don't bind us to `--interactive`; if PKGCLS-04 mandates it, planner needs to adjust."*

PKGCLS-04 reads in full:

> Unit test in `packages/vault-io/tests/` against a fixture repo with one packages dir (5/6 manifested) asserts `_classify_dir` returns `package`. Operational verification: running `graph-wiki-agent bootstrap` on this repo without `--interactive` classifies `packages/` as `package` and creates `wiki/packages/` automatically.

The phrase "without `--interactive`" only describes the operational mode — it doesn't require the flag to exist. The unit test (the binding part of the requirement) makes no mention of `--interactive`. **PKGCLS-04 is satisfiable in this phase without exposing the flag.** No planner adjustment needed.

## File:Line Targets (verified 2026-05-21)

### Primary edit — `packages/vault-io/src/vault_io/detect_containers.py`

| Line range | Current content | Phase 25 action |
|------------|-----------------|------------------|
| **80-145** | `_classify_dir` function (whole) | scope of the edit |
| 86-96 | Rule 1: docs container | leave unchanged |
| 98-110 | Rule 2: domain container | leave unchanged |
| **112-129** | Rule 3: package container — has both the all-or-nothing branch (115-121) and the mixed-→ambiguous branch (123-129) | **rewrite per D-01..D-03**: collapse into a single "≥1 manifest_kid → package" branch. Compute `skipped = len(children) - len(manifest_kids) + (len(md_files) if md_files else 0)`; emit reason like `"5/6 children have manifests; 1 skipped"`. `children_count = len(manifest_kids)` per D-02. |
| 131-138 | Fallback: children but no rule matched → `ambiguous` | leave unchanged (D-04) |
| 140-145 | Fallback: empty → `ambiguous` | leave unchanged (D-04) |

The CONTEXT.md line-range claims (`80-145` for the function, `132-145` for the fallback branch) are accurate; the planner can quote them in PLAN.md verbatim.

### Read-only context — `packages/vault-io/src/vault_io/init_vault.py`

| Line range | Content | Phase 25 action |
|------------|---------|------------------|
| **84-133** | `_resolve_pinned_containers` | **no edit.** The `if cls == "ambiguous"` branch at line 111-124 still functions correctly for fallback-ambiguous rows (D-05). |

CONTEXT.md cites lines 84-133 — accurate.

### Plugin shim — `plugins/graph-wiki/skills/graph-wiki/scripts/detect_containers.py`

Confirmed 9 lines total. Just a `from vault_io.detect_containers import main` + `if __name__ == "__main__": main()`. **No edit required** (D-06 auto-satisfied).

### Plugin reference doc — `plugins/graph-wiki/skills/graph-wiki/references/detection-workflow.md`

Currently (verified):
- Lines 10-17: numbered "Classification rules (first match wins)" — already enumerates rules including `package` (rule 3) and `ambiguous` (rule 6). The current rule-3 wording is *"immediate children are folders with package manifests"* (silent on the mixed-manifest case).
- Lines 30-36: "Ambiguous containers" subsection — currently says ambiguity fires when *"Some children have manifests and some don't (no clear majority pattern)"*. **This bullet point describes the old behavior and is now wrong** — under the new rule, mixed-manifest dirs are no longer ambiguous.

**Required edits per D-07/D-08:**
1. Tighten rule 3 (line 14) to clarify: *"≥1 immediate child has a package manifest. Non-manifested siblings and loose `.md` files at the container root are silently excluded from the wiki layout."*
2. Delete or revise the "some children have manifests and some don't" bullet in the "Ambiguous containers" subsection (line 33) — it now contradicts rule 3.
3. (Optional, satisfies D-08 fallback) The doc already describes the heuristic explicitly across rules 1-6, so no new "Rules" subsection is needed — the planner can mark D-08 as auto-satisfied.

### Plugin CLAUDE.md — `plugins/graph-wiki/CLAUDE.md`

Verified the two referenced sections:

- §"Wiki layout invariants" (line 54): *"Container detection runs through `detect_containers` and is interactive when classifications are ambiguous."* **Still true after D-12** — fallback-ambiguous classifications still trigger the interactive prompt path in `init_vault._resolve_pinned_containers` when `non_interactive=False`. **No edit required.**
- §"Iron rules the skill enforces" (lines 60-68): Rule 1 (code is source of truth) and Rule 4 (≥3 files touched per ingest/scan) — preserved by this phase; no edits.

**Conclusion:** The CONTEXT.md concern that *"the 'interactive' framing may need a small edit after D-12 — re-read before drafting"* — research finding: **no edit needed.** The interactive prompt path remains for fallback-ambiguous rows. The planner should explicitly note this in PLAN.md so a reviewer doesn't second-guess.

### Roadmap — `.planning/ROADMAP.md`

Phase 25 Success Criteria block is at **lines 130-135** (header "**Success Criteria** (what must be TRUE):" on line 130, numbered items 1-5 on lines 131-135).

| Line | Current text | Phase 25 edit |
|------|--------------|---------------|
| 131 | SC#1: bootstrap on this repo classifies `packages/` as `package` and creates `wiki/packages/` | **keep** (satisfied by code change) |
| 132 | SC#2: `_classify_dir` 5/6 fixture → `package`; unit test asserts | **keep** |
| 133 | SC#3: plugin classifier applies identical ≥80% majority heuristic | **revise per D-01**: the plugin classifier auto-inherits (D-06 — shim is a passthrough). Either reword to *"plugin-side classifier `…/scripts/detect_containers.py` imports the updated `vault_io.detect_containers` (no separate port)"*, or note the heuristic is now "≥1 manifest" not "≥80%". Recommend the former wording — it's the actual implementation guarantee. |
| 134 | SC#4: `--interactive` prompts on remaining ambiguous classifications | **REMOVE per D-12** |
| 135 | SC#5: todo moved to resolved AND `--interactive` flag visible in `bootstrap --help` | **revise per D-13**: drop the `--interactive` clause. Becomes simply *".planning/todos/pending/2026-05-20-fix-packages-dir-misclassification.md is moved to .planning/todos/resolved/"* |

After the edit, Phase 25 will have 4 success criteria (1, 2, revised-3, revised-5).

The planner must also update the **Phase 25 one-liner** at line 81 to drop the `--interactive` clause:
- Current: *"Bootstrap bug: `_classify_dir` majority-manifest heuristic, plugin-side classifier sync, `--interactive` flag, unit test, and todo resolution"*
- Suggested: *"Bootstrap bug: `_classify_dir` permissive heuristic, plugin-side classifier sync, unit tests, and todo resolution"*

### Todo move — `.planning/todos/pending/2026-05-20-fix-packages-dir-misclassification.md`

Verified the file exists with the YAML frontmatter `resolves_phase: 25`. D-11 says move to `resolved/`. The phase SUMMARY will live at `.planning/phases/25-packages-dir-misclassification-fix/25-SUMMARY.md` after completion — the planner should specify that the move task append a short "Resolved by Phase 25 — see [25-SUMMARY.md](…)" note to the frontmatter or as an appended section.

## Existing Tests Pass Under New Rule

Traced each of the 4 existing tests in `test_detect_containers.py` against the post-D-01..D-03 implementation:

| Test | Fixture shape relevant to rule 3 | Old rule outcome | New rule outcome | Pass? |
|------|----------------------------------|------------------|------------------|-------|
| `test_v2_layout_finds_repo_containers` | `packages/` has 2 children both with `pyproject.toml`; no loose `.md` | `package` (2/2, no md) | `package` (2 manifest_kids, 0 skipped) | ✅ |
| `test_workspace_path_excluded` | same fixture as above; asserts `graph-wiki` excluded | exclusion logic in `detect()`, not `_classify_dir` | unchanged | ✅ |
| `test_v1_layout_guard` | `packages/` has 1 child with `pyproject.toml`; no loose `.md` | `package` (1/1, no md) | `package` (1 manifest_kid, 0 skipped) | ✅ |
| `test_v2_synthetic_repo` | same fixture as test 1; asserts classification is `package` | `package` | `package` | ✅ |

**Conclusion:** All 4 existing tests pass without modification under the new rule (D-10 holds). The planner does not need to insert a "verify existing tests still pass" remediation task — but should include a verification step running `uv run --package vault-io pytest tests/test_detect_containers.py` as part of the implementation task.

## Test Strategy (D-09 + edge cases revealed by code reading)

D-09 specifies 3 tests. Reading the rewritten Rule 3 carefully, there are two additional edge cases worth pinning. Recommend adding them — the marginal cost is ~10 LOC and they lock the behavior `_classify_dir` will exhibit under the new rule:

| # | Test name (suggested) | Fixture | Assertion | Source |
|---|------------------------|---------|-----------|--------|
| 1 | `test_mixed_manifest_dirs_classify_as_package` | 5 children with `pyproject.toml`, 1 dir (`prompt_sources`) without | `classification == "package"`, `children_count == 5`, reason mentions "skipped" | D-09 #1 (the bug repro) |
| 2 | `test_loose_md_file_at_container_root_does_not_block_package` | 2 children with `package.json`, 1 loose `README.md` at container root | `classification == "package"`, `children_count == 2` | D-09 #2 |
| 3 | `test_empty_dir_falls_back_to_ambiguous` | empty dir (no children, no files) | `classification == "ambiguous"`, reason matches "empty or unrecognized" | D-09 #3 |
| 4 (recommended add) | `test_single_manifested_child_with_many_non_manifested_siblings_still_package` | 1 child with `pyproject.toml`, 5 dirs without manifests | `classification == "package"`, `children_count == 1` | edge case: confirms D-01's "≥1" semantics — even a single manifest kid wins. Without this test, "≥1" is implicit. |
| 5 (recommended add) | `test_no_manifest_kids_with_md_files_predominant_classifies_as_docs_not_ambiguous` | 0 manifest kids, 8 loose `.md` files at container root | `classification == "docs"` | regression guard: makes sure Rule 1 (docs) still fires when Rule 3 doesn't apply. Locks the rules-order invariant. |

All 5 tests use the inline `tmp_path` + `Path.write_text` pattern (matches existing `test_detect_containers.py` style). No new helpers needed.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|--------------|----------------|-----------|
| Container classification | `packages/vault-io` (library) | — | All real logic lives in vault-io; the plugin shim is a passthrough by design (plugin CLAUDE.md §"Source-of-truth split"). |
| Plugin-side CLI surfacing | `plugins/graph-wiki/.../scripts/detect_containers.py` | `packages/vault-io` (via import) | 9-line shim — touched only when adding a new entry point, not for behavior changes. |
| Bootstrap orchestration | `packages/vault-io/init_vault.py` | `agents/graph-wiki-agent/.../commands/init.py` | `_resolve_pinned_containers` consumes the classifier's output and decides `skip` vs prompt. Phase 25 does NOT touch this tier. |
| Doc lockstep | `plugins/graph-wiki/.../references/detection-workflow.md` | plugin CLAUDE.md (read-only) | Plugin CLAUDE.md mandates code+doc co-update; the reference doc is the doc half. |

This map is straightforward: this phase touches **one tier** (vault-io classifier) plus a doc and a roadmap. The planner should not see cross-tier tasks.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Manifest detection | New regex over `MANIFEST_FILES` | Existing `_has_manifest(d)` helper | Lines 52-53 of detect_containers.py; correct as-is. |
| Immediate subdir iteration | Reimplement `iterdir + filter` in the new branch | Existing `_immediate_subdirs(d)` helper | Lines 56-57 of detect_containers.py; already handles `SKIP_DIRS` + dotfile exclusion. |
| Test fixture construction | New helpers in tests/helpers.py | Inline `Path.mkdir` + `Path.write_text` in each test | Matches existing test style; helpers.py doesn't exist (see Inaccuracy 1). |
| Todo move | Complex move logic with note insertion | `git mv` + a short Markdown append | Standard pattern; see how prior phases resolved todos. |

## Common Pitfalls

### Pitfall 1: Rewriting `children_count` semantics in callers
**What goes wrong:** Some downstream code may have assumed `children_count` was the raw `len(children)`. After D-02, it becomes `len(manifest_kids)` — different value when there are non-manifested siblings.
**Why it happens:** The field name is generic; readers may infer the wrong meaning.
**How to avoid:** Grep for `children_count` across the codebase before merging. If any caller uses it for display purposes (not just for "did we find anything?"), update accordingly.
**Warning signs:** If a test in `test_init_vault.py` or `test_scan_monorepo.py` asserts a specific `children_count` value against a fixture that has non-manifested siblings, it would break. (No such test was found at research time — but the planner should grep to confirm.)

### Pitfall 2: Forgetting that detection-workflow.md's "Ambiguous containers" bullet contradicts the new rule
**What goes wrong:** If only rule 3 wording is updated and the lower "Ambiguous containers" subsection is left intact, readers see two contradictory statements.
**Why it happens:** The doc has two passes over the same topic — the rules list and a dedicated subsection.
**How to avoid:** Edit both spots in the same commit. Specifically delete the "Some children have manifests and some don't" bullet from line 33 (or rephrase to "It's empty or unrecognized.").
**Warning signs:** `grep -n "some children have manifests" plugins/graph-wiki/skills/graph-wiki/references/detection-workflow.md` returns a hit after the phase.

### Pitfall 3: Treating PKGCLS-03 as in-scope
**What goes wrong:** Planner sees PKGCLS-03 in the requirement list and writes an `--interactive` flag task.
**Why it happens:** The requirements file (REQUIREMENTS.md) still lists PKGCLS-03 as a Phase-25 requirement, but D-12 defers it.
**How to avoid:** PLAN.md must explicitly call out: *"PKGCLS-03 is deferred to a future backlog item per CONTEXT.md D-12; this phase does NOT modify `agents/graph-wiki-agent/src/graph_wiki_agent/commands/init.py`."*
**Warning signs:** Any task referencing `commands/init.py:88` or adding a Typer flag is wrong scope.

### Pitfall 4: Editing the plugin shim
**What goes wrong:** Planner sees `plugins/graph-wiki/skills/graph-wiki/scripts/detect_containers.py` in the requirement (PKGCLS-02) and writes an edit task.
**Why it happens:** PKGCLS-02 says "Plugin-side classifier updated to match" — sounds like an edit. D-06 says it's auto-satisfied because the shim already imports from vault-io.
**How to avoid:** PLAN.md must explicitly state: *"plugins/graph-wiki/skills/graph-wiki/scripts/detect_containers.py is a 9-line `from vault_io.detect_containers import main` shim — PKGCLS-02 is auto-satisfied. No edit task."*

## Code Examples

### Pattern for the rewritten Rule 3 (illustrative; planner & implementer to finalize wording)

```python
# Rule 3: package container — at least one immediate child has a manifest
if children:
    manifest_kids = [c for c in children if _has_manifest(c)]
    if manifest_kids:
        skipped_dirs = len(children) - len(manifest_kids)
        skipped_md = len(md_files)
        if skipped_dirs or skipped_md:
            reason = (
                f"{len(manifest_kids)}/{len(children)} children have manifests; "
                f"{skipped_dirs} dir(s) and {skipped_md} loose .md skipped"
            )
        else:
            reason = f"all {len(manifest_kids)} children have manifests"
        return {
            "source": d.name,
            "classification": "package",
            "children_count": len(manifest_kids),
            "reason": reason,
        }
```

Notes on this draft:
- Collapses the old "all-or-nothing" branch (lines 115-121) and the old "mixed → ambiguous" branch (lines 123-129) into one branch.
- Preserves the existing "all clean" reason wording when there's nothing to skip — minimizes diff against pre-fix output for the v2_workspace fixture and avoids any cosmetic test churn in the existing 4 tests.
- `children_count` = `len(manifest_kids)` per D-02.
- Wording in the "skipped" branch is the planner's discretion; the above is a verified-grammatical option.

### Pattern for the new unit test (matches existing style)

```python
def test_mixed_manifest_dirs_classify_as_package(tmp_path: Path) -> None:
    """5/6 manifested children → package, with 1 non-manifested sibling silently skipped.

    Regression: pre-D-01..D-03 this was 'ambiguous'. See
    .planning/todos/resolved/2026-05-20-fix-packages-dir-misclassification.md.
    """
    from vault_io.detect_containers import _classify_dir

    container = tmp_path / "packages"
    for name in ("core-bedrock", "eval-harness", "model-adapter", "subagent-runtime", "vault-io"):
        (container / name).mkdir(parents=True)
        (container / name / "pyproject.toml").write_text('[project]\nname="x"\n', encoding="utf-8")
    (container / "prompt_sources").mkdir()  # no manifest

    rec = _classify_dir(container)

    assert rec["classification"] == "package"
    assert rec["children_count"] == 5
```

Style notes:
- Inline `from vault_io.detect_containers import _classify_dir` matches the existing `from vault_io.detect_containers import detect` pattern.
- No `helpers.py` import needed.
- The fixture replicates this repo's actual layout (the bug repro from the todo file).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest ≥8.3 + pytest-asyncio 1.3.0 (asyncio not needed for these tests) |
| Config file | `pyproject.toml` in `packages/vault-io/` (workspace member) |
| Quick run command | `uv run --package vault-io pytest tests/test_detect_containers.py -x` |
| Full suite command | `uv run --package vault-io pytest` |
| Phase gate command | `uv run pytest` (full workspace) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| PKGCLS-01 | `_classify_dir` mixed-manifest → `package` | unit | `uv run --package vault-io pytest tests/test_detect_containers.py::test_mixed_manifest_dirs_classify_as_package -x` | ❌ new test |
| PKGCLS-01 | loose `.md` at container root no longer blocks `package` | unit | `… ::test_loose_md_file_at_container_root_does_not_block_package -x` | ❌ new test |
| PKGCLS-01 | empty dir still `ambiguous` (fallback retained) | unit | `… ::test_empty_dir_falls_back_to_ambiguous -x` | ❌ new test |
| PKGCLS-01 | single manifested child with non-manifested siblings still `package` (recommended) | unit | `… ::test_single_manifested_child_with_many_non_manifested_siblings_still_package -x` | ❌ new test |
| PKGCLS-01 | docs rule still fires when no manifest kids (regression guard, recommended) | unit | `… ::test_no_manifest_kids_with_md_files_predominant_classifies_as_docs_not_ambiguous -x` | ❌ new test |
| PKGCLS-01 | regression: existing 4 tests unchanged | unit | `uv run --package vault-io pytest tests/test_detect_containers.py -x` | ✅ existing |
| PKGCLS-02 | plugin shim still imports from vault_io | smoke | `python -c "from vault_io.detect_containers import main"` (existing CI) | ✅ existing |
| PKGCLS-04 | bootstrap on this repo creates `wiki/packages/` | operational (manual; not gated) | `uv run graph-wiki-agent bootstrap …` against this repo and grep output for `"packages": "classification": "package"` | manual |
| PKGCLS-05 | todo file moved | filesystem assertion | `test -f .planning/todos/resolved/2026-05-20-fix-packages-dir-misclassification.md && ! test -f .planning/todos/pending/2026-05-20-fix-packages-dir-misclassification.md` | will exist after move |

### Sampling Rate
- **Per task commit:** `uv run --package vault-io pytest tests/test_detect_containers.py -x` (~1 second)
- **Per wave merge:** N/A — single PLAN, single wave
- **Phase gate:** `uv run pytest` full workspace green before `/gsd:verify-work`

### Wave 0 Gaps
- None. Existing test infrastructure (`conftest.py` with `tmp_repo`, `write_file`) covers all phase requirements. No new helpers, no new framework setup.

## Runtime State Inventory

This phase is a code edit + doc edit + todo move + roadmap edit. No persistent runtime state involved.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — verified by reading the bug report; the fix changes how new bootstraps classify, not how prior bootstraps stored anything. Any wiki/CLAUDE.md layout block written under the OLD rule already pinned its `packages/` row as either `skip` (the bug) or got manually patched. **The user already manually patched this repo's `wiki/CLAUDE.md`** per the todo file. New bootstraps on other repos will use the new rule. | None for the phase. Pat may want to re-run bootstrap on this repo with `--force` after the fix lands — out of scope. |
| Live service config | None — no external services involved | None |
| OS-registered state | None | None |
| Secrets/env vars | None — `GRAPH_WIKI_WORKSPACE` env var is unaffected | None |
| Build artifacts | None — `vault-io` is a uv workspace member installed editable, so the code change takes effect on next import. No egg-info regeneration needed. | None |

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11+ | all of vault-io | ✓ (project floor) | — | — |
| pytest ≥8.3 | new unit tests | ✓ (workspace dep group) | — | — |
| `uv` workspace tooling | running tests | ✓ (project standard) | — | — |

No external services, no DB, no Docker, no LLM calls. The classifier is pure stdlib (`pathlib.Path`, `argparse`, `json`). The new tests are pure stdlib + pytest.

## Project Constraints (from CLAUDE.md)

Relevant to this phase:

- **Source-of-truth split:** Behavior changes happen in `packages/vault-io/`; the plugin shim is not edited (auto-inherits). This phase honors that strictly.
- **Tests live in the package, not the plugin tree:** New tests go in `packages/vault-io/tests/test_detect_containers.py`. This phase honors that.
- **Doc + code lockstep invariant:** plugin CLAUDE.md §"When changing how layout is detected, classified, or written…" mandates updating `references/detection-workflow.md` together. D-07/D-08 honor this — the planner must put the doc edit in the same commit as the code edit (or at minimum the same phase + verified in a single review).
- **Iron Rule 1 ("code is source of truth"):** This phase fixes a bug where the code's classifier was too strict — the new rule lets the code match what real monorepos actually look like. Aligns with the rule.
- **`vault-io` write path through `layout_io.py`:** Not relevant — this phase does not write any layout. (Worth noting because a careless planner might propose updating an example layout block in the docs. Skip that — it's not needed.)
- **GSD workflow:** This phase is being planned via `/gsd:plan-phase` after `/gsd:discuss-phase`. Standard workflow applies.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `children_count` field is not used as a strict-equality assertion target by any test outside `test_detect_containers.py` | Pitfall 1 | If wrong: another test breaks unexpectedly when D-02 lands. Mitigation: planner should grep `children_count` across the workspace before merging. **[ASSUMED — grep not performed at research time]** |
| A2 | The user's wording for the "Rules" subsection of `detection-workflow.md` (D-08) is satisfied by the existing rules-list and does not require a new heading | "Plugin reference doc" section above | Low risk; if the user actually wants a separate heading the planner can pivot in the task description. |
| A3 | The plugin shim at `…/scripts/detect_containers.py` truly auto-inherits — i.e. the running `uv` workspace symlinks `vault_io` correctly when the plugin script is invoked via `uv run --project "$AGENT_RESEARCH_ROOT"` | D-06 / Pitfall 4 | Verified statically (shim is a passthrough import), but not via an end-to-end run during research. Standard workflow per plugin CLAUDE.md says this works; consider a one-line smoke test in the verification step. |

## Open Questions

1. **Should `children_count` field be renamed to reflect D-02 semantics?**
   - What we know: D-02 changes the meaning silently from "raw kids" to "manifest kids" for the `package` classification.
   - What's unclear: Whether downstream readers (the LLM that consumes the JSON output of `detect_containers --json` during bootstrap interactive flows) will silently get confused.
   - Recommendation: **Don't rename in this phase.** The field name is locked by D-02's wording ("`children_count` reports `len(manifest_kids)`"). If a rename is wanted, defer to a follow-up.

2. **Does the wiki/CLAUDE.md on Pat's local repo need to be updated post-fix?**
   - What we know: The user manually patched `wiki/CLAUDE.md` after hitting the bug.
   - What's unclear: Whether re-running `graph-wiki-agent bootstrap --force` on this repo will overwrite the manual patch correctly.
   - Recommendation: **Out of scope for this phase.** Pat may want to re-bootstrap after the fix lands — but that's a user action, not a phase task.

## Sources

### Primary (HIGH confidence)
- Filesystem read of `packages/vault-io/src/vault_io/detect_containers.py` (this worktree, 2026-05-21)
- Filesystem read of `packages/vault-io/tests/test_detect_containers.py` + `tests/conftest.py` (this worktree, 2026-05-21)
- Filesystem read of `plugins/graph-wiki/skills/graph-wiki/scripts/detect_containers.py` (9-line shim confirmed)
- Filesystem read of `plugins/graph-wiki/skills/graph-wiki/references/detection-workflow.md`
- Filesystem read of `plugins/graph-wiki/CLAUDE.md` (sections "Wiki layout invariants" and "Iron rules")
- `.planning/REQUIREMENTS.md` PKGCLS-01..05 (lines 54-62 + traceability 109-113)
- `.planning/ROADMAP.md` Phase 25 block (lines 126-135) and one-liner (line 81)
- `.planning/todos/pending/2026-05-20-fix-packages-dir-misclassification.md` (original bug report)
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/init.py:88` — `non_interactive=True` hardcoding confirmed
- `packages/vault-io/src/vault_io/init_vault.py` lines 84-133 — `_resolve_pinned_containers` confirmed

### Secondary (MEDIUM confidence)
- Trace of existing-test pass/fail outcomes under the new rule (analytical, not run live)
- Mapping of `children_count` consumers across the codebase (Pitfall 1 / A1 — grep not performed)

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- File:line targets: HIGH — verified against worktree
- Existing-tests-pass claim: HIGH — traced each test analytically
- `helpers.py` non-existence: HIGH — verified by filesystem scan
- PKGCLS-04 not binding `--interactive`: HIGH — quoted requirements text directly
- Plugin CLAUDE.md "interactive" framing still valid: MEDIUM — reasoned from `_resolve_pinned_containers` behavior, no live UAT

**Research date:** 2026-05-21
**Valid until:** 2026-06-21 (30 days; this phase should ship well before then)

---

## RESEARCH COMPLETE

**Phase:** 25 — packages-dir-misclassification-fix
**Confidence:** HIGH

### Five things the planner needs to know

1. **CONTEXT.md says `tests/helpers.py` exports `tmp_repo`/`write_pkg`/`write_file`/`write_claude_plugin` — it doesn't exist.** Only `tmp_repo` and `write_file` exist (in `conftest.py`); `write_pkg` and `write_claude_plugin` are not in the codebase. New tests should inline their fixture construction (matches the existing 4 tests' style).
2. **PKGCLS-04 does NOT mandate `--interactive`** — verified against REQUIREMENTS.md wording. The "without `--interactive`" clause describes the operational mode, not a flag requirement. No planner adjustment needed.
3. **Existing 4 tests all pass under the new rule without modification** (D-10 holds, verified by analytical trace). No remediation tasks needed for the existing test file.
4. **File:line targets in CONTEXT.md are accurate.** `_classify_dir` is at lines 80-145; the mixed-manifest branch to delete is lines 122-129 (CONTEXT.md said "Rule 3 branch" — concretely it's both lines 115-121 + 123-129, collapsed into one new branch). Fallback `ambiguous` branches at 131-145 stay. `_resolve_pinned_containers` at 84-133 is read-only. The plugin shim is 9 lines and auto-inherits — do not edit it.
5. **ROADMAP.md edits are at lines 130-135 (Success Criteria) + line 81 (one-liner).** Drop SC#4 entirely; revise SC#3 (the ≥80% heuristic wording is now `≥1`); revise SC#5 to drop the `--interactive` flag-visibility clause. Plugin CLAUDE.md's "interactive" framing still applies to fallback-ambiguous rows — **no edit needed there**.

### File Created
`/Users/pat/Personal/agent-research/.claude/worktrees/phase-25-discuss/.planning/phases/25-packages-dir-misclassification-fix/25-RESEARCH.md`

### Ready for Planning
Yes. Recommend the planner produce a single PLAN.md with ~6 tasks: (1) rewrite `_classify_dir` Rule 3 branch; (2) add 3-5 new unit tests; (3) update `detection-workflow.md` (rule 3 wording + delete contradicting bullet); (4) move todo to `resolved/` with a "resolved by Phase 25" note; (5) edit ROADMAP.md Phase 25 block (line 81 + lines 130-135 SC list); (6) verification step running `uv run pytest`.
