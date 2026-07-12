"""workspace-io: graph-wiki workspace bootstrap, manifest IO, and config resolution."""

from workspace_io.config import GraphWikiConfig, discover_members, resolve
from workspace_io.init import init
from workspace_io.manifest import read_guidance, read_roles, read_state_gate
from workspace_io.registry import ConfigEntry
from workspace_io.versions import PendingUpdate, pending_updates, warn_if_stale

__all__ = [
    "ConfigEntry",
    "GraphWikiConfig",
    "PendingUpdate",
    "discover_members",
    "init",
    "pending_updates",
    "read_guidance",
    "read_roles",
    "read_state_gate",
    "resolve",
    "warn_if_stale",
]
