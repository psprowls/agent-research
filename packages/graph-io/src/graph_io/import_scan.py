"""Shared import-graph scanner.

Used by test_suites.emit (Phase 30, TestSuite -> Package edges) and
derived_edges.compute (Phase 31, references / depends_on derivation).
The two callers differ only in whether test files are included; the
regex passes and the package-prefix index are identical.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from graph_io.structural_nodes import _owning_package, _resolve_import_root  # noqa: F401

PkgRow = tuple[str, str | None, str | None]
"""(pkg_name, pkg_rel, pkg_attrs_json) — the tuple shape callers pass in."""

_PYTHON_IMPORT_RE = re.compile(r"^\s*(?:from|import)\s+([\w\.]+)", re.MULTILINE)
_JS_IMPORT_RE = re.compile(
    r"""(?:from|import|require)\s*\(?\s*['"]([^'"]+)['"]"""
)

_JS_EXTENSIONS = (".ts", ".js", ".tsx", ".jsx", ".mjs", ".cjs")
_JS_INDEX_SUFFIXES = ("index.ts", "index.js", "index.tsx", "index.jsx")
_SCAN_EXTENSIONS_JS = frozenset(_JS_EXTENSIONS)


def _build_pkg_index(
    pkg_rows: list[PkgRow],
) -> list[tuple[str, str, str | None]]:
    """Return [(pkg_prefix, pkg_name, pkg_rel)] sorted deepest-prefix-first.

    pkg_prefix is pkg_rel if not None else "" (root-rooted packages).
    """
    rows: list[tuple[str, str, str | None]] = []
    for pkg_name, pkg_rel, _attrs in pkg_rows:
        prefix = pkg_rel if pkg_rel is not None else ""
        rows.append((prefix, pkg_name, pkg_rel))
    rows.sort(key=lambda row: len(row[0]), reverse=True)
    return rows


def _build_importable_maps(
    pkg_rows: list[PkgRow],
) -> tuple[
    dict[str, tuple[str, str | None]],
    dict[str, tuple[str, str | None]],
]:
    """Return (py_importable_to_pkg, js_name_to_pkg).

    Python: pkg.name.replace('-', '_') -> (name, rel)
    JS/TS:  pkg.name -> (name, rel)  (package.json name including @scope)
    """
    py_map: dict[str, tuple[str, str | None]] = {}
    js_map: dict[str, tuple[str, str | None]] = {}
    for pkg_name, pkg_rel, pkg_attrs_json in pkg_rows:
        attrs = json.loads(pkg_attrs_json) if pkg_attrs_json else {}
        lang = attrs.get("language")
        if lang == "python":
            importable = pkg_name.replace("-", "_")
            py_map[importable] = (pkg_name, pkg_rel)
        elif lang in {"javascript", "typescript"}:
            js_map[pkg_name] = (pkg_name, pkg_rel)
    return py_map, js_map


def _match_python_import(
    module_str: str,
    py_map: dict[str, tuple[str, str | None]],
) -> tuple[str, str | None] | None:
    """Return (pkg_name, pkg_rel) for the first dotted segment, or None."""
    top = module_str.split(".", 1)[0]
    return py_map.get(top)


def _match_js_import(
    spec: str,
    importing_file: Path,
    repo_root: Path,
    js_map: dict[str, tuple[str, str | None]],
    pkg_index: list[tuple[str, str, str | None]],
) -> tuple[str, str | None] | None:
    """Resolve a JS/TS import specifier to (pkg_name, pkg_rel) or None."""
    if spec.startswith(".") or spec.startswith("/"):
        try:
            resolved = (importing_file.parent / spec).resolve()
        except OSError:
            return None
        candidates: list[Path] = [resolved]
        for ext in _JS_EXTENSIONS:
            candidates.append(resolved.with_suffix(ext))
        for idx in _JS_INDEX_SUFFIXES:
            candidates.append(resolved / idx)
        for cand in candidates:
            if cand.exists():
                try:
                    rel = cand.relative_to(repo_root).as_posix()
                except ValueError:
                    continue
                return _owning_package(rel, pkg_index)
        return None
    # Bare specifier — split @scope/name (two segments) or name (one)
    if spec.startswith("@"):
        key = "/".join(spec.split("/", 2)[:2])
    else:
        key = spec.split("/", 1)[0]
    return js_map.get(key)


# Task 2 adds: scan_package_imports / scan_files_imports
