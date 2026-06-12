#!/usr/bin/env python3
"""Plugin shim for filing a curated-page proposal into wiki/proposals/.

Pure local IO — no Bedrock backend branch (the ledger write has no LLM in it).
"""

from __future__ import annotations

from _uv_reexec import ensure as _ensure_uv

_ensure_uv()


def main() -> None:
    from wiki_io.file_proposal import main as _main

    _main()


if __name__ == "__main__":
    main()
