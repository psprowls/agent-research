#!/usr/bin/env python3
"""Plugin shim for reconciling stale work-item doc pointers after a source archive.

Pure local IO — no Bedrock backend branch (gw wiki ingest already reconciles).
"""

from __future__ import annotations

from _uv_reexec import ensure as _ensure_uv

_ensure_uv()


def main() -> None:
    from wiki_io.reconcile_doc_pointers import main as _main

    _main()


if __name__ == "__main__":
    main()
