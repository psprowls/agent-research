from __future__ import annotations

"""Scan command — walk a monorepo, diff against vault, fan-out scanner subagents.

Public API:
    ScanResult              — dataclass: added, updated, deleted, renamed, errors, state_gate
    build_stub_prompt(pkg)  — human message: package metadata + representative file snippets
    run_scan(workspace_path, no_file_map, max_depth)  — end-to-end scan pipeline

The scanner system prompt is constructed inline via
`build_scanner_system(project_context=...)` where `project_context` is the
rendered output of `render_project_context(wiki)` — see CTX-03.
"""

import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path

from graph_io import exit_codes, queries
from graph_io.store import GraphNotInitializedError, read_only_connect
from langchain_aws import ChatBedrockConverse
from langchain_core.messages import HumanMessage, SystemMessage
from model_adapter.loader import load_role_config, make_llm
from subagent_runtime.pool import FanOutResult, SubagentPool, TaskResult
from wiki_io._workspace import resolve_wiki_and_repo
from wiki_io.append_log import append_log
from wiki_io.layout_io import read_layout
from wiki_io.scan_monorepo import (
    _load_existing_pages,
    _wiki_relative_path_for,
    attach_changed_files,
    build_file_map,
    compute_diff,
    compute_state_gate,
    discover_workspaces,
    regenerate_dependencies_index,
)
from wiki_io.update_index import update_index
from workspace_io.paths import graph_dir

from graph_wiki_agent.commands.graph import _build_namespace, _capture_run, ops_update
from graph_wiki_agent.prompts.project_context import render_project_context
from graph_wiki_agent.prompts.scanner import build_scanner_system

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


def _query_package_domains(conn) -> dict[str, str]:
    """Return {package_name: domain_name} for every package with a
    `belongs_to_domain` edge.

    Single SQL round trip. Packages with no domain edge are absent from the
    returned dict (caller uses dict.get with the filesystem-derived default).
    """
    rows = conn.execute(
        "SELECT p.name, d.name FROM nodes p "
        "JOIN edges e ON e.src = p.id AND e.kind='belongs_to_domain' "
        "JOIN nodes d ON e.dst = d.id "
        "WHERE p.kind='package' AND d.kind='domain'"
    ).fetchall()
    return {row[0]: row[1] for row in rows}


def _query_package_uris(conn) -> dict[str, str]:
    """Return {package_name: uri} for every package node in the graph.

    Reads from the dedicated `nodes.uri` column populated by `upsert._upsert_node`
    (which pops `uri` from attrs before serializing the rest into attrs_json,
    see packages/graph-io/src/graph_io/upsert.py). Single SQL round trip.
    """
    rows = conn.execute(
        "SELECT name, uri FROM nodes WHERE kind='package' AND uri IS NOT NULL"
    ).fetchall()
    return {row[0]: row[1] for row in rows}


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
        added:             Names of packages that received newly created vault pages.
        updated:           Names of packages whose existing vault pages were refreshed.
        deleted:           Names of packages marked stale (vault page exists, repo package gone).
        renamed:           Pairs [[old_name, new_name], ...] for detected renames.
        errors:            Error strings for packages that failed during fan-out.
        state_gate:        Dict from compute_state_gate() — {allowed, reason, head_commit}.
        entities_created:  URIs of entity pages newly written this scan (Phase 45 D-15).
        entities_updated:  URIs of entity pages whose frontmatter changed this scan.
        entities_deleted:  URIs of entity pages hard-deleted by `write_entities` (vanished from graph).
        entities_narrated: URIs that received a successful narrator body injection.
        entity_errors:     repr() of EntityWriteError + narrator failure messages,
                           accumulated for partial-success reporting.
    """

    added: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    renamed: list[list[str]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    state_gate: dict = field(default_factory=dict)
    # Phase 45 D-15: URI-keyed entity reporting (alongside legacy name-keyed fields above).
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
        pkg:        Workspace metadata dict (from discover_workspaces).
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
        kind:           One of ADMITTED_KINDS_V18.
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
# Helper: _add_stale_tag
# ---------------------------------------------------------------------------


def _add_stale_tag(page_path: Path) -> None:
    """Prepend stale: true to the YAML frontmatter of an existing vault page.

    Idempotent: checks for existing stale: line before prepending (T-05-04-03).
    Preserves all other frontmatter keys and body content.
    """
    if not page_path.exists():
        logger.warning("Cannot add stale tag — page not found: %s", page_path)
        return

    text = page_path.read_text(encoding="utf-8")

    # Already stale — check only within frontmatter to avoid false positives
    # from body prose that mentions "stale: true"
    frontmatter_end = text.find("\n---", 3)
    if frontmatter_end != -1:
        frontmatter = text[:frontmatter_end]
    else:
        frontmatter = text
    if "stale: true" in frontmatter:
        return

    # Insert stale: true as the first field after the opening ---
    if text.startswith("---\n"):
        # Replace opening --- with --- + stale: true
        new_text = "---\nstale: true\n" + text[4:]
    else:
        # No frontmatter — prepend it
        new_text = "---\nstale: true\n---\n\n" + text

    page_path.write_text(new_text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Public: run_scan
# ---------------------------------------------------------------------------


async def run_scan(
    workspace_path: Path | None = None,
    no_file_map: bool = False,
    max_depth: int = 3,
    repo_path: Path | None = None,
    model_override: str | None = None,
) -> ScanResult:
    """End-to-end scan: discovery → diff → scanner fan-out → post-processing.

    Steps:
        1. Resolve wiki and repo from workspace_path.
        2. Read layout block from wiki/CLAUDE.md or wiki/AGENTS.md.
        3. discover_workspaces(repo, pinned_containers=pinned).
        4. Build file_map per workspace (unless no_file_map=True).
        5. _load_existing_pages(wiki) — existing vault pages by name.
        6. attach_changed_files(workspaces, existing, repo).
        7. compute_diff(workspaces, existing) → {new, renamed, deleted, unchanged}.
        8. compute_state_gate(repo) → {allowed, reason, head_commit}.
        9. Scanner fan-out: SubagentPool.run_all for new + changed packages.
        10. Write successful stub pages (LLM body + deterministic file map).
        11. Add stale: true to deleted/renamed vault pages + log entries.
        12. regenerate_dependencies_index + update_index.
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

    Returns:
        ScanResult with added, updated, deleted, renamed, errors, state_gate.
    """
    # Step 1: resolve wiki and repo
    wiki, resolved_repo = resolve_wiki_and_repo(workspace_path)
    project_ctx = render_project_context(wiki)
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
        # NOTE: ops_update interprets `workspace` as the workspace ROOT (where
        # `.graph/code.db` is written), not the wiki directory. Phase 38's
        # commands/graph.py (`_resolve_paths` → `cfg.workspace`) and the
        # librarian (`graph_dir(wiki.parent)` in commands/query.py) both use
        # the workspace root. We follow that convention here so the post-update
        # `read_only_connect(graph_dir(wiki.parent) / "code.db")` finds the
        # DB cg just created. (The plan's must_have says `workspace=wiki`;
        # that is a plan-spec drift — passing `wiki` makes cg write to
        # `<wiki>/.graph/code.db` while the read path looks under
        # `<workspace>/.graph/code.db`, so the conn open would fall through
        # to the post-update NOT_INITIALIZED fallback every time. See Phase
        # 39 SUMMARY's deviations section.)
        _workspace_root = wiki.parent
        _cg_args = _build_namespace(
            ops_update, repo=repo, workspace=_workspace_root, full=False
        )
        _cg_exit, _cg_stdout, _cg_stderr = _capture_run(ops_update, _cg_args)
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

        # Step 2: read layout block
        # When repo_path is supplied as an override, also bypass the vault's
        # pinned_containers — the vault layout describes the ORIGINAL monorepo
        # the vault was generated from (e.g. `graph-wiki/packages/` + `plugins/`)
        # and almost certainly does not match the override repo's directory
        # structure. Using unpinned discovery against the override lets
        # discover_workspaces find the workspace by its own pyproject.toml.
        pinned: list[dict] | None = None
        if repo_path is None:
            for schema_name in ("CLAUDE.md", "AGENTS.md"):
                layout = read_layout(wiki / schema_name)
                if layout and layout.get("containers"):
                    pinned = layout.get("containers", [])
                    break

        # Step 3: discover workspaces
        workspaces = discover_workspaces(repo, pinned_containers=pinned)

        # Phase 39 Step 3.5 (D-03/D-04): decorate workspaces with graph URIs + domain.
        # queries.list_packages enumerates known package NodeRecords (one round trip);
        # _query_package_uris (one round trip) maps name → nodes.uri because the URI
        # lives in the dedicated uri column rather than attrs_json (see upsert.py);
        # _query_package_domains (one SQL join) maps name → domain via
        # belongs_to_domain. wiki_relative_path is recomputed only when graph
        # domain changes the routing.
        from wiki_io.scan_monorepo import unscope as _unscope
        if conn is not None:
            known_pkg_names = {rec.name for rec in queries.list_packages(conn)}
            pkg_uri_map = _query_package_uris(conn)
            domain_map = _query_package_domains(conn)
            n_decorated = 0
            for w in workspaces:
                key = _unscope(w["name"])
                if key not in known_pkg_names:
                    continue
                uri = pkg_uri_map.get(key)
                if uri:
                    w["uri"] = uri
                    n_decorated += 1
                graph_domain = domain_map.get(key)
                if graph_domain and w.get("domain") != graph_domain:
                    w["domain"] = graph_domain
                    # Domain-routed workspaces use domains/<d>/packages/<n>/overview.md;
                    # vault_dir is structurally unused on that branch.
                    w["wiki_relative_path"] = _wiki_relative_path_for(w, vault_dir=None)
            append_log(
                wiki,
                "scan",
                f"graph decoration: {n_decorated}/{len(workspaces)} workspaces",
                detail=None,
                silent=True,
                raise_exception=True,
            )

        # Step 4: build file_map per workspace
        if not no_file_map:
            for w in workspaces:
                pkg_dir = repo / w["path"]
                fm = build_file_map(pkg_dir, max_depth=max_depth)
                if fm is not None:
                    w["file_map"] = fm

        # Step 5: load existing vault pages
        existing = _load_existing_pages(wiki)

        # Step 6: attach changed files since last sync
        attach_changed_files(workspaces, existing, repo)

        # Step 7: compute diff
        diff = compute_diff(workspaces, existing)

        # Step 8: compute state gate
        state_gate = compute_state_gate(repo)

        # Build workspace lookup by unscoped name for post-processing
        unscope = _unscope
        ws_by_name = {unscope(w["name"]): w for w in workspaces}

        # Step 9: scanner fan-out
        # Items = new packages + unchanged packages with changed files
        fan_items: list[dict] = []
        for name in diff["new"]:
            if name in ws_by_name:
                fan_items.append(ws_by_name[name])
        for name in diff["unchanged"]:
            if name in ws_by_name:
                w = ws_by_name[name]
                changed = w.get("changed_files")
                if changed:  # non-empty list means files changed
                    fan_items.append(w)

        cfg = load_role_config("scanner")
        pool = SubagentPool(trace_dir=wiki / ".graph-wiki" / "traces")
        if model_override is not None:
            scanner_llm = ChatBedrockConverse(
                model_id=model_override,
                region_name=cfg["region"],
                max_tokens=cfg["max_tokens"],
            )
        else:
            scanner_llm = make_llm("scanner")

        async def generate_stub(pkg: dict) -> TaskResult:
            prompt = build_stub_prompt(pkg, no_file_map=no_file_map, repo_root=repo)
            msgs = [
                SystemMessage(content=build_scanner_system(project_context=project_ctx)),
                HumanMessage(content=prompt),
            ]
            resp = await scanner_llm.ainvoke(msgs)
            # Phase 16-02 G-01: wrap in TaskResult so pool's trace record carries
            # resp.usage_metadata; downstream still sees the string body.
            return TaskResult(value=resp.content, response=resp)

        fan_result: FanOutResult = await pool.run_all(
            items=fan_items,
            task=generate_stub,
            role="scanner",
            model_id=cfg["model_id"],
            max_concurrency=cfg["max_concurrency"],
        )

        # Step 10: write successful stub pages
        added: list[str] = []
        updated: list[str] = []

        for pkg, llm_body in fan_result.successes:
            pkg_name = unscope(pkg["name"])
            vault_page_rel = pkg.get("wiki_relative_path", f"packages/{pkg_name}/{pkg_name}.md")
            page_path = wiki / vault_page_rel
            page_path.parent.mkdir(parents=True, exist_ok=True)

            # Deterministic file map append (RESEARCH Risk 5)
            pkg_dir = repo / pkg["path"]
            file_map_text = ""
            if not no_file_map:
                fm = build_file_map(pkg_dir, max_depth=max_depth)
                if fm is not None:
                    file_map_text = "\n\n" + fm

            final_page = llm_body + file_map_text
            page_path.write_text(final_page, encoding="utf-8")

            if pkg_name in diff["new"]:
                added.append(pkg_name)
            else:
                updated.append(pkg_name)

        # Collect errors
        errors: list[str] = [
            f"{unscope(err.item['name'])}: {err.exception}"
            for err in fan_result.errors
        ]

        # Step 11: stale-tag deleted packages
        for pkg_name in diff["deleted"]:
            existing_rec = existing.get(pkg_name)
            if existing_rec:
                page_path = wiki / existing_rec["wiki_relative_path"]
                _add_stale_tag(page_path)
                append_log(
                    wiki,
                    "scan",
                    f"marked stale: {pkg_name}",
                    detail=None,
                    silent=True,
                    raise_exception=True,
                )
                logger.info("Marked stale: %s", pkg_name)

        # stale-tag renamed packages (old side)
        for rename_pair in diff["renamed"]:
            old_name = rename_pair[0]
            existing_rec = existing.get(old_name)
            if existing_rec:
                page_path = wiki / existing_rec["wiki_relative_path"]
                _add_stale_tag(page_path)
                new_name = rename_pair[1] if len(rename_pair) > 1 else "unknown"
                append_log(
                    wiki,
                    "scan",
                    f"marked stale: {old_name} (renamed to {new_name})",
                    detail=None,
                    silent=True,
                    raise_exception=True,
                )
                logger.info("Marked stale (renamed): %s -> %s", old_name, new_name)

        # Step 12: regenerate indexes
        regenerate_dependencies_index(wiki, workspaces)
        try:
            update_index(wiki)
        except Exception as exc:
            logger.warning("update_index failed (non-fatal): %s", exc)

        # Step 13: final log entry
        n_added = len(added)
        n_updated = len(updated)
        n_deleted = len(diff["deleted"])
        append_log(
            wiki,
            "scan",
            f"scan complete: +{n_added} ~{n_updated} -{n_deleted}",
            detail=None,
            silent=True,
            raise_exception=True,
        )

        return ScanResult(
            added=added,
            updated=updated,
            deleted=diff["deleted"],
            renamed=diff["renamed"],
            errors=errors,
            state_gate=state_gate,
        )
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass  # closing a read-only conn should not raise; defensive
