---
phase: 01-infrastructure-vault-io-and-mcp-skeleton
reviewed: 2026-05-13T00:00:00Z
depth: standard
files_reviewed: 33
files_reviewed_list:
  - .github/workflows/ci.yml
  - agents/code-wiki-agent/pyproject.toml
  - agents/code-wiki-agent/src/code_wiki_agent/cli.py
  - agents/code-wiki-agent/src/code_wiki_mcp/server.py
  - agents/code-wiki-agent/tests/integration/test_bedrock_iam.py
  - agents/code-wiki-agent/tests/integration/test_mcp_stdio.py
  - agents/code-wiki-agent/tests/unit/test_cli_help.py
  - agents/code-wiki-agent/tests/unit/test_stdout_guard.py
  - cores/model-adapter/models.toml
  - cores/model-adapter/pyproject.toml
  - cores/model-adapter/src/model_adapter/exceptions.py
  - cores/model-adapter/src/model_adapter/loader.py
  - cores/model-adapter/tests/test_loader.py
  - cores/vault-io/pyproject.toml
  - cores/vault-io/src/vault_io/_workspace.py
  - cores/vault-io/src/vault_io/append_log.py
  - cores/vault-io/src/vault_io/detect_containers.py
  - cores/vault-io/src/vault_io/git_state.py
  - cores/vault-io/src/vault_io/graph_analyzer.py
  - cores/vault-io/src/vault_io/init_vault.py
  - cores/vault-io/src/vault_io/layout_io.py
  - cores/vault-io/src/vault_io/lint/common.py
  - cores/vault-io/src/vault_io/scan_monorepo.py
  - cores/vault-io/src/vault_io/update_index.py
  - cores/vault-io/src/vault_io/update_tokens.py
  - cores/vault-io/tests/conftest.py
  - cores/vault-io/tests/test_layout_io_smoke.py
  - cores/vault-io/tests/test_ports_importable.py
  - cores/vault-io/tests/test_round_trip.py
  - cores/vault-io/tests/test_truncated_frontmatter.py
  - cores/vault-io/tests/test_wikilink_predicate.py
  - pyproject.toml
  - scripts/verify_bedrock_iam.py
findings:
  critical: 4
  warning: 5
  info: 3
  total: 12
status: issues_found
---

# Phase 01: Code Review Report

**Reviewed:** 2026-05-13T00:00:00Z
**Depth:** standard
**Files Reviewed:** 33
**Status:** issues_found

## Summary

Phase 1 ships a walking skeleton: a Bedrock model loader, a FastMCP stdio server, a vault-io port, and a CI pipeline. The MCP server wiring is clean — the `_StdoutGuard` is correctly installed before any other import and the `_GuardedChatBedrockConverse` subclass-override strategy soundly works around Pydantic v2's `extra='forbid'`. The test suite is well-structured with clear integration/unit separation.

Four blockers were found:

1. `update_tokens.py` uses `tiktoken` with `cl100k_base` (OpenAI's GPT-4 tokenizer). CLAUDE.md explicitly prohibits this for Bedrock/Claude models and mandates the Bedrock CountTokens API. Token counts stored in vault frontmatter will be systematically wrong for Claude models.

2. Three CLI `main()` entry points (`detect_containers`, `scan_monorepo`, `init_vault`) always exit with error code 1 in v1 because `resolve_wiki_and_repo()` always returns `(wiki, None)` for `repo`, and each `main()` immediately exits on `repo is None`. These scripts are completely non-functional as standalone tools.

3. `graph_analyzer.connected_components()` produces phantom nodes (`"log"` and `"index"`) in component membership. Wikilinks found in `log.md` / `index.md` add those files' keys to `inb[resolved]` sets, then the BFS traverses those keys even though they were excluded from `nodes`. Component size counts and sample arrays in the output are corrupted.

4. `layout_io._parse_yaml()` crashes with an unhandled `ValueError` if the `version:` field is not a pure integer (e.g., `version: 2.0` or `version: draft`). Line 121 calls `int(out["version"])` with no error handling.

Five warnings were found including a fragile `models.toml` path that breaks on non-editable installs, a false Go workspace discovery claim in `scan_monorepo`'s docstring, a zombie-process risk in the MCP stdio test, a hardcoded version string in `cli.py` that will drift, and a subprocess resource leak on timeout.

## Critical Issues

### CR-01: `tiktoken` (`cl100k_base`) used for token counting — wrong tokenizer for Claude/Bedrock models

**File:** `cores/vault-io/src/vault_io/update_tokens.py:29-41`
**Issue:** `update_tokens.py` imports `tiktoken` and uses the `cl100k_base` encoding (GPT-4's BPE tokenizer) to count tokens stamped into vault frontmatter. CLAUDE.md explicitly prohibits `tiktoken` for this project: "tiktoken — OpenAI-specific BPE tokenizer, does not work with Claude or Bedrock models" and lists it in the Avoid table. The `vault-io/pyproject.toml` also lists `tiktoken>=0.7` as a direct dependency, violating the project constraint. Token counts stored under `tokens:` frontmatter keys will be systematically incorrect for Claude/Bedrock models, making any downstream budget estimation based on those counts unreliable.

**Fix:** Replace with the Bedrock CountTokens API. The boto3 call is synchronous and requires model ID and region:

```python
import boto3

def count_tokens(text: str, model_id: str = "us.anthropic.claude-haiku-4-5-20251001-v1:0", region: str = "us-east-1") -> int:
    client = boto3.client("bedrock-runtime", region_name=region)
    response = client.count_tokens(
        modelId=model_id,
        content=[{"text": text}],
    )
    return response["inputTokenCount"]
```

Remove `tiktoken>=0.7` from `cores/vault-io/pyproject.toml` and replace with `boto3>=1.38` (already required by model-adapter).

---

### CR-02: `detect_containers.py`, `scan_monorepo.py`, and `init_vault.py` CLI `main()` entry points always exit with error code 1

**File:** `cores/vault-io/src/vault_io/detect_containers.py:172-175`, `cores/vault-io/src/vault_io/scan_monorepo.py:1082-1085`, `cores/vault-io/src/vault_io/init_vault.py:295-298`
**Issue:** All three scripts call `resolve_wiki_and_repo()` and then check `if repo is None: sys.exit(1)`. The `_workspace.resolve_wiki_and_repo()` implementation always returns `(wiki, None)` for `repo` in v1 (the docstring at line 18 explicitly states "repo_root is always None in v1"). This means all three CLI scripts are broken as standalone commands — they always print `"[error] could not resolve repo root from workspace"` and exit. The underlying library functions (`detect()`, `discover_workspaces()`, `init_wiki()`) are fine when called programmatically with explicit arguments; only the CLI entry points are broken.

**Fix:** Each `main()` should derive `repo_root` from `wiki.parent` or accept it as an explicit `--repo` argument, rather than depending on `resolve_wiki_and_repo()` to supply it:

```python
# detect_containers.py main()
wiki, _ = resolve_wiki_and_repo()
repo = wiki.parent  # v1: repo is always wiki's parent directory
if not repo.exists():
    print(f"[error] repo not found: {repo}", file=sys.stderr)
    sys.exit(1)
```

Apply the same pattern to `scan_monorepo.main()` and `init_vault.main()`.

---

### CR-03: `graph_analyzer.connected_components()` introduces phantom nodes from `log.md`/`index.md`

**File:** `cores/vault-io/src/vault_io/graph_analyzer.py:113-114`, `133-154`
**Issue:** In `build_graph()`, `index.md` and `log.md` are excluded from `nodes` (first loop, line 76) but are still processed in the second loop (line 84). For these `is_index=True` files, wikilinks add their key (`"log"` or `"index"`) to `inb[resolved]` sets (line 114: `inb[resolved].add(key)`). In `connected_components()`, the BFS builds `adj[n]` as `out[n] | inb[n]` and traverses the entire adjacency, including non-`nodes` keys. When a real page links to something and that link is recorded with `"log"` as the source, `adj[real_page]` includes `"log"`. The BFS adds `"log"` to the component even though it is not in `nodes`. The component's `size` and `sample` arrays are then wrong.

**Fix:** Filter the BFS traversal to only include keys that are in `nodes`:

```python
def connected_components(nodes, out, inb):
    adj = defaultdict(set)
    for n in nodes:
        adj[n] |= (out.get(n, set()) & nodes)   # only follow edges to real nodes
        adj[n] |= (inb.get(n, set()) & nodes)   # only accept inbound from real nodes
    seen = set()
    components = []
    for n in nodes:
        if n in seen:
            continue
        stack = [n]
        comp = set()
        while stack:
            v = stack.pop()
            if v in seen:
                continue
            seen.add(v)
            comp.add(v)
            stack.extend(adj[v] - seen)
        components.append(comp)
    components.sort(key=len, reverse=True)
    return components
```

---

### CR-04: `layout_io._parse_yaml()` crashes with unhandled `ValueError` on non-integer `version:` field

**File:** `cores/vault-io/src/vault_io/layout_io.py:120-122`
**Issue:** `_parse_yaml()` calls `int(out["version"])` unconditionally if the key exists. If a layout block contains a version value that is not a pure integer (for example `version: 2.0` produced by a different YAML serializer, or `version: draft` in a hand-edited file), `int()` raises `ValueError` which propagates uncaught to all callers of `read_layout()`. Callers include `scan_monorepo._load_existing_pages()` (called on every scan) and `init_vault.init_wiki()`. A single malformed `CLAUDE.md` would break the entire scan.

**Fix:** Wrap the conversion defensively:

```python
if "version" in out:
    try:
        out["version"] = int(out["version"])
    except (ValueError, TypeError):
        out["version"] = 1  # fall back to v1 schema
```

## Warnings

### WR-01: `models.toml` path fragile — breaks on non-editable install

**File:** `cores/model-adapter/src/model_adapter/loader.py:29`
**Issue:** `_MODELS_TOML = Path(__file__).parent.parent.parent / "models.toml"` resolves correctly only in the editable workspace layout (`src/model_adapter/loader.py` → `../../models.toml`). Under a non-editable wheel install `__file__` points inside `site-packages/model_adapter/` and the three-parent traversal lands outside the project. `pyproject.toml` declares no `[tool.uv.build.include]` or `package-data` entry, so `models.toml` is not bundled into the wheel. While uv workspaces always install editable, this is a brittle assumption that will break at first non-editable install (Docker, release wheel, CI outside the workspace).

**Fix:** Move `models.toml` under `src/model_adapter/models.toml` and load it via `importlib.resources`:

```python
from importlib import resources

def _load_models_config() -> dict:
    with resources.files("model_adapter").joinpath("models.toml").open("rb") as f:
        return tomllib.load(f)
```

---

### WR-02: `scan_monorepo.py` docstring claims Go workspace discovery that is not implemented

**File:** `cores/vault-io/src/vault_io/scan_monorepo.py:15`
**Issue:** The module docstring lists "go.mod + go.work (Go)" as a supported discovery method. `_discover_heuristic()` does not contain any Go workspace collection code — it handles Node/pnpm, Rust Cargo, Python pyproject, and Claude plugins only. `_infer_language()` can detect Go as the language of an already-found package (line 166), but no code walks `go.work` or discovers Go module roots. A developer relying on the documented behavior to scan a Go monorepo will get an empty workspace list with no error.

**Fix:** Either implement Go workspace discovery, or remove "go.mod + go.work (Go)" from the docstring and add a TODO:

```
Detects workspace packages from (in priority order):
  - package.json + pnpm-workspace.yaml / workspaces field  (Node/pnpm/yarn/npm)
  - pyproject.toml                                         (Python — poetry/hatch/uv)
  - Cargo.toml with [workspace]                            (Rust)
  - .claude-plugin/plugin.json                             (Claude Code plugins)
  # TODO: go.mod + go.work (Go) — not yet implemented
```

---

### WR-03: `_run_server` timeout leaves zombie process and swallows diagnostic

**File:** `agents/code-wiki-agent/tests/integration/test_mcp_stdio.py:71-76`
**Issue:** `proc.communicate(timeout=15)` raises `subprocess.TimeoutExpired` on timeout. The `finally` block calls `proc.kill()` but does not follow up with `proc.communicate()` to reap stdout/stderr from the killed process. The `TimeoutExpired` exception then propagates with no useful diagnostic (no stderr dump). The child process becomes a zombie until the test runner exits.

**Fix:**

```python
def _run_server(payload_objs: list[dict]) -> tuple[str, str]:
    payload = "\n".join(json.dumps(obj) for obj in payload_objs) + "\n"
    proc = subprocess.Popen(
        ["uv", "run", "--package", "code-wiki-agent", "code-wiki-mcp"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        stdout_bytes, stderr_bytes = proc.communicate(input=payload.encode(), timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()
        stdout_bytes, stderr_bytes = proc.communicate()  # reap zombie, collect output
        pytest.fail(
            f"MCP server did not respond within 15s.\nstderr: {stderr_bytes.decode()[:500]}"
        )
    return stdout_bytes.decode(), stderr_bytes.decode()
```

---

### WR-04: `cli.py` version string is hardcoded and will drift from `pyproject.toml`

**File:** `agents/code-wiki-agent/src/code_wiki_agent/cli.py:15`
**Issue:** `typer.echo("code-wiki-agent 0.1.0")` hardcodes the version string. When the version in `pyproject.toml` is bumped, the `version` command output will silently fall behind. This is particularly misleading because Typer and pip both support `importlib.metadata.version()` for dynamic version reads.

**Fix:**

```python
import importlib.metadata

@app.command()
def version() -> None:
    """Print version and exit."""
    v = importlib.metadata.version("code-wiki-agent")
    typer.echo(f"code-wiki-agent {v}")
```

---

### WR-05: `detect_containers.py` Rule 1 (docs) only fires on flat directories; subdirectoried docs containers are never classified as docs

**File:** `cores/vault-io/src/vault_io/detect_containers.py:87`
**Issue:** Rule 1 classifies a directory as `docs` only when `not children` (no subdirectories). A typical `docs/` container with nested subdirectories (`docs/api/`, `docs/guides/`) would never receive the `docs` classification — it falls through to the ambiguous bucket. This is a logic error: the classification should be based on the overall proportion of markdown content, not on whether any subdirectories exist at all.

**Fix:** Remove the `not children` guard and extend the markdown-ratio check to cover both files and recursed children, or at minimum add a recursive markdown check:

```python
# Rule 1: docs container — predominantly markdown, no manifests anywhere
total_files = sum(1 for p in d.rglob("*") if p.is_file() and not p.name.startswith("."))
md_count = sum(1 for p in d.rglob("*.md") if not p.name.startswith("."))
if total_files and not has_manifest_in_root and md_count / total_files >= DOC_THRESHOLD:
    if not any(_has_manifest(c) for c in children):
        return {"source": d.name, "classification": "docs", ...}
```

## Info

### IN-01: `update_tokens.py` reconstructs `parts = raw.split("---", 2)` twice

**File:** `cores/vault-io/src/vault_io/update_tokens.py:87,107`
**Issue:** The same `raw.split("---", 2)` call appears at line 87 (for baseline construction) and again at line 107 (for the write path). This is redundant: `parts` from the first split is still in scope and valid. The duplication can cause confusion if one call is modified and the other is not.

**Fix:**

```python
parts = raw.split("---", 2)
if len(parts) < 3:
    print(f"[warn] skipping {path}: no closing frontmatter fence", file=sys.stderr)
    return ("skipped", 0)
# ... use parts for both baseline and write path
```

---

### IN-02: `Cargo.toml` multi-line `members` arrays are silently skipped in `_parse_cargo_toml`

**File:** `cores/vault-io/src/vault_io/scan_monorepo.py:105`
**Issue:** `_parse_cargo_toml` applies `re.search(r"members\s*=\s*\[(.*?)\]", s, re.DOTALL)` to a single line `s` inside the line-by-line loop. Real `Cargo.toml` files almost always declare members across multiple lines:

```toml
members = [
  "crates/foo",
  "crates/bar",
]
```

The single-line regex never matches this form, so Rust workspaces with multi-line member arrays are silently treated as having no members. The `re.DOTALL` flag is ineffective when applied to a single-line string.

**Fix:** Collect all lines in the `[workspace]` section first, then apply the regex to the full section text:

```python
if section == "[workspace]":
    workspace_lines.append(s)
# After the loop:
workspace_text = "\n".join(workspace_lines)
m = re.search(r"members\s*=\s*\[(.*?)\]", workspace_text, re.DOTALL)
```

---

### IN-03: CI workflow `push` trigger has no branch filter — runs on every branch push

**File:** `.github/workflows/ci.yml:3-5`
**Issue:** The `on: push` trigger fires on every branch without restriction. For a solo project this is fine, but as the repo gains contributors or feature branches, every push (including WIP pushes) triggers a full CI run including `uv sync`. Adding a branch filter or a path filter prevents unnecessary runs.

**Fix:**

```yaml
on:
  push:
    branches: [main]
  pull_request:
```

---

_Reviewed: 2026-05-13T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
