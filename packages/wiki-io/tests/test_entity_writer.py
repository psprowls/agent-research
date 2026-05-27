"""Unit + property tests for wiki_io.entity_writer (Phase 42 / Plan 01).

Validates the THREE Phase 42 contracts (D-10):

1. ADMITTED_KINDS is the 7 underscore-form kinds (D-02).
2. SCANNER_OWNED_KEYS is disjoint from the human-only keys (D-09).
3. encode_slug + decode_slug round-trip on every admitted-kind URI (D-03)
   and the encoder is injective on a sample batch (D-05).

Property tests use Hypothesis (D-11, D-12). The 3 new URI builders
(`package_family_uri`, `plugin_uri`, `dependency_uri`) from Plan 02 are
NOT imported here — Plan 01 + Plan 02 are Wave-1 parallel, so this test
constructs their URIs inline (`f"package_family:{name}"`, etc.) per
Plan 01's <interfaces> note.
"""

from __future__ import annotations

import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

from graph_io.uri import (
    RepoContext,
    domain_uri,
    pkg_uri,
    repo_uri,
)
from graph_io.uri import test_suite_uri as _test_suite_uri  # alias: avoid pytest collection
from wiki_io.entity_writer import (
    ADMITTED_KINDS,
    SCANNER_OWNED_KEYS,
    decode_slug,
    encode_slug,
)


# ----------------------------------------------------------------------------
# Unit tests
# ----------------------------------------------------------------------------


def test_admitted_kinds_shape() -> None:
    """ADMITTED_KINDS is exactly the 7 underscore-form v1.8 kinds (D-02)."""
    expected = frozenset(
        {
            "repository",
            "domain",
            "package",
            "package_family",
            "plugin",
            "dependency",
            "test_suite",
        }
    )
    assert ADMITTED_KINDS == expected
    # Sanity check: kinds that exist in graph_io._VALID_KINDS but are NOT
    # admitted to the entity lane (per the v1.8 design notes) must stay out.
    excluded = {"subpackage", "file", "function", "class", "method"}
    assert ADMITTED_KINDS.isdisjoint(excluded)


def test_scanner_owned_keys_disjoint_from_human() -> None:
    """SCANNER_OWNED_KEYS does not include any of the documented human keys (D-09)."""
    human_only = {"status", "last_reviewed", "owner", "notes"}
    assert SCANNER_OWNED_KEYS.isdisjoint(human_only)
    # Spot-check a baseline of D-07 keys ARE present.
    for key in ("uri", "kind", "domains", "depends_on", "ecosystem"):
        assert key in SCANNER_OWNED_KEYS, f"missing baseline key: {key!r}"


@pytest.mark.parametrize(
    "uri,expected_slug",
    [
        ("pkg:agent-research/graph-io", "pkg__agent-research__graph-io"),
        ("domain:agent-research/billing", "domain__agent-research__billing"),
        (
            "test_suite:agent-research/eval-harness/unit",
            "test_suite__agent-research__eval-harness__unit",
        ),
        (
            "repo:agent-research/agent-research",
            "repo__agent-research__agent-research",
        ),
        ("package_family:aws", "package_family__aws"),
        ("plugin:graph-wiki", "plugin__graph-wiki"),
        ("dependency:pypi/boto3", "dependency__pypi__boto3"),
    ],
)
def test_slug_encode_examples(uri: str, expected_slug: str) -> None:
    """Parametrized examples from CONTEXT.md D-01."""
    assert encode_slug(uri) == expected_slug


def test_decode_slug_rejects_unknown_kind() -> None:
    """decode_slug raises ValueError on unrecognized URI prefix."""
    with pytest.raises(ValueError, match="unknown URI prefix"):
        decode_slug("notakind__x")


def test_decode_slug_rejects_too_few_segments() -> None:
    """decode_slug raises ValueError when the slug has no `__` separator."""
    with pytest.raises(ValueError, match="malformed slug"):
        decode_slug("pkg")


# ----------------------------------------------------------------------------
# Hypothesis strategies — one composite per admitted kind (D-12)
# ----------------------------------------------------------------------------

# Real-world package / org / suite names use ASCII alphanumerics plus dashes
# and dots. Underscores are EXCLUDED from the fragment alphabet because the
# slug encoding uses `__` as the separator: a fragment starting or ending
# with `_` produces 3+ consecutive underscores in the slug, which splits
# ambiguously and breaks round-trip. This restriction matches real-world
# PEP-8 / npm-package / cargo-crate naming conventions (dashes preferred to
# underscores in distribution names). See Pitfall 1 in PITFALLS.md.
_fragment_alphabet = st.characters(
    whitelist_categories=("Ll", "Nd"),
    whitelist_characters="-.",
)
_fragment = st.text(alphabet=_fragment_alphabet, min_size=1, max_size=20)


@st.composite
def _pkg_uri_strategy(draw: st.DrawFn) -> str:
    org = draw(_fragment)
    repo = draw(_fragment)
    name = draw(_fragment)
    for f in (org, repo, name):
        assume("__" not in f)
    return pkg_uri(RepoContext(org, repo), name)


@st.composite
def _domain_uri_strategy(draw: st.DrawFn) -> str:
    org = draw(_fragment)
    repo = draw(_fragment)
    name = draw(_fragment)
    for f in (org, repo, name):
        assume("__" not in f)
    return domain_uri(RepoContext(org, repo), name)


@st.composite
def _repository_uri_strategy(draw: st.DrawFn) -> str:
    org = draw(_fragment)
    repo = draw(_fragment)
    for f in (org, repo):
        assume("__" not in f)
    return repo_uri(RepoContext(org, repo))


@st.composite
def _test_suite_uri_strategy(draw: st.DrawFn) -> str:
    org = draw(_fragment)
    repo = draw(_fragment)
    suite = draw(_fragment)
    for f in (org, repo, suite):
        assume("__" not in f)
    return _test_suite_uri(RepoContext(org, repo), suite)


@st.composite
def _package_family_uri_strategy(draw: st.DrawFn) -> str:
    # Inline construction — Plan 02 adds the builder; Wave-1 parallelism means
    # we cannot import it yet.
    name = draw(_fragment)
    assume("__" not in name)
    return f"package_family:{name}"


@st.composite
def _plugin_uri_strategy(draw: st.DrawFn) -> str:
    name = draw(_fragment)
    assume("__" not in name)
    return f"plugin:{name}"


@st.composite
def _dependency_uri_strategy(draw: st.DrawFn) -> str:
    ecosystem = draw(_fragment)
    name = draw(_fragment)
    for f in (ecosystem, name):
        assume("__" not in f)
    return f"dependency:{ecosystem}/{name}"


_admitted_uri_strategy = st.one_of(
    _pkg_uri_strategy(),
    _domain_uri_strategy(),
    _repository_uri_strategy(),
    _test_suite_uri_strategy(),
    _package_family_uri_strategy(),
    _plugin_uri_strategy(),
    _dependency_uri_strategy(),
)


# ----------------------------------------------------------------------------
# Property tests
# ----------------------------------------------------------------------------


@given(uri=_admitted_uri_strategy)
@settings(
    max_examples=1000,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much],
)
def test_slug_round_trip(uri: str) -> None:
    """decode_slug(encode_slug(uri)) == uri for every admitted-kind URI (D-03)."""
    assert decode_slug(encode_slug(uri)) == uri


@given(
    uris=st.lists(
        _admitted_uri_strategy,
        min_size=50,
        max_size=200,
        unique=True,
    )
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much],
)
def test_slug_batch_injective(uris: list[str]) -> None:
    """Distinct URIs encode to distinct slugs — no collisions (D-05)."""
    slugs = {encode_slug(u) for u in uris}
    assert len(slugs) == len(uris)
