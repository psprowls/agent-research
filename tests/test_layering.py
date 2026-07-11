"""Static layering enforcement over every workspace member (package-layering-review S6).

Two checks per `packages/*` member — third-party deps are unconstrained,
only in-repo edges are policed:

  (a) declared deps: the in-repo subset of `project.dependencies` and every
      `project.optional-dependencies` group must be within the layer policy.
      graph-wiki-core's BASE set excludes model-adapter/subagent-runtime —
      those are legal only inside its `bedrock` extra (EXTRA_POLICY).
  (b) AST imports: every `import` / `from … import` of an in-repo package at
      ANY scope under the member's `src/` tree must be within the same policy.
      The import-name -> dist-name mapping is derived at runtime from
      `packages/*/src/<import_name>` directory names, so it cannot rot.

The AST check cannot see the base-vs-extra split (core's gated modules
legitimately import the bedrock stack); base-closure importability is owned by
tests/integration/test_base_closure_import.py.

A member absent from LAYER_POLICY fails: new packages must declare their layer.

When this test flags a new violation, the default answer is to FIX it — move
the code to the right layer or invert the dependency (inject the value, expose
a public API on the lower package) — not to allowlist it. Widen LAYER_POLICY /
EXTRA_POLICY only for a deliberate architecture change, and add to
SANCTIONED_EXCEPTIONS only for known, tracked drift with a linked work item.
The exception table is a ledger of debt being paid down, not an escape hatch.
"""

from __future__ import annotations

import ast
import re
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PACKAGES_DIR = REPO_ROOT / "packages"

# Foundation: allowed as a dependency of ANY member.
FOUNDATION = {"workspace-io"}

# dist name -> allowed in-repo deps beyond FOUNDATION (base sets only; extras
# live in EXTRA_POLICY, sanctioned drift in SANCTIONED_EXCEPTIONS).
LAYER_POLICY: dict[str, set[str]] = {
    "workspace-io": set(),
    "source-parser": set(),
    "model-adapter": set(),
    "subagent-runtime": set(),
    "graph-io": {"source-parser"},  # its parsing engine, not a peer io package
    "wiki-io": set(),
    "work-io": set(),
    "guidance-io": set(),
    "graph-wiki-core": {"graph-io", "wiki-io", "work-io", "guidance-io"},
    "graph-wiki-cli": {"graph-wiki-core"},
    "graph-wiki-mcp": {"graph-wiki-core"},
    "eval-harness": {"graph-wiki-core"},
    "subagent-cli": {"graph-wiki-core"},
    "claude-code-evals": {"model-adapter"},  # standalone leaf
}

# dist name -> extra name -> additional in-repo deps allowed in that extra.
EXTRA_POLICY: dict[str, dict[str, set[str]]] = {
    "graph-wiki-core": {"bedrock": {"model-adapter", "subagent-runtime"}},
}

# Known, tracked drift only — removing an entry when its item lands is a one-line diff.
SANCTIONED_EXCEPTIONS: dict[str, set[str]] = {
    # graph-wiki-cli + subagent-cli: surface bypasses sanctioned pending
    # 2026-07-05-thin-the-delivery-surfaces-route-graph-wiki-cli-and-subagent-cli-through-graph-wiki-core.
    "graph-wiki-cli": {"graph-io", "wiki-io", "work-io", "subagent-runtime"},
    "subagent-cli": {"graph-io", "wiki-io", "guidance-io", "model-adapter", "subagent-runtime"},
    # graph-wiki-mcp: same surface-bypass shape (server.py imports graph_io.open_reader and the
    # PRIVATE wiki_io._workspace.resolve_wiki_and_repo); no dedicated work item filed yet —
    # file one before removing this entry.
    "graph-wiki-mcp": {"graph-io", "wiki-io"},
    # eval-harness: same surface-bypass shape; no dedicated work item filed yet —
    # file one before removing this entry.
    "eval-harness": {"graph-io", "model-adapter", "subagent-runtime"},
}

_REQ_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")

# Shared remediation suffix so every violation message says what to do next.
_REMEDY = (
    " — either remove the edge, or if intentional extend LAYER_POLICY/EXTRA_POLICY"
    " (architecture change) or SANCTIONED_EXCEPTIONS (known drift; needs a linked work item)"
)


def _members() -> dict[str, Path]:
    return {p.name: p for p in sorted(PACKAGES_DIR.iterdir()) if (p / "pyproject.toml").is_file()}


def _req_dist(req: str) -> str:
    """Normalize a requirement string to its dist name (strips extras/version)."""
    m = _REQ_NAME.match(req)
    assert m, f"unparseable requirement: {req!r}"
    return m.group(1).lower()


def _allowed(dist: str) -> set[str]:
    assert dist in LAYER_POLICY, (
        f"package {dist!r} is not declared in LAYER_POLICY — new workspace members must declare their layer"
    )
    return LAYER_POLICY[dist] | FOUNDATION | SANCTIONED_EXCEPTIONS.get(dist, set())


def _import_to_dist() -> dict[str, str]:
    """Derive the import-name -> dist-name mapping from packages/*/src/<import_name>.

    Only regular package dirs (`src/<name>/__init__.py`) are mapped; a single-file
    `src/<name>.py` module or a namespace package would be skipped.
    """
    mapping: dict[str, str] = {}
    for dist, pkg_dir in _members().items():
        src = pkg_dir / "src"
        if not src.is_dir():
            continue
        for child in src.iterdir():
            if child.is_dir() and (child / "__init__.py").is_file():
                mapping[child.name] = dist
    return mapping


def _top_level_imports(tree: ast.AST) -> set[str]:
    """Top-level module names imported anywhere in the tree, at any scope."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return names


def test_every_member_has_a_declared_layer() -> None:
    members = set(_members())
    undeclared = members - set(LAYER_POLICY)
    stale = set(LAYER_POLICY) - members
    assert not undeclared, f"packages missing from LAYER_POLICY: {sorted(undeclared)}"
    assert not stale, f"LAYER_POLICY entries with no package on disk: {sorted(stale)}"


def test_declared_deps_respect_layer_policy() -> None:
    members = _members()
    in_repo = set(members)
    violations: list[str] = []
    for dist, pkg_dir in members.items():
        project = tomllib.loads((pkg_dir / "pyproject.toml").read_text(encoding="utf-8"))["project"]
        allowed = _allowed(dist)
        base = {_req_dist(r) for r in project.get("dependencies", [])} & in_repo
        violations.extend(
            f"{dist}: declared dep {dep!r} violates the layer policy{_REMEDY}" for dep in sorted(base - allowed)
        )
        for extra, reqs in project.get("optional-dependencies", {}).items():
            extra_allowed = allowed | EXTRA_POLICY.get(dist, {}).get(extra, set())
            extra_deps = {_req_dist(r) for r in reqs} & in_repo
            violations.extend(
                f"{dist}[{extra}]: declared dep {dep!r} violates the layer policy{_REMEDY}"
                for dep in sorted(extra_deps - extra_allowed)
            )
    assert not violations, "\n".join(violations)


def test_src_imports_respect_layer_policy() -> None:
    members = _members()
    import_map = _import_to_dist()
    violations: list[str] = []
    for dist, pkg_dir in members.items():
        # The AST check can't see the base/extra split — fold extras in; the
        # base-closure import test owns module-scope importability.
        allowed = _allowed(dist)
        for extra_set in EXTRA_POLICY.get(dist, {}).values():
            allowed |= extra_set
        src = pkg_dir / "src"
        if not src.is_dir():
            continue
        for py in sorted(src.rglob("*.py")):
            if "__pycache__" in py.parts:
                continue
            tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
            for top in sorted(_top_level_imports(tree)):
                dep = import_map.get(top)
                if dep is None or dep == dist:
                    continue
                if dep not in allowed:
                    violations.append(
                        f"{dist}: {py.relative_to(REPO_ROOT)} imports {top!r} ({dep})"
                        f" — violates the layer policy{_REMEDY}"
                    )
    assert not violations, "\n".join(violations)
