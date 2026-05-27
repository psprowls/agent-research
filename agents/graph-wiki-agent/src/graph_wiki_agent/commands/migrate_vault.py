"""``cg migrate-vault`` — v1.8 entity-restructure atomic cutover.

Phase 46. Public API: :func:`run_migrate_vault`.

Composition (per CONTEXT.md D-06):
    0. Idempotency guard (CONTEXT D-09 / D-10)
    1. write_entities — populate ``wiki/entities/``
    2. link_rewriter.rewrite_vault — rewrite inbound wikilinks in 5 curated lanes
    3. git rm -r — remove old layout directories
    4. generate_index — write ``wiki/index.md`` (graph-driven)
    5. update_index — regenerate per-folder sub-indexes (Phase 45 surgical form)
    6. write manifest marker — ``.graph-wiki/manifest.json``
    7. git commit — atomic single commit

On ANY failure between steps 1 and 6, the script aborts before commit (D-07);
exit code 2 is returned and the working tree is left dirty for manual recovery
via ``git restore --staged .`` + ``git restore .``.

``--dry-run`` (D-11/D-12) computes the rewrite table read-only and prints a
preview; no writes, no commit. ``--force`` (D-10) bypasses the idempotency
check. ``--no-write-marker`` (testing affordance) runs the full cutover but
skips step 6.
"""
from __future__ import annotations

import datetime as _dt
import json
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Optional

from wiki_io._workspace import resolve_wiki_and_repo
from wiki_io.entity_writer import ADMITTED_KINDS_V18, write_entities
from wiki_io.index_generator import generate_index
from wiki_io.link_rewriter import (
    OLD_LAYOUT_ROOTS,
    build_rewrite_table,
    rewrite_vault,
)
from wiki_io.update_index import update_index


MIGRATION_MARKER_VALUE = "v1.8-entity-restructure"
COMMIT_MESSAGE = """feat(46): v1.8 entity restructure cutover

Atomic vault migration:
- Populate wiki/entities/ via write_entities
- Rewrite inbound wikilinks across 5 curated lanes
- Remove wiki/packages/, wiki/dependencies/, wiki/domain/, wiki/plugin/, wiki/package-family/
- Regenerate wiki/index.md (generate_index) + per-folder sub-indexes (update_index)
- Write .graph-wiki/manifest.json migration marker

Refs: MIGRATION-01, MIGRATION-02, MIGRATION-03, MIGRATION-04, MIGRATION-05
"""


def _utc_iso_z() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _is_already_migrated(manifest_path: Path) -> bool:
    if not manifest_path.exists():
        return False
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return manifest.get("migrated_to") == MIGRATION_MARKER_VALUE


def _is_clean_post_migration(manifest_path: Path, wiki_root: Path) -> bool:
    """True when marker present AND no old layout dirs remain — ``--force`` is a no-op."""
    if not manifest_path.exists():
        return False
    any_remain = any((wiki_root / d).exists() for d in OLD_LAYOUT_ROOTS)
    return not any_remain


def _open_graph_db(workspace_root: Path) -> sqlite3.Connection:
    db_path = workspace_root / ".graph-wiki" / "graph.db"
    if not db_path.exists():
        raise FileNotFoundError(f"graph DB not found at {db_path}")
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _git_rm_old_dirs(repo_root: Path, wiki_root: Path) -> list[str]:
    """Stage ``git rm -r`` for any existing old layout dirs. Returns the list of paths removed."""
    targets: list[str] = []
    for dir_name in OLD_LAYOUT_ROOTS:
        dir_path = wiki_root / dir_name
        if dir_path.exists():
            try:
                rel = str(dir_path.relative_to(repo_root))
            except ValueError:
                rel = str(dir_path)
            targets.append(rel)
    if not targets:
        return []
    subprocess.run(
        ["git", "rm", "-r", *targets],
        cwd=repo_root,
        check=True,
    )
    return targets


def _git_commit_cutover(repo_root: Path) -> None:
    subprocess.run(["git", "add", "-A"], cwd=repo_root, check=True)
    subprocess.run(
        ["git", "commit", "-m", COMMIT_MESSAGE],
        cwd=repo_root,
        check=True,
    )


def _write_manifest(manifest_path: Path, rewrite_result) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "migrated_to": MIGRATION_MARKER_VALUE,
        "migrated_at": _utc_iso_z(),
        "rewrite_count": rewrite_result.rewrites_total,
        "rewrite_unresolved": rewrite_result.unresolved_total,
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _human_content_warning(dir_path: Path) -> Optional[str]:
    """Return ``⚠ human content detected: ...`` if any ``.md`` file in ``dir_path``
    has frontmatter indicating human-authored content (status/notes/last_reviewed/owner)."""
    try:
        import frontmatter  # noqa: WPS433 — lazy import; not used in hot paths.
    except ImportError:
        return None
    sentinel_keys = ("status", "notes", "last_reviewed", "owner")
    for md in dir_path.rglob("*.md"):
        try:
            post = frontmatter.load(md)
        except Exception:
            continue
        for key in sentinel_keys:
            val = post.metadata.get(key)
            if val:
                return f"⚠ human content detected: {key}: {val} in {md.name}"
    return None


def _print_preview(wiki_root: Path, table: dict, project_name: str) -> None:
    """Print the dry-run preview to stdout (CONTEXT D-12)."""
    resolved = {k: v for k, v in table.items() if v is not None}
    unresolved = {k: v for k, v in table.items() if v is None}
    by_prefix = {
        "packages/": 0,
        "dependencies/": 0,
        "domain/": 0,
        "plugin/": 0,
        "test-suites/": 0,
    }
    for k in resolved:
        for p in by_prefix:
            if k.startswith(p):
                by_prefix[p] += 1
                break
    print(f"Vault migration preview — {project_name}\n")
    print("Entities (from graph):")
    # Source 1 emits bare + wiki/-prefixed forms for every entity — divide by 2.
    print(f"  * {by_prefix['packages/'] // 2} packages")
    print(f"  * {by_prefix['dependencies/'] // 2} dependencies")
    print(f"  * {by_prefix['domain/'] // 2} domains")
    print(f"  * {by_prefix['plugin/'] // 2} plugins")
    print(f"  * {by_prefix['test-suites/'] // 2} test_suites")
    print()
    print(f"Wikilink rewrites ({len(resolved)} total table entries):")
    for old, new in sorted(resolved.items())[:10]:
        print(f"  {old}  →  {new}")
    if len(resolved) > 10:
        print(f"  ... and {len(resolved) - 10} more")
    print()
    print(f"Unresolvable ({len(unresolved)} — will be left as-is):")
    for k in sorted(unresolved.keys())[:5]:
        print(f"  {k}")
    if len(unresolved) > 5:
        print(f"  ... and {len(unresolved) - 5} more")
    print()
    print("Directories to remove (git rm -r):")
    for dir_name in OLD_LAYOUT_ROOTS:
        dir_path = wiki_root / dir_name
        if dir_path.exists():
            md_count = sum(1 for _ in dir_path.rglob("*.md"))
            warning = _human_content_warning(dir_path)
            warn_suffix = f"  {warning}" if warning else ""
            print(f"  * wiki/{dir_name}/  ({md_count} files){warn_suffix}")
    print()
    print("Idempotency marker would be written to .graph-wiki/manifest.json")
    print()
    print("Run without --dry-run to execute as one atomic commit.")


def run_migrate_vault(
    dry_run: bool,
    force: bool,
    write_marker: bool,
    *,
    workspace_path: Optional[Path] = None,
) -> int:
    """Execute the 7-step atomic cutover. Returns process exit code.

    Exit codes:
        0 — success (or already-migrated no-op).
        1 — pre-flight failure (missing graph DB, missing wiki dir, bad workspace).
        2 — runtime failure during any step (aborts before commit; D-07).
    """
    try:
        wiki_root, repo_root = resolve_wiki_and_repo(workspace_path)
    except Exception as e:
        print(f"[error] workspace resolution failed: {e}", file=sys.stderr)
        return 1
    if not wiki_root.is_dir():
        print(f"[error] wiki directory not found: {wiki_root}", file=sys.stderr)
        return 1
    workspace_root = wiki_root.parent
    manifest_path = workspace_root / ".graph-wiki" / "manifest.json"
    log_path = workspace_root / ".graph-wiki" / "migration.log"

    # Step 0: idempotency guard (D-09 / D-10).
    if not force:
        if _is_already_migrated(manifest_path):
            print("Vault is already migrated. Use --force to re-run (not recommended).")
            return 0
    else:
        if _is_clean_post_migration(manifest_path, wiki_root):
            print("Vault is already cleanly migrated. --force has no effect.")
            return 0

    # Open graph DB for build_rewrite_table + write_entities + generate_index.
    try:
        conn = _open_graph_db(workspace_root)
    except FileNotFoundError as e:
        print(f"[error] {e}", file=sys.stderr)
        return 1

    try:
        # Build the rewrite table — always needed (read-only against the graph).
        table = build_rewrite_table(
            conn, wiki_root, log_path=None if dry_run else log_path
        )

        if dry_run:
            _print_preview(wiki_root, table, project_name=workspace_root.name)
            return 0

        # Step 1: write_entities.
        try:
            write_entities(conn, wiki_root, ADMITTED_KINDS_V18)
        except Exception as e:
            print(f"[error] write_entities failed: {e}", file=sys.stderr)
            return 2

        # Step 2: link_rewriter.rewrite_vault.
        try:
            rewrite_result = rewrite_vault(wiki_root, table, log_path=log_path)
        except Exception as e:
            print(f"[error] link_rewriter failed: {e}", file=sys.stderr)
            return 2

        # Step 3: git rm old dirs.
        try:
            _git_rm_old_dirs(repo_root, wiki_root)
        except subprocess.CalledProcessError as e:
            print(f"[error] git rm failed: {e}", file=sys.stderr)
            return 2

        # Step 4: generate_index.
        try:
            generate_index(conn, wiki_root)
        except Exception as e:
            print(f"[error] generate_index failed: {e}", file=sys.stderr)
            return 2

        # Step 5: update_index (per-folder sub-indexes — Phase 45 surgical form).
        try:
            update_index(wiki_root)
        except Exception as e:
            print(f"[error] update_index failed: {e}", file=sys.stderr)
            return 2

        # Step 6: manifest marker (skipped under --no-write-marker for tests).
        if write_marker:
            try:
                _write_manifest(manifest_path, rewrite_result)
            except Exception as e:
                print(f"[error] manifest write failed: {e}", file=sys.stderr)
                return 2

        # Step 7: atomic commit.
        try:
            _git_commit_cutover(repo_root)
        except subprocess.CalledProcessError as e:
            print(f"[error] git commit failed: {e}", file=sys.stderr)
            return 2

        print(
            f"Cutover complete: {rewrite_result.files_modified} files modified, "
            f"{rewrite_result.rewrites_total} wikilinks rewritten, "
            f"{rewrite_result.unresolved_total} unresolvable (logged)."
        )
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass
