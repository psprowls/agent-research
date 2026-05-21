#!/usr/bin/env python3
"""Plugin shim for init_vault — dispatches to vault_io (claude) or graph-wiki-agent (bedrock)."""
import subprocess
import sys

from _uv_reexec import ensure as _ensure_uv

_ensure_uv()

from vault_io.init_vault import main as _core_main


def main() -> None:
    try:
        from _config import backend_for
    except ImportError:
        def backend_for(cmd: str, repo: object = None) -> str:  # type: ignore[misc]
            return "claude"

    backend = backend_for("init")

    if backend == "bedrock":
        result = subprocess.run(
            ["graph-wiki-agent", "init"] + sys.argv[1:],
            check=True,
        )
        sys.exit(result.returncode)
    else:
        _core_main()


if __name__ == "__main__":
    main()
