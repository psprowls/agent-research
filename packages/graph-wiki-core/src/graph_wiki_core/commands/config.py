"""gw config — the sole programmatic writer for graph-wiki configuration.

Logic layer for the config verbs (get/set/unset/list/sync); the Typer surface
in graph-wiki-cli is a thin shell over these functions. Hooks wiring and the
interactive init flow live in this module too (added by later tasks).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from workspace_io.projection import write_projection
from workspace_io.registry import Resolved, _get_path, _raw_manifest, resolve_key, set_key, unset_key

from graph_wiki_core.config_catalog import CATALOG

_MASK = "••••"


def _resolve_workspace(workspace_path: Path | None) -> Path:
    if workspace_path is not None:
        return Path(workspace_path).resolve()
    from workspace_io import resolve

    return resolve().workspace


@dataclass
class ConfigValue:
    """A single resolved config key, ready for display or programmatic use."""

    key: str
    value: object
    origin: str  # "env" | "manifest" | "default"
    default: object
    description: str
    kind: str
    env_var: str | None
    secret: bool
    shadows: object | None = None  # explicit manifest value hidden behind an env override


def _to_config_value(workspace: Path, resolved: Resolved) -> ConfigValue:
    entry = resolved.entry
    value = _MASK if (entry.secret and resolved.value not in (None, "")) else resolved.value
    shadows = None
    if resolved.origin == "env" and entry.kind == "manifest":
        explicit = _get_path(_raw_manifest(workspace), resolved.key)
        if explicit is not None:
            shadows = explicit
    return ConfigValue(
        key=resolved.key,
        value=value,
        origin=resolved.origin,
        default=_MASK if (entry.secret and entry.default not in (None, "")) else entry.default,
        description=entry.description,
        kind=entry.kind,
        env_var=entry.env_var,
        secret=entry.secret,
        shadows=shadows,
    )


async def run_config_get(key: str, workspace_path: Path | None = None) -> ConfigValue:
    """Resolve a single config key through the env > manifest > default precedence."""
    workspace = _resolve_workspace(workspace_path)
    return _to_config_value(workspace, resolve_key(CATALOG, key, workspace=workspace))


async def run_config_set(key: str, value: str, workspace_path: Path | None = None) -> ConfigValue:
    """Write a key into the manifest (validated + rollback-safe) and re-resolve it."""
    workspace = _resolve_workspace(workspace_path)
    return _to_config_value(workspace, set_key(CATALOG, key, value, workspace=workspace))


async def run_config_unset(key: str, workspace_path: Path | None = None) -> ConfigValue:
    """Remove a key's explicit manifest value, returning its now-resolved (env/default) value."""
    workspace = _resolve_workspace(workspace_path)
    unset_key(CATALOG, key, workspace=workspace)
    return _to_config_value(workspace, resolve_key(CATALOG, key, workspace=workspace))


def _expand_wildcards(workspace: Path) -> list[str]:
    """Concrete keys present in the manifest that match a wildcard catalog entry.

    Handles both wildcard shapes: `roles.*.<field>` (head="roles", field="<field>")
    and `plugin.backend_overrides.*` (head="plugin.backend_overrides", field="").
    """
    raw = _raw_manifest(workspace)
    concrete: list[str] = []
    for entry in CATALOG:
        if "*" not in entry.key:
            continue
        head, _, tail = entry.key.partition(".*")
        block = _get_path(raw, head)
        if not isinstance(block, dict):
            continue
        field = tail.lstrip(".")
        for name, fields in block.items():
            if field:
                if isinstance(fields, dict) and field in fields:
                    concrete.append(f"{head}.{name}.{field}")
            else:
                concrete.append(f"{head}.{name}")
    return concrete


async def run_config_list(workspace_path: Path | None = None) -> list[ConfigValue]:
    """One row per catalog entry, with wildcard entries expanded to concrete keys."""
    workspace = _resolve_workspace(workspace_path)
    keys = [entry.key for entry in CATALOG if "*" not in entry.key] + _expand_wildcards(workspace)
    return [_to_config_value(workspace, resolve_key(CATALOG, key, workspace=workspace)) for key in keys]


async def run_config_sync(workspace_path: Path | None = None) -> Path:
    """Regenerate `<workspace>/.graph-wiki/config.json` from the manifest and return its path."""
    return write_projection(_resolve_workspace(workspace_path))


# --- Host wiring: .claude/settings.local.json ------------------------------
# Host config (hook registrations, permissions.deny, the env block), not
# graph-wiki config — written by deterministic JSON merge, never hand-diffed.


@dataclass(frozen=True)
class HookWiring:
    array: str  # settings hooks key: "PostToolUse" | "Stop" | "SessionEnd"
    matcher: str
    script: str  # filename under plugins/graph-wiki/hooks/examples/

    @staticmethod
    def for_feature(feature: str) -> tuple["HookWiring", ...]:
        if feature == "gates":
            return (
                HookWiring("PostToolUse", "TaskUpdate", "post-task-complete-revalidate.sh"),
                HookWiring("Stop", "", "stop-revalidate-user-gates.sh"),
            )
        if feature == "transcript":
            return (HookWiring("SessionEnd", "", "session-end-transcript-capture.sh"),)
        raise ValueError(f"unknown hooks feature {feature!r} (valid: gates, transcript)")


@dataclass
class HooksResult:
    settings_path: Path
    changed: bool
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


def _default_scripts_dir() -> Path:
    # gw runs from the agent-research checkout (uv workspace): walk up from
    # this module to the repo root and use the plugin's examples dir.
    for candidate in Path(__file__).resolve().parents:
        examples = candidate / "plugins" / "graph-wiki" / "hooks" / "examples"
        if examples.is_dir():
            return examples
    raise RuntimeError(
        "could not locate plugins/graph-wiki/hooks/examples/ — "
        "is graph-wiki-core running outside the agent-research checkout?"
    )


def _settings_path(repo_root: Path) -> Path:
    return Path(repo_root) / ".claude" / "settings.local.json"


def _read_settings(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8")) or {}


def _write_settings(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    # Confirm the write: re-read and re-parse; raises on corruption.
    json.loads(path.read_text(encoding="utf-8"))


def _resolve_repo_root(repo_root: Path | None) -> Path:
    if repo_root is not None:
        return Path(repo_root).resolve()
    from workspace_io import resolve

    return resolve().repo_root


async def run_config_hooks(
    action: str,
    feature: str,
    *,
    repo_root: Path | None = None,
    scripts_dir: Path | None = None,
) -> HooksResult:
    """Merge (enable) or remove (disable) a hook feature's registrations in settings.local.json.

    Dedup is by script filename inside the `command` string, so enabling twice
    is a no-op and disable removes exactly what enable added. `gates` also
    manages `permissions.deny: ["EnterPlanMode"]`. Every write is re-read and
    re-parsed to confirm the entries landed; a parse failure raises.
    """
    if action not in ("enable", "disable"):
        raise ValueError(f"unknown hooks action {action!r} (valid: enable, disable)")
    repo = _resolve_repo_root(repo_root)
    scripts = Path(scripts_dir) if scripts_dir is not None else _default_scripts_dir()
    target = _settings_path(repo)
    data = _read_settings(target)
    result = HooksResult(settings_path=target, changed=False)
    hooks_block = data.setdefault("hooks", {})

    for wiring in HookWiring.for_feature(feature):
        arr = hooks_block.setdefault(wiring.array, [])
        present = any(wiring.script in h.get("command", "") for e in arr for h in e.get("hooks", []))
        if action == "enable":
            if present:
                result.skipped.append(wiring.script)
                continue
            script_path = scripts / wiring.script
            if not script_path.is_file():
                raise RuntimeError(f"hook script missing: {script_path}")
            arr.append(
                {
                    "matcher": wiring.matcher,
                    "hooks": [{"type": "command", "command": f"bash {script_path}"}],
                }
            )
            result.added.append(wiring.script)
            result.changed = True
        else:
            kept = []
            for e in arr:
                original = e.get("hooks", [])
                e_hooks = [h for h in original if wiring.script not in h.get("command", "")]
                if len(e_hooks) < len(original):
                    result.removed.append(wiring.script)
                    result.changed = True
                    if e_hooks:  # entry mixed target + unrelated hooks: keep the trimmed entry
                        kept.append({**e, "hooks": e_hooks})
                else:
                    kept.append(e)
            hooks_block[wiring.array] = kept
            if not hooks_block[wiring.array]:
                del hooks_block[wiring.array]

    if feature == "gates":
        deny = data.setdefault("permissions", {}).setdefault("deny", [])
        if action == "enable" and "EnterPlanMode" not in deny:
            deny.append("EnterPlanMode")
            result.changed = True
        if action == "disable" and "EnterPlanMode" in deny:
            deny.remove("EnterPlanMode")
            result.changed = True
        if not data["permissions"]["deny"]:
            del data["permissions"]["deny"]
        if not data["permissions"]:
            del data["permissions"]
    if not data.get("hooks"):
        data.pop("hooks", None)

    if result.changed:
        _write_settings(target, data)
    return result


def write_workspace_env_block(repo_root: Path, workspace: Path) -> Path:
    """Merge `{"env": {"GRAPH_WIKI_WORKSPACE": <abs workspace>}}` into settings.local.json."""
    target = _settings_path(Path(repo_root))
    data = _read_settings(target)
    data.setdefault("env", {})["GRAPH_WIKI_WORKSPACE"] = str(Path(workspace).resolve())
    _write_settings(target, data)
    return target


# --- gw config init ---------------------------------------------------------

_GUIDED_TIERS = {"mechanical": "haiku", "standard": "sonnet", "frontier": "inherit"}
_ROUTING_KEYS = tuple(f"workflow.model_routing.{t}" for t in ("mechanical", "standard", "frontier"))


@dataclass
class InitAnswers:
    """None = skip the feature entirely (unanswered)."""

    model_routing: str | None = None  # "guided" | "fixed:<model>" | "off"
    commit_strategy: str | None = None  # "per-task" | "at-end"
    gates: bool | None = None
    transcript: bool | None = None
    write_env: bool | None = None


@dataclass
class InitResult:
    actions: list[str] = field(default_factory=list)


async def run_config_init(
    answers: InitAnswers,
    workspace_path: Path | None = None,
    *,
    repo_root: Path | None = None,
    scripts_dir: Path | None = None,
) -> InitResult:
    workspace = _resolve_workspace(workspace_path)
    result = InitResult()

    if answers.model_routing is not None:
        if answers.model_routing == "guided":
            for tier, model in _GUIDED_TIERS.items():
                await run_config_set(f"workflow.model_routing.{tier}", model, workspace)
            result.actions.append(
                "gw config set workflow.model_routing.{mechanical=haiku,standard=sonnet,frontier=inherit}"
            )
        elif answers.model_routing.startswith("fixed:"):
            model = answers.model_routing.split(":", 1)[1]
            for key in _ROUTING_KEYS:
                await run_config_set(key, model, workspace)
            result.actions.append(f"gw config set workflow.model_routing.* {model}")
        elif answers.model_routing == "off":
            for key in _ROUTING_KEYS:
                await run_config_unset(key, workspace)
            result.actions.append("gw config unset workflow.model_routing.*")
        else:
            raise ValueError(f"invalid model_routing answer {answers.model_routing!r}")

    if answers.commit_strategy is not None:
        if answers.commit_strategy == "at-end":
            await run_config_set("workflow.commit_strategy", "at-end", workspace)
            result.actions.append("gw config set workflow.commit_strategy at-end")
        elif answers.commit_strategy == "per-task":
            await run_config_unset("workflow.commit_strategy", workspace)
            result.actions.append("gw config unset workflow.commit_strategy (per-task default)")
        else:
            raise ValueError(f"invalid commit_strategy answer {answers.commit_strategy!r}")

    for feature, answer in (("gates", answers.gates), ("transcript", answers.transcript)):
        if answer is None:
            continue
        action = "enable" if answer else "disable"
        hr = await run_config_hooks(action, feature, repo_root=repo_root, scripts_dir=scripts_dir)
        result.actions.append(f"gw config hooks {action} {feature} -> {hr.settings_path}")

    if answers.write_env:
        repo = _resolve_repo_root(repo_root)
        target = write_workspace_env_block(repo, workspace)
        result.actions.append(f"wrote GRAPH_WIKI_WORKSPACE env block -> {target}")

    return result
