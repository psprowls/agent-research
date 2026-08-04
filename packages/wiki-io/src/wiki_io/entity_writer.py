"""Entity writer — graph-driven entity page rendering for the wiki.

This module owns THREE contracts every downstream entity-writing phase
(43-46) depends on:

1. **URI-to-filename derivation (Phase 52 D-03..D-07; cleanup Phase 53 D-04..D-06).**
   `short_filename(uri, collision_set, ...)` is the pure function that maps a
   graph URI to a short, human-readable vault filename stem (e.g.
   `pkg_graph-io`, `dep_boto3`, `unit_tests_wiki-io`). Colliders across
   different URIs receive a deterministic `__<6hex>` sha256 disambiguator
   suffix. `_compute_collision_set` precomputes the colliding-URI set in a
   single graph pass; both `write_entities` and the index/link consumers
   thread that same set so every filename consumer agrees byte-for-byte on
   each entity's stem. The legacy bidirectional slug helpers were removed
   in Phase 53 — reverse lookups go through
   `frontmatter.load(entity_path).metadata["uri"]`.

2. **Data frontmatter whitelist.**
   `DATA_KEYS` is a flat frozenset enumerating every frontmatter key the
   scan regenerates from the graph on every run (full replacement; empty
   values omitted). Everything outside this set is preserved as-is when the
   scanner re-renders an entity page (`merge_frontmatter`); `summary` is a
   fill-when-empty special case.

   Human-only keys are NOT enumerated as a constant; the explicit examples
   documented for readers are: `status`, `last_reviewed`, `owner`, `notes`.
   A unit test asserts disjointness from these four. Provenance keys —
   `last_updated_commit` (the HEAD at which `## Narrative` was last
   regenerated) and `drift_propagated_commit` (the M4 drift-producer
   watermark), plus `content_hash` on curated pages — are scanner-stamped
   but NOT in `DATA_KEYS`: they must survive re-render.

3. **Two-class section model.**
   If the graph can compute a section, it is deterministic; if a model (or
   human) wrote it, it is prose. `DETERMINISTIC_SECTIONS` enumerates the
   deterministic H2 headings (`## File map` is matched by prefix via
   `_is_file_map_heading`). At merge time the six agent_plugin data tables
   (`_TEMPLATE_AUTHORITATIVE`) always take the fresh template render;
   `## Referenced in wiki` and `## File map` are carried from disk and
   refreshed by the always-run inject post-passes; every other H2 is prose,
   carried from disk verbatim. The `## Narrative` H2 string remains a hard
   convention — humans must not rename the heading.
"""

from __future__ import annotations

import hashlib

# Admitted entity kinds — the 6 graph-derived kinds the wiki materializes
# as standalone pages under `wiki/entities/`. Underscore-form per D-02 matches
# the graph store's `_VALID_KINDS` casing. Phase 43+ imports this constant when
# routing graph rows to the correct template / URI builder.
#
# Phase 51 PKGFAM-03 / D-04: the retired family-grouping kind is gone;
# this frozenset is complete and final (no subtraction-narrow). Re-
# introducing a family-like grouping is deferred (REQUIREMENTS.md
# "Future Requirements") and would build on domain-clustering primitives,
# not a separate kind.
#
# Phase 49 D-16: `builtin` is intentionally NOT admitted here. Stdlib modules
# are inspectable via `cg list-builtins` / `cg describe-builtin` but do not
# warrant standalone wiki pages — rendering one page per stdlib module would
# dilute the entity surface without meaningful documentation value.
#
# Phase 52 D-06: `app` is admitted alongside `package`. Apps are classified
# by Phase 50's pipeline (a package-like node that has an entry point /
# distribution / app-shape signal). The wiki renders apps as standalone
# entity pages so SC#1's literal `app_graph-wiki-agent.md` output can be
# produced from a real scan.
ADMITTED_KINDS: frozenset[str] = frozenset(
    {
        "repository",
        "package",
        "app",
        "agent_plugin",
        "dependency",
        "test_suite",
    }
)

# Map admitted kind names to their URI prefix as produced by the graph's URI
# builders. Two prefixes are shortened aliases of the kind name (`repository`
# -> `repo`, `package` -> `pkg`); the remaining four are identical.
#
# Phase 53 D-06: `_ADMITTED_URI_PREFIXES` was removed alongside the legacy
# bidirectional-slug machinery (its only consumer). The forward
# `short_filename` helper consumes `_FILENAME_PREFIX_BY_URI_PREFIX` directly,
# which is the only filename-layer prefix surface that remains.
_URI_PREFIX_BY_KIND: dict[str, str] = {
    "repository": "repo",
    "package": "pkg",
    "app": "app",
    "agent_plugin": "agent_plugin",
    # Phase 52 D-05: filename-layer alias only. Graph URIs (built by
    # the graph's `dependency_uri` builder) continue to use the `dependency:` prefix;
    # the short-form filename for dependency entities is `dep_<name>` and is
    # produced by `short_filename` via
    # `_FILENAME_PREFIX_BY_URI_PREFIX["dependency"] = "dep"`.
    "dependency": "dep",
    "test_suite": "test_suite",
}

# Frontmatter keys regenerated from the graph on every scan — full
# replacement from the scanner update; empty values omitted (see
# merge_frontmatter). Anything outside this set is preserved as-is when the
# scanner re-renders an entity page.
#
# Documented human-only keys (NOT in this whitelist; do not add):
#   - status, last_reviewed, owner, notes
# Preserved provenance keys (scanner-stamped, NOT in this whitelist):
#   - last_updated_commit, drift_propagated_commit
DATA_KEYS: frozenset[str] = frozenset(
    {
        # Universal
        "uri",
        "kind",
        "graph_name",
        "last_scan_at",
        # Edge-derived (package)
        "depends_on",
        "test_suites",
        "entry_points",
        # Node-attr-derived (package)
        "language",
        "version",
        # Node-attr-derived (app — Phase 52 D-06; mirrors package + app-specific keys)
        "app_kind",
        "app_signals",
        # Edge-derived (test_suite)
        "tested_packages",
        "suite_kind",
        "file_count",
        # Edge-derived (dependency)
        "ecosystem",
        "used_by",
        "versions_in_use",
        # Edge-derived (repository)
        "package_count",
    }
)


# ----------------------------------------------------------------------------
# Phase 52 D-03/D-04/D-05/D-07: short_filename pure helper (WIKI-FN-04)
# ----------------------------------------------------------------------------

# Filename-layer prefix per URI prefix (D-05): "dependency" is aliased to "dep"
# at the filename layer only — the URI prefix itself remains "dependency".
# For "test_suite", this dict entry is the suite_kind=None / unknown fallback;
# the test_suite branch in `short_filename` overrides for known suite_kinds.
_FILENAME_PREFIX_BY_URI_PREFIX: dict[str, str] = {
    "repo": "repo",
    "pkg": "pkg",
    "app": "app",
    "agent_plugin": "agent-plugin",
    "dependency": "dep",
    "test_suite": "tests",
}


def short_filename(
    uri: str,
    collision_set: frozenset[str],
    *,
    suite_kind: str | None = None,
    pkg_for_suite: str | None = None,
) -> str:
    """Compute the slim vault filename stem for a graph URI (D-03, D-04, D-05, D-07).

    Pure function — no I/O, no SQL, no logging side effects from inside the
    function body. Fallback warnings (e.g. for `test_suite` URIs missing
    `suite_kind`) are logged at the call site, not here, per Phase 50 D-04.

    Parameters
    ----------
    uri
        Graph URI of an admitted entity (e.g. ``pkg:org/repo/utils``).
    collision_set
        Frozenset of URIs known to collide on the plain stem. If ``uri`` is
        in this set, a 6-hex sha256 disambiguator suffix is appended
        (D-03, D-04 — all colliders carry the suffix, not just N-1 of them).
    suite_kind
        For ``test_suite:`` URIs only — selects the prefix per D-07:
        ``unit`` → ``unit_tests``, ``integration`` → ``int_tests``,
        ``e2e`` → ``e2e_tests``, ``contract`` → ``contract_tests``,
        any other value or ``None`` → ``tests``. Ignored for non-test_suite
        URIs.
    pkg_for_suite
        For ``test_suite:`` URIs only — the package name to embed in the
        stem. If omitted, derived from the URI path: the second-to-last
        path segment if the path has ≥ 2 segments, else the last segment.

    Returns
    -------
    str
        The filename stem (without ``.md`` extension).

    Raises
    ------
    ValueError
        If ``uri`` is empty, lacks a ``:`` prefix separator, or has an
        unknown URI prefix.

    Examples
    --------
    >>> short_filename("pkg:org/repo/utils", frozenset())
    'pkg_utils'
    >>> short_filename("dependency:pypi/boto3", frozenset())
    'dep_boto3'
    >>> short_filename(
    ...     "test_suite:org/repo/wiki-io/tests",
    ...     frozenset(),
    ...     suite_kind="unit",
    ...     pkg_for_suite="wiki-io",
    ... )
    'unit_tests_wiki-io'
    >>> stem = short_filename("pkg:org/repo/utils", frozenset({"pkg:org/repo/utils"}))
    >>> stem.startswith("pkg_utils__")
    True
    >>> len(stem.rsplit("__", 1)[-1])
    6
    """
    if not uri:
        raise ValueError("short_filename: empty uri")
    if ":" not in uri:
        raise ValueError(f"short_filename: malformed uri {uri!r}: missing `:` prefix separator")
    uri_prefix, path = uri.split(":", 1)

    if uri_prefix == "test_suite":
        kind_prefix_by_suite = {
            "unit": "unit_tests",
            "integration": "int_tests",
            "e2e": "e2e_tests",
            "contract": "contract_tests",
        }
        kind_prefix = kind_prefix_by_suite.get(suite_kind or "", "tests")
        if pkg_for_suite is not None:
            pkg_part = pkg_for_suite
        else:
            segments = path.split("/")
            pkg_part = segments[-2] if len(segments) >= 2 else segments[-1]
        plain_stem = f"{kind_prefix}_{pkg_part}"
    else:
        kind_prefix = _FILENAME_PREFIX_BY_URI_PREFIX.get(uri_prefix)
        if kind_prefix is None:
            raise ValueError(f"short_filename: unknown uri prefix {uri_prefix!r}")
        name = path.split("/")[-1]
        plain_stem = f"{kind_prefix}_{name}"

    if uri in collision_set:
        suffix = hashlib.sha256(uri.encode("utf-8")).hexdigest()[:6]
        return f"{plain_stem}__{suffix}"
    return plain_stem


# ============================================================================
# Phase 43 Plan 02: write_entities orchestrator + helpers
# ============================================================================

import datetime as _dt  # noqa: E402
import fcntl  # noqa: E402
import json  # noqa: E402
import logging  # noqa: E402
import os  # noqa: E402
import re  # noqa: E402
from collections.abc import Iterable  # noqa: E402
from contextlib import contextmanager  # noqa: E402
from dataclasses import dataclass, field  # noqa: E402
from importlib.resources import files as _resource_files  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any, Callable, Iterator  # noqa: E402

import frontmatter  # noqa: E402
import yaml  # noqa: E402

_logger = logging.getLogger(__name__)


def _load_frontmatter(path: Path) -> frontmatter.Post:
    return frontmatter.load(str(path))


from wiki_io._graph_protocol import GraphReaderLike  # noqa: E402
from wiki_io.lint.common import SECTION_HEADER_RE, _split_pipes, parse_markdown_table  # noqa: E402
from wiki_io.md_escape import escape_angle_brackets  # noqa: E402

# Subset of DATA_KEYS that triggers needs_narrative when changed (D-10).
# Phase 51 PKGFAM-03: `members` removed (was the sole carrier for the
# retired family-grouping kind).
STRUCTURAL_KEYS: frozenset[str] = frozenset(
    {
        "depends_on",
        "test_suites",
        "entry_points",
        "tested_packages",
        "used_by",
    }
)

# Defence-in-depth: enforce the STRUCTURAL_KEYS ⊂ DATA_KEYS invariant at import.
assert STRUCTURAL_KEYS.issubset(DATA_KEYS), "STRUCTURAL_KEYS must be a subset of DATA_KEYS (D-10)"


class WriteLockHeldError(RuntimeError):
    """Raised by `write_entities` when another scan holds `.graph-wiki/scan.lock`."""


@dataclass(frozen=True)
class EntityWriteError:
    """A per-page failure during `write_entities` (D-09 / D-21)."""

    uri: str
    slug: str
    exception: str  # repr() of the caught exception


@dataclass(frozen=True)
class EntityWriteResult:
    """Bucketed URIs + per-page errors from one `write_entities` invocation (D-09).

    Lists are sorted alphabetically for deterministic comparison in tests.
    `needs_narrative` is a `set` of URIs requiring LLM prose generation
    (new pages OR pages whose STRUCTURAL_KEYS changed since last write).
    """

    created: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    needs_narrative: set[str] = field(default_factory=set)
    errors: list[EntityWriteError] = field(default_factory=list)


# ----------------------------------------------------------------------------
# merge_frontmatter (D-12, D-13, D-14)
# ----------------------------------------------------------------------------


def _sort_dedupe(value: Any) -> Any:
    """Return a sorted, deduped list if value is a list; otherwise return as-is.

    Mixed-type lists are sorted by (type_name, repr) to keep behavior total.
    """
    if isinstance(value, list):
        try:
            return sorted(set(value), key=lambda x: (str(type(x)), str(x)))
        except TypeError:
            # Unhashable items (e.g. dicts) — leave order alone but drop None? No.
            return value
    return value


def _is_empty(value: Any) -> bool:
    """Filter for D-14 step 3: scanner keys with these values are omitted."""
    return value is None or value == "" or value == [] or value == {}


def merge_frontmatter(existing: dict, scanner_update: dict) -> dict:
    """Merge scanner-computed frontmatter into an existing page's frontmatter.

    Semantics:
    - Data keys (DATA_KEYS) = full replacement from `scanner_update`.
      Empty values omitted (kept compact).
    - Non-data keys (human-authored or preserved provenance) kept verbatim,
      in original encountered order.
    - Key order on output: uri, kind, then data keys alphabetical
      (non-empty only), then remaining keys in original encountered order.
    - Collection values inside data keys are sorted + deduped.
    """
    out: dict = {}
    # 1. uri (always present; may come from existing if scanner_update omits it)
    if "uri" in scanner_update:
        out["uri"] = scanner_update["uri"]
    elif "uri" in existing:
        out["uri"] = existing["uri"]
    # 2. kind
    if "kind" in scanner_update:
        out["kind"] = scanner_update["kind"]
    elif "kind" in existing:
        out["kind"] = existing["kind"]
    # 2b. summary — fill-when-empty special case. `summary` is deliberately
    # NOT in DATA_KEYS (adding it there would clobber a human-edited summary
    # on every re-scan). Instead: a non-empty existing summary is preserved
    # verbatim (human edit survives); an absent/empty one is filled from the
    # scanner-derived value. Placed here for a stable slot right after `kind`.
    existing_summary = existing.get("summary")
    if not _is_empty(existing_summary):
        out["summary"] = existing_summary
    elif not _is_empty(scanner_update.get("summary")):
        out["summary"] = scanner_update["summary"]
    # 3. Data keys, alphabetical, non-empty only
    for key in sorted(DATA_KEYS - {"uri", "kind"}):
        if key in scanner_update:
            val = scanner_update[key]
            if not _is_empty(val):
                out[key] = _sort_dedupe(val) if isinstance(val, list) else val
    # 4. Remaining keys preserved in original encountered order from `existing`
    for key, val in existing.items():
        if key not in DATA_KEYS and key not in out:
            out[key] = val
    return out


# ----------------------------------------------------------------------------
# _acquire_scan_lock (D-19, D-20, D-21)
# ----------------------------------------------------------------------------


@contextmanager
def _acquire_scan_lock(workspace_root: Path) -> Iterator[None]:
    """Acquire an exclusive non-blocking advisory lock at
    `<workspace_root>/.graph-wiki/scan.lock` for the duration of the with-block.

    Raises `WriteLockHeldError` on contention (no wait). Releases the lock
    even on exception paths (D-19, D-21).

    POSIX-only — Phase 43 RESEARCH.md notes the rest of the stack is also
    POSIX-only; on Windows users should run inside WSL.
    """
    lock_path = workspace_root / ".graph-wiki" / "scan.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(lock_path, os.O_WRONLY | os.O_CREAT, 0o644)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise WriteLockHeldError(f"another scan in progress for this workspace: {workspace_root}") from exc
        try:
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


# ----------------------------------------------------------------------------
# deletions.log helpers (D-17, D-18)
# ----------------------------------------------------------------------------


def _rotate_deletions_log(log_path: Path, max_bytes: int = 10_000_000) -> None:
    """If `log_path` exceeds `max_bytes`, rename to `.log.1` (overwriting any
    prior `.log.1`). Two-file scheme per D-18. No-op if file is small or
    doesn't exist.
    """
    if not log_path.exists():
        return
    if log_path.stat().st_size < max_bytes:
        return
    rotated = log_path.with_suffix(".log.1")
    if rotated.exists():
        rotated.unlink()
    log_path.rename(rotated)


def _append_deletion(log_path: Path, record: dict) -> None:
    """Append one JSONL record to `.graph-wiki/deletions.log` (D-17).

    Rotates first (D-18). Creates parent dir if missing. Uses compact JSON
    (no extra whitespace) so log lines are unambiguous.
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)
    _rotate_deletions_log(log_path)
    line = json.dumps(record, separators=(",", ":"), sort_keys=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


# ----------------------------------------------------------------------------
# Structural change detection + page rendering (D-10, D-11, D-14, D-15)
# ----------------------------------------------------------------------------


def _detect_structural_change(existing_fm: dict, new_fm: dict) -> bool:
    """Return True iff any STRUCTURAL_KEYS value differs (sort+dedupe lists).

    Used to populate `needs_narrative` per D-10: pages with structural drift
    must re-run the LLM narrative generator.
    """
    for key in STRUCTURAL_KEYS:
        old = existing_fm.get(key)
        new = new_fm.get(key)
        if isinstance(old, list) and isinstance(new, list):
            if sorted(set(old), key=str) != sorted(set(new), key=str):
                return True
        elif old != new:
            return True
    return False


# Phase 56 D-03: any template `{{...}}` data token left unsubstituted (no
# node-derived value) is rewritten to this visible TODO marker rather than
# surviving raw — keeps SCAN-01 satisfied (no `{{...}}` survives) and surfaces
# the gap (D-12 blockquote style).
_RESIDUAL_TOKEN_RE = re.compile(r"\{\{[^}]+\}\}")


# Living Wiki M2a: per-entity provenance key. Holds the full HEAD SHA at which
# this entity's `## Narrative` was last regenerated. NOT in DATA_KEYS —
# merge_frontmatter preserves it; only the scan pipeline stamps it (on narration).
LAST_UPDATED_COMMIT_KEY = "last_updated_commit"


def _render_page_text(frontmatter_dict: dict, body: str) -> str:
    """Frame a frontmatter dict + body into the canonical entity-page text.

    Single source of truth for the dump convention (D-14/D-15): `sort_keys=False`
    (order pre-decided by `merge_frontmatter`), one trailing newline. Shared by
    `_render_entity_page` and `set_frontmatter_value` so a page stamped by the
    latter re-renders byte-identically through the former.
    """
    yaml_block = yaml.safe_dump(
        frontmatter_dict,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
        width=10_000,
    ).rstrip("\n")
    return f"---\n{yaml_block}\n---\n{body}".rstrip("\n") + "\n"


# ---------------------------------------------------------------------------
# Two-class section model: deterministic vs prose.
# If the graph can compute a section, it is deterministic; if a model (or
# human) wrote it, it is prose and carried from the existing page verbatim.
# ---------------------------------------------------------------------------

# Deterministic (pure graph projection) H2 headings. Downstream contract:
# refresh passes exclude these sections from model prompts (Child 2); lint's
# scanner_heading rule retargets to this constant (Child 5). `## File map` is
# also deterministic but carries a `- <name>` heading suffix, so it is matched
# by `_is_file_map_heading`, not by membership here.
DETERMINISTIC_SECTIONS: frozenset[str] = frozenset(
    {
        "## Referenced in wiki",
        "## Commands",
        "## Agents",
        "## Skills",
        "## Scripts",
        "## Hooks",
        "## MCP servers",
    }
)

# The agent_plugin data tables: deterministic sections whose fresh data is
# substituted into the template at render time (_agent_plugin_table_variables),
# so for them "fresh render" IS the template chunk — never sourced from disk
# at merge. `## Referenced in wiki` and `## File map` are deterministic but
# inject-refreshed by always-run post-passes (regenerate_referenced_in_wiki /
# inject_file_map), so the merge carries their on-disk copy instead.
_TEMPLATE_AUTHORITATIVE: frozenset[str] = DETERMINISTIC_SECTIONS - {"## Referenced in wiki"}


def _is_file_map_heading(heading: str) -> bool:
    """True for `## File map[ - <name>]` headings.

    The `- <name>` suffix differs between the template render (slug) and the
    injected deterministic block (basename), so File map is matched by prefix —
    the only heading that ever needed suffix normalization.
    """
    return heading.strip().startswith("## File map")


def _split_h2_sections(text: str) -> tuple[str, list[tuple[str, str]]]:
    """Split a page body into ``(preamble, [(heading, chunk), ...])``.

    ``preamble`` is everything before the first H2 (the H1 + any intro). Each
    ``chunk`` starts at its ``## `` heading and runs up to (but not including)
    the next H2, or EOF; ``heading`` is the stripped first line of the chunk.
    Lossless: ``preamble + "".join(chunks) == text`` (uses ``_NEXT_H2_RE``,
    defined at module scope below).
    """
    starts = [m.start() for m in _NEXT_H2_RE.finditer(text)]
    if not starts:
        return text, []
    preamble = text[: starts[0]]
    sections: list[tuple[str, str]] = []
    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(text)
        chunk = text[start:end]
        heading = chunk.split("\n", 1)[0].strip()
        sections.append((heading, chunk))
    return preamble, sections


def _merge_preserved_sections(template_body: str, existing_body: str) -> str:
    """Merge an existing page's content into ``template_body`` (two-class model).

    - Preamble (H1 + intro) always from the template.
    - Template-authoritative sections (``_TEMPLATE_AUTHORITATIVE`` — the six
      agent_plugin data tables) always take the freshly-rendered template
      chunk; never sourced from disk.
    - The File map section (``_is_file_map_heading`` prefix match, so the
      `- <slug>` vs `- <basename>` suffix mismatch cannot orphan it) carries
      the on-disk chunk when the page has one (first occurrence), else the
      template chunk (new page). Freshness is enforced at pipeline level by
      the always-run ``inject_file_map`` post-pass.
    - Every other template section is prose: the on-disk chunk by exact
      heading match when present, else the template chunk (placeholder).
    - On-disk sections the template does not define are appended in original
      order — except deterministic/File-map headings, which are
      template-driven and never linger. Prose is never silently dropped.

    Idempotent: ``_merge_preserved_sections(t, t) == t`` because the split is
    lossless and each section round-trips.
    """
    pre_t, secs_t = _split_h2_sections(template_body)
    _pre_e, secs_e = _split_h2_sections(existing_body)

    existing_by_heading: dict[str, str] = {}
    existing_file_map: str | None = None
    for heading, chunk in secs_e:
        if heading in _TEMPLATE_AUTHORITATIVE:
            continue  # never sourced from the on-disk page
        if _is_file_map_heading(heading):
            if existing_file_map is None:
                existing_file_map = chunk  # first occurrence wins
        else:
            existing_by_heading.setdefault(heading, chunk)  # first occurrence wins

    out = [pre_t]
    template_headings: set[str] = set()
    consumed: set[str] = set()
    for heading, chunk in secs_t:
        template_headings.add(heading)
        if heading in _TEMPLATE_AUTHORITATIVE:
            out.append(chunk)  # always the fresh graph render
        elif _is_file_map_heading(heading):
            out.append(existing_file_map if existing_file_map is not None else chunk)
        elif heading in existing_by_heading:
            out.append(existing_by_heading[heading])
            consumed.add(heading)
        else:
            out.append(chunk)

    # Append on-disk sections the template does not define (prose only —
    # deterministic sections never linger).
    for heading, chunk in secs_e:
        if (
            heading in template_headings
            or heading in consumed
            or heading in DETERMINISTIC_SECTIONS
            or _is_file_map_heading(heading)
        ):
            continue
        consumed.add(heading)
        out.append(chunk)

    return "".join(out)


def _render_entity_page(
    template_path: Path,
    frontmatter_dict: dict,
    variables: dict[str, str],
    existing_body: str | None = None,
) -> str:
    """Render an entity page: template body + given frontmatter dict.

    Frontmatter is emitted with `sort_keys=False` because key order has
    already been determined by `merge_frontmatter` (D-14). Output ends with
    exactly one trailing newline for byte-stability (D-15).

    Phase 56 SCAN-01 (D-01/D-02): the body's `{{...}}` *data* tokens are
    substituted from `variables` using the same literal `str.replace` mechanism
    as `init_vault.render_template` — NO Jinja. Only `{{...}}` is substituted;
    instruction-style `<...>` placeholders (authoring guidance inside
    `> TODO:` blockquotes etc.) are left untouched (the two-token rule). Any
    `{{...}}` token with no mapped value is rewritten to a visible TODO marker
    (D-03) so no raw `{{...}}` survives. Frontmatter is built from the dict, so
    only the body needs substituting.
    """
    template = _load_frontmatter(template_path)
    body = template.content
    for k, v in variables.items():
        body = body.replace("{{" + k + "}}", v)
    # D-03: rewrite any residual (unmapped) data token to a visible TODO marker.
    # Strip the braces from the token name so the marker itself carries NO `{{`
    # (else SCAN-01's "no {{ survives" guarantee would be defeated).
    body = _RESIDUAL_TOKEN_RE.sub(lambda m: f"> TODO: <add value for {m.group(0).strip('{}')}>", body)
    # Living Wiki M1: preserve human-owned sections from the existing page.
    if existing_body is not None:
        body = _merge_preserved_sections(body, existing_body)
    return _render_page_text(frontmatter_dict, body)


def set_frontmatter_value(page_path: Path, key: str, value: str) -> None:
    """Set a single frontmatter `key` to `value` on an entity page, preserving
    the body bytes and the canonical dump convention.

    The key is updated in place when present, or appended last when new — which
    matches `merge_frontmatter`'s placement of non-scanner keys, so a subsequent
    `write_entities` re-render is byte-identical. Writes atomically via a temp
    file + `os.replace` (mirrors `inject_narrative`).

    Raises:
        FileNotFoundError: when `page_path` does not exist.
    """
    post = _load_frontmatter(page_path)  # raises FileNotFoundError naturally
    fm = dict(post.metadata)
    fm[key] = value
    new_content = _render_page_text(fm, post.content)
    tmp_path = page_path.with_suffix(page_path.suffix + ".tmp")
    tmp_path.write_text(new_content, encoding="utf-8")
    os.replace(tmp_path, page_path)


def update_frontmatter(
    page_path: Path,
    updates: dict[str, object] | None = None,
    *,
    delete: Iterable[str] = (),
) -> None:
    """Apply frontmatter `updates` and key `delete`s in one atomic read-modify-write.

    Structured sibling of `set_frontmatter_value` (which is scalar-string only):
    `updates` values may be any YAML-serializable object; `delete` removes keys.
    Body bytes and the canonical dump convention are preserved via
    `_render_page_text`, so a subsequent `write_entities` re-render is
    byte-identical. New keys append last (matching `merge_frontmatter`'s
    placement of non-data keys). Writes atomically via temp file + `os.replace`.

    Raises:
        FileNotFoundError: when `page_path` does not exist.
    """
    post = _load_frontmatter(page_path)  # raises FileNotFoundError naturally
    fm = dict(post.metadata)
    for key, value in (updates or {}).items():
        fm[key] = value
    for key in delete:
        fm.pop(key, None)
    new_content = _render_page_text(fm, post.content)
    tmp_path = page_path.with_suffix(page_path.suffix + ".tmp")
    tmp_path.write_text(new_content, encoding="utf-8")
    os.replace(tmp_path, page_path)


# ----------------------------------------------------------------------------
# write_entities orchestrator (D-08, D-15, D-16, D-21, D-22)
# ----------------------------------------------------------------------------


# Mapping from kind to list_fn — each closes over a GraphReader and calls the
# matching `reader.list_*()` handle method.
def _kind_list_fns() -> dict[str, Callable]:
    return {
        "repository": lambda reader: reader.list_repositories(),
        "package": lambda reader: reader.list_packages(),
        "app": lambda reader: reader.list_apps(),
        "test_suite": lambda reader: reader.list_test_suites(),
        "dependency": lambda reader: reader.list_dependencies(),
        "agent_plugin": lambda reader: reader.list_agent_plugins(),
    }


def _template_path_for_kind(kind: str) -> Path:
    """Return the on-disk path to the entity-<kind>.md template (Phase 42 Plan 02)."""
    fname = f"entity-{kind.replace('_', '-')}.md"
    return Path(str(_resource_files("wiki_io.assets.page-templates").joinpath(fname)))


def scanner_frontmatter_for_node(reader: Any, kind: str, node: Any) -> dict:
    """Build the scanner-update frontmatter dict from a graph node + its description.

    Returns a dict ready for `merge_frontmatter`. Always populates `uri`,
    `kind`. Per-kind logic pulls relation lists from `describe_*` and
    attrs from the node.
    """
    # Node URI: prefer the node's nodes.uri column (NodeRecord may carry it
    # in attrs because describe_* surfaces use the column at projection time).
    uri = node.attrs.get("uri", "") if isinstance(node.attrs, dict) else ""
    fm: dict = {
        "uri": uri,
        "kind": kind,
    }
    # Phase 56 SCAN-02 (D-05): derive `summary` UNIFORMLY across kinds from the
    # node's description (packages/apps are populated by graph-io's Plan 04
    # change). Read defensively so this works even before
    # that lands. D-03/D-12: an empty/absent description yields a visible TODO
    # marker, never an empty string — so every page ends with a non-empty
    # summary. NOTE: `summary` is intentionally a fill-when-empty key, NOT a
    # DATA_KEYS member — see the special-case in merge_frontmatter (D-07).
    description = node.attrs.get("description") if isinstance(node.attrs, dict) else None
    fm["summary"] = description or f"TODO add a one-line summary for {node.name}"
    if kind == "repository":
        d = reader.describe_repository()
        if d is not None:
            fm["package_count"] = d.package_count
    elif kind == "package":
        d = reader.describe_package(name=node.name)
        if d is not None:
            fm["language"] = d.language
            fm["version"] = d.version
            fm["test_suites"] = [s.name for s in d.test_suites]
            fm["entry_points"] = [e.name for e in d.entry_points]
    elif kind == "app":
        d = reader.describe_app(name=node.name)
        if d is not None:
            # AppDescription mirrors PackageDescription field-for-field with
            # two additions: `app_kind` (one of `_VALID_APP_KINDS`) and
            # `app_signals` (sorted list of classification signals) — both
            # surfaced as data keys (D-06).
            fm["language"] = d.language
            fm["version"] = d.version
            fm["test_suites"] = [s.name for s in d.test_suites]
            fm["entry_points"] = [e.name for e in d.entry_points]
            fm["app_kind"] = d.app_kind
            fm["app_signals"] = list(d.app_signals)
    elif kind == "test_suite":
        d = reader.describe_test_suite(suite_name=node.name)
        if d is not None:
            fm["suite_kind"] = d.kind
            fm["file_count"] = d.file_count
    elif kind == "dependency":
        ecosystem = node.attrs.get("ecosystem", "pypi") if isinstance(node.attrs, dict) else "pypi"
        d = reader.describe_dependency(ecosystem=ecosystem, name=node.name)
        if d is not None:
            fm["ecosystem"] = d.ecosystem
            fm["versions_in_use"] = list(d.versions_in_use)
            fm["used_by"] = list(d.used_by)
    elif kind == "agent_plugin":
        d = reader.describe_agent_plugin(name=node.name)
        if d is not None:
            fm["ecosystem"] = d.ecosystem
            fm["version"] = d.version
    return fm


def _is_template_body_default(body: str, template_body: str) -> bool:
    """Heuristic: True if the body equals the unmodified template body."""
    return body.rstrip() == template_body.rstrip()


def _compute_collision_set(
    reader: GraphReaderLike,
    admitted_kinds: frozenset[str],
    list_fns: dict[str, Callable],
) -> frozenset[str]:
    """Pre-pass that returns the set of URIs whose plain short stem collides.

    Iterates every admitted-kind node once, computes each node's *plain*
    short filename via ``short_filename(uri, collision_set=frozenset(), ...)``
    (i.e. with an empty collision set so no suffix is added), groups by stem,
    and returns the set of URIs whose stem appears more than once across the
    whole admitted-kind enumeration.

    D-01 + D-02: extends to TestSuite kind-aware names by reading
    ``suite_kind`` from ``node.attrs["suite_kind"]`` and ``pkg_for_suite``
    from ``Path(node.attrs["path"]).parent.name`` (or last segment fallback)
    when ``kind == "test_suite"``. This means two test_suites with the same
    kind + same package name (e.g. two ``unit`` suites for the same package
    name) will be flagged as colliding and both receive a ``__<6hex>``
    disambiguator — matching the all-colliders D-04 semantics for the rest
    of the entity surface.

    Internal helper (single-leading-underscore): exists to keep
    ``write_entities`` readable + unit-testable in isolation. Reads the
    graph in a read-only fashion; does not write or mutate global state.
    """
    stem_to_uris: dict[str, list[str]] = {}
    for kind in sorted(admitted_kinds):
        list_fn = list_fns.get(kind)
        if list_fn is None:
            continue
        for node in list_fn(reader):
            uri = node.attrs.get("uri") if isinstance(node.attrs, dict) else None
            if not uri:
                continue
            if kind == "test_suite":
                attrs = node.attrs if isinstance(node.attrs, dict) else {}
                suite_kind = attrs.get("suite_kind") or None
                suite_path = attrs.get("path")
                pkg_for_suite: str | None = None
                if suite_path:
                    pkg_for_suite = Path(suite_path).parent.name or None
                if not pkg_for_suite:
                    pkg_for_suite = None
                stem = short_filename(
                    uri,
                    frozenset(),
                    suite_kind=suite_kind,
                    pkg_for_suite=pkg_for_suite,
                )
            else:
                stem = short_filename(uri, frozenset())
            stem_to_uris.setdefault(stem, []).append(uri)
    return frozenset(uri for uris in stem_to_uris.values() if len(uris) > 1 for uri in uris)


def _md_escape(cell: str) -> str:
    """Escape a markdown-table cell: pipes and newlines would break the row;
    bare `<`/`>` would otherwise be parsed as an unclosed HTML tag by
    Obsidian's renderer (see `obsidian-render-angle-bracket`)."""
    return escape_angle_brackets(str(cell).replace("|", "\\|").replace("\n", " ").strip())


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    """Render a GitHub-flavored markdown table, or `_None._` when there are no
    rows (so the template token is always substituted to a non-empty value and
    no residual `{{...}}` survives)."""
    if not rows:
        return "_None._"
    head = "| " + " | ".join(headers) + " |"
    sep = "| " + " | ".join("---" for _ in headers) + " |"
    body = "\n".join("| " + " | ".join(_md_escape(c) for c in row) + " |" for row in rows)
    return f"{head}\n{sep}\n{body}"


def _agent_plugin_table_variables(reader: Any, node: Any) -> dict[str, str]:
    """Build the six `{{*_table}}` substitution values for an agent_plugin page
    from its component inventory. Returns `_None._` per section when empty."""
    d = reader.describe_agent_plugin(name=node.name)
    if d is None:
        empty = "_None._"
        return {
            "commands_table": empty,
            "agents_table": empty,
            "skills_table": empty,
            "scripts_table": empty,
            "hooks_table": empty,
            "mcp_servers_table": empty,
        }
    return {
        "commands_table": _md_table(
            ["Command", "Description"],
            [[c.get("name", ""), c.get("description", "")] for c in d.commands],
        ),
        "agents_table": _md_table(
            ["Agent", "Model", "Tools", "Description"],
            [
                [a.get("name", ""), a.get("model", ""), ", ".join(a.get("tools", []) or []), a.get("description", "")]
                for a in d.agents
            ],
        ),
        "skills_table": _md_table(
            ["Skill", "Description"],
            [[s.get("name", ""), s.get("description", "")] for s in d.skills],
        ),
        "scripts_table": _md_table(
            ["Script", "Language"],
            [[s.get("path", ""), s.get("lang", "")] for s in d.scripts],
        ),
        "hooks_table": _md_table(
            ["Event", "Matchers"],
            [[h.get("event", ""), ", ".join(h.get("matchers", []) or [])] for h in d.hooks],
        ),
        "mcp_servers_table": _md_table(
            ["Server", "Command"],
            [[m.get("name", ""), m.get("command", "")] for m in d.mcp_servers],
        ),
    }


def write_entities(
    reader: GraphReaderLike,
    wiki_root: Path,
    admitted_kinds: frozenset[str],
) -> EntityWriteResult:
    """Create / merge / hard-delete entity pages from the graph.

    See `.planning/phases/43-entity-writer/43-CONTEXT.md` for the locked
    decisions (D-08..D-22). Acquires `.graph-wiki/scan.lock` on entry;
    releases in `finally` (including exception paths) (D-19, D-21).

    Returns `EntityWriteResult` with per-state URI buckets + `needs_narrative`
    for the Phase 45 LLM fan-out + per-page errors for partial-success.
    """
    workspace_root = wiki_root.parent  # `.graph-wiki/` sits next to `wiki/`
    entities_dir = wiki_root / "entities"
    entities_dir.mkdir(parents=True, exist_ok=True)
    deletions_log = workspace_root / ".graph-wiki" / "deletions.log"

    created: list[str] = []
    updated: list[str] = []
    deleted: list[str] = []
    unchanged: list[str] = []
    needs_narrative: set[str] = set()
    errors: list[EntityWriteError] = []
    admitted_uris: set[str] = set()

    list_fns = _kind_list_fns()
    # Phase 52 D-01: one-shot collision pre-pass; reads the graph read-only, no lock needed
    collision_set = _compute_collision_set(reader, admitted_kinds, list_fns)

    with _acquire_scan_lock(workspace_root):
        # --- Per-kind create / merge ---
        for kind in sorted(admitted_kinds):
            list_fn = list_fns.get(kind)
            if list_fn is None:
                continue  # unknown admitted kind without a list_fn — skip
            template_path = _template_path_for_kind(kind)
            if not template_path.exists():
                errors.append(
                    EntityWriteError(
                        uri=f"<missing-template:{kind}>",
                        slug="",
                        exception=repr(FileNotFoundError(str(template_path))),
                    )
                )
                continue
            for node in list_fn(reader):
                uri = node.attrs.get("uri") if isinstance(node.attrs, dict) else None
                if not uri:
                    continue
                admitted_uris.add(uri)
                # Phase 52 D-01..D-07: derive short filename, handling test_suite kind-aware naming.
                suite_kind_for_node: str | None = None
                pkg_for_suite_for_node: str | None = None
                if kind == "test_suite":
                    attrs_for_node = node.attrs if isinstance(node.attrs, dict) else {}
                    suite_kind_for_node = attrs_for_node.get("suite_kind") or None
                    suite_path = attrs_for_node.get("path")
                    if suite_path:
                        pkg_for_suite_for_node = Path(suite_path).parent.name or None
                    if not suite_kind_for_node:
                        _logger.warning(
                            "test_suite node has no suite_kind attr (uri=%s); "
                            "falling back to tests_<pkg> short filename",
                            uri,
                        )
                slug = short_filename(
                    uri,
                    collision_set,
                    suite_kind=suite_kind_for_node,
                    pkg_for_suite=pkg_for_suite_for_node,
                )
                page_path = entities_dir / f"{slug}.md"
                try:
                    scanner_fm = scanner_frontmatter_for_node(reader, kind, node)
                    existing_fm: dict = {}
                    existing_body: str | None = None
                    existed = page_path.exists()
                    if existed:
                        post = _load_frontmatter(page_path)
                        existing_fm = dict(post.metadata)
                        existing_body = post.content
                    merged_fm = merge_frontmatter(existing_fm, scanner_fm)
                    # Phase 56 SCAN-01 (D-04): build the {{...}} data-token map
                    # from node-available data. Keys here are DATA tokens only;
                    # instruction `<...>` placeholders are never in this map and
                    # are never substituted (the two-token rule, D-01). Any token
                    # a template references but that is absent here is rewritten
                    # to a TODO marker by _render_entity_page (D-03).
                    variables: dict[str, str] = {
                        # Per-kind H1 name token, e.g. {{package_name}} -> node.name
                        f"{kind}_name": node.name,
                        # entity-test-suite.md uses {{PACKAGE_SLUG}} (and the
                        # lowercase form is accepted for symmetry); both map to slug.
                        "package_slug": slug,
                        "PACKAGE_SLUG": slug,
                    }
                    if kind == "agent_plugin":
                        variables.update(_agent_plugin_table_variables(reader, node))
                    new_content = _render_entity_page(
                        template_path,
                        merged_fm,
                        variables,
                        existing_body=existing_body,
                    )
                    new_bytes = new_content.encode("utf-8")
                    if existed:
                        old_bytes = page_path.read_bytes()
                        # PTO: write_entities no longer resets scanner sections
                        # to placeholders (the merge preserves them), so a no-op
                        # rescan renders byte-identical content and the plain
                        # compare buckets it `unchanged`. (M2c #3's churn-mask
                        # helper absorbed the reset churn; PTO removes the reset,
                        # so the helper is gone.)
                        if old_bytes == new_bytes:
                            unchanged.append(uri)
                            continue
                        page_path.write_text(new_content, encoding="utf-8")
                        page_path.chmod(0o644)
                        updated.append(uri)
                        if _detect_structural_change(existing_fm, merged_fm):
                            needs_narrative.add(uri)
                    else:
                        page_path.write_text(new_content, encoding="utf-8")
                        page_path.chmod(0o644)
                        created.append(uri)
                        needs_narrative.add(uri)
                except Exception as exc:  # noqa: BLE001 — D-21 partial-failure isolation
                    errors.append(
                        EntityWriteError(
                            uri=uri,
                            slug=slug,
                            exception=repr(exc),
                        )
                    )

        # --- Deletion sweep ---
        for page_path in sorted(entities_dir.glob("*.md")):
            try:
                post = _load_frontmatter(page_path)
                uri = post.metadata.get("uri")
                if not isinstance(uri, str) or uri in admitted_uris:
                    continue
                kind_metadata = post.metadata.get("kind")
                kind_from_fm = kind_metadata if isinstance(kind_metadata, str) else uri.split(":", 1)[0]
                template_path = _template_path_for_kind(kind_from_fm)
                template_body = ""
                if template_path.exists():
                    template_body = _load_frontmatter(template_path).content
                body_was_empty = _is_template_body_default(post.content, template_body)
                record = {
                    "timestamp": _dt.datetime.now(_dt.timezone.utc)
                    .isoformat(timespec="seconds")
                    .replace("+00:00", "Z"),
                    "uri": uri,
                    "slug": page_path.stem,
                    "path": str(page_path.relative_to(workspace_root)),
                    "kind": kind_from_fm,
                    "body_was_empty": body_was_empty,
                }
                _append_deletion(deletions_log, record)
                page_path.unlink()
                deleted.append(uri)
            except Exception as exc:  # noqa: BLE001
                errors.append(
                    EntityWriteError(
                        uri=str(page_path.name),
                        slug=page_path.stem,
                        exception=repr(exc),
                    )
                )

        # --- Placeholder self-heal (runs after create/merge + deletion sweep,
        # so it reflects post-sweep state). Keep entities/ committable when
        # empty; drop the placeholder once real pages exist. ---
        gitkeep = entities_dir / ".gitkeep"
        if any(entities_dir.glob("*.md")):
            gitkeep.unlink(missing_ok=True)
        elif not gitkeep.exists():
            gitkeep.write_text("", encoding="utf-8")

    return EntityWriteResult(
        created=sorted(created),
        updated=sorted(updated),
        deleted=sorted(deleted),
        unchanged=sorted(unchanged),
        needs_narrative=needs_narrative,
        errors=errors,
    )


# ---------------------------------------------------------------------------
# Phase 45 D-07: inject_narrative — overwrite the `## Narrative` body region
# ---------------------------------------------------------------------------

# Hard convention per Phase 42 D-16: humans must not rename this heading.
_NARRATIVE_HEADING = "## Narrative"

# Match `## Narrative` at column 0 followed only by optional trailing whitespace
# and a newline (so `### Narrative` and `## Narrative Foo` do NOT match).
_NARRATIVE_HEADING_RE = re.compile(r"^## Narrative[ \t]*\n", re.MULTILINE)

# Match the next H2 heading at column 0 (used to locate the end of the
# narrative body region).
_NEXT_H2_RE = re.compile(r"^## ", re.MULTILINE)

# Living Wiki M2a: the entity templates' `## Narrative` placeholder. A section
# equal to this (or empty) is treated as "no prose" by extract_narrative.
_NARRATIVE_PLACEHOLDER = "_(scanner will populate on next scan)_"


def extract_narrative(text: str) -> str | None:
    """Return the stripped body of the `## Narrative` section, or None when the
    section is missing, empty, or still the template placeholder.

    Used by the scan pipeline to snapshot narrated prose before re-render and
    to guard the restore step from overwriting freshly-injected prose.
    """
    match = _NARRATIVE_HEADING_RE.search(text)
    if match is None:
        return None
    body_start = match.end()
    next_h2 = _NEXT_H2_RE.search(text, body_start)
    body_end = next_h2.start() if next_h2 is not None else len(text)
    body = text[body_start:body_end].strip()
    if not body or body == _NARRATIVE_PLACEHOLDER:
        return None
    return body


def inject_narrative(page_path: Path, prose: str) -> None:
    """Replace the body of the `## Narrative` section with `prose`.

    Phase 45 D-07: locates the FIRST `## Narrative` H2 heading at column 0;
    replaces the body region from end-of-that-heading up to the next H2 (or
    EOF) with `prose.strip()`. Writes atomically via temp-file + `os.replace`.

    Idempotent: calling with the same arguments twice produces byte-identical
    output on the second call.

    Logs a WARNING and returns without writing when the page is missing the
    `## Narrative` heading (defensive — entity templates always carry it).

    Raises:
        FileNotFoundError: when `page_path` does not exist.
    """
    text = page_path.read_text(encoding="utf-8")  # raises FileNotFoundError naturally

    match = _NARRATIVE_HEADING_RE.search(text)
    if match is None:
        _logger.warning("inject_narrative: no `## Narrative` heading found at %s", page_path)
        return

    body_start = match.end()  # index immediately after the heading's newline

    next_h2 = _NEXT_H2_RE.search(text, body_start)
    body_end = next_h2.start() if next_h2 is not None else len(text)

    cleaned = prose.strip()
    new_body = f"\n{cleaned}\n\n" if cleaned else "\n\n"
    new_content = text[:body_start] + new_body + text[body_end:]

    tmp_path = page_path.with_suffix(page_path.suffix + ".tmp")
    tmp_path.write_text(new_content, encoding="utf-8")
    os.replace(tmp_path, page_path)


# ---------------------------------------------------------------------------
# prose_section_bodies / replace_prose_sections — two-class prose write surface
# ---------------------------------------------------------------------------


def _h2_chunk_body(chunk: str) -> str:
    """Body of a `_split_h2_sections` chunk (everything after the heading line)."""
    heading_end = chunk.find("\n")
    if heading_end == -1:
        return ""
    return chunk[heading_end + 1 :]


def _is_prose_heading(heading: str) -> bool:
    """True when a heading is prose (not deterministic or file-map).

    Prose headings are the only ones the refresh agent can modify.
    """
    return heading not in DETERMINISTIC_SECTIONS and not _is_file_map_heading(heading)


def prose_section_bodies(text: str) -> dict[str, str]:
    """Map every non-deterministic H2 heading to its current stripped body.

    Excludes ``DETERMINISTIC_SECTIONS`` members and ``## File map*`` headings —
    the prose surface handed to (and accepted back from) the prose-refresh
    agent. First occurrence wins on duplicate headings.
    """
    _preamble, sections = _split_h2_sections(text)
    out: dict[str, str] = {}
    for heading, chunk in sections:
        if not _is_prose_heading(heading):
            continue
        out.setdefault(heading, _h2_chunk_body(chunk).strip())
    return out


def replace_prose_sections(page_path: Path, replacements: dict[str, str]) -> list[str]:
    """Replace the bodies of existing non-deterministic H2 sections.

    Keys are FULL headings (``"## Narrative"``). ``DETERMINISTIC_SECTIONS``
    members, File-map headings, headings absent from the page, and
    empty/whitespace replacements are ignored. Headings are never created or
    deleted. Returns the headings changed, in page order. Atomic write.

    Idempotent: calling with the same arguments twice produces byte-identical
    output on the second call.

    Raises:
        FileNotFoundError: when ``page_path`` does not exist.
    """
    text = page_path.read_text(encoding="utf-8")
    wanted = {
        heading: body.strip() for heading, body in replacements.items() if body.strip() and _is_prose_heading(heading)
    }
    if not wanted:
        return []
    preamble, sections = _split_h2_sections(text)
    changed: list[str] = []
    seen: set[str] = set()
    rebuilt: list[str] = [preamble]
    for heading, chunk in sections:
        replacement = wanted.get(heading)
        if replacement is None or heading in seen:
            rebuilt.append(chunk)
            continue
        seen.add(heading)
        current_body = _h2_chunk_body(chunk).strip()
        if current_body == replacement:
            rebuilt.append(chunk)
            continue
        suffix_len = len(chunk) - len(chunk.rstrip("\n"))
        suffix = chunk[-suffix_len:] if suffix_len else ""
        heading_line = chunk.split("\n", 1)[0]
        rebuilt.append(f"{heading_line}\n{replacement}{suffix}")
        changed.append(heading)
    new_text = "".join(rebuilt)
    if new_text != text:
        tmp_path = page_path.with_suffix(page_path.suffix + ".tmp")
        tmp_path.write_text(new_text, encoding="utf-8")
        os.replace(tmp_path, page_path)
    else:
        changed = []
    return changed


_TODO_HEAD_RE = re.compile(r"^(?:>\s*)?(?:[-*]\s*)?(?:TODO\b|[-—]\s*TODO\b)", re.IGNORECASE)


def is_todo_like_body(body: str) -> bool:
    """Return True when ``body`` still looks like a placeholder."""
    cleaned = body.strip()
    if not cleaned:
        return True
    for line in cleaned.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if not _TODO_HEAD_RE.match(stripped):
            return False
    return True


def has_todo_prose(text: str) -> bool:
    """True when any prose section (see ``prose_section_bodies``) still looks
    like a TODO placeholder.

    Replaces the old ``find_todo_human_sections``: both call sites (the
    first-fill gate and the anchor-stamp gate) tested only truthiness, so this
    returns a bool instead of the sections themselves. The old ``entity_kind``
    parameter is gone — ``prose_section_bodies`` already excludes
    ``DETERMINISTIC_SECTIONS`` (the agent_plugin data tables among them)
    unconditionally, for every kind, so the kind-specific exclusion is
    redundant under the two-class ownership model.
    """
    return any(is_todo_like_body(b) for b in prose_section_bodies(text).values())


def extract_file_map(body: str) -> str | None:
    """Return the stripped ``## File map[ - <name>]`` chunk, or None when absent."""
    _preamble, sections = _split_h2_sections(body)
    for heading, chunk in sections:
        if _is_file_map_heading(heading):
            return chunk.strip()
    return None


# ---------------------------------------------------------------------------
# inject_file_map — overwrite the whole `## File map` section deterministically
# ---------------------------------------------------------------------------

# Match the `## File map` H2 heading line at column 0, with or without the
# `- <name>` suffix the template/scanner emit. Captures the full heading line so
# the replacement (which carries its own heading) starts cleanly.
_FILE_MAP_HEADING_RE = re.compile(r"^## File map\b.*\n", re.MULTILINE)

# Extract the package/app name from a `## File map - <name>` heading line.
_FILE_MAP_NAME_RE = re.compile(r"^## File map\s*-\s*(\S.*?)\s*$", re.MULTILINE)

# A backticked path cell: `` `src/foo.py` `` → `src/foo.py`.
_FILE_MAP_PATH_CELL_RE = re.compile(r"^\s*`(.+?)`\s*$")

_DIR_SECTION_PLACEHOLDER = "TODO — describe what this directory contains."
_OVERVIEW_PLACEHOLDER = "TODO — overview of this package's tree."


def _is_filled_description(desc: str) -> bool:
    """True when a File-map Description cell carries real content (not a placeholder).

    Placeholders are the deterministic `— TODO`, the template's
    `— > TODO — <...>`, or any cell that reduces to empty / a `TODO` / `>`
    blockquote stub. Used to decide which descriptions are worth preserving
    across a rescan.
    """
    d = desc.strip().lstrip("—").strip()
    if not d:
        return False
    if d.startswith(">"):
        return False
    if d.upper().startswith("TODO"):
        return False
    return True


def _file_map_full_path(current_path: str, token: str) -> str:
    """Join an H3 section path context with a row's path cell into a package-root
    path (e.g. ``("src", "foo.py") -> "src/foo.py"``)."""
    name = token.rstrip("/")
    return f"{current_path}/{name}" if current_path else name


def _section_path_context(header_text: str, pkg_name: str) -> str:
    """Map an H3 header (`### <pkg>/<sub>/`) to its package-root path context.

    The synthetic root section `### <pkg>/` yields `""`; `### <pkg>/src/`
    yields `"src"`. Headers that do not start with `<pkg>/` reset context to
    `""` (defensive — matches `parse_section_entries`).
    """
    header = header_text.rstrip("/").strip()
    if header == pkg_name:
        return ""
    if header.startswith(pkg_name + "/"):
        return header[len(pkg_name) + 1 :]
    return ""


def _extract_file_map_descriptions(section_text: str, pkg_name: str) -> dict[str, str]:
    """Return ``{package_root_path: description}`` for every File-map row whose
    Description cell is filled (non-placeholder).

    ``section_text`` is the body of a `## File map - <name>` section (the H3
    sub-sections + tables, without the H2 heading line). Mirrors the
    section-context walk in ``wiki_io.lint.common.parse_section_entries`` but
    captures the Description column. Descriptions are returned with table-pipe
    escapes already decoded (via ``parse_markdown_table``); the merge step
    re-escapes on write.
    """
    descs: dict[str, str] = {}
    current_path = ""
    lines = section_text.splitlines()
    n = len(lines)
    i = 0
    while i < n:
        m = SECTION_HEADER_RE.match(lines[i])
        if not m:
            i += 1
            continue
        current_path = _section_path_context(m.group(1), pkg_name)
        i += 1
        section_lines: list[str] = []
        while i < n and not SECTION_HEADER_RE.match(lines[i]):
            section_lines.append(lines[i])
            i += 1
        table = parse_markdown_table("\n".join(section_lines))
        if table is None:
            continue
        _headers, rows = table
        for row in rows:
            if len(row) < 3:
                continue
            bm = _FILE_MAP_PATH_CELL_RE.match(row[0])
            token = bm.group(1) if bm else row[0].strip()
            if not token.strip("/"):
                continue
            if _is_filled_description(row[2]):
                descs[_file_map_full_path(current_path, token)] = row[2].strip()
    return descs


def _merge_preserved_descriptions(block: str, pkg_name: str, preserved: dict[str, str]) -> str:
    """Rewrite the Description cell of any row in ``block`` whose package-root
    path has a preserved (filled) description.

    Only `— TODO`/placeholder cells are candidates for substitution — a block
    fresh from ``build_file_map`` carries `— TODO` on every row, so this is a
    pure restore of prior descriptions for paths still present on disk. Rows
    for new paths keep their `— TODO` (to be filled by the code-reader pass).
    """
    if not preserved:
        return block
    trailing_nl = block.endswith("\n")
    lines = block.splitlines()
    current_path = ""
    out: list[str] = []
    for line in lines:
        m = SECTION_HEADER_RE.match(line)
        if m:
            current_path = _section_path_context(m.group(1), pkg_name)
            out.append(line)
            continue
        stripped = line.strip()
        if stripped.startswith("|"):
            cells = _split_pipes(stripped)
            if len(cells) >= 3:
                bm = _FILE_MAP_PATH_CELL_RE.match(cells[0])
                if bm is None:
                    out.append(line)
                    continue
                full = _file_map_full_path(current_path, bm.group(1))
                preserved_desc = preserved.get(full)
                if preserved_desc and not _is_filled_description(cells[2]):
                    cells[2] = preserved_desc
                    cells = [escape_angle_brackets(c.replace("|", "\\|")) for c in cells]
                    line = "| " + " | ".join(cells) + " |"
        out.append(line)
    result = "\n".join(out)
    return result + "\n" if trailing_nl else result


def inject_file_map(
    page_path: Path,
    file_map_block: str,
    preserved: dict[str, str] | None = None,
) -> None:
    """Replace the entire `## File map` section with `file_map_block`.

    Faithful port of the plugin scanner-agent step: locates the FIRST
    `## File map` H2 heading at column 0 and replaces from that heading through
    the next H2 (or EOF) with `file_map_block`. Unlike `inject_narrative`, the
    replaced region *includes* the heading, because `build_file_map()` /
    `build_file_maps()` emit a complete `## File map - <name>` block (its own
    heading plus per-folder H3 tables). Writes atomically via temp-file +
    `os.replace`.

    The block carries deterministic `path` + `kind` rows with `— TODO`
    Description placeholders. When ``preserved`` is provided (a
    ``{package_root_path: description}`` map, live-sourced under PTO from the
    page's current File map at inject time), each row whose path still appears
    in the block has its `— TODO` Description restored from the map. New paths
    keep `— TODO`, to be filled by the code-reader pass.

    Idempotent: the deterministic block is stable for a fixed file tree, so a
    second call with the same block (and same ``preserved``) produces
    byte-identical output.

    Logs a WARNING and returns without writing when the page is missing a
    `## File map` heading (defensive — package templates always carry it).

    Raises:
        FileNotFoundError: when `page_path` does not exist.
    """
    text = page_path.read_text(encoding="utf-8")  # raises FileNotFoundError naturally

    match = _FILE_MAP_HEADING_RE.search(text)
    if match is None:
        _logger.warning("inject_file_map: no `## File map` heading found at %s", page_path)
        return

    section_start = match.start()
    next_h2 = _NEXT_H2_RE.search(text, match.end())
    section_end = next_h2.start() if next_h2 is not None else len(text)

    block = file_map_block.strip()
    if block and preserved:
        name_match = _FILE_MAP_NAME_RE.search(block)
        pkg_name = name_match.group(1).strip() if name_match else ""
        block = _merge_preserved_descriptions(block, pkg_name, preserved)
    new_section = f"{block}\n\n" if block else ""
    new_content = text[:section_start] + new_section + text[section_end:]

    tmp_path = page_path.with_suffix(page_path.suffix + ".tmp")
    tmp_path.write_text(new_content, encoding="utf-8")
    os.replace(tmp_path, page_path)


def _file_map_section_span(text: str) -> tuple[int, int] | None:
    """Return ``(start, end)`` byte offsets of the `## File map` section
    (heading through next H2 / EOF), or None when there is no File map heading."""
    match = _FILE_MAP_HEADING_RE.search(text)
    if match is None:
        return None
    next_h2 = _NEXT_H2_RE.search(text, match.end())
    return match.start(), (next_h2.start() if next_h2 is not None else len(text))


def file_map_todo_paths(page_path: Path) -> list[str]:
    """Return the package-root paths of File-map *file* rows whose Description
    is still an unfilled placeholder (`— TODO`).

    Used to scope the code-reader description pass: a package with no unfilled
    rows needs no model call. Returns ``[]`` when the page has no File map
    section. Directory rows are excluded (descriptions target files).
    """
    text = page_path.read_text(encoding="utf-8")
    span = _file_map_section_span(text)
    if span is None:
        return []
    section = text[span[0] : span[1]]
    name_match = _FILE_MAP_NAME_RE.search(section)
    pkg_name = name_match.group(1).strip() if name_match else ""
    todo: list[str] = []
    current_path = ""
    lines = section.splitlines()
    n = len(lines)
    i = 0
    while i < n:
        m = SECTION_HEADER_RE.match(lines[i])
        if not m:
            i += 1
            continue
        current_path = _section_path_context(m.group(1), pkg_name)
        i += 1
        section_lines: list[str] = []
        while i < n and not SECTION_HEADER_RE.match(lines[i]):
            section_lines.append(lines[i])
            i += 1
        table = parse_markdown_table("\n".join(section_lines))
        if table is None:
            continue
        _headers, rows = table
        for row in rows:
            if len(row) < 3:
                continue
            kind = row[1].strip().lower()
            bm = _FILE_MAP_PATH_CELL_RE.match(row[0])
            token = bm.group(1) if bm else row[0].strip()
            if kind == "dir" or token.endswith("/") or not token.strip("/"):
                continue
            if not _is_filled_description(row[2]):
                todo.append(_file_map_full_path(current_path, token))
    return todo


def dir_section_todo_contexts(page_path: Path) -> list[str]:
    """Return package-root path contexts for H3 directory sections whose placeholder is unfilled.

    Walks the File-map H3 sections. For each section where the line immediately after
    the ``### heading`` is exactly the section placeholder string, returns that section's
    package-root path context (``""`` for the root section ``### pkg/``, ``"src"`` for
    ``### pkg/src/``). Returns ``[]`` when no unfilled sections exist or the page has no
    File map heading.
    """
    text = page_path.read_text(encoding="utf-8")
    span = _file_map_section_span(text)
    if span is None:
        return []
    section = text[span[0] : span[1]]
    name_match = _FILE_MAP_NAME_RE.search(section)
    pkg_name = name_match.group(1).strip() if name_match else ""
    contexts: list[str] = []
    lines = section.splitlines()
    n = len(lines)
    for i in range(n - 1):
        m = SECTION_HEADER_RE.match(lines[i])
        if m and lines[i + 1] == _DIR_SECTION_PLACEHOLDER:
            contexts.append(_section_path_context(m.group(1), pkg_name))
    return contexts


def is_overview_unfilled(page_path: Path) -> bool:
    """Return True when the ## File map overview placeholder is still unfilled."""
    text = page_path.read_text(encoding="utf-8")
    match = _FILE_MAP_HEADING_RE.search(text)
    if match is None:
        return False
    rest = text[match.end() :]
    first_line = rest.split("\n", 1)[0]
    return first_line == _OVERVIEW_PLACEHOLDER


def fill_file_map_descriptions(page_path: Path, descriptions: dict[str, str]) -> int:
    """Fill unfilled (`— TODO`) File-map Description cells in ``page_path`` with
    ``descriptions`` (keyed by package-root path).

    Only placeholder cells are touched — already-filled (human or
    preserved) descriptions are never overwritten (the merge step checks
    ``_is_filled_description``). Writes atomically. Returns the number of cells
    filled (0 when nothing matched or the page has no File map heading).

    Raises:
        FileNotFoundError: when ``page_path`` does not exist.
    """
    if not descriptions:
        return 0
    text = page_path.read_text(encoding="utf-8")
    span = _file_map_section_span(text)
    if span is None:
        _logger.warning(
            "fill_file_map_descriptions: no `## File map` heading found at %s",
            page_path,
        )
        return 0
    section = text[span[0] : span[1]]
    # Only count keys that correspond to a currently-unfilled row, so the
    # return value reflects real fills (not re-applying already-filled cells).
    todo_before = set(file_map_todo_paths(page_path))
    applied = sum(1 for p in descriptions if p in todo_before)
    if applied == 0:
        return 0
    name_match = _FILE_MAP_NAME_RE.search(section)
    pkg_name = name_match.group(1).strip() if name_match else ""
    new_section = _merge_preserved_descriptions(section, pkg_name, descriptions)
    if new_section == section:
        return 0
    new_content = text[: span[0]] + new_section + text[span[1] :]
    tmp_path = page_path.with_suffix(page_path.suffix + ".tmp")
    tmp_path.write_text(new_content, encoding="utf-8")
    os.replace(tmp_path, page_path)
    return applied


def fill_dir_section_descriptions(page_path: Path, descriptions: dict[str, str]) -> int:
    """Replace the placeholder line in H3 directory sections whose context key is in descriptions.

    Keys are package-root path contexts (``""`` = root section, ``"src"`` = ``### pkg/src/``).
    Only replaces lines that are exactly ``_DIR_SECTION_PLACEHOLDER``. Atomic write.
    Returns count of replacements made (0 when nothing matched or no File map heading).

    Raises:
        FileNotFoundError: when ``page_path`` does not exist.
    """
    if not descriptions:
        return 0
    text = page_path.read_text(encoding="utf-8")
    span = _file_map_section_span(text)
    if span is None:
        _logger.warning(
            "fill_dir_section_descriptions: no `## File map` heading found at %s",
            page_path,
        )
        return 0
    section = text[span[0] : span[1]]
    name_match = _FILE_MAP_NAME_RE.search(section)
    pkg_name = name_match.group(1).strip() if name_match else ""
    lines = section.splitlines()
    n = len(lines)
    out: list[str] = []
    filled = 0
    i = 0
    while i < n:
        out.append(lines[i])
        m = SECTION_HEADER_RE.match(lines[i])
        if m and i + 1 < n and lines[i + 1] == _DIR_SECTION_PLACEHOLDER:
            ctx = _section_path_context(m.group(1), pkg_name)
            if ctx in descriptions:
                out.append(escape_angle_brackets(descriptions[ctx]))
                filled += 1
                i += 2
                continue
        i += 1
    if filled == 0:
        return 0
    trailing = "\n" if section.endswith("\n") else ""
    new_section = "\n".join(out) + trailing
    new_content = text[: span[0]] + new_section + text[span[1] :]
    tmp = page_path.with_suffix(page_path.suffix + ".tmp")
    tmp.write_text(new_content, encoding="utf-8")
    os.replace(tmp, page_path)
    return filled


def fill_file_map_overview(page_path: Path, overview: str) -> bool:
    """Replace the ## File map overview placeholder with overview.

    Only replaces when the line immediately following ``## File map - <name>`` is
    exactly ``_OVERVIEW_PLACEHOLDER``. Atomic write. Returns True if replaced.

    Raises:
        FileNotFoundError: when ``page_path`` does not exist.
    """
    text = page_path.read_text(encoding="utf-8")
    match = _FILE_MAP_HEADING_RE.search(text)
    if match is None:
        return False
    rest = text[match.end() :]
    first_line = rest.split("\n", 1)[0]
    if first_line != _OVERVIEW_PLACEHOLDER:
        return False
    new_content = text[: match.end()] + escape_angle_brackets(overview) + rest[len(first_line) :]
    tmp = page_path.with_suffix(page_path.suffix + ".tmp")
    tmp.write_text(new_content, encoding="utf-8")
    os.replace(tmp, page_path)
    return True


def extract_file_map_descriptions(page_path: Path) -> dict[str, str]:
    """Return ``{package_root_path: description}`` for all filled file rows in the File map.

    Page-level wrapper around ``_extract_file_map_descriptions``. Used by
    scan.py Step 10d to get child file descriptions without duplicating
    section-walking. Returns ``{}`` when the page has no File map heading.

    Raises:
        FileNotFoundError: when ``page_path`` does not exist.
    """
    text = page_path.read_text(encoding="utf-8")
    span = _file_map_section_span(text)
    if span is None:
        return {}
    section = text[span[0] : span[1]]
    name_match = _FILE_MAP_NAME_RE.search(section)
    pkg_name = name_match.group(1).strip() if name_match else ""
    return _extract_file_map_descriptions(section, pkg_name)
