#!/usr/bin/env python3
"""Plugin shim for graph_analyzer — delegates to vault_io.graph_analyzer."""
from _uv_reexec import ensure as _ensure_uv

_ensure_uv()

from vault_io.graph_analyzer import main

if __name__ == "__main__":
    main()
