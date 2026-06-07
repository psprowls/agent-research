"""Scan command — build the code graph, write one page per admitted entity.

Public API:
    ScanResult                          — dataclass with state_gate + entity result fields
    build_stub_prompt(pkg)              — human message used by build_entity_narrative_prompt
                                          callers and downstream eval harnesses
    build_entity_narrative_prompt(...)  — (system, human) for the narrator LLM (Phase 45 D-05)
    run_scan(workspace_path, ...)       — end-to-end scan pipeline (Step 9a write_entities +
                                          Step 9b narrator fan-out + Step 12 dual-writer indexes)
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

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

if TYPE_CHECKING:
    from subagent_runtime.pool import SubagentPool as SubagentPoolType
    from subagent_runtime.pool import TaskResult as TaskResultType

from wiki_io._workspace import resolve_wiki_and_repo
from wiki_io.append_log import append_log
from wiki_io.backlink_index import regenerate_referenced_in_wiki
from wiki_io.drift import (
    clear_resolved_flags,
    extract_file_map,
    iter_human_sections,
    section_hash,
)
from wiki_io.entity_writer import (
    ADMITTED_KINDS,
    LAST_UPDATED_COMMIT_KEY,
    _agent_plugin_table_variables,
    _compute_collision_set,
    _extract_file_map_descriptions,
    _kind_list_fns,
    extract_narrative,
    file_map_todo_paths,
    fill_file_map_descriptions,
    inject_file_map,
    inject_narrative,
    scanner_frontmatter_for_node,
    set_frontmatter_value,
    short_filename,
    update_frontmatter,
    write_entities,
)
from wiki_io.git_state import changed_files_since, short_commit
from wiki_io.human_sections import find_todo_human_sections, replace_todo_human_sections
from wiki_io.index_generator import generate_index
from wiki_io.lint.common import FILE_MAP_SECTION_RE
from wiki_io.scan_monorepo import (
    build_dir_file_map,
    build_file_map,
    compute_state_gate,
)
from wiki_io.update_index import update_index
from workspace_io import manifest as _manifest
from workspace_io.paths import graph_dir, manifest_path

from graph_wiki_core.commands.graph import run_build as _cg_run_build
from graph_wiki_core.commands.package_reader import PackageReaderItem, run_package_reader
from graph_wiki_core.commands.propagate_drift import run_propagate_drift
from graph_wiki_core.graph_tools import build_graph_tools
from graph_wiki_core.prompts.drift_judge import (
    build_drift_judge_prompt,
    parse_drift_verdict,
)
from graph_wiki_core.prompts.file_describer import FILE_DESCRIBER_SYSTEM

logger = logging.getLogger(__name__)


def _bedrock_stack() -> tuple[Any, Any, type["SubagentPoolType"], type["TaskResultType"]] | None:
    if load_role_config is None or make_llm is None or SubagentPool is None or TaskResult is None:
        return None
    return (
        cast(Any, load_role_config),
        cast(Any, make_llm),
        cast(type["SubagentPoolType"], SubagentPool),
        cast(type["TaskResultType"], TaskResult),
    )


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
            f"cg update failed (exit_code={exit_code}); scan aborted. stderr: {stderr.strip() or '<empty>'}"
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

PACKAGE_READER_TARGET_KINDS = frozenset({"package", "app", "agent_plugin", "test_suite"})


def _is_init_failure_stderr(stderr: str) -> bool:
    """Return True if `stderr` matches a known init-failure pattern (D-08)."""
    return any(p in stderr for p in _INIT_FAILURE_STDERR_PATTERNS)


def _live_file_map_descriptions(page_path: Path) -> dict[str, str]:
    """Read filled File-map descriptions from a single entity page's CURRENT
    on-disk `## File map` section, keyed by package-root path.

    Returns ``{}`` when the page is missing, malformed, or has no filled rows.
    PTO replacement for the old pre-scan File-map snapshot pass: under
    preserve-then-overwrite, `write_entities` no longer resets the File-map
    body, so at Step 10b injection time the page still holds the descriptions a
    prior scan filled — read them live here instead of snapshotting every page
    before the write.
    """
    try:
        post = frontmatter.load(str(page_path))
    except Exception:  # noqa: BLE001 — a missing/malformed page must not abort scan
        return {}
    section = FILE_MAP_SECTION_RE.search(post.content)
    if not section:
        return {}
    pkg_name = section.group(1).strip()
    return _extract_file_map_descriptions(section.group(2), pkg_name)


@dataclass(frozen=True)
class _PackageReaderCandidate:
    page_path: Path
    graph_path: str | None = None
    kind: str | None = None
    name: str | None = None
    language: str | None = None


async def _run_package_reader_pass(
    *,
    wiki: Path,
    repo: Path,
    conn: Any | None,
    model_override: str | None,
    candidate_pages: dict[str, _PackageReaderCandidate],
) -> tuple[set[str], list[str]]:
    stack = _bedrock_stack()
    if stack is None:
        return set(), []
    load_role_config_fn, make_llm_fn, subagent_pool_type, task_result_type = stack

    graph_tools = build_graph_tools(conn) if conn is not None else []
    errors: list[str] = []
    items: list[tuple[str, Path, PackageReaderItem]] = []
    for uri, candidate in sorted(candidate_pages.items()):
        page_path = candidate.page_path
        try:
            post = frontmatter.load(page_path)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{uri}: package_reader page load failed: {exc!r}")
            continue
        kind = str(candidate.kind or post.metadata.get("kind") or "")
        if kind not in PACKAGE_READER_TARGET_KINDS:
            continue
        try:
            page_text = page_path.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{uri}: package_reader page read failed: {exc!r}")
            continue
        todo_sections = find_todo_human_sections(page_text, entity_kind=kind)
        if not todo_sections:
            continue
        graph_path = str(candidate.graph_path or post.metadata.get("graph_path") or post.metadata.get("path") or "")
        if not graph_path:
            errors.append(f"{uri}: package_reader missing graph path")
            continue
        item = PackageReaderItem(
            uri=uri,
            kind=kind,
            name=str(candidate.name or post.metadata.get("graph_name") or post.metadata.get("title") or page_path.stem),
            graph_path=graph_path,
            language=str(candidate.language or post.metadata.get("language") or "unknown"),
            frontmatter=cast(Any, dict(post.metadata)),
            page_content=page_text,
            requested_sections={section.heading: section.body for section in todo_sections},
            narrative=extract_narrative(page_text) or "",
            file_map=extract_file_map(page_text) or "",
            graph_context="",
            entity_root=graph_path,
        )
        items.append((uri, page_path, item))

    if not items:
        return set(), errors

    cfg = load_role_config_fn("package_reader")
    llm = make_llm_fn("package_reader", model_override=model_override)
    pool = subagent_pool_type(trace_dir=graph_dir(wiki.parent) / "traces")

    async def fill_sections(item_tuple: tuple[str, Path, PackageReaderItem]) -> Any:
        _uri, _page_path, reader_item = item_tuple
        result = await run_package_reader(llm=llm, item=reader_item, repo=repo, wiki=wiki, graph_tools=graph_tools)
        return task_result_type(value=result, response=result)

    fanout = await pool.run_all(
        items=items,
        task=fill_sections,
        role="package_reader",
        model_id=cfg["model_id"],
        max_concurrency=cfg["max_concurrency"],
    )
    filled: set[str] = set()
    for item_tuple, result in fanout.successes:
        uri, page_path, _reader_item = item_tuple
        if result.error:
            errors.append(f"{uri}: {result.error}")
        if not result.replacements:
            continue
        try:
            changed = replace_todo_human_sections(page_path, result.replacements)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{uri}: replace_todo_human_sections failed: {exc!r}")
            continue
        if changed:
            filled.add(uri)
    for err in fanout.errors:
        uri = err.item[0]
        errors.append(f"{uri}: {err.exception!r}")
    return filled, errors


def _record_package_reader_candidate(
    candidates: dict[str, _PackageReaderCandidate],
    *,
    uri: str,
    candidate: _PackageReaderCandidate,
) -> None:
    existing = candidates.get(uri)
    if existing is None or (not existing.graph_path and candidate.graph_path):
        candidates[uri] = candidate


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


# Ordered (heading, dict-key) pairs for the agent_plugin component inventory
# injected into the narrator prompt (D3 — grounding the narrator in components).
_AGENT_PLUGIN_INVENTORY_SECTIONS: tuple[tuple[str, str], ...] = (
    ("## Commands", "commands_table"),
    ("## Agents", "agents_table"),
    ("## Skills", "skills_table"),
    ("## Scripts", "scripts_table"),
    ("## Hooks", "hooks_table"),
    ("## MCP servers", "mcp_servers_table"),
)

# Human-readable labels for each scanner-owned relation key. Used by the
# narrator prompt to render relations as natural prose hints instead of YAML.
_NARRATIVE_RELATION_LABELS: dict[str, str] = {
    "depends_on": "Depends on",
    "test_suites": "Test suites",
    "entry_points": "Entry points",
    "domains": "Domains",
    "parent_domain": "Parent domain",
    "sub_domains": "Sub-domains",
    "packages": "Packages",
    "tested_packages": "Tested packages",
    "used_by": "Used by",
    "members": "Members",
    "ecosystem": "Ecosystem",
    "language": "Language",
    "version": "Version",
    "suite_kind": "Suite kind",
    "file_count": "File count",
    "package_count": "Package count",
    "versions_in_use": "Versions in use",
}


def build_entity_narrative_prompt(
    node,
    kind: str,
    file_map_text: str,
    relations: dict,
    components_text: str = "",
) -> tuple[str, str]:
    """Return (system_message, human_message) for the narrator LLM (Phase 45 D-05).

    The narrator generates ONLY the prose body that lives between the
    `## Narrative` heading and the next H2 on an entity page. Frontmatter,
    headings, and all other page structure are scanner-owned and MUST NOT
    appear in the model's output.

    Args:
        node:            graph_io.queries.NodeRecord (has `.name`, `.attrs["uri"]`).
        kind:            One of ADMITTED_KINDS.
        file_map_text:   Optional file listing (non-empty only for `package` kinds).
        relations:       Per-kind relation dict from `scanner_frontmatter_for_node`,
                         with `uri` and `kind` already stripped or harmlessly ignored.
        components_text: Optional component inventory (non-empty only for `agent_plugin`
                         kinds); rendered tables joined under their H2 headings.

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

    if kind == "agent_plugin" and components_text:
        lines.append("")
        lines.append("Component inventory (for reference; do NOT reproduce verbatim in your output):")
        lines.append(components_text[:2000])  # wider cap than file_map: the six component tables are denser

    lines.append("")
    lines.append("Write the narrative body for this page (prose only).")

    return system, "\n".join(lines)


# ---------------------------------------------------------------------------
# Phase: file-map description fan-out (code-reader role) — prompt + parser
# ---------------------------------------------------------------------------


def build_file_describer_prompt(pkg: dict, todo_paths: list[str], repo_root: Path | None = None) -> tuple[str, str]:
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

    lines.append("Return the JSON object mapping each describable path to its one-line description.")
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


def _changed_rel_paths(changed: list[str], node_path: str) -> set[str]:
    """Relativize repo-relative changed paths to package-root-relative keys.

    `changed_files_since` returns repo-relative paths (e.g.
    ``packages/foo/src/bar.py``); the File-map ``preserved`` dict is keyed by
    package-root-relative paths (e.g. ``src/bar.py``, see
    ``_extract_file_map_descriptions``). This maps the former to the latter so
    the preserved-drop's set-matching works. Paths not under ``node_path`` are
    silently dropped — they cannot match a row in this page's File map (§3.3).
    """
    base = Path(node_path)
    rel: set[str] = set()
    for p in changed:
        try:
            rel.add(str(Path(p).relative_to(base)))
        except ValueError:
            continue
    return rel


def _commit_dirty_changes(
    wiki: Path,
    repo: Path,
    conn: Any,
    head: str | None,
    collision_set: frozenset[str],
) -> dict[str, list[str] | None]:
    """Map `package`/`app`/`test_suite`/`agent_plugin` URIs whose files changed since the commit
    recorded on their page (`last_updated_commit`) to the changed-file list.

    Keys are the dirty URIs (so ``result.keys()`` is the M2a "needs
    re-narration" set). Each value is the repo-relative list of files
    ``changed_files_since`` reported, or ``None`` when the anchor SHA is unknown
    to this repo (D-D self-correction). Pages WITHOUT an anchor are skipped
    (D-C). M2a used only the keys; M2b consumes the values to drop changed rows
    from the File-map ``preserved`` map (§3.1).
    """
    dirty: dict[str, list[str] | None] = {}
    if head is None or conn is None:
        return dirty
    list_fns = _kind_list_fns()
    for kind in ("package", "app", "test_suite", "agent_plugin"):
        list_fn = list_fns.get(kind)
        if list_fn is None:
            continue
        for node in list_fn(conn):
            if not isinstance(node.attrs, dict):
                continue
            uri = node.attrs.get("uri")
            node_path = node.path
            if not uri or not node_path:
                continue
            page_path = _entity_page_path(wiki, kind, node, uri, collision_set)
            if not page_path.exists():
                continue
            try:
                anchor = frontmatter.load(str(page_path)).metadata.get(LAST_UPDATED_COMMIT_KEY)
            except Exception:  # noqa: BLE001 — a malformed page must not abort scan
                continue
            if not anchor:
                continue
            changed = changed_files_since(repo, str(anchor), node_path)
            if changed is None or changed:
                dirty[uri] = changed
    return dirty


# Living Wiki M2e: kinds with BOTH a regenerated `## Narrative` and human-owned
# sections worth drift-checking. `repository`/`domain`/`dependency` have no
# curated human prose and are excluded (spec §3.4). `agent_plugin` is included
# now for forward-compatibility — its commit-gated coverage completes with the
# agent-plugin parity plan, but it already narrates on structural change.
DRIFT_TARGET_KINDS: frozenset[str] = frozenset({"package", "app", "test_suite", "agent_plugin"})


def _drift_candidates(wiki: Path) -> list[tuple[Path, str, str, str | None]]:
    """Return ``[(page_path, anchor, narrative, file_map), ...]`` for entity pages
    whose narrative is newer than their last drift check (spec §3.1 step 1).

    Gate (all required): kind in DRIFT_TARGET_KINDS; `last_updated_commit`
    present; `## Narrative` present (ground truth); and
    `drift_checked_commit != last_updated_commit` (a missing checked-commit
    counts as lagging). Comparison is string inequality — SHAs are not ordered.
    """
    entities_dir = wiki / "entities"
    if not entities_dir.is_dir():
        return []
    out: list[tuple[Path, str, str, str | None]] = []
    for page_path in sorted(entities_dir.glob("*.md")):
        try:
            post = frontmatter.load(str(page_path))
        except Exception:  # noqa: BLE001 — a malformed page must not abort scan
            continue
        meta = post.metadata
        if meta.get("kind") not in DRIFT_TARGET_KINDS:
            continue
        anchor = meta.get(LAST_UPDATED_COMMIT_KEY)
        if not anchor:
            continue
        if meta.get("drift_checked_commit") == anchor:
            continue  # already drift-checked at this narrative revision
        narrative = extract_narrative(post.content)
        if not narrative:
            continue  # no ground truth -> nothing to judge against
        out.append((page_path, str(anchor), narrative, extract_file_map(post.content)))
    return out


async def _drift_flag_pass(wiki: Path, model_override: str | None) -> None:
    """Judge each human-owned section of every drift candidate against its page's
    regenerated narrative; write `drift_review` + advance `drift_checked_commit`.

    Judge-once: only candidate pages (narrative newer than last check) are judged,
    and each is stamped to its anchor afterward, so a (page, narrative-change) pair
    costs LLM tokens exactly once (spec §3.1/D3).
    """
    stack = _bedrock_stack()
    if stack is None:
        return
    load_role_config_fn, make_llm_fn, subagent_pool_type, task_result_type = stack
    candidates = _drift_candidates(wiki)
    if not candidates:
        return

    # item = (page_path, anchor, heading, chunk, narrative, file_map)
    items: list[tuple[Path, str, str, str, str, str | None]] = []
    page_anchor: dict[Path, str] = {}
    for page_path, anchor, narrative, file_map in candidates:
        page_anchor[page_path] = anchor
        body = page_path.read_text(encoding="utf-8")
        for heading, chunk in iter_human_sections(body):
            items.append((page_path, anchor, heading, chunk, narrative, file_map))

    verdicts: list[tuple] = []
    if items:
        drift_cfg = load_role_config_fn("drift_judge")
        drift_llm = make_llm_fn("drift_judge", model_override=model_override)
        drift_pool = subagent_pool_type(trace_dir=graph_dir(wiki.parent) / "traces")

        async def judge(item: tuple) -> TaskResultType:
            _pp, _anchor, heading, chunk, narrative, file_map = item
            system_msg, human_msg = build_drift_judge_prompt(heading, chunk, narrative, file_map)
            resp = await drift_llm.ainvoke([SystemMessage(content=system_msg), HumanMessage(content=human_msg)])
            return task_result_type(value=parse_drift_verdict(resp.content), response=resp)

        fan = await drift_pool.run_all(
            items=items,
            task=judge,
            role="drift_judge",
            model_id=drift_cfg["model_id"],
            max_concurrency=drift_cfg["max_concurrency"],
        )
        verdicts = list(fan.successes)

    flags_by_page: dict[Path, list[dict]] = {}
    for item, verdict in verdicts:
        page_path, anchor, heading, chunk, _narr, _fmp = item
        if isinstance(verdict, dict) and verdict.get("stale"):
            flags_by_page.setdefault(page_path, []).append(
                {
                    "section": heading.removeprefix("## ").strip(),
                    "detected_commit": anchor,
                    "hash": section_hash(chunk),
                    "reason": str(verdict.get("reason", "")),
                }
            )

    for page_path, anchor in page_anchor.items():
        entries = flags_by_page.get(page_path)
        try:
            if entries:
                update_frontmatter(
                    page_path,
                    {"drift_checked_commit": anchor, "drift_review": entries},
                )
            else:
                update_frontmatter(
                    page_path,
                    {"drift_checked_commit": anchor},
                    delete=["drift_review"],
                )
        except Exception as exc:  # noqa: BLE001 — non-fatal flag write
            logger.warning("drift flag write failed for %s: %s", page_path, exc)


def _drift_clear_pass(wiki: Path) -> None:
    """Free, every-scan flag resolution (spec §3.2/D4). For every entity page
    holding a `drift_review` key, recompute each flagged section's current hash;
    drop entries whose hash changed (prose edited) or whose section is gone, and
    remove the key when it empties. No LLM, runs even on --no-narrate scans."""
    entities_dir = wiki / "entities"
    if not entities_dir.is_dir():
        return
    for page_path in sorted(entities_dir.glob("*.md")):
        try:
            post = frontmatter.load(str(page_path))
        except Exception:  # noqa: BLE001 — malformed page must not abort scan
            continue
        entries = post.metadata.get("drift_review")
        if not isinstance(entries, list):
            continue
        survivors = clear_resolved_flags(cast(list[dict[str, Any]], entries), post.content)
        if survivors == entries:
            continue
        try:
            if survivors:
                update_frontmatter(page_path, {"drift_review": survivors})
            else:
                update_frontmatter(page_path, delete=["drift_review"])
        except Exception as exc:  # noqa: BLE001 — non-fatal
            logger.warning("drift clear write failed for %s: %s", page_path, exc)


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
    propagate_drift: bool = False,
) -> ScanResult:
    """End-to-end scan: graph build → entity writes → narrator fan-out → indexes.

    Steps:
        1. Resolve wiki and repo from workspace_path; run `cg update`, open conn.
        8. compute_state_gate(repo, workspace=wiki.parent) → {allowed, reason, head_commit}.
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
        propagate_drift: When True (and narrate=True), after the drift passes run
                        the M4 cross-page drift producer (gw wiki propagate-drift)
                        over the just-written entity pages, proposing curated-page
                        updates into the ledger. Off by default. Needs the
                        Bedrock stack (gated alongside narrate).

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
        # `.graph-wiki/code.db` is written), not the wiki directory. commands/graph.py
        # (`_resolve_paths` → `cfg.workspace`) and the librarian
        # (`graph_dir(wiki.parent)` in commands/query.py) both use the workspace
        # root. We follow that convention here so the post-update
        # `read_only_connect(graph_dir(wiki.parent) / "code.db")` finds the
        # DB the graph build just created. (The plan's must_have says
        # `workspace=wiki`; that is a plan-spec drift — passing `wiki` makes the
        # build write to `<wiki>/.graph-wiki/code.db` while the read path looks under
        # `<workspace>/.graph-wiki/code.db`, so the conn open would fall through
        # to the post-update NOT_INITIALIZED fallback every time. See Phase
        # 39 SUMMARY's deviations section.)
        #
        # Phase 59 (59-02b): migrated off the deleted _build_namespace/_capture_run
        # shim onto the typed run_build core. update.run is silent on success, so
        # _cg_stdout is always "" here (sanctioned by D-06).
        _workspace_root = wiki.parent
        _cg_exit, _cg_stdout, _cg_stderr = _cg_run_build(repo, _workspace_root, full=False)
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
            reason = _cg_stderr.strip().splitlines()[-1] if _cg_stderr.strip() else "unknown init failure"
            sys.stderr.write(
                f"[NOT_INITIALIZED fallback: graph could not be initialized ({reason}); using path-based slugs]\n"
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
        # wiki is workspace/wiki under the standard layout; .graph-wiki lives next to it
        # (mirrors the pattern in commands/query.py — librarian's graph-tools wiring).
        if _graph_ready:
            try:
                conn = read_only_connect(graph_dir(wiki.parent) / "code.db")
            except GraphNotInitializedError as exc:
                # Defensive: should not happen after a successful cg update,
                # but treat as a NOT_INITIALIZED-class fallback if it does.
                sys.stderr.write(
                    f"[NOT_INITIALIZED fallback: graph could not be initialized ({exc}); using path-based slugs]\n"
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
        state_gate = compute_state_gate(repo, workspace=wiki.parent)
        head = state_gate.get("head_commit")
        # Item 1: abbreviate to git's canonical short form ONCE per scan (HEAD is
        # the same for every page stamped this run). Falls back to the full SHA on
        # any git failure, so stamping never breaks (full SHAs stay git-resolvable).
        short_head = short_commit(repo, head) if head else head

        # Phase 45 D-04: Step 9 splits into 9a (entity write) + 9b (narrator fan-out).
        # The legacy scanner fan-out for wiki/packages/<name>/<name>.md pages is
        # REMOVED in v1.8 — D-08 hard cutover. `model_override` is kept available
        # for future eval sweeps targeting the narrator role.
        entity_write_result = None
        narrator_result: Any | None = None
        # M2b: per-URI changed-file lists for commit-dirty package/app pages
        # (keys = dirty URIs; value = repo-relative changed paths, or None when
        # the page's anchor SHA is unknown to the repo). Consumed by Step 10b's
        # preserved-drop. Pre-initialized so the file-map block reads it safely
        # even when the graph conn is None.
        commit_dirty: dict[str, list[str] | None] = {}

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

            # M2a commit-gate: re-narrate package/app entities whose files
            # changed since their recorded last_updated_commit (Living Wiki M2).
            commit_dirty = _commit_dirty_changes(
                wiki,
                repo,
                conn,
                head,
                _compute_collision_set(conn, ADMITTED_KINDS, _kind_list_fns()),
            )
            if commit_dirty:
                # EntityWriteResult is a frozen dataclass; mutate the set in
                # place rather than rebinding the field (`|=` would rebind).
                entity_write_result.needs_narrative.update(commit_dirty.keys())
                append_log(
                    wiki,
                    "scan",
                    f"commit-gate: {len(commit_dirty)} entity(s) flagged for re-narration",
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
                stack = _bedrock_stack()
                if stack is None:
                    narrator_items = []
                else:
                    load_role_config_fn, make_llm_fn, subagent_pool_type, task_result_type = stack
                    narrator_cfg = load_role_config_fn("narrator")
                    narrator_llm = make_llm_fn("narrator", model_override=model_override)
                    narrator_pool = subagent_pool_type(trace_dir=graph_dir(wiki.parent) / "traces")

                    async def generate_narrative(
                        item: tuple[str, str, Any],
                    ) -> TaskResultType:
                        uri_inner, kind_inner, node_inner = item
                        relations = scanner_frontmatter_for_node(conn, kind_inner, node_inner)
                        relations_for_prompt = {k: v for k, v in relations.items() if k not in ("uri", "kind")}
                        # File maps are graph-sourced (Step 10b); the narrator no
                        # longer receives a per-workspace file-map hint.
                        file_map = ""
                        components_text = ""
                        if kind_inner == "agent_plugin":
                            tv = _agent_plugin_table_variables(conn, node_inner)
                            components_text = "\n\n".join(
                                f"{heading}\n{tv[key]}" for heading, key in _AGENT_PLUGIN_INVENTORY_SECTIONS
                            )
                        system_msg, human_msg = build_entity_narrative_prompt(
                            node_inner,
                            kind_inner,
                            file_map,
                            relations_for_prompt,
                            components_text=components_text,
                        )
                        msgs = [
                            SystemMessage(content=system_msg),
                            HumanMessage(content=human_msg),
                        ]
                        resp = await narrator_llm.ainvoke(msgs)
                        return task_result_type(value=resp.content, response=resp)

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
        # M2c Part 3 (§3.3 D4): the narrator loop no longer stamps the anchor
        # inline. It records which pages got real prose (`good_prose_uris`) and
        # where each narrated page lives (`narrated_page_paths`); a single
        # refill-gated pass after Step 10c does the stamping. This closes the
        # narrator-path residual where good prose advanced the anchor even though
        # a dropped file-map row was never refilled.
        good_prose_uris: set[str] = set()
        narrated_page_paths: dict[str, Path] = {}
        narrated_page_candidates: dict[str, _PackageReaderCandidate] = {}
        if narrator_result is not None:
            assert conn is not None
            inject_collision_set = _compute_collision_set(
                conn,
                ADMITTED_KINDS,
                _kind_list_fns(),
            )

            for item, prose in narrator_result.successes:
                uri_inner, kind_inner, node_inner = item
                entity_page_path = _entity_page_path(
                    wiki,
                    kind_inner,
                    node_inner,
                    uri_inner,
                    inject_collision_set,
                )
                try:
                    inject_narrative(entity_page_path, prose)
                    narrated_page_paths[uri_inner] = entity_page_path
                    attrs = node_inner.attrs if isinstance(node_inner.attrs, dict) else {}
                    narrated_page_candidates[uri_inner] = _PackageReaderCandidate(
                        page_path=entity_page_path,
                        graph_path=node_inner.path,
                        kind=kind_inner,
                        name=node_inner.name,
                        language=str(attrs.get("language") or "unknown"),
                    )
                    # Empty-prose guard (M2b §3.4): empty narration records
                    # nothing, so it can never mint an anchor on its own.
                    if head and prose.strip():
                        good_prose_uris.add(uri_inner)
                    entities_narrated.append(uri_inner)
                except Exception as inject_exc:  # noqa: BLE001 — partial-success
                    narrator_errors.append(f"{uri_inner}: inject_narrative failed: {inject_exc!r}")
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
        # M2b §3.4: package/app URIs whose File map was re-described this scan
        # (>=1 changed row dropped from preserved, or an unknown anchor forced a
        # full drop). Consumed by the shared-anchor restamp after Step 10c.
        redescribed_uris: set[str] = set()
        if entity_write_result is not None and conn is not None:
            refreshed = set(entity_write_result.created) | set(entity_write_result.updated)
            # M2b §3.2 (load-bearing): a package whose source changed with no
            # structural delta is in commit_dirty but NOT refreshed; without this
            # union its File map is never re-injected and the preserved-drop below
            # can't fire. Mirrors M2a's needs_narrative.update(commit_dirty).
            fm_targets = refreshed | set(commit_dirty)
            list_fns = _kind_list_fns()
            # Collision set shared by the package/app and test-suite branches.
            fm_collision_set = _compute_collision_set(conn, ADMITTED_KINDS, list_fns) if fm_targets else frozenset()
            fm_list_fns = [list_fns.get("package"), list_fns.get("app")]
            if fm_targets and any(fm_list_fns) and not no_file_map:
                fm_nodes = [n for fn in fm_list_fns if fn for n in fn(conn)]
                for node in fm_nodes:
                    if not isinstance(node.attrs, dict):
                        continue
                    node_uri = node.attrs.get("uri")
                    if not node_uri or node_uri not in fm_targets:
                        continue
                    node_path = node.path
                    if not node_path:
                        continue
                    file_map = build_file_map(repo / node_path, max_depth=max_depth)
                    if not file_map:
                        continue
                    slug = short_filename(node_uri, fm_collision_set)
                    fm_page_path = wiki / "entities" / f"{slug}.md"
                    # PTO: re-source surviving descriptions from the LIVE page —
                    # write_entities no longer reset the File-map body, so the
                    # filled rows are still on disk here. Then M2b's
                    # preserved-drop (below, unchanged) drops changed rows so
                    # they re-emerge as `— TODO` for Step 10c.
                    preserved = dict(_live_file_map_descriptions(fm_page_path))
                    if narrate and node_uri in commit_dirty:
                        changed = commit_dirty[node_uri]
                        if changed is None:
                            # Unknown anchor: no preserved row can be trusted —
                            # drop all, forcing a full re-describe (D-D / §3.1).
                            preserved = {}
                            redescribed_uris.add(node_uri)
                        else:
                            changed_rel = _changed_rel_paths(changed, node_path)
                            dropped = {p for p in preserved if p in changed_rel}
                            if dropped:
                                for p in dropped:
                                    preserved.pop(p, None)
                                redescribed_uris.add(node_uri)
                    try:
                        inject_file_map(
                            fm_page_path,
                            file_map,
                            preserved=preserved,
                        )
                        entities_file_mapped.append(node_uri)
                        file_mapped_pages.append((node_uri, node, fm_page_path))
                    except Exception as fm_exc:  # noqa: BLE001 — partial-success
                        file_map_errors.append(f"{node_uri}: inject_file_map failed: {fm_exc!r}")
            # Step 10b-ts: test-suite File-map injection — commit-gated parity
            # with Step 10b (M2c #4 §3.1). The suite map starts at the suite root
            # (node.path, authoritative — D1) and is UNPARTITIONED (every tracked
            # file under the root). Trigger is the suite slice of fm_targets so a
            # commit-dirty-but-structurally-unchanged suite is still re-injected;
            # the preserved-drop re-queues changed rows as `— TODO`, and
            # re-described suites join redescribed_uris for the unified stamp.
            # `not no_file_map` mirrors the package/app branch guard (D4 parity).
            if fm_targets and not no_file_map:
                for node in queries.list_test_suites(conn):
                    if not isinstance(node.attrs, dict):
                        continue
                    suite_uri = node.attrs.get("uri")
                    if not suite_uri or suite_uri not in fm_targets:
                        continue
                    suite_path = node.path
                    if not suite_path:
                        continue
                    block = build_dir_file_map(repo / suite_path, max_depth=max_depth)
                    if not block:
                        continue
                    ts_page_path = _entity_page_path(
                        wiki,
                        "test_suite",
                        node,
                        suite_uri,
                        fm_collision_set,
                    )
                    # PTO: live-source preserved descriptions from the suite page
                    # (mirrors Step 10b; the suite branch is at package parity).
                    preserved = dict(_live_file_map_descriptions(ts_page_path))
                    if narrate and suite_uri in commit_dirty:
                        changed = commit_dirty[suite_uri]
                        if changed is None:
                            # Unknown anchor: no preserved row can be trusted —
                            # drop all, forcing a full re-describe (D-D / §3.1).
                            preserved = {}
                            redescribed_uris.add(suite_uri)
                        else:
                            changed_rel = _changed_rel_paths(changed, suite_path)
                            dropped = {p for p in preserved if p in changed_rel}
                            if dropped:
                                for p in dropped:
                                    preserved.pop(p, None)
                                redescribed_uris.add(suite_uri)
                    try:
                        inject_file_map(
                            ts_page_path,
                            block,
                            preserved=preserved,
                        )
                        entities_file_mapped.append(suite_uri)
                        file_mapped_pages.append((suite_uri, node, ts_page_path))
                    except Exception as fm_exc:  # noqa: BLE001 — partial-success
                        file_map_errors.append(f"{suite_uri}: inject_file_map failed: {fm_exc!r}")
            if entities_file_mapped or file_map_errors:
                append_log(
                    wiki,
                    "scan",
                    (f"file maps injected: {len(entities_file_mapped)} (errors: {len(file_map_errors)})"),
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
                stack = _bedrock_stack()
                if stack is None:
                    describer_items = []
                else:
                    load_role_config_fn, make_llm_fn, subagent_pool_type, task_result_type = stack
                    describer_cfg = load_role_config_fn("code_reader")
                    describer_llm = make_llm_fn("code_reader")
                    describer_pool = subagent_pool_type(trace_dir=graph_dir(wiki.parent) / "traces")

                    async def describe_files(
                        item: tuple[str, dict, Path, list[str]],
                    ) -> TaskResultType:
                        _uri, ws_dict_inner, _page, todo_inner = item
                        system_msg, human_msg = build_file_describer_prompt(ws_dict_inner, todo_inner, repo_root=repo)
                        resp = await describer_llm.ainvoke(
                            [
                                SystemMessage(content=system_msg),
                                HumanMessage(content=human_msg),
                            ]
                        )
                        return task_result_type(value=resp.content, response=resp)

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
                            describer_errors.append(f"{uri_inner}: fill_file_map_descriptions failed: {fill_exc!r}")
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

        package_reader_filled_uris: set[str] = set()
        package_reader_errors: list[str] = []
        if narrate:
            package_reader_candidates: dict[str, _PackageReaderCandidate] = dict(narrated_page_candidates)
            for uri_inner, node, page_path in file_mapped_pages:
                attrs = node.attrs if isinstance(node.attrs, dict) else {}
                _record_package_reader_candidate(
                    package_reader_candidates,
                    uri=uri_inner,
                    candidate=_PackageReaderCandidate(
                        page_path=page_path,
                        graph_path=node.path,
                        kind=node.kind,
                        name=node.name,
                        language=str(attrs.get("language") or "unknown"),
                    ),
                )
            if package_reader_candidates:
                package_reader_filled_uris, package_reader_errors = await _run_package_reader_pass(
                    wiki=wiki,
                    repo=repo,
                    conn=conn,
                    model_override=model_override,
                    candidate_pages=package_reader_candidates,
                )
                if package_reader_filled_uris or package_reader_errors:
                    append_log(
                        wiki,
                        "scan",
                        (
                            f"package-reader sections filled: {len(package_reader_filled_uris)} "
                            f"entity(s) (errors: {len(package_reader_errors)})"
                        ),
                        detail=None,
                        silent=True,
                        raise_exception=True,
                    )

        # M2c Part 3 (§3.3 D4): unified, refill-gated anchor stamping. A page
        # advances last_updated_commit to HEAD iff it was re-narrated with good
        # prose OR had a file-map row re-described this scan, AND no file-map
        # `— TODO` row remains. The single gate covers both stamp reasons:
        #   - good prose with an unrefilled dropped row → NOT stamped (stays
        #     commit-dirty; next scan retries the describe) — closes the residual;
        #   - a re-described page whose rows are all refilled → stamped
        #     (idempotence + cost-churn guard, preserves M2b);
        #   - a narrated-only page with no file-map TODO (file_map_todo_paths
        #     returns [] for pages with all rows filled or no File map section) →
        #     stamped, preserving M2a behavior.
        if narrate and head:
            stamp_page_paths: dict[str, Path] = dict(narrated_page_paths)
            for uri_inner, _node, page_path in file_mapped_pages:
                stamp_page_paths.setdefault(uri_inner, page_path)
            for uri_inner in good_prose_uris | redescribed_uris | package_reader_filled_uris:
                page_path = stamp_page_paths.get(uri_inner)
                if page_path is None:
                    continue
                try:
                    # The refill check + the stamp share the try so an
                    # unreadable/missing page is non-fatal (mirrors the old
                    # narrator-loop try block that wrapped the equivalent I/O).
                    if file_map_todo_paths(page_path):
                        continue
                    set_frontmatter_value(page_path, LAST_UPDATED_COMMIT_KEY, cast(str, short_head))
                except Exception as exc:  # noqa: BLE001 — non-fatal stamp
                    logger.warning("anchor stamp failed for %s: %s", uri_inner, exc)

        # Living Wiki M2e: human-section drift flagging post-pass. Runs after
        # anchor stamping so each page holds its final `## Narrative` and settled
        # human sections plus its freshly-stamped last_updated_commit. Gated on
        # `narrate` (needs the cheap-tier drift_judge LLM); self-recovers any page
        # whose drift pass was skipped in a prior scan (drift_checked_commit lag).
        if narrate:
            await _drift_flag_pass(wiki, model_override)

        # Free clear pass — runs every scan (even --no-narrate): a human edit to a
        # flagged section clears its flag promptly without an LLM call.
        _drift_clear_pass(wiki)

        # Living Wiki M4: opt-in cross-page drift producer. Runs after narration
        # (narratives fresh, last_updated_commit advanced) and reads M4's own
        # anchors off disk, so no in-memory state is threaded in. Gated on both
        # narrate (needs Bedrock) and the explicit flag (off by default, §3.7).
        if narrate and propagate_drift and conn is not None:
            await run_propagate_drift(wiki=wiki, repo=repo, conn=conn)

        # Step 12: regenerate indexes (Phase 45 D-01).
        # Order: graph-driven wiki/index.md → per-folder sub-indexes.
        if conn is not None:
            # generate_index is read-only on the graph; raises on failure (Phase 44 D-19).
            # Title the index with the wiki's human topic (manifest `topic`),
            # falling back to the wiki dir name for pre-topic workspaces.
            display_name = _manifest.read(manifest_path(wiki.parent)).get("topic")
            index_result = generate_index(conn, wiki, display_name)
            append_log(
                wiki,
                "scan",
                (f"index: wiki/index.md changed={index_result.changed} bytes={index_result.bytes_written}"),
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
            logger.warning("regenerate_referenced_in_wiki failed (non-fatal): %s", exc)

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
                entity_write_errors + narrator_errors + file_map_errors + describer_errors + package_reader_errors
            ),
        )
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass  # closing a read-only conn should not raise; defensive
