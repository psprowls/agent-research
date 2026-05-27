#!/usr/bin/env python3
"""
scan_monorepo.py — Walk a repo and emit a structured inventory of its workspaces.

Container-aware: reads the wiki's CLAUDE.md for a graph-wiki:layout block to
scope the scan to pinned `app`/`package`/`domain` containers. Falls back to the
heuristic walk from repo root (Node/pnpm globs, pyproject.toml rglob, Cargo.toml workspaces).

Discovers repo and wiki locations from the resolved graph-wiki workspace.

Detects workspace packages from (in priority order):
  - package.json + pnpm-workspace.yaml / workspaces field  (Node/pnpm/yarn/npm)
  - pyproject.toml                                         (Python — poetry/hatch/uv)
  - Cargo.toml with [workspace]                            (Rust)
  - .claude-plugin/plugin.json                             (Claude Code plugins)
  # TODO: go.mod + go.work (Go) — not yet implemented

For each detected package, emits:
  - name, path (relative to repo), type (library/app/service), language
  - exports (from package.json `exports` / pyproject `[project.scripts]` / etc.)
  - depends_on (internal workspace dependencies)

Also computes a diff against existing pages in `wiki/apps/<name>/<name>.md`,
`wiki/packages/<name>/<name>.md`, and `wiki/domains/<d>/packages/<name>/<name>.md`:
  - new    — on disk, no vault page
  - deleted — has a vault page, no longer on disk
  - renamed — heuristic match (same path, new name or same name, new path)
  - unchanged

Usage:
    python scan_monorepo.py --json
    python scan_monorepo.py
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from wiki_io._workspace import resolve_wiki_and_repo
from wiki_io.layout_io import read_layout
from wiki_io.lint.workflow_hints import _parse_workflow_hints

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


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

    sources = (data.get("tool", {}).get("uv", {}).get("sources") or {})
    workspace_names = {
        name for name, src in sources.items()
        if isinstance(src, dict) and src.get("workspace") is True
    }

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
        spec = req.strip()[len(name):].strip()
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
    """Turn glob patterns like 'packages/*' or 'domains/**' into dirs."""
    dirs = set()
    for g in globs:
        for p in repo.glob(g):
            if p.is_dir() and (p / "package.json").exists():
                dirs.add(p.resolve())
    return sorted(dirs)


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
        "path": str(pkg_path.relative_to(repo)).replace("\\", "/"),
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
        "path": str(pkg_path.relative_to(repo)).replace("\\", "/"),
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
        "path": str(pkg_path.relative_to(repo)).replace("\\", "/"),
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
        "path": str(pkg_path.relative_to(repo)).replace("\\", "/"),
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
    return sorted(line.strip() for line in result.stdout.splitlines() if line.strip())


# ---------------------------------------------------------------------------
# Test-path classification
# ---------------------------------------------------------------------------

_TEST_DIR_NAMES = frozenset({"tests", "__tests__", "test", "spec"})
_TEST_CONFIG_NAMES = frozenset({
    "conftest.py", "pytest.ini", "tox.ini", "pyproject-tests.toml",
    "karma.conf.js", "karma.conf.ts",
})
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
    max_entries: int = 80,
) -> str:
    """Emit a ``## File map - <pkg_name>`` block from the given file list.

    Shared implementation used by both build_file_map() and build_file_maps().
    ``files`` must already be truncated to max_entries before calling.
    ``truncated`` controls whether the truncation marker is appended.
    ``max_entries`` is used only in the truncation marker text.
    """
    title_line = f"## File map - {pkg_name}"
    section_placeholder = "TODO — describe what this directory contains."
    overview_placeholder = "TODO — overview of this package's tree."

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

    out: list[str] = [title_line, overview_placeholder, ""]

    # Synthetic root section: ### <pkg>/
    root_dir_rows: list[str] = []
    for top in sorted(sub_trees.keys(), key=str.lower):
        if max_depth < 1:
            root_dir_rows.append(top)

    # Emit root section
    root_block: list[str] = [f"### {pkg_name}/", section_placeholder, "", TABLE_HEADER, TABLE_SEP]
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

        block: list[str] = [f"### {pkg_name}/{top}/", section_placeholder, "", TABLE_HEADER, TABLE_SEP]
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
    max_entries: int = 80,
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
    overview_placeholder = "TODO — overview of this package's tree."

    # Truncation applies to the combined list before splitting (backward compat).
    truncated = len(files) > max_entries
    if truncated:
        files = files[:max_entries]

    # Partition into prod and test lists.
    prod_files = [f for f in files if not _is_test_path(f)]
    test_files = [f for f in files if _is_test_path(f)]

    # Build prod block.
    if not prod_files:
        prod_block = f"{title_line}\n{overview_placeholder}\n\n- (no tracked files)\n"
        if truncated:
            prod_block = prod_block.rstrip("\n") + f"\n\n> Truncated at {max_entries} files.\n"
    else:
        prod_block = _emit_file_map_block(pkg_name, prod_files, truncated, max_depth, max_entries)

    # Build test block.
    if not test_files:
        test_block = (
            f"{title_line}\n{overview_placeholder}\n\n"
            f"### {pkg_name}/\n"
            f"TODO — no test files detected. Document test strategy here when tests land.\n"
        )
        if truncated:
            test_block = test_block.rstrip("\n") + f"\n\n> Truncated at {max_entries} files.\n"
    else:
        test_block = _emit_file_map_block(pkg_name, test_files, truncated, max_depth, max_entries)

    return prod_block, test_block


def build_file_map(pkg_path: Path, max_depth: int = 4, max_entries: int = 80) -> str | None:
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


def discover_workspaces(repo, pinned_containers=None, workspace_dir=None):
    """If pinned_containers is given, scan only those container subtrees.
    Otherwise fall back to the original heuristic walk.
    """
    repo = Path(repo).resolve()
    if pinned_containers is not None:
        workspaces = _discover_from_pinned(repo, pinned_containers)
    else:
        workspaces = _discover_heuristic(repo, workspace_dir=workspace_dir)
    for w in workspaces:
        vault_dir = w.pop("_container_vault_dir", None)
        w["wiki_relative_path"] = _wiki_relative_path_for(w, vault_dir=vault_dir)
    return workspaces


def _wiki_relative_path_for(pkg: dict, vault_dir: str | None = None) -> str:
    """Return the wiki-relative page path for a discovered workspace.

    Routing:
      - apps                                    -> ``apps/<name>/overview.md``
      - domain-scoped libraries/services/tools  -> ``domains/<d>/packages/<name>/overview.md``
      - everything else                         -> ``<vault_dir>/<name>/overview.md``
        (defaults to ``packages/`` when no pinned container vault_dir applies)

    The ``vault_dir`` argument is the matched container's pinned vault_dir
    from ``wiki/CLAUDE.md`` — honors per-repo layouts that map a non-default
    source directory (e.g. ``plugins/``) to a non-default vault directory.
    Falls back to ``packages`` for heuristic discovery and shared
    ``packages/lib``-type directories.
    """
    name = unscope(pkg["name"])
    if pkg.get("type") == "app":
        return f"apps/{name}/overview.md"
    domain = pkg.get("domain")
    if domain:
        return f"domains/{domain}/packages/{name}/overview.md"
    base = vault_dir or "packages"
    return f"{base}/{name}/overview.md"


def _discover_from_pinned(repo: Path, containers: list) -> list:
    workspaces = []
    seen_paths = set()
    for c in containers:
        cls = c.get("classification")
        if cls in (None, "skip", "docs", "ambiguous"):
            continue
        if c.get("source") == "" and cls == "single-package":
            pkg = (
                _collect_node_package(repo, repo)
                or _collect_python_package(repo, repo)
                or _collect_rust_crate(repo, repo)
                or _collect_claude_plugin(repo, repo)
            )
            if pkg and repo.resolve() not in seen_paths:
                pkg["_container_vault_dir"] = c.get("vault_dir")
                workspaces.append(pkg)
                seen_paths.add(repo.resolve())
            continue

        src = (repo / c["source"]).resolve()
        if not src.exists() or not src.is_dir():
            continue

        if cls in ("package", "app"):
            for child in sorted(p for p in src.iterdir() if p.is_dir() and not p.name.startswith(".")):
                if child.resolve() in seen_paths:
                    continue
                pkg = (
                    _collect_node_package(repo, child)
                    or _collect_python_package(repo, child)
                    or _collect_rust_crate(repo, child)
                    or _collect_claude_plugin(repo, child)
                )
                if pkg:
                    pkg["_container_vault_dir"] = c.get("vault_dir")
                    workspaces.append(pkg)
                    seen_paths.add(child.resolve())
        elif cls == "domain":
            # A domain dir may either hold packages directly
            # (``domains/<d>/<pkg>/``) or group them under a package container
            # (``domains/<d>/packages/<pkg>/``). Try the flat layout first;
            # only descend one level deeper for subdirs that don't carry a
            # manifest themselves.
            for domain_dir in sorted(p for p in src.iterdir() if p.is_dir() and not p.name.startswith(".")):
                for sub in sorted(p for p in domain_dir.iterdir() if p.is_dir() and not p.name.startswith(".")):
                    if sub.resolve() in seen_paths:
                        continue
                    pkg = (
                        _collect_node_package(repo, sub)
                        or _collect_python_package(repo, sub)
                        or _collect_rust_crate(repo, sub)
                        or _collect_claude_plugin(repo, sub)
                    )
                    if pkg:
                        pkg["domain"] = domain_dir.name
                        workspaces.append(pkg)
                        seen_paths.add(sub.resolve())
                        continue
                    # ``sub`` is a package container (``packages/``, ``libs/``,
                    # …); pick up packages one level deeper.
                    for grand in sorted(p for p in sub.iterdir() if p.is_dir() and not p.name.startswith(".")):
                        if grand.resolve() in seen_paths:
                            continue
                        pkg = (
                            _collect_node_package(repo, grand)
                            or _collect_python_package(repo, grand)
                            or _collect_rust_crate(repo, grand)
                            or _collect_claude_plugin(repo, grand)
                        )
                        if pkg:
                            pkg["domain"] = domain_dir.name
                            workspaces.append(pkg)
                            seen_paths.add(grand.resolve())

    # Reverse dependency count (mirroring _discover_heuristic's behavior)
    name_to_idx = {w["name"]: i for i, w in enumerate(workspaces)}
    for w in workspaces:
        w["depended_on_by"] = 0
    for w in workspaces:
        for dep in w.get("depends_on", []):
            if dep in name_to_idx:
                workspaces[name_to_idx[dep]]["depended_on_by"] += 1

    workspaces.sort(key=lambda w: w["name"])
    return workspaces


def _discover_heuristic(repo, workspace_dir=None):
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


def _parse_frontmatter(text):
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}
    fm = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.lstrip().startswith("#"):
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip().strip("'\"")
    return fm


@dataclass(frozen=True)
class ExistingPages:
    """Phase 45 D-11: dual view of vault pages — legacy (name-keyed) and entities (URI-keyed).

    legacy:   dict mapping workspace name → existing page metadata
              (wiki_relative_path, package_path, category, last_sync_commit).
              Shape unchanged from pre-Phase-45 — passes through to
              `attach_changed_files` and `compute_diff` directly.

    entities: dict mapping graph URI → {"path": Path, "frontmatter": dict}.
              Populated by walking `wiki/entities/*.md` and indexing by the
              page's `uri` frontmatter field. Pages missing a `uri` field are
              skipped silently. `_index.md` is skipped (Phase 43 convention).
    """

    legacy: dict[str, dict]
    entities: dict[str, dict]


def _load_existing_pages(wiki):
    """Return an `ExistingPages` dataclass.

    `legacy` is built by walking every place package/app pages may live:

      - wiki/apps/**/*.md                       (apps — default)
      - wiki/packages/**/*.md                   (cross-domain packages — default)
      - wiki/<container>/**/*.md                (any layout-pinned container
                                                    in wiki/CLAUDE.md whose
                                                    classification is package or app)
      - wiki/domains/<domain>/packages/**/*.md  (domain-scoped packages)

    The category is read from frontmatter when present so the diff can
    distinguish apps from libraries regardless of which directory they live in.

    `entities` is built by walking `wiki/entities/*.md` (excluding `_index.md`)
    and indexing by the page's `uri` frontmatter field (Phase 45 D-11).
    """
    if not wiki:
        return ExistingPages(legacy={}, entities={})
    legacy_pages: dict[str, dict] = {}
    vault = wiki
    walked: set[Path] = set()

    def _collect(root, default_category, fold_companions=False):
        resolved = root.resolve() if root.exists() else root
        if resolved in walked or not root.exists():
            return
        walked.add(resolved)

        # First pass: discover companion stems per directory from parent overviews.
        # A parent overview is the file named `overview.md`
        # (e.g. packages/wiki-io/overview.md). Its workflow_hints frontmatter
        # declares which sibling stems are companions and should be folded.
        companions_by_dir: dict[Path, set[str]] = {}
        if fold_companions:
            for md in root.rglob("*.md"):
                if md.name != "overview.md":
                    continue  # not a parent overview
                text = _safe_read_text(md)
                hints = _parse_workflow_hints(text)
                companion_stems = {Path(p).stem for sub in hints.values() for p in sub}
                if companion_stems:
                    companions_by_dir[md.parent] = companion_stems

        # Second pass: walk and emit pages, skipping declared companion files.
        for md in root.rglob("*.md"):
            if fold_companions and md.stem in companions_by_dir.get(md.parent, set()):
                continue  # fold this companion into its parent overview
            fm = _parse_frontmatter(_safe_read_text(md))
            name = fm.get("title") or md.stem
            category = fm.get("category", default_category)
            path_key = fm.get("app_path") if category == "app" else fm.get("package_path")
            legacy_pages[name] = {
                "wiki_relative_path": str(md.relative_to(wiki)).replace("\\", "/"),
                "package_path": path_key,
                "category": category,
                "last_sync_commit": fm.get("last_sync_commit") or None,
            }

    _collect(vault / "apps", "app")
    _collect(vault / "packages", "package", fold_companions=True)

    for schema_name in ("CLAUDE.md", "AGENTS.md"):
        layout = read_layout(wiki / schema_name)
        if not layout:
            continue
        for c in layout.get("containers", []):
            classification = c.get("classification")
            if classification not in ("package", "app"):
                continue
            vault_dir = c.get("vault_dir")
            if not vault_dir:
                continue
            _collect(vault / vault_dir, classification, fold_companions=(classification == "package"))
        break

    domains_dir = vault / "domains"
    if domains_dir.exists():
        # First pass: build companion-stem sets from parent overviews in domains.
        # Only applies to directories whose overview declares category == 'package'.
        domain_companions_by_dir: dict[Path, set[str]] = {}
        for md in domains_dir.rglob("*.md"):
            if md.name != "overview.md":
                continue  # not a parent overview
            text = _safe_read_text(md)
            fm_overview = _parse_frontmatter(text)
            if fm_overview.get("category") != "package":
                continue
            hints = _parse_workflow_hints(text)
            companion_stems = {Path(p).stem for sub in hints.values() for p in sub}
            if companion_stems:
                domain_companions_by_dir[md.parent] = companion_stems

        # Second pass: emit pages, folding companion stems for package directories.
        for md in domains_dir.rglob("*.md"):
            if md.stem in domain_companions_by_dir.get(md.parent, set()):
                continue  # fold companion into parent overview
            fm = _parse_frontmatter(_safe_read_text(md))
            category = fm.get("category")
            if category not in ("package", "app"):
                continue
            name = fm.get("title") or md.stem
            path_key = fm.get("app_path") if category == "app" else fm.get("package_path")
            legacy_pages[name] = {
                "wiki_relative_path": str(md.relative_to(wiki)).replace("\\", "/"),
                "package_path": path_key,
                "category": category,
                "last_sync_commit": fm.get("last_sync_commit") or None,
            }

    # Phase 45 D-11: walk wiki/entities/ and index by URI.
    entities_dict: dict[str, dict] = {}
    entities_dir = wiki / "entities"
    if entities_dir.exists():
        import frontmatter as _frontmatter  # local import: only needed for entity walk

        for page_path in sorted(entities_dir.glob("*.md")):
            if page_path.name == "_index.md":
                continue
            try:
                post = _frontmatter.load(page_path)
            except Exception:
                continue  # silently skip pages with un-parseable frontmatter
            uri = post.metadata.get("uri") if isinstance(post.metadata, dict) else None
            if not uri:
                continue  # silently skip pages without a URI
            entities_dict[uri] = {
                "path": page_path,
                "frontmatter": dict(post.metadata),
            }

    return ExistingPages(legacy=legacy_pages, entities=entities_dict)


def compute_diff(workspaces, existing):
    # Wiki pages use the unscoped slug; manifests carry the scope.
    # Normalize disk-side identifiers so set-diffs compare like-for-like.
    disk_names = {unscope(w["name"]) for w in workspaces}
    disk_paths = {w["path"]: unscope(w["name"]) for w in workspaces}
    existing_names = set(existing.keys())

    new = sorted(disk_names - existing_names)
    deleted_candidates = sorted(existing_names - disk_names)
    unchanged = sorted(disk_names & existing_names)

    # Heuristic rename detection: a deleted name and a new name share the same path
    renamed = []
    still_deleted = []
    still_new = set(new)
    for dname in deleted_candidates:
        old_path = existing[dname].get("package_path")
        if old_path and old_path in disk_paths:
            new_name = disk_paths[old_path]
            if new_name in still_new:
                renamed.append([dname, new_name])
                still_new.discard(new_name)
                continue
        still_deleted.append(dname)

    return {
        "new": sorted(still_new),
        "renamed": renamed,
        "deleted": still_deleted,
        "unchanged": unchanged,
    }


def attach_changed_files(workspaces: list, existing: dict, repo: Path) -> None:
    """For each workspace, compute changed files since its recorded
    last_sync_commit and attach the result in-place.

    Sets:
      - w["last_sync_commit"]: the SHA recorded on the vault page (or None)
      - w["changed_files"]: list of repo-relative paths that changed since
        that SHA, [] when no changes, or None when no recorded SHA exists
        (bootstrap case — caller should treat as "first sync").
    """
    from wiki_io.git_state import changed_files_since

    by_name = {unscope(w["name"]): w for w in workspaces}
    for name, w in by_name.items():
        rec = existing.get(name) or {}
        sha = rec.get("last_sync_commit")
        w["last_sync_commit"] = sha
        if not sha:
            w["changed_files"] = None
            continue
        w["changed_files"] = changed_files_since(repo, sha, w["path"])


def compute_state_gate(repo: Path) -> dict:
    """Return JSON-serializable gate info: whether state writes are allowed.

    {"allowed": bool, "reason": str, "head_commit": str | None}

    The agent reads this to decide whether to bump last_sync_commit on
    reviewed packages. When allowed=False, scan still runs in read-only
    mode — it reports drift but does not bump state.
    """
    from wiki_io.git_state import head_commit, is_clean_main

    ok, reason = is_clean_main(repo)
    return {
        "allowed": ok,
        "reason": reason,
        "head_commit": head_commit(repo),
    }


def reconcile_layout(repo: Path, pinned: list[dict]) -> dict:
    """Compare current detection against pinned layout. Returns:
    {"new": [<record>...], "missing": [<source>...], "changed": [{source, from, to}...]}
    """
    from wiki_io.detect_containers import detect

    detected = detect(repo)
    detected_by_source = {r["source"]: r for r in detected if r["source"]}
    pinned_by_source = {p["source"]: p for p in pinned if p["source"]}

    new = []
    for src, rec in detected_by_source.items():
        if src not in pinned_by_source and rec["classification"] != "ambiguous":
            new.append(rec)

    missing = []
    for src in pinned_by_source:
        if src not in detected_by_source:
            missing.append(src)

    changed = []
    for src, p in pinned_by_source.items():
        if src in detected_by_source:
            d = detected_by_source[src]
            if p["classification"] != d["classification"] and d["classification"] != "ambiguous":
                changed.append(
                    {
                        "source": src,
                        "from": p["classification"],
                        "to": d["classification"],
                    }
                )

    return {"new": new, "missing": missing, "changed": changed}


def _existing_source_paths(wiki: Path) -> set[str]:
    """Return the set of source_path frontmatter values across wiki/sources/.

    Used to skip ingest candidates whose summary page already exists. Paths
    are normalized to forward-slash form to match emitted candidate paths.
    """
    seen: set[str] = set()
    sources_dir = wiki / "sources"
    if not sources_dir.exists():
        return seen
    for md in sources_dir.rglob("*.md"):
        fm = _parse_frontmatter(_safe_read_text(md))
        sp = fm.get("source_path")
        if sp:
            seen.add(sp.replace("\\", "/").strip())
    return seen


def discover_docs(repo: Path, wiki: Path, pinned_containers: list[dict]) -> list[dict]:
    """Find ingest candidates in pinned `docs` containers.

    Walks the container recursively for .md files (plans live at
    docs/<area>/plans/<date>-<slug>.md and similar nested shapes).
    Returns one record per .md that has no existing source summary page.
    Records carry repo-relative paths so the LLM can hand them straight
    to /graph-wiki:ingest. PDF/DOCX support is deferred — see
    references/ingest-workflow.md "Future formats".
    """
    candidates: list[dict] = []
    existing = _existing_source_paths(wiki)
    for c in pinned_containers:
        if c.get("classification") != "docs":
            continue
        src_rel = c.get("source")
        if not src_rel:
            continue
        source_dir = repo / src_rel
        if not source_dir.exists() or not source_dir.is_dir():
            continue
        for md in sorted(source_dir.rglob("*.md")):
            rel_in_container = md.relative_to(source_dir).as_posix()
            rel_path = f"{src_rel}/{rel_in_container}"
            if rel_path in existing:
                continue
            candidates.append(
                {
                    "path": rel_path,
                    "container": src_rel,
                    "mtime": _dt.date.fromtimestamp(md.stat().st_mtime).isoformat(),
                    "title_guess": md.stem.replace("-", " ").replace("_", " ").title(),
                }
            )
    return candidates


# ----------------------------------------------------------------------------
# Index regeneration — dependencies/index.md
#
# Marker contract per wiki-schema.md "Auto-rendered sections":
#   <!-- auto:dependencies-index generated:<ISO> -->
#   (table)
#   <!-- /auto:dependencies-index -->
# Content outside the marker pair is preserved on regen.
# ----------------------------------------------------------------------------

DEPS_INDEX_OPEN = "<!-- auto:dependencies-index"
DEPS_INDEX_CLOSE = "<!-- /auto:dependencies-index -->"

_AUTO_BLOCK_RE_TEMPLATE = r"<!--\s*auto:{name}[^>]*-->.*?<!--\s*/auto:{name}\s*-->"


def collect_external_dependencies(workspaces: list[dict]) -> list[dict]:
    """Aggregate external dependencies across scanned workspaces.

    Returns a list sorted by (ecosystem, name) where each entry is::

        {
            "name": "react",
            "kind": "package",
            "ecosystem": "npm",
            "versions_in_use": ["19.0.0", "18.3.1"],
            "used_by": ["web-next-ts", "app-expo-ts"],
        }
    """
    by_key: dict[tuple[str, str], dict] = {}
    for w in workspaces:
        ecosystem = w.get("ecosystem")
        ext = w.get("external_deps") or {}
        if not ecosystem or not ext:
            continue
        ws_name = unscope(w["name"])
        for dep_name, version in ext.items():
            key = (ecosystem, dep_name)
            entry = by_key.get(key)
            if entry is None:
                entry = {
                    "name": dep_name,
                    "kind": "package",
                    "ecosystem": ecosystem,
                    "versions_in_use": [],
                    "used_by": [],
                }
                by_key[key] = entry
            v = (version or "").strip()
            if v and v not in entry["versions_in_use"]:
                entry["versions_in_use"].append(v)
            if ws_name not in entry["used_by"]:
                entry["used_by"].append(ws_name)
    for entry in by_key.values():
        entry["versions_in_use"].sort()
        entry["used_by"].sort()
    return sorted(by_key.values(), key=lambda e: (e["ecosystem"], e["name"].lower()))


def load_services_yaml(wiki: Path) -> list[dict]:
    """Read hand-maintained wiki/dependencies/services.yaml.

    Minimal parser tailored to a list-of-dicts shape::

        - name: MongoDB Atlas
          provider: mongodb-atlas
          used_by: [location-aws-node-ts, healthkit-aws-node-ts]
          load_bearing: true

    Returns ``[]`` when the file is absent or unparseable. Each entry comes
    out as a ``kind: service`` dict slotted into the index alongside packages.
    """
    services_path = wiki / "dependencies" / "services.yaml"
    if not services_path.exists():
        return []
    try:
        text = services_path.read_text(encoding="utf-8")
    except OSError:
        return []
    services: list[dict] = []
    current: dict | None = None
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith("- "):
            if current:
                services.append(current)
            current = {"kind": "service"}
            rest = line[2:]
            k, _, v = rest.partition(":")
            current[k.strip()] = _parse_yaml_scalar(v.strip())
        elif line.startswith("  ") and current is not None:
            k, _, v = line.strip().partition(":")
            current[k.strip()] = _parse_yaml_scalar(v.strip())
    if current:
        services.append(current)
    # Normalize used_by to a list
    for s in services:
        ub = s.get("used_by")
        if isinstance(ub, str):
            s["used_by"] = [x.strip() for x in ub.strip("[]").split(",") if x.strip()]
        elif ub is None:
            s["used_by"] = []
    return services


def _parse_yaml_scalar(v: str):
    if v == "" or v == "null":
        return None
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1].strip()
        if not inner:
            return []
        return [x.strip().strip("'\"") for x in inner.split(",") if x.strip()]
    if v in ("true", "false"):
        return v == "true"
    if v.lstrip("-").isdigit():
        return int(v)
    return v.strip("'\"")


def render_dependencies_index_table(
    deps: list[dict],
    services: list[dict],
    deps_dir: Path | None = None,
) -> str:
    """Render the marker-bounded table body for dependencies/index.md.

    When ``deps_dir`` is provided, the Detail column emits a wikilink only when
    a matching ``<name>.md`` page exists under ``deps_dir``; otherwise the cell
    is ``—`` so the lint doesn't flag the auto-block as a broken-link source.
    """
    def _detail_for(slug: str) -> str:
        if deps_dir is not None and not (deps_dir / f"{slug}.md").exists():
            return "—"
        return f"[[{slug}]]"

    lines = [
        "| Name | Kind | Ecosystem/Provider | Versions | Used by | Detail |",
        "|---|---|---|---|---|---|",
    ]
    for d in deps:
        versions = ", ".join(d["versions_in_use"]) if d["versions_in_use"] else "—"
        used_by = ", ".join(d["used_by"]) if d["used_by"] else "—"
        detail = _detail_for(d["name"])
        lines.append(f"| {d['name']} | package | {d['ecosystem']} | {versions} | {used_by} | {detail} |")
    for s in services:
        name = s.get("name", "")
        provider = s.get("provider", "")
        used_by = ", ".join(s.get("used_by") or []) or "—"
        detail = _detail_for(_to_slug(name)) if s.get("load_bearing") else "—"
        lines.append(f"| {name} | service | {provider} | n/a | {used_by} | {detail} |")
    return "\n".join(lines) + "\n"


def _to_slug(name: str) -> str:
    out: list[str] = []
    prev_alnum = False
    for c in name:
        if c.isalnum():
            out.append(c.lower())
            prev_alnum = True
        elif prev_alnum:
            out.append("-")
            prev_alnum = False
    return "".join(out).strip("-")


def _replace_or_append_auto_block(
    existing: str,
    open_tag: str,
    close_marker: str,
    block: str,
) -> str:
    """Replace the marker-bounded block in ``existing``, or append it."""
    pattern = re.compile(
        re.escape(open_tag) + r"[^>]*-->.*?" + re.escape(close_marker),
        re.DOTALL,
    )
    if pattern.search(existing):
        return pattern.sub(block, existing, count=1)
    sep = "" if not existing or existing.endswith("\n") else "\n"
    return existing + sep + "\n" + block + "\n"


def _extract_auto_block_body(
    existing: str,
    open_tag: str,
    close_marker: str,
) -> str | None:
    """Return the body between the open marker's ``-->`` and the close marker,
    or ``None`` when the auto-block isn't present. Lets callers compare
    rendered content against what's on disk and skip writes when only the
    timestamp would change.
    """
    pattern = re.compile(
        re.escape(open_tag) + r"[^>]*-->\n?(.*?)" + re.escape(close_marker),
        re.DOTALL,
    )
    m = pattern.search(existing)
    return m.group(1) if m else None


def regenerate_dependencies_index(wiki: Path, workspaces: list[dict]) -> Path | None:
    """Regenerate wiki/dependencies/index.md (marker-bounded). Returns the
    written path, or None if the dependencies/ folder doesn't exist yet or
    when the table body is unchanged (skipping the write keeps re-runs
    byte-identical so the scanner doesn't trip its own state gate)."""
    deps_dir = wiki / "dependencies"
    if not deps_dir.exists():
        return None
    deps = collect_external_dependencies(workspaces)
    services = load_services_yaml(wiki)
    table = render_dependencies_index_table(deps, services, deps_dir=deps_dir)
    index_path = deps_dir / "index.md"
    existing = index_path.read_text(encoding="utf-8") if index_path.exists() else ""
    existing_body = _extract_auto_block_body(existing, DEPS_INDEX_OPEN, DEPS_INDEX_CLOSE)
    if existing_body is not None and existing_body == table:
        return None
    generated = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    block = f"{DEPS_INDEX_OPEN} generated:{generated} -->\n{table}{DEPS_INDEX_CLOSE}"
    if not existing:
        existing = (
            "# Dependencies\n\n"
            "Auto-generated dependency index. The marker-bounded block below is "
            "regenerated by `/graph-wiki:scan`. Manual notes can sit outside the markers.\n\n"
        )
    new_text = _replace_or_append_auto_block(existing, DEPS_INDEX_OPEN, DEPS_INDEX_CLOSE, block)
    index_path.write_text(new_text, encoding="utf-8")
    return index_path


def main():
    p = argparse.ArgumentParser(description="Scan a monorepo for workspaces and diff against the wiki.")
    p.add_argument("--json", action="store_true", help="Emit JSON only")
    p.add_argument(
        "--no-file-map",
        action="store_true",
        help="Skip per-workspace file-map generation (saves time on huge monorepos)",
    )
    p.add_argument(
        "--max-depth",
        type=int,
        default=4,
        help="Max directory depth expanded as header sections in the file map (default: 4). "
        "Sub-directories deeper than this are listed as folder bullets in their parent section.",
    )
    p.add_argument(
        "--no-index-regen",
        action="store_true",
        help="Skip regenerating dependencies/index.md",
    )
    args = p.parse_args()

    wiki, _ = resolve_wiki_and_repo()
    workspace = wiki.parent

    layout = read_layout(wiki / "CLAUDE.md") if wiki.exists() else None
    pinned = layout.get("containers", []) if layout else None

    # Scan target = workspace + layout["repo_root"]. Defaults to the workspace
    # itself (workspace-is-repo layout); set `repo_root: ..` in the layout block
    # when the workspace lives inside the repo (e.g. <repo>/graph-wiki/).
    repo_root_rel = layout.get("repo_root", ".") if layout else "."
    repo = (workspace / repo_root_rel).resolve()
    if not repo.exists():
        print(f"[error] repo not found: {repo}", file=sys.stderr)
        sys.exit(1)

    if wiki.exists() and pinned:
        diff = reconcile_layout(repo, pinned)
        if any(diff[k] for k in ("new", "missing", "changed")) and not args.json:
            print("Layout drift detected:")
            for r in diff["new"]:
                print(f"  + new container: {r['source']} ({r['classification']})")
            for s in diff["missing"]:
                print(f"  - pinned container missing on disk: {s}")
            for c in diff["changed"]:
                print(f"  ~ classification change: {c['source']}: {c['from']} -> {c['to']}")
            print("(Re-run /graph-wiki:bootstrap or hand-edit the layout block to update.)")
            print()

    workspaces = discover_workspaces(repo, pinned_containers=pinned, workspace_dir=workspace)
    if not args.no_file_map:
        for w in workspaces:
            pkg_dir = repo / w["path"]
            fms = build_file_maps(pkg_dir, max_depth=args.max_depth)
            if fms is not None:
                prod_block, test_block = fms
                w["file_map"] = prod_block
                w["file_map_testing"] = test_block
    existing_pages = _load_existing_pages(wiki) if wiki.exists() else ExistingPages(legacy={}, entities={})
    existing_legacy = existing_pages.legacy
    if wiki.exists():
        attach_changed_files(workspaces, existing_legacy, repo)
    diff = compute_diff(workspaces, existing_legacy)

    doc_candidates: list[dict] = []
    if wiki.exists() and pinned:
        doc_candidates = discover_docs(repo, wiki, pinned)

    regenerated_indexes: list[str] = []
    if wiki.exists() and not args.no_index_regen:
        dep_index = regenerate_dependencies_index(wiki, workspaces)
        if dep_index is not None:
            regenerated_indexes.append(str(dep_index.relative_to(wiki)))

    result = {
        "repo": str(repo),
        "wiki": str(wiki),
        "workspace_count": len(workspaces),
        "workspaces": workspaces,
        "diff": diff,
        "doc_candidates": doc_candidates,
        "state_gate": compute_state_gate(repo),
        "regenerated_indexes": regenerated_indexes,
    }

    if args.json:
        print(json.dumps(result, indent=2))
        return

    print(f"Monorepo scan — {repo}")
    print(f"Detected {len(workspaces)} workspace package(s)")
    print()
    gate = result["state_gate"]
    if gate["allowed"]:
        print(f"State writes ALLOWED (HEAD: {gate['head_commit'][:8]})")
    else:
        print(f"State writes BLOCKED — {gate['reason']} (read-only scan)")
    print()
    for w in workspaces:
        dep_str = f" deps={len(w['depends_on'])}, used-by={w['depended_on_by']}"
        print(f"  - {w['name']} ({w['type']}, {w['language']}) @ {w['path']}{dep_str}")
    if wiki.exists():
        print()
        print(f"Diff against {wiki}/{{apps,packages,domains/*/packages}}/")
        print(f"  new:       {len(diff['new'])}")
        for n in diff["new"]:
            print(f"    + {n}")
        print(f"  renamed?:  {len(diff['renamed'])}")
        for old, new in diff["renamed"]:
            print(f"    ~ {old} -> {new}")
        print(f"  deleted?:  {len(diff['deleted'])}")
        for d in diff["deleted"]:
            print(f"    - {d}")
        print(f"  unchanged: {len(diff['unchanged'])}")
    if doc_candidates:
        print()
        print(f"Docs to ingest: {len(doc_candidates)}")
        for d in doc_candidates:
            print(f"  ? {d['path']}  (run /graph-wiki:ingest {d['path']})")

    if regenerated_indexes:
        print()
        print("Regenerated indexes:")
        for path in regenerated_indexes:
            print(f"  ✎ {path}")


# Public alias so callers can do: from wiki_io.scan_monorepo import scan
scan = discover_workspaces


if __name__ == "__main__":
    main()
