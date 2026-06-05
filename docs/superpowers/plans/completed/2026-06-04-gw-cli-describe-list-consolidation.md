# gw CLI `describe` / `list` Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Collapse the 10 `gw graph describe-<kind>` and 6 of the 7 `gw graph list-<kind>` subcommands into two dispatcher commands — `gw graph describe <selector> [--kind K]` and `gw graph list --kind K` — cutting the `graph` surface from 31 to ~17 commands without losing any capability.

**Architecture:** Two thin **router modules** (`q_describe.py`, `q_list.py`) own a kind→module dispatch table and delegate to the *existing, already-tested* per-kind `q_describe_*` / `q_list_*` `run(args)` functions, which are kept as internal library helpers (only their Typer command registrations are removed). `describe` resolves the kind from an explicit `--kind` or, when omitted, infers it (no-selector→repo, `builtin:` prefix→builtin, single cross-kind name match→that kind, ambiguous→error, otherwise→path). The old command names are dropped entirely (single-dev research repo, no external consumers, no migrations pre-v2.0 per `.claude/rules/backward-compatibility.md`).

**Tech Stack:** Python 3.11, Typer, `uv` workspace, pytest (subprocess-driven CLI tests against a `--mode test` graph DB).

---

## Background the engineer needs

- **Run scoping.** This package is `graph-wiki-cli`. Run its tests with `uv run --package graph-wiki-cli pytest <path>` from the repo root `/Users/pat/Personal/agent-research`. Never run bare `pytest` from the root.
- **Command surface lives in** `packages/graph-wiki-cli/src/graph_wiki_cli/graph_cli/main.py`. Each leaf command is a `@graph_app.command(...)` function whose body calls the shared helper `_run(module, ctx, **kwargs)` (main.py:80-84). `_run` builds an `args` namespace from the `--repo/--fmt/--mode` callback, copies in the `**kwargs` as attributes, and does `raise typer.Exit(code=module.run(args))`.
- **Each per-kind module** (e.g. `q_describe_package.py`, `q_list_apps.py`) exposes `run(args) -> int` that opens the graph DB read-only, runs one query, prints human or `--fmt json` output, and returns an `exit_codes.*` int. These modules are NOT changing — we only stop registering them as Typer commands and instead call them through the routers.
- **Exit codes** (`graph_io.exit_codes`): `SUCCESS=0`, `GENERIC=1`, `NOT_INITIALIZED=3`, `SCHEMA_MISMATCH=4`, `AMBIGUOUS=7`.
- **CLI test invocation pattern** (used across the test files):
  ```python
  def _cg(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
      return subprocess.run(
          [sys.executable, "-m", "graph_wiki_cli.graph_cli.main", "--repo", str(cwd), "--mode", "test", *args],
          capture_output=True, text=True,
      )
  ```
- **Graph node kinds** are mutually exclusive: a classified app is stored as `kind='app'` (NOT also `kind='package'`), so cross-kind name inference rarely collides. `describe_package` queries `kind='package'`, `describe_app` queries `kind='app'`.

## Kind vocabulary (lock these strings — used verbatim in later tasks)

**describe** (singular), with the module each routes to and the `args` attribute that module reads as its selector:

| `--kind` value | module | selector attr |
|---|---|---|
| `package` | `q_describe_package` | `name` |
| `app` | `q_describe_app` | `name` |
| `domain` | `q_describe_domain` | `name` |
| `suite` | `q_describe_suite` | `name` |
| `dependency` | `q_describe_dependency` | `name` (also reads `ecosystem`) |
| `agent-plugin` | `q_describe_agent_plugin` | `name` |
| `entry-point` | `q_describe_entry_point` | `name` |
| `builtin` | `q_describe_builtin` | `uri` |
| `path` | `q_describe_path` | `path` |
| `repo` | `q_describe_repo` | *(none)* |

**list** (plural): `apps`→`q_list_apps`, `builtins`→`q_list_builtins`, `packages`→`q_list_packages`, `scripts`→`q_list_scripts`, `suites`→`q_list_suites`, `domains`→`q_list_domains`.

**Deliberate carve-outs (do NOT fold):**
- `list-entry-points <package> [--kind executable|library]` stays its own command — it has a *required positional selector* and a different `--kind` axis; folding it into `list` would make `list`'s `--kind` mean two different things.
- `what-tests`, `domain-*`, `cross-cutting`, edge queries (`callers`/`imports`/…), and `ops` (`update`/`status`/…) are out of scope and untouched.

## File Structure

- **Create** `packages/graph-wiki-cli/src/graph_wiki_cli/graph_cli/q_list.py` — list dispatcher (kind→module table + `run`).
- **Create** `packages/graph-wiki-cli/src/graph_wiki_cli/graph_cli/q_describe.py` — describe dispatcher (kind→(module, selector-attr) table, `_resolve_kind` inference, `run`).
- **Modify** `packages/graph-wiki-cli/src/graph_wiki_cli/graph_cli/main.py` — swap imports; delete the 16 old command functions; add `describe` + `list` commands.
- **Create** `packages/graph-wiki-cli/tests/graph_cli/test_cli_describe_list_dispatch.py` — router behavior incl. inference + ambiguity.
- **Modify** `packages/graph-wiki-cli/tests/graph_cli/test_cli_smoke.py` — migrate old-name invocations.
- **Modify** `packages/graph-wiki-cli/tests/graph_cli/test_cli_exit_codes.py` — migrate old-name invocations.
- **Modify** `packages/graph-wiki-cli/tests/graph_cli/test_cli_anti_regression.py` — migrate old-name invocations.
- **Modify** `packages/graph-wiki-cli/tests/graph_cli/test_cli_main.py` — registry assertions for new/removed commands.
- **Modify** `docs/gw-cli.md` — document the new surface.

The existing module-level tests `test_cli_describe.py` and `test_cli_describe_entry_point.py` call `q_describe_*.run(SimpleNamespace(...))` directly and are **unaffected** (the modules are unchanged) — do not touch them.

---

### Task 1: `list` dispatcher

**Files:**
- Create: `packages/graph-wiki-cli/src/graph_wiki_cli/graph_cli/q_list.py`
- Modify: `packages/graph-wiki-cli/src/graph_wiki_cli/graph_cli/main.py`
- Test: `packages/graph-wiki-cli/tests/graph_cli/test_cli_smoke.py`

- [ ] **Step 1: Write the failing test**

Append to `packages/graph-wiki-cli/tests/graph_cli/test_cli_smoke.py` (it already defines `_cg` and the `populated_repo` fixture):

```python
# ── gw graph list --kind dispatcher ───────────────────────────────────────────
def test_list_packages_via_kind(populated_repo: Path) -> None:
    res = _cg(["list", "--kind", "packages"], populated_repo)
    assert res.returncode == 0, res.stderr
    assert "demo" in res.stdout


def test_list_unknown_kind_is_bad_parameter(populated_repo: Path) -> None:
    res = _cg(["list", "--kind", "wombats"], populated_repo)
    assert res.returncode == 2
    assert "kind must be one of" in res.stderr
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --package graph-wiki-cli pytest tests/graph_cli/test_cli_smoke.py::test_list_packages_via_kind -v`
Expected: FAIL — Typer reports `No such command 'list'`, returncode 2 but stderr lacks `demo`.

- [ ] **Step 3: Create the dispatcher module**

Create `packages/graph-wiki-cli/src/graph_wiki_cli/graph_cli/q_list.py`:

```python
"""gw graph list --kind <kind> — dispatch to the per-kind list modules.

The per-kind ``q_list_*`` modules are kept as library helpers; this router
only selects which one's ``run(args)`` to call. ``list-entry-points`` is NOT
routed here — it has a required positional package argument and a different
``--kind`` axis, so it remains its own command.
"""

from __future__ import annotations

from graph_wiki_cli.graph_cli import (
    q_list_apps,
    q_list_builtins,
    q_list_domains,
    q_list_packages,
    q_list_scripts,
    q_list_suites,
)

_DISPATCH = {
    "apps": q_list_apps,
    "builtins": q_list_builtins,
    "packages": q_list_packages,
    "scripts": q_list_scripts,
    "suites": q_list_suites,
    "domains": q_list_domains,
}
LIST_KINDS = tuple(_DISPATCH)


def run(args: object) -> int:
    return _DISPATCH[args.kind].run(args)
```

- [ ] **Step 4: Wire the `list` command and remove the old `list-*` commands**

In `packages/graph-wiki-cli/src/graph_wiki_cli/graph_cli/main.py`:

(a) In the `from graph_wiki_cli.graph_cli import (...)` block (lines 16-50), **remove** these six names — `q_list_apps`, `q_list_builtins`, `q_list_domains`, `q_list_packages`, `q_list_scripts`, `q_list_suites` — and **add** `q_list`. Keep `q_list_entry_points` (still used by `list-entry-points`). The block should still import everything else it imported before.

(b) **Delete** these six command functions entirely: `list_apps_cmd`, `list_builtins_cmd`, `list_packages_cmd`, `list_scripts_cmd`, `list_suites_cmd`, `list_domains_cmd` (the `@graph_app.command(name="list-apps")` etc. blocks). **Keep** `list_entry_points_cmd`.

(c) Add this command (place it near the other list/describe commands):

```python
@graph_app.command(name="list")
def list_cmd(
    ctx: typer.Context,
    kind: str = typer.Option(..., "--kind", "-k", help=f"Entity kind: {', '.join(q_list.LIST_KINDS)}."),
) -> None:
    """List graph entities of a given kind."""
    if kind not in q_list.LIST_KINDS:
        raise typer.BadParameter(f"kind must be one of: {', '.join(q_list.LIST_KINDS)}")
    _run(q_list, ctx, kind=kind)
```

- [ ] **Step 5: Migrate the existing `list-builtins` / `list-apps` smoke tests**

In `packages/graph-wiki-cli/tests/graph_cli/test_cli_smoke.py`, replace each old-name invocation argument list (the command verb only — leave `--fmt json` and the repo arg as-is):

- `_cg(["list-builtins"], ...)` → `_cg(["list", "--kind", "builtins"], ...)` (lines ~223, ~250)
- `_cg(["--fmt", "json", "list-builtins"], ...)` → `_cg(["--fmt", "json", "list", "--kind", "builtins"], ...)` (lines ~232, ~256)
- `_cg(["list-apps"], ...)` → `_cg(["list", "--kind", "apps"], ...)` (lines ~290, ~320)
- `_cg(["--fmt", "json", "list-apps"], ...)` → `_cg(["--fmt", "json", "list", "--kind", "apps"], ...)` (lines ~298, ~326)

Leave the assertions and docstrings unchanged.

- [ ] **Step 6: Run the smoke suite to verify it passes**

Run: `uv run --package graph-wiki-cli pytest tests/graph_cli/test_cli_smoke.py -v`
Expected: PASS — including the two new `list` tests and the migrated builtins/apps tests.

- [ ] **Step 7: Commit**

```bash
git add packages/graph-wiki-cli/src/graph_wiki_cli/graph_cli/q_list.py \
        packages/graph-wiki-cli/src/graph_wiki_cli/graph_cli/main.py \
        packages/graph-wiki-cli/tests/graph_cli/test_cli_smoke.py
git commit -m "feat(gw): consolidate list-* into 'gw graph list --kind'"
```

---

### Task 2: `describe` dispatcher with explicit `--kind`

**Files:**
- Create: `packages/graph-wiki-cli/src/graph_wiki_cli/graph_cli/q_describe.py`
- Modify: `packages/graph-wiki-cli/src/graph_wiki_cli/graph_cli/main.py`
- Test: `packages/graph-wiki-cli/tests/graph_cli/test_cli_describe_list_dispatch.py` (create)

This task adds `describe` with **explicit `--kind` only** (inference comes in Task 3). The `run` already reads `args.kind`; when `None` it falls through to a stub that returns `GENERIC` until Task 3 fills it in — but every test here passes `--kind`, so that path is unexercised this task.

- [ ] **Step 1: Write the failing test**

Create `packages/graph-wiki-cli/tests/graph_cli/test_cli_describe_list_dispatch.py`:

```python
"""gw graph describe/list dispatcher behavior (router + inference)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from ._git_repo import init_repo, write_and_commit


def _cg(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "graph_wiki_cli.graph_cli.main", "--repo", str(cwd), "--mode", "test", *args],
        capture_output=True, text=True,
    )


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    init_repo(tmp_path)
    write_and_commit(
        tmp_path,
        {
            "pyproject.toml": '[project]\nname = "demo"\nversion = "0.1.1"\n',
            "src/demo/__init__.py": "__all__ = ['delta']\n\ndef delta():\n    return 1\n",
        },
        "init",
    )
    res = _cg(["update", "--full"], tmp_path)
    assert res.returncode == 0, res.stderr
    return tmp_path


def test_describe_package_explicit_kind(repo: Path) -> None:
    res = _cg(["describe", "demo", "--kind", "package"], repo)
    assert res.returncode == 0, res.stderr
    assert "demo" in res.stdout


def test_describe_package_explicit_kind_json(repo: Path) -> None:
    res = _cg(["--fmt", "json", "describe", "demo", "--kind", "package"], repo)
    assert res.returncode == 0, res.stderr
    assert json.loads(res.stdout)["name"] == "demo"


def test_describe_unknown_kind_is_bad_parameter(repo: Path) -> None:
    res = _cg(["describe", "demo", "--kind", "wombat"], repo)
    assert res.returncode == 2
    assert "kind must be one of" in res.stderr


def test_describe_repo_explicit_kind_no_selector(repo: Path) -> None:
    res = _cg(["describe", "--kind", "repo"], repo)
    assert res.returncode == 0, res.stderr
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --package graph-wiki-cli pytest tests/graph_cli/test_cli_describe_list_dispatch.py -v`
Expected: FAIL — `No such command 'describe'`.

- [ ] **Step 3: Create the dispatcher module**

Create `packages/graph-wiki-cli/src/graph_wiki_cli/graph_cli/q_describe.py`:

```python
"""gw graph describe <selector> [--kind] — dispatch to the per-kind describe modules.

The per-kind ``q_describe_*`` modules are kept as library helpers; this router
selects which one's ``run(args)`` to call, copies the single ``selector`` onto
the attribute that module expects (``name`` / ``uri`` / ``path``), and — when
``--kind`` is omitted — infers the kind (see ``_resolve_kind``).
"""

from __future__ import annotations

import sys

from workspace_io.paths import graph_dir

from graph_io import exit_codes, store

from graph_wiki_cli.graph_cli import (
    q_describe_agent_plugin,
    q_describe_app,
    q_describe_builtin,
    q_describe_dependency,
    q_describe_domain,
    q_describe_entry_point,
    q_describe_package,
    q_describe_path,
    q_describe_repo,
    q_describe_suite,
)

# CLI kind -> (module, name of the args attribute that module reads as its selector)
_DISPATCH = {
    "package": (q_describe_package, "name"),
    "app": (q_describe_app, "name"),
    "domain": (q_describe_domain, "name"),
    "suite": (q_describe_suite, "name"),
    "dependency": (q_describe_dependency, "name"),
    "agent-plugin": (q_describe_agent_plugin, "name"),
    "entry-point": (q_describe_entry_point, "name"),
    "builtin": (q_describe_builtin, "uri"),
    "path": (q_describe_path, "path"),
    "repo": (q_describe_repo, None),
}
DESCRIBE_KINDS = tuple(_DISPATCH)

# Bare-name CLI kinds eligible for inference -> their DB node kind.
_INFER_DB_KIND = {
    "package": "package",
    "app": "app",
    "domain": "domain",
    "dependency": "dependency",
    "suite": "test_suite",
    "agent-plugin": "agent_plugin",
    "entry-point": "entry_point",
}
_DB_KIND_TO_CLI = {db: cli for cli, db in _INFER_DB_KIND.items()}


def _resolve_kind(args: object) -> "str | int":
    """Infer the describe kind from ``args.selector``.

    Returns a CLI kind string, or an int exit code on DB/ambiguity error
    (the error message is already printed to stderr).
    """
    selector = args.selector
    if selector is None:
        return "repo"
    if selector.startswith("builtin:"):
        return "builtin"
    db = graph_dir(args.workspace) / "code.db"
    try:
        conn = store.read_only_connect(db)
    except store.GraphNotInitializedError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exit_codes.NOT_INITIALIZED
    except store.SchemaMismatchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exit_codes.SCHEMA_MISMATCH
    try:
        rows = conn.execute(
            "SELECT DISTINCT kind FROM nodes WHERE name = ? AND kind IN "
            "('package','app','domain','dependency','test_suite','agent_plugin','entry_point')",
            (selector,),
        ).fetchall()
    finally:
        conn.close()
    cli_kinds = sorted({_DB_KIND_TO_CLI[r[0]] for r in rows})
    if not cli_kinds:
        # Not a known entity name — fall back to a path lookup; describe_path
        # reports "path not found in graph" if it is not one.
        return "path"
    if len(cli_kinds) > 1:
        print(
            f"error: ambiguous selector {selector!r} matches kinds: "
            f"{', '.join(cli_kinds)}; disambiguate with --kind",
            file=sys.stderr,
        )
        return exit_codes.AMBIGUOUS
    return cli_kinds[0]


def run(args: object) -> int:
    kind = args.kind
    if kind is None:
        kind = _resolve_kind(args)
        if isinstance(kind, int):
            return kind
    module, selector_attr = _DISPATCH[kind]
    if selector_attr is not None:
        setattr(args, selector_attr, args.selector)
    return module.run(args)
```

- [ ] **Step 4: Wire the `describe` command and remove the old `describe-*` commands**

In `packages/graph-wiki-cli/src/graph_wiki_cli/graph_cli/main.py`:

(a) In the import block, **remove** these ten names — `q_describe_agent_plugin`, `q_describe_app`, `q_describe_builtin`, `q_describe_dependency`, `q_describe_domain`, `q_describe_entry_point`, `q_describe_package`, `q_describe_path`, `q_describe_repo`, `q_describe_suite` — and **add** `q_describe`. (They are now imported by the router instead.)

(b) **Delete** these ten command functions entirely: `describe_agent_plugin_cmd`, `describe_app_cmd`, `describe_builtin_cmd`, `describe_dependency_cmd`, `describe_package_cmd`, `describe_path_cmd`, `describe_repo_cmd`, `describe_suite_cmd`, `describe_domain_cmd`, `describe_entry_point_cmd`.

(c) Add this command:

```python
@graph_app.command(name="describe")
def describe_cmd(
    ctx: typer.Context,
    selector: Optional[str] = typer.Argument(None, help="Name / path / URI of the entity (omit only for --kind repo)."),
    kind: Optional[str] = typer.Option(
        None, "--kind", "-k",
        help=f"Entity kind: {', '.join(q_describe.DESCRIBE_KINDS)}. Inferred from the selector when omitted.",
    ),
    ecosystem: Optional[str] = typer.Option(None, "--ecosystem", help="Dependency ecosystem (use with --kind dependency)."),
) -> None:
    """Describe a graph entity. Kind is inferred from the selector when --kind is omitted."""
    if kind is not None and kind not in q_describe.DESCRIBE_KINDS:
        raise typer.BadParameter(f"kind must be one of: {', '.join(q_describe.DESCRIBE_KINDS)}")
    _run(q_describe, ctx, selector=selector, kind=kind, ecosystem=ecosystem)
```

- [ ] **Step 5: Run the dispatcher test to verify it passes**

Run: `uv run --package graph-wiki-cli pytest tests/graph_cli/test_cli_describe_list_dispatch.py -v`
Expected: PASS — all four tests.

- [ ] **Step 6: Migrate the remaining old-name `describe-*` invocations**

These three test files still invoke old describe names and will now fail (command removed). Migrate each invocation's verb to the new form:

`packages/graph-wiki-cli/tests/graph_cli/test_cli_smoke.py`:
- `_cg(["--fmt", "json", "describe-package", "demo"], ...)` → `_cg(["--fmt", "json", "describe", "demo", "--kind", "package"], ...)` (line ~76)
- `_cg(["--fmt", "json", "describe-path", "src/a.py"], ...)` → `_cg(["--fmt", "json", "describe", "src/a.py", "--kind", "path"], ...)` (line ~84)

`packages/graph-wiki-cli/tests/graph_cli/test_cli_exit_codes.py`:
- `_cg(["describe-package", "no-such-package"], ...)` → `_cg(["describe", "no-such-package", "--kind", "package"], ...)` (line ~67)
- In the parametrized list (~lines 115-116): `["describe-package", "anything"]` → `["describe", "anything", "--kind", "package"]`, and `["describe-path", "a.py"]` → `["describe", "a.py", "--kind", "path"]`.

`packages/graph-wiki-cli/tests/graph_cli/test_cli_anti_regression.py` (the `args_by_cmd` dict, ~lines 123-124):
- `"describe-package": ["describe-package", refs.package_name]` → `"describe-package": ["describe", refs.package_name, "--kind", "package"]`
- `"describe-path": ["describe-path", refs.file_path]` → `"describe-path": ["describe", refs.file_path, "--kind", "path"]`

Leave the parametrize `kind` labels (`"describe-package"`, `"describe-path"`) as dict keys — only the invoked argument lists change.

- [ ] **Step 7: Run the three migrated suites**

Run: `uv run --package graph-wiki-cli pytest tests/graph_cli/test_cli_smoke.py tests/graph_cli/test_cli_exit_codes.py tests/graph_cli/test_cli_anti_regression.py -v`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add packages/graph-wiki-cli/src/graph_wiki_cli/graph_cli/q_describe.py \
        packages/graph-wiki-cli/src/graph_wiki_cli/graph_cli/main.py \
        packages/graph-wiki-cli/tests/graph_cli/test_cli_describe_list_dispatch.py \
        packages/graph-wiki-cli/tests/graph_cli/test_cli_smoke.py \
        packages/graph-wiki-cli/tests/graph_cli/test_cli_exit_codes.py \
        packages/graph-wiki-cli/tests/graph_cli/test_cli_anti_regression.py
git commit -m "feat(gw): consolidate describe-* into 'gw graph describe --kind'"
```

---

### Task 3: Smart-fallback kind inference for `describe`

**Files:**
- Modify: `packages/graph-wiki-cli/src/graph_wiki_cli/graph_cli/q_describe.py` (already has `_resolve_kind` from Task 2 — this task only adds the *tests* that exercise it; if the Task 2 implementation matches, no source change is needed)
- Test: `packages/graph-wiki-cli/tests/graph_cli/test_cli_describe_list_dispatch.py`

`_resolve_kind` was already written in Task 2. This task pins its behavior with tests for every inference branch. Add a richer fixture that contains a builtin and a domain so inference has something to resolve.

- [ ] **Step 1: Write the failing tests**

Append to `packages/graph-wiki-cli/tests/graph_cli/test_cli_describe_list_dispatch.py`:

```python
def test_describe_infers_package_from_bare_name(repo: Path) -> None:
    """No --kind: a bare name matching exactly one package resolves to it."""
    res = _cg(["describe", "demo"], repo)
    assert res.returncode == 0, res.stderr
    assert "demo" in res.stdout


def test_describe_infers_repo_when_no_selector(repo: Path) -> None:
    """No --kind and no selector resolves to the repository node."""
    res = _cg(["describe"], repo)
    assert res.returncode == 0, res.stderr


def test_describe_infers_builtin_from_uri_prefix(repo: Path) -> None:
    """A selector starting with 'builtin:' routes to the builtin describer."""
    # Not asserting success (no such builtin in this tiny repo) — asserting it
    # did NOT mis-route to a name/path lookup. The builtin describer emits
    # 'not a builtin URI' only for non-builtin: strings, so its absence proves
    # the builtin path was taken.
    res = _cg(["describe", "builtin:python/os"], repo)
    assert "not a builtin URI" not in res.stderr


def test_describe_falls_back_to_path_for_unknown_name(repo: Path) -> None:
    """A selector matching no entity name falls through to a path lookup."""
    res = _cg(["describe", "src/demo/__init__.py"], repo)
    assert res.returncode == 0, res.stderr


def test_describe_ambiguous_selector_errors(tmp_path: Path) -> None:
    """A name matching two kinds (package + domain) reports AMBIGUOUS (exit 7)."""
    init_repo(tmp_path)
    # A package literally named 'shared' plus a domain 'shared' in domains.yaml.
    write_and_commit(
        tmp_path,
        {
            "pyproject.toml": '[project]\nname = "shared"\nversion = "0.1.0"\n',
            "src/shared/__init__.py": "x = 1\n",
            "graph-wiki/.graph-wiki/domains.yaml": "domains:\n  - name: shared\n    includes: ['shared']\n",
        },
        "init",
    )
    assert _cg(["update", "--full"], tmp_path).returncode == 0
    res = _cg(["describe", "shared"], tmp_path)
    assert res.returncode == 7
    assert "ambiguous" in res.stderr.lower()
    assert "--kind" in res.stderr
```

- [ ] **Step 2: Run the inference tests**

Run: `uv run --package graph-wiki-cli pytest tests/graph_cli/test_cli_describe_list_dispatch.py -v -k infer or ambiguous or fall or repo`
Expected: the four inference branches PASS off the Task-2 implementation. If `test_describe_ambiguous_selector_errors` does not produce two kinds (the domains.yaml location/format differs in this repo), see Step 3.

- [ ] **Step 3: Fix the ambiguity fixture if needed**

If the ambiguity test fails because the domain was not created, confirm where domains are configured in this repo by reading an existing domain test:

Run: `uv run --package graph-wiki-cli pytest tests/graph_cli/ -v -k domain --collect-only` and inspect `tests/graph_cli/fixtures/` for a `domains.yaml` example, then adjust the fixture's `domains.yaml` path/format to match. Re-run Step 2 until green. Do **not** weaken the assertion — the goal is a genuine two-kind collision returning exit 7.

- [ ] **Step 4: Run the full dispatch test file**

Run: `uv run --package graph-wiki-cli pytest tests/graph_cli/test_cli_describe_list_dispatch.py -v`
Expected: PASS — all tests (explicit-kind from Task 2 + inference from Task 3).

- [ ] **Step 5: Commit**

```bash
git add packages/graph-wiki-cli/tests/graph_cli/test_cli_describe_list_dispatch.py \
        packages/graph-wiki-cli/src/graph_wiki_cli/graph_cli/q_describe.py
git commit -m "test(gw): pin describe kind-inference (repo/builtin/name/path/ambiguous)"
```

---

### Task 4: Registry assertions + docs + full-suite verification

**Files:**
- Modify: `packages/graph-wiki-cli/tests/graph_cli/test_cli_main.py`
- Modify: `docs/gw-cli.md`

- [ ] **Step 1: Write the failing registry assertions**

In `packages/graph-wiki-cli/tests/graph_cli/test_cli_main.py`, add to the existing `test_graph_app_is_native_typer_surface` (or as a new test using the existing `_command_names()` helper):

```python
def test_describe_list_consolidation_registry() -> None:
    commands = _command_names()
    # New consolidated commands exist.
    assert "describe" in commands
    assert "list" in commands
    # Old per-kind commands are gone.
    for gone in (
        "describe-package", "describe-app", "describe-builtin", "describe-dependency",
        "describe-path", "describe-repo", "describe-suite", "describe-domain",
        "describe-entry-point", "describe-agent-plugin",
        "list-apps", "list-builtins", "list-packages", "list-scripts",
        "list-suites", "list-domains",
    ):
        assert gone not in commands, f"{gone} should have been removed"
    # Deliberate carve-out: entry-point listing stays its own command.
    assert "list-entry-points" in commands
```

- [ ] **Step 2: Run it to verify it passes**

Run: `uv run --package graph-wiki-cli pytest tests/graph_cli/test_cli_main.py -v`
Expected: PASS (the commands were already swapped in Tasks 1-2; this just pins it).

- [ ] **Step 3: Update the docs**

In `docs/gw-cli.md`, replace the `describe-*` / `list-*` documentation with the consolidated surface. Use this block (adapt headings to the file's existing style):

```markdown
### Describe an entity

`gw graph describe <selector> [--kind KIND] [--ecosystem ECO]`

`--kind` is one of: `package`, `app`, `domain`, `suite`, `dependency`,
`agent-plugin`, `entry-point`, `builtin`, `path`, `repo`. When omitted, the
kind is inferred from the selector:

- no selector → `repo`
- selector starting with `builtin:` → `builtin`
- a name matching exactly one entity → that kind
- a name matching more than one kind → error (exit 7); pass `--kind`
- otherwise → treated as a `path`

Use `--ecosystem` with `--kind dependency`.

### List entities

`gw graph list --kind KIND`

`--kind` is one of: `apps`, `builtins`, `packages`, `scripts`, `suites`,
`domains`.

Entry points are listed with the separate `gw graph list-entry-points <package> [--kind executable|library]` command (scoped to one package).
```

- [ ] **Step 4: Full package test suite**

Run: `uv run --package graph-wiki-cli pytest -m "not integration"`
Expected: PASS — entire `graph-wiki-cli` suite green.

- [ ] **Step 5: Manual CLI sanity check**

Run: `uv run --package graph-wiki-cli gw graph --help`
Expected: the command list shows `describe` and `list` (and `list-entry-points`), and no `describe-*` / `list-{apps,builtins,packages,scripts,suites,domains}` entries. The `graph` group is now ~17 commands.

- [ ] **Step 6: Lint + format**

Run: `uv run ruff check packages/graph-wiki-cli && uv run ruff format packages/graph-wiki-cli`
Expected: clean (ruff may reformat — re-stage if so).

- [ ] **Step 7: Commit**

```bash
git add packages/graph-wiki-cli/tests/graph_cli/test_cli_main.py docs/gw-cli.md
git commit -m "docs(gw): document consolidated describe/list surface; pin registry"
```

---

## Self-Review notes (verified against the spec)

- **Coverage:** all 10 `describe-*` kinds and 6 `list-*` kinds are mapped (kind-vocabulary table); `list-entry-points` carve-out is explicit and asserted. Inference covers every branch chosen in design (repo / builtin / single-match / ambiguous / path-fallback) and each has a test (Task 3).
- **No placeholders:** every code step shows complete code; every run step states the command + expected result. The one conditional step (Task 3 Step 3) is a contingency with concrete diagnostic commands, not a deferral.
- **Type/name consistency:** `DESCRIBE_KINDS` / `LIST_KINDS` exported names, `_DISPATCH` tables, the `selector`/`kind`/`ecosystem` args, and the `_resolve_kind` return contract (kind string | int exit code) are used identically across the router source, the `main.py` commands, and the tests.
- **Behavior preserved:** the per-kind `q_describe_*` / `q_list_*` modules are untouched, so `--fmt json`, exit codes, and not-found messages are unchanged; `test_cli_describe.py` and `test_cli_describe_entry_point.py` (direct module-level tests) keep passing without edits.
- **Known double-open:** `describe` inference opens the DB read-only once to resolve the kind, then the delegated module opens it again. This is intentional and cheap (read-only); it keeps all store-error handling in one place and the per-kind modules unchanged.
```
