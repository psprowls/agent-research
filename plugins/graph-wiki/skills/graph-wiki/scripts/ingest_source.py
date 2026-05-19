#!/usr/bin/env python3
"""Plugin shim for ingest_source — dispatches to vault_io (claude) or code-wiki-agent (bedrock)."""
import subprocess
import sys

from vault_io.ingest_source import main as _core_main


def main() -> None:
    try:
        from _config import backend_for
    except ImportError:
        def backend_for(cmd: str, repo: object = None) -> str:  # type: ignore[misc]
            return "claude"

    backend = backend_for("ingest")

    if backend == "bedrock":
        result = subprocess.run(
            ["code-wiki-agent", "ingest"] + sys.argv[1:],
            check=True,
        )
        sys.exit(result.returncode)
    else:
        _core_main()


if __name__ == "__main__":
    main()
