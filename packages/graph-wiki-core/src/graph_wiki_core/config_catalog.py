"""Static catalog of every graph-wiki config knob (manifest-kind + env-only).

Peer of roles.py. The generic mechanism lives in workspace_io.registry; this
module only declares entries and hands them to commands/config.py. `gw config
list` renders this catalog — it is the canonical documentation surface for
every knob, including env-only ones that are never stored.

Env-only defaults here are documentation: behavioral defaults stay where they
are read (graph_io/update.py, the bash hooks under plugins/graph-wiki/hooks/).
test_config_catalog.py pins the two copies together (spec §4 accepted
duplication — graph-io cannot import from core, and the hooks are bash).
Author obligation: any new env-only entry whose default is read elsewhere must
get a matching pin in test_config_catalog.py.

Internal sentinels (GRAPH_WIKI_BOOTSTRAP_REEXEC, GRAPH_WIKI_SHIM_REEXEC — uv
re-exec loop guards set by the tooling itself) are not config knobs and are
deliberately absent.

Deferred (recorded, not built): a contribution protocol letting each package
register its own entries into workspace-io. For now this is one static module.
"""

from __future__ import annotations

from workspace_io.registry import ConfigEntry


def _env(key: str, default: object, description: str, *, type: str = "str", secret: bool = False) -> ConfigEntry:
    return ConfigEntry(
        key=key,
        type=type,
        default=default,
        description=description,
        kind="env-only",
        env_var=key,
        secret=secret,
    )


_MANIFEST_ENTRIES: tuple[ConfigEntry, ...] = (
    ConfigEntry("topic", "str", None, "Wiki display name recorded at bootstrap."),
    ConfigEntry(
        "plugin.backend_default",
        "str",
        "claude",
        "Default execution backend for plugin shims.",
        allowed=("claude", "bedrock"),
    ),
    ConfigEntry(
        "plugin.backend_overrides.*",
        "str",
        None,
        "Per-command backend override (e.g. plugin.backend_overrides.scan).",
        allowed=("claude", "bedrock"),
    ),
    ConfigEntry(
        "state_gate.enabled",
        "bool",
        True,
        "Require a clean gated branch before mutating commands run.",
    ),
    ConfigEntry(
        "state_gate.branches",
        "list[str]",
        ["main"],
        "Branches the state gate protects (comma-separated on set).",
    ),
    ConfigEntry(
        "guidance.enabled",
        "bool",
        False,
        "Attach phase-relevant guidance pages to gw next output (opt-in, off by default).",
    ),
    ConfigEntry(
        "roles.*.model_id",
        "str",
        None,
        "Model id override for a role (packaged defaults: models.toml).",
    ),
    ConfigEntry(
        "roles.*.region",
        "str",
        "us-east-1",
        "AWS region override for a role.",
    ),
    ConfigEntry(
        "roles.*.max_tokens",
        "int",
        None,
        "Max output tokens override for a role.",
    ),
    ConfigEntry(
        "roles.*.max_concurrency",
        "int",
        None,
        "SubagentPool concurrency override for a role.",
    ),
    ConfigEntry(
        "roles.*.backend",
        "str",
        "bedrock",
        "Model backend for a role (vercel = AI Gateway).",
        allowed=("bedrock", "vercel"),
    ),
    ConfigEntry(
        "workflow.commit_strategy",
        "str",
        "per-task",
        "Plan-execution commit cadence: per-task commits or one commit at plan end.",
        allowed=("per-task", "at-end"),
    ),
    ConfigEntry(
        "workflow.model_routing.mechanical",
        "str",
        None,
        "Model alias for mechanical-tier plan tasks ('inherit' = session model). Absent block = routing off.",
    ),
    ConfigEntry(
        "workflow.model_routing.standard",
        "str",
        None,
        "Model alias for standard-tier plan tasks and reviewers ('inherit' = session model).",
    ),
    ConfigEntry(
        "workflow.model_routing.frontier",
        "str",
        None,
        "Model alias for frontier-tier plan tasks ('inherit' = session model).",
    ),
)

_ENV_ONLY_ENTRIES: tuple[ConfigEntry, ...] = (
    _env(
        "GRAPH_WIKI_WORKSPACE",
        None,
        "Workspace directory pointer — the only external-workspace pointer. Normally supplied "
        "by the repo's .claude/settings.local.json env block; bare terminals use --workspace or "
        "a shell export.",
    ),
    # Hook kill switches (all default on; set to 0 to disable). Names verified
    # against plugins/graph-wiki/hooks/ and hooks/examples/ on disk. Defaults
    # are the string "1" deliberately: they mirror the bash `${VAR:-1}` literal
    # a user would export; Python never reads these.
    _env("GRAPH_WIKI_AGENT_RETURN_GUARD", "1", "Kill switch for post-agent-return-validate hook."),
    _env("GRAPH_WIKI_DISPATCH_GUARD", "1", "Kill switch for pre-agent-task-dispatch-validate hook."),
    _env("GRAPH_WIKI_BLOCKEDBY_GUARD", "1", "Kill switch for pre-task-blockedby-enforce hook."),
    _env("GRAPH_WIKI_DEFLECTION_GUARD", "1", "Kill switch for stop-deflection-guard hook."),
    _env("GRAPH_WIKI_USERGATE_GUARD", "1", "Kill switch for post-task-complete-revalidate hook."),
    _env("GRAPH_WIKI_USERGATE_STOP_GUARD", "1", "Kill switch for stop-revalidate-user-gates hook."),
    _env("GRAPH_WIKI_TRANSCRIPT_CAPTURE_GUARD", "1", "Kill switch for session-end-transcript-capture hook."),
    _env(
        "GRAPH_WIKI_ROUTING_GUARD",
        "1",
        "Kill switch for the model-routing gates (pre-agent-model-routing, "
        "pre-taskcreate-model-tier, pre-askuser-handoff-guard).",
    ),
    # Tuning vars.
    _env(
        "GRAPH_WIKI_USERGATE_TRACE_LOG",
        "/tmp/claude-hooks/user-gate-trace.log",
        "Trace log path shared by the user-gate/dispatch/routing hook family.",
    ),
    _env(
        "GRAPH_WIKI_TRANSCRIPT_CAPTURE_TRACE_LOG",
        "/tmp/claude-hooks/transcript-capture-trace.log",
        "Trace log path for session-end transcript capture.",
    ),
    _env(
        "GRAPH_WIKI_CONTEXT_LIMIT",
        200000,
        "Context-size denominator (total context window in tokens) used by the deflection guard.",
        type="int",
    ),
    _env(
        "GRAPH_WIKI_DEFLECTION_THRESHOLD_PCT",
        50,
        "Context-usage percentage below which the deflection guard's deflection-phrase check fires.",
        type="int",
    ),
    _env(
        "GRAPH_WIKI_USERGATE_KEYWORDS",
        None,
        "Extra comma-separated keywords the post-task-complete-revalidate hook treats as gate language.",
    ),
    _env(
        "GRAPH_WIKI_LOCK_TIMEOUT_MS",
        30_000,
        "SQLite busy-timeout for graph-io writes (behavioral default lives in graph_io/update.py "
        "_default_lock_timeout).",
        type="int",
    ),
    # Eval gates.
    _env("GRAPH_WIKI_RUN_EVAL", None, "Set to 1 to run eval-marked tests (deepeval sweep suite)."),
    _env("GRAPH_WIKI_RUN_JUDGES", None, "Set to 1 to additionally run LLM-judge panel scoring in eval sweeps."),
    _env(
        "GRAPH_WIKI_RUN_INTEGRATION",
        None,
        "Set to 1 to run integration-marked tests (real Bedrock calls or subprocess launches).",
    ),
    # Gateway credentials.
    _env(
        "AI_GATEWAY_API_KEY",
        None,
        "Vercel AI Gateway credential (secret — never stored, never echoed).",
        secret=True,
    ),
    _env("AI_GATEWAY_BASE_URL", None, "Vercel AI Gateway base URL override."),
)

CATALOG: tuple[ConfigEntry, ...] = _MANIFEST_ENTRIES + _ENV_ONLY_ENTRIES


def entry(key: str) -> ConfigEntry | None:
    """Exact-key lookup (pattern keys are matched literally here; use
    workspace_io.registry.find_entry for wildcard resolution)."""
    for e in CATALOG:
        if e.key == key:
            return e
    return None
