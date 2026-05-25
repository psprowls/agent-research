"""wiki-io — pure-Python vault read/write and analysis (ported from lattice-wiki-core)."""

from wiki_io._workspace import resolve_wiki_and_repo
from wiki_io.layout_io import read_layout, write_layout

__all__ = ["read_layout", "write_layout", "resolve_wiki_and_repo"]
