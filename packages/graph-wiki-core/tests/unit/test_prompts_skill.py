from graph_wiki_core.prompts.skill_planner import build_skill_planner_system


def test_skill_planner_system_is_nonempty_str():
    s = build_skill_planner_system()
    assert isinstance(s, str) and len(s) > 200


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
