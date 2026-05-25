---
phase: quick-260521-mfm
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - plugins/graph-wiki/skills/graph-wiki/scripts/_uv_reexec.py
  - plugins/graph-wiki/skills/graph-wiki/scripts/detect_containers.py
  - plugins/graph-wiki/skills/graph-wiki/scripts/ingest_source.py
  - plugins/graph-wiki/skills/graph-wiki/scripts/init_vault.py
  - plugins/graph-wiki/skills/graph-wiki/scripts/lint_wiki.py
  - plugins/graph-wiki/skills/graph-wiki/scripts/scan_monorepo.py
  - plugins/graph-wiki/skills/graph-wiki/scripts/wiki_search.py
autonomous: true
requirements: []

must_haves:
  truths:
    - "Running `python plugins/graph-wiki/skills/graph-wiki/scripts/detect_containers.py --help` from the repo root succeeds (no ModuleNotFoundError) because the shim re-execs itself under uv."
    - "If `GRAPH_WIKI_SHIM_REEXEC=1` is already set in the environment, the shim does NOT re-exec a second time — it lets the original ImportError surface."
    - "Each of the 6 shims calls `_uv_reexec.ensure()` before importing anything from `vault_io`."
  artifacts:
    - path: "plugins/graph-wiki/skills/graph-wiki/scripts/_uv_reexec.py"
      provides: "ensure() helper that re-execs the current script under `uv run --project <repo>/packages/vault-io` on ImportError of vault_io"
      contains: "def ensure"
    - path: "plugins/graph-wiki/skills/graph-wiki/scripts/detect_containers.py"
      provides: "Simple shim updated to call _uv_reexec.ensure() before importing vault_io"
      contains: "_uv_reexec"
  key_links:
    - from: "plugins/graph-wiki/skills/graph-wiki/scripts/detect_containers.py"
      to: "plugins/graph-wiki/skills/graph-wiki/scripts/_uv_reexec.py"
      via: "from _uv_reexec import ensure; ensure()"
      pattern: "_uv_reexec"
    - from: "plugins/graph-wiki/skills/graph-wiki/scripts/_uv_reexec.py"
      to: "packages/vault-io/pyproject.toml"
      via: "walk-up search for the workspace package, then os.execvpe('uv', ['uv', 'run', '--project', <pkg_dir>, ...])"
      pattern: "packages/vault-io/pyproject.toml"
---

<objective>
Make the 6 graph-wiki plugin shim scripts self-healing: when invoked with bare `python script.py` outside the `uv` workspace, they should detect the missing `vault_io` import, re-exec themselves under `uv run --project <repo>/packages/vault-io python <self> <args...>`, and use an env-var guard to prevent infinite re-exec loops.

Purpose: Today every `/graph-wiki:*` command in the installed plugin must be invoked via `uv run --project "$DEEP_AGENTS_ROOT" python ...` (per the 260521-kxi doc fix). Making the shims self-healing lets bare `python <shim>` work too, removing a class of user setup errors and the need to keep `uv run --project` plumbed through every command body.

Output: One new helper module (`_uv_reexec.py`) and 6 modified shims, each calling `_uv_reexec.ensure()` before its top-level `vault_io` import.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@CLAUDE.md
@plugins/graph-wiki/CLAUDE.md
@plugins/graph-wiki/skills/graph-wiki/scripts/detect_containers.py
@plugins/graph-wiki/skills/graph-wiki/scripts/init_vault.py
@plugins/graph-wiki/skills/graph-wiki/scripts/_config.py

<interfaces>
<!-- Shape of all 6 existing shims, distilled from reads. Executor should not need to re-read these. -->

`detect_containers.py` (simple shim) — current contents:
- Shebang `#!/usr/bin/env python3`
- Docstring
- `import sys`
- `from vault_io.detect_containers import main`  ← the import that fails when run bare
- `if __name__ == "__main__": main()`

`init_vault.py` (dispatching shim) — current shape:
- Shebang + docstring
- `import subprocess`, `import sys`
- `from vault_io.init_vault import main as _core_main`  ← the import that fails when run bare
- Local `def main()` that reads `_config.backend_for("init")` and either subprocesses `graph-wiki-agent init <args>` or calls `_core_main()`
- `if __name__ == "__main__": main()`

The other four dispatching shims (`ingest_source.py`, `lint_wiki.py`, `scan_monorepo.py`, `wiki_search.py`) follow the same dispatching pattern as `init_vault.py` — each imports a `main as _core_main` from a `vault_io.<name>` submodule, then dispatches via `_config.backend_for`. Confirm exact module paths with `grep -n '^from vault_io' plugins/graph-wiki/skills/graph-wiki/scripts/*.py` before editing.

`_config.py` — unchanged by this plan. Its `workspace_io` import is wrapped in `try/except Exception` already; do not touch it.
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create _uv_reexec.py helper with ensure() and walk-up workspace discovery</name>
  <files>plugins/graph-wiki/skills/graph-wiki/scripts/_uv_reexec.py</files>
  <action>
Create a new module at `plugins/graph-wiki/skills/graph-wiki/scripts/_uv_reexec.py` exposing a single public function `ensure() -> None`.

Behavior:
1. If the env var `GRAPH_WIKI_SHIM_REEXEC` is set (any truthy/non-empty value), return immediately. This is the re-entry guard — we have already re-execed once; if the import still fails after that, let the caller's `from vault_io...` raise naturally so the user sees a real error instead of an infinite loop.
2. Try `import vault_io`. If it succeeds, return — we are already inside the uv workspace environment, no re-exec needed.
3. On `ImportError` (or `ModuleNotFoundError`): walk up the directory tree starting from `Path(__file__).resolve().parent`, looking at each ancestor for a file at `<ancestor>/packages/vault-io/pyproject.toml`. Stop at the filesystem root. If found, that ancestor is the repo root; pass `<ancestor>/packages/vault-io` as the `--project` argument to `uv run`.
4. If no `packages/vault-io/pyproject.toml` is found anywhere up the tree, return without re-execing. Letting the caller's import raise the original `ModuleNotFoundError` is more useful than swallowing it here.
5. When the workspace path is found: build a new env dict from `os.environ` with `GRAPH_WIKI_SHIM_REEXEC=1` added, then call `os.execvpe("uv", ["uv", "run", "--project", str(workspace_pkg_dir), "python", sys.argv[0], *sys.argv[1:]], new_env)`. `execvpe` replaces the current process — control does not return.

Implementation notes:
- The helper file MUST NOT import `vault_io` at module top level (it is the chicken-and-egg shim bootstrap; importing the thing it is checking for would defeat the purpose). The `import vault_io` belongs inside `ensure()`'s try block.
- Keep the file small (~30 lines incl. blank lines). Imports: `os`, `sys`, `from pathlib import Path`. No other dependencies.
- Use a module docstring AND inline comments to explain WHY this exists (chicken-and-egg shim bootstrap: shims live inside the plugin tree but depend on a workspace package; users may invoke them with bare `python` from outside `uv run`; we re-exec to recover).
- Walk-up termination: stop when `path == path.parent` (filesystem root sentinel), not by a fixed parent-index count — per the constraint to avoid `parents[N]` indexing.
- Look specifically for `packages/vault-io/pyproject.toml` (the file), not just the directory, to avoid false positives from empty/stale `packages/vault-io/` folders elsewhere on disk.
- No try/except on the `os.execvpe` call itself — if `uv` is not on PATH, the OSError will surface with a clear message, which is the correct behavior (user needs `uv` installed).
- No `argparse`, no `__main__` block, no validation of `sys.argv[0]` — it is whatever the caller's interpreter ran, which is exactly what we want to re-exec.
  </action>
  <verify>
    <automated>cd /Users/pat/Personal/agent-research &amp;&amp; python plugins/graph-wiki/skills/graph-wiki/scripts/_uv_reexec.py 2>&amp;1 || true; python -c "import sys; sys.path.insert(0, 'plugins/graph-wiki/skills/graph-wiki/scripts'); import _uv_reexec; assert hasattr(_uv_reexec, 'ensure'), 'ensure() missing'; print('OK: _uv_reexec.ensure exists')"</automated>
  </verify>
  <done>
File `plugins/graph-wiki/skills/graph-wiki/scripts/_uv_reexec.py` exists, is ~30 lines, defines `ensure() -> None`, does not import `vault_io` at top level, walks up looking for `packages/vault-io/pyproject.toml`, and uses `os.execvpe` with `GRAPH_WIKI_SHIM_REEXEC=1` guard set in the child env.
  </done>
</task>

<task type="auto">
  <name>Task 2: Wire ensure() into all 6 shim scripts before their vault_io imports</name>
  <files>plugins/graph-wiki/skills/graph-wiki/scripts/detect_containers.py, plugins/graph-wiki/skills/graph-wiki/scripts/ingest_source.py, plugins/graph-wiki/skills/graph-wiki/scripts/init_vault.py, plugins/graph-wiki/skills/graph-wiki/scripts/lint_wiki.py, plugins/graph-wiki/skills/graph-wiki/scripts/scan_monorepo.py, plugins/graph-wiki/skills/graph-wiki/scripts/wiki_search.py</files>
  <action>
In each of the 6 shim files, insert a call to `_uv_reexec.ensure()` BEFORE any `from vault_io...` import. The call must run at module top level (not inside a function), so that re-exec happens during interpreter startup before any workspace-package import can fail.

Required insertion pattern at the top of each shim, AFTER the shebang/docstring and AFTER any pure-stdlib imports (`sys`, `subprocess`, `os`, `pathlib`), but BEFORE the first `from vault_io...` line:

```
from _uv_reexec import ensure as _ensure_uv

_ensure_uv()
```

This works because each shim is invoked as a script — Python adds the script's own directory (`plugins/graph-wiki/skills/graph-wiki/scripts/`) to `sys.path[0]`, which is where `_uv_reexec.py` lives. This is the same mechanism by which `init_vault.py` already does `from _config import backend_for` inside `main()`.

Concretely:

- `detect_containers.py`: insert the two new lines between `import sys` and `from vault_io.detect_containers import main`.
- `init_vault.py`: insert between `import sys` and `from vault_io.init_vault import main as _core_main`.
- `ingest_source.py`, `lint_wiki.py`, `scan_monorepo.py`, `wiki_search.py`: same insertion pattern — after stdlib imports, before the first `from vault_io...` import. If you have not already, `grep -n '^from vault_io' plugins/graph-wiki/skills/graph-wiki/scripts/*.py` to confirm the exact line in each.

Do NOT:
- Refactor any dispatching logic (`backend_for`, subprocess fan-out to `graph-wiki-agent`) — leave the rest of each shim's body untouched.
- Wrap the `_ensure_uv()` call in try/except — if `_uv_reexec` itself is missing (e.g., the user has a partial install), the resulting `ImportError` is the correct failure mode and the user should fix their install.
- Change `_config.py` — its `workspace_io` import is already guarded inside a `try/except Exception` and is not in scope for this plan.
- Add type hints or rename the alias — `from _uv_reexec import ensure as _ensure_uv` keeps the call site distinctive at a glance and avoids shadowing any local `ensure` name in `init_vault`'s subprocess-dispatch code path.
  </action>
  <verify>
    <automated>cd /Users/pat/Personal/agent-research &amp;&amp; for f in detect_containers ingest_source init_vault lint_wiki scan_monorepo wiki_search; do path="plugins/graph-wiki/skills/graph-wiki/scripts/$f.py"; grep -q '_uv_reexec' "$path" || { echo "MISSING ensure() in $f"; exit 1; }; grep -n '_uv_reexec\|from vault_io' "$path" | awk -F: 'BEGIN{r=0;v=0} /_uv_reexec/{if(r==0)r=$1} /from vault_io/{if(v==0)v=$1} END{if(r==0||v==0||r>=v){print "ORDER BAD in '"$f"': reexec="r" vault_io="v; exit 1}}' || exit 1; done; echo 'OK: all 6 shims call _uv_reexec before vault_io import'</automated>
  </verify>
  <done>
All 6 shims contain `from _uv_reexec import ensure as _ensure_uv` followed by a `_ensure_uv()` call, both appearing on lines strictly before the file's first `from vault_io...` import. No other changes to dispatching logic.
  </done>
</task>

<task type="auto">
  <name>Task 3: End-to-end smoke test — bare `python` invocation succeeds via re-exec</name>
  <files>(no file changes — verification task)</files>
  <action>
Verify the self-healing behavior end-to-end. The cheapest deterministic check is to invoke one of the shims with bare `python` (NOT `uv run python`) from the repo root and confirm it does not fail with `ModuleNotFoundError: No module named 'vault_io'`.

Steps:

1. From `/Users/pat/Personal/agent-research`, run:
   `python plugins/graph-wiki/skills/graph-wiki/scripts/detect_containers.py --help`
   This should print the underlying `vault_io.detect_containers` help text (or whatever the tool emits when given `--help` / when it has no required args), NOT a `ModuleNotFoundError`. The shim should silently re-exec under `uv run --project .../packages/vault-io python ...` and the user-visible output should look the same as if the user had typed `uv run --project . python ...` themselves.

2. Then verify the re-entry guard works — running with `GRAPH_WIKI_SHIM_REEXEC=1` already set should bypass re-exec. If `vault_io` is not importable in the current interpreter (which is the case when running bare `python` outside `uv run`), this MUST fail with the original `ModuleNotFoundError`, not an infinite loop:
   `GRAPH_WIKI_SHIM_REEXEC=1 python plugins/graph-wiki/skills/graph-wiki/scripts/detect_containers.py --help`
   Expected: `ModuleNotFoundError: No module named 'vault_io'`. This proves the guard short-circuits and the original import surfaces.

3. Sanity check: invoking via `uv run --project /Users/pat/Personal/agent-research python plugins/graph-wiki/skills/graph-wiki/scripts/detect_containers.py --help` should still work as before (no regression). The first `import vault_io` inside `ensure()` will succeed and the function returns immediately.

If step 1 fails with `ModuleNotFoundError` despite the shim being wired correctly, the most likely cause is that `uv` is not on PATH for the bare-`python` subshell — investigate by running `which uv` and confirming it is in the env that `os.execvpe` will inherit.

Note: this task adds no files and is verification-only. If steps 1-3 all pass, the plan is done.
  </action>
  <verify>
    <automated>cd /Users/pat/Personal/agent-research &amp;&amp; OUT=$(python plugins/graph-wiki/skills/graph-wiki/scripts/detect_containers.py --help 2>&amp;1); EC=$?; echo "$OUT" | grep -qi 'No module named'\''vault_io'\''\|ModuleNotFoundError.*vault_io' &amp;&amp; { echo "FAIL: bare python still errors with ModuleNotFoundError"; echo "$OUT"; exit 1; }; echo "OK: bare python invocation did not ModuleNotFoundError (exit=$EC)"; GUARD_OUT=$(GRAPH_WIKI_SHIM_REEXEC=1 python plugins/graph-wiki/skills/graph-wiki/scripts/detect_containers.py --help 2>&amp;1 || true); echo "$GUARD_OUT" | grep -qi 'ModuleNotFoundError\|No module named' &amp;&amp; echo "OK: guard env var short-circuits re-exec (original ImportError surfaces)" || { echo "WARN: guard test did not surface ModuleNotFoundError — may indicate vault_io is importable in the current interpreter; manual confirmation needed"; }</automated>
  </verify>
  <done>
Bare `python <shim> --help` from the repo root succeeds (no `ModuleNotFoundError`) AND running the same command with `GRAPH_WIKI_SHIM_REEXEC=1` already set produces the original `ModuleNotFoundError` (proving no infinite loop). No regression for `uv run --project ... python <shim>` invocation.
  </done>
</task>

</tasks>

<verification>
- `python plugins/graph-wiki/skills/graph-wiki/scripts/detect_containers.py --help` from the repo root succeeds without `ModuleNotFoundError`.
- `GRAPH_WIKI_SHIM_REEXEC=1 python plugins/graph-wiki/skills/graph-wiki/scripts/detect_containers.py --help` surfaces the original `ModuleNotFoundError` (proves guard works).
- `grep -L '_uv_reexec' plugins/graph-wiki/skills/graph-wiki/scripts/{detect_containers,ingest_source,init_vault,lint_wiki,scan_monorepo,wiki_search}.py` returns nothing (every shim is wired).
- `_uv_reexec.py` does not contain `vault_io` at module top level (the helper must not depend on the thing it bootstraps).
</verification>

<success_criteria>
- 6 shims are self-healing: bare `python <shim>` works from the repo root.
- A re-entry guard env var (`GRAPH_WIKI_SHIM_REEXEC=1`) prevents infinite re-exec.
- `_uv_reexec.py` is small (~30 lines), well-commented for the WHY, no excess validation.
- Workspace discovery walks up from `__file__` looking for `packages/vault-io/pyproject.toml` (no `parents[N]` indexing).
- No changes to `_config.py`, no changes to dispatching logic in any shim, no changes to docs.
</success_criteria>

<output>
Create `.planning/quick/260521-mfm-add-self-healing-uv-re-exec-to-graph-wik/260521-mfm-SUMMARY.md` when done.
</output>
