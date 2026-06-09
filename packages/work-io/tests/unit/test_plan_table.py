from __future__ import annotations

from work_io.plan_table import ensure_plan_row, parse_plan

BODY_WITH_PLAN = """
## Plan

| Action | Done when | Rationale |
|---|---|---|
| Write tests | Tests pass | TDD |
| Deploy | CI green | Release |
"""

BODY_MISSING_HEADING = """
## Summary
Some content here.
"""

BODY_MALFORMED = """
## Plan

No table here, just prose.
"""

BODY_EMPTY_TABLE = """
## Plan

| Action | Done when | Rationale |
|---|---|---|
"""

BODY_ESCAPED_PIPE = r"""
## Plan

| Action | Done when | Rationale |
|---|---|---|
| Fix A \| B | Done | Reason |
"""


def test_parse_ok_returns_rows() -> None:
    result = parse_plan(BODY_WITH_PLAN)
    assert result.state == "ok"
    assert len(result.rows) == 2
    assert result.rows[0]["action"] == "Write tests"
    assert result.rows[0]["done_when"] == "Tests pass"
    assert result.rows[0]["rationale"] == "TDD"


def test_parse_missing_heading() -> None:
    result = parse_plan(BODY_MISSING_HEADING)
    assert result.state == "missing"
    assert result.rows == []


def test_parse_malformed_no_table() -> None:
    result = parse_plan(BODY_MALFORMED)
    assert result.state == "malformed"


def test_parse_empty_table() -> None:
    result = parse_plan(BODY_EMPTY_TABLE)
    assert result.state == "empty"
    assert result.rows == []


def test_parse_escaped_pipe_in_cell() -> None:
    result = parse_plan(BODY_ESCAPED_PIPE)
    assert result.state == "ok"
    assert result.rows[0]["action"] == "Fix A | B"


def test_parse_permissive_two_of_three_columns() -> None:
    body = """
## Plan

| Action | Rationale |
|---|---|
| Step 1 | Because |
"""
    result = parse_plan(body)
    assert result.state == "ok"
    assert result.rows[0]["done_when"] == ""


def test_parse_case_insensitive_headers() -> None:
    body = """
## Plan

| ACTION | DONE WHEN | RATIONALE |
|---|---|---|
| Step | Done | OK |
"""
    result = parse_plan(body)
    assert result.state == "ok"


def test_parse_heading_case_insensitive() -> None:
    body = "## plan\n\n| Action | Done when | Rationale |\n|---|---|\n| x | y | z |\n"
    result = parse_plan(body)
    assert result.state == "ok"


# --- ensure_plan_row ---


def test_ensure_plan_row_appends_section_when_heading_missing() -> None:
    body = "## Summary\nsome text\n"
    out = ensure_plan_row(body, action="Do the thing", done_when="It is done", rationale="Because")
    result = parse_plan(out)
    assert result.state == "ok"
    assert result.rows == [{"action": "Do the thing", "done_when": "It is done", "rationale": "Because"}]
    assert "## Summary" in out  # existing content preserved


def test_ensure_plan_row_appends_to_existing_table() -> None:
    body = "## Plan\n\n| Action | Done when | Rationale |\n| --- | --- | --- |\n| First row | done | why |\n"
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


def test_ensure_plan_row_escapes_pipe_and_stays_idempotent() -> None:
    body = "## Summary\nx\n"
    action = "tests pass | lint clean"
    once = ensure_plan_row(body, action=action, done_when="d", rationale="r")
    twice = ensure_plan_row(once, action=action, done_when="d", rationale="r")
    assert once == twice
    result = parse_plan(once)
    assert result.state == "ok"
    assert result.rows[0]["action"] == "tests pass | lint clean"


def test_ensure_plan_row_malformed_pipe_table_not_absorbed() -> None:
    body = "## Plan\n| Bad | Header |\n| --- | --- |\n| x | y |\n"
    out = ensure_plan_row(body, action="Row", done_when="d", rationale="r")
    result = parse_plan(out)
    assert result.state == "ok"
    assert result.rows == [{"action": "Row", "done_when": "d", "rationale": "r"}]
    assert "| Bad | Header |" in out  # old content still present below


def test_ensure_plan_row_inserts_before_following_section() -> None:
    body = (
        "## Plan\n\n"
        "| Action | Done when | Rationale |\n"
        "| --- | --- | --- |\n"
        "| First row | done | why |\n\n"
        "## Next\nprose\n"
    )
    out = ensure_plan_row(body, action="New row", done_when="d", rationale="r")
    result = parse_plan(out)
    assert [r["action"] for r in result.rows] == ["First row", "New row"]
    assert out.index("## Next") > out.index("| New row |")
