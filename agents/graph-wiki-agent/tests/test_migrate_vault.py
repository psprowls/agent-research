"""Phase 46 Plan 03: CLI + integration tests for ``graph-wiki-agent migrate-vault``."""
from __future__ import annotations

import json
import sqlite3
import subprocess
from pathlib import Path

import pytest

from graph_io.schema import apply_schema
from graph_wiki_agent.commands.migrate_vault import (
    MIGRATION_MARKER_VALUE,
    run_migrate_vault,
)


# ----------------------------------------------------------------------------
# Fixture: minimal git-initialized vault + seeded graph DB
# ----------------------------------------------------------------------------


def _git_init(repo: Path) -> None:
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=repo, check=True)


def _seed_graph_db(db_path: Path) -> None:
    """Create the graph schema and insert 1 package + 1 domain node."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    try:
        apply_schema(conn)
        conn.execute(
            "INSERT INTO nodes (kind, name, path, line, attrs_json, uri) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("package", "graph-io", None, None, "{}", "pkg:agent-research/graph-io"),
        )
        conn.execute(
            "INSERT INTO nodes (kind, name, path, line, attrs_json, uri) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("domain", "billing", None, None, "{}", "domain:agent-research/billing"),
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def vault(tmp_path, monkeypatch):
    """Build a minimal fixture vault with git init + graph DB + seed pages.

    Returns ``(repo_root, wiki_root)``.
    """
    repo = tmp_path / "agent-research"
    repo.mkdir()
    _git_init(repo)

    wiki = repo / "wiki"
    (wiki / "concepts").mkdir(parents=True)
    (wiki / "adrs").mkdir()
    (wiki / "architecture").mkdir()
    (wiki / "sources").mkdir()
    (wiki / "entities").mkdir()
    (wiki / "packages" / "graph-io").mkdir(parents=True)
    (wiki / "packages" / "graph-io" / "index.md").write_text("legacy page\n")
    (repo / "work").mkdir()

    # Curated-lane files with wikilinks.
    (wiki / "concepts" / "per-repo-layout.md").write_text(
        "Refers to [[packages/graph-io/index]] for the package.\n",
        encoding="utf-8",
    )
    (wiki / "adrs" / "001.md").write_text(
        "[[packages/graph-io/index|graph-io]]\n",
        encoding="utf-8",
    )

    # Graph DB.
    (repo / ".graph").mkdir(exist_ok=True)
    _seed_graph_db(repo / ".graph" / "code.db")

    # Initial commit so the cutover has something to git-rm and amend.
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "initial"], cwd=repo, check=True)

    # Point the CLI at this workspace.
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(repo))
    return repo, wiki


# ----------------------------------------------------------------------------
# Tests
# ----------------------------------------------------------------------------


def test_migrate_vault_dry_run_makes_no_changes(vault):
    repo, wiki = vault
    exit_code = run_migrate_vault(dry_run=True, force=False, write_marker=True)
    assert exit_code == 0
    # No file changes.
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True
    ).stdout
    assert status == ""
    # No marker.
    assert not (repo / ".graph-wiki" / "manifest.json").exists()
    # Old dir still present.
    assert (wiki / "packages" / "graph-io" / "index.md").exists()


def test_migrate_vault_dry_run_output_sections(vault, capsys):
    """Assert the dry-run output contains the sections required by CONTEXT D-12."""
    run_migrate_vault(dry_run=True, force=False, write_marker=True)
    out = capsys.readouterr().out
    assert "Vault migration preview" in out
    assert "Entities (from graph):" in out
    assert "Wikilink rewrites" in out
    assert "Directories to remove" in out
    assert "Idempotency marker would be written" in out
    assert "Run without --dry-run" in out


def test_migrate_vault_full_cutover_writes_manifest(vault):
    repo, wiki = vault
    exit_code = run_migrate_vault(dry_run=False, force=False, write_marker=True)
    assert exit_code == 0
    manifest_path = repo / ".graph-wiki" / "manifest.json"
    assert manifest_path.exists()
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert data["migrated_to"] == MIGRATION_MARKER_VALUE
    assert "migrated_at" in data
    assert "rewrite_count" in data
    assert "rewrite_unresolved" in data


def test_migrate_vault_full_cutover_removes_old_dirs(vault):
    repo, wiki = vault
    run_migrate_vault(dry_run=False, force=False, write_marker=True)
    assert not (wiki / "packages").exists()


def test_migrate_vault_full_cutover_populates_entities(vault):
    repo, wiki = vault
    run_migrate_vault(dry_run=False, force=False, write_marker=True)
    entities = list((wiki / "entities").glob("*.md"))
    assert any("pkg__agent-research__graph-io" in p.name for p in entities)


def test_migrate_vault_single_commit(vault):
    repo, wiki = vault
    before = subprocess.run(
        ["git", "rev-list", "--count", "HEAD"],
        cwd=repo, capture_output=True, text=True,
    ).stdout.strip()
    run_migrate_vault(dry_run=False, force=False, write_marker=True)
    after = subprocess.run(
        ["git", "rev-list", "--count", "HEAD"],
        cwd=repo, capture_output=True, text=True,
    ).stdout.strip()
    assert int(after) == int(before) + 1
    subject = subprocess.run(
        ["git", "log", "-1", "--format=%s"],
        cwd=repo, capture_output=True, text=True,
    ).stdout.strip()
    assert subject == "feat(46): v1.8 entity restructure cutover"


def test_migrate_vault_second_run_no_op(vault, capsys):
    repo, wiki = vault
    run_migrate_vault(dry_run=False, force=False, write_marker=True)
    capsys.readouterr()  # drain first run output
    exit_code = run_migrate_vault(dry_run=False, force=False, write_marker=True)
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "already migrated" in out.lower()
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True
    ).stdout
    assert status == ""


def test_migrate_vault_force_recovery(vault, capsys):
    repo, wiki = vault
    # Simulate a partial-cutover state: write the marker but leave wiki/packages/ present.
    manifest_path = repo / ".graph-wiki" / "manifest.json"
    manifest_path.parent.mkdir(exist_ok=True, parents=True)
    manifest_path.write_text(
        json.dumps({
            "migrated_to": MIGRATION_MARKER_VALUE,
            "migrated_at": "2026-05-27T00:00:00Z",
        }),
        encoding="utf-8",
    )
    # Without --force: skip with "already migrated".
    exit_code = run_migrate_vault(dry_run=False, force=False, write_marker=True)
    assert exit_code == 0
    assert (wiki / "packages").exists()
    capsys.readouterr()
    # Commit the marker first so the cutover has a clean working tree.
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "stash marker"], cwd=repo, check=True)
    # With --force: proceeds and removes the dir.
    exit_code = run_migrate_vault(dry_run=False, force=True, write_marker=True)
    assert exit_code == 0
    assert not (wiki / "packages").exists()


def test_migrate_vault_force_no_effect_on_clean_state(vault, capsys):
    repo, wiki = vault
    # Run a full cutover.
    run_migrate_vault(dry_run=False, force=False, write_marker=True)
    capsys.readouterr()
    # Now run with --force on a clean post-migration state.
    exit_code = run_migrate_vault(dry_run=False, force=True, write_marker=True)
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "no effect" in out.lower() or "already" in out.lower()


def test_migrate_vault_no_write_marker(vault):
    repo, wiki = vault
    exit_code = run_migrate_vault(dry_run=False, force=False, write_marker=False)
    assert exit_code == 0
    # Full cutover happened.
    assert not (wiki / "packages").exists()
    # But NO marker.
    assert not (repo / ".graph-wiki" / "manifest.json").exists()


def test_migrate_vault_unresolvable_target_left_alone(vault):
    repo, wiki = vault
    fake_file = wiki / "concepts" / "foo-with-unresolvable.md"
    fake_file.write_text(
        "Refers to [[packages/totally-fake/index]] which is not in the graph.\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "add unresolvable"], cwd=repo, check=True)

    run_migrate_vault(dry_run=False, force=False, write_marker=True)
    content = fake_file.read_text(encoding="utf-8")
    assert "[[packages/totally-fake/index]]" in content
    log_path = repo / ".graph-wiki" / "migration.log"
    assert log_path.exists()
    records = [
        json.loads(line) for line in log_path.read_text().splitlines() if line
    ]
    assert any(
        r.get("phase") == "unresolved"
        and r.get("target") == "packages/totally-fake/index"
        for r in records
    )


def test_migrate_vault_aborts_before_commit_on_failure(vault, monkeypatch):
    repo, wiki = vault
    # Patch the symbol that migrate_vault.py imported, not the source module.
    from graph_wiki_agent.commands import migrate_vault as mv_module

    def boom(*args, **kwargs):
        raise RuntimeError("simulated failure")

    monkeypatch.setattr(mv_module, "generate_index", boom)

    before_count = subprocess.run(
        ["git", "rev-list", "--count", "HEAD"],
        cwd=repo, capture_output=True, text=True,
    ).stdout.strip()
    exit_code = run_migrate_vault(dry_run=False, force=False, write_marker=True)
    assert exit_code == 2
    after_count = subprocess.run(
        ["git", "rev-list", "--count", "HEAD"],
        cwd=repo, capture_output=True, text=True,
    ).stdout.strip()
    # No new commit.
    assert before_count == after_count
    # Working tree has staged changes (the cutover got partway through).
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True
    ).stdout
    assert status != ""


def test_migrate_vault_help_exits_zero():
    """Smoke test that the CLI subcommand registration works end-to-end."""
    result = subprocess.run(
        ["uv", "run", "graph-wiki-agent", "migrate-vault", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "--dry-run" in result.stdout
    assert "--force" in result.stdout
