"""Parse the ## Plan markdown table from a work item body."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal


@dataclass
class PlanResult:
    state: Literal["missing", "empty", "malformed", "ok"]
    rows: list[dict] = field(default_factory=list)


def parse_plan(body: str) -> PlanResult:
    """Locate ## Plan heading; extract markdown table rows."""
    lines = body.splitlines()

    plan_idx = None
    for i, line in enumerate(lines):
        if re.match(r"^##\s+plan\s*$", line.strip(), re.IGNORECASE):
            plan_idx = i
            break

    if plan_idx is None:
        return PlanResult(state="missing")

    table_lines: list[str] = []
    for line in lines[plan_idx + 1 :]:
        stripped = line.strip()
        if stripped.startswith("|"):
            table_lines.append(stripped)
        elif table_lines:
            break

    if not table_lines:
        return PlanResult(state="malformed")

    header_cells = _split_row(table_lines[0])
    header_lower = [h.lower().strip() for h in header_cells]

    canonical = {"action", "done when", "rationale"}
    found = {name for name in canonical if name in header_lower}
    if len(found) < 2:
        return PlanResult(state="malformed")

    col_action = header_lower.index("action") if "action" in header_lower else None
    col_done_when = header_lower.index("done when") if "done when" in header_lower else None
    col_rationale = header_lower.index("rationale") if "rationale" in header_lower else None

    data_lines = [ln for ln in table_lines[1:] if not re.match(r"^\|[\s\-:|]+\|$", ln)]

    if not data_lines:
        return PlanResult(state="empty")

    max_col = max(c for c in [col_action, col_done_when, col_rationale] if c is not None)
    rows = []
    for line in data_lines:
        cells = _split_row(line)
        while len(cells) <= max_col:
            cells.append("")
        rows.append(
            {
                "action": cells[col_action].strip() if col_action is not None else "",
                "done_when": cells[col_done_when].strip() if col_done_when is not None else "",
                "rationale": cells[col_rationale].strip() if col_rationale is not None else "",
            }
        )

    return PlanResult(state="ok", rows=rows)


_PLAN_TABLE_HEADER = ["| Action | Done when | Rationale |", "| --- | --- | --- |"]


def ensure_plan_row(body: str, *, action: str, done_when: str, rationale: str) -> str:
    """Return body with a ## Plan table containing the given row.

    Creates the heading and table when absent; appends to an existing table;
    inserts a fresh table under a malformed heading (prose preserved below).
    Idempotent: a row whose action cell already matches is not duplicated.
    """
    existing = parse_plan(body)
    normalized_action = action.strip().replace("\n", " ")
    if existing.state == "ok" and any(r["action"] == normalized_action for r in existing.rows):
        return body

    row = f"| {_cell(action)} | {_cell(done_when)} | {_cell(rationale)} |"
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
    # Trailing blank line keeps any old pipe-table content from merging into the fresh table.
    return "\n".join(lines[: plan_idx + 1] + ["", *_PLAN_TABLE_HEADER, row, ""] + lines[plan_idx + 1 :]) + "\n"


def _cell(value: str) -> str:
    """Normalize a value for a markdown table cell: strip, flatten newlines, escape pipes."""
    return value.strip().replace("\n", " ").replace("|", "\\|")


def _split_row(row: str) -> list[str]:
    """Split a markdown table row into cells, unescaping \\| in cell content."""
    row = row.strip().strip("|")
    cells = re.split(r"(?<!\\)\|", row)
    return [c.replace(r"\|", "|") for c in cells]
