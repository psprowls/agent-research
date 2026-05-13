"""vault-io — pure-Python vault read/write and analysis (ported from lattice-wiki-core)."""

from vault_io._workspace import resolve_wiki_and_repo
from vault_io.layout_io import read_layout, write_layout

__all__ = ["read_layout", "write_layout", "resolve_wiki_and_repo"]
