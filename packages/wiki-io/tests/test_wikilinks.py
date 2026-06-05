"""Unit tests for vault_wikilink — the single vault-relative wikilink builder."""

from __future__ import annotations

import pytest

from wiki_io.wikilinks import vault_wikilink


def test_bare_link_no_text():
    assert vault_wikilink("concepts/foo") == "[[concepts/foo]]"


def test_piped_link_with_text():
    assert vault_wikilink("concepts/foo", "Foo") == "[[concepts/foo|Foo]]"


def test_strips_trailing_md():
    assert vault_wikilink("concepts/foo.md", "Foo") == "[[concepts/foo|Foo]]"


def test_entities_path():
    assert vault_wikilink("entities/pkg_subagent-runtime", "subagent-runtime") == (
        "[[entities/pkg_subagent-runtime|subagent-runtime]]"
    )


def test_work_path_passes_through_unprefixed():
    # work/ lives under the wiki now — no special-casing, same base as any page.
    assert vault_wikilink("work/2026-05-03-foo.md", "Foo") == "[[work/2026-05-03-foo|Foo]]"


def test_forbids_wiki_prefix():
    with pytest.raises(ValueError, match="wiki/"):
        vault_wikilink("wiki/concepts/foo", "Foo")
