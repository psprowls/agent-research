"""Property + unit tests for `wiki_io.entity_writer.short_filename` (Phase 52 / Plan 01).

Covers WIKI-FN-04 (purity + idempotence + collision-resistance) and the
function-level portion of WIKI-FN-02 (suite-kind dispatch). The end-to-end
vault-write check lives in `test_entity_writer.py`.
"""

from __future__ import annotations

import hashlib

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from wiki_io.entity_writer import short_filename


# ----------------------------------------------------------------------------
# Parametrized unit cases
# ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "uri,kwargs,expected",
    [
        ("repo:agent-research/agent-research", {}, "repo_agent-research"),
        ("pkg:agent-research/agent-research/wiki-io", {}, "pkg_wiki-io"),
        (
            "app:agent-research/agent-research/graph-wiki-agent",
            {},
            "app_graph-wiki-agent",
        ),
        (
            "domain:agent-research/agent-research/observability",
            {},
            "domain_observability",
        ),
        ("plugin:graph-wiki", {}, "plugin_graph-wiki"),
        ("dependency:pypi/langchain-aws", {}, "dep_langchain-aws"),
        (
            "test_suite:agent-research/agent-research/packages/wiki-io/tests",
            {"suite_kind": "unit", "pkg_for_suite": "wiki-io"},
            "unit_tests_wiki-io",
        ),
    ],
)
def test_examples_no_collision(uri: str, kwargs: dict, expected: str) -> None:
    """Happy-path: each of the 7 admitted URI shapes produces its documented stem."""
    assert short_filename(uri, frozenset(), **kwargs) == expected


@pytest.mark.parametrize(
    "suite_kind,expected_prefix",
    [
        ("unit", "unit_tests"),
        ("integration", "int_tests"),
        ("e2e", "e2e_tests"),
        ("contract", "contract_tests"),
        (None, "tests"),
        ("garbage_value", "tests"),
    ],
)
def test_suite_kind_dispatch(suite_kind: str | None, expected_prefix: str) -> None:
    """D-07: suite_kind dispatches to the documented prefix; unknown falls back to `tests`."""
    assert (
        short_filename(
            "test_suite:org/repo/pkg/tests",
            frozenset(),
            suite_kind=suite_kind,
            pkg_for_suite="pkg",
        )
        == f"{expected_prefix}_pkg"
    )


def test_suite_pkg_derivation_from_uri_when_pkg_for_suite_missing() -> None:
    """When `pkg_for_suite` is omitted, the second-to-last URI segment is used."""
    assert (
        short_filename(
            "test_suite:org/repo/wiki-io/tests",
            frozenset(),
            suite_kind="unit",
        )
        == "unit_tests_wiki-io"
    )


def test_collision_suffix_format() -> None:
    """D-03: collision suffix is exactly `__<6hex>` from sha256(uri)[:6]."""
    uri = "pkg:org/repo/utils"
    expected_suffix = hashlib.sha256(uri.encode("utf-8")).hexdigest()[:6]
    result = short_filename(uri, frozenset({uri}))
    assert result == f"pkg_utils__{expected_suffix}"


def test_value_errors() -> None:
    """Empty uri, missing `:`, and unknown prefix all raise ValueError."""
    with pytest.raises(ValueError, match="empty uri"):
        short_filename("", frozenset())
    with pytest.raises(ValueError, match="missing|malformed"):
        short_filename("nocolon", frozenset())
    with pytest.raises(ValueError, match="unknown uri prefix"):
        short_filename("xyz:foo/bar", frozenset())


# ----------------------------------------------------------------------------
# Hypothesis strategies
# ----------------------------------------------------------------------------


# Fragment alphabet: lowercase letters, digits, dash, dot.  Excludes underscore
# so the plain-stem invariant `"__" not in result` holds for non-colliding URIs.
_FRAGMENT = st.text(
    alphabet=st.characters(
        whitelist_categories=("Ll", "Nd"),
        whitelist_characters="-.",
    ),
    min_size=1,
    max_size=20,
)


@st.composite
def _uri_strategy(draw: st.DrawFn) -> str:
    """Draw a URI from the 7 admitted templates with random fragment fills."""
    template = draw(
        st.sampled_from(
            [
                "repo",
                "pkg",
                "app",
                "domain",
                "plugin",
                "dependency",
                "test_suite",
            ]
        )
    )
    if template == "repo":
        return f"repo:{draw(_FRAGMENT)}/{draw(_FRAGMENT)}"
    if template == "pkg":
        return f"pkg:{draw(_FRAGMENT)}/{draw(_FRAGMENT)}/{draw(_FRAGMENT)}"
    if template == "app":
        return f"app:{draw(_FRAGMENT)}/{draw(_FRAGMENT)}/{draw(_FRAGMENT)}"
    if template == "domain":
        return f"domain:{draw(_FRAGMENT)}/{draw(_FRAGMENT)}/{draw(_FRAGMENT)}"
    if template == "plugin":
        return f"plugin:{draw(_FRAGMENT)}"
    if template == "dependency":
        return f"dependency:{draw(_FRAGMENT)}/{draw(_FRAGMENT)}"
    # test_suite
    return (
        f"test_suite:{draw(_FRAGMENT)}/{draw(_FRAGMENT)}/"
        f"{draw(_FRAGMENT)}/{draw(_FRAGMENT)}"
    )


# ----------------------------------------------------------------------------
# Property tests (Hypothesis)
# ----------------------------------------------------------------------------


@given(
    uri=_uri_strategy(),
    in_set=st.booleans(),
    suite_kind=st.sampled_from(["unit", "integration", "e2e", "contract", None]),
)
@settings(max_examples=50, deadline=None)
def test_idempotence(uri: str, in_set: bool, suite_kind: str | None) -> None:
    """short_filename is deterministic — same inputs always produce same output."""
    collision_set = frozenset({uri}) if in_set else frozenset()
    a = short_filename(uri, collision_set, suite_kind=suite_kind)
    b = short_filename(uri, collision_set, suite_kind=suite_kind)
    assert a == b


@given(u1=_uri_strategy(), u2=_uri_strategy())
@settings(max_examples=50, deadline=None)
def test_collision_resistance_within_set(u1: str, u2: str) -> None:
    """Distinct URIs in the same collision_set produce distinct filenames."""
    assume(u1 != u2)
    s = frozenset({u1, u2})
    assert short_filename(u1, s) != short_filename(u2, s)


@given(uri=_uri_strategy())
@settings(max_examples=50, deadline=None)
def test_suffix_triggering_in_set(uri: str) -> None:
    """When uri is in collision_set, the trailing `__<6hex>` matches sha256(uri)[:6]."""
    result = short_filename(uri, frozenset({uri}))
    expected_suffix = hashlib.sha256(uri.encode("utf-8")).hexdigest()[:6]
    assert result.split("__")[-1] == expected_suffix


@given(uri=_uri_strategy())
@settings(max_examples=50, deadline=None)
def test_suffix_absence_when_not_in_set(uri: str) -> None:
    """Plain stems contain no `__` since the fragment alphabet excludes underscore."""
    result = short_filename(uri, frozenset())
    assert "__" not in result
