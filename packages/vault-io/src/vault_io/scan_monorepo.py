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
from pathlib import Path

from vault_io._workspace import resolve_wiki_and_repo
from vault_io.layout_io import read_layout
from vault_io.lint.workflow_hints import _parse_workflow_hints

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
    name = _parse_pyproject(_safe_read_text(pp))
    if not name:
        return None
    return {
        "name": name,
        "path": str(pkg_path.relative_to(repo)).replace("\\", "/"),
        "type": "library",
        "language": "python",
        "version": None,
        "depends_on": [],
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


def build_file_map(pkg_path: Path, max_depth: int = 4, max_entries: int = 80) -> str | None:
    """Build a markdown ``## File map - <name>`` block for ``pkg_path``.

    Emits a sectioned format (full block including the H2 heading):

    - ``## File map - <pkg-name>`` at the top with a paragraph placeholder
      and bullets for files at the package root.
    - One header section per subdirectory (``### <pkg>/<sub>/``,
      ``#### <pkg>/<sub>/<sub2>/``, ...) up to ``max_depth`` directory
      levels (default 4 → headings stop at H6 / ``######``).
    - Subdirectories deeper than the cutoff are emitted as folder bullets
      (``- `<sub>/` — TODO``) inside their parent section instead of getting
      their own header.

    Uses ``git ls-files`` so .gitignore is respected. Per-entry
    descriptions ("— TODO") are filled in by the agent later. Returns
    ``None`` when ``pkg_path`` isn't under git.
    """
    files = _git_ls_files(pkg_path)
    if files is None:
        return None

    pkg_name = pkg_path.name
    title_line = f"## File map - {pkg_name}"
    placeholder = "TODO — describe what this directory contains."

    if not files:
        return f"{title_line}\n{placeholder}\n\n- (no tracked files)\n"

    truncated = len(files) > max_entries
    files = files[:max_entries]

    tree: dict = {}
    for rel in files:
        parts = rel.split("/")
        node = tree
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = None

    out: list[str] = []

    def emit(node: dict, dir_depth: int, dir_path: str) -> None:
        # ``dir_path`` is the path from (and including) the package root
        # without a trailing slash — e.g. ``p`` for the root, ``p/src`` for
        # a sub-section. The trailing slash is added at emit time.
        if dir_depth == 0:
            out.append(title_line)
        else:
            hashes = "#" * (dir_depth + 2)
            out.append(f"{hashes} {dir_path}/")
        out.append(placeholder)
        out.append("")

        file_names = sorted([k for k, v in node.items() if v is None], key=str.lower)
        dir_names = sorted([k for k, v in node.items() if v is not None], key=str.lower)

        for f in file_names:
            out.append(f"- `{f}` — TODO")
        # Sub-dirs whose own depth would exceed ``max_depth`` are listed as
        # folder bullets in this section instead of recursing.
        bullet_dirs = [d for d in dir_names if dir_depth + 1 > max_depth]
        for d in bullet_dirs:
            out.append(f"- `{d}/` — TODO")
        out.append("")

        section_dirs = [d for d in dir_names if dir_depth + 1 <= max_depth]
        for d in section_dirs:
            emit(node[d], dir_depth + 1, f"{dir_path}/{d}")

    emit(tree, dir_depth=0, dir_path=pkg_name)

    if truncated:
        out.append(f"> Truncated at {max_entries} files.")
        out.append("")

    return "\n".join(out).rstrip() + "\n"


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
        w["vault_path"] = _vault_path_for(w, vault_dir=vault_dir)
    return workspaces


def _vault_path_for(pkg: dict, vault_dir: str | None = None) -> str:
    """Return the canonical vault page path for a discovered workspace.

    Routing:
      - apps                                    -> ``apps/<name>/<name>.md``
      - domain-scoped libraries/services/tools  -> ``domains/<d>/packages/<name>/<name>.md``
      - everything else                         -> ``<vault_dir>/<name>/<name>.md``
        (defaults to ``packages/`` when no pinned container vault_dir applies)

    The ``vault_dir`` argument is the matched container's pinned vault_dir
    from ``wiki/CLAUDE.md`` — honors per-repo layouts that map a non-default
    source directory (e.g. ``plugins/``) to a non-default vault directory.
    Falls back to ``packages`` for heuristic discovery and shared
    ``packages/lib``-type directories.
    """
    name = unscope(pkg["name"])
    if pkg.get("type") == "app":
        return f"apps/{name}/{name}.md"
    domain = pkg.get("domain")
    if domain:
        return f"domains/{domain}/packages/{name}/{name}.md"
    base = vault_dir or "packages"
    return f"{base}/{name}/{name}.md"


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


def _load_existing_pages(wiki):
    """Return dict of workspace name → {vault_path, package_path, category}.

    Walks every place package/app pages may live:

      - wiki/apps/**/*.md                       (apps — default)
      - wiki/packages/**/*.md                   (cross-domain packages — default)
      - wiki/<container>/**/*.md                (any layout-pinned container
                                                    in wiki/CLAUDE.md whose
                                                    classification is package or app)
      - wiki/domains/<domain>/packages/**/*.md  (domain-scoped packages)

    The category is read from frontmatter when present so the diff can
    distinguish apps from libraries regardless of which directory they live in.
    """
    if not wiki:
        return {}
    pages = {}
    vault = wiki
    walked: set[Path] = set()

    def _collect(root, default_category, fold_companions=False):
        resolved = root.resolve() if root.exists() else root
        if resolved in walked or not root.exists():
            return
        walked.add(resolved)

        # First pass: discover companion stems per directory from parent overviews.
        # A parent overview is the .md whose stem matches its parent directory name
        # (e.g. packages/vault-io/vault-io.md). Its workflow_hints frontmatter
        # declares which sibling stems are companions and should be folded.
        companions_by_dir: dict[Path, set[str]] = {}
        if fold_companions:
            for md in root.rglob("*.md"):
                if md.stem != md.parent.name:
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
            pages[name] = {
                "vault_path": str(md.relative_to(wiki)).replace("\\", "/"),
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
            if md.stem != md.parent.name:
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
            pages[name] = {
                "vault_path": str(md.relative_to(wiki)).replace("\\", "/"),
                "package_path": path_key,
                "category": category,
                "last_sync_commit": fm.get("last_sync_commit") or None,
            }
    return pages


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
    from vault_io.git_state import changed_files_since

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
    from vault_io.git_state import head_commit, is_clean_main

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
    from vault_io.detect_containers import detect

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


def render_dependencies_index_table(deps: list[dict], services: list[dict]) -> str:
    """Render the marker-bounded table body for dependencies/index.md."""
    lines = [
        "| Name | Kind | Ecosystem/Provider | Versions | Used by | Detail |",
        "|---|---|---|---|---|---|",
    ]
    for d in deps:
        versions = ", ".join(d["versions_in_use"]) if d["versions_in_use"] else "—"
        used_by = ", ".join(d["used_by"]) if d["used_by"] else "—"
        detail = f"[[{d['name']}]]"
        lines.append(f"| {d['name']} | package | {d['ecosystem']} | {versions} | {used_by} | {detail} |")
    for s in services:
        name = s.get("name", "")
        provider = s.get("provider", "")
        used_by = ", ".join(s.get("used_by") or []) or "—"
        detail = f"[[{_to_slug(name)}]]" if s.get("load_bearing") else "—"
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
    table = render_dependencies_index_table(deps, services)
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
            print("(Re-run /graph-wiki:init or hand-edit the layout block to update.)")
            print()

    workspaces = discover_workspaces(repo, pinned_containers=pinned, workspace_dir=workspace)
    if not args.no_file_map:
        for w in workspaces:
            pkg_dir = repo / w["path"]
            fm = build_file_map(pkg_dir, max_depth=args.max_depth)
            if fm is not None:
                w["file_map"] = fm
    existing = _load_existing_pages(wiki) if wiki.exists() else {}
    if wiki.exists():
        attach_changed_files(workspaces, existing, repo)
    diff = compute_diff(workspaces, existing)

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


# Public alias so callers can do: from vault_io.scan_monorepo import scan
scan = discover_workspaces


if __name__ == "__main__":
    main()
