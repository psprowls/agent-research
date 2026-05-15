from __future__ import annotations

"""Unit tests for divergence baseline load/write/regression-check (EVAL-13).

All tests are pure unit — no Bedrock calls, no subprocess. Tests cover:
- load_baseline(): returns empty dict when file is missing
- write_baseline(): writes JSON with all required schema keys
- check_regression(): raises AssertionError when hard-severity failures increase
- check_regression(): does not raise for soft-severity increases
- check_regression(): does not raise for -JUDGE aggregate increases
- --accept-divergence-baseline flag: rewrites baseline file
"""

import json
from pathlib import Path

import pytest

from eval_harness.divergence.metric import (
    check_regression,
    load_baseline,
    write_baseline,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_results(**overrides: dict) -> dict:
    """Build a minimal librarian results dict with optional per-rule overrides."""
    base = {
        "LIB-001-wikilink-resolves": {"runs": 5, "failures": 0, "accepted_failures": []},
        "LIB-002-citation-present": {"runs": 5, "failures": 0, "accepted_failures": []},
        "LIB-003-no-slug-only-wikilinks": {"runs": 5, "failures": 0, "accepted_failures": []},
        "LIB-004-code-path-format": {"runs": 5, "failures": 0, "accepted_failures": []},
        "LIB-JUDGE": {"runs": 5, "failures": 0, "accepted_failures": []},
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# load_baseline() tests
# ---------------------------------------------------------------------------


def test_load_baseline_returns_empty_when_missing(tmp_path: Path) -> None:
    """load_baseline returns {} when the baseline file does not exist (Pitfall 5)."""
    result = load_baseline("librarian", tmp_path)
    assert result == {}


# ---------------------------------------------------------------------------
# write_baseline() tests
# ---------------------------------------------------------------------------


def test_write_baseline_schema(tmp_path: Path) -> None:
    """write_baseline writes JSON with all required schema keys: role, recorded_at, agent_commit, checks."""
    results = _make_results()
    p = write_baseline("librarian", tmp_path, results, "deadbeef")
    assert p.exists()
    snapshot = json.loads(p.read_text(encoding="utf-8"))
    required_keys = {"role", "recorded_at", "agent_commit", "checks"}
    assert required_keys <= snapshot.keys(), f"Missing keys: {required_keys - snapshot.keys()}"
    assert snapshot["role"] == "librarian"
    assert snapshot["agent_commit"] == "deadbeef"
    assert isinstance(snapshot["checks"], dict)


def test_write_baseline_json_format(tmp_path: Path) -> None:
    """write_baseline writes indented JSON ending with a newline character."""
    results = _make_results()
    p = write_baseline("librarian", tmp_path, results, "abc")
    raw = p.read_text(encoding="utf-8")
    assert raw.endswith("\n"), "JSON file must end with a trailing newline"
    # Indented JSON: second line should start with 2-space indent
    lines = raw.splitlines()
    assert len(lines) > 1, "JSON output must be multi-line (indent=2)"
    # At least one line starts with exactly 2 spaces (top-level key indent)
    indented_lines = [ln for ln in lines if ln.startswith("  ")]
    assert indented_lines, "No 2-space indented lines found — expected indent=2"


# ---------------------------------------------------------------------------
# check_regression() tests
# ---------------------------------------------------------------------------


def test_check_regression_raises_on_hard_increase(tmp_path: Path) -> None:
    """check_regression raises AssertionError when hard-severity failures increase vs baseline.

    The error message must mention 'accept-divergence-baseline' so the caller
    knows how to re-accept the baseline.
    """
    # Baseline: 1 failure for LIB-001 (hard severity)
    baseline_results = _make_results(
        **{"LIB-001-wikilink-resolves": {"runs": 5, "failures": 1, "accepted_failures": []}}
    )
    write_baseline("librarian", tmp_path, baseline_results, "abc")
    baseline = load_baseline("librarian", tmp_path)

    # Current: 3 failures — regression!
    current = _make_results(
        **{"LIB-001-wikilink-resolves": {"runs": 5, "failures": 3, "accepted_failures": []}}
    )
    with pytest.raises(AssertionError, match="accept-divergence-baseline"):
        check_regression("librarian", current, baseline)


def test_check_regression_does_not_raise_for_soft(tmp_path: Path) -> None:
    """check_regression does not raise for soft-severity failure increases.

    LIB-004-code-path-format is soft severity — a regression must not fail the gate.
    """
    # Baseline: 0 failures for soft rule
    baseline_results = _make_results()
    write_baseline("librarian", tmp_path, baseline_results, "abc")
    baseline = load_baseline("librarian", tmp_path)

    # Current: 3 failures on LIB-004 (soft) — should NOT raise
    current = _make_results(
        **{"LIB-004-code-path-format": {"runs": 5, "failures": 3, "accepted_failures": []}}
    )
    # Must not raise
    check_regression("librarian", current, baseline)


def test_check_regression_does_not_raise_for_judge(tmp_path: Path) -> None:
    """check_regression does not raise for -JUDGE aggregate regressions.

    Judge results carry non-determinism and are always treated as soft severity,
    regardless of the severity_lookup (RESEARCH §Pitfall 2).
    """
    baseline_results = _make_results()
    write_baseline("librarian", tmp_path, baseline_results, "abc")
    baseline = load_baseline("librarian", tmp_path)

    # Simulate judge regression
    current = _make_results(
        **{"LIB-JUDGE": {"runs": 5, "failures": 4, "accepted_failures": []}}
    )
    # Must not raise
    check_regression("librarian", current, baseline)


def test_check_regression_passes_when_equal(tmp_path: Path) -> None:
    """check_regression does not raise when current failures equal baseline."""
    results = _make_results(
        **{"LIB-001-wikilink-resolves": {"runs": 5, "failures": 2, "accepted_failures": []}}
    )
    write_baseline("librarian", tmp_path, results, "abc")
    baseline = load_baseline("librarian", tmp_path)

    # Same failures — equal, should not raise
    current = _make_results(
        **{"LIB-001-wikilink-resolves": {"runs": 5, "failures": 2, "accepted_failures": []}}
    )
    check_regression("librarian", current, baseline)


def test_check_regression_passes_when_decreased(tmp_path: Path) -> None:
    """check_regression does not raise when current failures are below baseline (improvement)."""
    results = _make_results(
        **{"LIB-001-wikilink-resolves": {"runs": 5, "failures": 5, "accepted_failures": []}}
    )
    write_baseline("librarian", tmp_path, results, "abc")
    baseline = load_baseline("librarian", tmp_path)

    # Fewer failures — improvement, should not raise
    current = _make_results(
        **{"LIB-001-wikilink-resolves": {"runs": 5, "failures": 1, "accepted_failures": []}}
    )
    check_regression("librarian", current, baseline)


# ---------------------------------------------------------------------------
# --accept-divergence-baseline flag flow
# ---------------------------------------------------------------------------


def test_accept_baseline_flag_rewrites_file(tmp_path: Path) -> None:
    """When write_baseline is called twice, the second call overwrites the first file.

    This simulates the --accept-divergence-baseline flow: the integration test
    calls write_baseline when accept_baseline=True, replacing the prior content.
    """
    first_results = _make_results(
        **{"LIB-001-wikilink-resolves": {"runs": 3, "failures": 1, "accepted_failures": []}}
    )
    p = write_baseline("librarian", tmp_path, first_results, "commit-v1")
    assert p.exists()
    first_data = json.loads(p.read_text(encoding="utf-8"))
    assert first_data["agent_commit"] == "commit-v1"
    assert first_data["checks"]["LIB-001-wikilink-resolves"]["failures"] == 1

    # Second call — simulates accept flag
    second_results = _make_results(
        **{"LIB-001-wikilink-resolves": {"runs": 5, "failures": 3, "accepted_failures": []}}
    )
    write_baseline("librarian", tmp_path, second_results, "commit-v2")
    second_data = json.loads(p.read_text(encoding="utf-8"))
    assert second_data["agent_commit"] == "commit-v2"
    assert second_data["checks"]["LIB-001-wikilink-resolves"]["failures"] == 3
