"""TypeScript parser — extends the JavaScript LanguageConfig with TS-specific node types."""

from __future__ import annotations

from dataclasses import replace

import tree_sitter

from source_parser.grammars import get_language
from source_parser.parsers._base import LanguageParser
from source_parser.parsers._generic import generic_walk
from source_parser.parsers.javascript import JAVASCRIPT_CONFIG

TYPESCRIPT_CONFIG = replace(
    JAVASCRIPT_CONFIG,
    grammar_name="typescript",
    language="typescript",
    class_types=JAVASCRIPT_CONFIG.class_types | {"abstract_class_declaration"},
    function_types=JAVASCRIPT_CONFIG.function_types | {"function_signature"},
    method_types=JAVASCRIPT_CONFIG.method_types | {"method_signature", "abstract_method_signature"},
)


class TypeScriptParser(LanguageParser):
    name = "typescript"
    file_extensions = (".ts", ".tsx")

    @property
    def grammar(self) -> tree_sitter.Language:
        return get_language("typescript")

    def parse(self, path, source, *, package=None):
        return generic_walk(
            TYPESCRIPT_CONFIG,
            path,
            source,
            package=package,
            language="typescript",
        )
