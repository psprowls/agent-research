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
from graph_io import GraphNotInitializedError, exit_codes, open_reader
from graph_io.tokens import count_tokens
from langchain_core.messages import HumanMessage, SystemMessage

# Bedrock fan-out stack — imported only for the narrated path (narrate=True).
# Guarded so the plugin's Claude branch (narrate=False) runs without these
# workspace members installed. When absent, the narrator/file-describer blocks
# are unreachable (gated on `narrate`), so the None bindings are never called.
try:
    from subagent_runtime.pool import FanOutResult, SubagentPool, TaskResult

    from graph_wiki_core.roles import load_role_config, make_llm
except ImportError:  # pragma: no cover — exercised by the lazy-import test via reload
    load_role_config = make_llm = None  # type: ignore[assignment]
    SubagentPool = TaskResult = FanOutResult = None  # type: ignore[assignment]

if TYPE_CHECKING:
    from subagent_runtime.pool import SubagentPool as SubagentPoolType
    from subagent_runtime.pool import TaskResult as TaskResultType

from wiki_io._workspace import resolve_wiki_and_repo
from wiki_io.append_log import append_log
from wiki_io.backlink_index import build_entity_backlink_map, regenerate_referenced_in_wiki
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
    dir_section_todo_contexts,
    extract_file_map_descriptions,
    extract_narrative,
    file_map_todo_paths,
    fill_dir_section_descriptions,
    fill_file_map_descriptions,
    fill_file_map_overview,
    inject_file_map,
    inject_narrative,
    is_overview_unfilled,
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
from wiki_io.proposals import HUMAN_DECIDED, list_proposals
from wiki_io.scan_monorepo import (
    build_dir_file_map,
    build_file_map,
    compute_state_gate,
)
from wiki_io.update_index import update_index
from wiki_io.update_tokens import update_vault
from workspace_io import manifest as _manifest
from workspace_io.paths import graph_dir, manifest_path

from graph_wiki_core.commands._reindex import regen_indexes_and_backlinks
from graph_wiki_core.commands._repo_gates import build_repo_paths, compute_state_gates, owning_repo
from graph_wiki_core.commands.graph import run_build as _cg_run_build
from graph_wiki_core.commands.package_reader import PackageReaderItem, run_package_reader
from graph_wiki_core.commands.propagate_drift import (
    DRIFT_PROPAGATED_COMMIT_KEY,
    _build_targets,
    _page_title,
    propagation_candidates,
    write_propagation_findings,
)
from graph_wiki_core.commands.scan_contract import (
    ApplyResult,
    DriftResultItem,
    DriftSectionInput,
    DriftTask,
    DriftVerdict,
    FillNeeds,
    FillResult,
    FillTask,
    PropagateEntity,
    PropagateFinding,
    PropagateResultItem,
    PropagateTask,
    ScanResults,
    ScanWorklist,
)
from graph_wiki_core.graph_tools import build_graph_tools
from graph_wiki_core.prompts.dir_describer import build_dir_describer_prompt, parse_dir_describer_output
from graph_wiki_core.prompts.drift_judge import (
    build_drift_judge_prompt,
    parse_drift_verdict,
)
from graph_wiki_core.prompts.drift_propagator import (
    build_drift_propagator_prompt,
    parse_drift_propagator_verdict,
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
    reader: Any | None,
    model_override: str | None,
    candidate_pages: dict[str, _PackageReaderCandidate],
) -> tuple[set[str], list[str]]:
    stack = _bedrock_stack()
    if stack is None:
        return set(), []
    load_role_config_fn, make_llm_fn, subagent_pool_type, task_result_type = stack

    graph_tools = build_graph_tools(reader) if reader is not None else []
    errors: list[str] = []
    items: list[tuple[str, Path, PackageReaderItem]] = []
    for uri, candidate in sorted(candidate_pages.items()):
        page_path = candidate.page_path
        try:
            post = frontmatter.load(str(page_path))
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
        if candidate.graph_path is None:
            errors.append(f"{uri}: package_reader missing graph path")
            continue
        graph_path = candidate.graph_path
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
    if existing is None or (existing.graph_path is None and candidate.graph_path is not None):
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


def _head_for_uri(uri: str, gates: dict, fallback: str | None) -> str | None:
    """Resolve the owning repo's ``head_commit`` for an entity URI.

    Parses ``'{org}/{repo}'`` from the URI (``_parse_repo_key``) and returns the
    matching gate's HEAD. When the workspace has exactly one member and the URI's
    repo key isn't in ``gates`` (e.g. a remote-URL key mismatch), the sole gate's
    HEAD is returned as a best-effort fallback. Otherwise — no key match with
    multiple gates, or empty ``gates`` (single-repo mode, ``gates == {}``) — the
    provided ``fallback`` is returned, keeping the single-repo path unchanged.

    Consumed by per-repo narrative/drift gating (Tasks 6/7).
    """
    from wiki_io.index_generator import _parse_repo_key

    key = _parse_repo_key(uri or "")
    if key and key in gates:
        return gates[key].get("head_commit")
    if len(gates) == 1:
        return next(iter(gates.values())).get("head_commit")
    return fallback


def _commit_dirty_changes(
    wiki: Path,
    repo: Path,
    reader: Any,
    head: str | None,
    collision_set: frozenset[str],
    gates: dict | None = None,
    repo_paths: dict[str, Path] | None = None,
) -> dict[str, list[str] | None]:
    """Map `package`/`app`/`test_suite`/`agent_plugin` URIs whose files changed since the commit
    recorded on their page (`last_updated_commit`) to the changed-file list.

    Keys are the dirty URIs (so ``result.keys()`` is the M2a "needs
    re-narration" set). Each value is the repo-relative list of files
    ``changed_files_since`` reported, or ``None`` when the anchor SHA is unknown
    to this repo (D-D self-correction). Pages WITHOUT an anchor are skipped
    (D-C). M2a used only the keys; M2b consumes the values to drop changed rows
    from the File-map ``preserved`` map (§3.1).

    ``gates`` is the multi-repo ``{repo-key -> gate}`` map. When non-empty the
    per-entity HEAD presence-guard is resolved from the owning repo's gate
    (``_head_for_uri``); when empty/None the single-repo ``head`` is used for
    every entity (unchanged behavior).

    Task 6: ``repo_paths`` (``{repo-key -> member checkout path}``) makes the
    dirty check per-owning-repo — a change in member B never flags member A's
    entities. The owning repo's checkout drives ``changed_files_since`` so the
    diff is computed against the repo that actually owns the entity. When
    ``repo_paths`` is empty/None (single-repo), every entity resolves to
    ``repo`` — byte-identical to pre-Task-6 behavior.
    """
    gates = gates or {}
    repo_paths = repo_paths or {}
    dirty: dict[str, list[str] | None] = {}
    if (head is None and not gates) or reader is None:
        return dirty
    list_fns = _kind_list_fns()
    for kind in ("package", "app", "test_suite", "agent_plugin"):
        list_fn = list_fns.get(kind)
        if list_fn is None:
            continue
        for node in list_fn(reader):
            if not isinstance(node.attrs, dict):
                continue
            uri = node.attrs.get("uri")
            node_path = node.path
            if not uri or not node_path:
                continue
            # Owning repo HEAD: in multi-repo this is the entity's member-repo
            # HEAD (and a None means the URI resolves to a repo with no gate
            # entry -> skip). No-op for single-repo (gates == {} -> returns
            # `head`, never None here).
            owning_head = _head_for_uri(uri, gates, head)
            if owning_head is None:
                continue
            # Owning repo checkout path: in multi-repo the member that owns this
            # URI; single-repo (empty repo_paths) falls back to `repo`.
            owning_repo_path = owning_repo(uri, repo, repo_paths)
            page_path = _entity_page_path(wiki, kind, node, uri, collision_set)
            if not page_path.exists():
                continue
            try:
                anchor = frontmatter.load(str(page_path)).metadata.get(LAST_UPDATED_COMMIT_KEY)
            except Exception:  # noqa: BLE001 — a malformed page must not abort scan
                continue
            if not anchor:
                continue
            changed = changed_files_since(owning_repo_path, str(anchor), node_path)
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
# Living Wiki M1.5 (split scan pipeline): emit-half worklist assembly
# ---------------------------------------------------------------------------


def _build_drift_tasks(wiki: Path) -> list[DriftTask]:
    """Serialize M2e drift candidates into DriftTasks (emit-time ground truth).

    Mirror of _drift_flag_pass's candidate+item assembly minus the LLM judge.
    Each candidate page becomes one DriftTask carrying its regenerated narrative,
    file map, and every human section chunk. The uri is read from frontmatter so
    apply can key verdicts back to the page.
    """
    tasks: list[DriftTask] = []
    for page_path, anchor, narrative, file_map in _drift_candidates(wiki):
        try:
            uri = frontmatter.load(str(page_path)).metadata.get("uri")
        except Exception:  # noqa: BLE001 — a malformed page must not abort scan
            continue
        if not uri:
            continue
        body = page_path.read_text(encoding="utf-8")
        sections = [DriftSectionInput(heading=heading, chunk=chunk) for heading, chunk in iter_human_sections(body)]
        if not sections:
            continue
        tasks.append(
            DriftTask(
                uri=str(uri),
                page_path=str(page_path),
                anchor=anchor,
                narrative=narrative,
                file_map=file_map,
                sections=sections,
            )
        )
    return tasks


def _build_propagate_tasks(
    wiki: Path, repo: Path, reader: Any, repo_paths: dict[str, Path] | None = None
) -> tuple[list[PropagateTask], dict[str, str], dict[str, str]]:
    """M4 emit: curated propagate targets + per-candidate stamp bookkeeping.

    Reuses propagate_drift's candidate/target/title machinery with the ledger
    pre-filter (skip targets the human already disposed of). Returns the tasks
    plus ``(anchors, pages)`` mapping EVERY considered candidate's uri to its
    ``last_updated_commit`` / entity page_path — apply stamps
    ``drift_propagated_commit`` for all of them (idempotence), including
    candidates whose targets were all pre-filtered.
    """
    candidates = propagation_candidates(wiki, repo, reader, repo_paths=repo_paths)
    if not candidates:
        return [], {}, {}
    targets = _build_targets(candidates, build_entity_backlink_map(wiki))
    settled = {(rec["kind"], rec["target_slug"]) for rec in list_proposals(wiki) if rec["status"] in HUMAN_DECIDED}
    tasks: list[PropagateTask] = []
    for entry in targets.values():
        if (entry["kind"], entry["target_slug"]) in settled:
            continue  # ledger pre-filter
        title = _page_title(entry["page_path"], entry["target_slug"])
        tasks.append(
            PropagateTask(
                kind=entry["kind"],
                target_slug=entry["target_slug"],
                title=title,
                page_path=str(entry["page_path"]),
                entities=[
                    PropagateEntity(stem=c.stem, narrative=c.narrative, changed_files=c.changed_files)
                    for c in entry["candidates"]
                ],
            )
        )
    anchors = {c.uri: c.last_updated_commit for c in candidates}
    pages = {c.uri: str(c.page_path) for c in candidates}
    return tasks, anchors, pages


async def build_scan_worklist(
    workspace_path: Path | None = None,
    *,
    repo_path: Path | None = None,
    no_file_map: bool = False,
    max_depth: int = 3,
    propagate_drift: bool = False,
) -> tuple[ScanWorklist, ScanResult]:
    """Mechanical front-half of a narrated scan + the commit-gated worklist.

    Side effects (identical to run_scan's narrate=True front-half): cg update,
    write_entities, deterministic file-map injection. Returns the worklist the
    provider fills plus a ScanResult carrying created/updated/deleted/errors so
    callers can still report the mechanical pass. The preserved-drop runs
    unconditionally here (this is always the narrating path).
    """
    # Step 1: resolve wiki and repo (lifted from run_scan).
    wiki, resolved_repo = resolve_wiki_and_repo(workspace_path)
    if repo_path is not None:
        repo = repo_path.resolve()
    elif resolved_repo is not None:
        repo = resolved_repo
    else:
        repo = Path.cwd()

    # cg update + open the read-only graph reader (lifted; ScanAbortedError kept).
    # reader is closed right before return; exceptions propagate (no try/finally).
    reader = None
    append_log(
        wiki,
        "scan",
        "cg update (incremental)",
        detail=None,
        silent=True,
        raise_exception=True,
    )
    _workspace_root = wiki.parent
    _cg_exit, _cg_stdout, _cg_stderr = _cg_run_build(repo, _workspace_root, full=False, scope_to_repo=False)
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
        append_log(
            wiki,
            "scan",
            f"cg update failed: exit_code={_cg_exit}",
            detail=None,
            silent=True,
            raise_exception=True,
        )
        raise ScanAbortedError(exit_code=_cg_exit, stderr=_cg_stderr)

    if _graph_ready:
        try:
            reader = open_reader(wiki.parent)
        except GraphNotInitializedError as exc:
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
            reader = None

    try:
        return await _build_scan_worklist_body(
            wiki=wiki,
            repo=repo,
            reader=reader,
            no_file_map=no_file_map,
            max_depth=max_depth,
            propagate_drift=propagate_drift,
        )
    finally:
        if reader is not None:
            try:
                reader.close()
            except Exception:  # noqa: BLE001 — closing a read-only reader should not raise
                pass


async def _build_scan_worklist_body(
    *,
    wiki: Path,
    repo: Path,
    reader: Any | None,
    no_file_map: bool,
    max_depth: int,
    propagate_drift: bool,
) -> tuple[ScanWorklist, ScanResult]:
    """Worklist assembly body (split out so build_scan_worklist's reader is closed
    in a finally even when write_entities / file-map injection raises)."""
    # Step 8: compute state gate.
    state_gate = compute_state_gate(repo, workspace=wiki.parent)
    head = state_gate.get("head_commit")
    short_head = short_commit(repo, head) if head else head

    # Multi-repo per-repo state-gate map: one HEAD per workspace member, keyed by
    # '{org}/{repo}'. Single-repo workspaces have no members → `gates == {}` and
    # downstream gating uses the single-repo `head`/`state_gate` unchanged. Tasks
    # 6/7 consume `gates` (via `_head_for_uri`) for per-repo narrative-refresh and
    # drift gating.
    from workspace_io.config import resolve as _resolve_cfg

    members = list(_resolve_cfg(repo, require_manifest=False).members)
    # `repo_paths` (repo-key -> member checkout path) drives the per-entity dirty
    # diff and the apply-phase anchor stamp; empty for single-repo so both fall
    # back to the single-repo `repo`/`head`. Per-entity HEAD gating reads `gates`.
    repo_paths: dict[str, Path] = {}
    if members:
        gates = compute_state_gates(members, workspace=wiki.parent)
        repo_paths = build_repo_paths(members)
    else:
        gates = {}

    entity_write_result = None
    commit_dirty: dict[str, list[str] | None] = {}

    if reader is not None:
        # Step 9a: graph-driven entity page writes.
        entity_write_result = write_entities(reader, wiki, ADMITTED_KINDS)
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

        # M2a commit-gate: re-narrate entities whose files changed since their
        # recorded last_updated_commit. Decision A: the needs_narrative set
        # (which the worklist consumes) includes this commit_dirty union.
        commit_dirty = _commit_dirty_changes(
            wiki,
            repo,
            reader,
            head,
            _compute_collision_set(reader, ADMITTED_KINDS, _kind_list_fns()),
            gates=gates,
            repo_paths=repo_paths,
        )
        if commit_dirty:
            entity_write_result.needs_narrative.update(commit_dirty.keys())
            append_log(
                wiki,
                "scan",
                f"commit-gate: {len(commit_dirty)} entity(s) flagged for re-narration",
                detail=None,
                silent=True,
                raise_exception=True,
            )

    # Step 10b: deterministic File-map injection. Same as run_scan's port, but
    # the preserved-drop runs UNCONDITIONALLY here (this is always the narrating
    # front-half) — `if narrate and node_uri in commit_dirty` -> `if node_uri in commit_dirty`.
    entities_file_mapped: list[str] = []
    file_map_errors: list[str] = []
    file_mapped_pages: list[tuple[str, Any, Path]] = []
    redescribed_uris: set[str] = set()
    if entity_write_result is not None and reader is not None:
        refreshed = set(entity_write_result.created) | set(entity_write_result.updated)
        fm_targets = refreshed | set(commit_dirty)
        list_fns = _kind_list_fns()
        fm_collision_set = _compute_collision_set(reader, ADMITTED_KINDS, list_fns) if fm_targets else frozenset()
        fm_list_fns = [list_fns.get("package"), list_fns.get("app")]
        if fm_targets and any(fm_list_fns) and not no_file_map:
            fm_nodes = [n for fn in fm_list_fns if fn for n in fn(reader)]
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
                preserved = dict(_live_file_map_descriptions(fm_page_path))
                if node_uri in commit_dirty:
                    changed = commit_dirty[node_uri]
                    if changed is None:
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
        # Step 10b-ts: test-suite File-map injection (preserved-drop unconditional).
        if fm_targets and not no_file_map:
            for node in reader.list_test_suites():
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
                preserved = dict(_live_file_map_descriptions(ts_page_path))
                if suite_uri in commit_dirty:
                    changed = commit_dirty[suite_uri]
                    if changed is None:
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

    # --- Build the worklist from the in-memory sets ---
    needs_narr_set: set[str] = set(entity_write_result.needs_narrative) if entity_write_result else set()

    fill_tasks: list[FillTask] = []
    if reader is not None and entity_write_result is not None:
        list_fns = _kind_list_fns()
        page_path_by_uri: dict[str, Path] = {uri: pp for uri, _node, pp in file_mapped_pages}
        node_by_uri: dict[str, Any] = {uri: node for uri, node, _pp in file_mapped_pages}
        # Resolve any narrative-needing entity not already in file_mapped_pages
        # (e.g. agent_plugin / domain — narrative-only, no deterministic file map).
        if needs_narr_set - page_path_by_uri.keys():
            collision = _compute_collision_set(reader, ADMITTED_KINDS, list_fns)
            for kind in sorted(ADMITTED_KINDS):
                fn = list_fns.get(kind)
                if fn is None:
                    continue
                for node in fn(reader):
                    if not isinstance(node.attrs, dict):
                        continue
                    uri = node.attrs.get("uri")
                    if uri and uri in needs_narr_set and uri not in page_path_by_uri:
                        page_path_by_uri[uri] = _entity_page_path(wiki, kind, node, uri, collision)
                        node_by_uri[uri] = node

        candidate_uris = set(page_path_by_uri.keys()) | needs_narr_set
        for uri in sorted(candidate_uris):
            page_path = page_path_by_uri.get(uri)
            if page_path is None or not page_path.exists():
                continue
            node = node_by_uri.get(uri)
            kind = getattr(node, "kind", "") or ""
            name = getattr(node, "name", "") or page_path.stem
            graph_path = getattr(node, "path", "") or ""
            attrs = node.attrs if (node is not None and isinstance(node.attrs, dict)) else {}
            language = str(attrs.get("language") or "unknown")
            page_text = page_path.read_text(encoding="utf-8", errors="replace")
            todo_sections = find_todo_human_sections(page_text, entity_kind=kind) if kind else []
            # find_todo_human_sections returns BARE headings (the "## " prefix is
            # stripped — human_sections.py:52), matching how run_scan's package
            # reader keys requested_sections on section.heading.
            todo_headings = {s.heading for s in todo_sections}
            needs = FillNeeds(
                # decision A: placeholder OR commit-dirty (uri in needs_narr_set).
                narrative=(extract_narrative(page_text) is None) or (uri in needs_narr_set),
                file_todo_paths=file_map_todo_paths(page_path),
                dir_todo_contexts=dir_section_todo_contexts(page_path),
                overview=is_overview_unfilled(page_path),
                purpose="Purpose" in todo_headings,
                public_api="Public API" in todo_headings,
            )
            if not needs.any:
                continue
            # Owning member-repo short HEAD for the apply-phase anchor stamp.
            # Multi-repo: the entity's member HEAD (per its repo path); single-
            # repo (empty maps): None -> apply falls back to worklist short_head.
            owning_short_head: str | None = None
            if repo_paths:
                owning_head = _head_for_uri(uri, gates, head)
                if owning_head:
                    owning_short_head = short_commit(owning_repo(uri, repo, repo_paths), owning_head)
            fill_tasks.append(
                FillTask(
                    uri=uri,
                    kind=kind,
                    name=name,
                    page_path=str(page_path),
                    graph_path=graph_path,
                    language=language,
                    needs=needs,
                    owning_short_head=owning_short_head,
                )
            )

    drift_tasks = _build_drift_tasks(wiki)
    propagate_tasks, propagate_anchors, propagate_pages = (
        _build_propagate_tasks(wiki, repo, reader, repo_paths=repo_paths)
        if (propagate_drift and reader is not None)
        else ([], {}, {})
    )

    worklist = ScanWorklist(
        head_commit=head,
        short_head=short_head,
        fill_tasks=fill_tasks,
        drift_tasks=drift_tasks,
        propagate_tasks=propagate_tasks,
        propagate_anchors=propagate_anchors,
        propagate_pages=propagate_pages,
    )
    scan_result = ScanResult(
        state_gate=state_gate,
        entities_created=sorted(entity_write_result.created) if entity_write_result else [],
        entities_updated=sorted(entity_write_result.updated) if entity_write_result else [],
        entities_deleted=sorted(entity_write_result.deleted) if entity_write_result else [],
        # Surface deterministic file-map injection failures alongside entity-write
        # errors so partial-success reporting matches the pre-split narrate path.
        entity_errors=([repr(e) for e in entity_write_result.errors] if entity_write_result else []) + file_map_errors,
    )
    return worklist, scan_result


# ---------------------------------------------------------------------------
# Living Wiki M1.5 (split scan pipeline): in-process Bedrock provider
# ---------------------------------------------------------------------------


async def _bedrock_provider(
    worklist: ScanWorklist,
    wiki: Path,
    repo: Path,
    *,
    model_override: str | None = None,
    propagate: bool = False,
) -> ScanResults:
    """Turn a ScanWorklist into ScanResults via the in-process Bedrock fan-outs.

    Lifts run_scan's narrator / code_reader / synthesizer / package_reader /
    drift_judge blocks, but each fan-out writes into a FillResult / DriftResultItem
    keyed by uri instead of injecting into the page. The prompts, parsers, and
    run_all role/item shapes are byte-identical to the old in-line blocks (the
    test spies that intercept SubagentPool.run_all observe the same tuples).

    package_reader is the one exception: it still writes human sections to disk
    via _run_package_reader_pass (its replacements are not threaded through
    FillResult for the in-process surface — apply's stamp gate reads the result
    off disk). Its errors are surfaced via `results.provider_errors`, which
    run_scan merges into the ScanResult so partial-success reporting is unchanged.
    """
    results = ScanResults()
    provider_errors: list[str] = []
    fills_by_uri: dict[str, FillResult] = {}

    def _fill(uri: str) -> FillResult:
        f = fills_by_uri.get(uri)
        if f is None:
            f = FillResult(uri=uri)
            fills_by_uri[uri] = f
        return f

    stack = _bedrock_stack()

    # Open a read-only reader for narrator relations / agent_plugin tables and the
    # package_reader graph-tools. Closed in finally. The open mirrors run_scan's
    # `if reader is not None` gating: on a NOT_INITIALIZED fallback the graph DB
    # was never written, so open_reader raises GraphNotInitializedError and we
    # proceed reader-less.
    reader = None
    try:
        try:
            reader = open_reader(wiki.parent)
        except GraphNotInitializedError:
            reader = None

        narrative_uris = {t.uri for t in worklist.fill_tasks if t.needs.narrative}

        # --- Narrator fan-out (role="narrator") ---
        if stack is not None and reader is not None and narrative_uris:
            load_role_config_fn, make_llm_fn, subagent_pool_type, task_result_type = stack
            narrator_items: list[tuple[str, str, Any]] = []
            list_fns = _kind_list_fns()
            for kind in sorted(ADMITTED_KINDS):
                list_fn = list_fns.get(kind)
                if list_fn is None:
                    continue
                for node in list_fn(reader):
                    if not isinstance(node.attrs, dict):
                        continue
                    node_uri = node.attrs.get("uri")
                    if node_uri and node_uri in narrative_uris:
                        narrator_items.append((node_uri, kind, node))

            if narrator_items:
                narrator_cfg = load_role_config_fn("narrator")
                narrator_llm = make_llm_fn("narrator", model_override=model_override)
                narrator_pool = subagent_pool_type(trace_dir=graph_dir(wiki.parent) / "traces")

                async def generate_narrative(item: tuple[str, str, Any]) -> TaskResultType:
                    uri_inner, kind_inner, node_inner = item
                    relations = scanner_frontmatter_for_node(reader, kind_inner, node_inner)
                    relations_for_prompt = {k: v for k, v in relations.items() if k not in ("uri", "kind")}
                    file_map = ""
                    components_text = ""
                    if kind_inner == "agent_plugin":
                        tv = _agent_plugin_table_variables(reader, node_inner)
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
                    msgs = [SystemMessage(content=system_msg), HumanMessage(content=human_msg)]
                    resp = await narrator_llm.ainvoke(msgs)
                    return task_result_type(value=resp.content, response=resp)

                narrator_result = await narrator_pool.run_all(
                    items=narrator_items,
                    task=generate_narrative,
                    role="narrator",
                    model_id=narrator_cfg["model_id"],
                    max_concurrency=narrator_cfg["max_concurrency"],
                )
                for item, prose in narrator_result.successes:
                    uri_inner, _kind_inner, _node_inner = item
                    _fill(uri_inner).narrative = prose
                for err in narrator_result.errors:
                    uri_inner = err.item[0]
                    provider_errors.append(f"{uri_inner}: {err.exception!r}")

        # --- code_reader fan-out (role="code_reader") — file-map descriptions ---
        describer_items: list[tuple[str, dict, Path, list[str]]] = []
        for task in worklist.fill_tasks:
            todo_paths = list(task.needs.file_todo_paths)
            if not todo_paths:
                continue
            ws_dict = {
                "name": task.name,
                "path": task.graph_path,
                "type": task.kind,
                "language": task.language,
            }
            describer_items.append((task.uri, ws_dict, Path(task.page_path), todo_paths))

        if stack is not None and describer_items:
            load_role_config_fn, make_llm_fn, subagent_pool_type, task_result_type = stack
            describer_cfg = load_role_config_fn("code_reader")
            describer_llm = make_llm_fn("code_reader")
            describer_pool = subagent_pool_type(trace_dir=graph_dir(wiki.parent) / "traces")

            async def describe_files(item: tuple[str, dict, Path, list[str]]) -> TaskResultType:
                _uri, ws_dict_inner, _page, todo_inner = item
                system_msg, human_msg = build_file_describer_prompt(ws_dict_inner, todo_inner, repo_root=repo)
                resp = await describer_llm.ainvoke([SystemMessage(content=system_msg), HumanMessage(content=human_msg)])
                return task_result_type(value=resp.content, response=resp)

            describer_result = await describer_pool.run_all(
                items=describer_items,
                task=describe_files,
                role="code_reader",
                model_id=describer_cfg["model_id"],
                max_concurrency=describer_cfg["max_concurrency"],
            )
            described_entities = 0
            describer_errors = 0
            for item, value in describer_result.successes:
                uri_inner = item[0]
                descriptions = parse_file_describer_output(value)
                if descriptions:
                    _fill(uri_inner).file_descriptions.update(descriptions)
                    described_entities += 1
            for err in describer_result.errors:
                uri_inner = err.item[0]
                provider_errors.append(f"{uri_inner}: {err.exception!r}")
                describer_errors += 1
            if described_entities or describer_errors:
                append_log(
                    wiki,
                    "scan",
                    f"file descriptions filled: {described_entities} entity(s) (errors: {describer_errors})",
                    detail=None,
                    silent=True,
                    raise_exception=True,
                )

        # --- synthesizer fan-out (role="synthesizer") — dir sections + overview ---
        dir_items: list[tuple[str, str, Path, list[str], bool]] = []
        for task in worklist.fill_tasks:
            todo_ctxs = list(task.needs.dir_todo_contexts)
            needs_ov = task.needs.overview
            if not todo_ctxs and not needs_ov:
                continue
            dir_items.append((task.uri, task.name, Path(task.page_path), todo_ctxs, needs_ov))

        if stack is not None and dir_items:
            load_role_config_fn, make_llm_fn, subagent_pool_type, task_result_type = stack
            dir_cfg = load_role_config_fn("synthesizer")
            dir_llm = make_llm_fn("synthesizer")
            dir_pool = subagent_pool_type(trace_dir=graph_dir(wiki.parent) / "traces")

            async def describe_dirs(item: tuple[str, str, Path, list[str], bool]) -> TaskResultType:
                _uri, pkg_name_inner, page_inner, todo_ctxs_inner, needs_ov_inner = item
                file_descs = extract_file_map_descriptions(page_inner)
                pkg = {"name": pkg_name_inner}
                system_msg, human_msg = build_dir_describer_prompt(pkg, todo_ctxs_inner, file_descs, needs_ov_inner)
                resp = await dir_llm.ainvoke([SystemMessage(content=system_msg), HumanMessage(content=human_msg)])
                return task_result_type(value=resp.content, response=resp)

            dir_result = await dir_pool.run_all(
                items=dir_items,
                task=describe_dirs,
                role="synthesizer",
                model_id=dir_cfg["model_id"],
                max_concurrency=dir_cfg["max_concurrency"],
            )
            for item, value in dir_result.successes:
                uri_inner = item[0]
                descriptions = parse_dir_describer_output(value)
                if not descriptions:
                    continue
                overview = descriptions.pop("_overview", None)
                fill = _fill(uri_inner)
                if descriptions:
                    fill.dir_descriptions.update(descriptions)
                if overview:
                    fill.overview = overview
            for err in dir_result.errors:
                uri_inner = err.item[0]
                provider_errors.append(f"{uri_inner}: {err.exception!r}")

        # --- package_reader pass (role="package_reader") — writes human sections to disk ---
        if stack is not None:
            package_reader_candidates: dict[str, _PackageReaderCandidate] = {}
            for task in worklist.fill_tasks:
                _record_package_reader_candidate(
                    package_reader_candidates,
                    uri=task.uri,
                    candidate=_PackageReaderCandidate(
                        page_path=Path(task.page_path),
                        graph_path=task.graph_path,
                        kind=task.kind,
                        name=task.name,
                        language=task.language,
                    ),
                )
            if package_reader_candidates:
                _pr_filled, _pr_errors = await _run_package_reader_pass(
                    wiki=wiki,
                    repo=repo,
                    reader=reader,
                    model_override=model_override,
                    candidate_pages=package_reader_candidates,
                )
                provider_errors.extend(_pr_errors)

        # --- drift_judge fan-out (role="drift_judge") — emit-time ground truth ---
        if stack is not None and worklist.drift_tasks:
            load_role_config_fn, make_llm_fn, subagent_pool_type, task_result_type = stack
            # item = (page_path, anchor, heading, chunk, narrative, file_map) —
            # identical to _drift_flag_pass so the spies' verdict_fn(it) works.
            drift_items: list[tuple[Path, str, str, str, str, str | None]] = []
            for dtask in worklist.drift_tasks:
                page_path = Path(dtask.page_path)
                for section in dtask.sections:
                    drift_items.append(
                        (page_path, dtask.anchor, section.heading, section.chunk, dtask.narrative, dtask.file_map)
                    )

            if drift_items:
                drift_cfg = load_role_config_fn("drift_judge")
                drift_llm = make_llm_fn("drift_judge", model_override=model_override)
                drift_pool = subagent_pool_type(trace_dir=graph_dir(wiki.parent) / "traces")

                async def judge(item: tuple) -> TaskResultType:
                    _pp, _anchor, heading, chunk, narrative, file_map = item
                    system_msg, human_msg = build_drift_judge_prompt(heading, chunk, narrative, file_map)
                    resp = await drift_llm.ainvoke([SystemMessage(content=system_msg), HumanMessage(content=human_msg)])
                    return task_result_type(value=parse_drift_verdict(resp.content), response=resp)

                fan = await drift_pool.run_all(
                    items=drift_items,
                    task=judge,
                    role="drift_judge",
                    model_id=drift_cfg["model_id"],
                    max_concurrency=drift_cfg["max_concurrency"],
                )
                drift_by_uri: dict[str, DriftResultItem] = {}
                task_uri_by_page = {Path(d.page_path): d.uri for d in worklist.drift_tasks}
                for item, verdict in fan.successes:
                    page_path, _anchor, heading, _chunk, _narr, _fmp = item
                    uri = task_uri_by_page.get(page_path)
                    if uri is None:
                        continue
                    if not isinstance(verdict, dict):
                        continue
                    item_out = drift_by_uri.setdefault(uri, DriftResultItem(uri=uri))
                    item_out.verdicts.append(
                        DriftVerdict(
                            section=heading.removeprefix("## ").strip(),
                            stale=bool(verdict.get("stale")),
                            reason=str(verdict.get("reason", "")),
                        )
                    )
                results.drift = list(drift_by_uri.values())

        # --- drift_propagator fan-out (role="drift_propagator") — M4, opt-in ---
        if propagate and stack is not None and worklist.propagate_tasks:
            load_role_config_fn, make_llm_fn, subagent_pool_type, task_result_type = stack
            # item = (kind, target_slug, title, body, entity_tuples) — mirrors
            # run_propagate_drift's judge half (entity_tuples = (stem, narrative, files)).
            prop_items: list[tuple[str, str, str, str, list[tuple[str, str, list[str]]]]] = []
            for ptask in worklist.propagate_tasks:
                body = Path(ptask.page_path).read_text(encoding="utf-8")
                entity_tuples = [(e.stem, e.narrative, e.changed_files) for e in ptask.entities]
                prop_items.append((ptask.kind, ptask.target_slug, ptask.title, body, entity_tuples))

            if prop_items:
                prop_cfg = load_role_config_fn("drift_propagator")
                prop_llm = make_llm_fn("drift_propagator", model_override=model_override)
                prop_pool = subagent_pool_type(trace_dir=graph_dir(wiki.parent) / "traces")

                async def judge_propagate(item: tuple) -> TaskResultType:
                    kind_inner, _slug, title, body, entity_tuples = item
                    system_msg, human_msg = build_drift_propagator_prompt(kind_inner, title, body, entity_tuples)
                    resp = await prop_llm.ainvoke([SystemMessage(content=system_msg), HumanMessage(content=human_msg)])
                    return task_result_type(value=parse_drift_propagator_verdict(resp.content), response=resp)

                fan = await prop_pool.run_all(
                    items=prop_items,
                    task=judge_propagate,
                    role="drift_propagator",
                    model_id=prop_cfg["model_id"],
                    max_concurrency=prop_cfg["max_concurrency"],
                )
                propagate_results: list[PropagateResultItem] = []
                for item, verdict in fan.successes:
                    kind_inner, slug, _title, _body, _entity_tuples = item
                    if not (isinstance(verdict, dict) and verdict.get("stale")):
                        continue
                    findings = [
                        PropagateFinding(
                            entity_stem=str(f.get("entity_stem", "")),
                            claim=str(f.get("stale_claim", "")),
                            reason=str(f.get("rationale", "")),
                        )
                        for f in (verdict.get("findings") or [])
                        if str(f.get("entity_stem", "")).strip()
                    ]
                    if findings:
                        propagate_results.append(
                            PropagateResultItem(kind=kind_inner, target_slug=slug, stale=True, findings=findings)
                        )
                results.propagate = propagate_results
    finally:
        if reader is not None:
            try:
                reader.close()
            except Exception:  # noqa: BLE001
                pass

    results.fills = list(fills_by_uri.values())
    results.provider_errors = provider_errors
    return results


# ---------------------------------------------------------------------------
# Living Wiki M1.5 (split scan pipeline): apply-half (deterministic back-half)
# ---------------------------------------------------------------------------


def _apply_propagate_results(worklist: ScanWorklist, results: ScanResults, wiki: Path) -> int:
    """M4 apply: write one source:drift ledger origin per stale finding, then
    stamp ``drift_propagated_commit`` for every considered candidate (idempotence).

    Reuses ``write_propagation_findings`` so the proposals are byte-identical to
    ``run_propagate_drift``. detected_commit / page resolution come off the
    worklist's per-candidate ``propagate_anchors`` / ``propagate_pages`` (joined
    by uri); the entity narrative for the origin hash comes from the task's
    ``PropagateEntity``. Stamping covers ALL candidates — including those whose
    targets were all settled-filtered — so repeat runs are idempotent.
    """
    written = 0
    task_by_slug = {(t.kind, t.target_slug): t for t in worklist.propagate_tasks}
    # stem -> last_updated_commit (detected_commit), joined uri-wise from anchors+pages.
    anchor_by_stem: dict[str, str] = {}
    for uri, page_path in worklist.propagate_pages.items():
        anchor = worklist.propagate_anchors.get(uri)
        if anchor is not None:
            anchor_by_stem[Path(page_path).stem] = anchor

    for item in results.propagate:
        if not item.stale:
            continue
        task = task_by_slug.get((item.kind, item.target_slug))
        if task is None:
            continue
        narrative_by_stem = {e.stem: e.narrative for e in task.entities}
        finding_tuples: list[tuple[str, str, str, str]] = []
        for f in item.findings:
            if f.entity_stem not in narrative_by_stem:
                continue  # finding references an entity not in this target's batch
            detected_commit = anchor_by_stem.get(f.entity_stem, "")
            finding_tuples.append((f.entity_stem, f.reason, detected_commit, narrative_by_stem[f.entity_stem]))
        if finding_tuples:
            written += write_propagation_findings(wiki, item.kind, item.target_slug, task.title, finding_tuples)

    # Stamp drift_propagated_commit for every considered candidate (idempotence).
    for uri, anchor in worklist.propagate_anchors.items():
        page_path = worklist.propagate_pages.get(uri)
        if page_path is None:
            continue
        try:
            update_frontmatter(Path(page_path), {DRIFT_PROPAGATED_COMMIT_KEY: anchor})
        except Exception as exc:  # noqa: BLE001 — non-fatal stamp
            logger.warning("drift_propagated stamp failed for %s: %s", uri, exc)
    return written


async def apply_scan_results(
    worklist: ScanWorklist,
    results: ScanResults,
    wiki: Path,
    repo: Path,
    *,
    propagate: bool = False,
) -> ApplyResult:
    """Deterministic back-half: inject results, stamp, write drift, regen indexes.

    Disk-driven + results-driven. Recomputes the M2c no-`— TODO` stamp gate from
    disk, so the only state crossing the process boundary is short_head and the
    per-page results. Every inject/fill/write is wrapped so one bad entity is
    isolated (mirrors Bedrock per-item try/except).
    """
    out = ApplyResult()
    fills_by_uri = {f.uri: f for f in results.fills}
    drift_by_uri = {d.uri: d for d in results.drift}
    task_by_uri = {t.uri: t for t in worklist.fill_tasks}
    short_head = worklist.short_head
    head = worklist.head_commit

    # --- Inject fills ---
    for uri, fill in fills_by_uri.items():
        task = task_by_uri.get(uri)
        if task is None:
            continue  # result references an entity not in this worklist — skip
        page_path = Path(task.page_path)
        try:
            if fill.narrative and fill.narrative.strip():
                inject_narrative(page_path, fill.narrative)
                out.narrated += 1
            if fill.file_descriptions:
                n = fill_file_map_descriptions(page_path, fill.file_descriptions)
                out.described += n
            if fill.dir_descriptions:
                n = fill_dir_section_descriptions(page_path, fill.dir_descriptions)
                out.dir_filled += n
            if fill.overview and fill.overview.strip():
                if fill_file_map_overview(page_path, fill.overview):
                    out.dir_filled += 1
            replacements: dict[str, str] = {}
            if fill.purpose and fill.purpose.strip():
                replacements["Purpose"] = fill.purpose
            if fill.public_api and fill.public_api.strip():
                replacements["Public API"] = fill.public_api
            if replacements:
                changed = replace_todo_human_sections(page_path, replacements)
                out.sections_filled += len(changed)
        except Exception as exc:  # noqa: BLE001 — partial-success isolation
            out.entity_errors.append(f"{uri}: apply fill failed: {exc!r}")

    # --- M2c refill-gated anchor stamp (decision A: also require non-placeholder narrative) ---
    if head:
        for uri, task in task_by_uri.items():
            page_path = Path(task.page_path)
            try:
                if not page_path.exists():
                    continue
                page_text = page_path.read_text(encoding="utf-8", errors="replace")
                if task.needs.narrative and extract_narrative(page_text) is None:
                    continue  # narrative still placeholder — failed narration, do not stamp
                if (
                    file_map_todo_paths(page_path)
                    or dir_section_todo_contexts(page_path)
                    or is_overview_unfilled(page_path)
                ):
                    continue
                # Task 6: stamp the OWNING member-repo short HEAD when present
                # (multi-repo, computed at emit time); single-repo falls back to
                # the worklist-wide short_head (byte-identical to pre-Task-6).
                stamp_head = task.owning_short_head or short_head
                set_frontmatter_value(page_path, LAST_UPDATED_COMMIT_KEY, cast(str, stamp_head))
                out.stamped += 1
            except Exception as exc:  # noqa: BLE001 — non-fatal stamp
                logger.warning("anchor stamp failed for %s: %s", uri, exc)

    # --- M2e drift flag WRITE (judge already done by the provider) ---
    for drift_task in worklist.drift_tasks:
        page_path = Path(drift_task.page_path)
        anchor = drift_task.anchor
        result_item = drift_by_uri.get(drift_task.uri)
        # Map verdicts by section name (without "## ") for hashing the current chunk.
        chunk_by_section = {s.heading.removeprefix("## ").strip(): s.chunk for s in drift_task.sections}
        entries: list[dict] = []
        if result_item is not None:
            for v in result_item.verdicts:
                if not v.stale:
                    continue
                chunk = chunk_by_section.get(v.section, "")
                entries.append(
                    {
                        "section": v.section,
                        "detected_commit": anchor,
                        "hash": section_hash(chunk),
                        "reason": v.reason,
                    }
                )
        try:
            if entries:
                update_frontmatter(page_path, {"drift_checked_commit": anchor, "drift_review": entries})
                out.drift_flagged += len(entries)
            else:
                update_frontmatter(page_path, {"drift_checked_commit": anchor}, delete=["drift_review"])
        except Exception as exc:  # noqa: BLE001 — non-fatal flag write
            logger.warning("drift flag write failed for %s: %s", page_path, exc)

    # --- Free every-scan clear pass ---
    _drift_clear_pass(wiki)

    # --- M4 propagate WRITE: ledger proposals + per-candidate idempotence stamp.
    # Runs whenever propagate is on and candidates were considered (anchors set) —
    # stamping must advance even when no target is stale.
    if propagate and worklist.propagate_anchors:
        out.propagated += _apply_propagate_results(worklist, results, wiki)

    # --- Index + backlink + log ---
    regen_indexes_and_backlinks(wiki)

    return out


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
        1. Resolve wiki and repo from workspace_path; run `cg update`, open reader.
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
    # Living Wiki M1.5: the narrated path now flows through the split contract —
    # build_scan_worklist (mechanical front-half) → in-process Bedrock provider →
    # apply_scan_results (deterministic back-half). The narrate=False structural-
    # only fast path below is unchanged (it runs without the Bedrock stack).
    if narrate:
        worklist, scan_result = await build_scan_worklist(
            workspace_path=workspace_path,
            repo_path=repo_path,
            no_file_map=no_file_map,
            max_depth=max_depth,
            propagate_drift=propagate_drift,
        )
        wiki, resolved_repo = resolve_wiki_and_repo(workspace_path)
        if repo_path is not None:
            repo = repo_path.resolve()
        elif resolved_repo is not None:
            repo = resolved_repo
        else:
            repo = Path.cwd()

        results = await _bedrock_provider(
            worklist, wiki, repo, model_override=model_override, propagate=propagate_drift
        )
        # Living Wiki M4: opt-in cross-page drift producer now flows through the
        # contract once — propagate_tasks (emit) → drift_propagator fan-out
        # (_bedrock_provider) → _apply_propagate_results (apply). No direct call.
        applied = await apply_scan_results(worklist, results, wiki, repo, propagate=propagate_drift)

        scan_result.entities_narrated = sorted(f.uri for f in results.fills if f.narrative and f.narrative.strip())
        scan_result.entity_errors = (
            list(scan_result.entity_errors) + list(results.provider_errors) + list(applied.entity_errors)
        )

        # Stamp `tokens` frontmatter on every page now that all writes are done.
        # Bedrock-only (CountTokens), so it runs solely on the narrated path — the
        # narrate=False plugin branch has no AWS access. Idempotent across re-scans.
        update_vault(wiki, count_tokens)

        entity_create_count = len(scan_result.entities_created)
        entity_update_count = len(scan_result.entities_updated)
        entity_delete_count = len(scan_result.entities_deleted)
        append_log(
            wiki,
            "scan",
            (
                f"scan complete: entities +{entity_create_count} ~{entity_update_count} "
                f"-{entity_delete_count}  (narrated: {len(scan_result.entities_narrated)})"
            ),
            detail=None,
            silent=True,
            raise_exception=True,
        )
        return scan_result

    # narrate=False: the structural-only fast path (unchanged behavior). It runs
    # without the Bedrock stack — entity pages keep their `## Narrative`
    # placeholder and `— TODO` rows; only the deterministic writes + drift clear
    # pass + indexes run.
    return await _run_scan_structural_only(
        workspace_path=workspace_path,
        no_file_map=no_file_map,
        max_depth=max_depth,
        repo_path=repo_path,
    )


async def _run_scan_structural_only(
    *,
    workspace_path: Path | None,
    no_file_map: bool,
    max_depth: int,
    repo_path: Path | None,
) -> ScanResult:
    """Structural-only scan (the former run_scan(narrate=False) body, verbatim
    minus the now-dead narrate-gated fan-out blocks).

    cg update → write_entities → deterministic file-map injection → free drift
    clear pass → indexes/backlinks. No narrator / code_reader / synthesizer /
    package_reader / drift_judge fan-outs and no anchor stamping (those live in
    the narrated path's _bedrock_provider + apply_scan_results). Runs without
    model_adapter / subagent_runtime installed.
    """
    # Step 1: resolve wiki and repo
    wiki, resolved_repo = resolve_wiki_and_repo(workspace_path)
    if repo_path is not None:
        repo = repo_path.resolve()
    elif resolved_repo is not None:
        repo = resolved_repo
    else:
        repo = Path.cwd()

    # Phase 39 D-05: single read-only reader for graph queries; closed in finally
    reader = None
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
        # the `.graph-wiki/` graph DB is written), not the wiki directory.
        # commands/graph.py (`_resolve_paths` → `cfg.workspace`) and the librarian
        # (`graph_dir(wiki.parent)` in commands/query.py) both use the workspace
        # root. We follow that convention here so the post-update
        # `open_reader(wiki.parent)` finds the DB the graph build just
        # created. (The plan's must_have says `workspace=wiki`; that is a
        # plan-spec drift — passing `wiki` makes the build write under
        # `<wiki>/.graph-wiki/` while the read path looks under
        # `<workspace>/.graph-wiki/`, so the reader open would fall through
        # to the post-update NOT_INITIALIZED fallback every time. See Phase
        # 39 SUMMARY's deviations section.)
        #
        # Phase 59 (59-02b): migrated off the deleted _build_namespace/_capture_run
        # shim onto the typed run_build core. update.run is silent on success, so
        # _cg_stdout is always "" here (sanctioned by D-06).
        _workspace_root = wiki.parent
        _cg_exit, _cg_stdout, _cg_stderr = _cg_run_build(repo, _workspace_root, full=False, scope_to_repo=False)
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

        # Phase 39 Step 1.6 (D-05): open the read-only graph reader ONCE on success.
        # wiki is workspace/wiki under the standard layout; .graph-wiki lives next to it
        # (mirrors the pattern in commands/query.py — librarian's graph-tools wiring).
        if _graph_ready:
            try:
                reader = open_reader(wiki.parent)
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
                reader = None

        # Step 8: compute state gate. `head` gates _commit_dirty_changes; no anchor
        # is stamped on the structural-only path (stamping is narrate-only).
        state_gate = compute_state_gate(repo, workspace=wiki.parent)
        head = state_gate.get("head_commit")

        # Step 9a: entity write only. The narrator fan-out (former Step 9b) lives
        # in the narrated path's _bedrock_provider — structural-only never narrates.
        entity_write_result = None
        # M2b: per-URI changed-file lists for commit-dirty package/app pages
        # (keys = dirty URIs; value = repo-relative changed paths, or None when
        # the page's anchor SHA is unknown to the repo). Consumed by Step 10b's
        # preserved-drop. Pre-initialized so the file-map block reads it safely
        # even when the graph reader is None.
        commit_dirty: dict[str, list[str] | None] = {}

        if reader is not None:
            # Step 9a: graph-driven entity page writes (Phase 43 write_entities).
            entity_write_result = write_entities(reader, wiki, ADMITTED_KINDS)
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
                reader,
                head,
                _compute_collision_set(reader, ADMITTED_KINDS, _kind_list_fns()),
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

        # Phase 45 D-07/D-08: Step 10 — inject narrator prose into entity pages.
        # The legacy `wiki/packages/<name>/<name>.md` write block is REMOVED (D-08
        # hard cutover — only entity pages are written from Phase 45 onward).
        # Phase 53 D-05: derive entity filenames via `short_filename` (mirroring
        # `write_entities`) so the inject-narrative path lines up with the file
        # that `write_entities` just produced.
        # Structural-only never narrates; these stay empty for the final result.
        entities_narrated: list[str] = []
        narrator_errors: list[str] = []

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
        describer_errors: list[str] = []
        # (uri, node, page_path) for each package/app whose File map was injected
        # this scan.
        file_mapped_pages: list[tuple[str, Any, Path]] = []
        if entity_write_result is not None and reader is not None:
            refreshed = set(entity_write_result.created) | set(entity_write_result.updated)
            # M2b §3.2 (load-bearing): a package whose source changed with no
            # structural delta is in commit_dirty but NOT refreshed; without this
            # union its File map is never re-injected and the preserved-drop below
            # can't fire. Mirrors M2a's needs_narrative.update(commit_dirty).
            fm_targets = refreshed | set(commit_dirty)
            list_fns = _kind_list_fns()
            # Collision set shared by the package/app and test-suite branches.
            fm_collision_set = _compute_collision_set(reader, ADMITTED_KINDS, list_fns) if fm_targets else frozenset()
            fm_list_fns = [list_fns.get("package"), list_fns.get("app")]
            if fm_targets and any(fm_list_fns) and not no_file_map:
                fm_nodes = [n for fn in fm_list_fns if fn for n in fn(reader)]
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
                    # filled rows are still on disk here. The commit-dirty
                    # preserved-drop is narrate-only and lives in the narrated
                    # front-half (build_scan_worklist).
                    preserved = dict(_live_file_map_descriptions(fm_page_path))
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
                for node in reader.list_test_suites():
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
                    # The commit-dirty preserved-drop is narrate-only (front-half).
                    preserved = dict(_live_file_map_descriptions(ts_page_path))
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

        # Steps 10c/10d (code_reader / synthesizer fan-outs), the package_reader
        # pass, the M2c refill-gated anchor stamp, the M2e drift judge, and the M4
        # producer are all narrate-only — they live in the narrated path's
        # _bedrock_provider + apply_scan_results and never ran here. Structural-only
        # keeps the deterministic file maps + the free drift clear pass + indexes.
        dir_describer_errors: list[str] = []
        package_reader_errors: list[str] = []

        # Free clear pass — runs every scan (even --no-narrate): a human edit to a
        # flagged section clears its flag promptly without an LLM call.
        _drift_clear_pass(wiki)

        # Step 12: regenerate indexes (Phase 45 D-01).
        # Order: graph-driven wiki/index.md → per-folder sub-indexes.
        if reader is not None:
            # generate_index is read-only on the graph; raises on failure (Phase 44 D-19).
            # Title the index with the wiki's human topic (manifest `topic`),
            # falling back to the wiki dir name for pre-topic workspaces.
            display_name = _manifest.read(manifest_path(wiki.parent)).get("topic")
            index_result = generate_index(reader, wiki, display_name)
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
                entity_write_errors
                + narrator_errors
                + file_map_errors
                + describer_errors
                + package_reader_errors
                + dir_describer_errors
            ),
        )
    finally:
        if reader is not None:
            try:
                reader.close()
            except Exception:
                pass  # closing a read-only reader should not raise; defensive


# ---------------------------------------------------------------------------
# Living Wiki M1.5: out-of-process entrypoints (Task 4)
# ---------------------------------------------------------------------------


async def emit_scan_worklist(
    *,
    workspace_path: Path | None,
    repo_path: Path | None,
    no_file_map: bool,
    max_depth: int,
    propagate: bool,
    out_path: Path,
) -> ScanResult:
    """Run the mechanical front-half, write worklist.json to out_path, return the ScanResult.

    Thin wrapper over build_scan_worklist for the out-of-process (Claude plugin) path.
    Creates parent directories as needed.
    """
    worklist, scan_result = await build_scan_worklist(
        workspace_path=workspace_path,
        repo_path=repo_path,
        no_file_map=no_file_map,
        max_depth=max_depth,
        propagate_drift=propagate,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(worklist.to_json(), encoding="utf-8")
    return scan_result


async def apply_scan_worklist(
    *,
    workspace_path: Path | None,
    repo_path: Path | None,
    results_path: Path,
    short_head: str | None,
    propagate: bool,
    worklist_path: Path,
) -> ApplyResult:
    """Read results.json + worklist.json, apply fill results, return ApplyResult.

    The worklist is read from disk (written by emit_scan_worklist) so the apply
    view is identical to the emit view — no second scan is needed. short_head is
    passed in to honor the state-gate decision made at emit time; it overrides the
    worklist's stored value (the only state crossing the process boundary).
    """
    results = ScanResults.from_json(results_path.read_text(encoding="utf-8"))
    worklist = ScanWorklist.from_json(worklist_path.read_text(encoding="utf-8"))
    # Honor the emit-time stamp value handed back by the orchestrator.
    worklist.short_head = short_head
    if short_head is None:
        worklist.head_commit = None
    wiki, resolved_repo = resolve_wiki_and_repo(workspace_path)
    repo = repo_path.resolve() if repo_path else (resolved_repo or Path.cwd())
    return await apply_scan_results(worklist, results, wiki, repo, propagate=propagate)
