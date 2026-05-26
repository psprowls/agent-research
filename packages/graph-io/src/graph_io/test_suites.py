"""TestSuite emitter: TestSuite nodes + physically_contains re-parenting + tests edges (TEST-01..07).

Discovers test root directories from filesystem layout (conventional
tests/, __tests__/ and package-local equivalents) and framework config
(pyproject [tool.pytest.ini_options] testpaths, pytest.ini, jest/vitest
'roots'). Emits one TestSuite per root, re-parents every is_test=true
File node from Repository to its suite, and derives tests edges from
import scans of the test files.

Suites are flat (TEST-07, D-16): tests/integration/auth/ produces ONE
suite named tests/integration/auth/, not nested suites.

Phase 30 emits only TestSuite -> Package and TestSuite -> Repository
edges; TestSuite -> Domain is Phase 31's responsibility (D-13).
"""

from __future__ import annotations

import fnmatch
import json
import re
import sqlite3
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from source_parser.projections.graph import GraphEdge, GraphNode, GraphRecords

from graph_io import _ignore, upsert
from graph_io.structural_nodes import (
    _TEST_DIR_NAMES,
    _owning_package,
    _resolve_import_root,
)
from graph_io.uri import RepoContext, test_suite_uri

# --- Module-private constants ---

_REPOSITORY_EDGE_THRESHOLD = 5  # D-12: K=5 for whole-system tests edge

_SPEC_FILENAME_GLOBS = ("*_spec.py", "*_spec.js", "*_spec.ts")  # D-17 contract
_UNIT_FILENAME_GLOBS = (
    "test_*.py", "*_test.py",
    "*.test.js", "*.test.ts", "*.test.jsx", "*.test.tsx",
    "*_test.js", "*_test.ts",
)

_PYTEST_INI_FILENAMES = frozenset({"pytest.ini"})
_JS_TEST_CONFIG_GLOBS = ("jest.config.*", "vitest.config.*")

_PYTHON_IMPORT_RE = re.compile(r"^\s*(?:from|import)\s+([\w\.]+)", re.MULTILINE)
_JS_IMPORT_RE = re.compile(
    r"""(?:from|import|require)\s*\(?\s*['"]([^'"]+)['"]""",
    re.MULTILINE,
)


@dataclass(frozen=True)
class _TestRoot:
    rel_path: str                              # e.g. "tests/integration" or "packages/foo/tests"
    owner_kind: str                            # "repository" or "package"
    owner_name: str | None                     # pkg_name when owner_kind=='package'
    owner_pkg_rel: str | None                  # pkg_rel when owner_kind=='package'
    language: str | None                       # 'python'|'javascript'|'typescript'|None


# --- Helpers ---


def _build_pkg_index(
    pkg_rows: list[tuple[str, str | None, str | None]],
) -> list[tuple[str, str, str | None]]:
    """Build the (pkg_prefix, pkg_name, pkg_rel) index sorted deepest-first
    for _owning_package consumption."""
    return sorted(
        (
            (pkg_rel or "", pkg_name, pkg_rel)
            for pkg_name, pkg_rel, _ in pkg_rows
        ),
        key=lambda t: len(t[0]),
        reverse=True,
    )


def _read_pytest_testpaths(pkg_dir: Path) -> Iterable[list[str]]:
    """Yield testpaths lists from pyproject.toml and pytest.ini if present."""
    pp = pkg_dir / "pyproject.toml"
    if pp.exists():
        try:
            data = tomllib.loads(pp.read_text(encoding="utf-8"))
            testpaths = (
                data.get("tool", {})
                    .get("pytest", {})
                    .get("ini_options", {})
                    .get("testpaths")
            )
            if isinstance(testpaths, list):
                yield [str(x) for x in testpaths if isinstance(x, str)]
            elif isinstance(testpaths, str):
                yield testpaths.split()
        except tomllib.TOMLDecodeError as exc:
            print(f"[test_suites] warning: {pp} malformed: {exc}", file=sys.stderr)

    ini = pkg_dir / "pytest.ini"
    if ini.exists():
        try:
            text = ini.read_text(encoding="utf-8")
            m = re.search(r"^\s*testpaths\s*=\s*(.+)$", text, re.MULTILINE)
            if m:
                yield m.group(1).split()
        except OSError as exc:
            print(f"[test_suites] warning: {ini} unreadable: {exc}", file=sys.stderr)


def _classify_suite_kind(suite_rel: str, file_rels: list[str]) -> str:
    """D-17 kind classification: dir-name precedence then filename fallback."""
    parts = suite_rel.lower().split("/")
    for p in parts:
        if "integration" in p:
            return "integration"
        if p in {"e2e", "system"}:
            return "e2e"
        if "contract" in p:
            return "contract"

    has_spec = any(
        fnmatch.fnmatch(Path(f).name, g)
        for f in file_rels
        for g in _SPEC_FILENAME_GLOBS
    )
    if has_spec:
        return "contract"

    has_unit = any(
        fnmatch.fnmatch(Path(f).name, g)
        for f in file_rels
        for g in _UNIT_FILENAME_GLOBS
    )
    if has_unit:
        return "unit"
    return "unknown"


def _discover_test_roots(
    repo_root: Path,
    skip_dirs: frozenset[str],
    pkg_rows: list[tuple[str, str | None, str | None]],
) -> list[_TestRoot]:
    """Discover conventional + config-declared test root directories.

    Conventional (filesystem-driven):
      - repo-root tests/: if it has subdirs, each subdir is a root; otherwise
        if it holds files directly, tests/ itself is one root (TEST-02).
      - Each Package's <pkg>/tests/ and <pkg>/__tests__/ if present (TEST-03).

    Config-driven (D-18):
      - pyproject [tool.pytest.ini_options] testpaths -> additional roots
        relative to the Package directory.
      - pytest.ini [pytest] testpaths via single-line regex.
    """
    roots: list[_TestRoot] = []
    seen: set[str] = set()

    def _add(
        rel: str,
        owner_kind: str,
        *,
        owner_name: str | None = None,
        owner_pkg_rel: str | None = None,
        language: str | None = None,
    ) -> None:
        if rel in seen:
            return
        if _ignore.should_skip(rel, skip_dirs):
            return
        seen.add(rel)
        roots.append(
            _TestRoot(
                rel_path=rel,
                owner_kind=owner_kind,
                owner_name=owner_name,
                owner_pkg_rel=owner_pkg_rel,
                language=language,
            )
        )

    # Repo-root tests/ (TEST-02)
    repo_tests = repo_root / "tests"
    if repo_tests.is_dir():
        subdirs = [
            d
            for d in repo_tests.iterdir()
            if d.is_dir() and not _ignore.should_skip(d.name, skip_dirs)
        ]
        if subdirs:
            for sub in sorted(subdirs):
                rel = sub.relative_to(repo_root).as_posix()
                _add(rel, "repository")
        else:
            # Flat: tests/ itself is the suite if it holds files.
            files = [f for f in repo_tests.iterdir() if f.is_file()]
            if files:
                _add("tests", "repository")

    # Package-local tests/ and __tests__/ (TEST-03)
    for pkg_name, pkg_rel, pkg_attrs_json in pkg_rows:
        pkg_attrs = json.loads(pkg_attrs_json) if pkg_attrs_json else {}
        lang = pkg_attrs.get("language")
        if not pkg_rel:
            # Root Package — already covered by repo-root tests/ scan above.
            continue
        pkg_dir = repo_root / pkg_rel
        for candidate in ("tests", "__tests__"):
            cdir = pkg_dir / candidate
            if cdir.is_dir():
                rel = cdir.relative_to(repo_root).as_posix()
                _add(
                    rel,
                    "package",
                    owner_name=pkg_name,
                    owner_pkg_rel=pkg_rel,
                    language=lang,
                )

    # Config-driven roots (D-18) — pyproject testpaths.
    pkg_index = _build_pkg_index(pkg_rows)
    for pkg_name, pkg_rel, pkg_attrs_json in pkg_rows:
        pkg_attrs = json.loads(pkg_attrs_json) if pkg_attrs_json else {}
        lang = pkg_attrs.get("language")
        pkg_dir = (repo_root / pkg_rel) if pkg_rel else repo_root
        if lang == "python":
            for cfg_paths in _read_pytest_testpaths(pkg_dir):
                for tp_rel in cfg_paths:
                    full = (pkg_dir / tp_rel).resolve()
                    try:
                        rel = full.relative_to(repo_root).as_posix()
                    except ValueError:
                        continue
                    if not full.is_dir():
                        continue
                    owner = _owning_package(rel, pkg_index)
                    if owner is None:
                        _add(rel, "repository", language="python")
                    else:
                        own_name, own_rel = owner
                        _add(
                            rel,
                            "package",
                            owner_name=own_name,
                            owner_pkg_rel=own_rel,
                            language="python",
                        )

    return roots


# --- Public emit() ---


def emit(
    conn: sqlite3.Connection,
    *,
    repo_root: Path,
    ctx: RepoContext,
    skip_dirs: frozenset[str],
) -> None:
    """Emit TestSuite nodes + physically_contains re-parenting + tests edges.

    Filled in by Tasks 2 and 3.
    """
    return
