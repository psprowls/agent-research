"""Source-language metadata projected from graph-io's parsing engine.

source-parser stays graph-io-private (package-layering-review): consumers that
need language metadata get it through this module instead of importing
source_parser directly.
"""

from __future__ import annotations

from source_parser.parsers import EXTENSIONS


def extension_languages() -> dict[str, str]:
    """Return the file-extension → language-name map (e.g. ".py" -> "python").

    Derived from the parser registry's canonical extension map, so it tracks
    exactly the languages the code graph can parse.
    """
    return {ext: parser.name for ext, parser in EXTENSIONS.items()}
