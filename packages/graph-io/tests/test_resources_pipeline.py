"""Pipeline integration: graph.resources -> resource nodes + edges via update.run."""

from __future__ import annotations

from pathlib import Path

from _git_repo import init_repo, write_and_commit
from graph_io import schema, store, update
from workspace_io.paths import graph_dir

_MANIFEST = (
    "version: 2\n"
    "initialized_at: '2026-06-20'\n"
    "graph:\n"
    "  resources:\n"
    "    location-service:\n"
    "      resource_kind: api\n"
    "      provided_by: location-aws-node-ts\n"
    "      consumed_by: [location-data-node-ts]\n"
)


def test_pipeline_emits_resources(tmp_path: Path) -> None:
    init_repo(tmp_path)
    write_and_commit(
        tmp_path,
        {
            "location-aws-node-ts/pyproject.toml": '[project]\nname = "location-aws-node-ts"\nversion = "0.1.0"\n',
            "location-aws-node-ts/src/a.py": "x = 1\n",
            "location-data-node-ts/pyproject.toml": '[project]\nname = "location-data-node-ts"\nversion = "0.1.0"\n',
            "location-data-node-ts/src/b.py": "y = 2\n",
        },
        "init",
    )
    # Workspace == repo root for this test; write the manifest there.
    (tmp_path / ".graph-wiki.yaml").write_text(_MANIFEST, encoding="utf-8")

    update.run(tmp_path, workspace=tmp_path, full=True)

    conn = store.read_only_connect(graph_dir(tmp_path) / "code.db")
    try:
        assert conn.execute("SELECT COUNT(*) FROM nodes WHERE kind='resource'").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM edges WHERE kind='provides'").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM edges WHERE kind='consumes'").fetchone()[0] == 1
        dv = conn.execute("SELECT value FROM metadata WHERE key='deriver_version'").fetchone()
        assert dv == (str(schema.DERIVER_VERSION),)
    finally:
        conn.close()
