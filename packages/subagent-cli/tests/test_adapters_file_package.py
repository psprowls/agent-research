from pathlib import Path

import pytest
from graph_io import testing as graph_testing
from subagent_cli.adapters.base import Prepared, RunContext
from subagent_cli.adapters.guidance_classifier import GuidanceClassifierAdapter
from subagent_cli.adapters.package_reader import PackageReaderAdapter


def _seed_db(tmp_path: Path) -> None:
    db = tmp_path / ".graph-wiki" / "code.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    graph_testing.open_store(db, create=True).close()


def test_run_context_lazy_conn(tmp_path):
    _seed_db(tmp_path)
    ctx = RunContext(workspace=tmp_path, repo_root=tmp_path, wiki=tmp_path / "wiki")
    c1 = ctx.graph_reader()
    c2 = ctx.graph_reader()
    assert c1 is c2  # cached
    ctx.close()


def test_prepared_defaults():
    p = Prepared(item_id="x", system="s", human="h")
    assert p.parse is None and p.note is None


def _ctx_with_repo(tmp_path):
    _seed_db(tmp_path)
    (tmp_path / "wiki" / "entities").mkdir(parents=True)
    (tmp_path / "wiki" / "guidance").mkdir(parents=True)  # vocab needs the dir
    return RunContext(workspace=tmp_path, repo_root=tmp_path, wiki=tmp_path / "wiki")


async def test_guidance_classifier_prepare_builds_real_prompt(tmp_path):
    ctx = _ctx_with_repo(tmp_path)
    src = tmp_path / "packages" / "foo" / "x.py"
    src.parent.mkdir(parents=True)
    src.write_text("def parse():\n    return 1\n")
    adapter = GuidanceClassifierAdapter()
    prepared = await adapter.prepare(ctx, "packages/foo/x.py")
    assert prepared.item_id == "packages/foo/x.py"
    assert "packages/foo/x.py" in prepared.human  # rel path appears in real prompt
    assert prepared.parse is not None
    # parser is fail-safe on garbage and returns the documented shape
    out = prepared.parse("not yaml :::")
    assert set(out) == {"topics", "tags"}
    ctx.close()


async def test_package_reader_missing_page_raises(tmp_path):
    ctx = _ctx_with_repo(tmp_path)
    adapter = PackageReaderAdapter()
    with pytest.raises(FileNotFoundError):
        await adapter.prepare(ctx, "nonexistent-pkg")
    ctx.close()


async def test_package_reader_prepare_from_entity_page(tmp_path):
    ctx = _ctx_with_repo(tmp_path)
    page = ctx.wiki / "entities" / "pkg_foo.md"
    page.write_text(
        "---\n"
        "uri: pkg:me/repo/foo\n"
        "kind: package\n"
        "language: python\n"
        "---\n"
        "# foo\n\n"
        "## Purpose\n\nTODO: describe the purpose.\n"
    )
    adapter = PackageReaderAdapter()
    prepared = await adapter.prepare(ctx, "foo")
    assert prepared.system  # PACKAGE_READER_SYSTEM
    assert "foo" in prepared.item_id
    assert prepared.note and "tool loop" in prepared.note
    assert prepared.parse is not None
    ctx.close()
