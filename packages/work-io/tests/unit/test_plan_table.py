from __future__ import annotations

from work_io.plan_table import parse_plan

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
