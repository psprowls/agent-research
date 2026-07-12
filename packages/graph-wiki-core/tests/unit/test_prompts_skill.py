from graph_wiki_core.prompts.skill_planner import build_skill_planner_system
from graph_wiki_core.prompts.skill_synthesizer import build_skill_synthesizer_system


def test_skill_planner_system_mentions_chunking_and_yaml():
    s = build_skill_planner_system().lower()
    assert "guidance" in s
    assert "yaml" in s
    # One page per rule; whole-skill for instructional flows.
    assert "rule" in s
    assert "topic" in s


def test_skill_planner_system_inserts_project_context():
    s = build_skill_planner_system(project_context="PROJECT_CTX_MARKER")
    assert "PROJECT_CTX_MARKER" in s


def test_skill_synthesizer_system_fixes_category_and_format():
    s = build_skill_synthesizer_system()
    assert "category: guidance" in s
    assert "## Guidance" in s
    assert "## Applies to" in s
    # Must begin with --- (no code fence), mirroring the ingestor contract.
    assert "---" in s


def test_skill_synthesizer_system_inserts_project_context():
    s = build_skill_synthesizer_system(project_context="SYNTH_CTX_MARKER")
    assert "SYNTH_CTX_MARKER" in s
