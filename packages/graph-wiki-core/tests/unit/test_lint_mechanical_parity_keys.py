"""Tests for the five scan() keys added for mechanical parity with gw lint:

obsidian_render_findings, guidance_lint_findings, work_lifecycle,
scanner_heading_drift, source_path_drift.

Each check gets one fixture exercising a violation, plus the no-op paths
(no guidance pages, no wiki/work/ dir). Fail-soft behavior surfaces an
{"error": ...} dict per check instead of killing the pass.
"""

from __future__ import annotations

from pathlib import Path

from graph_wiki_core.commands.lint_mechanical import scan


def _mk_wiki(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    wiki = workspace / "wiki"
    wiki.mkdir(parents=True)
    return wiki


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_obsidian_render_findings_reported(tmp_path: Path) -> None:
    wiki = _mk_wiki(tmp_path)
    _write(
        wiki / "concepts" / "bad.md",
        "---\ntitle: Bad\ncategory: concept\nsummary: s\ntokens: 1\n---\n\na bare <slug> placeholder\n",
    )
    result = scan(wiki, stale_days=90, log_gap_days=14)
    findings = result["obsidian_render_findings"]
    assert [f["rule_id"] for f in findings] == ["obsidian-render-angle-bracket"]
    assert set(findings[0]) == {"rule_id", "severity", "slug", "message"}


def test_obsidian_render_covers_index_pages(tmp_path: Path) -> None:
    wiki = _mk_wiki(tmp_path)
    _write(wiki / "index.md", "---\ntitle: Index\n---\n\na bare <slug> placeholder\n")
    result = scan(wiki, stale_days=90, log_gap_days=14)
    assert [f["slug"] for f in result["obsidian_render_findings"]] == ["index"]


def test_guidance_lint_findings_reported(tmp_path: Path) -> None:
    wiki = _mk_wiki(tmp_path)
    _write(wiki / "concepts" / "ok.md", "---\ntitle: Ok\ncategory: concept\nsummary: s\ntokens: 1\n---\n\nBody.\n")
    # Guidance page with invalid frontmatter (missing required keys).
    _write(wiki / "guidance" / "testing" / "bad-page.md", "---\ntitle: Bad guidance\n---\n\nBody.\n")
    result = scan(wiki, stale_days=90, log_gap_days=14)
    findings = result["guidance_lint_findings"]
    assert findings, "expected guidance lint findings for invalid frontmatter"
    assert all(set(f) == {"rule_id", "severity", "slug", "message"} for f in findings)
    assert any(f["rule_id"] == "guidance-invalid-frontmatter" for f in findings)


def test_guidance_absent_returns_empty(tmp_path: Path) -> None:
    wiki = _mk_wiki(tmp_path)
    _write(wiki / "concepts" / "ok.md", "---\ntitle: Ok\ncategory: concept\nsummary: s\ntokens: 1\n---\n\nBody.\n")
    result = scan(wiki, stale_days=90, log_gap_days=14)
    assert result["guidance_lint_findings"] == []


def test_work_lifecycle_reported(tmp_path: Path) -> None:
    wiki = _mk_wiki(tmp_path)
    _write(
        wiki / "work" / "2026-01-01-broken-item.md",
        "---\ntitle: Broken\nstatus: bogus\nkind: bug\n---\n\n## Summary\nx\n",
    )
    result = scan(wiki, stale_days=90, log_gap_days=14)
    wl = result["work_lifecycle"]
    assert wl["total_items"] == 1
    rule_ids = {f["rule_id"] for f in wl["findings"]}
    assert "status-not-in-enum" in rule_ids
    assert all(set(f) == {"rule_id", "severity", "slug", "message"} for f in wl["findings"])


def test_work_lifecycle_no_work_dir(tmp_path: Path) -> None:
    wiki = _mk_wiki(tmp_path)
    _write(wiki / "concepts" / "ok.md", "---\ntitle: Ok\ncategory: concept\nsummary: s\ntokens: 1\n---\n\nBody.\n")
    result = scan(wiki, stale_days=90, log_gap_days=14)
    wl = result["work_lifecycle"]
    assert wl["total_items"] == 0
    # Parity with gw lint: the sidecar-missing warning still fires on an empty
    # wiki (work-index.json absent); no per-item findings are possible.
    assert {f["rule_id"] for f in wl["findings"]} <= {"sidecar-missing"}


def test_scanner_heading_drift_reported(tmp_path: Path) -> None:
    wiki = _mk_wiki(tmp_path)
    # Entity page (kind: package) missing every deterministic section.
    _write(
        wiki / "entities" / "my-pkg.md",
        "---\nuri: pkg:org/repo/my-pkg\nkind: package\n---\n\n# my-pkg\n\n## Purpose\nhand-written\n",
    )
    result = scan(wiki, stale_days=90, log_gap_days=14)
    drift = result["scanner_heading_drift"]
    assert any("entities/my-pkg" in issue and "## Referenced in wiki" in issue for issue in drift)


def test_source_path_drift_propagated(tmp_path: Path) -> None:
    wiki = _mk_wiki(tmp_path)
    _write(
        wiki / "sources" / "gone.md",
        "---\ntitle: Gone\ncategory: source\nsummary: s\ntokens: 1\nsource_path: raw/gone.md\n---\n\nBody.\n",
    )
    result = scan(wiki, stale_days=90, log_gap_days=14)
    assert result["source_path_drift"] == ["sources/gone"]


def test_print_report_covers_parity_sections(tmp_path: Path, capsys) -> None:
    """print_report renders a section for every parity key (and source-path
    drift), so plugin-side runs surface the findings instead of dropping them."""
    from graph_wiki_core.commands.lint_mechanical import print_report

    wiki = _mk_wiki(tmp_path)
    _write(
        wiki / "sources" / "gone.md",
        "---\ntitle: Gone\ncategory: source\nsummary: s\ntokens: 1\nsource_path: raw/gone.md\n---\n\na bare <slug>\n",
    )
    _write(
        wiki / "work" / "2026-01-01-broken-item.md",
        "---\ntitle: Broken\nstatus: bogus\nkind: bug\n---\n\n## Summary\nx\n",
    )
    result = scan(wiki, stale_days=90, log_gap_days=14)
    print_report(result)
    out = capsys.readouterr().out
    assert "obsidian render" in out.lower()
    assert "guidance lint" in out.lower()
    assert "work lifecycle" in out.lower()
    assert "scanner heading drift" in out.lower()
    assert "source path drift" in out.lower()


def test_new_checks_fail_soft(tmp_path: Path, monkeypatch) -> None:
    """An unexpected exception in a new check surfaces as {"error": ...} for
    that key only — never fatal to the pass, never silently swallowed."""
    import guidance_io.lint as guidance_lint

    def _boom(workspace):
        raise RuntimeError("guidance exploded")

    monkeypatch.setattr(guidance_lint, "run_lint", _boom)

    wiki = _mk_wiki(tmp_path)
    _write(wiki / "concepts" / "ok.md", "---\ntitle: Ok\ncategory: concept\nsummary: s\ntokens: 1\n---\n\nBody.\n")
    result = scan(wiki, stale_days=90, log_gap_days=14)
    assert result["guidance_lint_findings"] == {"error": "guidance exploded"}
    # The rest of the pass is unaffected.
    assert result["work_lifecycle"]["total_items"] == 0
    assert result["obsidian_render_findings"] == []
