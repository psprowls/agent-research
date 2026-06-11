"""19 lifecycle lint rules for work items."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal

from work_io.plan_table import PlanResult

VALID_STATUSES = frozenset({"open", "accepted", "in-progress", "mitigated", "resolved", "wontfix", "superseded"})
VALID_KINDS = frozenset({"bug", "tech-debt", "test-gap", "security", "perf", "feature", "initiative", "spike"})
BUG_LIKE_KINDS = frozenset({"bug", "security", "perf", "tech-debt", "test-gap"})
TERMINAL_STATUSES = frozenset({"resolved", "wontfix", "superseded"})
FEATURE_LIKE_KINDS = frozenset({"feature", "initiative"})

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
) -> list[LintFinding]:
    """Run all 19 lifecycle rules. Each item dict has keys: slug, fm, plan (PlanResult)."""
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
        if status == "resolved" and not fm.get("resolved_in"):
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
                    if not token.startswith("http") and not (repo_root / token).exists():
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
        if status in TERMINAL_STATUSES and _days_since(str(fm.get("updated", ""))) >= 7:
            findings.append(
                LintFinding(
                    "archive-eligible",
                    "info",
                    slug,
                    f"status={status!r} (terminal) and updated >=7 days ago; consider archiving",
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


def _days_since(date_str: str) -> int:
    """Days elapsed since a YYYY-MM-DD date string. Returns 0 on parse failure."""
    try:
        dt = date.fromisoformat(date_str[:10])
        return (date.today() - dt).days
    except (ValueError, TypeError):
        return 0
