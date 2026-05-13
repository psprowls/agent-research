# Phase 1: Infrastructure, Vault IO, and MCP Skeleton — Pattern Map

**Mapped:** 2026-05-13
**Files analyzed:** 22 (new/modified files this phase)
**Analogs found:** 16 / 22 (6 greenfield — no analog exists yet)

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `pyproject.toml` (workspace root) | config | — | `/Users/pat/Personal/lattice/pyproject.toml` | exact |
| `cores/vault-io/pyproject.toml` | config | — | `/Users/pat/Personal/lattice/packages/lattice-wiki-core/pyproject.toml` | exact |
| `cores/model-adapter/pyproject.toml` | config | — | `/Users/pat/Personal/lattice/packages/lattice-wiki-core/pyproject.toml` | role-match |
| `agents/code-wiki-agent/pyproject.toml` | config | — | `/Users/pat/Personal/lattice/packages/lattice-wiki-core/pyproject.toml` | role-match |
| `cores/vault-io/src/vault_io/layout_io.py` | utility | file-I/O | `/Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/layout_io.py` | **verbatim port** |
| `cores/vault-io/src/vault_io/update_tokens.py` | utility | file-I/O | `/Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/update_tokens.py` | **verbatim port** |
| `cores/vault-io/src/vault_io/detect_containers.py` | utility | batch | `/Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/detect_containers.py` | **verbatim port** |
| `cores/vault-io/src/vault_io/_workspace.py` | utility | — | `/Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/_workspace.py` | adapted port (import surgery required) |
| `cores/vault-io/src/vault_io/append_log.py` | utility | file-I/O | `/Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/append_log.py` | **verbatim port** |
| `cores/vault-io/src/vault_io/update_index.py` | utility | file-I/O | `/Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/update_index.py` | **verbatim port** |
| `cores/vault-io/src/vault_io/graph_analyzer.py` | utility | batch | `/Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/graph_analyzer.py` | **verbatim port** |
| `cores/vault-io/src/vault_io/scan_monorepo.py` | utility | batch | `/Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/scan_monorepo.py` | **verbatim port** |
| `cores/vault-io/src/vault_io/init_vault.py` | utility | file-I/O | `/Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/init_vault.py` | adapted port (lattice_workspace dep removed) |
| `cores/vault-io/src/vault_io/lint/common.py` | utility | transform | `/Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/lint/common.py` | **verbatim port** |
| `cores/model-adapter/src/model_adapter/loader.py` | service | request-response | none | greenfield |
| `cores/model-adapter/models.toml` | config | — | none | greenfield |
| `agents/code-wiki-agent/src/code_wiki_agent/cli.py` | utility | request-response | none | greenfield |
| `agents/code-wiki-agent/src/code_wiki_mcp/server.py` | service | request-response | none | greenfield |
| `cores/vault-io/tests/conftest.py` | test | — | `/Users/pat/Personal/lattice/packages/lattice-wiki-core/tests/conftest.py` + `helpers.py` | role-match |
| `cores/vault-io/tests/test_round_trip.py` | test | file-I/O | `/Users/pat/Personal/lattice/packages/lattice-wiki-core/tests/test_update_tokens.py` | role-match |
| `cores/vault-io/tests/test_truncated_frontmatter.py` | test | file-I/O | `/Users/pat/Personal/lattice/packages/lattice-wiki-core/tests/test_update_tokens.py` lines 127-137 | exact |
| `cores/vault-io/tests/test_wikilink_predicate.py` | test | transform | `/Users/pat/Personal/lattice/packages/lattice-wiki-core/tests/test_lint_wikilink_placeholders.py` | exact |

---

## Pattern Assignments

### `pyproject.toml` (workspace root, config)

**Analog:** `/Users/pat/Personal/lattice/pyproject.toml`

**Core pattern** (full file — only 10 lines in analog):
```toml
[tool.uv.workspace]
members = ["cores/*", "agents/*"]

[dependency-groups]
dev = [
    "pytest>=8.3",
    "pytest-asyncio==1.3.0",
    "ruff>=0.15",
    "pre-commit",
]

[tool.ruff]
line-length = 120
exclude = ["**/fixtures/**"]

[tool.ruff.lint]
select = ["E", "F", "I"]

[tool.pytest.ini_options]
addopts = "--import-mode=importlib"
```

**Key constraint:** No `[project]` table at workspace root. No `testpaths` at workspace root (per-member testpaths handle scoping). The `exclude = ["**/fixtures/**"]` ruff rule is critical — ruff must not lint the committed vault fixture files.

---

### `cores/vault-io/pyproject.toml` (config)

**Analog:** `/Users/pat/Personal/lattice/packages/lattice-wiki-core/pyproject.toml`

**Core pattern** (full file, 14 lines):
```toml
[project]
name = "vault-io"
version = "0.1.0"
description = "Vault IO for code-wiki-agent"
requires-python = ">=3.11"
dependencies = [
    "python-frontmatter>=1.1",
    "tiktoken>=0.7",
]

[build-system]
requires = ["uv_build>=0.11.14,<0.12"]
build-backend = "uv_build"

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--import-mode=importlib"
```

**Note:** Build backend switches from `hatchling` (lattice analog) to `uv_build` (required for uv workspace). `lattice-workspace` dep is dropped entirely — it is not available in deep-agents.

---

### `cores/model-adapter/pyproject.toml` (config)

**Analog:** `/Users/pat/Personal/lattice/packages/lattice-wiki-core/pyproject.toml` (structure only)

**Core pattern:**
```toml
[project]
name = "model-adapter"
version = "0.1.0"
description = "AWS Bedrock model loader for code-wiki-agent"
requires-python = ">=3.11"
dependencies = [
    "langchain-aws>=1.4.6",
    "boto3>=1.38",
]

[build-system]
requires = ["uv_build>=0.11.14,<0.12"]
build-backend = "uv_build"

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--import-mode=importlib"
```

---

### `agents/code-wiki-agent/pyproject.toml` (config)

**Analog:** `/Users/pat/Personal/lattice/packages/lattice-wiki-core/pyproject.toml` (structure only)

**Core pattern** — note the `[project.scripts]` block and `[tool.uv.sources]` for workspace deps:
```toml
[project]
name = "code-wiki-agent"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "vault-io",
    "model-adapter",
    "mcp>=1.27.1",
    "langchain-aws>=1.4.6",
    "typer>=0.25.1",
]

[project.scripts]
code-wiki-agent = "code_wiki_agent.cli:app"
code-wiki-mcp   = "code_wiki_mcp.server:main"

[build-system]
requires = ["uv_build>=0.11.14,<0.12"]
build-backend = "uv_build"

[tool.uv.sources]
vault-io      = { workspace = true }
model-adapter = { workspace = true }

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--import-mode=importlib"
markers = ["integration: requires real Bedrock or subprocess (skipped in CI by default)"]
```

---

### `cores/vault-io/src/vault_io/layout_io.py` (utility, file-I/O) — VERBATIM PORT

**Analog:** `/Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/layout_io.py`

**Port instruction:** Copy the file verbatim. Change the module docstring's first line from "lattice-wiki layout block" to "vault-io layout block". No other changes — the sentinel strings (`<!-- lattice-wiki:layout:start -->`) must remain identical because existing CLAUDE.md/AGENTS.md files in vaults use them.

**Imports pattern** (lines 25-31):
```python
from __future__ import annotations

import datetime as dt
import re
from pathlib import Path
from typing import Optional
```
No external deps — stdlib only. No import changes needed on port.

**Core pattern** (lines 41-61) — the read/write API surface:
```python
def read_layout(schema_path: Path) -> Optional[dict]:
    """Return parsed layout dict, or None if no block is present."""

def write_layout(schema_path: Path, layout: dict) -> None:
    """Replace the existing block, or append a new one if none exists."""
```

**Hand-rolled emitter** (lines 67-87) — the non-negotiable write path:
```python
def _emit_yaml(layout: dict) -> str:
    out = []
    out.append(f"version: {int(layout.get('version', 1))}")
    out.append(f"detected_at: {layout.get('detected_at', '')}")
    out.append(f"repo_root: {layout.get('repo_root', '..')}")
    out.append("containers:")
    for c in layout.get("containers", []):
        out.append(f"  - source: {c['source']}")
        out.append(f"    vault_dir: {_emit_scalar(c.get('vault_dir'))}")
        out.append(f"    classification: {c['classification']}")
        if "children_count" in c:
            out.append(f"    children_count: {int(c['children_count'])}")
        if c.get("note"):
            out.append(f'    note: "{c["note"]}"')
    return "\n".join(out) + "\n"

def _emit_scalar(v) -> str:
    if v is None:
        return "null"
    return str(v)
```

---

### `cores/vault-io/src/vault_io/update_tokens.py` (utility, file-I/O) — VERBATIM PORT with import surgery

**Analog:** `/Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/update_tokens.py`

**Port instruction:** Copy verbatim. Apply these import changes only:
- `from lattice_wiki_core._version_check import check_for_updates` → remove (drop `check_for_updates` calls in `main()` too)
- `from lattice_wiki_core._workspace import resolve_wiki_and_repo` → `from vault_io._workspace import resolve_wiki_and_repo`

**Critical truncated-frontmatter guard** (lines 88-92) — must be preserved exactly:
```python
parts = raw.split("---", 2)
# Guard against truncated frontmatter (missing closing ---).
if len(parts) < 3:
    print(f"[warn] skipping {path}: no closing frontmatter fence", file=sys.stderr)
    return ("skipped", 0)
```

**Raw-string write pattern** (lines 108-128) — never use `frontmatter.dumps()`:
```python
parts = raw.split("---", 2)
fm_lines = parts[1].strip().split("\n")
updated_lines = []
tokens_found = False
for line in fm_lines:
    if line == "tokens:" or line.startswith("tokens: "):
        updated_lines.append(f"tokens: {count}")
        tokens_found = True
    else:
        updated_lines.append(line)
if not tokens_found:
    updated_lines.append(f"tokens: {count}")
updated_fm = "\n".join(updated_lines)
updated_raw = f"---\n{updated_fm}\n---{parts[2]}"
path.write_text(updated_raw, encoding="utf-8")
```

---

### `cores/vault-io/src/vault_io/detect_containers.py` (utility, batch) — VERBATIM PORT with import surgery

**Analog:** `/Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/detect_containers.py`

**Port instruction:** Copy verbatim. Import change:
- `from lattice_wiki_core._workspace import resolve_wiki_and_repo` → `from vault_io._workspace import resolve_wiki_and_repo`

The `main()` function calls `resolve_wiki_and_repo()` to get `repo`. After adaptation, `_workspace.py`'s function signature changes (see below). In Phase 1, `main()` is not exercised — only `detect(repo_root)` is called by tests. Leave `main()` intact; it will need updating in Phase 5 when the command glue lands.

**Public API** (lines 146-164) — the function tests and consumers use:
```python
def detect(repo_root: Path) -> list[dict]:
    """Returns sorted list of container classification dicts."""
```

---

### `cores/vault-io/src/vault_io/_workspace.py` (utility) — ADAPTED PORT

**Analog:** `/Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/_workspace.py`

**Port instruction:** Do NOT copy verbatim. The `lattice_workspace` package does not exist in deep-agents. Replace the entire implementation:

```python
"""Workspace path resolution for vault-io.

In deep-agents, the vault path is always supplied explicitly via the
CODE_WIKI_REAL_VAULT_PATH environment variable or as a direct Path argument.
There is no lattice-workspace discovery in this codebase.
"""
from __future__ import annotations

import os
from pathlib import Path


def resolve_wiki_and_repo(
    vault_path: Path | None = None,
) -> tuple[Path, Path | None]:
    """Return (wiki_path, repo_root).

    Priority:
    1. `vault_path` argument if provided
    2. CODE_WIKI_REAL_VAULT_PATH env var
    3. Raises RuntimeError — no fallback heuristic (avoids wrong-path silent failures)
    """
    if vault_path is not None:
        return vault_path.resolve(), None
    env = os.environ.get("CODE_WIKI_REAL_VAULT_PATH")
    if env:
        return Path(env).resolve(), None
    raise RuntimeError(
        "Vault path not specified. "
        "Set CODE_WIKI_REAL_VAULT_PATH or pass vault_path explicitly."
    )
```

**Why adapted not verbatim:** The original fallback (`Path("lattice").resolve()`) would silently point at a nonexistent path in deep-agents. The adapted version raises loudly on misconfiguration, which matches the project's "actionable error" philosophy (D-09).

---

### `cores/vault-io/src/vault_io/scan_monorepo.py` (utility, batch) — VERBATIM PORT with import surgery

**Analog:** `/Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/scan_monorepo.py`

**Port instruction:** Copy verbatim. Import changes:
- `from lattice_wiki_core._version_check import ...` → remove
- `from lattice_wiki_core._workspace import resolve_wiki_and_repo` → `from vault_io._workspace import resolve_wiki_and_repo`
- `from lattice_wiki_core.layout_io import read_layout` → `from vault_io.layout_io import read_layout`

The `main()` call to `check_for_updates()` should be removed. Everything else is unchanged — `detect_packages()`, `diff_vault()`, and `scan()` are the public API Phase 5 will use.

---

### `cores/vault-io/src/vault_io/init_vault.py` (utility, file-I/O) — ADAPTED PORT

**Analog:** `/Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/init_vault.py`

**Port instruction:** Copy with two adaptations:
1. Remove `from lattice_workspace.init import init as workspace_init` and its call in `main()` — lattice-workspace is not in deep-agents.
2. Replace `from lattice_wiki_core.*` imports with `from vault_io.*`.

The core vault directory structure creation (`FIXED_VAULT_DIRS`, template copying, `write_layout`) is ported verbatim. The `main()` function's `workspace_init()` call is stubbed with a comment: `# TODO Phase 5: workspace init (lattice-workspace equivalent)`.

---

### `cores/vault-io/src/vault_io/append_log.py` (utility, file-I/O) — VERBATIM PORT with import surgery

**Analog:** `/Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/append_log.py`

**Port instruction:** Copy verbatim. Import changes:
- `from lattice_wiki_core._version_check import check_for_updates` → remove
- `from lattice_wiki_core._workspace import resolve_wiki_and_repo` → `from vault_io._workspace import resolve_wiki_and_repo`

**Stderr error pattern** (lines 41-46) — copy this error helper pattern to all vault-io modules with `main()`:
```python
def _error(message, as_json=False):
    if as_json:
        print(json.dumps({"status": "error", "message": message}))
    else:
        print(f"[error] {message}", file=sys.stderr)
    sys.exit(1)
```

---

### `cores/vault-io/src/vault_io/update_index.py` and `graph_analyzer.py` — VERBATIM PORTS with import surgery

**Analogs:**
- `/Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/update_index.py`
- `/Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/graph_analyzer.py`

**Port instruction:** Copy verbatim. Apply the same import surgery pattern as `scan_monorepo.py`: replace `lattice_wiki_core.*` with `vault_io.*`, remove `_version_check` imports and their call sites.

---

### `cores/vault-io/src/vault_io/lint/common.py` (utility, transform) — VERBATIM PORT

**Analog:** `/Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/lint/common.py`

**Port instruction:** Copy verbatim. No import changes needed — `lint/common.py` has no internal imports in the source.

**Wikilink placeholder predicate** — extract this function into `lint/common.py` from `lint_wiki.py` (the predicate lives in `lint_wiki.py` in the source but belongs in `common.py` for the port, per CONTEXT.md):
```python
def _is_placeholder_target(target: str) -> bool:
    """Returns True for template tokens like [[wiki/...]], [[work/<slug>]].

    Placeholder targets contain template markers (..., <, or >)
    and should not be treated as broken links.
    """
    return "..." in target or "<" in target or ">" in target
```

**Wikilink regex** (line 10) — also port from `common.py`:
```python
WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
```

---

### `cores/model-adapter/src/model_adapter/loader.py` (service, request-response) — GREENFIELD

**Analog:** None. Use pattern from RESEARCH.md Pattern 5 (already fully specified).

**Imports pattern:**
```python
from __future__ import annotations
import tomllib
from pathlib import Path
import botocore.exceptions
from langchain_aws import ChatBedrockConverse
from model_adapter.exceptions import BedrockAccessDenied
```

**models.toml path resolution** — use `Path(__file__)` relative to locate the TOML at package root, not at `src/`:
```python
# models.toml sits at cores/model-adapter/models.toml, two levels above loader.py
# which is at cores/model-adapter/src/model_adapter/loader.py
_MODELS_TOML = Path(__file__).parent.parent.parent / "models.toml"
```

**Error wrapping pattern** — wrap the invoke method, not the constructor:
```python
def _wrap_access_denied(llm: ChatBedrockConverse, model_id: str) -> ChatBedrockConverse:
    original_invoke = llm.invoke
    def invoke_with_error(*args, **kwargs):
        try:
            return original_invoke(*args, **kwargs)
        except botocore.exceptions.ClientError as e:
            if e.response["Error"]["Code"] == "AccessDeniedException":
                raise BedrockAccessDenied(
                    f"Bedrock access denied.\n"
                    f"  Model ARN attempted: {model_id}\n"
                    f"  IAM action required: bedrock:InvokeModel\n"
                    f"  Add an IAM policy with: "
                    f'  {{"Effect":"Allow","Action":"bedrock:InvokeModel",'
                    f'"Resource":"arn:aws:bedrock:*::foundation-model/*"}}\n'
                    f"  Original error: {e}"
                ) from e
            raise
    llm.invoke = invoke_with_error  # type: ignore[method-assign]
    return llm
```

**Assumption flagged in RESEARCH.md:** If `ChatBedrockConverse` uses `__slots__` or a custom `__setattr__`, monkey-patching `llm.invoke` will fail. Safer fallback: subclass `ChatBedrockConverse` and override `_generate`. Verify against `langchain-aws` 1.4.6 during implementation.

---

### `cores/model-adapter/models.toml` (config) — GREENFIELD

**Analog:** None.

**Full content** (verified ARNs from RESEARCH.md):
```toml
[roles.haiku]
model_id = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
region   = "us-east-1"

[roles.sonnet]
model_id = "us.anthropic.claude-sonnet-4-6"
region   = "us-east-1"
```

---

### `agents/code-wiki-agent/src/code_wiki_agent/cli.py` (utility, request-response) — GREENFIELD

**Analog:** None in lattice-wiki (the plugin is Claude Code, not a CLI). Use Typer pattern from CLAUDE.md.

**Full Phase 1 stub** (minimal — just `--help` working, per INFRA-06):
```python
from __future__ import annotations
import typer

app = typer.Typer(
    name="code-wiki-agent",
    help="code-wiki-agent: AWS Bedrock-powered wiki maintenance CLI.",
    no_args_is_help=True,
)

@app.command()
def version() -> None:
    """Print version and exit."""
    typer.echo("code-wiki-agent 0.1.0")

if __name__ == "__main__":
    app()
```

**Entry point registration** in `agents/code-wiki-agent/pyproject.toml`:
```toml
[project.scripts]
code-wiki-agent = "code_wiki_agent.cli:app"
```

---

### `agents/code-wiki-agent/src/code_wiki_mcp/server.py` (service, request-response) — GREENFIELD

**Analog:** None. Use pattern from RESEARCH.md Pattern 6 (already fully specified).

**Critical ordering constraint:** `_StdoutGuard` must be installed and `sys.stdout` rebound before ANY other import that could trigger library-level stdout writes. This means the guard must be the first executable statement after the `from __future__ import annotations` line.

```python
from __future__ import annotations
import sys

class _StdoutGuard:
    """Raise immediately if any non-FastMCP code writes to stdout."""
    def write(self, data: str) -> int:
        if data.strip():
            raise RuntimeError(
                f"Illegal stdout write in MCP server: {data!r}\n"
                "All logging must go to sys.stderr."
            )
        return len(data)
    def flush(self) -> None:
        pass

sys.stdout = _StdoutGuard()  # type: ignore[assignment]

# All other imports come AFTER the guard is installed
import logging
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel
```

**Tool schema pattern** — fully typed Pydantic models (not raw dicts):
```python
class PingInput(BaseModel):
    message: str = "ping"

class PingOutput(BaseModel):
    status: str
    echo: str

@mcp.tool(
    name="wiki_ping",
    description="Returns pong; used to verify MCP wiring is intact.",
)
def wiki_ping(input: PingInput) -> PingOutput:
    return PingOutput(status="pong", echo=input.message)
```

**Entry point** — `mcp.run()` with no args defaults to stdio; be explicit to guard against future defaults changing:
```python
def main() -> None:
    mcp.run(transport="stdio")
```

---

### `cores/vault-io/tests/conftest.py` (test) — ROLE-MATCH

**Analog:** `/Users/pat/Personal/lattice/packages/lattice-wiki-core/tests/conftest.py` + `helpers.py`

**Port instruction:** The lattice analog uses `sys.path.insert(0, ...)` to make `helpers.py` importable — do NOT copy this pattern. With `--import-mode=importlib`, put helpers directly in `conftest.py` or a `tests/helpers.py` imported via relative path.

**Recommended conftest.py pattern** (adapts the `tmp_repo` + `write_file` helpers into pytest fixtures):
```python
from __future__ import annotations
import shutil
import tempfile
from pathlib import Path
import pytest

@pytest.fixture
def tmp_repo(tmp_path: Path) -> Path:
    """Return a fresh temp directory (pytest tmp_path variant)."""
    return tmp_path

def write_file(path: Path, content: str = "") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path

@pytest.fixture
def vault_path(tmp_path: Path) -> Path:
    """Return a minimal vault directory with a single test page."""
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    return wiki
```

**Round-trip fixture** — how to discover the committed vault snapshot:
```python
FIXTURE_VAULT = Path(__file__).parent / "fixtures" / "round-trip-vault"

@pytest.fixture
def round_trip_vault() -> Path:
    """Return path to the committed vault fixture (or real vault if env var set)."""
    import os
    override = os.environ.get("CODE_WIKI_REAL_VAULT_PATH")
    if override:
        return Path(override)
    return FIXTURE_VAULT
```

---

### `cores/vault-io/tests/test_round_trip.py` (test, file-I/O)

**Analog:** `/Users/pat/Personal/lattice/packages/lattice-wiki-core/tests/test_update_tokens.py` (structure) and `test_layout_io.py` (round-trip assertion style)

**Core test pattern** — read page, write to tmp, compare bytes:
```python
import subprocess
from pathlib import Path
import pytest

def test_round_trip_all_fixture_pages(round_trip_vault: Path, tmp_path: Path):
    """git diff must be empty after reading and re-writing every fixture page."""
    import shutil
    # Copy the fixture vault to a temp location so we can write into it
    copy = tmp_path / "vault"
    shutil.copytree(round_trip_vault, copy)
    # Run the token updater over the copy (the only write-path in Phase 1)
    from vault_io.update_tokens import update_vault
    import tiktoken
    enc = tiktoken.get_encoding("cl100k_base")
    # First pass stamps tokens; second pass must be all-unchanged
    update_vault(copy)
    result = update_vault(copy)
    assert result["updated"] == [], (
        f"Second pass should be unchanged but updated: {result['updated']}"
    )
    # git diff the copy against the original fixture
    diff = subprocess.run(
        ["git", "diff", "--no-index", str(round_trip_vault), str(copy)],
        capture_output=True, text=True
    )
    assert diff.returncode == 0, (
        f"Round-trip produced diffs:\n{diff.stdout[:2000]}"
    )
```

---

### `cores/vault-io/tests/test_truncated_frontmatter.py` (test, file-I/O)

**Analog:** `/Users/pat/Personal/lattice/packages/lattice-wiki-core/tests/test_update_tokens.py` lines 127-137 — exact test already exists in the source.

**Copy pattern verbatim** (adjust imports only):
```python
def test_update_page_skips_truncated_frontmatter(tmp_path: Path):
    import tiktoken
    enc = tiktoken.get_encoding("cl100k_base")
    page = tmp_path / "truncated.md"
    page.write_text("---\ntitle: No closing fence\ncategory: concept\n", encoding="utf-8")
    before = page.read_text(encoding="utf-8")

    from vault_io.update_tokens import update_page
    status, count = update_page(page, enc, dry_run=False)
    assert status == "skipped"
    assert count == 0
    assert page.read_text(encoding="utf-8") == before
```

**Stderr assertion** — add a `capsys` check to verify the warning is emitted:
```python
def test_truncated_frontmatter_emits_stderr_warning(tmp_path: Path, capsys):
    # ... same setup ...
    update_page(page, enc, dry_run=False)
    err = capsys.readouterr().err
    assert "no closing frontmatter fence" in err
    assert str(page) in err or page.name in err
```

---

### `cores/vault-io/tests/test_wikilink_predicate.py` (test, transform)

**Analog:** `/Users/pat/Personal/lattice/packages/lattice-wiki-core/tests/test_lint_wikilink_placeholders.py`

**Port instruction:** Copy the test class verbatim. Change imports:
- `from lattice_wiki_core.lint_wiki import _is_placeholder_target` → `from vault_io.lint.common import _is_placeholder_target`

The four test methods (`test_detects_ellipsis_as_placeholder`, `test_detects_angle_brackets_as_placeholder`, `test_rejects_normal_wiki_links`, `test_rejects_empty_and_simple_targets`) are copied unchanged.

---

### `agents/code-wiki-agent/tests/unit/test_cli_help.py` (test, request-response) — GREENFIELD

**Pattern:**
```python
import subprocess
import sys

def test_cli_help_exits_zero():
    result = subprocess.run(
        ["uv", "run", "--package", "code-wiki-agent", "code-wiki-agent", "--help"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f"--help exited {result.returncode}\n{result.stderr}"
    assert "code-wiki-agent" in result.stdout.lower()
```

---

### `agents/code-wiki-agent/tests/integration/test_mcp_stdio.py` (test, request-response) — GREENFIELD

**Pattern:** Use exactly as specified in RESEARCH.md Pattern 7. No modifications needed — the pattern is already concrete and complete. Key assertion: every stdout line must be valid JSON-RPC with a `jsonrpc` key.

---

### `agents/code-wiki-agent/tests/integration/test_bedrock_iam.py` (test, request-response) — GREENFIELD

**Pattern:**
```python
import os
import pytest

pytestmark = pytest.mark.integration

def test_make_llm_haiku_invoke(monkeypatch):
    if not os.environ.get("CODE_WIKI_RUN_INTEGRATION"):
        pytest.skip("Set CODE_WIKI_RUN_INTEGRATION=1 to run Bedrock tests")
    from model_adapter.loader import make_llm
    llm = make_llm("haiku")
    result = llm.invoke("ping")
    assert result.content  # non-empty response

def test_make_llm_raises_bedrock_access_denied_on_bad_creds(monkeypatch):
    """BedrockAccessDenied must include the model ARN in its message."""
    import botocore.exceptions
    from model_adapter.loader import make_llm
    from model_adapter.exceptions import BedrockAccessDenied

    llm = make_llm("haiku")
    # Simulate AccessDeniedException from botocore
    def fake_invoke(*args, **kwargs):
        raise botocore.exceptions.ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "denied"}},
            "InvokeModel",
        )
    # Patch the underlying invoke before wrapping
    object.__setattr__(llm, "_original_invoke", llm.invoke)
    llm.invoke = fake_invoke

    with pytest.raises(BedrockAccessDenied) as exc_info:
        llm.invoke("ping")
    assert "us.anthropic.claude-haiku-4-5-20251001-v1:0" in str(exc_info.value)
    assert "bedrock:InvokeModel" in str(exc_info.value)
```

---

### `scripts/verify_bedrock_iam.py` (utility, request-response) — GREENFIELD

**Pattern** (standalone diagnostic; not a pytest test):
```python
#!/usr/bin/env python3
"""Verify AWS Bedrock IAM permissions from scratch.

Run this on a new account before anything else:
    uv run python scripts/verify_bedrock_iam.py
"""
from __future__ import annotations
import sys
from pathlib import Path

# Allow running from repo root without installing the package
sys.path.insert(0, str(Path(__file__).parent.parent / "cores" / "model-adapter" / "src"))

from model_adapter.loader import make_llm
from model_adapter.exceptions import BedrockAccessDenied

def main() -> None:
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
```

---

## Shared Patterns

### Import Surgery Rule (all verbatim-port files)

**Apply to:** All ported `vault_io/*.py` files that import from `lattice_wiki_core`.

**Rule:** For every internal import of the form `from lattice_wiki_core.X import Y`, change to `from vault_io.X import Y`. For every `from lattice_wiki_core._version_check import check_for_updates`, delete the import and remove all `check_for_updates(...)` call sites (the function is not ported).

**No other changes** to ported files. Behavior must be byte-identical to the source.

---

### Stderr-Only Logging

**Source:** RESEARCH.md Pattern 6 (`_StdoutGuard`) and `update_tokens.py` lines 77, 92 (`print(..., file=sys.stderr)`)

**Apply to:** All modules that run under MCP stdio (everything in `code_wiki_mcp/`). All vault-io modules that emit warnings use `print(..., file=sys.stderr)` — copy this verbatim from the source.

**Pattern for warnings in vault-io modules:**
```python
print(f"[warn] skipping {path}: <reason>", file=sys.stderr)
```

**Pattern for errors in vault-io modules with `main()`:**
```python
print(f"[error] <message>", file=sys.stderr)
sys.exit(1)
```

---

### `from __future__ import annotations`

**Source:** All lattice-wiki-core files use this as their first import.

**Apply to:** All new Python files in this phase. It is not optional — it is the project convention established by the source codebase.

---

### `encoding="utf-8"` on all file I/O

**Source:** Every `read_text` / `write_text` in the lattice-wiki-core source specifies `encoding="utf-8"` explicitly.

**Apply to:** All `Path.read_text()` and `Path.write_text()` calls in ported and new files.

---

### Per-Member Test Isolation

**Apply to:** `cores/vault-io/pyproject.toml`, `cores/model-adapter/pyproject.toml`, `agents/code-wiki-agent/pyproject.toml`

Each member's `[tool.pytest.ini_options]` must include:
```toml
testpaths = ["tests"]
addopts = "--import-mode=importlib"
```

This ensures `uv run --package vault-io pytest` only collects vault-io tests, and `uv run --package code-wiki-agent pytest` only collects agent tests.

---

## No Analog Found

Files with no analog in the lattice-wiki source (planner uses RESEARCH.md patterns for these):

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `cores/model-adapter/src/model_adapter/loader.py` | service | request-response | No Python Bedrock loader exists in lattice-wiki (it uses the Claude Code plugin SDK, not LangChain) |
| `cores/model-adapter/src/model_adapter/exceptions.py` | utility | — | Custom exception class; no equivalent |
| `cores/model-adapter/models.toml` | config | — | No model registry TOML in lattice-wiki |
| `agents/code-wiki-agent/src/code_wiki_agent/cli.py` | utility | request-response | lattice-wiki is a Claude Code plugin, not a CLI |
| `agents/code-wiki-agent/src/code_wiki_mcp/server.py` | service | request-response | lattice-wiki is a Claude Code plugin, not an MCP server |
| `.github/workflows/ci.yml` | config | — | No CI in lattice-wiki |

---

## Metadata

**Analog search scope:**
- `/Users/pat/Personal/lattice/packages/lattice-wiki-core/src/lattice_wiki_core/` (primary source)
- `/Users/pat/Personal/lattice/packages/lattice-wiki-core/tests/` (test patterns)
- `/Users/pat/Personal/lattice/pyproject.toml` (workspace root pattern)

**Files scanned:** 15 source files + 8 test files + 2 config files

**Pattern extraction date:** 2026-05-13

**Key constraint reminder:** RESEARCH.md Pattern 5 (`make_llm` wrapper) contains an assumption (A1) that monkey-patching `llm.invoke` works on `ChatBedrockConverse`. If it does not, the subclass-override fallback must be used. Verify this during implementation of `loader.py` before writing the test.
