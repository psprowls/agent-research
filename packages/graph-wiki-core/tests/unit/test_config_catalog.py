"""Catalog shape + accepted-duplication guard: catalog defaults must match the
behavioral constants where they are actually read (spec §4)."""

from pathlib import Path

from graph_wiki_core.config_catalog import CATALOG, entry

REPO_ROOT = Path(__file__).resolve().parents[4]
HOOKS_DIR = REPO_ROOT / "plugins" / "graph-wiki" / "hooks"


def test_all_env_only_entries_carry_env_var_and_description():
    for e in CATALOG:
        if e.kind == "env-only":
            assert e.env_var, f"{e.key} missing env_var"
        assert e.description, f"{e.key} missing description"


def test_manifest_keys_present():
    for key in (
        "topic",
        "plugin.backend_default",
        "plugin.backend_overrides.*",
        "state_gate.enabled",
        "state_gate.branches",
        "roles.*.model_id",
        "roles.*.backend",
        "workflow.commit_strategy",
        "workflow.model_routing.mechanical",
        "workflow.model_routing.standard",
        "workflow.model_routing.frontier",
    ):
        assert entry(key) is not None, key


def test_secret_flag_on_gateway_key():
    assert entry("AI_GATEWAY_API_KEY").secret is True
    assert entry("AI_GATEWAY_BASE_URL").secret is False


def test_lock_timeout_default_matches_graph_io(monkeypatch):
    from graph_io.update import _default_lock_timeout

    monkeypatch.delenv("GRAPH_WIKI_LOCK_TIMEOUT_MS", raising=False)
    assert entry("GRAPH_WIKI_LOCK_TIMEOUT_MS").default == _default_lock_timeout()


def test_hook_env_defaults_match_catalog():
    # bash defaults live in the shell scripts that read them; the catalog value
    # is documentation and must track them (spec §4 accepted duplication).
    sources = "".join(
        # errors="ignore" so a future binary file in hooks/ can't break the pin.
        p.read_text(encoding="utf-8", errors="ignore")
        for p in list(HOOKS_DIR.iterdir()) + list((HOOKS_DIR / "examples").iterdir())
        if p.is_file()
    )
    for var in (
        "GRAPH_WIKI_CONTEXT_LIMIT",
        "GRAPH_WIKI_DEFLECTION_THRESHOLD_PCT",
        "GRAPH_WIKI_USERGATE_TRACE_LOG",
        "GRAPH_WIKI_TRANSCRIPT_CAPTURE_TRACE_LOG",
    ):
        # Qualified ${VAR:-default} form so ":-50}" can't match some other var.
        assert f"${{{var}:-{entry(var).default}}}" in sources, var
