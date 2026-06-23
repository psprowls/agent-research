from pathlib import Path

from graph_io import store
from subagent_cli.adapters.base import Prepared, RunContext


def _seed_db(tmp_path: Path) -> Path:
    db = tmp_path / "code.db"
    conn = store.connect(db, create=True)
    conn.close()
    return db


def test_run_context_lazy_conn(tmp_path):
    db = _seed_db(tmp_path)
    ctx = RunContext(workspace=tmp_path, repo_root=tmp_path, wiki=tmp_path / "wiki", db_path=db)
    c1 = ctx.graph_conn()
    c2 = ctx.graph_conn()
    assert c1 is c2  # cached
    ctx.close()


def test_prepared_defaults():
    p = Prepared(item_id="x", system="s", human="h")
    assert p.parse is None and p.note is None
