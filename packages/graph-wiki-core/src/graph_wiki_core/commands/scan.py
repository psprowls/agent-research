from __future__ import annotations

"""Scan command — build the code graph, write one page per admitted entity.

Public API:
    ScanResult                          — dataclass with state_gate + entity result fields
    build_stub_prompt(pkg)              — human message used by build_entity_narrative_prompt
                                          callers and downstream eval harnesses
    build_entity_narrative_prompt(...)  — (system, human) for the narrator LLM (Phase 45 D-05)
    run_scan(workspace_path, ...)       — end-to-end scan pipeline (Step 9a write_entities +
                                          Step 9b narrator fan-out + Step 12 dual-writer indexes)
"""

import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import frontmatter
from graph_io import exit_codes, queries
from graph_io.store import GraphNotInitializedError, read_only_connect
from langchain_core.messages import HumanMessage, SystemMessage
# Bedrock fan-out stack — imported only for the narrated path (narrate=True).
# Guarded so the plugin's Claude branch (narrate=False) runs without these
# workspace members installed. When absent, the narrator/file-describer blocks
# are unreachable (gated on `narrate`), so the None bindings are never called.
try:
    from model_adapter.loader import load_role_config, make_llm
    from subagent_runtime.pool import FanOutResult, SubagentPool, TaskResult
except ImportError:  # pragma: no cover — exercised by the lazy-import test via reload
    load_role_config = make_llm = None  # type: ignore[assignment]
    SubagentPool = TaskResult = FanOutResult = None  # type: ignore[assignment]
from wiki_io._workspace import resolve_wiki_and_repo
from wiki_io.append_log import append_log
from wiki_io.entity_writer import (
    ADMITTED_KINDS,
    _compute_collision_set,
    _extract_file_map_descriptions,
    _kind_list_fns,
    fill_file_map_descriptions,
    file_map_todo_paths,
    inject_file_map,
    inject_narrative,
    scanner_frontmatter_for_node,
    short_filename,
    write_entities,
)
from wiki_io.index_generator import generate_index
from wiki_io.lint.common import FILE_MAP_SECTION_RE
from wiki_io.scan_monorepo import (
    build_dir_file_map,
    build_file_map,
    compute_state_gate,
)
from wiki_io.backlink_index import regenerate_referenced_in_wiki
from wiki_io.update_index import update_index
from workspace_io.paths import graph_dir

from graph_wiki_core.commands.graph import run_build as _cg_run_build
from graph_wiki_core.prompts.file_describer import FILE_DESCRIBER_SYSTEM

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Phase 39 — graph-io integration helpers
# ---------------------------------------------------------------------------


class ScanAbortedError(RuntimeError):
    """Raised when run_scan() must hard-abort because `cg update` failed with
    a non-recoverable runtime error (D-07).

    Carries the cg exit_code and any stderr the cg layer produced so callers
    (CLI / MCP tool) can surface a meaningful diagnostic without re-running.
    """

    def __init__(self, exit_code: int, stderr: str) -> None:
        self.exit_code = exit_code
        self.stderr = stderr
        super().__init__(
            f"cg update failed (exit_code={exit_code}); scan aborted. "
            f"stderr: {stderr.strip() or '<empty>'}"
        )


# D-08 init-failure detection: when `cg update` returns GENERIC and stderr matches
# one of these substrings, we treat it as a filesystem init failure (permission/disk)
# rather than a runtime data-correctness failure. Conservative — false positives
# would graceful-fallback on a runtime error; false negatives would hard-abort on
# an unusual init failure. Both are safe-side per Phase 39 RESEARCH §11.
_INIT_FAILURE_STDERR_PATTERNS = (
    "Permission denied",
    "Read-only file system",
    "No space left on device",
    "Errno 13",
    "Errno 28",
    "Errno 30",
)


def _is_init_failure_stderr(stderr: str) -> bool:
    """Return True if `stderr` matches a known init-failure pattern (D-08)."""
    return any(p in stderr for p in _INIT_FAILURE_STDERR_PATTERNS)


def _snapshot_file_map_descriptions(wiki: Path) -> dict[str, dict[str, str]]:
    """Snapshot filled File-map descriptions from existing entity pages, keyed
    by entity URI, BEFORE ``write_entities`` resets page bodies to template.

    Returns ``{uri: {package_root_path: description}}`` containing only rows
    whose Description cell is filled (non-placeholder). Pages without a uri,
    without a `## File map` section, or with no filled rows are omitted.

    This is the durability mechanism for expensive code-reader descriptions:
    ``write_entities`` re-renders updated pages from the template (wiping the
    injected File-map body), so the prior descriptions must be captured here
    and merged back in by ``inject_file_map(preserved=...)``.
    """
    snapshot: dict[str, dict[str, str]] = {}
    entities_dir = wiki / "entities"
    if not entities_dir.is_dir():
        return snapshot
    for page_path in entities_dir.glob("*.md"):
        try:
            post = frontmatter.load(page_path)
        except Exception:  # noqa: BLE001 — a malformed page must not abort scan
            continue
        uri = post.metadata.get("uri")
        if not uri:
            continue
        section = FILE_MAP_SECTION_RE.search(post.content)
        if not section:
            continue
        pkg_name = section.group(1).strip()
        descs = _extract_file_map_descriptions(section.group(2), pkg_name)
        if descs:
            snapshot[uri] = descs
    return snapshot


# ---------------------------------------------------------------------------
# Local helper: pick_representative
# ---------------------------------------------------------------------------


def pick_representative(pkg_path: Path, entries: list[Path] | None = None) -> list[Path]:
    """Return up to 3 representative source files from a package directory.

    Priority order:
    1. Entry point files (main.py, __init__.py, index.ts, index.js, lib.rs, mod.rs)
    2. Files in src/ or lib/ directories
    3. Any other tracked source files (non-test, non-config)

    If entries is None, walk the package directory directly.
    Returns at most 3 paths.
    """
    if entries is None:
        try:
            entries = list(pkg_path.rglob("*"))
        except OSError:
            return []

    _ENTRY_NAMES = {"main.py", "__init__.py", "index.ts", "index.js", "lib.rs", "mod.rs", "main.ts", "main.js"}
    _SOURCE_EXTS = {".py", ".ts", ".js", ".rs", ".go", ".java", ".kt"}
    _SKIP_DIRS = {"node_modules", ".git", ".venv", "__pycache__", "dist", "build", ".next"}
    _SKIP_PATTERNS = {"test", "spec", "fixture", "mock"}

    def _is_source(p: Path) -> bool:
        # Skip non-files
        if not p.is_file():
            return False
        # Skip files in skippable dirs
        if any(part in _SKIP_DIRS for part in p.parts):
            return False
        # Skip test/fixture files
        name_lower = p.name.lower()
        if any(pat in name_lower for pat in _SKIP_PATTERNS):
            return False
        return p.suffix in _SOURCE_EXTS

    source_files = [p for p in entries if _is_source(p)]

    # Priority 1: entry points
    entry_points = [p for p in source_files if p.name in _ENTRY_NAMES]

    # Priority 2: files in src/ or lib/
    src_files = [p for p in source_files if any(part in {"src", "lib"} for part in p.parts) and p not in entry_points]

    # Combine and deduplicate up to 3
    candidates = entry_points + src_files + [p for p in source_files if p not in entry_points and p not in src_files]
    return candidates[:3]

# ---------------------------------------------------------------------------
# ScanResult dataclass
# ---------------------------------------------------------------------------


@dataclass
class ScanResult:
    """Result of a run_scan() call.

    Fields:
        state_gate:        Dict from compute_state_gate() — {allowed, reason, head_commit}.
        entities_created:  URIs of entity pages newly written this scan (Phase 45 D-15).
        entities_updated:  URIs of entity pages whose frontmatter changed this scan.
        entities_deleted:  URIs of entity pages hard-deleted by `write_entities` (vanished from graph).
        entities_narrated: URIs that received a successful narrator body injection.
        entity_errors:     repr() of EntityWriteError + narrator failure messages,
                           accumulated for partial-success reporting.
    """

    state_gate: dict = field(default_factory=dict)
    # Phase 45 D-15: URI-keyed entity reporting.
    entities_created: list[str] = field(default_factory=list)
    entities_updated: list[str] = field(default_factory=list)
    entities_deleted: list[str] = field(default_factory=list)
    entities_narrated: list[str] = field(default_factory=list)
    entity_errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helper: build_stub_prompt
# ---------------------------------------------------------------------------


def build_stub_prompt(pkg: dict, no_file_map: bool = False, repo_root: Path | None = None) -> str:
    """Return the human message text for the scanner LLM.

    Includes package metadata dict, repo-relative path, and up to 3 sampled
    file snippets via pick_representative(). File snippets are capped at 800
    chars each to stay within the 500-token scanner budget.

    Args:
        pkg:        Package metadata dict (name/path/type/language/...).
        no_file_map: Skip file_map section if True.
        repo_root:  Absolute path to the repo root. When provided, resolves
                    pkg['path'] against repo_root instead of cwd so file
                    snippets work correctly regardless of the process's cwd.
    """
    lines: list[str] = [
        f"Package name: {pkg.get('name', 'unknown')}",
        f"Path in repo: {pkg.get('path', 'unknown')}",
        f"Type: {pkg.get('type', 'unknown')}",
        f"Language: {pkg.get('language', 'unknown')}",
        f"Version: {pkg.get('version') or 'unknown'}",
        f"Exports: {pkg.get('exports') or []}",
        f"Depends on (workspace): {pkg.get('depends_on') or []}",
        "",
    ]

    # Attach file_map if it was pre-computed
    if not no_file_map and pkg.get("file_map"):
        lines.append("File listing (for reference):")
        lines.append(pkg["file_map"][:1000])
        lines.append("")

    # Representative file snippets (up to 3)
    pkg_path_str = pkg.get("path")
    if pkg_path_str:
        try:
            if repo_root is not None:
                pkg_abs = (repo_root / pkg_path_str).resolve()
            else:
                pkg_abs = Path(pkg_path_str).resolve()
            representatives = pick_representative(pkg_abs)
            for file_path in representatives[:3]:
                try:
                    snippet = file_path.read_text(encoding="utf-8", errors="replace")
                    if len(snippet) > 800:
                        snippet = snippet[:800] + "\n[TRUNCATED]"
                    lines.append(f"--- {file_path.name} ---")
                    lines.append(snippet)
                    lines.append("")
                except OSError:
                    pass
        except Exception:
            pass  # pick_representative failures are non-fatal

    lines.append("Write the vault stub page for this package. Do NOT include a ## File map section.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Phase 45: build_entity_narrative_prompt — prose-only generator for entity pages
# ---------------------------------------------------------------------------


# Human-readable labels for each scanner-owned relation key. Used by the
# narrator prompt to render relations as natural prose hints instead of YAML.
_NARRATIVE_RELATION_LABELS: dict[str, str] = {
    "depends_on":      "Depends on",
    "test_suites":     "Test suites",
    "entry_points":    "Entry points",
    "domains":         "Domains",
    "parent_domain":   "Parent domain",
    "sub_domains":     "Sub-domains",
    "packages":        "Packages",
    "tested_packages": "Tested packages",
    "used_by":         "Used by",
    "members":         "Members",
    "ecosystem":       "Ecosystem",
    "language":        "Language",
    "version":         "Version",
    "suite_kind":      "Suite kind",
    "file_count":      "File count",
    "package_count":   "Package count",
    "versions_in_use": "Versions in use",
}


def build_entity_narrative_prompt(
    node, kind: str, file_map_text: str, relations: dict,
) -> tuple[str, str]:
    """Return (system_message, human_message) for the narrator LLM (Phase 45 D-05).

    The narrator generates ONLY the prose body that lives between the
    `## Narrative` heading and the next H2 on an entity page. Frontmatter,
    headings, and all other page structure are scanner-owned and MUST NOT
    appear in the model's output.

    Args:
        node:           graph_io.queries.NodeRecord (has `.name`, `.attrs["uri"]`).
        kind:           One of ADMITTED_KINDS.
        file_map_text:  Optional file listing (non-empty only for `package` kinds).
        relations:      Per-kind relation dict from `scanner_frontmatter_for_node`,
                        with `uri` and `kind` already stripped or harmlessly ignored.

    Returns:
        A `(system, human)` string pair ready to wrap in SystemMessage + HumanMessage.
    """
    system = (
        "You write the narrative body of a graph-derived wiki entity page. "
        "Output ONLY prose: no YAML frontmatter, no H1, no H2 headings, no fenced "
        "code blocks unless the prose specifically describes code. Your output "
        "will be injected between the page's `## Narrative` heading and the next "
        "H2 — write only what belongs there.\n\n"
        "Tone: factual, concise, technical. Length: 2-4 short paragraphs. Cite "
        "the entity's relations naturally (e.g. 'It depends on `pkg:foo`...'); "
        "do not enumerate them in a list."
    )

    uri = node.attrs.get("uri", "") if isinstance(node.attrs, dict) else ""
    lines: list[str] = [
        f"Entity URI: {uri}",
        f"Kind: {kind}",
        f"Name: {node.name}",
    ]

    for key, label in _NARRATIVE_RELATION_LABELS.items():
        if key not in relations:
            continue
        val = relations[key]
        if val is None or val == [] or val == "":
            continue
        if isinstance(val, list):
            rendered = ", ".join(str(v) for v in val)
        else:
            rendered = str(val)
        lines.append(f"{label}: {rendered}")

    if kind == "package" and file_map_text:
        lines.append("")
        lines.append("File listing (for reference; do NOT include this in your output):")
        lines.append(file_map_text[:1500])

    lines.append("")
    lines.append("Write the narrative body for this page (prose only).")

    return system, "\n".join(lines)


# ---------------------------------------------------------------------------
# Phase: file-map description fan-out (code-reader role) — prompt + parser
# ---------------------------------------------------------------------------


def build_file_describer_prompt(
    pkg: dict, todo_paths: list[str], repo_root: Path | None = None
) -> tuple[str, str]:
    """Return (system, human) for the file-map description LLM (code_reader role).

    The human message carries package metadata, the list of paths still needing
    a description (the model must key its JSON to these verbatim), and up to 3
    representative source snippets (capped per file) for grounding — mirroring
    `build_stub_prompt`'s snippet sampling.

    Args:
        pkg:       Package metadata dict (built from the graph node in Step 10c).
        todo_paths: Package-root paths whose Description cell is still `— TODO`.
        repo_root: Absolute repo root; `pkg['path']` is resolved against it so
                   snippet reads work regardless of cwd.
    """
    system = FILE_DESCRIBER_SYSTEM
    lines: list[str] = [
        f"Package name: {pkg.get('name', 'unknown')}",
        f"Path in repo: {pkg.get('path', 'unknown')}",
        f"Type: {pkg.get('type', 'unknown')}",
        f"Language: {pkg.get('language', 'unknown')}",
        "",
        "Paths needing a description (use these exact strings as JSON keys):",
    ]
    for p in todo_paths:
        lines.append(f"- {p}")
    lines.append("")

    pkg_path_str = pkg.get("path")
    if pkg_path_str:
        try:
            if repo_root is not None:
                pkg_abs = (repo_root / pkg_path_str).resolve()
            else:
                pkg_abs = Path(pkg_path_str).resolve()
            representatives = pick_representative(pkg_abs)
            if representatives:
                lines.append("Representative file snippets (for context):")
                for file_path in representatives[:3]:
                    try:
                        snippet = file_path.read_text(encoding="utf-8", errors="replace")
                        if len(snippet) > 800:
                            snippet = snippet[:800] + "\n[TRUNCATED]"
                        lines.append(f"--- {file_path.name} ---")
                        lines.append(snippet)
                        lines.append("")
                    except OSError:
                        pass
        except Exception:
            pass  # snippet sampling is best-effort; metadata + paths suffice

    lines.append(
        "Return the JSON object mapping each describable path to its one-line description."
    )
    return system, "\n".join(lines)


def parse_file_describer_output(text: str) -> dict[str, str]:
    """Parse the describer LLM's response into a ``{path: description}`` dict.

    Tolerates a leading/trailing ```` ```json ```` fence and surrounding prose
    by extracting the first balanced ``{...}`` JSON object. Returns ``{}`` on
    any parse failure or non-object payload. Non-string keys/values are dropped;
    descriptions are stripped and collapsed to a single line.
    """
    if not text:
        return {}
    candidate = text.strip()
    # Strip a fenced code block if present.
    if candidate.startswith("```"):
        candidate = candidate.split("\n", 1)[-1]
        if candidate.rstrip().endswith("```"):
            candidate = candidate.rsplit("```", 1)[0]
    # Extract the first {...} object span.
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {}
    import json

    try:
        obj = json.loads(candidate[start : end + 1])
    except (ValueError, TypeError):
        return {}
    if not isinstance(obj, dict):
        return {}
    out: dict[str, str] = {}
    for key, val in obj.items():
        if not isinstance(key, str) or not isinstance(val, str):
            continue
        desc = " ".join(val.split()).strip()
        if key.strip() and desc:
            out[key.strip()] = desc
    return out


# ---------------------------------------------------------------------------
# Helper: _entity_page_path
# ---------------------------------------------------------------------------


def _entity_page_path(
    wiki: Path,
    kind: str,
    node: Any,
    uri: str,
    collision_set: frozenset[str],
) -> Path:
    """Resolve the ``entities/<stem>.md`` path for a graph node.

    Applies the suite-aware slug (``suite_kind`` + ``pkg_for_suite`` derived
    from ``attrs['path']``) for ``test_suite`` kinds, matching what
    ``write_entities`` produces; all other kinds use the plain prefix slug.
    """
    suite_kind: str | None = None
    pkg_for_suite: str | None = None
    if kind == "test_suite":
        attrs = node.attrs if isinstance(node.attrs, dict) else {}
        suite_kind = attrs.get("suite_kind") or None
        suite_path = attrs.get("path")
        if suite_path:
            pkg_for_suite = Path(suite_path).parent.name or None
    stem = short_filename(
        uri,
        collision_set,
        suite_kind=suite_kind,
        pkg_for_suite=pkg_for_suite,
    )
    return wiki / "entities" / f"{stem}.md"


# ---------------------------------------------------------------------------
# Public: run_scan
# ---------------------------------------------------------------------------


async def run_scan(
    workspace_path: Path | None = None,
    no_file_map: bool = False,
    max_depth: int = 3,
    repo_path: Path | None = None,
    model_override: str | None = None,
    narrate: bool = True,
) -> ScanResult:
    """End-to-end scan: graph build → entity writes → narrator fan-out → indexes.

    Steps:
        1. Resolve wiki and repo from workspace_path; run `cg update`, open conn.
        8. compute_state_gate(repo) → {allowed, reason, head_commit}.
        9a. write_entities — graph-driven entity pages.
        9b. narrator fan-out gated on needs_narrative.
        10. inject narrator prose + deterministic file maps + code-reader fan-out.
        12. generate_index + update_index + backlink regeneration.
        13. Final append_log summary.
        14. Return ScanResult.

    Args:
        workspace_path: Path to the wiki workspace root (None → env var / git heuristic).
        no_file_map:    Skip per-workspace file-map generation (faster on huge repos).
        max_depth:      Max directory depth for file map section headers.
        repo_path:      Override the monorepo root used for workspace discovery.
                        When supplied, replaces both the cwd fallback and any
                        repo returned by resolve_wiki_and_repo. Useful for tests
                        that point the scanner at a known-good package fixture
                        (the eval-harness divergence test uses this — see
                        packages/eval-harness/tests/eval_helpers.py).
        model_override: Bedrock model ID to use for the scanner role instead of
                        the default from models.toml. Used by the sweep runner
                        for single-role-swap evaluation (D-06).
        narrate:        When True (default), run the narrator and file-describer
                        Bedrock fan-outs that fill `## Narrative` bodies and
                        `— TODO` file-map descriptions. When False, skip both
                        fan-outs entirely (structural-only scan) — entity pages
                        keep their `## Narrative` placeholder and `— TODO` rows.
                        The plugin's Claude branch calls with narrate=False so the
                        scan needs neither model_adapter nor subagent_runtime.

    Returns:
        ScanResult with state_gate and the entities_* / entity_errors fields.
    """
    # Step 1: resolve wiki and repo
    wiki, resolved_repo = resolve_wiki_and_repo(workspace_path)
    if repo_path is not None:
        repo = repo_path.resolve()
    elif resolved_repo is not None:
        repo = resolved_repo
    else:
        repo = Path.cwd()

    # Phase 39 D-05: single read-only conn for graph queries; closed in finally
    conn = None
    try:
        # Phase 39 Step 1.5 (D-01/D-02/D-06/D-07/D-08): pre-scan cg update.
        # Use Phase 38's in-process helpers — full=False, no --trace, no --model.
        append_log(
            wiki,
            "scan",
            "cg update (incremental)",
            detail=None,
            silent=True,
            raise_exception=True,
        )
        # NOTE: run_build interprets `workspace` as the workspace ROOT (where
        # `.graph/code.db` is written), not the wiki directory. commands/graph.py
        # (`_resolve_paths` → `cfg.workspace`) and the librarian
        # (`graph_dir(wiki.parent)` in commands/query.py) both use the workspace
        # root. We follow that convention here so the post-update
        # `read_only_connect(graph_dir(wiki.parent) / "code.db")` finds the
        # DB the graph build just created. (The plan's must_have says
        # `workspace=wiki`; that is a plan-spec drift — passing `wiki` makes the
        # build write to `<wiki>/.graph/code.db` while the read path looks under
        # `<workspace>/.graph/code.db`, so the conn open would fall through
        # to the post-update NOT_INITIALIZED fallback every time. See Phase
        # 39 SUMMARY's deviations section.)
        #
        # Phase 59 (59-02b): migrated off the deleted _build_namespace/_capture_run
        # shim onto the typed run_build core. update.run is silent on success, so
        # _cg_stdout is always "" here (sanctioned by D-06).
        _workspace_root = wiki.parent
        _cg_exit, _cg_stdout, _cg_stderr = _cg_run_build(
            repo, _workspace_root, full=False
        )
        _graph_ready = False
        if _cg_exit == exit_codes.SUCCESS:
            append_log(
                wiki,
                "scan",
                "cg update complete: exit_code=0",
                detail=None,
                silent=True,
                raise_exception=True,
            )
            _graph_ready = True
        elif _cg_exit == exit_codes.GENERIC and _is_init_failure_stderr(_cg_stderr):
            # D-08 graceful fallback: init failure (permission/disk). One stderr line.
            reason = (
                _cg_stderr.strip().splitlines()[-1]
                if _cg_stderr.strip()
                else "unknown init failure"
            )
            sys.stderr.write(
                f"[NOT_INITIALIZED fallback: graph could not be initialized "
                f"({reason}); using path-based slugs]\n"
            )
            append_log(
                wiki,
                "scan",
                f"NOT_INITIALIZED fallback: {reason}",
                detail=None,
                silent=True,
                raise_exception=True,
            )
            _graph_ready = False
        else:
            # D-07 hard abort: any other non-success exit code or unrecognized GENERIC stderr.
            append_log(
                wiki,
                "scan",
                f"cg update failed: exit_code={_cg_exit}",
                detail=None,
                silent=True,
                raise_exception=True,
            )
            raise ScanAbortedError(exit_code=_cg_exit, stderr=_cg_stderr)

        # Phase 39 Step 1.6 (D-05): open the read-only graph conn ONCE on success.
        # wiki is workspace/wiki under the standard layout; .graph lives next to it
        # (mirrors the pattern in commands/query.py — librarian's graph-tools wiring).
        if _graph_ready:
            try:
                conn = read_only_connect(graph_dir(wiki.parent) / "code.db")
            except GraphNotInitializedError as exc:
                # Defensive: should not happen after a successful cg update,
                # but treat as a NOT_INITIALIZED-class fallback if it does.
                sys.stderr.write(
                    f"[NOT_INITIALIZED fallback: graph could not be initialized "
                    f"({exc}); using path-based slugs]\n"
                )
                append_log(
                    wiki,
                    "scan",
                    f"NOT_INITIALIZED fallback (post-update): {exc}",
                    detail=None,
                    silent=True,
                    raise_exception=True,
                )
                conn = None

        # Step 8: compute state gate
        state_gate = compute_state_gate(repo)

        # Phase 45 D-04: Step 9 splits into 9a (entity write) + 9b (narrator fan-out).
        # The legacy scanner fan-out for wiki/packages/<name>/<name>.md pages is
        # REMOVED in v1.8 — D-08 hard cutover. `model_override` is kept available
        # for future eval sweeps targeting the narrator role.
        entity_write_result = None
        narrator_result: FanOutResult | None = None

        # Snapshot prior File-map descriptions BEFORE write_entities re-renders
        # entity pages from template (which wipes the injected File-map body).
        # Keyed by URI so Step 10b can merge them back into the deterministic
        # block, preserving expensive code-reader descriptions across rescans.
        prior_file_map_descs: dict[str, dict[str, str]] = {}
        if conn is not None:
            prior_file_map_descs = _snapshot_file_map_descriptions(wiki)

        if conn is not None:
            # Step 9a: graph-driven entity page writes (Phase 43 write_entities).
            entity_write_result = write_entities(conn, wiki, ADMITTED_KINDS)
            append_log(
                wiki,
                "scan",
                (
                    f"entities: +{len(entity_write_result.created)} "
                    f"~{len(entity_write_result.updated)} "
                    f"-{len(entity_write_result.deleted)} "
                    f"(needs_narrative: {len(entity_write_result.needs_narrative)})"
                ),
                detail=None,
                silent=True,
                raise_exception=True,
            )

            # Step 9b: narrator fan-out gated on needs_narrative.
            narrator_items: list[tuple[str, str, Any]] = []
            if narrate and entity_write_result.needs_narrative:
                list_fns = _kind_list_fns()
                wanted = set(entity_write_result.needs_narrative)
                for kind in sorted(ADMITTED_KINDS):
                    list_fn = list_fns.get(kind)
                    if list_fn is None:
                        continue
                    for node in list_fn(conn):
                        if not isinstance(node.attrs, dict):
                            continue
                        node_uri = node.attrs.get("uri")
                        if node_uri and node_uri in wanted:
                            narrator_items.append((node_uri, kind, node))

            if narrator_items:
                narrator_cfg = load_role_config("narrator")
                narrator_llm = make_llm("narrator", model_override=model_override)
                narrator_pool = SubagentPool(
                    trace_dir=wiki / ".graph-wiki" / "traces"
                )

                async def generate_narrative(
                    item: tuple[str, str, Any],
                ) -> TaskResult:
                    uri_inner, kind_inner, node_inner = item
                    relations = scanner_frontmatter_for_node(conn, kind_inner, node_inner)
                    relations_for_prompt = {
                        k: v for k, v in relations.items() if k not in ("uri", "kind")
                    }
                    # File maps are graph-sourced (Step 10b); the narrator no
                    # longer receives a per-workspace file-map hint.
                    file_map = ""
                    system_msg, human_msg = build_entity_narrative_prompt(
                        node_inner, kind_inner, file_map, relations_for_prompt,
                    )
                    msgs = [
                        SystemMessage(content=system_msg),
                        HumanMessage(content=human_msg),
                    ]
                    resp = await narrator_llm.ainvoke(msgs)
                    return TaskResult(value=resp.content, response=resp)

                narrator_result = await narrator_pool.run_all(
                    items=narrator_items,
                    task=generate_narrative,
                    role="narrator",
                    model_id=narrator_cfg["model_id"],
                    max_concurrency=narrator_cfg["max_concurrency"],
                )

        # Phase 45 D-07/D-08: Step 10 — inject narrator prose into entity pages.
        # The legacy `wiki/packages/<name>/<name>.md` write block is REMOVED (D-08
        # hard cutover — only entity pages are written from Phase 45 onward).
        # Phase 53 D-05: derive entity filenames via `short_filename` (mirroring
        # `write_entities`) so the inject-narrative path lines up with the file
        # that `write_entities` just produced.
        entities_narrated: list[str] = []
        narrator_errors: list[str] = []
        if narrator_result is not None:
            inject_collision_set = _compute_collision_set(
                conn, ADMITTED_KINDS, _kind_list_fns(),
            )

            for item, prose in narrator_result.successes:
                uri_inner, kind_inner, node_inner = item
                entity_page_path = _entity_page_path(
                    wiki, kind_inner, node_inner, uri_inner, inject_collision_set,
                )
                try:
                    inject_narrative(entity_page_path, prose)
                    entities_narrated.append(uri_inner)
                except Exception as inject_exc:  # noqa: BLE001 — partial-success
                    narrator_errors.append(
                        f"{uri_inner}: inject_narrative failed: {inject_exc!r}"
                    )
            for err in narrator_result.errors:
                uri_inner, _kind_inner, _node_inner = err.item
                narrator_errors.append(f"{uri_inner}: {err.exception!r}")

        # Step 10b: deterministic File-map injection (faithful port of the
        # plugin scanner-agent step). For every `package`/`app` entity page that
        # write_entities (re)wrote this scan — created or updated, i.e. whose
        # `## File map` section was just reset to the empty template — replace
        # that section with the deterministic `build_file_map` block (path +
        # kind rows; Description stays `— TODO`, filled by a later ingest pass).
        # `unchanged` pages are left untouched so prior ingest-filled
        # descriptions survive no-op scans. Skipped entirely when no_file_map
        # is True (guard on the `if refreshed and any(fm_list_fns)` branch).
        entities_file_mapped: list[str] = []
        file_map_errors: list[str] = []
        describer_filled: list[str] = []
        describer_errors: list[str] = []
        # (uri, node, page_path) for each package/app whose File map was injected
        # this scan — Step 10c uses these to fill remaining `— TODO` rows.
        file_mapped_pages: list[tuple[str, Any, Path]] = []
        if entity_write_result is not None and conn is not None:
            refreshed = set(entity_write_result.created) | set(
                entity_write_result.updated
            )
            list_fns = _kind_list_fns()
            # Collision set shared by the package/app and test-suite branches.
            fm_collision_set = (
                _compute_collision_set(conn, ADMITTED_KINDS, list_fns)
                if refreshed
                else frozenset()
            )
            fm_list_fns = [list_fns.get("package"), list_fns.get("app")]
            if refreshed and any(fm_list_fns) and not no_file_map:
                fm_nodes = [n for fn in fm_list_fns if fn for n in fn(conn)]
                for node in fm_nodes:
                    if not isinstance(node.attrs, dict):
                        continue
                    node_uri = node.attrs.get("uri")
                    if not node_uri or node_uri not in refreshed:
                        continue
                    node_path = node.path
                    if not node_path:
                        continue
                    file_map = build_file_map(repo / node_path, max_depth=max_depth)
                    if not file_map:
                        continue
                    slug = short_filename(node_uri, fm_collision_set)
                    fm_page_path = wiki / "entities" / f"{slug}.md"
                    try:
                        inject_file_map(
                            fm_page_path,
                            file_map,
                            preserved=prior_file_map_descs.get(node_uri),
                        )
                        entities_file_mapped.append(node_uri)
                        file_mapped_pages.append((node_uri, node, fm_page_path))
                    except Exception as fm_exc:  # noqa: BLE001 — partial-success
                        file_map_errors.append(
                            f"{node_uri}: inject_file_map failed: {fm_exc!r}"
                        )
            # Step 10b-ts: test-suite File-map injection. Mirrors Step 10b but
            # for test_suite entity pages — the suite map starts at the suite
            # root (node.attrs["path"]) and is UNPARTITIONED (every tracked file
            # under the root). Reuses the shared collision set and the same
            # snapshot→merge durability path (preserved=...). Appends each
            # injected page to file_mapped_pages so Step 10c fills its TODO rows.
            if refreshed:
                for node in queries.list_test_suites(conn):
                    if not isinstance(node.attrs, dict):
                        continue
                    suite_uri = node.attrs.get("uri")
                    if not suite_uri or suite_uri not in refreshed:
                        continue
                    suite_path = node.attrs.get("path")
                    if not suite_path:
                        continue
                    block = build_dir_file_map(repo / suite_path, max_depth=max_depth)
                    if not block:
                        continue
                    ts_page_path = _entity_page_path(
                        wiki, "test_suite", node, suite_uri, fm_collision_set,
                    )
                    try:
                        inject_file_map(
                            ts_page_path,
                            block,
                            preserved=prior_file_map_descs.get(suite_uri),
                        )
                        entities_file_mapped.append(suite_uri)
                        file_mapped_pages.append((suite_uri, node, ts_page_path))
                    except Exception as fm_exc:  # noqa: BLE001 — partial-success
                        file_map_errors.append(
                            f"{suite_uri}: inject_file_map failed: {fm_exc!r}"
                        )
            if entities_file_mapped or file_map_errors:
                append_log(
                    wiki,
                    "scan",
                    (
                        f"file maps injected: {len(entities_file_mapped)} "
                        f"(errors: {len(file_map_errors)})"
                    ),
                    detail=None,
                    silent=True,
                    raise_exception=True,
                )

        # Step 10c: code-reader fan-out to fill remaining `— TODO` Description
        # cells. For each just-file-mapped package that still has unfilled file
        # rows, dispatch a code_reader-role subagent that reads representative
        # files and returns {path: one-line description}; we fill ONLY the
        # unfilled cells (preserved/human descriptions are never overwritten).
        # Steady-state cost is zero: once a package's rows are all filled (and
        # preserved across rescans by Step 10b's merge), it has no TODO paths
        # and is skipped — no model call.
        if narrate and file_mapped_pages and conn is not None:
            # Build (uri, ws_dict, page_path, todo_paths) for packages with work.
            describer_items: list[tuple[str, dict, Path, list[str]]] = []
            for node_uri, node, page_path in file_mapped_pages:
                todo_paths = file_map_todo_paths(page_path)
                if not todo_paths:
                    continue
                attrs = node.attrs if isinstance(node.attrs, dict) else {}
                ws_dict = {
                    "name": node.name,
                    "path": node.path or attrs.get("path"),
                    "type": node.kind,
                    "language": attrs.get("language", "unknown"),
                }
                describer_items.append((node_uri, ws_dict, page_path, todo_paths))

            if describer_items:
                describer_cfg = load_role_config("code_reader")
                describer_llm = make_llm("code_reader")
                describer_pool = SubagentPool(
                    trace_dir=wiki / ".graph-wiki" / "traces"
                )

                async def describe_files(
                    item: tuple[str, dict, Path, list[str]],
                ) -> TaskResult:
                    _uri, ws_dict_inner, _page, todo_inner = item
                    system_msg, human_msg = build_file_describer_prompt(
                        ws_dict_inner, todo_inner, repo_root=repo
                    )
                    resp = await describer_llm.ainvoke(
                        [
                            SystemMessage(content=system_msg),
                            HumanMessage(content=human_msg),
                        ]
                    )
                    return TaskResult(value=resp.content, response=resp)

                describer_result = await describer_pool.run_all(
                    items=describer_items,
                    task=describe_files,
                    role="code_reader",
                    model_id=describer_cfg["model_id"],
                    max_concurrency=describer_cfg["max_concurrency"],
                )

                for item, value in describer_result.successes:
                    uri_inner, _ws, page_path, _todo = item
                    descriptions = parse_file_describer_output(value)
                    if not descriptions:
                        continue
                    try:
                        n_filled = fill_file_map_descriptions(page_path, descriptions)
                        if n_filled:
                            describer_filled.append(f"{uri_inner}: {n_filled}")
                    except Exception as fill_exc:  # noqa: BLE001 — partial-success
                        describer_errors.append(
                            f"{uri_inner}: fill_file_map_descriptions failed: {fill_exc!r}"
                        )
                for err in describer_result.errors:
                    uri_inner = err.item[0]
                    describer_errors.append(f"{uri_inner}: {err.exception!r}")

                if describer_filled or describer_errors:
                    append_log(
                        wiki,
                        "scan",
                        (
                            f"file descriptions filled: {len(describer_filled)} "
                            f"entity(s) (errors: {len(describer_errors)})"
                        ),
                        detail=None,
                        silent=True,
                        raise_exception=True,
                    )

        # Step 12: regenerate indexes (Phase 45 D-01).
        # Order: graph-driven wiki/index.md → per-folder sub-indexes.
        if conn is not None:
            # generate_index is read-only on the graph; raises on failure (Phase 44 D-19).
            index_result = generate_index(conn, wiki)
            append_log(
                wiki,
                "scan",
                (
                    f"index: wiki/index.md changed={index_result.changed} "
                    f"bytes={index_result.bytes_written}"
                ),
                detail=None,
                silent=True,
                raise_exception=True,
            )
        try:
            update_index(wiki)  # per-folder */index.md sub-indexes only (Phase 45 D-02)
        except Exception as exc:
            logger.warning("update_index failed (non-fatal): %s", exc)

        # Step 12b (Slice 4): regenerate the scanner-owned `## Referenced in
        # wiki` backlink section on every entity page from the [[entities/...]]
        # forward-links in preserved pages. Pure Python, graph-independent —
        # runs in both narrated and narrate=False scans.
        try:
            backlinked = regenerate_referenced_in_wiki(wiki)
            append_log(
                wiki,
                "scan",
                f"referenced-in-wiki: {len(backlinked)} entity page(s)",
                detail=None,
                silent=True,
                raise_exception=True,
            )
        except Exception as exc:  # noqa: BLE001 — non-fatal post-processing
            logger.warning(
                "regenerate_referenced_in_wiki failed (non-fatal): %s", exc
            )

        # Step 13: final log entry — entity counters.
        entity_create_count = len(entity_write_result.created) if entity_write_result else 0
        entity_update_count = len(entity_write_result.updated) if entity_write_result else 0
        entity_delete_count = len(entity_write_result.deleted) if entity_write_result else 0
        needs_count = len(entity_write_result.needs_narrative) if entity_write_result else 0
        narrated_count = len(entities_narrated)
        append_log(
            wiki,
            "scan",
            (
                f"scan complete: entities +{entity_create_count} ~{entity_update_count} "
                f"-{entity_delete_count}  (narrated: {narrated_count} of {needs_count})"
            ),
            detail=None,
            silent=True,
            raise_exception=True,
        )

        entity_write_errors: list[str] = []
        if entity_write_result is not None:
            entity_write_errors = [repr(e) for e in entity_write_result.errors]

        return ScanResult(
            state_gate=state_gate,
            entities_created=sorted(entity_write_result.created) if entity_write_result else [],
            entities_updated=sorted(entity_write_result.updated) if entity_write_result else [],
            entities_deleted=sorted(entity_write_result.deleted) if entity_write_result else [],
            entities_narrated=sorted(entities_narrated),
            entity_errors=(
                entity_write_errors
                + narrator_errors
                + file_map_errors
                + describer_errors
            ),
        )
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass  # closing a read-only conn should not raise; defensive
