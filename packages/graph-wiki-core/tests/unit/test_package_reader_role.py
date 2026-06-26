from __future__ import annotations


def test_package_reader_role_in_models_toml() -> None:
    from graph_wiki_core.roles import load_role_config

    cfg = load_role_config("package_reader")

    assert cfg["model_id"] == "moonshotai.kimi-k2.5"
    assert cfg["region"] == "us-east-1"
    assert cfg["max_tokens"] == 4096
    assert cfg["max_concurrency"] == 3
    assert "openai.gpt-oss-120b-1:0" in cfg["sweep_candidates"]
    assert "moonshotai.kimi-k2.5" in cfg["sweep_candidates"]
