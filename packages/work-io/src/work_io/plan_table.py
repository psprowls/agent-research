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


def _split_row(row: str) -> list[str]:
    """Split a markdown table row into cells, unescaping \\| in cell content."""
    row = row.strip().strip("|")
    cells = re.split(r"(?<!\\)\|", row)
    return [c.replace(r"\|", "|") for c in cells]
