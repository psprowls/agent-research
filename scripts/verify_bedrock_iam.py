#!/usr/bin/env python3
"""Verify AWS Bedrock IAM permissions end-to-end.

Run from the repo root:

    uv run python scripts/verify_bedrock_iam.py

Exit codes:
    0 — Bedrock invoke succeeded with the haiku role.
    1 — Bedrock rejected the call with AccessDeniedException (IAM fix needed).
    2 — Any other failure (network, ValidationException, credentials missing, ...).

All diagnostic output is written to stderr so the script is safe to invoke
from an MCP stdio host without corrupting JSON-RPC framing.
"""

from __future__ import annotations

import sys


def main() -> None:
    # Import inside main() so the module is importable for smoke checks
    # (e.g. ``importlib.util.spec_from_file_location``) without forcing
    # the model_adapter dependency tree to load at import time.
    from model_adapter.exceptions import BedrockAccessDenied
    from model_adapter.loader import make_llm

    print("Verifying Bedrock IAM (haiku role)...", file=sys.stderr)
    try:
        llm = make_llm("haiku")
        result = llm.invoke("Reply with exactly: pong")
        print(f"OK: {result.content!r}", file=sys.stderr)
    except BedrockAccessDenied as e:
        print(f"\nACCESS DENIED:\n{e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\nUNEXPECTED ERROR: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
