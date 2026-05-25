import pytest

from _fixture_loader import (
    diff,
    fixtures_for,
    load_expected,
    serialize_tree,
)
from source_parser.parsers.typescript import TypeScriptParser

_PARSER = TypeScriptParser()
_FIXTURES = fixtures_for("typescript", (".ts", ".tsx"))


def test_basic_metadata():
    assert _PARSER.name == "typescript"
    assert _PARSER.file_extensions == (".ts", ".tsx")


@pytest.mark.parametrize("fixture", _FIXTURES, ids=lambda p: p.stem)
def test_fixture(fixture):
    source = fixture.read_bytes()
    tree = TypeScriptParser().parse(fixture, source, package="fixtures")
    actual = serialize_tree(tree)
    expected = load_expected(fixture)
    diffs = diff(actual, expected)
    assert diffs == [], "\n".join(diffs)
