"""Lifecycle lint rules for work items (per-item schema/state rules plus cross-item hierarchy rules)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal

from work_io.plan_table import PlanResult

VALID_STATUSES = frozenset({"open", "accepted", "in-progress", "mitigated", "resolved", "wontfix", "superseded"})
VALID_KINDS = frozenset({"bug", "tech-debt", "test-gap", "security", "perf", "feature", "epic", "spike"})
BUG_LIKE_KINDS = frozenset({"bug", "security", "perf", "tech-debt", "test-gap"})
TERMINAL_STATUSES = frozenset({"resolved", "wontfix", "superseded"})
FEATURE_LIKE_KINDS = frozenset({"feature", "epic"})
VALID_EFFORTS = frozenset({"xtra-small", "small", "medium", "large", "xtra-large"})
VALID_PHASES = frozenset({"design", "plan", "execute", "finish", "done"})

# Rule 22 compatibility map: statuses listed here constrain which phases are coherent.
# Statuses absent from the map (open, mitigated, wontfix, superseded) are unconstrained.
_PHASE_COMPAT = {
    "accepted": frozenset({"execute", "finish", "done"}),
    "in-progress": frozenset({"execute", "finish"}),
    "resolved": frozenset({"done"}),
}

_PATH_RE = re.compile(r"\b([\w][\w.\-]*/[\w.\-/]+)\b")


@dataclass
class LintFinding:
    rule_id: str
    severity: Literal["error", "warn", "info"]
    slug: str
    message: str


def run_lint(
    items: list[dict],
    repo_root: Path | None,
    sidecar: dict | None,
    workspace_root: Path | None = None,
) -> list[LintFinding]:
    """Run all lifecycle rules. Each item dict has keys: slug, fm, plan (PlanResult).

    workspace_root enables the workspace-relative checks (rule 23, and the
    workspace fallback in rule 11); when None those checks are skipped.
    """
    findings: list[LintFinding] = []

    for item in items:
        slug: str = item["slug"]
        fm: dict = item["fm"]
        plan: PlanResult = item["plan"]
        status = str(fm.get("status", ""))
        kind = str(fm.get("kind", ""))

        # 1. status-not-in-enum
        if status not in VALID_STATUSES:
            findings.append(
                LintFinding("status-not-in-enum", "error", slug, f"status {status!r} not in {sorted(VALID_STATUSES)}")
            )

        # 2. kind-not-in-enum
        if kind not in VALID_KINDS:
            findings.append(
                LintFinding("kind-not-in-enum", "error", slug, f"kind {kind!r} not in {sorted(VALID_KINDS)}")
            )

        # 3. severity-on-non-bug
        if fm.get("severity") and kind not in BUG_LIKE_KINDS:
            findings.append(
                LintFinding(
                    "severity-on-non-bug",
                    "info",
                    slug,
                    f"severity set on kind={kind!r}; severity applies to bug-like kinds only",
                )
            )

        # 4. accepted-without-plan
        if status == "accepted" and plan.state not in ("ok", "empty"):
            findings.append(
                LintFinding(
                    "accepted-without-plan", "error", slug, "status=accepted but ## Plan table is missing or malformed"
                )
            )

        # 5. in-progress-without-ref
        if status == "in-progress" and not (fm.get("owner") or fm.get("related_prs")):
            findings.append(
                LintFinding(
                    "in-progress-without-ref", "error", slug, "status=in-progress but no owner or related_prs set"
                )
            )

        # 6. resolved-without-ref
        # Epics are exempt: they resolve via the children-terminal gate, not a resolved_in ref.
        if status == "resolved" and kind != "epic" and not fm.get("resolved_in"):
            findings.append(
                LintFinding("resolved-without-ref", "warn", slug, "status=resolved but resolved_in is blank")
            )

        # 7. superseded-without-link
        if status == "superseded" and not fm.get("superseded_by"):
            findings.append(
                LintFinding("superseded-without-link", "error", slug, "status=superseded but superseded_by is blank")
            )

        # 8. mitigated-without-mitigation
        if status == "mitigated" and not fm.get("mitigation"):
            findings.append(
                LintFinding(
                    "mitigated-without-mitigation", "error", slug, "status=mitigated but mitigation field is blank"
                )
            )

        # 9. wontfix-without-rationale
        if status == "wontfix" and not fm.get("rationale"):
            findings.append(
                LintFinding("wontfix-without-rationale", "warn", slug, "status=wontfix but rationale field is blank")
            )

        # 10. affects-target-missing (skipped when repo_root is None)
        if repo_root is not None:
            for affects_path in fm.get("affects") or []:
                if affects_path and not (repo_root / str(affects_path)).exists():
                    findings.append(
                        LintFinding(
                            "affects-target-missing",
                            "error",
                            slug,
                            f"affects path {affects_path!r} does not exist under repo root",
                        )
                    )

        # 11. plan-action-target-missing (skipped when repo_root is None)
        if repo_root is not None and plan.state == "ok":
            for row in plan.rows:
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

        # 12. stuck-open
        if status == "open" and _days_since(str(fm.get("updated", ""))) > 30:
            findings.append(LintFinding("stuck-open", "warn", slug, "status=open with no update in >30 days"))

        # 13. stuck-accepted
        if status == "accepted" and _days_since(str(fm.get("updated", ""))) > 60:
            findings.append(LintFinding("stuck-accepted", "warn", slug, "status=accepted with no update in >60 days"))

        # 14. archive-eligible
        if status in TERMINAL_STATUSES:
            findings.append(
                LintFinding(
                    "archive-eligible",
                    "info",
                    slug,
                    f"status={status!r} (terminal); consider archiving",
                )
            )

        # 15. done-when-missing
        if kind in FEATURE_LIKE_KINDS and plan.state == "ok":
            if any(not row.get("done_when") for row in plan.rows):
                findings.append(
                    LintFinding(
                        "done-when-missing", "warn", slug, f"kind={kind!r} plan has rows with empty 'Done when' column"
                    )
                )

        # 16. feature-without-target
        if kind in FEATURE_LIKE_KINDS and not fm.get("target"):
            findings.append(
                LintFinding("feature-without-target", "warn", slug, f"kind={kind!r} has no target (YYYY-QN or YYYY-MM)")
            )

        # 17. plan-table-malformed
        if plan.state == "malformed":
            findings.append(
                LintFinding(
                    "plan-table-malformed", "warn", slug, "## Plan heading present but no valid markdown table follows"
                )
            )

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

    # 24-29. hierarchy rules (cross-item; resolved against the full item set)
    by_slug = {it["slug"]: it["fm"] for it in items}
    dep_graph: dict[str, list[str]] = {}
    for item in items:
        slug = item["slug"]
        fm = item["fm"]
        kind = str(fm.get("kind", ""))
        parent = fm.get("parent")
        depends_on = list(fm.get("depends_on") or [])
        dep_graph[slug] = [str(dep) for dep in depends_on]

        # 24. parent-missing / 25. parent-not-epic
        if parent:
            parent_fm = by_slug.get(str(parent))
            if parent_fm is None:
                findings.append(
                    LintFinding("parent-missing", "error", slug, f"parent {parent!r} has no matching work item")
                )
            elif str(parent_fm.get("kind", "")) != "epic":
                findings.append(
                    LintFinding(
                        "parent-not-epic",
                        "error",
                        slug,
                        f"parent {parent!r} resolves but its kind is {parent_fm.get('kind')!r}, not 'epic'",
                    )
                )

        # 26. depends-on-missing / 27. depends-on-not-sibling
        for dep in depends_on:
            dep_fm = by_slug.get(str(dep))
            if dep_fm is None:
                findings.append(
                    LintFinding("depends-on-missing", "error", slug, f"depends_on {dep!r} has no matching work item")
                )
            elif parent and dep_fm.get("parent") != parent:
                findings.append(
                    LintFinding(
                        "depends-on-not-sibling",
                        "warn",
                        slug,
                        f"depends_on {dep!r} has parent {dep_fm.get('parent')!r}, not this item's parent {parent!r}",
                    )
                )

        # 29. epic-without-children
        if kind == "epic" and str(fm.get("phase", "")) in {"execute", "finish", "done"}:
            has_children = any(it["fm"].get("parent") == slug for it in items)
            if not has_children:
                findings.append(
                    LintFinding(
                        "epic-without-children", "warn", slug, f"epic at phase={fm.get('phase')!r} has no children"
                    )
                )

    # 28. depends-on-cycle
    for slug in _cycle_nodes(dep_graph):
        findings.append(LintFinding("depends-on-cycle", "error", slug, "depends_on participates in a cycle"))

    # 18. sidecar-missing (global)
    if sidecar is None:
        findings.append(
            LintFinding("sidecar-missing", "warn", "(sidecar)", "work-index.json is absent; run `gw work regen-index`")
        )

    # 19. sidecar-stale (global)
    if sidecar is not None:
        generated_prefix = sidecar.get("generated_at", "")[:10]
        max_updated = max(
            (str(item["fm"].get("updated", ""))[:10] for item in items),
            default="",
        )
        if generated_prefix and max_updated > generated_prefix:
            findings.append(
                LintFinding(
                    "sidecar-stale",
                    "warn",
                    "(sidecar)",
                    f"sidecar generated_at {generated_prefix!r} is older than newest item updated {max_updated!r}",
                )
            )

    return findings


def _cycle_nodes(graph: dict[str, list[str]]) -> list[str]:
    """Return the sorted set of nodes that participate in any depends_on cycle."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {n: WHITE for n in graph}
    in_cycle: set[str] = set()
    stack: list[str] = []

    def visit(node: str) -> None:
        color[node] = GRAY
        stack.append(node)
        for nxt in graph.get(node, []):
            if nxt not in graph:
                continue
            if color[nxt] == GRAY:
                idx = stack.index(nxt)
                in_cycle.update(stack[idx:])
            elif color[nxt] == WHITE:
                visit(nxt)
        stack.pop()
        color[node] = BLACK

    for node in graph:
        if color[node] == WHITE:
            visit(node)
    return sorted(in_cycle)


def _days_since(date_str: str) -> int:
    """Days elapsed since a YYYY-MM-DD date string. Returns 0 on parse failure."""
    try:
        dt = date.fromisoformat(date_str[:10])
        return (date.today() - dt).days
    except (ValueError, TypeError):
        return 0
