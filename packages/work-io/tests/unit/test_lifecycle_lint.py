from __future__ import annotations

from datetime import date, timedelta

from work_io.lifecycle_lint import LintFinding, run_lint
from work_io.plan_table import PlanResult


def _item(
    slug: str = "test-item",
    status: str = "open",
    kind: str = "bug",
    severity: str | None = None,
    updated_days_ago: int = 0,
    plan: PlanResult | None = None,
    **extra,
) -> dict:
    updated = (date.today() - timedelta(days=updated_days_ago)).isoformat()
    fm: dict = {"title": slug, "status": status, "kind": kind, "updated": updated}
    if severity:
        fm["severity"] = severity
    fm.update(extra)
    return {"slug": slug, "fm": fm, "plan": plan or PlanResult(state="missing")}


def _rule_ids(findings: list[LintFinding]) -> set[str]:
    return {f.rule_id for f in findings}


# --- Schema-shape rules ---


def test_status_not_in_enum() -> None:
    findings = run_lint([_item(status="unknown-status")], None, None)
    assert "status-not-in-enum" in _rule_ids(findings)


def test_kind_not_in_enum() -> None:
    findings = run_lint([_item(kind="unknown-kind")], None, None)
    assert "kind-not-in-enum" in _rule_ids(findings)


def test_severity_on_non_bug() -> None:
    findings = run_lint([_item(kind="feature", severity="high")], None, None)
    assert "severity-on-non-bug" in _rule_ids(findings)


def test_severity_on_bug_is_ok() -> None:
    findings = run_lint([_item(kind="bug", severity="high")], None, None)
    assert "severity-on-non-bug" not in _rule_ids(findings)


# --- State-conditional rules ---


def test_accepted_without_plan() -> None:
    findings = run_lint([_item(status="accepted", plan=PlanResult(state="missing"))], None, None)
    assert "accepted-without-plan" in _rule_ids(findings)


def test_accepted_with_plan_ok() -> None:
    plan = PlanResult(state="ok", rows=[{"action": "Do it", "done_when": "", "rationale": ""}])
    findings = run_lint([_item(status="accepted", plan=plan)], None, None)
    assert "accepted-without-plan" not in _rule_ids(findings)


def test_in_progress_without_ref() -> None:
    findings = run_lint([_item(status="in-progress")], None, None)
    assert "in-progress-without-ref" in _rule_ids(findings)


def test_in_progress_with_owner_ok() -> None:
    findings = run_lint([_item(status="in-progress", owner="pat")], None, None)
    assert "in-progress-without-ref" not in _rule_ids(findings)


def test_resolved_without_ref() -> None:
    findings = run_lint([_item(status="resolved")], None, None)
    assert "resolved-without-ref" in _rule_ids(findings)


def test_superseded_without_link() -> None:
    findings = run_lint([_item(status="superseded")], None, None)
    assert "superseded-without-link" in _rule_ids(findings)


def test_mitigated_without_mitigation() -> None:
    findings = run_lint([_item(status="mitigated")], None, None)
    assert "mitigated-without-mitigation" in _rule_ids(findings)


def test_wontfix_without_rationale() -> None:
    findings = run_lint([_item(status="wontfix")], None, None)
    assert "wontfix-without-rationale" in _rule_ids(findings)


# --- Lifecycle / staleness ---


def test_stuck_open_over_30d() -> None:
    findings = run_lint([_item(status="open", updated_days_ago=31)], None, None)
    assert "stuck-open" in _rule_ids(findings)


def test_stuck_open_under_30d_ok() -> None:
    findings = run_lint([_item(status="open", updated_days_ago=29)], None, None)
    assert "stuck-open" not in _rule_ids(findings)


def test_stuck_accepted_over_60d() -> None:
    findings = run_lint(
        [
            _item(
                status="accepted",
                updated_days_ago=61,
                plan=PlanResult(state="ok", rows=[{"action": "x", "done_when": "", "rationale": ""}]),
            )
        ],
        None,
        None,
    )
    assert "stuck-accepted" in _rule_ids(findings)


def test_archive_eligible() -> None:
    findings = run_lint([_item(status="resolved", updated_days_ago=0, resolved_in="pr#1")], None, None)
    assert "archive-eligible" in _rule_ids(findings)


# --- Body shape ---


def test_done_when_missing_for_feature() -> None:
    plan = PlanResult(state="ok", rows=[{"action": "Step", "done_when": "", "rationale": ""}])
    findings = run_lint([_item(kind="feature", plan=plan, status="in-progress", owner="pat")], None, None)
    assert "done-when-missing" in _rule_ids(findings)


def test_feature_without_target() -> None:
    findings = run_lint([_item(kind="feature", status="open")], None, None)
    assert "feature-without-target" in _rule_ids(findings)


def test_feature_with_target_ok() -> None:
    findings = run_lint([_item(kind="feature", status="open", target="2026-Q3")], None, None)
    assert "feature-without-target" not in _rule_ids(findings)


def test_plan_table_malformed() -> None:
    findings = run_lint([_item(plan=PlanResult(state="malformed"))], None, None)
    assert "plan-table-malformed" in _rule_ids(findings)


# --- Sidecar rules ---


def test_sidecar_missing() -> None:
    findings = run_lint([_item()], None, sidecar=None)
    assert "sidecar-missing" in _rule_ids(findings)


def test_sidecar_stale() -> None:
    items = [_item(updated_days_ago=0)]  # updated today
    sidecar = {"generated_at": "2026-01-01T00:00:00+00:00", "items": []}
    findings = run_lint(items, None, sidecar)
    assert "sidecar-stale" in _rule_ids(findings)


def test_sidecar_fresh_not_stale() -> None:
    items = [_item(updated_days_ago=5)]
    sidecar = {"generated_at": "9999-01-01T00:00:00+00:00", "items": []}
    findings = run_lint(items, None, sidecar)
    assert "sidecar-stale" not in _rule_ids(findings)


def test_sidecar_stale_tolerates_date_object_updated() -> None:
    # Unquoted YAML dates parse as datetime.date; rule 19 must not raise on them.
    item = _item()
    item["fm"]["updated"] = date.today()
    sidecar = {"generated_at": "2026-01-01T00:00:00+00:00", "items": []}
    findings = run_lint([item], None, sidecar)
    assert "sidecar-stale" in _rule_ids(findings)


# --- Finding shape ---


def test_lint_finding_has_required_fields() -> None:
    findings = run_lint([_item(status="bad-status")], None, None)
    f = next(f for f in findings if f.rule_id == "status-not-in-enum")
    assert f.severity == "error"
    assert f.slug == "test-item"
    assert f.message


# --- Workflow rules (20-23) ---


def test_effort_not_in_enum_warns() -> None:
    findings = run_lint([_item(effort="s")], None, None)
    f = next(f for f in findings if f.rule_id == "effort-not-in-enum")
    assert f.severity == "warn"


def test_effort_valid_ok() -> None:
    findings = run_lint([_item(effort="xtra-small")], None, None)
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
    findings = run_lint([_item(spec_doc="raw/specs/test-item.md")], None, None, workspace_root=tmp_path)
    f = next(f for f in findings if f.rule_id == "artifact-doc-missing")
    assert f.severity == "warn"


def test_artifact_doc_present_ok(tmp_path) -> None:
    (tmp_path / "raw" / "specs").mkdir(parents=True)
    (tmp_path / "raw" / "specs" / "test-item.md").write_text("# spec\n")
    findings = run_lint([_item(spec_doc="raw/specs/test-item.md")], None, None, workspace_root=tmp_path)
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
        rows=[
            {"action": "Execute implementation plan: raw/plans/test-item.md", "done_when": "merged", "rationale": ""}
        ],
    )
    findings = run_lint([_item(status="accepted", plan=plan)], repo, None, workspace_root=workspace)
    assert "plan-action-target-missing" not in _rule_ids(findings)


def test_plan_action_target_missing_in_both_roots_fails_rule_11(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    workspace = tmp_path / "ws"
    workspace.mkdir()
    plan = PlanResult(
        state="ok",
        rows=[{"action": "Execute implementation plan: raw/plans/nope.md", "done_when": "merged", "rationale": ""}],
    )
    findings = run_lint([_item(status="accepted", plan=plan)], repo, None, workspace_root=workspace)
    assert "plan-action-target-missing" in _rule_ids(findings)
