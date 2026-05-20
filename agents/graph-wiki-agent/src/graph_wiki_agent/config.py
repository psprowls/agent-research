from __future__ import annotations

"""WikiConfig — shared configuration module for graph-wiki-agent.

Provides:
- WikiConfig dataclass with fields for vault_path and state_gate_enabled
- load_config(path) — reads a TOML file and returns a WikiConfig
  (unknown keys silently dropped for forward-compatibility)
- get_config() — returns the module-level active config singleton
- _active_config — module-level mutable singleton; available for
  programmatic configuration (no longer set by any CLI / MCP entry
  point — the `--config` / CODE_WIKI_CONFIG pathway was removed in
  Phase 20 / WMC-03; per-workspace config now lives in
  `<workspace>/.graph-wiki.yaml`).
"""

import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass
class WikiConfig:
    """Runtime configuration for graph-wiki-agent.

    Fields:
        vault_path: Default vault path (overrides GRAPH_WIKI_WORKSPACE env var).
        state_gate_enabled: Whether git state-gate checks are enforced (default: True).
    """

    vault_path: str | None = None
    state_gate_enabled: bool = True


# Module-level mutable singleton — mutated by CLI callback and MCP startup.
_active_config: WikiConfig = WikiConfig()


def load_config(path: Path) -> WikiConfig:
    """Read a TOML config file and return a WikiConfig instance.

    Unknown TOML keys are silently dropped so future TOML additions do not
    break older versions of the agent.

    Args:
        path: Path to the TOML configuration file.

    Returns:
        WikiConfig populated from the TOML file.

    Raises:
        FileNotFoundError: If path does not exist.
        tomllib.TOMLDecodeError: If the file is not valid TOML.
    """
    with path.open("rb") as f:
        data = tomllib.load(f)
    # Drop unknown keys — forward-compatibility guard.
    known = {k: v for k, v in data.items() if k in WikiConfig.__dataclass_fields__}
    return WikiConfig(**known)


def get_config() -> WikiConfig:
    """Return the currently active WikiConfig singleton."""
    return _active_config
