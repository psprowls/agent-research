"""Unit tests for build_skill_ingest_brief — the skill-aware Claude-branch brief.

Pure / Bedrock-free: assembles a manifest from gather_skill_sources without any
model_adapter / subagent_runtime import. The agent reads `included_files` itself
before chunking the skill into wiki/guidance/<topic>/<slug>.md pages.
"""

from __future__ import annotations

from pathlib import Path

from wiki_io.ingest_source import build_skill_ingest_brief, resolve_skill_anchor


def _make_skill(root: Path) -> Path:
    """Minimal skill: SKILL.md linking one companion .md, plus a non-md script.

    Returns the skill directory. `scripts/` makes the bundle scripts_dominant.
    """
    skill = root / "my-skill"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\nname: My Skill\n---\n\n# My Skill\n\nSee [advanced](references/advanced.md).\n",
        encoding="utf-8",
    )
    (skill / "references").mkdir()
    (skill / "references" / "advanced.md").write_text("# Advanced\n\nMore.\n", encoding="utf-8")
    (skill / "scripts").mkdir()
    (skill / "scripts" / "helper.py").write_text("print('x')\n", encoding="utf-8")
    return skill


def _wiki(root: Path) -> Path:
    wiki = root / "wiki"
    wiki.mkdir()
    return wiki


def test_skill_directory_emits_skill_brief(tmp_path: Path) -> None:
    skill = _make_skill(tmp_path)
    wiki = _wiki(tmp_path)

    brief = build_skill_ingest_brief(
        anchor=resolve_skill_anchor(skill),
        wiki=wiki,
        repo=tmp_path,
        workspace_root=tmp_path,
    )

    assert brief["is_skill"] is True
    assert brief["source_type"] == "skill"
    assert brief["title"] == "My Skill"
    assert brief["slug"] == "my-skill"
    assert brief["guidance_dir"] == "guidance/"
    assert brief["suggested_summary_path"].startswith("sources/")
    assert brief["suggested_summary_path"].endswith("-my-skill.md")
    assert brief["included_files"] == ["SKILL.md", "references/advanced.md"]
    assert "scripts/helper.py" in brief["excluded_files"]
    assert brief["merge_mode"] is False
    assert "state_gate" in brief
    assert brief["entity_match"] == {"uri": None, "entity_filename": None}


def test_bare_skill_md_file_resolves_same_brief(tmp_path: Path) -> None:
    skill = _make_skill(tmp_path)
    wiki = _wiki(tmp_path)
    anchor = resolve_skill_anchor(skill / "SKILL.md")
    assert anchor is not None

    brief = build_skill_ingest_brief(anchor=anchor, wiki=wiki, repo=tmp_path, workspace_root=tmp_path)

    assert brief["is_skill"] is True
    assert brief["included_files"] == ["SKILL.md", "references/advanced.md"]
    assert brief["source_path"] == str(skill.resolve())


def test_scripts_dominant_sets_warning(tmp_path: Path) -> None:
    # A skill with a top-level scripts/ dir is scripts_dominant by definition.
    skill = _make_skill(tmp_path)
    wiki = _wiki(tmp_path)

    brief = build_skill_ingest_brief(
        anchor=resolve_skill_anchor(skill), wiki=wiki, repo=tmp_path, workspace_root=tmp_path
    )

    assert brief["scripts_dominant"] is True
    assert "scripts_dominant" in brief["warnings"]


def test_excluded_files_capture_non_markdown_only(tmp_path: Path) -> None:
    skill = _make_skill(tmp_path)
    wiki = _wiki(tmp_path)

    brief = build_skill_ingest_brief(
        anchor=resolve_skill_anchor(skill), wiki=wiki, repo=tmp_path, workspace_root=tmp_path
    )

    # Every non-.md file under the skill dir is excluded; no .md leaks in.
    assert brief["excluded_files"] == ["scripts/helper.py"]
    assert all(not p.endswith(".md") for p in brief["excluded_files"])


def test_non_skill_path_resolves_to_none(tmp_path: Path) -> None:
    # A plain folder with no SKILL.md is not a skill; the builder is never invoked.
    folder = tmp_path / "raw" / "examples" / "demo"
    folder.mkdir(parents=True)
    (folder / "a.md").write_text("# A\n", encoding="utf-8")

    assert resolve_skill_anchor(folder) is None
    # A loose file is likewise not a skill anchor.
    assert resolve_skill_anchor(folder / "a.md") is None
