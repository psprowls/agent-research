#!/usr/bin/env python3
"""Self-healing uv re-exec bootstrap for graph-wiki plugin shims.

Chicken-and-egg problem: the shims in this directory live inside the installed
plugin tree but depend on workspace packages — `graph_wiki_core` and, through
its base dependency closure, `wiki_io`, `work_io`, `guidance_io`, and
`workspace_io` — under `packages/`. When a user invokes a shim with bare
`python <shim>` (outside `uv run`), those imports fail. This helper detects
that case and re-execs the current script under
`uv run --project <repo>/packages/graph-wiki-core python <self> <args...>` so
the imports resolve. The re-exec targets core's BASE closure on purpose: the
plugin path never requests the [bedrock] extra, so the Bedrock stack is never
required to run the Claude-hosted shims. A `GRAPH_WIKI_SHIM_REEXEC=1` env-var
guard prevents infinite re-exec loops — if re-execing still does not satisfy
the import, the caller's real ImportError surfaces.
"""

import os
import sys
from pathlib import Path


def ensure() -> None:
    # Guard: already re-execed once — do not loop. Let the caller's import raise.
    if os.environ.get("GRAPH_WIKI_SHIM_REEXEC"):
        return

    # If graph_wiki_core is already importable, we are inside a capable env —
    # its base closure covers every wiki_io / work_io import the shims make.
    try:
        import graph_wiki_core  # noqa: F401

        return
    except ImportError:
        pass

    # Walk up from this file looking for packages/graph-wiki-core/pyproject.toml.
    here = Path(__file__).resolve().parent
    while True:
        candidate = here / "packages" / "graph-wiki-core" / "pyproject.toml"
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
