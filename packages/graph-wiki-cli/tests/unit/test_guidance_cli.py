from __future__ import annotations

from unittest.mock import patch

from graph_wiki_cli.cli import app
from typer.testing import CliRunner

runner = CliRunner()


def test_guidance_listed_in_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0, result.output
    assert "guidance" in result.output


def test_guidance_scan_help() -> None:
    result = runner.invoke(app, ["guidance", "scan", "--help"])
    assert result.exit_code == 0, result.output


def test_guidance_scan_invokes_core() -> None:
    from graph_wiki_core.commands.guidance_scan import GuidanceScanResult

    with patch(
        "graph_wiki_cli.guidance_cli.main.run_guidance_scan",
        return_value=GuidanceScanResult(scanned=["a.py"], total=1, vocab_hash="h"),
    ) as scan:
        result = runner.invoke(app, ["guidance", "--repo", ".", "--mode", "test", "scan", "--limit", "5"])
    assert result.exit_code == 0, result.output
    assert scan.call_args.kwargs["limit"] == 5


def test_guidance_suggest_invokes_core_and_renders() -> None:
    from graph_wiki_core.commands.guidance_suggest import GuidanceSuggestResult, RankedGuidance

    fake = GuidanceSuggestResult(
        ranked=[RankedGuidance("python/retry", "high", ["index", "entity"], "matches")],
        index_present=True,
    )
    with patch("graph_wiki_cli.guidance_cli.main.run_guidance_suggest", return_value=fake) as suggest:
        result = runner.invoke(
            app,
            ["guidance", "--repo", ".", "--mode", "test", "suggest", "add retry", "--path", "x.py"],
        )
    assert result.exit_code == 0, result.output
    assert "python/retry" in result.output
    assert suggest.call_args.kwargs["paths"] == ["x.py"]


def test_guidance_suggest_threads_role() -> None:
    from graph_wiki_core.commands.guidance_suggest import GuidanceSuggestResult, RankedGuidance

    fake = GuidanceSuggestResult(
        ranked=[RankedGuidance("python/review", "high", ["index"], "matches")], index_present=True
    )
    with patch("graph_wiki_cli.guidance_cli.main.run_guidance_suggest", return_value=fake) as suggest:
        result = runner.invoke(
            app,
            [
                "guidance",
                "--repo",
                ".",
                "--mode",
                "test",
                "suggest",
                "review diff",
                "--role",
                "review",
                "--path",
                "x.py",
            ],
        )
    assert result.exit_code == 0, result.output
    assert suggest.call_args.kwargs["role"] == "review"
    assert suggest.call_args.kwargs["paths"] == ["x.py"]


def test_guidance_suggest_writes_file(tmp_path) -> None:
    from graph_wiki_core.commands.guidance_suggest import GuidanceSuggestResult, RankedGuidance

    out = tmp_path / "sub" / "bundle.md"
    fake = GuidanceSuggestResult(
        ranked=[RankedGuidance("python/review", "high", ["index"], "matches")],
        assembled="ASSEMBLED BODY",
        index_present=True,
    )
    with patch("graph_wiki_cli.guidance_cli.main.run_guidance_suggest", return_value=fake) as suggest:
        result = runner.invoke(
            app,
            ["guidance", "--mode", "test", "suggest", "review diff", "--file", str(out)],
        )
    assert result.exit_code == 0, result.output
    assert suggest.call_args.kwargs["assemble"] is True
    assert out.read_text(encoding="utf-8") == "ASSEMBLED BODY"


def test_guidance_suggest_file_auto_resolves_via_slug_and_phase(tmp_path, monkeypatch) -> None:
    from graph_wiki_core.commands.guidance_suggest import GuidanceSuggestResult, RankedGuidance

    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(tmp_path))
    fake = GuidanceSuggestResult(
        ranked=[RankedGuidance("python/review", "high", ["index"], "matches")],
        assembled="ASSEMBLED BODY",
        index_present=True,
    )
    with patch("graph_wiki_cli.guidance_cli.main.run_guidance_suggest", return_value=fake) as suggest:
        result = runner.invoke(
            app,
            [
                "guidance",
                "--mode",
                "test",
                "suggest",
                "review diff",
                "--role",
                "review",
                "--slug",
                "my-slug",
                "--phase",
                "plan",
                "--file",
                "auto",
            ],
        )
    assert result.exit_code == 0, result.output
    assert suggest.call_args.kwargs["assemble"] is True
    expected = tmp_path / "wiki" / "work" / "my-slug" / "02-plan-guidance-review.md"
    assert expected.read_text(encoding="utf-8") == "ASSEMBLED BODY"


def test_guidance_suggest_file_explicit_overrides_slug_and_phase(tmp_path, monkeypatch) -> None:
    from graph_wiki_core.commands.guidance_suggest import GuidanceSuggestResult, RankedGuidance

    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(tmp_path))
    out = tmp_path / "explicit" / "bundle.md"
    fake = GuidanceSuggestResult(
        ranked=[RankedGuidance("python/review", "high", ["index"], "matches")],
        assembled="ASSEMBLED BODY",
        index_present=True,
    )
    with patch("graph_wiki_cli.guidance_cli.main.run_guidance_suggest", return_value=fake) as suggest:
        result = runner.invoke(
            app,
            [
                "guidance",
                "--mode",
                "test",
                "suggest",
                "review diff",
                "--role",
                "review",
                "--slug",
                "my-slug",
                "--phase",
                "plan",
                "--file",
                str(out),
            ],
        )
    assert result.exit_code == 0, result.output
    assert suggest.call_args.kwargs["assemble"] is True
    assert out.read_text(encoding="utf-8") == "ASSEMBLED BODY"
    auto_resolved = tmp_path / "wiki" / "work" / "my-slug" / "02-plan-guidance-review.md"
    assert not auto_resolved.exists()


def test_guidance_suggest_file_auto_requires_slug_and_phase() -> None:
    result = runner.invoke(app, ["guidance", "--mode", "test", "suggest", "add retry", "--file", "auto"])
    assert result.exit_code != 0
    assert "--slug" in result.output
    assert "--phase" in result.output


def test_guidance_suggest_json() -> None:
    import json

    from graph_wiki_core.commands.guidance_suggest import GuidanceSuggestResult, RankedGuidance

    fake = GuidanceSuggestResult(
        ranked=[RankedGuidance("python/retry", "high", ["index"], "matches")], index_present=True
    )
    with patch("graph_wiki_cli.guidance_cli.main.run_guidance_suggest", return_value=fake):
        result = runner.invoke(app, ["guidance", "--mode", "test", "suggest", "add retry", "--fmt", "json"])
    assert result.exit_code == 0, result.output
    assert '"slug": "python/retry"' in result.output
    payload = json.loads(result.output)
    assert payload["guidance_file"] is None


def test_guidance_suggest_json_includes_guidance_file_when_written(tmp_path, monkeypatch) -> None:
    import json

    from graph_wiki_core.commands.guidance_suggest import GuidanceSuggestResult, RankedGuidance

    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(tmp_path))
    fake = GuidanceSuggestResult(
        ranked=[RankedGuidance("python/review", "high", ["index"], "matches")],
        assembled="ASSEMBLED BODY",
        index_present=True,
    )
    with patch("graph_wiki_cli.guidance_cli.main.run_guidance_suggest", return_value=fake):
        result = runner.invoke(
            app,
            [
                "guidance",
                "--mode",
                "test",
                "suggest",
                "review diff",
                "--role",
                "review",
                "--slug",
                "my-slug",
                "--phase",
                "plan",
                "--file",
                "auto",
                "--fmt",
                "json",
            ],
        )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    expected = tmp_path / "wiki" / "work" / "my-slug" / "02-plan-guidance-review.md"
    assert payload["guidance_file"] == str(expected)
    assert expected.read_text(encoding="utf-8") == "ASSEMBLED BODY"


def test_guidance_archive_help() -> None:
    result = runner.invoke(app, ["guidance", "archive", "--help"])
    assert result.exit_code == 0, result.output


def test_guidance_archive_invokes_core_with_slugs() -> None:
    from graph_wiki_core.commands.guidance_archive import GuidanceArchiveResult

    fake = GuidanceArchiveResult(
        dry_run=False,
        moved=[{"slug": "python/old", "src": "s", "dst": "d"}],
        skipped=[],
    )
    with patch("graph_wiki_cli.guidance_cli.main.run_guidance_archive", return_value=fake) as arch:
        result = runner.invoke(
            app,
            ["guidance", "--repo", ".", "--mode", "test", "archive", "python/old", "rust/dead"],
        )
    assert result.exit_code == 0, result.output
    assert arch.call_args.kwargs["slugs"] == ["python/old", "rust/dead"]
    assert arch.call_args.kwargs["dry_run"] is False
    assert "python/old" in result.output


def test_guidance_archive_dry_run_flag() -> None:
    from graph_wiki_core.commands.guidance_archive import GuidanceArchiveResult

    fake = GuidanceArchiveResult(dry_run=True, moved=[], skipped=[])
    with patch("graph_wiki_cli.guidance_cli.main.run_guidance_archive", return_value=fake) as arch:
        result = runner.invoke(app, ["guidance", "--mode", "test", "archive", "python/old", "--dry-run"])
    assert result.exit_code == 0, result.output
    assert arch.call_args.kwargs["dry_run"] is True


def test_guidance_archive_json() -> None:
    from graph_wiki_core.commands.guidance_archive import GuidanceArchiveResult

    fake = GuidanceArchiveResult(dry_run=False, moved=[{"slug": "python/old", "src": "s", "dst": "d"}], skipped=[])
    with patch("graph_wiki_cli.guidance_cli.main.run_guidance_archive", return_value=fake):
        result = runner.invoke(app, ["guidance", "--mode", "test", "--fmt", "json", "archive", "python/old"])
    assert result.exit_code == 0, result.output
    assert '"slug": "python/old"' in result.output
