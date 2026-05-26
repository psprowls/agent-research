"""Structural nodes: Repository + SubPackage + File role flags (STRUCT-01..05).

This module is the bulk of Phase 29: it walks the repository tree and emits
the strict physical containment subgraph that all later structural queries
(Phase 30 EntryPoint, Phase 31 Domain, Phase 32 query layer) build on.

Tree shape (D-13):
  Repository
    -> Package (always)
       Python:  -> SubPackage -> [SubPackage -> ...] -> File
       JS/TS:   -> File (no SubPackage layer; D-18)
  Repository (test files only, D-14)
    -> File (is_test=true; Phase 30 will re-parent under TestSuite)

Every emitted node carries a `uri` so `resolve.sweep` (D-16) can distinguish
URI-bearing structural nodes from orphan AST nodes by predicate.
"""

from __future__ import annotations

import fnmatch
import json
import os
import sqlite3
from pathlib import Path
from typing import Iterator

from source_parser.projections.graph import GraphEdge, GraphNode, GraphRecords

from graph_io import _ignore, upsert
from graph_io.update import NotInGitRepoError, _git
from graph_io.uri import RepoContext, file_uri, pkg_uri, repo_uri, subpkg_uri

# --- Module-private constants (role-flag heuristics, D-09..D-12, D-15) ---

_CONFIG_FILENAMES: frozenset[str] = frozenset({
    # Python ecosystem
    "pyproject.toml", "setup.cfg", "setup.py", "tox.ini", "pytest.ini",
    "mypy.ini", ".flake8", "ruff.toml", "uv.toml",
    # JS/TS ecosystem (exact-match common manifests)
    "package.json",
    # Other
    "Cargo.toml", "go.mod", "Makefile", "Justfile", ".editorconfig",
})

_CONFIG_GLOBS: tuple[str, ...] = (
    "tsconfig*.json",
    "*.config.js", "*.config.ts", "*.config.mjs", "*.config.cjs",
    ".eslintrc", ".eslintrc.*",
    ".prettierrc", ".prettierrc.*",
    "babel.config.*",
)

_GENERATED_FILENAME_PATTERNS: tuple[str, ...] = (
    "*_pb2.py", "*_pb2_grpc.py", "*.pb.go",
    "*.gen.ts", "*.gen.go",
    "*.generated.ts", "*.generated.go",
)

_GENERATED_DIRS: frozenset[str] = frozenset({"__generated__", "generated"})

_SHEBANG_EXTENSIONS: frozenset[str] = frozenset({
    ".py", ".sh", ".bash", ".zsh", ".js", ".ts", ".rb", ".pl", "",
})

_TEST_DIR_NAMES: frozenset[str] = frozenset({"tests", "__tests__", "test"})

_TEST_FILENAME_GLOBS: tuple[str, ...] = (
    "test_*.py", "*_test.py",
    "*.test.js", "*.test.ts", "*.test.tsx", "*.test.jsx",
    "*.spec.js", "*.spec.ts", "*.spec.tsx", "*.spec.jsx",
)

_GENERIC_CONTAINER_DIRS: frozenset[str] = frozenset({
    "packages", "libs", "tests", "apps", "shared", "common",
})

_JSTS_EXTENSIONS: frozenset[str] = frozenset({".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"})


# --- Repository helpers (D-01, D-02) ---


def _detect_default_branch(repo_root: Path) -> str | None:
    """Return the repo's default branch name, or None on detached HEAD.

    Tries `git symbolic-ref --short refs/remotes/origin/HEAD` first; falls
    back to `git symbolic-ref --short HEAD`. Returns None if both fail
    (detached HEAD or not a git repo).
    """
    try:
        out = _git(
            ["symbolic-ref", "--short", "refs/remotes/origin/HEAD"], cwd=repo_root
        ).strip()
    except NotInGitRepoError:
        try:
            out = _git(["symbolic-ref", "--short", "HEAD"], cwd=repo_root).strip()
        except NotInGitRepoError:
            return None
    return out.removeprefix("origin/") or None


def _detect_repo_url(repo_root: Path, ctx: RepoContext) -> str:
    """Return the canonical url for the Repository node.

    Remote mode (ctx.org != 'local'): `git remote get-url origin` stdout.
    Local-fallback mode: absolute filesystem path. On any git failure in
    remote mode, falls back to the filesystem path so the structural tree
    always has a usable url (D-02).
    """
    if ctx.org == "local":
        return str(repo_root.absolute())
    try:
        return _git(["remote", "get-url", "origin"], cwd=repo_root).strip()
    except NotInGitRepoError:
        return str(repo_root.absolute())


# --- Role-flag heuristics (D-09..D-12) ---


def _is_test_path(rel_path: str) -> bool:
    """D-09: True if path traverses a test directory OR filename matches a test glob."""
    p = Path(rel_path)
    for part in p.parts[:-1]:
        if part in _TEST_DIR_NAMES:
            return True
    name = p.name
    for glob in _TEST_FILENAME_GLOBS:
        if fnmatch.fnmatch(name, glob):
            return True
    return False


def _is_config_file(name: str) -> bool:
    """D-10: True if filename is in the curated allow-list or matches a config glob."""
    if name in _CONFIG_FILENAMES:
        return True
    for glob in _CONFIG_GLOBS:
        if fnmatch.fnmatch(name, glob):
            return True
    return False


def _is_generated(path: Path, name: str, rel_path: str = "") -> bool:
    """D-11: True if filename pattern matches OR first 20 lines contain a marker."""
    for glob in _GENERATED_FILENAME_PATTERNS:
        if fnmatch.fnmatch(name, glob):
            return True
    # Directory-based detection
    parts = Path(rel_path).parts if rel_path else ()
    for part in parts[:-1]:
        if part in _GENERATED_DIRS:
            return True
    # Content marker scan — capped at 1 MB, first 20 lines
    try:
        if path.stat().st_size > 1_000_000:
            return False
        with path.open("r", encoding="utf-8", errors="ignore") as fh:
            for i, line in enumerate(fh):
                if i >= 20:
                    break
                if "@generated" in line:
                    return True
                low = line.lower()
                if "code generated by" in low or "do not edit" in low:
                    return True
    except OSError:
        return False
    return False


def _is_type_only(name: str) -> bool:
    """D-11: True for .d.ts and .pyi files."""
    return name.endswith(".d.ts") or name.endswith(".pyi")


def _is_executable(path: Path, name: str) -> bool:
    """D-12: True if OS exec bit set OR (eligible extension AND shebang first line)."""
    try:
        if os.access(path, os.X_OK) and path.is_file():
            return True
    except OSError:
        pass
    ext = Path(name).suffix
    if ext not in _SHEBANG_EXTENSIONS:
        return False
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as fh:
            first = fh.readline()
            return first.startswith("#!")
    except OSError:
        return False


# --- SubPackage helpers (D-04..D-08) ---


def _resolve_import_root(pkg_dir: Path, importable: str) -> Path | None:
    """D-06: src-layout probe then flat-layout probe; None if neither."""
    src_root = pkg_dir / "src" / importable / "__init__.py"
    if src_root.exists():
        return pkg_dir / "src" / importable
    flat_root = pkg_dir / importable / "__init__.py"
    if flat_root.exists():
        return pkg_dir / importable
    return None


def _walk_subpackages(
    import_root: Path, skip_dirs: frozenset[str], repo_root: Path
) -> Iterator[Path]:
    """Yield each __init__.py-containing subdirectory under import_root.

    Includes import_root itself. Honors skip_dirs via _ignore.should_skip.
    Does not follow symlinks (os.walk default).
    """
    if not (import_root / "__init__.py").exists():
        return
    for dirpath, dirnames, filenames in os.walk(import_root, followlinks=False):
        d = Path(dirpath)
        # Skip filtered dirs in-place so os.walk doesn't descend into them
        dirnames[:] = [
            name for name in dirnames
            if not _ignore.should_skip(name, skip_dirs)
        ]
        if "__init__.py" in filenames:
            try:
                rel = d.relative_to(repo_root).as_posix()
            except ValueError:
                continue
            if _ignore.should_skip(rel, skip_dirs):
                continue
            yield d


def _dotted_path(subpkg_dir: Path, import_root: Path) -> str:
    """D-07: dotted path including the top-level importable name."""
    parent = import_root.parent
    rel = subpkg_dir.relative_to(parent).as_posix()
    return ".".join(rel.split("/"))


# --- Public emit() ---


def emit(
    conn: sqlite3.Connection,
    *,
    repo_root: Path,
    ctx: RepoContext,
    skip_dirs: frozenset[str],
) -> None:
    """Emit Repository + SubPackage + File nodes and physically_contains edges.

    Reads the existing Package rows (written by `packages.refresh`) to drive
    per-Package SubPackage walks (Python only; D-18) and File enumeration.
    Reads File SourceNode attrs (`_has_main_block`, `_has_importable_symbols`
    landed by SPARSER-01) from `nodes.attrs_json` for the `has_main` /
    `is_importable` File role flags (D-20).

    Builds the strict containment tree (D-13):
      Repository -> Package
      Python:  Package -> SubPackage -> [SubPackage -> ...] -> File
      JS/TS:   Package -> File
      Test files (is_test=true): Repository -> File (D-14)
      Generic container directories never emit nodes (D-15).
    """
    repo_root = Path(repo_root).resolve()

    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []

    # --- Repository node (D-01, D-02, D-03) ---

    repo_node = GraphNode(
        kind="repository",
        name=ctx.repo,
        path=None,
        line=None,
        attrs={
            "uri": repo_uri(ctx),
            "owner": ctx.org,
            "name": ctx.repo,
            "url": _detect_repo_url(repo_root, ctx),
            "default_branch": _detect_default_branch(repo_root),
        },
    )
    nodes.append(repo_node)

    repo_key = ("repository", ctx.repo, None)

    # --- Read existing Package rows ---

    pkg_rows = conn.execute(
        "SELECT name, path, attrs_json FROM nodes WHERE kind='package'"
    ).fetchall()

    # Repository -> Package edges (D-03)
    for pkg_name, pkg_path, _ in pkg_rows:
        edges.append(
            GraphEdge(
                src=repo_key,
                dst=("package", pkg_name, pkg_path),
                kind="physically_contains",
                attrs={},
            )
        )

    # --- Per-package emission ---

    # Track which files we've already covered so we don't double-emit when
    # files sit under multiple packages (e.g. root manifest + nested manifest).
    emitted_file_paths: set[str] = set()

    for pkg_name, pkg_rel_path, pkg_attrs_json in pkg_rows:
        pkg_attrs = json.loads(pkg_attrs_json) if pkg_attrs_json else {}
        language = pkg_attrs.get("language")
        pkg_key = ("package", pkg_name, pkg_rel_path)

        pkg_dir = (
            repo_root / pkg_rel_path
            if pkg_rel_path
            else repo_root
        ).resolve()

        # SubPackage emission (Python only, D-18)
        subpkg_dirs: list[Path] = []
        import_root: Path | None = None
        if language == "python":
            importable = pkg_name.replace("-", "_")
            import_root = _resolve_import_root(pkg_dir, importable)
            if import_root is not None:
                subpkg_dirs = sorted(
                    _walk_subpackages(import_root, skip_dirs, repo_root),
                    key=lambda p: p.as_posix(),
                )

        # Build SubPackage nodes + edges
        # Track subpkg by absolute path -> (dotted_path, rel_path) for File parenting
        subpkg_by_dir: dict[Path, tuple[str, str]] = {}
        for subpkg_dir in subpkg_dirs:
            assert import_root is not None
            dotted = _dotted_path(subpkg_dir, import_root)
            rel = subpkg_dir.relative_to(repo_root).as_posix()
            subpkg_by_dir[subpkg_dir.resolve()] = (dotted, rel)

            # D-15 guard: SubPackage nodes never carry generic container names
            if dotted in _GENERIC_CONTAINER_DIRS:
                continue

            nodes.append(
                GraphNode(
                    kind="subpackage",
                    name=dotted,
                    path=rel,
                    line=None,
                    attrs={
                        "uri": subpkg_uri(ctx, pkg_name, dotted),
                        "dotted_path": dotted,
                        "language": "python",
                    },
                )
            )

            # Parent: deepest enclosing SubPackage, else Package
            parent_dir = subpkg_dir.parent.resolve()
            if subpkg_dir.resolve() == import_root.resolve():
                # Top-level subpkg sits directly under Package
                parent_src = pkg_key
            elif parent_dir in subpkg_by_dir:
                parent_dotted, parent_rel = subpkg_by_dir[parent_dir]
                parent_src = ("subpackage", parent_dotted, parent_rel)
            else:
                # Shouldn't happen, but fall back to Package
                parent_src = pkg_key

            edges.append(
                GraphEdge(
                    src=parent_src,
                    dst=("subpackage", dotted, rel),
                    kind="physically_contains",
                    attrs={},
                )
            )

        # File emission — walk every tracked file under pkg_dir
        for dirpath, dirnames, filenames in os.walk(pkg_dir, followlinks=False):
            d = Path(dirpath)
            try:
                d_rel = d.relative_to(repo_root).as_posix()
            except ValueError:
                continue
            # Filter dirs in-place
            dirnames[:] = [
                name for name in dirnames
                if not _ignore.should_skip(name, skip_dirs)
            ]
            if d_rel and _ignore.should_skip(d_rel, skip_dirs):
                continue
            for filename in filenames:
                fpath = d / filename
                try:
                    rel = fpath.relative_to(repo_root).as_posix()
                except ValueError:
                    continue
                if _ignore.should_skip(rel, skip_dirs):
                    continue
                if rel in emitted_file_paths:
                    continue
                emitted_file_paths.add(rel)

                ext = Path(filename).suffix
                is_python = ext == ".py"
                is_jsts = ext in _JSTS_EXTENSIONS
                file_language = "python" if is_python else (
                    "javascript" if ext in {".js", ".jsx", ".mjs", ".cjs"} else (
                        "typescript" if ext in {".ts", ".tsx"} else None
                    )
                )

                # SPARSER attrs for Python (D-20)
                has_main = False
                is_importable = False
                if is_python:
                    row = conn.execute(
                        "SELECT attrs_json FROM nodes WHERE kind='file' AND path=?",
                        (rel,),
                    ).fetchone()
                    if row and row[0]:
                        sparser_attrs = json.loads(row[0])
                        has_main = bool(sparser_attrs.get("_has_main_block", False))
                        is_importable = bool(
                            sparser_attrs.get("_has_importable_symbols", False)
                        )
                elif is_jsts:
                    has_main = False
                    is_importable = True
                # else: both default False

                is_test = _is_test_path(rel)
                is_config = _is_config_file(filename)
                is_generated = _is_generated(fpath, filename, rel)
                is_type_only = _is_type_only(filename)
                is_executable = _is_executable(fpath, filename)

                file_attrs = {
                    "uri": file_uri(ctx, rel),
                    "is_importable": is_importable,
                    "is_executable": is_executable,
                    "has_main": has_main,
                    "is_test": is_test,
                    "is_config": is_config,
                    "is_generated": is_generated,
                    "is_type_only": is_type_only,
                }
                if file_language is not None:
                    file_attrs["language"] = file_language

                # D-15 guard: file basenames matching generic container dirs
                # would only matter if someone literally named a file "tests"
                # without an extension. Defensive: skip if it would collide.
                if filename in _GENERIC_CONTAINER_DIRS:
                    continue

                nodes.append(
                    GraphNode(
                        kind="file",
                        name=filename,
                        path=rel,
                        line=None,
                        attrs=file_attrs,
                    )
                )

                # Parent resolution (D-13, D-14)
                if is_test:
                    parent_src = repo_key  # D-14: Repository, not Package
                elif is_python and subpkg_by_dir:
                    # Find deepest enclosing SubPackage by directory
                    cur = d.resolve()
                    parent_src = None
                    while True:
                        if cur in subpkg_by_dir:
                            sp_dotted, sp_rel = subpkg_by_dir[cur]
                            parent_src = ("subpackage", sp_dotted, sp_rel)
                            break
                        if cur == pkg_dir or cur.parent == cur:
                            break
                        cur = cur.parent
                    if parent_src is None:
                        parent_src = pkg_key
                else:
                    parent_src = pkg_key

                edges.append(
                    GraphEdge(
                        src=parent_src,
                        dst=("file", filename, rel),
                        kind="physically_contains",
                        attrs={},
                    )
                )

    upsert.upsert_records(conn, GraphRecords(nodes=nodes, edges=edges))
