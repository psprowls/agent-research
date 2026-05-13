---
phase: 01-infrastructure-vault-io-and-mcp-skeleton
reviewed: 2026-05-13T00:00:00Z
depth: standard
files_reviewed: 39
files_reviewed_list:
  - .github/workflows/ci.yml
  - .github/workflows/eval.yml
  - .pre-commit-config.yaml
  - agents/code-wiki-agent/pyproject.toml
  - agents/code-wiki-agent/src/code_wiki_agent/__init__.py
  - agents/code-wiki-agent/src/code_wiki_agent/cli.py
  - agents/code-wiki-agent/src/code_wiki_mcp/__init__.py
  - agents/code-wiki-agent/src/code_wiki_mcp/server.py
  - agents/code-wiki-agent/tests/integration/test_bedrock_iam.py
  - agents/code-wiki-agent/tests/integration/test_mcp_stdio.py
  - agents/code-wiki-agent/tests/unit/test_cli_help.py
  - agents/code-wiki-agent/tests/unit/test_stdout_guard.py
  - cores/model-adapter/models.toml
  - cores/model-adapter/pyproject.toml
  - cores/model-adapter/src/model_adapter/__init__.py
  - cores/model-adapter/src/model_adapter/exceptions.py
  - cores/model-adapter/src/model_adapter/loader.py
  - cores/model-adapter/tests/test_loader.py
  - cores/vault-io/pyproject.toml
  - cores/vault-io/src/vault_io/__init__.py
  - cores/vault-io/src/vault_io/_workspace.py
  - cores/vault-io/src/vault_io/append_log.py
  - cores/vault-io/src/vault_io/detect_containers.py
  - cores/vault-io/src/vault_io/git_state.py
  - cores/vault-io/src/vault_io/graph_analyzer.py
  - cores/vault-io/src/vault_io/init_vault.py
  - cores/vault-io/src/vault_io/layout_io.py
  - cores/vault-io/src/vault_io/lint/__init__.py
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
  critical: 1
  warning: 7
  info: 4
  total: 12
status: issues_found
---

# Phase 01: Code Review Report

**Reviewed:** 2026-05-13
**Depth:** standard
**Files Reviewed:** 39 (vault-io ports treated as historical; new code scrutinized in depth)
**Status:** issues_found

## Summary

Phase 1 ships a walking skeleton (Bedrock loader + FastMCP stdio entry + vault-io port + CI). The new code is generally tight: the `_StdoutGuard` is correctly installed before any other import; the `_GuardedChatBedrockConverse` subclass-override strategy works around Pydantic v2 `extra='forbid'`; the integration vs unit split is sound and tests pass locally.

Primary defect: **`cores/model-adapter/models.toml` is not packaged into the built wheel**, so `make_llm()` raises `FileNotFoundError` for any consumer that installs the package from a wheel rather than the editable workspace. This is a distribution-time blocker that the editable-install CI does not catch.

Secondary defects: stale `lattice-workspace` references in three vault-io module docstrings actively mislead readers (they document an env var that this codebase does not read), and one of those strings leaks into the user-facing `init_wiki` result JSON.

vault-io modules are verbatim ports per the format-compatibility constraint and were not scrutinized for stylistic issues; only correctness regressions and leaked references that affect this project are reported below.

## Critical Issues

### CR-01: `models.toml` is not included in the model-adapter wheel; `make_llm()` will FileNotFoundError under any non-editable install

**File:** `cores/model-adapter/pyproject.toml` (whole file) + `cores/model-adapter/src/model_adapter/loader.py:29`

**Issue:** `loader.py` computes `_MODELS_TOML = Path(__file__).parent.parent.parent / "models.toml"`, which resolves to `cores/model-adapter/models.toml` only in the editable workspace layout (`cores/model-adapter/src/model_adapter/loader.py` → `../../models.toml`). The `pyproject.toml` uses `uv_build` with no `[tool.uv.build.include]`, `[tool.hatch.build.targets.wheel.shared-data]`, or PEP 517 `package-data` declaration. Therefore `uv build` produces a wheel that contains only `src/model_adapter/`; `models.toml` is silently dropped. Once installed from that wheel, `make_llm()` calls `Path(__file__).parent.parent.parent` which now points two directories above `site-packages/model_adapter/` — not a project root — and `open(_MODELS_TOML, "rb")` raises `FileNotFoundError`.

CI currently runs everything through `uv sync` (editable) so the bug is invisible. The first time the package is installed as a wheel (release, CI cache rebuild on a non-workspace consumer, or Docker image build), every `make_llm()` call breaks.

**Fix:** Ship `models.toml` alongside the package and load it via `importlib.resources`:

```python
# 1) Move models.toml under the package so it's auto-included in the wheel:
#    cores/model-adapter/src/model_adapter/models.toml

# 2) Replace the path math in loader.py with importlib.resources:
from importlib import resources

def _load_models_config() -> dict:
    with resources.files("model_adapter").joinpath("models.toml").open("rb") as f:
        return tomllib.load(f)
```

Alternatively, keep `models.toml` at the package root and declare it explicitly:

```toml
# cores/model-adapter/pyproject.toml
[tool.uv.build]
module-name = "model_adapter"
# Include the sibling config file in the sdist; then move it under src/ for the wheel.
```

The `importlib.resources` approach is the standard fix and removes the `parent.parent.parent` fragility. Add a regression test that builds the wheel (`uv build`) and verifies `make_llm("haiku")` works against the installed artifact.

## Warnings

### WR-01: `vault_io/append_log.py` docstring claims `LATTICE_WORKSPACE` env var; codebase actually reads `CODE_WIKI_REAL_VAULT_PATH`

**File:** `cores/vault-io/src/vault_io/append_log.py:8-9`

**Issue:** The module docstring says "Discovers wiki location from the resolved lattice workspace. Requires LATTICE_WORKSPACE env var or git repo with lattice/ workspace directory." That description was true upstream but is false here: `_workspace.resolve_wiki_and_repo` only consults `CODE_WIKI_REAL_VAULT_PATH` and the explicit `vault_path` argument. A developer following the docstring will set the wrong env var and get a `RuntimeError`. The same false claim appears in `detect_containers.py:6` and `graph_analyzer.py:5`.

**Fix:** Update the three docstrings to reflect the actual contract:

```python
# append_log.py top docstring
"""
append_log.py — Append a standardized entry to wiki/log.md.

The log is append-only and uses a consistent header so unix tools can parse it:
    ## [YYYY-MM-DD] <op> | <title>

Discovers wiki location via vault_io._workspace.resolve_wiki_and_repo, which
requires either an explicit vault_path argument or the
CODE_WIKI_REAL_VAULT_PATH environment variable.
"""
```

### WR-02: `init_vault.py` emits `"owned by lattice-workspace"` strings into the user-facing result JSON

**File:** `cores/vault-io/src/vault_io/init_vault.py:241-242,246-247`

**Issue:** The `result["layers"]` dict returned by `init_wiki()` (and printed to stdout / surfaced via JSON) contains:

```python
"raw": f"{workspace_path}/raw/ — owned by lattice-workspace",
"work": f"{workspace_path}/work/ — owned by lattice-workspace",
```

`lattice-workspace` is not part of this codebase; the `raw/` and `work/` directories are never created here (the TODO at line 155 even says "Phase 5: workspace init (lattice-workspace equivalent)"). Users see a layer description that points at non-existent directories owned by a non-existent component. The `next_steps` strings at 246-247 ("Open `{workspace_path}` in Obsidian") share the same confusion.

**Fix:** Either suppress the `raw`/`work` entries until Phase 5 lands a workspace bootstrap equivalent, or replace the "owned by lattice-workspace" annotation with a Phase 5 deferral notice:

```python
"layers": {
    "wiki": f"{wiki_path}/ — LLM-maintained knowledge base",
    "index": f"{wiki_path}/index.md",
    "log": f"{wiki_path}/log.md",
    # raw/ and work/ layers deferred to Phase 5 workspace bootstrap.
},
```

### WR-03: `_MODELS_TOML` parent-traversal is path-fragile and breaks under any layout move

**File:** `cores/model-adapter/src/model_adapter/loader.py:29`

**Issue:** `Path(__file__).parent.parent.parent / "models.toml"` hardcodes the assumption that `loader.py` sits exactly three directories above `models.toml`. Any future restructuring (e.g., flattening `src/` into the package root, splitting modules into subpackages) silently breaks model loading. This is the same root cause as CR-01 but separable: even within the editable workspace, the path math is brittle. `importlib.resources` removes both problems at once.

**Fix:** Use `importlib.resources` as shown in CR-01; this both packages the file correctly and removes the parent-traversal.

### WR-04: `scripts/verify_bedrock_iam.py` has no test coverage and no smoke import check

**File:** `scripts/verify_bedrock_iam.py` (whole file)

**Issue:** The script is the documented manual gate for IAM verification, but no test imports it. A typo, accidental top-level `print` (which would later be discovered when the script is run from an MCP host), or broken import chain would not be caught by any CI run. The script's `main()` does its imports lazily so it's importable cheaply — a 3-line smoke test would catch regressions for free.

**Fix:** Add a unit test under `agents/code-wiki-agent/tests/unit/` or a new `scripts/tests/`:

```python
def test_verify_bedrock_iam_module_imports():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "verify_bedrock_iam",
        Path(__file__).parents[3] / "scripts" / "verify_bedrock_iam.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert callable(mod.main)
```

### WR-05: MCP stdio integration tests run unmarked in the default ("not integration") set despite spawning a subprocess

**File:** `agents/code-wiki-agent/tests/integration/test_mcp_stdio.py:80,115`

**Issue:** The file's docstring asserts this is intentional ("Intentionally NOT marked as an integration-only test (D-16): runs in CI by default because wiki_ping never calls Bedrock"). But the tests still:
1. Spawn `uv run --package code-wiki-agent code-wiki-mcp` (cold-starts uv, resolves the workspace, builds and launches a subprocess) — ~1 second per test;
2. Live inside `tests/integration/` so a developer naturally assumes the `-m integration` filter excludes them.

The directory placement plus the absence of the marker is misleading: it violates the convention the rest of the file structure sets. Either the tests belong in `tests/unit/` (since they exercise wiring, not Bedrock), or they should carry a separate `subprocess` marker.

**Fix:** Move the file to `tests/unit/test_mcp_stdio.py` (the docstring already explains why it runs in the unit set), or add a `subprocess` pytest marker registered in `pyproject.toml` and used to filter slow-but-network-free tests.

### WR-06: `proc.kill()` in `_run_server` finally-block leaves zombie processes on timeout

**File:** `agents/code-wiki-agent/tests/integration/test_mcp_stdio.py:71-77`

**Issue:** When `proc.communicate(timeout=15)` raises `TimeoutExpired`, the `finally` block calls `proc.kill()` and then the exception propagates without a second `communicate()` call to reap the child. On Linux CI runners the kill signal will be reaped by the runner's init eventually, but during local runs the test process holds onto a defunct child until the parent exits. More importantly, the test fails with a stack trace pointing at `communicate` rather than a clean assertion failure.

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
        stdout_bytes, stderr_bytes = proc.communicate(
            input=payload.encode(), timeout=15
        )
    except subprocess.TimeoutExpired:
        proc.kill()
        stdout_bytes, stderr_bytes = proc.communicate()
        raise
    return stdout_bytes.decode(), stderr_bytes.decode()
```

This reaps the child on timeout and avoids the unconditional `proc.kill()` after a successful `communicate()` (which is harmless but pointless).

### WR-07: `_StdoutGuard` exposes the raw binary buffer; any library writing via `sys.stdout.buffer.write(b"...")` bypasses the guard silently

**File:** `agents/code-wiki-agent/src/code_wiki_mcp/server.py:39`

**Issue:** The guard caches `buffer = _ORIGINAL_STDOUT.buffer` so FastMCP can build its JSON-RPC writer. That is correct and necessary — FastMCP must own the raw fd. But any other library that imports `sys.stdout` and writes through `.buffer.write(b"oops\n")` will corrupt the JSON-RPC stream without tripping the guard. The class docstring acknowledges this ("All subsequent JSON-RPC frames go through that wrapper directly, bypassing write() below"), but it does not warn that the same hole exists for arbitrary writers.

This is currently a theoretical hole — boto3/botocore/anyio do not write to `sys.stdout.buffer` directly. But the protection is one-sided: high-level text writes are caught loudly, low-level binary writes pass silently. If a future dependency starts emitting telemetry through `sys.stdout.buffer` (e.g., a tracing library that thinks it owns stdout), MCP framing breaks with no diagnostic.

**Fix:** Wrap the buffer in a similar guard that distinguishes "framing writes from FastMCP" (legal) from "everyone else" (illegal). Since FastMCP captures `.buffer` exactly once at startup, you can hand it a wrapper that flips to read-only after first capture:

```python
class _BufferGuard:
    def __init__(self, real_buffer):
        self._real = real_buffer
        self._captured = False

    def write(self, b):
        if self._captured:
            raise RuntimeError(f"Illegal stdout.buffer write: {b!r}")
        return self._real.write(b)
    # ... proxy the rest of the BufferedWriter API FastMCP uses,
    # and flip self._captured = True after FastMCP grabs the buffer.
```

If that is too invasive for v1, at minimum document the gap as a known hole in the module docstring so future maintainers do not assume the guard is airtight.

## Info

### IN-01: `code_wiki_agent/__init__.py` and `code_wiki_mcp/__init__.py` are empty

**File:** `agents/code-wiki-agent/src/code_wiki_agent/__init__.py`, `agents/code-wiki-agent/src/code_wiki_mcp/__init__.py`

**Issue:** Both files are single blank lines. Acceptable as namespace markers under PEP 420-compatible layouts, but `__init__.py` could declare `__all__` and a package version. Optional polish.

**Fix:** Either leave as-is or add a minimal:
```python
__version__ = "0.1.0"
```

### IN-02: `eval.yml` workflow is a literal stub

**File:** `.github/workflows/eval.yml:10-11`

**Issue:** The workflow only runs `echo "Eval workflow stub - implemented in Phase 4"`. Acceptable per the Phase 4 deferral, but the file ships in `main` with a `workflow_dispatch` trigger that does nothing useful. A developer who runs it gets no signal.

**Fix:** Either gate behind a TODO and remove the trigger until Phase 4, or have the stub run a smoke test (e.g., `uv run --directory cores/model-adapter pytest`) so the workflow at least proves it can boot.

### IN-03: `pyproject.toml` ruff lint selection is narrow

**File:** `pyproject.toml:18-19`

**Issue:** `select = ["E", "F", "I"]` covers pycodestyle errors, pyflakes, and import ordering but omits `B` (flake8-bugbear catches mutable defaults, useless except, etc.) and `UP` (pyupgrade). For a Python 3.11+ codebase, `UP` would catch deprecated patterns automatically. Optional.

**Fix:**
```toml
[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP"]
```

### IN-04: Ruff pre-commit hook auto-fixes can mask CI failures

**File:** `.pre-commit-config.yaml:5-6`

**Issue:** The pre-commit hook runs `ruff --fix`, which silently rewrites code before commit. CI runs `ruff check .` (no `--fix`). The hook will fix issues that would otherwise fail in CI — fine for clean diffs, but it means the developer never sees the diagnostic. If they push without running pre-commit (e.g., `git commit --no-verify`), CI catches the issue but the developer has no local muscle memory for the rule. Optional behavioral note; common pattern; flag-only.

**Fix:** No change required. If desired, swap `--fix` for the default (report-only) so developers see the diagnostic locally too:

```yaml
- id: ruff
  # remove `args: [--fix]` so the hook reports rather than rewrites
```

---

_Reviewed: 2026-05-13_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
