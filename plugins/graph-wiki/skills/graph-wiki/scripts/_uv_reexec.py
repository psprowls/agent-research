#!/usr/bin/env python3
"""Self-healing uv re-exec bootstrap for graph-wiki plugin shims.

Chicken-and-egg problem: the shims in this directory live inside the installed
plugin tree but depend on `wiki_io`, a workspace package under
`packages/wiki-io/`. When a user invokes a shim with bare `python <shim>`
(outside `uv run`), the `from wiki_io...` import fails. This helper detects
that case and re-execs the current script under
`uv run --project <repo>/packages/wiki-io python <self> <args...>` so the
import resolves. A `GRAPH_WIKI_SHIM_REEXEC=1` env-var guard prevents infinite
re-exec loops if re-execing still does not satisfy the import.
"""
import os
import sys
from pathlib import Path


def ensure() -> None:
    # Guard: already re-execed once — do not loop. Let the caller's import raise.
    if os.environ.get("GRAPH_WIKI_SHIM_REEXEC"):
        return

    # If wiki_io is already importable, we are inside the uv workspace; bail out.
    try:
        import wiki_io  # noqa: F401
        return
    except ImportError:
        pass

    # Walk up from this file looking for packages/wiki-io/pyproject.toml.
    here = Path(__file__).resolve().parent
    while True:
        candidate = here / "packages" / "wiki-io" / "pyproject.toml"
        if candidate.is_file():
            pkg_dir = candidate.parent
            new_env = {**os.environ, "GRAPH_WIKI_SHIM_REEXEC": "1"}
            os.execvpe(
                "uv",
                ["uv", "run", "--project", str(pkg_dir), "python", sys.argv[0], *sys.argv[1:]],
                new_env,
            )
        if here == here.parent:
            # Reached filesystem root; let the caller's import raise the real error.
            return
        here = here.parent
