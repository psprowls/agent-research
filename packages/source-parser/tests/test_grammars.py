import pytest
from tree_sitter import Language, Parser

from source_parser import UnsupportedLanguageError
from source_parser.grammars import get_language


def test_python_loads():
    lang = get_language("python")
    assert isinstance(lang, Language)
    parser = Parser(lang)
    tree = parser.parse(b"x = 1\n")
    assert tree.root_node is not None


def test_javascript_loads():
    lang = get_language("javascript")
    parser = Parser(lang)
    tree = parser.parse(b"const x = 1;\n")
    assert tree.root_node is not None


def test_typescript_loads_and_parses_tsx():
    lang = get_language("typescript")
    parser = Parser(lang)
    tree_ts = parser.parse(b"const x: number = 1;\n")
    assert tree_ts.root_node is not None
    tree_tsx = parser.parse(b"const X = () => <div>hi</div>;\n")
    assert tree_tsx.root_node is not None


def test_unknown_language_raises():
    with pytest.raises(UnsupportedLanguageError):
        get_language("cobol")


def test_lookup_is_cached():
    a = get_language("python")
    b = get_language("python")
    assert a is b
