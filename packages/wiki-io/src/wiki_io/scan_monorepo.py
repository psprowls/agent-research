#!/usr/bin/env python3
"""
scan_monorepo.py — heuristic package discovery + file-map building helpers.

This module is a library of pure functions; it has no CLI and does no
container/layout/diff bookkeeping. Its callers (the scan command and the lint
code-drift check) import individual helpers directly.

Package discovery — ``_discover_heuristic(repo)`` walks the repo and returns a
sorted list of package dicts, one per manifest it finds (in priority order):
  - package.json + pnpm-workspace.yaml / workspaces field  (Node/pnpm/yarn/npm)
  - pyproject.toml                                          (Python — poetry/hatch/uv)
  - Cargo.toml with [workspace]                             (Rust)
  - .claude-plugin/plugin.json                              (Claude Code plugins)
Vendored trees (``node_modules``, ``.venv``) and test-fixture manifests
(``tests``/``fixtures``/``samples`` segments) are skipped. Each dict is built by
the matching ``_collect_*`` collector and carries at least ``name``, ``path``
(relative to repo), ``type``, ``language``, ``depends_on`` (internal workspace
deps), and ``exports``; ``_discover_heuristic`` also fills ``depended_on_by``.

File maps — ``build_file_map`` (prod-only), ``build_file_maps`` (prod + test
pair), and ``build_dir_file_map`` (whole-dir, no prod/test split) emit the
``## File map`` markdown block for a package or directory. The prod/test split
rule lives in ``_is_test_path``.

Other helpers: ``unscope`` (normalize ``@scope/foo`` -> ``foo``),
``compute_state_gate`` (whether state writes are allowed for a repo), and
``_git_ls_files`` (tracked + non-ignored files under a path).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

from wiki_io.entity_writer import _DIR_SECTION_PLACEHOLDER, _OVERVIEW_PLACEHOLDER


def unscope(name: str) -> str:
    """Strip an npm-style scope prefix (``@scope/foo`` -> ``foo``).

    Wiki stub pages use the unscoped slug as filename and title, while
    workspace manifests (``package.json#name``) carry the scope. Diffing
    and cross-lookups must normalize both sides through this helper.
    """
    if isinstance(name, str) and name.startswith("@") and "/" in name:
        return name.split("/", 1)[1]
    return name


def _safe_read_text(path):
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _load_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _parse_pyproject(text):
    """Minimal stdlib TOML parsing — just looks for [project] name."""
    name = None
    in_project = False
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            in_project = s == "[project]" or s == "[tool.poetry]"
            continue
        if in_project and s.startswith("name"):
            m = re.search(r'name\s*=\s*["\']([^"\']+)["\']', s)
            if m:
                name = m.group(1)
                break
    return name


# Split a PEP 508 requirement specifier on the first character that begins the
# version/marker/extras portion, so ``foo>=1.2`` → ``foo`` and ``foo[bar]>=1``
# → ``foo``. Falls back to the trimmed input if no boundary char is found.
_PEP508_BOUNDARY = re.compile(r"[\s\[<>=!~;@]")


def _pep508_name(requirement: str) -> str:
    s = requirement.strip()
    m = _PEP508_BOUNDARY.search(s)
    return (s[: m.start()] if m else s).strip()


def _parse_pyproject_deps(text: str) -> tuple[list[str], dict[str, str]]:
    """Parse ``[project].dependencies`` and ``[tool.uv.sources]`` from a
    pyproject.toml.

    Returns ``(workspace_dep_names, external_deps)`` where:
      - ``workspace_dep_names`` lists deps marked ``{ workspace = true }`` in
        ``[tool.uv.sources]`` (these are workspace-internal, not external).
      - ``external_deps`` maps the requirement name to its version specifier
        (e.g. ``{"boto3": ">=1.38"}``); the empty string is used when no
        specifier is declared.

    Falls back to ``([], {})`` on any parse failure so a single malformed
    pyproject doesn't break the whole scan.
    """
    try:
        import tomllib  # Python 3.11+ stdlib
    except ImportError:  # pragma: no cover — 3.10 fallback, not a target
        return [], {}
    try:
        data = tomllib.loads(text)
    except Exception:  # noqa: BLE001 — malformed pyproject, skip silently
        return [], {}

    sources = data.get("tool", {}).get("uv", {}).get("sources") or {}
    workspace_names = {name for name, src in sources.items() if isinstance(src, dict) and src.get("workspace") is True}

    raw_deps = data.get("project", {}).get("dependencies") or []
    workspace_deps: list[str] = []
    external: dict[str, str] = {}
    for req in raw_deps:
        if not isinstance(req, str):
            continue
        name = _pep508_name(req)
        if not name:
            continue
        if name in workspace_names:
            workspace_deps.append(name)
            continue
        spec = req.strip()[len(name) :].strip()
        external[name] = spec
    return sorted(workspace_deps), external


def _parse_cargo_toml(text):
    """Detect [workspace] with `members = [...]` and [package] with name."""
    members = []
    pkg_name = None
    section = None
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            section = s
            continue
        if section == "[workspace]" and s.startswith("members"):
            m = re.search(r"members\s*=\s*\[(.*?)\]", s, re.DOTALL)
            if m:
                members = [x.strip().strip('"').strip("'") for x in m.group(1).split(",") if x.strip()]
        if section == "[package]" and s.startswith("name"):
            m = re.search(r'name\s*=\s*["\']([^"\']+)["\']', s)
            if m:
                pkg_name = m.group(1)
    return pkg_name, members


def _discover_pnpm_workspace(repo):
    """Read pnpm-workspace.yaml glob patterns."""
    yml = repo / "pnpm-workspace.yaml"
    if not yml.exists():
        return None
    text = _safe_read_text(yml)
    globs = []
    in_packages = False
    for line in text.splitlines():
        s = line.rstrip()
        if s.startswith("packages:"):
            in_packages = True
            continue
        if in_packages:
            m = re.match(r"\s*-\s*[\"']?([^\"']+?)[\"']?\s*$", s)
            if m:
                globs.append(m.group(1))
            elif s and not s.startswith(" ") and not s.startswith("#") and not s.startswith("-"):
                break
    return globs or None


def _expand_globs(repo, globs):
    """Turn glob patterns like 'packages/*' or 'domains/**' into dirs.

    Handles two pnpm-workspace idioms that crash a naive ``repo.glob(g)``:
      - ``.``/``./``/``''`` means "the repo root is itself a package" — pathlib's
        ``glob('.')`` raises IndexError, so map it to the repo root directly.
      - any glob is expanded defensively (per-pattern try/except) so one bad
        pattern can't abort discovery of the rest.
    """
    dirs = set()
    for g in globs:
        if g.strip().strip("/") in ("", "."):
            if (repo / "package.json").exists():
                dirs.add(repo.resolve())
            continue
        try:
            matches = list(repo.glob(g))
        except (IndexError, ValueError):
            continue
        for p in matches:
            if p.is_dir() and (p / "package.json").exists():
                dirs.add(p.resolve())
    return sorted(dirs)


def _rel_to_repo(pkg_path: Path, repo: Path) -> str:
    """Package path relative to ``repo``, forward-slash normalized.

    pnpm legitimately allows out-of-tree workspace members (``../sibling``);
    ``Path.relative_to`` raises ValueError for those, so fall back to
    ``os.path.relpath`` (yielding a ``../``-prefixed path) instead of crashing
    discovery. Shared by every ``_collect_*`` collector.
    """
    try:
        return str(pkg_path.relative_to(repo)).replace("\\", "/")
    except ValueError:
        return os.path.relpath(pkg_path, repo).replace("\\", "/")


def _infer_package_type(pkg_path, pkg_json):
    """Heuristic: app vs library vs service."""
    rel = str(pkg_path.name).lower()
    if "app" in rel or "web" in rel or "expo" in rel:
        return "app"
    if pkg_json and pkg_json.get("scripts", {}).get("start"):
        return "service"
    if pkg_json and pkg_json.get("bin"):
        return "tool"
    return "library"


def _infer_language(pkg_path):
    if (pkg_path / "tsconfig.json").exists():
        return "typescript"
    if (pkg_path / "pyproject.toml").exists() or any(pkg_path.rglob("*.py")):
        return "python"
    if (pkg_path / "Cargo.toml").exists():
        return "rust"
    if (pkg_path / "go.mod").exists():
        return "go"
    if (pkg_path / "package.json").exists():
        return "javascript"
    return "unknown"


def _collect_node_package(repo, pkg_path):
    pj = _load_json(pkg_path / "package.json")
    if not pj:
        return None
    name = pj.get("name")
    if not name:
        return None
    deps = {}
    for key in ("dependencies", "devDependencies", "peerDependencies"):
        deps.update(pj.get(key, {}) or {})
    workspace_deps = [d for d, v in deps.items() if str(v).startswith("workspace:")]
    external_deps = {d: str(v) for d, v in deps.items() if not str(v).startswith("workspace:")}
    exports_field = pj.get("exports")
    exports = []
    if isinstance(exports_field, dict):
        exports = sorted(exports_field.keys())
    elif isinstance(exports_field, str):
        exports = [exports_field]
    return {
        "name": name,
        "path": _rel_to_repo(pkg_path, repo),
        "type": _infer_package_type(pkg_path, pj),
        "language": _infer_language(pkg_path),
        "version": pj.get("version"),
        "depends_on": sorted(workspace_deps),
        "external_deps": external_deps,
        "ecosystem": "npm",
        "exports": exports,
        "scripts": sorted(list((pj.get("scripts") or {}).keys())),
    }


def _collect_python_package(repo, pkg_path):
    pp = pkg_path / "pyproject.toml"
    if not pp.exists():
        return None
    text = _safe_read_text(pp)
    name = _parse_pyproject(text)
    if not name:
        return None
    workspace_deps, external_deps = _parse_pyproject_deps(text)
    return {
        "name": name,
        "path": _rel_to_repo(pkg_path, repo),
        "type": "library",
        "language": "python",
        "version": None,
        "depends_on": workspace_deps,
        "external_deps": external_deps,
        "ecosystem": "pypi",
        "exports": [],
        "scripts": [],
    }


def _collect_claude_plugin(repo, pkg_path):
    """Detect a Claude Code plugin by its .claude-plugin/plugin.json manifest.

    The manifest declares ``name`` (required), ``version``, ``description``, and
    ``keywords``. The package "path" is the directory containing
    ``.claude-plugin/`` (not the .claude-plugin/ dir itself).
    """
    manifest = pkg_path / ".claude-plugin" / "plugin.json"
    if not manifest.exists():
        return None
    pj = _load_json(manifest)
    if not pj:
        return None
    name = pj.get("name")
    if not name:
        return None
    keywords = pj.get("keywords") or []
    return {
        "name": name,
        "path": _rel_to_repo(pkg_path, repo),
        "type": "tool",
        "language": "claude-code-plugin",
        "version": pj.get("version"),
        "depends_on": [],
        "external_deps": {},
        "ecosystem": "claude-code-plugin",
        "exports": sorted(keywords) if isinstance(keywords, list) else [],
        "scripts": [],
    }


def _collect_rust_crate(repo, pkg_path):
    cargo = pkg_path / "Cargo.toml"
    if not cargo.exists():
        return None
    name, _ = _parse_cargo_toml(_safe_read_text(cargo))
    if not name:
        return None
    return {
        "name": name,
        "path": _rel_to_repo(pkg_path, repo),
        "type": "library",
        "language": "rust",
        "version": None,
        "depends_on": [],
        "exports": [],
        "scripts": [],
    }


def _git_ls_files(pkg_path: Path) -> list[str] | None:
    """Return tracked + non-ignored untracked files relative to pkg_path.

    Returns None when pkg_path is not under git or git is unavailable —
    callers leave the file map as a placeholder for the agent to fill in.
    """
    try:
        # git ls-files exits 0 even outside a repo on some versions; check explicitly.
        check = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=str(pkg_path),
            capture_output=True,
            timeout=10,
        )
        if check.returncode != 0:
            return None
        result = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=str(pkg_path),
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return sorted(
        rel for line in result.stdout.splitlines() if (rel := line.strip()) and not _is_compiled_artifact(rel)
    )


def _is_compiled_artifact(rel: str) -> bool:
    """True for Python bytecode artifacts that should never appear in a file map.

    ``__pycache__`` dirs and ``.pyc``/``.pyo`` files are virtually always
    gitignored in real repos, so ``git ls-files`` won't surface them — but a
    tree that tracks them anyway (e.g. a test fixture built with ``git add .``
    over stray compiled files) would otherwise leak version-stamped bytecode
    names into the deterministic file map. Filtering here keeps the map source-
    only for every ``_git_ls_files`` consumer.
    """
    parts = rel.split("/")
    if "__pycache__" in parts:
        return True
    return parts[-1].endswith((".pyc", ".pyo"))


# ---------------------------------------------------------------------------
# Test-path classification
# ---------------------------------------------------------------------------

_TEST_DIR_NAMES = frozenset({"tests", "__tests__", "test", "spec"})
_TEST_CONFIG_NAMES = frozenset(
    {
        "conftest.py",
        "pytest.ini",
        "tox.ini",
        "pyproject-tests.toml",
        "karma.conf.js",
        "karma.conf.ts",
    }
)
# Matches names like jest.config.{js,ts,mjs,cjs,json}, vitest.config.{js,ts,mjs},
# playwright.config.{js,ts}, cypress.config.{js,ts}, mocha.config.js,
# .mocharc.{js,json,yaml,yml}, ava.config.{js,cjs,mjs}
_TEST_CONFIG_RE = re.compile(
    r"^("
    r"jest\.config\.(?:js|ts|mjs|cjs|json)"
    r"|vitest\.config\.(?:js|ts|mjs)"
    r"|playwright\.config\.(?:js|ts)"
    r"|cypress\.config\.(?:js|ts)"
    r"|mocha\.config\.js"
    r"|\.mocharc\.(?:js|json|yaml|yml)"
    r"|ava\.config\.(?:js|cjs|mjs)"
    r")$"
)


def _is_test_path(rel: str) -> bool:
    """Classify a package-relative path as test (True) or prod (False).

    Rule:
      1. Any path component (split on '/') matching _TEST_DIR_NAMES -> True.
      2. Basename in _TEST_CONFIG_NAMES OR matching _TEST_CONFIG_RE -> True
         (applies at any depth; conftest.py is a common pytest pattern at
         non-root paths too).
      3. Otherwise -> False.

    Precondition: ``rel`` is a forward-slash-separated path relative to the
    package root (the same shape build_file_map already receives from
    _git_ls_files).
    """
    parts = rel.split("/")
    if any(p in _TEST_DIR_NAMES for p in parts):
        return True
    basename = parts[-1]
    if basename in _TEST_CONFIG_NAMES or _TEST_CONFIG_RE.match(basename):
        return True
    return False


# ---------------------------------------------------------------------------
# File map emitter
# ---------------------------------------------------------------------------


def _emit_file_map_block(
    pkg_name: str,
    files: list[str],
    truncated: bool,
    max_depth: int,
    max_entries: int = 200,
) -> str:
    """Emit a ``## File map - <pkg_name>`` block from the given file list.

    Shared implementation used by build_file_map(), build_file_maps(), and build_dir_file_map().
    ``files`` must already be truncated to max_entries before calling.
    ``truncated`` controls whether the truncation marker is appended.
    ``max_entries`` is used only in the truncation marker text.
    """
    title_line = f"## File map - {pkg_name}"

    TABLE_HEADER = "| Path | Kind | Description |"
    TABLE_SEP = "|---|---|---|"

    # Build a two-level grouping:
    #   root_files: files at depth 0 (no "/" in path)
    #   sub_trees: dict[depth1_dir -> list of relative paths within that dir]
    root_files: list[str] = []
    sub_trees: dict[str, list[str]] = {}

    for rel in files:
        parts = rel.split("/")
        if len(parts) == 1:
            root_files.append(parts[0])
        else:
            top = parts[0]
            rest = "/".join(parts[1:])
            sub_trees.setdefault(top, []).append(rest)

    out: list[str] = [title_line, _OVERVIEW_PLACEHOLDER, ""]

    # Synthetic root section: ### <pkg>/
    root_dir_rows: list[str] = []
    for top in sorted(sub_trees.keys(), key=str.lower):
        if max_depth < 1:
            root_dir_rows.append(top)

    # Emit root section
    root_block: list[str] = [f"### {pkg_name}/", _DIR_SECTION_PLACEHOLDER, "", TABLE_HEADER, TABLE_SEP]
    for name in sorted(root_files, key=str.lower):
        root_block.append(f"| `{name}` | file | — TODO |")
    for name in root_dir_rows:
        root_block.append(f"| `{name}/` | dir | — TODO |")
    root_block.append("")
    out.extend(root_block)

    # One H3 per depth-1 directory (sorted alphabetically, case-insensitive).
    for top in sorted(sub_trees.keys(), key=str.lower):
        if max_depth < 1:
            continue

        rel_paths = sorted(sub_trees[top], key=str.lower)
        file_rows: list[str] = []
        dir_rows: list[str] = []

        sub_dir_files: dict[str, list[str]] = {}
        direct_files: list[str] = []

        for rel in rel_paths:
            parts = rel.split("/")
            if len(parts) == 1:
                direct_files.append(parts[0])
            else:
                sub = parts[0]
                rest = "/".join(parts[1:])
                sub_dir_files.setdefault(sub, []).append(rest)

        for f in sorted(direct_files, key=str.lower):
            file_rows.append(f)

        for sub in sorted(sub_dir_files.keys(), key=str.lower):
            if max_depth < 2:
                dir_rows.append(f"{sub}/")
            else:
                for sub_rel in sorted(sub_dir_files[sub], key=str.lower):
                    file_rows.append(f"{sub}/{sub_rel}")

        block: list[str] = [f"### {pkg_name}/{top}/", _DIR_SECTION_PLACEHOLDER, "", TABLE_HEADER, TABLE_SEP]
        for name in file_rows:
            block.append(f"| `{name}` | file | — TODO |")
        for name in dir_rows:
            block.append(f"| `{name}` | dir | — TODO |")
        block.append("")
        out.extend(block)

    if truncated:
        out.append(f"> Truncated at {max_entries} files.")
        out.append("")

    return "\n".join(out).rstrip() + "\n"


def build_file_maps(
    pkg_path: Path,
    max_depth: int = 4,
    max_entries: int = 200,
) -> tuple[str, str] | None:
    """Return ``(prod_block, test_block)`` where each is a full markdown
    ``## File map - <name>`` block in the table format.

    - prod_block: H2 + per-major-folder H3 sections covering ONLY prod files +
      prod root-level config. Test directories (tests/, __tests__/, test/,
      spec/) and test-config files are excluded.
    - test_block: H2 + per-major-folder H3 sections covering ONLY test files,
      test config, and fixtures.

    Returns None when ``_git_ls_files(pkg_path)`` returns None.

    When there are no test files in the package, ``test_block`` is a minimal
    placeholder (no table).

    When there are no prod files (tests-only meta-package), ``prod_block`` uses
    the existing empty-package short circuit (``- (no tracked files)``).

    The split rule lives in ``_is_test_path()`` and is the single source of
    truth. The caller (``main()``) stores the result as ``w["file_map"]``
    (prod) and ``w["file_map_testing"]`` (test) on each workspace dict.
    """
    files = _git_ls_files(pkg_path)
    if files is None:
        return None

    pkg_name = pkg_path.name
    title_line = f"## File map - {pkg_name}"

    # Truncation applies to the combined list before splitting (backward compat).
    truncated = len(files) > max_entries
    if truncated:
        files = files[:max_entries]

    # Partition into prod and test lists.
    prod_files = [f for f in files if not _is_test_path(f)]
    test_files = [f for f in files if _is_test_path(f)]

    # Build prod block.
    if not prod_files:
        prod_block = f"{title_line}\n{_OVERVIEW_PLACEHOLDER}\n\n- (no tracked files)\n"
        if truncated:
            prod_block = prod_block.rstrip("\n") + f"\n\n> Truncated at {max_entries} files.\n"
    else:
        prod_block = _emit_file_map_block(pkg_name, prod_files, truncated, max_depth, max_entries)

    # Build test block.
    if not test_files:
        test_block = (
            f"{title_line}\n{_OVERVIEW_PLACEHOLDER}\n\n"
            f"### {pkg_name}/\n"
            f"TODO — no test files detected. Document test strategy here when tests land.\n"
        )
        if truncated:
            test_block = test_block.rstrip("\n") + f"\n\n> Truncated at {max_entries} files.\n"
    else:
        test_block = _emit_file_map_block(pkg_name, test_files, truncated, max_depth, max_entries)

    return prod_block, test_block


def build_file_map(pkg_path: Path, max_depth: int = 4, max_entries: int = 200) -> str | None:
    """Return the prod-only ``## File map - <name>`` block. (Legacy single-
    return API; see ``build_file_maps()`` for the paired prod+test output.)

    NOTE: This API now returns prod-only output. Prior to quick-260523-i35 it
    returned a combined prod+test block. Callers relying on test-path rows in
    the output must migrate to ``build_file_maps()[1]``.
    """
    fms = build_file_maps(pkg_path, max_depth=max_depth, max_entries=max_entries)
    if fms is None:
        return None
    return fms[0]


def build_dir_file_map(path: Path, max_depth: int = 4, max_entries: int = 200) -> str | None:
    """Return an unpartitioned ``## File map - <root-basename>`` block covering
    ALL tracked files under ``path``.

    Unlike ``build_file_map`` (prod-only) / ``build_file_maps`` (prod+test
    split), this lists everything under the root with no prod/test partition.
    Used for test-suite entity pages: everything under a suite root is
    test-related, so partitioning would mis-route files (a root ``conftest.py``
    into the dropped test half, a plain ``helpers.py`` into prod).

    The heading label is the root directory basename (``path.name``) — stable
    unless the suite physically moves. This stability is load-bearing for
    cross-rescan description preservation: the snapshot/merge round-trip strips
    this label to reconstruct suite-root-relative path keys.

    Returns ``None`` when ``_git_ls_files(path)`` returns ``None`` (not git).
    Emits the ``- (no tracked files)`` short-circuit for an empty root. Honors
    ``max_entries`` truncation. Mirrors ``build_file_maps``' contracts.
    """
    files = _git_ls_files(path)
    if files is None:
        return None

    name = path.name
    truncated = len(files) > max_entries
    if truncated:
        files = files[:max_entries]

    if not files:
        title_line = f"## File map - {name}"
        block = f"{title_line}\n{_OVERVIEW_PLACEHOLDER}\n\n- (no tracked files)\n"
        if truncated:
            block = block.rstrip("\n") + f"\n\n> Truncated at {max_entries} files.\n"
        return block

    return _emit_file_map_block(name, files, truncated, max_depth, max_entries)


def _discover_heuristic(repo, workspace_dir=None):
    """Walk ``repo`` and return a sorted list of package dicts (one per manifest).

    ``workspace_dir`` is the graph-wiki workspace subtree to exclude when it is a
    proper subdirectory of ``repo`` (the "D-11 guard parity" filter — keeps the
    workspace's own vault/scaffold from being mistaken for a package). Current
    callers (lint code-drift) don't pass it; kept for that guard / forward compat.
    """
    workspaces = []
    seen_paths = set()

    # D-11 guard parity: only filter when workspace is a proper subdir of repo
    workspace_segments: set[str] = set()
    if workspace_dir is not None:
        wd = Path(workspace_dir).resolve()
        repo_r = Path(repo).resolve()
        if wd != repo_r and wd.parent == repo_r:
            workspace_segments = {wd.name}

    # Node / pnpm
    root_pj = _load_json(repo / "package.json")
    globs = _discover_pnpm_workspace(repo)
    if globs is None and root_pj and isinstance(root_pj.get("workspaces"), list):
        globs = root_pj["workspaces"]
    if globs is None and root_pj and isinstance(root_pj.get("workspaces"), dict):
        globs = root_pj["workspaces"].get("packages", [])
    if globs:
        for d in _expand_globs(repo, globs):
            if d in seen_paths:
                continue
            pkg = _collect_node_package(repo, d)
            if pkg:
                workspaces.append(pkg)
                seen_paths.add(d)

    # Rust [workspace]
    root_cargo = repo / "Cargo.toml"
    if root_cargo.exists():
        _, members = _parse_cargo_toml(_safe_read_text(root_cargo))
        for m in members:
            for d in repo.glob(m):
                if d.is_dir() and d.resolve() not in seen_paths:
                    pkg = _collect_rust_crate(repo, d.resolve())
                    if pkg:
                        workspaces.append(pkg)
                        seen_paths.add(d.resolve())

    # Python — walk up to depth 3 looking for pyproject.toml
    # Skip vendored/venv trees and test-fixture packages that happen to ship
    # their own manifest (e.g. samples/ under another workspace). Per
    # ADR-0013, a manifest under a tests/fixtures/samples segment is not a
    # workspace — it's an artifact of another workspace's test harness.
    fixture_segments = {"tests", "__tests__", "test", "__test__", "fixtures", "samples"}
    for pp in repo.rglob("pyproject.toml"):
        if "node_modules" in pp.parts or ".venv" in pp.parts:
            continue
        if any(part in fixture_segments for part in pp.parts):
            continue
        if workspace_segments and any(part in workspace_segments for part in pp.parts):
            continue
        d = pp.parent.resolve()
        if d in seen_paths:
            continue
        pkg = _collect_python_package(repo, d)
        if pkg:
            workspaces.append(pkg)
            seen_paths.add(d)

    # Claude Code plugins — rglob for .claude-plugin/plugin.json. Same
    # fixture/vendored filter as pyproject so test plugins aren't picked up.
    for manifest in repo.rglob(".claude-plugin/plugin.json"):
        if "node_modules" in manifest.parts or ".venv" in manifest.parts:
            continue
        if any(part in fixture_segments for part in manifest.parts):
            continue
        if workspace_segments and any(part in workspace_segments for part in manifest.parts):
            continue
        d = manifest.parent.parent.resolve()
        if d in seen_paths:
            continue
        pkg = _collect_claude_plugin(repo, d)
        if pkg:
            workspaces.append(pkg)
            seen_paths.add(d)

    # Reverse dependency count
    name_to_idx = {w["name"]: i for i, w in enumerate(workspaces)}
    for w in workspaces:
        w["depended_on_by"] = 0
    for w in workspaces:
        for dep in w["depends_on"]:
            if dep in name_to_idx:
                workspaces[name_to_idx[dep]]["depended_on_by"] += 1

    workspaces.sort(key=lambda w: w["name"])
    return workspaces


def compute_state_gate(repo: Path, workspace: Path | None = None) -> dict:
    """Return JSON-serializable gate info: whether state writes are allowed.

    {"allowed": bool, "reason": str, "head_commit": str | None}

    The agent reads this to decide whether to bump last_updated_commit on
    reviewed pages. When allowed=False, scan still runs in read-only mode — it
    reports drift but does not bump state.

    Gate config comes from `<workspace>/.graph-wiki.yaml`'s `state_gate` block.
    `workspace=None` preserves the historical default (enabled, branches=["main"]).
    """
    from wiki_io.git_state import head_commit, is_clean_on_branches

    if workspace is None:
        enabled, branches = True, ["main"]
    else:
        from workspace_io import manifest

        enabled, branches = manifest.read_state_gate(workspace / ".graph-wiki.yaml")

    if not enabled:
        return {
            "allowed": True,
            "reason": "state gate disabled in .graph-wiki.yaml",
            "head_commit": head_commit(repo),
        }

    ok, reason = is_clean_on_branches(repo, branches)
    return {
        "allowed": ok,
        "reason": reason,
        "head_commit": head_commit(repo),
    }
