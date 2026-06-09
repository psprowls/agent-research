# graph-wiki:workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Status/kind-driven dispatcher for work items: `gw work next` (read-only routing decision) + `gw work advance` (single mutation point) + a thin `/graph-wiki:workflow` skill that dispatches one stage skill per invocation.

**Architecture:** Pure routing logic in `work-io` (`workflow.py` — a function over `(kind, status, phase, effort)`), async orchestrators in `graph-wiki-core/commands/work.py`, thin Typer wrappers in `graph-wiki-cli`, prose-thin skill in the plugin. New `phase` frontmatter key tracks pipeline position; `status` semantics unchanged. Four new lint rules (19 → 23), all presence-gated so existing items lint clean.

**Tech Stack:** Python 3.11, uv workspace, Typer, pytest. No Bedrock dependency anywhere in this plan — deterministic file I/O only.

**Spec:** `docs/superpowers/specs/2026-06-09-graph-wiki-workflow-design.md`

---

## Design notes the spec leaves implicit (read first)

These decisions were made while mapping the spec onto the existing code. They are load-bearing for the tasks below:

1. **`advance` applies `on_dispatch or on_complete`.** `route()` returns both transitions. When a dispatch precondition isn't met yet (phase absent, or execute-stage status ≠ `in-progress`), `on_dispatch` is non-None and `advance` applies *it*. Once applied, re-routing the new state returns `on_dispatch=None`, so the next `advance` call applies `on_complete`. This is how "first dispatch sets phase" and the spec's two-step execute transition both work without special-casing.
2. **`on_dispatch` appears for first dispatch too**, not just the execute stage. Setting `phase: design` on a fresh item is a frontmatter change needed *before* the stage runs; the same mechanism handles it. The spec's JSON example omits `on_dispatch` for a fresh bug, but section 1 says "first dispatch sets it" — this is the mechanism.
3. **`plan-or-execute` is a reporting sentinel, never written.** When a bug-like item's design-complete transition can't be decided without `effort`, `on_complete.phase` is the literal string `"plan-or-execute"` with `requires: ["effort"]` (matches the spec's JSON example). `advance` refuses to apply any transition whose `requires` includes `effort` and errors with a clear message — that error is the skill's prompt hook.
4. **`spec_doc`/`plan_doc` are stamped unconditionally** at design/plan completion (not only when the file exists). The new `artifact-doc-missing` lint rule (warn) catches stamped-but-missing files, and `advance` re-runs lint and reports findings, so a missing artifact is surfaced immediately. Stamping unconditionally also makes "came through plan" detection (`has_plan_doc` → subagent-driven-development vs TDD) a pipeline fact, not a filesystem fact.
5. **Rule 11 (`plan-action-target-missing`) gets a workspace fallback.** The plan-table row that `advance` inserts references `raw/plans/<slug>.md`, which lives under the *workspace*, not the repo. Without the fallback, every workflow-managed item would trip rule 11. The amendment: a path token passes if it exists under `repo_root` **or** `workspace_root`.
6. **Frontmatter round-trip:** `work_io.frontmatter.parse` leaves the body with its leading newline intact (one `\n` is consumed by the closing fence). Reconstruction is `emit(fm) + "\n" + body` — NOT `+ "\n\n" +` (that's only correct for freshly-built bodies like `run_work_file` uses).
7. **Slug = file stem.** Work items live at `wiki/work/<stem>.md` where the stem includes the date prefix (e.g. `2026-06-09-fix-login-timeout`). All CLI slug arguments and artifact filenames use the full stem.
8. **MCP surface is untouched** — it does not expose work commands today, and the spec doesn't ask for it.

## File structure

| File | Action | Responsibility |
|---|---|---|
| `packages/work-io/src/work_io/lifecycle_lint.py` | Modify | `VALID_EFFORTS`, `VALID_PHASES`, rules 20–23, rule-11 workspace fallback, `workspace_root` param |
| `packages/work-io/src/work_io/plan_table.py` | Modify | `ensure_plan_row()` — idempotent `## Plan` row insertion |
| `packages/work-io/src/work_io/workflow.py` | Create | Pure routing table: `WorkItemState`, `Transition`, `RouteResult`, `route()` |
| `packages/work-io/tests/unit/test_lifecycle_lint.py` | Modify | Tests for rules 20–23 + rule-11 fallback |
| `packages/work-io/tests/unit/test_plan_table.py` | Modify | Tests for `ensure_plan_row` |
| `packages/work-io/tests/unit/test_workflow.py` | Create | Every routing cell, shortcut, effort-required, terminal refusal |
| `packages/graph-wiki-core/src/graph_wiki_core/commands/work.py` | Modify | `run_work_next`, `run_work_advance`, `workspace_root` pass-through in `run_work_lint` |
| `packages/graph-wiki-core/tests/unit/test_commands_workflow.py` | Create | JSON contract, frontmatter mutation, plan-table sync, sidecar regen, full pipeline walk |
| `packages/graph-wiki-cli/src/graph_wiki_cli/work_cli/main.py` | Modify | `gw work next`, `gw work advance` Typer wrappers; `--effort` help text |
| `plugins/graph-wiki/skills/workflow/SKILL.md` | Create | The dispatcher skill (prose-thin) |
| `plugins/graph-wiki/commands/workflow.md` | Create | `/graph-wiki:workflow <slug>` thin command |
| `plugins/graph-wiki/skills/graph-wiki/references/lifecycle-rules.md` | Modify | Document rules 20–23 |
| `plugins/graph-wiki/commands/lint.md` | Modify | "19 rules" → "23 rules" |

---

### Task 1: Enums + four lint rules + rule-11 workspace fallback

**Files:**
- Modify: `packages/work-io/src/work_io/lifecycle_lint.py`
- Test: `packages/work-io/tests/unit/test_lifecycle_lint.py`

- [ ] **Step 1: Write the failing tests**

Append to `packages/work-io/tests/unit/test_lifecycle_lint.py` (the `_item` helper at the top of the file already forwards `**extra` into frontmatter):

```python
# --- Workflow rules (20-23) ---


def test_effort_not_in_enum_warns() -> None:
    findings = run_lint([_item(effort="small")], None, None)
    f = next(f for f in findings if f.rule_id == "effort-not-in-enum")
    assert f.severity == "warn"


def test_effort_valid_ok() -> None:
    findings = run_lint([_item(effort="xs")], None, None)
    assert "effort-not-in-enum" not in _rule_ids(findings)


def test_effort_absent_ok() -> None:
    findings = run_lint([_item()], None, None)
    assert "effort-not-in-enum" not in _rule_ids(findings)


def test_phase_not_in_enum_errors() -> None:
    findings = run_lint([_item(phase="designing")], None, None)
    f = next(f for f in findings if f.rule_id == "phase-not-in-enum")
    assert f.severity == "error"


def test_phase_valid_ok() -> None:
    findings = run_lint([_item(phase="design")], None, None)
    assert "phase-not-in-enum" not in _rule_ids(findings)


def test_phase_absent_ok() -> None:
    findings = run_lint([_item()], None, None)
    assert "phase-not-in-enum" not in _rule_ids(findings)


def test_phase_status_incoherent_accepted_design() -> None:
    plan = PlanResult(state="ok", rows=[{"action": "x", "done_when": "", "rationale": ""}])
    findings = run_lint([_item(status="accepted", phase="design", plan=plan)], None, None)
    f = next(f for f in findings if f.rule_id == "phase-status-incoherent")
    assert f.severity == "warn"


def test_phase_status_coherent_accepted_execute() -> None:
    plan = PlanResult(state="ok", rows=[{"action": "x", "done_when": "", "rationale": ""}])
    findings = run_lint([_item(status="accepted", phase="execute", plan=plan)], None, None)
    assert "phase-status-incoherent" not in _rule_ids(findings)


def test_phase_status_open_design_not_in_compat_map() -> None:
    findings = run_lint([_item(status="open", phase="design")], None, None)
    assert "phase-status-incoherent" not in _rule_ids(findings)


def test_phase_status_in_progress_design_incoherent() -> None:
    findings = run_lint([_item(status="in-progress", phase="design", owner="pat")], None, None)
    assert "phase-status-incoherent" in _rule_ids(findings)


def test_artifact_doc_missing(tmp_path) -> None:
    findings = run_lint(
        [_item(spec_doc="raw/specs/test-item.md")], None, None, workspace_root=tmp_path
    )
    f = next(f for f in findings if f.rule_id == "artifact-doc-missing")
    assert f.severity == "warn"


def test_artifact_doc_present_ok(tmp_path) -> None:
    (tmp_path / "raw" / "specs").mkdir(parents=True)
    (tmp_path / "raw" / "specs" / "test-item.md").write_text("# spec\n")
    findings = run_lint(
        [_item(spec_doc="raw/specs/test-item.md")], None, None, workspace_root=tmp_path
    )
    assert "artifact-doc-missing" not in _rule_ids(findings)


def test_artifact_doc_skipped_without_workspace_root() -> None:
    findings = run_lint([_item(plan_doc="raw/plans/test-item.md")], None, None)
    assert "artifact-doc-missing" not in _rule_ids(findings)


def test_plan_action_target_in_workspace_passes_rule_11(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    workspace = tmp_path / "ws"
    (workspace / "raw" / "plans").mkdir(parents=True)
    (workspace / "raw" / "plans" / "test-item.md").write_text("# plan\n")
    plan = PlanResult(
        state="ok",
        rows=[{"action": "Execute implementation plan: raw/plans/test-item.md", "done_when": "merged", "rationale": ""}],
    )
    findings = run_lint([_item(status="accepted", plan=plan)], repo, None, workspace_root=workspace)
    assert "plan-action-target-missing" not in _rule_ids(findings)
```

Note: `test_artifact_doc_missing` and `test_artifact_doc_present_ok` pass `tmp_path` — add `from pathlib import Path` is NOT needed (pytest injects `tmp_path` as a fixture; no annotation required).

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --package work-io pytest tests/unit/test_lifecycle_lint.py -v -k "effort or phase or artifact or workspace"`
Expected: FAIL — `TypeError: run_lint() got an unexpected keyword argument 'workspace_root'` for the workspace tests, and missing rule-ids for the rest.

- [ ] **Step 3: Implement the rules**

In `packages/work-io/src/work_io/lifecycle_lint.py`:

3a. Update the module docstring (line 1):

```python
"""23 lifecycle lint rules for work items."""
```

3b. Add the new enums after `FEATURE_LIKE_KINDS` (line 17):

```python
VALID_EFFORTS = frozenset({"xs", "s", "m", "l", "xl"})
VALID_PHASES = frozenset({"design", "plan", "execute", "finish", "done"})

# Rule 22 compatibility map: statuses listed here constrain which phases are coherent.
# Statuses absent from the map (open, mitigated, wontfix, superseded) are unconstrained.
_PHASE_COMPAT = {
    "accepted": frozenset({"execute", "finish", "done"}),
    "in-progress": frozenset({"execute", "finish"}),
    "resolved": frozenset({"done"}),
}
```

3c. Change the `run_lint` signature and docstring:

```python
def run_lint(
    items: list[dict],
    repo_root: Path | None,
    sidecar: dict | None,
    workspace_root: Path | None = None,
) -> list[LintFinding]:
    """Run all 23 lifecycle rules. Each item dict has keys: slug, fm, plan (PlanResult).

    workspace_root enables the workspace-relative checks (rule 23, and the
    workspace fallback in rule 11); when None those checks are skipped.
    """
```

3d. Amend rule 11's inner check (currently `if not token.startswith("http") and not (repo_root / token).exists():`) to:

```python
                for token in _PATH_RE.findall(row.get("action", "")):
                    if token.startswith("http"):
                        continue
                    if (repo_root / token).exists():
                        continue
                    if workspace_root is not None and (workspace_root / token).exists():
                        continue
                    findings.append(
                        LintFinding(
                            "plan-action-target-missing",
                            "error",
                            slug,
                            f"plan action references {token!r} which does not exist under repo root",
                        )
                    )
```

3e. Add rules 20–23 inside the per-item loop, after rule 17 (`plan-table-malformed`) and before the `# 18. sidecar-missing` global block:

```python
        # 20. effort-not-in-enum (presence-gated; legacy free-text efforts degrade to warnings)
        effort = fm.get("effort")
        if effort and str(effort) not in VALID_EFFORTS:
            findings.append(
                LintFinding("effort-not-in-enum", "warn", slug, f"effort {effort!r} not in {sorted(VALID_EFFORTS)}")
            )

        # 21. phase-not-in-enum (presence-gated)
        phase = fm.get("phase")
        if phase and str(phase) not in VALID_PHASES:
            findings.append(
                LintFinding("phase-not-in-enum", "error", slug, f"phase {phase!r} not in {sorted(VALID_PHASES)}")
            )

        # 22. phase-status-incoherent (warn — humans may hand-edit status)
        if phase and status in _PHASE_COMPAT and str(phase) not in _PHASE_COMPAT[status]:
            findings.append(
                LintFinding(
                    "phase-status-incoherent",
                    "warn",
                    slug,
                    f"status {status!r} expects phase in {sorted(_PHASE_COMPAT[status])}, got {phase!r}",
                )
            )

        # 23. artifact-doc-missing (skipped when workspace_root is None)
        if workspace_root is not None:
            for doc_key in ("spec_doc", "plan_doc"):
                doc = fm.get(doc_key)
                if doc and not (workspace_root / str(doc)).exists():
                    findings.append(
                        LintFinding(
                            "artifact-doc-missing",
                            "warn",
                            slug,
                            f"{doc_key} {doc!r} does not exist under the workspace",
                        )
                    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run --package work-io pytest tests/unit/test_lifecycle_lint.py -v`
Expected: ALL PASS (new tests and the 19-rule originals).

- [ ] **Step 5: Commit**

```bash
git add packages/work-io/src/work_io/lifecycle_lint.py packages/work-io/tests/unit/test_lifecycle_lint.py
git commit -m "feat(work-io): effort/phase enums + lint rules 20-23 with workspace-aware checks"
```

---

### Task 2: `ensure_plan_row` in plan_table.py

**Files:**
- Modify: `packages/work-io/src/work_io/plan_table.py`
- Test: `packages/work-io/tests/unit/test_plan_table.py`

- [ ] **Step 1: Write the failing tests**

In `packages/work-io/tests/unit/test_plan_table.py`, add `ensure_plan_row` to the existing `from work_io.plan_table import ...` line at the top of the file (a mid-file import would trip ruff E402), then append:

```python
# --- ensure_plan_row ---


def test_ensure_plan_row_appends_section_when_heading_missing() -> None:
    body = "## Summary\nsome text\n"
    out = ensure_plan_row(body, action="Do the thing", done_when="It is done", rationale="Because")
    result = parse_plan(out)
    assert result.state == "ok"
    assert result.rows == [{"action": "Do the thing", "done_when": "It is done", "rationale": "Because"}]
    assert "## Summary" in out  # existing content preserved


def test_ensure_plan_row_appends_to_existing_table() -> None:
    body = (
        "## Plan\n\n"
        "| Action | Done when | Rationale |\n"
        "| --- | --- | --- |\n"
        "| First row | done | why |\n"
    )
    out = ensure_plan_row(body, action="Second row", done_when="later", rationale="more")
    result = parse_plan(out)
    assert [r["action"] for r in result.rows] == ["First row", "Second row"]


def test_ensure_plan_row_fills_empty_table() -> None:
    body = "## Plan\n\n| Action | Done when | Rationale |\n| --- | --- | --- |\n"
    out = ensure_plan_row(body, action="Only row", done_when="d", rationale="r")
    result = parse_plan(out)
    assert result.state == "ok"
    assert result.rows[0]["action"] == "Only row"


def test_ensure_plan_row_repairs_malformed_section() -> None:
    body = "## Plan\nfreeform prose, no table\n"
    out = ensure_plan_row(body, action="Row", done_when="d", rationale="r")
    result = parse_plan(out)
    assert result.state == "ok"
    assert "freeform prose, no table" in out  # prose preserved below the inserted table


def test_ensure_plan_row_idempotent() -> None:
    body = "## Summary\nx\n"
    once = ensure_plan_row(body, action="Row", done_when="d", rationale="r")
    twice = ensure_plan_row(once, action="Row", done_when="d", rationale="r")
    assert once == twice
```

If `test_plan_table.py` does not already import `parse_plan` at the top, the existing tests guarantee it does — verify and reuse.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --package work-io pytest tests/unit/test_plan_table.py -v -k ensure_plan_row`
Expected: FAIL with `ImportError: cannot import name 'ensure_plan_row'`.

- [ ] **Step 3: Implement `ensure_plan_row`**

Append to `packages/work-io/src/work_io/plan_table.py` (after `parse_plan`, before `_split_row`):

```python
_PLAN_TABLE_HEADER = ["| Action | Done when | Rationale |", "| --- | --- | --- |"]


def ensure_plan_row(body: str, *, action: str, done_when: str, rationale: str) -> str:
    """Return body with a ## Plan table containing the given row.

    Creates the heading and table when absent; appends to an existing table;
    inserts a fresh table under a malformed heading (prose preserved below).
    Idempotent: a row whose action cell already matches is not duplicated.
    """
    existing = parse_plan(body)
    if existing.state == "ok" and any(r["action"] == action for r in existing.rows):
        return body

    row = f"| {action} | {done_when} | {rationale} |"
    lines = body.splitlines()

    plan_idx = None
    for i, line in enumerate(lines):
        if re.match(r"^##\s+plan\s*$", line.strip(), re.IGNORECASE):
            plan_idx = i
            break

    if plan_idx is None:
        out = list(lines)
        if out and out[-1].strip():
            out.append("")
        out += ["## Plan", "", *_PLAN_TABLE_HEADER, row]
        return "\n".join(out) + "\n"

    if existing.state in ("ok", "empty"):
        # Insert the row after the last contiguous table line below the heading.
        last_table = plan_idx
        for j in range(plan_idx + 1, len(lines)):
            if lines[j].strip().startswith("|"):
                last_table = j
            elif last_table != plan_idx:
                break
        return "\n".join(lines[: last_table + 1] + [row] + lines[last_table + 1 :]) + "\n"

    # malformed: heading present, no table — insert a fresh table right below the heading.
    return "\n".join(lines[: plan_idx + 1] + ["", *_PLAN_TABLE_HEADER, row] + lines[plan_idx + 1 :]) + "\n"
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run --package work-io pytest tests/unit/test_plan_table.py -v`
Expected: ALL PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/work-io/src/work_io/plan_table.py packages/work-io/tests/unit/test_plan_table.py
git commit -m "feat(work-io): ensure_plan_row — idempotent ## Plan table row insertion"
```

---

### Task 3: The routing table (`work_io/workflow.py`)

**Files:**
- Create: `packages/work-io/src/work_io/workflow.py`
- Create: `packages/work-io/tests/unit/test_workflow.py`

- [ ] **Step 1: Write the failing tests**

Create `packages/work-io/tests/unit/test_workflow.py`:

```python
from __future__ import annotations

import pytest

from work_io.workflow import PLAN_OR_EXECUTE, Transition, WorkItemState, route


def _state(kind: str = "feature", status: str = "open", phase: str | None = None, effort: str | None = None,
           has_plan_doc: bool = False) -> WorkItemState:
    return WorkItemState(kind=kind, status=status, phase=phase, effort=effort, has_plan_doc=has_plan_doc)


# --- Validation blockers ---


@pytest.mark.parametrize(
    "state",
    [
        _state(kind="epic"),
        _state(status="todo"),
        _state(phase="designing"),
        _state(effort="small"),
    ],
)
def test_invalid_enums_block(state: WorkItemState) -> None:
    r = route(state)
    assert r.skill is None
    assert r.blockers


# --- Terminal / mitigated / done ---


@pytest.mark.parametrize("status", ["resolved", "wontfix", "superseded", "mitigated"])
def test_terminal_and_mitigated_never_dispatch(status: str) -> None:
    r = route(_state(status=status, phase="execute"))
    assert r.skill is None
    assert r.on_dispatch is None and r.on_complete is None
    assert r.blockers


def test_phase_done_reports_complete() -> None:
    r = route(_state(status="resolved", phase="done"))
    assert r.skill is None
    assert r.blockers  # report-and-exit surfaces as a blocker for uniform CLI handling


# --- First dispatch (entry) ---


@pytest.mark.parametrize("kind", ["feature", "initiative", "spike", "tech-debt"])
def test_entry_design_first_kinds_get_brainstorming(kind: str) -> None:
    r = route(_state(kind=kind))
    assert r.skill == "brainstorming"
    assert r.artifact_slot == "specs"
    assert r.on_dispatch == Transition(phase="design")


@pytest.mark.parametrize("kind", ["bug", "security", "perf"])
def test_entry_diagnosis_kinds_get_systematic_debugging(kind: str) -> None:
    r = route(_state(kind=kind))
    assert r.skill == "systematic-debugging"
    assert r.artifact_slot == "specs"
    assert r.on_dispatch == Transition(phase="design")


def test_entry_requires_open_status() -> None:
    r = route(_state(status="accepted", phase=None))
    assert r.skill is None
    assert r.blockers


def test_entry_test_gap_without_effort_blocks() -> None:
    r = route(_state(kind="test-gap"))
    assert r.skill is None
    assert any("effort" in b for b in r.blockers)


@pytest.mark.parametrize("effort", ["xs", "s"])
def test_entry_test_gap_small_goes_straight_to_execute(effort: str) -> None:
    r = route(_state(kind="test-gap", effort=effort))
    assert r.skill == "test-driven-development"
    assert r.on_dispatch == Transition(phase="execute", status="in-progress", requires=("owner",))


@pytest.mark.parametrize("effort", ["m", "l", "xl"])
def test_entry_test_gap_large_goes_to_plan(effort: str) -> None:
    r = route(_state(kind="test-gap", effort=effort))
    assert r.skill == "writing-plans"
    assert r.artifact_slot == "plans"
    assert r.on_dispatch == Transition(phase="plan")


# --- Design stage ---


def test_design_bug_like_small_effort_shortcuts_to_execute() -> None:
    r = route(_state(kind="bug", phase="design", effort="s"))
    assert r.skill == "systematic-debugging"
    assert r.on_dispatch is None
    assert r.on_complete == Transition(phase="execute", stamp_doc="spec_doc")


def test_design_bug_like_large_effort_goes_to_plan() -> None:
    r = route(_state(kind="tech-debt", phase="design", effort="l"))
    assert r.skill == "brainstorming"
    assert r.on_complete == Transition(phase="plan", stamp_doc="spec_doc")


def test_design_bug_like_missing_effort_reports_fork_sentinel() -> None:
    r = route(_state(kind="bug", phase="design"))
    assert r.skill == "systematic-debugging"
    assert not r.blockers  # dispatch is fine; only completion needs effort
    assert r.on_complete == Transition(phase=PLAN_OR_EXECUTE, requires=("effort",), stamp_doc="spec_doc")


@pytest.mark.parametrize("kind", ["feature", "initiative", "spike"])
def test_design_feature_like_always_plans_even_when_small(kind: str) -> None:
    r = route(_state(kind=kind, phase="design", effort="xs"))
    assert r.on_complete == Transition(phase="plan", stamp_doc="spec_doc")


# --- Plan stage ---


def test_plan_stage_routes_to_writing_plans() -> None:
    r = route(_state(kind="feature", phase="plan"))
    assert r.skill == "writing-plans"
    assert r.artifact_slot == "plans"
    assert r.on_complete == Transition(
        phase="execute", status="accepted", sync_plan_table=True, stamp_doc="plan_doc"
    )


# --- Execute stage ---


def test_execute_with_plan_doc_uses_subagent_driven_development() -> None:
    r = route(_state(kind="feature", status="accepted", phase="execute", has_plan_doc=True))
    assert r.skill == "subagent-driven-development"
    assert r.on_dispatch == Transition(status="in-progress", requires=("owner",))
    assert r.on_complete == Transition(phase="finish")


def test_execute_shortcut_path_uses_tdd() -> None:
    r = route(_state(kind="bug", status="open", phase="execute", effort="s"))
    assert r.skill == "test-driven-development"
    assert r.on_dispatch == Transition(status="in-progress", requires=("owner",))


def test_execute_already_in_progress_has_no_dispatch_transition() -> None:
    r = route(_state(kind="bug", status="in-progress", phase="execute", effort="s"))
    assert r.on_dispatch is None
    assert r.on_complete == Transition(phase="finish")


# --- Finish stage ---


def test_finish_routes_to_finishing_a_development_branch() -> None:
    r = route(_state(kind="feature", status="in-progress", phase="finish"))
    assert r.skill == "finishing-a-development-branch"
    assert r.on_complete == Transition(phase="done", status="resolved", requires=("resolved_in",))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --package work-io pytest tests/unit/test_workflow.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'work_io.workflow'`.

- [ ] **Step 3: Implement the routing table**

Create `packages/work-io/src/work_io/workflow.py`:

```python
"""Routing table for the work-item workflow: (kind, status, phase, effort) -> action.

Pure functions, no I/O. `route()` returns the stage skill to dispatch plus the
dispatch-time and completion-time transitions. `gw work next` reports the
result; `gw work advance` applies `on_dispatch or on_complete` as the single
mutation point. Kind variants later are one-row edits here.
"""

from __future__ import annotations

from dataclasses import dataclass

from work_io.lifecycle_lint import (
    BUG_LIKE_KINDS,
    TERMINAL_STATUSES,
    VALID_EFFORTS,
    VALID_KINDS,
    VALID_PHASES,
    VALID_STATUSES,
)

SMALL_EFFORTS = frozenset({"xs", "s"})
DIAGNOSIS_KINDS = frozenset({"bug", "security", "perf"})

# Sentinel phase reported when the design-complete fork cannot be decided
# without an effort value. Never written to frontmatter — `advance` refuses
# any transition that still requires effort.
PLAN_OR_EXECUTE = "plan-or-execute"


@dataclass(frozen=True)
class WorkItemState:
    kind: str
    status: str
    phase: str | None = None
    effort: str | None = None
    has_plan_doc: bool = False


@dataclass(frozen=True)
class Transition:
    """A single frontmatter mutation. None fields are left unchanged."""

    phase: str | None = None
    status: str | None = None
    requires: tuple[str, ...] = ()
    sync_plan_table: bool = False
    stamp_doc: str | None = None  # "spec_doc" | "plan_doc"


@dataclass(frozen=True)
class RouteResult:
    skill: str | None
    reason: str
    artifact_slot: str | None = None  # "specs" | "plans" | None
    on_dispatch: Transition | None = None
    on_complete: Transition | None = None
    blockers: tuple[str, ...] = ()


def route(state: WorkItemState) -> RouteResult:
    """Compute the workflow action for a work item's current state."""
    blockers = _validate(state)
    if blockers:
        return RouteResult(skill=None, reason="invalid item", blockers=tuple(blockers))
    if state.phase == "done":
        return RouteResult(
            skill=None,
            reason="pipeline complete",
            blockers=("phase=done: nothing to dispatch; archive once the item ages out",),
        )
    if state.status in TERMINAL_STATUSES or state.status == "mitigated":
        return RouteResult(
            skill=None,
            reason="disposition is human-owned",
            blockers=(f"status {state.status!r} never dispatches; set status to 'open' to re-enter the pipeline",),
        )
    if state.phase is None:
        return _entry(state)
    stage = {"design": _design, "plan": _plan, "execute": _execute, "finish": _finish}
    return stage[state.phase](state)


def _validate(state: WorkItemState) -> list[str]:
    blockers = []
    if state.kind not in VALID_KINDS:
        blockers.append(f"kind {state.kind!r} not in {sorted(VALID_KINDS)}")
    if state.status not in VALID_STATUSES:
        blockers.append(f"status {state.status!r} not in {sorted(VALID_STATUSES)}")
    if state.phase is not None and state.phase not in VALID_PHASES:
        blockers.append(f"phase {state.phase!r} not in {sorted(VALID_PHASES)}")
    if state.effort is not None and state.effort not in VALID_EFFORTS:
        blockers.append(f"effort {state.effort!r} not in {sorted(VALID_EFFORTS)}; re-size via --effort")
    return blockers


def _entry(state: WorkItemState) -> RouteResult:
    """First dispatch: status open, no phase. Sets the entry phase via on_dispatch."""
    if state.status != "open":
        return RouteResult(
            skill=None,
            reason="invalid entry",
            blockers=(f"no phase and status {state.status!r}; workflow entry requires status 'open'",),
        )
    if state.kind == "test-gap":
        # The gap is identified at filing time — skip design. The effort fork
        # applies here since there is no design stage to advance out of.
        if state.effort is None:
            return RouteResult(
                skill=None,
                reason="test-gap entry forks on effort",
                blockers=(
                    "effort required: test-gap routes to execute (xs/s) or plan (m/l/xl); "
                    "size the item and advance with --effort",
                ),
            )
        if state.effort in SMALL_EFFORTS:
            return RouteResult(
                skill="test-driven-development",
                reason=f"test-gap with effort {state.effort}: skip design and plan",
                on_dispatch=Transition(phase="execute", status="in-progress", requires=("owner",)),
                on_complete=Transition(phase="finish"),
            )
        return RouteResult(
            skill="writing-plans",
            reason=f"test-gap with effort {state.effort}: skip design, plan first",
            artifact_slot="plans",
            on_dispatch=Transition(phase="plan"),
            on_complete=Transition(phase="execute", status="accepted", sync_plan_table=True, stamp_doc="plan_doc"),
        )
    skill = "systematic-debugging" if state.kind in DIAGNOSIS_KINDS else "brainstorming"
    return RouteResult(
        skill=skill,
        reason=f"{state.kind} entering the pipeline at design",
        artifact_slot="specs",
        on_dispatch=Transition(phase="design"),
        on_complete=_design_complete(state),
    )


def _design_complete(state: WorkItemState) -> Transition:
    """The effort fork: small bug-like work skips planning."""
    if state.kind in BUG_LIKE_KINDS:
        if state.effort is None:
            return Transition(phase=PLAN_OR_EXECUTE, requires=("effort",), stamp_doc="spec_doc")
        if state.effort in SMALL_EFFORTS:
            return Transition(phase="execute", stamp_doc="spec_doc")
    return Transition(phase="plan", stamp_doc="spec_doc")


def _design(state: WorkItemState) -> RouteResult:
    skill = "systematic-debugging" if state.kind in DIAGNOSIS_KINDS else "brainstorming"
    return RouteResult(
        skill=skill,
        reason=f"{state.kind} at design stage",
        artifact_slot="specs",
        on_complete=_design_complete(state),
    )


def _plan(state: WorkItemState) -> RouteResult:
    return RouteResult(
        skill="writing-plans",
        reason=f"{state.kind} at plan stage",
        artifact_slot="plans",
        on_complete=Transition(phase="execute", status="accepted", sync_plan_table=True, stamp_doc="plan_doc"),
    )


def _execute(state: WorkItemState) -> RouteResult:
    if state.has_plan_doc:
        skill, reason = "subagent-driven-development", "execute stage with a written plan"
    else:
        skill, reason = "test-driven-development", "execute stage via small-bug shortcut (no plan)"
    on_dispatch = None
    if state.status != "in-progress":
        on_dispatch = Transition(status="in-progress", requires=("owner",))
    return RouteResult(
        skill=skill,
        reason=reason,
        on_dispatch=on_dispatch,
        on_complete=Transition(phase="finish"),
    )


def _finish(state: WorkItemState) -> RouteResult:
    return RouteResult(
        skill="finishing-a-development-branch",
        reason=f"{state.kind} at finish stage",
        on_complete=Transition(phase="done", status="resolved", requires=("resolved_in",)),
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run --package work-io pytest tests/unit/test_workflow.py -v`
Expected: ALL PASS.

- [ ] **Step 5: Run the whole work-io suite**

Run: `uv run --package work-io pytest`
Expected: ALL PASS.

- [ ] **Step 6: Commit**

```bash
git add packages/work-io/src/work_io/workflow.py packages/work-io/tests/unit/test_workflow.py
git commit -m "feat(work-io): pure routing table for the work-item workflow"
```

---

### Task 4: `run_work_next` in graph-wiki-core (+ `workspace_root` pass-through in `run_work_lint`)

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/work.py`
- Create: `packages/graph-wiki-core/tests/unit/test_commands_workflow.py`

- [ ] **Step 1: Write the failing tests**

Create `packages/graph-wiki-core/tests/unit/test_commands_workflow.py`. Helpers mirror `test_commands_work.py` but the writer returns the file stem (the slug used by `next`/`advance`) and accepts a `phase`/extra frontmatter:

```python
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path


def _make_workspace(tmp_path: Path) -> tuple[Path, Path]:
    """Return (workspace, wiki). Creates wiki/work/ structure."""
    workspace = tmp_path / "ws"
    wiki = workspace / "wiki"
    (wiki / "work").mkdir(parents=True)
    return workspace, wiki


def _write_item(
    work_dir: Path, name: str, status: str = "open", kind: str = "bug", body: str = "## Summary\ncontent\n", **extra_fm
) -> str:
    """Write a work item; returns the slug (file stem, date-prefixed like real items)."""
    opened = (date.today() - timedelta(days=1)).isoformat()
    fm_lines = [
        "---",
        f"title: {name}",
        f"status: {status}",
        f"kind: {kind}",
        f"opened: {opened}",
        f"updated: {date.today().isoformat()}",
    ]
    for k, v in extra_fm.items():
        fm_lines.append(f"{k}: {v}")
    slug = f"{opened}-{name}"
    (work_dir / f"{slug}.md").write_text("\n".join(fm_lines) + "\n---\n\n" + body)
    return slug


# --- run_work_next ---


def test_next_fresh_bug_routes_to_systematic_debugging(tmp_path: Path) -> None:
    import asyncio

    from graph_wiki_core.commands.work import run_work_next

    workspace, wiki = _make_workspace(tmp_path)
    slug = _write_item(wiki / "work", "fix-login-timeout", kind="bug")

    result = asyncio.run(run_work_next(workspace_path=workspace, slug=slug))

    assert result.blockers == []
    assert result.action == {"skill": "systematic-debugging", "reason": "bug entering the pipeline at design"}
    assert result.phase == "design"
    assert result.artifact == {"path": str(workspace / "raw" / "specs" / f"{slug}.md")}
    assert result.on_dispatch == {"phase": "design", "status": "open", "requires": []}
    assert result.on_complete == {"phase": "plan-or-execute", "status": "open", "requires": ["effort"]}


def test_next_unknown_slug_blocks(tmp_path: Path) -> None:
    import asyncio

    from graph_wiki_core.commands.work import run_work_next

    workspace, _wiki = _make_workspace(tmp_path)

    result = asyncio.run(run_work_next(workspace_path=workspace, slug="no-such-item"))

    assert result.action is None
    assert result.blockers


def test_next_terminal_item_blocks(tmp_path: Path) -> None:
    import asyncio

    from graph_wiki_core.commands.work import run_work_next

    workspace, wiki = _make_workspace(tmp_path)
    slug = _write_item(wiki / "work", "old-bug", status="resolved", resolved_in="pr#9")

    result = asyncio.run(run_work_next(workspace_path=workspace, slug=slug))

    assert result.action is None
    assert result.blockers


def test_next_execute_with_plan_doc_carries_dispatch_transition(tmp_path: Path) -> None:
    import asyncio

    from graph_wiki_core.commands.work import run_work_next

    workspace, wiki = _make_workspace(tmp_path)
    slug = _write_item(
        wiki / "work", "feat", kind="feature", status="accepted", phase="execute",
        plan_doc="raw/plans/feat.md",
        body="## Plan\n\n| Action | Done when | Rationale |\n| --- | --- | --- |\n| x | y | z |\n",
    )

    result = asyncio.run(run_work_next(workspace_path=workspace, slug=slug))

    assert result.action["skill"] == "subagent-driven-development"
    assert result.on_dispatch == {"phase": None, "status": "in-progress", "requires": ["owner"]}
    assert result.artifact is None


def test_lint_passes_workspace_root_for_artifact_rule(tmp_path: Path) -> None:
    import asyncio

    from graph_wiki_core.commands.work import run_work_lint

    workspace, wiki = _make_workspace(tmp_path)
    _write_item(wiki / "work", "with-ghost-spec", spec_doc="raw/specs/ghost.md")

    result = asyncio.run(run_work_lint(workspace_path=workspace))

    assert "artifact-doc-missing" in {f["rule_id"] for f in result.findings}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_commands_workflow.py -v`
Expected: FAIL with `ImportError: cannot import name 'run_work_next'` (and the lint test fails because `workspace_root` isn't passed yet).

- [ ] **Step 3: Implement `run_work_next` and the lint pass-through**

In `packages/graph-wiki-core/src/graph_wiki_core/commands/work.py`:

3a. Add the import (with the other `work_io` imports, alphabetical):

```python
from work_io import workflow as _workflow
```

3b. Update the module docstring's Public API block — add:

```
    run_work_next(workspace_path, slug)    -> WorkNextResult
    run_work_advance(workspace_path, ...)  -> WorkAdvanceResult
```

3c. Add the result dataclass after `WorkArchiveResult`:

```python
@dataclass
class WorkNextResult:
    """Result of run_work_next(). Field shapes match the `gw work next --json` contract."""

    slug: str
    status: str | None = None
    kind: str | None = None
    phase: str | None = None
    effort: str | None = None
    action: dict | None = None  # {"skill", "reason"}
    artifact: dict | None = None  # {"path": absolute path}
    on_dispatch: dict | None = None  # {"phase", "status", "requires"}
    on_complete: dict | None = None
    blockers: list[str] = field(default_factory=list)
```

3d. Add helpers in the Helpers section (after `_load_items`):

```python
def _load_item(wiki: Path, slug: str) -> tuple[Path, dict, str]:
    """Load wiki/work/<slug>.md; returns (path, frontmatter, body)."""
    path = wiki / "work" / f"{slug}.md"
    if not path.exists():
        raise FileNotFoundError(f"unknown slug {slug!r}: {path} not found")
    fm, body = _frontmatter.parse(path.read_text(encoding="utf-8"))
    return path, fm, body


def _state_from_fm(fm: dict, effort_override: str | None = None) -> _workflow.WorkItemState:
    effort = effort_override or (str(fm["effort"]) if fm.get("effort") else None)
    return _workflow.WorkItemState(
        kind=str(fm.get("kind", "")),
        status=str(fm.get("status", "")),
        phase=str(fm["phase"]) if fm.get("phase") else None,
        effort=effort,
        has_plan_doc=bool(fm.get("plan_doc")),
    )


def _transition_dict(t: _workflow.Transition | None, current_status: str) -> dict | None:
    """Render a Transition for the JSON contract: status shows the post-transition value."""
    if t is None:
        return None
    return {"phase": t.phase, "status": t.status or current_status, "requires": list(t.requires)}
```

3e. Add `run_work_next` (new section before `run_work_file`):

```python
# ---------------------------------------------------------------------------
# run_work_next
# ---------------------------------------------------------------------------


async def run_work_next(workspace_path: Path | None = None, *, slug: str) -> WorkNextResult:
    """Compute the workflow routing decision for one work item. Read-only."""
    wiki, _repo = resolve_wiki_and_repo(workspace_path)
    workspace = wiki.parent

    try:
        _path, fm, _body = _load_item(wiki, slug)
    except (FileNotFoundError, ValueError) as e:
        return WorkNextResult(slug=slug, blockers=[str(e)])

    state = _state_from_fm(fm)
    r = _workflow.route(state)
    phase = state.phase or (r.on_dispatch.phase if r.on_dispatch else None)
    artifact = None
    if r.artifact_slot:
        artifact = {"path": str(workspace / "raw" / r.artifact_slot / f"{slug}.md")}

    return WorkNextResult(
        slug=slug,
        status=state.status,
        kind=state.kind,
        phase=phase,
        effort=state.effort,
        action={"skill": r.skill, "reason": r.reason} if r.skill else None,
        artifact=artifact,
        on_dispatch=_transition_dict(r.on_dispatch, state.status),
        on_complete=_transition_dict(r.on_complete, state.status),
        blockers=list(r.blockers),
    )
```

3f. In `run_work_lint`, pass the workspace through (the existing call reads `findings = _lint.run_lint(items, repo, sidecar)`):

```python
    findings = _lint.run_lint(items, repo, sidecar, workspace_root=wiki.parent)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_commands_workflow.py -v`
Expected: ALL PASS.

- [ ] **Step 5: Run the neighbouring suite to catch regressions**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_commands_work.py -v`
Expected: ALL PASS.

- [ ] **Step 6: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/work.py packages/graph-wiki-core/tests/unit/test_commands_workflow.py
git commit -m "feat(core): run_work_next — read-only workflow routing decision"
```

---

### Task 5: `run_work_advance` in graph-wiki-core

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/work.py`
- Modify: `packages/graph-wiki-core/tests/unit/test_commands_workflow.py`

- [ ] **Step 1: Write the failing tests**

Append to `packages/graph-wiki-core/tests/unit/test_commands_workflow.py`:

```python
# --- run_work_advance ---


def _read_fm(wiki: Path, slug: str) -> dict:
    from work_io import frontmatter

    fm, _body = frontmatter.parse((wiki / "work" / f"{slug}.md").read_text())
    return fm


def test_advance_fresh_feature_enters_design(tmp_path: Path) -> None:
    import asyncio

    from graph_wiki_core.commands.work import run_work_advance

    workspace, wiki = _make_workspace(tmp_path)
    slug = _write_item(wiki / "work", "new-feature", kind="feature")

    result = asyncio.run(run_work_advance(workspace_path=workspace, slug=slug))

    fm = _read_fm(wiki, slug)
    assert fm["phase"] == "design"
    assert fm["status"] == "open"
    assert fm["updated"] == date.today().isoformat()  # `date` imported at module top
    assert result.phase == "design"
    assert (wiki / "work-index.json").exists()  # sidecar regenerated


def test_advance_design_complete_without_effort_errors(tmp_path: Path) -> None:
    import asyncio

    import pytest

    from graph_wiki_core.commands.work import run_work_advance

    workspace, wiki = _make_workspace(tmp_path)
    slug = _write_item(wiki / "work", "sized-later", kind="bug", phase="design")

    with pytest.raises(ValueError, match="effort"):
        asyncio.run(run_work_advance(workspace_path=workspace, slug=slug))


def test_advance_design_complete_small_bug_shortcuts_to_execute(tmp_path: Path) -> None:
    import asyncio

    from graph_wiki_core.commands.work import run_work_advance

    workspace, wiki = _make_workspace(tmp_path)
    slug = _write_item(wiki / "work", "small-bug", kind="bug", phase="design")
    (workspace / "raw" / "specs").mkdir(parents=True)
    (workspace / "raw" / "specs" / f"{slug}.md").write_text("# findings\n")

    result = asyncio.run(run_work_advance(workspace_path=workspace, slug=slug, effort="s"))

    fm = _read_fm(wiki, slug)
    assert fm["phase"] == "execute"
    assert fm["status"] == "open"  # shortcut skips accepted
    assert fm["effort"] == "s"
    assert fm["spec_doc"] == f"raw/specs/{slug}.md"
    assert result.stamped["spec_doc"] == f"raw/specs/{slug}.md"


def test_advance_plan_complete_sets_accepted_and_syncs_plan_table(tmp_path: Path) -> None:
    import asyncio

    from graph_wiki_core.commands.work import run_work_advance
    from work_io import frontmatter, plan_table

    workspace, wiki = _make_workspace(tmp_path)
    slug = _write_item(wiki / "work", "big-feature", kind="feature", phase="plan")
    (workspace / "raw" / "plans").mkdir(parents=True)
    (workspace / "raw" / "plans" / f"{slug}.md").write_text("# plan\n")

    result = asyncio.run(run_work_advance(workspace_path=workspace, slug=slug))

    fm, body = frontmatter.parse((wiki / "work" / f"{slug}.md").read_text())
    assert fm["status"] == "accepted"
    assert fm["phase"] == "execute"
    assert fm["plan_doc"] == f"raw/plans/{slug}.md"
    parsed = plan_table.parse_plan(body)
    assert parsed.state == "ok"  # rule 4 passes by construction
    assert any(f"raw/plans/{slug}.md" in row["action"] for row in parsed.rows)
    assert "accepted-without-plan" not in {f["rule_id"] for f in result.findings}


def test_advance_execute_dispatch_requires_owner(tmp_path: Path) -> None:
    import asyncio

    import pytest

    from graph_wiki_core.commands.work import run_work_advance

    workspace, wiki = _make_workspace(tmp_path)
    slug = _write_item(wiki / "work", "exec-me", kind="bug", phase="execute", effort="s")

    with pytest.raises(ValueError, match="owner"):
        asyncio.run(run_work_advance(workspace_path=workspace, slug=slug))


def test_advance_execute_dispatch_sets_in_progress(tmp_path: Path) -> None:
    import asyncio

    from graph_wiki_core.commands.work import run_work_advance

    workspace, wiki = _make_workspace(tmp_path)
    slug = _write_item(wiki / "work", "exec-me", kind="bug", phase="execute", effort="s")

    asyncio.run(run_work_advance(workspace_path=workspace, slug=slug, owner="pat"))

    fm = _read_fm(wiki, slug)
    assert fm["status"] == "in-progress"
    assert fm["owner"] == "pat"
    assert fm["phase"] == "execute"  # phase unchanged by the dispatch transition


def test_advance_execute_complete_moves_to_finish(tmp_path: Path) -> None:
    import asyncio

    from graph_wiki_core.commands.work import run_work_advance

    workspace, wiki = _make_workspace(tmp_path)
    slug = _write_item(
        wiki / "work", "executing", kind="bug", status="in-progress", phase="execute", effort="s", owner="pat"
    )

    asyncio.run(run_work_advance(workspace_path=workspace, slug=slug))

    fm = _read_fm(wiki, slug)
    assert fm["phase"] == "finish"
    assert fm["status"] == "in-progress"


def test_advance_finish_requires_resolved_in(tmp_path: Path) -> None:
    import asyncio

    import pytest

    from graph_wiki_core.commands.work import run_work_advance

    workspace, wiki = _make_workspace(tmp_path)
    slug = _write_item(
        wiki / "work", "finishing", kind="bug", status="in-progress", phase="finish", effort="s", owner="pat"
    )

    with pytest.raises(ValueError, match="resolved"):
        asyncio.run(run_work_advance(workspace_path=workspace, slug=slug))


def test_advance_finish_complete_resolves(tmp_path: Path) -> None:
    import asyncio

    from graph_wiki_core.commands.work import run_work_advance

    workspace, wiki = _make_workspace(tmp_path)
    slug = _write_item(
        wiki / "work", "finishing", kind="bug", status="in-progress", phase="finish", effort="s", owner="pat"
    )

    result = asyncio.run(run_work_advance(workspace_path=workspace, slug=slug, resolved_in="pr#42"))

    fm = _read_fm(wiki, slug)
    assert fm["status"] == "resolved"
    assert fm["phase"] == "done"
    assert fm["resolved_in"] == "pr#42"
    assert result.status == "resolved"


def test_advance_terminal_item_errors(tmp_path: Path) -> None:
    import asyncio

    import pytest

    from graph_wiki_core.commands.work import run_work_advance

    workspace, wiki = _make_workspace(tmp_path)
    slug = _write_item(wiki / "work", "done-item", kind="bug", status="resolved", resolved_in="pr#1")

    with pytest.raises(ValueError):
        asyncio.run(run_work_advance(workspace_path=workspace, slug=slug))


def test_full_feature_pipeline_walk(tmp_path: Path) -> None:
    """open/no-phase -> design -> plan -> execute(accepted) -> in-progress -> finish -> done."""
    import asyncio

    from graph_wiki_core.commands.work import run_work_advance, run_work_next

    workspace, wiki = _make_workspace(tmp_path)
    slug = _write_item(wiki / "work", "walk", kind="feature")
    (workspace / "raw" / "specs").mkdir(parents=True)
    (workspace / "raw" / "specs" / f"{slug}.md").write_text("# spec\n")
    (workspace / "raw" / "plans").mkdir(parents=True)
    (workspace / "raw" / "plans" / f"{slug}.md").write_text("# plan\n")

    def next_skill() -> str | None:
        r = asyncio.run(run_work_next(workspace_path=workspace, slug=slug))
        return r.action["skill"] if r.action else None

    assert next_skill() == "brainstorming"
    asyncio.run(run_work_advance(workspace_path=workspace, slug=slug))  # -> design
    assert next_skill() == "brainstorming"
    asyncio.run(run_work_advance(workspace_path=workspace, slug=slug))  # design done -> plan
    assert next_skill() == "writing-plans"
    asyncio.run(run_work_advance(workspace_path=workspace, slug=slug))  # plan done -> execute/accepted
    assert next_skill() == "subagent-driven-development"
    asyncio.run(run_work_advance(workspace_path=workspace, slug=slug, owner="pat"))  # dispatch -> in-progress
    asyncio.run(run_work_advance(workspace_path=workspace, slug=slug))  # execute done -> finish
    assert next_skill() == "finishing-a-development-branch"
    asyncio.run(run_work_advance(workspace_path=workspace, slug=slug, resolved_in="pr#7"))  # -> done

    fm = _read_fm(wiki, slug)
    assert fm["phase"] == "done"
    assert fm["status"] == "resolved"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_commands_workflow.py -v -k advance`
Expected: FAIL with `ImportError: cannot import name 'run_work_advance'`.

- [ ] **Step 3: Implement `run_work_advance`**

In `packages/graph-wiki-core/src/graph_wiki_core/commands/work.py`:

3a. Add the result dataclass after `WorkNextResult`:

```python
@dataclass
class WorkAdvanceResult:
    """Result of run_work_advance()."""

    slug: str
    phase: str | None = None  # phase after the transition
    status: str | None = None  # status after the transition
    applied: dict = field(default_factory=dict)  # {"phase": [before, after], "status": [before, after]}
    stamped: dict = field(default_factory=dict)  # frontmatter keys written (effort/owner/resolved_in/spec_doc/plan_doc)
    findings: list[dict] = field(default_factory=list)  # lint findings for this slug after the write
```

3b. Add the command after `run_work_next`:

```python
# ---------------------------------------------------------------------------
# run_work_advance
# ---------------------------------------------------------------------------


async def run_work_advance(
    workspace_path: Path | None = None,
    *,
    slug: str,
    effort: str | None = None,
    owner: str | None = None,
    resolved_in: str | None = None,
) -> WorkAdvanceResult:
    """Apply the routing table's next transition for one work item.

    The single mutation point of the workflow: applies on_dispatch when the
    current state has an unmet dispatch precondition, otherwise on_complete.
    Stamps `updated`, writes passed field flags, stamps spec_doc/plan_doc as
    artifacts land, syncs the ## Plan table on acceptance, regenerates the
    sidecar, and re-lints the item. Raises ValueError on blockers or missing
    required flags.
    """
    wiki, repo = resolve_wiki_and_repo(workspace_path)
    workspace = wiki.parent
    path, fm, body = _load_item(wiki, slug)

    state = _state_from_fm(fm, effort_override=effort)
    r = _workflow.route(state)
    if r.blockers:
        raise ValueError("; ".join(r.blockers))
    t = r.on_dispatch or r.on_complete
    if t is None:
        raise ValueError(f"nothing to advance: {r.reason}")
    if "effort" in t.requires:
        raise ValueError("effort required to advance: pass --effort xs|s|m|l|xl")
    if "owner" in t.requires and not (owner or fm.get("owner")):
        raise ValueError("owner required to advance: pass --owner <handle>")
    if "resolved_in" in t.requires and not (resolved_in or fm.get("resolved_in")):
        raise ValueError("resolved-in required to advance: pass --resolved-in <pr/commit>")

    applied: dict = {}
    if t.phase:
        applied["phase"] = [fm.get("phase"), t.phase]
        fm["phase"] = t.phase
    if t.status:
        applied["status"] = [fm.get("status"), t.status]
        fm["status"] = t.status

    stamped: dict = {}
    for key, value in (("effort", effort), ("owner", owner), ("resolved_in", resolved_in)):
        if value:
            fm[key] = value
            stamped[key] = value
    if t.stamp_doc:
        slot = "specs" if t.stamp_doc == "spec_doc" else "plans"
        rel = f"raw/{slot}/{slug}.md"
        fm[t.stamp_doc] = rel
        stamped[t.stamp_doc] = rel
    fm["updated"] = date.today().isoformat()

    if t.sync_plan_table:
        body = _plan_table.ensure_plan_row(
            body,
            action=f"Execute implementation plan: raw/plans/{slug}.md",
            done_when="Implementation lands and the item is resolved",
            rationale="Workflow plan stage complete",
        )

    # parse() consumed the closing fence plus one newline; emit() + "\n" + body round-trips.
    path.write_text(_frontmatter.emit(fm) + "\n" + body, encoding="utf-8")
    await run_work_regen_index(workspace_path=workspace_path)

    items = _load_items(wiki / "work")
    sidecar = _sidecar.load_sidecar(wiki)
    findings = _lint.run_lint(items, repo, sidecar, workspace_root=workspace)
    return WorkAdvanceResult(
        slug=slug,
        phase=str(fm["phase"]) if fm.get("phase") else None,
        status=str(fm.get("status")) if fm.get("status") else None,
        applied=applied,
        stamped=stamped,
        findings=[
            {"rule_id": f.rule_id, "severity": f.severity, "slug": f.slug, "message": f.message}
            for f in findings
            if f.slug == slug
        ],
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run --package graph-wiki-core pytest tests/unit/test_commands_workflow.py -v`
Expected: ALL PASS (including the full pipeline walk).

- [ ] **Step 5: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/work.py packages/graph-wiki-core/tests/unit/test_commands_workflow.py
git commit -m "feat(core): run_work_advance — single mutation point for the workflow"
```

---

### Task 6: CLI wrappers — `gw work next` / `gw work advance`

**Files:**
- Modify: `packages/graph-wiki-cli/src/graph_wiki_cli/work_cli/main.py`

The CLI layer is deliberately logic-free (everything is tested at the core layer, per the spec's testing section), so this task is implement + smoke-test rather than TDD.

- [ ] **Step 1: Add the commands**

In `packages/graph-wiki-cli/src/graph_wiki_cli/work_cli/main.py`:

1a. Extend the core import:

```python
from graph_wiki_core.commands.work import (
    run_work_advance,
    run_work_archive,
    run_work_file,
    run_work_lint,
    run_work_next,
    run_work_regen_index,
    run_work_status,
)
```

1b. Append the two commands at the end of the file:

```python
@work_app.command(name="next")
def next_cmd(
    slug: str = typer.Argument(..., help="Work item slug (file stem under wiki/work/)"),
    workspace: str = typer.Option("", "--workspace", help="Workspace path"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Compute the next workflow action for a work item (read-only)."""
    workspace_path = Path(workspace) if workspace else None
    try:
        result = asyncio.run(run_work_next(workspace_path=workspace_path, slug=slug))
    except RuntimeError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=3)

    if json_output:
        typer.echo(json.dumps(dataclasses.asdict(result), indent=2))
    else:
        typer.echo(f"{result.slug}: kind={result.kind} status={result.status} phase={result.phase}")
        if result.action:
            typer.echo(f"  dispatch: {result.action['skill']} — {result.action['reason']}")
        if result.artifact:
            typer.echo(f"  artifact: {result.artifact['path']}")
        for b in result.blockers:
            typer.echo(f"  blocked: {b}")

    if result.blockers:
        raise typer.Exit(code=1)


@work_app.command()
def advance(
    slug: str = typer.Argument(..., help="Work item slug (file stem under wiki/work/)"),
    effort: str = typer.Option("", "--effort", help="xs|s|m|l|xl"),
    owner: str = typer.Option("", "--owner", help="Owner handle"),
    resolved_in: str = typer.Option("", "--resolved-in", help="PR/commit reference"),
    workspace: str = typer.Option("", "--workspace", help="Workspace path"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Apply the routing table's next transition for a work item (single mutation point)."""
    workspace_path = Path(workspace) if workspace else None
    try:
        result = asyncio.run(
            run_work_advance(
                workspace_path=workspace_path,
                slug=slug,
                effort=effort or None,
                owner=owner or None,
                resolved_in=resolved_in or None,
            )
        )
    except (RuntimeError, FileNotFoundError, ValueError) as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=2)

    if json_output:
        typer.echo(json.dumps(dataclasses.asdict(result), indent=2))
    else:
        typer.echo(f"[ok] {result.slug}: phase={result.phase} status={result.status}")
        for key, change in result.applied.items():
            typer.echo(f"  {key}: {change[0]} -> {change[1]}")
        for key, value in result.stamped.items():
            typer.echo(f"  stamped {key}: {value}")
        for f in result.findings:
            typer.echo(f"  [{f['severity']}] {f['rule_id']} — {f['message']}")
```

1c. Update the stale `--effort` help text in the existing `file` command (line 36) from `help="trivial|small|medium|large"` to:

```python
    effort: str = typer.Option("", "--effort", help="xs|s|m|l|xl"),
```

- [ ] **Step 2: Smoke-test the wiring**

Run: `uv run --package graph-wiki-cli gw work next --help && uv run --package graph-wiki-cli gw work advance --help`
Expected: both help screens render with the documented arguments; exit 0.

- [ ] **Step 3: End-to-end smoke against a throwaway workspace**

```bash
WS=$(mktemp -d)/ws && mkdir -p "$WS/wiki/work"
uv run --package graph-wiki-cli gw work file --workspace "$WS" --title "smoke bug" --kind bug --summary "smoke test"
SLUG=$(basename "$WS"/wiki/work/*.md .md)
uv run --package graph-wiki-cli gw work next "$SLUG" --workspace "$WS" --json
uv run --package graph-wiki-cli gw work advance "$SLUG" --workspace "$WS"
uv run --package graph-wiki-cli gw work next "$SLUG" --workspace "$WS" --json
```

Expected: first `next` shows `"skill": "systematic-debugging"`, `"phase": "design"`, on_complete `"plan-or-execute"` requiring effort; `advance` reports `phase: None -> design`; second `next` shows phase `design` with no `on_dispatch`.

- [ ] **Step 4: Commit**

```bash
git add packages/graph-wiki-cli/src/graph_wiki_cli/work_cli/main.py
git commit -m "feat(cli): gw work next / gw work advance"
```

---

### Task 7: Workflow skill, command, and rule-doc updates

**Files:**
- Create: `plugins/graph-wiki/skills/workflow/SKILL.md`
- Create: `plugins/graph-wiki/commands/workflow.md`
- Modify: `plugins/graph-wiki/skills/graph-wiki/references/lifecycle-rules.md`
- Modify: `plugins/graph-wiki/commands/lint.md`

- [ ] **Step 1: Create the skill**

Create `plugins/graph-wiki/skills/workflow/SKILL.md`:

````markdown
---
name: workflow
description: Use when driving a work item through its development pipeline — runs `gw work next` to compute the stage, dispatches the stage skill (brainstorming, systematic-debugging, writing-plans, subagent-driven-development, test-driven-development, finishing-a-development-branch), verifies the artifact, and advances the item with `gw work advance`. One stage per invocation; clear context between stages.
---

# Work Item Workflow

Dispatch one pipeline stage for a work item, then advance it. The CLI owns every
decision (routing, transitions, validation); this skill only relays.

**One stage per invocation, by design.** Never chain stages in a session — each
stage gets a fresh context window. The work item plus `raw/` artifacts are the
durable state between sessions; nothing depends on conversation memory.

In this workspace `gw` runs as `uv run --package graph-wiki-cli gw …`.

## Steps

### 1. Resolve & report

Run `gw work next <slug> --json`.

- If `blockers` is non-empty: report each blocker and **stop**. Do not improvise
  around a blocker — terminal/mitigated items, invalid enums, and unknown slugs
  are all human decisions.
- If the only blocker says **effort required**: ask the user to size the item
  (xs / s / m / l / xl — xs/s means a bug-like item skips the planning stage),
  then run `gw work advance <slug> --effort <value>` and re-run `gw work next`.
- Otherwise announce the dispatch: item title, kind, phase, and the stage skill
  from `action.skill`.

### 2. Apply the dispatch transition (when present)

If the JSON carries a non-null `on_dispatch`, apply it mechanically **before**
dispatching: run `gw work advance <slug>`, supplying any flag named in
`on_dispatch.requires` (e.g. `--owner <handle>` when dispatching execution —
ask the user if no owner is known). Do not special-case stages; the CLI encodes
which transitions happen at dispatch time.

### 3. Dispatch the stage skill

Invoke the stage skill named by `action.skill` via the Skill tool (namespaced
`graph-wiki:<skill>`), prepending a work-item brief:

- title, kind, summary, `affects`, and effort from the item's frontmatter
- links to prior artifacts (`spec_doc`, `plan_doc`) so the stage starts from
  the durable state, not from memory
- when `artifact.path` is set: "Write your output document to
  `<artifact.path>` — this overrides the skill's default location."

The stock skills honor user-preference path overrides; they stay unmodified.

### 4. Verify the artifact

When `artifact.path` is set, check the file exists after the stage completes.
If the skill wrote to its stock location (`docs/superpowers/specs/` or
`docs/superpowers/plans/` in the repo), move the file to `artifact.path` and
say so.

### 5. Advance

Run `gw work advance <slug>` with whatever flags the stage produced
(`--effort` if the command demands it, `--resolved-in <ref>` when completing
the finish stage). Report the lint findings it returns — they are the item's
health check, not noise.

### 6. Hand off

End with: "Phase advanced to `<phase>`. Clear context (`/clear`) and run
`/graph-wiki:workflow <slug>` to continue."

When the item reaches `phase: done`, report the resolution (`resolved_in`) and
suggest `/graph-wiki:archive` once the item ages out.
````

- [ ] **Step 2: Create the command**

Create `plugins/graph-wiki/commands/workflow.md`:

```markdown
---
name: workflow
description: Drive a work item through its pipeline — compute the next stage with `gw work next`, dispatch the stage skill, verify the artifact, advance with `gw work advance`. One stage per invocation; clear context and re-run between stages. Usage /graph-wiki:workflow <slug>
---

# /graph-wiki:workflow

Dispatch the next pipeline stage for a work item.

## Usage

```
/graph-wiki:workflow <slug>
```

`<slug>` is the work item's file stem under `wiki/work/` (e.g. `2026-06-09-fix-login-timeout`).

## What happens

Invoke the graph-wiki:workflow skill with the given slug and follow it exactly as presented to you.

## Skill Reference

→ `workflow/SKILL.md`
```

- [ ] **Step 3: Document rules 20–23 in lifecycle-rules.md**

Append to `plugins/graph-wiki/skills/graph-wiki/references/lifecycle-rules.md` (after the `## Sidecar (2)` section), and update its intro/heading counts from 19 to 23 if a total is stated near the top (read the file's opening first):

```markdown
## Workflow (4)

These rules fire only when the workflow-owned keys are present — items filed
outside the workflow lint clean.

### `effort-not-in-enum` — warn
**Trigger:** `effort:` set but not one of `xs | s | m | l | xl`.
**Rationale:** the workflow's effort fork (small bug-like work skips planning) needs a comparable scale; legacy free-text efforts degrade to warnings, not errors.
**Remedy:** re-size the item (`gw work advance <slug> --effort <value>` or edit frontmatter).

### `phase-not-in-enum` — error
**Trigger:** `phase:` set but not one of `design | plan | execute | finish | done`.
**Rationale:** `phase` is machine-owned pipeline position; an unknown value breaks `gw work next` routing.
**Remedy:** fix the value or remove the key (the item re-enters the workflow at first dispatch).

### `phase-status-incoherent` — warn
**Trigger:** `accepted` with phase outside `execute | finish | done`; `in-progress` with phase outside `execute | finish`; `resolved` with phase other than `done`.
**Rationale:** status (commitment) and phase (pipeline position) advance together via `gw work advance`; divergence means hand-editing.
**Remedy:** re-run `gw work advance`, or hand-fix whichever field is wrong. Warn-level because disposition stays human-owned.

### `artifact-doc-missing` — warn
**Trigger:** `spec_doc:` or `plan_doc:` set but the workspace-relative file does not exist.
**Rationale:** fresh-context workflow sessions locate prior output through these pointers; a dangling pointer strands the next stage.
**Remedy:** restore the file under `<workspace>/raw/`, or clear the key.
```

- [ ] **Step 4: Update the lint command description**

In `plugins/graph-wiki/commands/lint.md`, change both occurrences of "19 rules" / "all 19 rules" to "23 rules" / "all 23 rules" (lines 3 and 30).

- [ ] **Step 5: Manual walkthrough check (no automated test — the skill is prose)**

Re-read the skill against spec section 4's five numbered steps and confirm each maps: resolve & report (step 1), mechanical on_dispatch (step 2 — spec folds this into "not special-cased in the skill"), dispatch with artifact override (step 3), verify artifact (step 4), advance + report lint (step 5), hand-off message (step 6).

- [ ] **Step 6: Commit**

```bash
git add plugins/graph-wiki/skills/workflow/SKILL.md plugins/graph-wiki/commands/workflow.md plugins/graph-wiki/skills/graph-wiki/references/lifecycle-rules.md plugins/graph-wiki/commands/lint.md
git commit -m "feat(plugin): graph-wiki:workflow skill + command; document lint rules 20-23"
```

---

### Task 8: Final verification

- [ ] **Step 1: Lint and format**

Run: `uv run ruff check . && uv run ruff format --check .`
Expected: clean (fix and re-run if not; line-length is 120).

- [ ] **Step 2: Full test sweep of every touched package**

```bash
uv run --package work-io pytest
uv run --package graph-wiki-core pytest -m "not integration"
uv run --package graph-wiki-cli pytest -m "not integration"
```

Expected: ALL PASS, no regressions.

- [ ] **Step 3: Commit any formatting fallout**

```bash
git add -A && git commit -m "chore: ruff formatting" # only if ruff changed files
```

---

## Spec coverage self-check

| Spec section | Tasks |
|---|---|
| §1 Phase model (`phase` key, status sync points, shortcut skips accepted, terminal refusal) | 1 (enums), 3 (transitions), 5 (advance) |
| §2 Routing table (kind table, effort fork, plan/execute/finish routing) | 3 |
| §3 `gw work next` JSON contract + `gw work advance` (effort error, plan-table sync, two-step execute) | 4, 5, 6 |
| §4 Workflow skill & command (5 steps, one stage per invocation) | 7 |
| §5 Artifact layout (`raw/specs`, `raw/plans`, `spec_doc`/`plan_doc` stamping) | 4 (artifact path), 5 (stamping) |
| §6 Schema & lint changes (enums + 4 presence-gated rules) | 1 |
| §7 Testing (routing units, command tests, lint cases, manual skill walkthrough) | 1, 3, 4, 5, 7 step 5 |
| Out of scope (variant skills, ingest, hooks, migrations) | untouched — verified no task adds them |
