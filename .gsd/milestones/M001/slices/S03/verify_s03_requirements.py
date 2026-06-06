#!/usr/bin/env python3
"""Verify S03 requirements contract and archive-boundary claims.

This is a document-contract verifier for M001/S03. It asserts that the
rendered DB-backed requirements file separates active/validated M001 work,
deferred future work, and explicit out-of-scope anti-features with source
traceability, while rejecting common overclaims that would promote archived or
deferred work into completed M001 scope.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
REQUIREMENTS = ROOT / ".gsd" / "REQUIREMENTS.md"


@dataclass(frozen=True)
class Requirement:
    id: str
    section: str
    body: str

    def field(self, label: str) -> str:
        match = re.search(rf"^- {re.escape(label)}: (.*)$", self.body, flags=re.MULTILINE)
        if not match:
            return ""
        return match.group(1).strip()


def fail(message: str) -> None:
    raise AssertionError(message)


def require_contains(text: str, needle: str) -> None:
    if needle not in text:
        fail(f"missing required text: {needle!r}")


def require_regex(text: str, pattern: str, description: str) -> None:
    if not re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL):
        fail(f"missing required pattern for {description}: {pattern}")


def forbid_regex(text: str, pattern: str, description: str) -> None:
    if re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL):
        fail(f"prohibited overclaim present for {description}: {pattern}")


def parse_requirements(text: str) -> dict[str, Requirement]:
    current_section = ""
    requirements: dict[str, Requirement] = {}
    current_id: str | None = None
    current_body: list[str] = []

    def flush() -> None:
        nonlocal current_id, current_body
        if current_id is None:
            return
        requirements[current_id] = Requirement(current_id, current_section, "\n".join(current_body).strip())
        current_id = None
        current_body = []

    for line in text.splitlines():
        section_match = re.match(r"^## (Active|Validated|Deferred|Out of Scope)$", line)
        if section_match:
            flush()
            current_section = section_match.group(1)
            continue

        req_match = re.match(r"^### (R\d{3}) — ", line)
        if req_match:
            flush()
            current_id = req_match.group(1)
            current_body = [line]
            continue

        if current_id is not None:
            current_body.append(line)

    flush()
    return requirements


def require_requirement(requirements: dict[str, Requirement], req_id: str) -> Requirement:
    req = requirements.get(req_id)
    if req is None:
        fail(f"missing requirement {req_id}")
    return req


def assert_owner(req: Requirement, primary: str, supporting: list[str] | None = None) -> None:
    actual_primary = req.field("Primary owning slice")
    if actual_primary != primary:
        fail(f"{req.id} primary owner mismatch: expected {primary!r}, found {actual_primary!r}")
    if supporting is not None:
        actual_supporting = [part.strip() for part in req.field("Supporting slices").split(",") if part.strip()]
        missing = [owner for owner in supporting if owner not in actual_supporting]
        if missing:
            fail(f"{req.id} supporting owner mismatch: missing {missing!r} from {actual_supporting!r}")


def assert_no_active_owner(req: Requirement) -> None:
    primary = req.field("Primary owning slice").lower()
    supporting = req.field("Supporting slices").lower()
    if primary not in {"none", ""}:
        fail(f"{req.id} should not have an active M001 primary owner, found {primary!r}")
    if supporting not in {"none", ""}:
        fail(f"{req.id} should not have active supporting slices, found {supporting!r}")


def verify_requirements_text(text: str) -> None:
    if not text.strip():
        fail("requirements file is empty")

    for needle in [
        "# Requirements",
        "## Active",
        "## Validated",
        "## Deferred",
        "## Out of Scope",
        "## Traceability",
        ".gsd/PROJECT.md",
        ".gsd/milestones/M001/M001-CONTEXT.md",
        ".planning/CONTINUE-sweep-harness-fixes-3.md",
        ".planning/deferred-items.md",
        ".planning/PROJECT.md",
        ".planning/MILESTONES.md",
    ]:
        require_contains(text, needle)

    requirements = parse_requirements(text)

    # Active or validated initialization requirements must remain mapped to the
    # correct M001 slices, even after R004 moves from active to validated.
    r001 = require_requirement(requirements, "R001")
    r002 = require_requirement(requirements, "R002")
    r003 = require_requirement(requirements, "R003")
    r004 = require_requirement(requirements, "R004")
    r005 = require_requirement(requirements, "R005")
    for req in [r001, r002, r003, r004, r005]:
        if req.section not in {"Active", "Validated"}:
            fail(f"{req.id} should be active or validated, found section {req.section!r}")
    assert_owner(r001, "M001/S01")
    assert_owner(r002, "M001/S02")
    assert_owner(r003, "M001/S02")
    assert_owner(r004, "M001/S03", ["M001/S04"])
    assert_owner(r005, "M001/S04", ["M001/S01", "M001/S02", "M001/S03"])

    # Deferred future-work records must stay clearly deferred/future and must
    # not acquire active M001 ownership.
    r006 = require_requirement(requirements, "R006")
    r007 = require_requirement(requirements, "R007")
    for req in [r006, r007]:
        if req.section != "Deferred" or req.field("Status") != "deferred":
            fail(f"{req.id} must stay in the deferred bucket")
        assert_no_active_owner(req)
        deferred_label_text = f"{req.field('Validation')}\n{req.field('Notes')}"
        require_regex(
            deferred_label_text, r"\b(deferred|future-only|future/deferred)\b", f"{req.id} deferred/future label"
        )
    require_regex(
        r006.body, r"cost-frontier.*(sweep|rerun|re-run).*winner", "R006 sweep rerun and winner-selection handoff"
    )
    require_regex(r006.body, r"no active M001 execution owner", "R006 no active M001 owner")
    require_regex(r007.body, r"optional archive.*index|structured archive index", "R007 optional archive index")
    require_regex(r007.body, r"no active M001 execution owner", "R007 no active M001 owner")

    # Out-of-scope records must prohibit the named anti-features.
    anti_features = {
        "R008": r"wholesale.*planning.*(conversion|convert)",
        "R009": r"migration/backfill|migration.*backfill|backfill.*tool|legacy audit/verification backfill",
        "R010": r"blindly resume|blind.*resum|exhaustive archive audit",
        "R011": r"cost-frontier sweep|Bedrock eval budget|authoritative winners|model defaults",
    }
    for req_id, pattern in anti_features.items():
        req = require_requirement(requirements, req_id)
        if req.section != "Out of Scope" or req.field("Status") != "out-of-scope":
            fail(f"{req.id} must stay in the out-of-scope bucket")
        assert_no_active_owner(req)
        require_regex(req.body, r"Explicit exclusion|Do not|out-of-scope", f"{req.id} explicit exclusion label")
        require_regex(req.body, pattern, f"{req.id} prohibited anti-feature")

    # Required source coverage across the rendered contract.
    for source in [
        ".gsd/PROJECT.md",
        ".gsd/milestones/M001/M001-CONTEXT.md",
        ".planning/CONTINUE-sweep-harness-fixes-3.md",
        ".planning/deferred-items.md",
        ".planning/PROJECT.md",
        ".planning/MILESTONES.md",
    ]:
        require_contains(text, source)

    # Prohibited affirmative overclaims. These patterns are intentionally
    # specific to affirmative claims so honest negated exclusions remain allowed.
    prohibited_patterns = {
        "wholesale conversion completed": r"M001\s+(completed|performed|finished)\s+(a\s+)?wholesale\s+[^\n.]*\.planning[^\n.]*conversion",
        "M001 ran the sweep": r"M001\s+(ran|runs|executed|executes|completed)\s+[^\n.]*\bsweep\b",
        "authoritative winners selected": r"authoritative\s+cost-frontier\s+winners?\s+(selected|chosen)",
        "legacy audits backfilled": r"legacy\s+audits\s+(were\s+)?backfilled",
        "legacy audit backfill completed": r"legacy\s+audit(?:/verification)?\s+backfill\s+(completed|done)",
    }
    for description, pattern in prohibited_patterns.items():
        forbid_regex(text, pattern, description)


def expect_failure(text: str, expected_message_part: str) -> None:
    try:
        verify_requirements_text(text)
    except AssertionError as exc:
        if expected_message_part not in str(exc):
            fail(
                f"negative self-check failed for unexpected reason: wanted {expected_message_part!r}, got {str(exc)!r}"
            )
        return
    fail(f"negative self-check unexpectedly passed: {expected_message_part}")


def run_negative_self_checks(text: str) -> None:
    """Exercise requested Q7 failure classes with inline mutated fixtures."""

    expect_failure(
        text.replace("- Primary owning slice: M001/S03", "- Primary owning slice: none", 1),
        "R004 primary owner mismatch",
    )
    missing_deferred_labels = text.replace("Deferred/future-only", "Reference-only").replace(
        "Future/deferred", "Reference-only"
    )
    expect_failure(missing_deferred_labels, "deferred/future label")
    expect_failure(
        text.replace(".planning/deferred-items.md", ".planning/deferred-items-MISSING.md"), "missing required text"
    )
    expect_failure(text + "\nM001 completed wholesale .planning conversion.\n", "wholesale conversion completed")
    expect_failure(text + "\nM001 ran the sweep.\n", "M001 ran the sweep")
    expect_failure(text + "\nAuthoritative cost-frontier winners selected.\n", "authoritative winners selected")
    expect_failure(text + "\nLegacy audits backfilled.\n", "legacy audits backfilled")


def main() -> None:
    if not REQUIREMENTS.exists():
        fail(f"requirements file is missing: {REQUIREMENTS}")
    text = REQUIREMENTS.read_text(encoding="utf-8")
    verify_requirements_text(text)
    run_negative_self_checks(text)
    print(f"S03 requirements verifier passed: {REQUIREMENTS}")


if __name__ == "__main__":
    main()
