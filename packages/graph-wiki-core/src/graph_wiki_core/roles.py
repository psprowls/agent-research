"""Role-keyed model resolution for graph-wiki.

make_llm(role) resolves a logical role name (e.g. "librarian", "scanner") to a
concrete chat model, layering a per-workspace override on top of the packaged
models.toml catalog. Model construction is delegated to model_adapter's generic
constructors -- this module owns the *role* concept; model_adapter owns the
*client*.

Resolution order for make_llm(role):
  1. Packaged graph_wiki_core/models.toml [roles.<role>], if present, as the
     base.
  2. Workspace manifest (<workspace>/.graph-wiki.yaml top-level roles.<role>)
     fields layered on top, per field -- a partial override (e.g. just
     max_tokens) fills in only the fields it sets and keeps the packaged
     values for the rest.
"""

from __future__ import annotations

import tomllib
from importlib import resources

from langchain_core.language_models import BaseChatModel
from model_adapter import make_bedrock_llm, make_gateway_llm


def _load_models_config() -> dict:
    # models.toml is bundled inside the graph_wiki_core package so it is
    # accessible under any install mode (editable, wheel, or zip).
    with resources.files("graph_wiki_core").joinpath("models.toml").open("rb") as f:
        return tomllib.load(f)


def _workspace_role_override(role: str) -> dict | None:
    """Return the workspace-defined role dict for `role`, or None.

    Reads the manifest's flattened top-level `roles:` mapping. Returns None on
    any failure (no workspace, role absent, ImportError in restricted test
    contexts).
    """
    try:
        from workspace_io import read_roles, resolve
    except ImportError:
        return None
    try:
        cfg = resolve()
    except RuntimeError:
        return None
    manifest_path = cfg.workspace / ".graph-wiki.yaml"
    return read_roles(manifest_path).get(role)


def make_llm(role: str, *, model_override: str | None = None) -> BaseChatModel:
    """Return a chat model configured for the given role.

    Resolution order: workspace manifest override merged, field by field, onto
    the packaged models.toml entry for the role -- the workspace can set any
    subset of {model_id, region, max_tokens, max_concurrency, backend} and the
    rest fall back to the packaged defaults. When the role has no packaged
    entry at all, the workspace override (if any) IS the definition. Backend
    is driven by the resolved role's ``backend`` key (default ``"bedrock"``;
    ``"vercel"`` selects the AI Gateway).

    Raises:
        KeyError: when `role` is absent from both sources, or resolves with no
            `model_id` (only reachable for a workspace-only role definition
            that omits it, since packaged roles always carry one).
        GatewayAccessDenied: for a vercel role when AI_GATEWAY_API_KEY is unset.
    """
    workspace_cfg = _workspace_role_override(role)
    packaged_cfg = _load_models_config()["roles"].get(role)

    if packaged_cfg is None and workspace_cfg is None:
        raise KeyError(role)
    if packaged_cfg is None:
        role_cfg = workspace_cfg
    elif workspace_cfg is None:
        role_cfg = packaged_cfg
    else:
        role_cfg = {**packaged_cfg, **workspace_cfg}

    if model_override is not None:
        model_id = model_override
    elif "model_id" in role_cfg:
        model_id = role_cfg["model_id"]
    else:
        raise KeyError(
            f"role {role!r} has no model_id: no packaged models.toml entry exists for it, and "
            "the workspace override does not set model_id either"
        )
    max_tokens = role_cfg.get("max_tokens")
    if role_cfg.get("backend", "bedrock") == "vercel":
        return make_gateway_llm(model_id, max_tokens=max_tokens)
    return make_bedrock_llm(model_id, region=role_cfg.get("region", "us-east-1"), max_tokens=max_tokens)


def load_role_config(role: str) -> dict:
    """Return the raw config dict for a role from the packaged models.toml.

    Packaged defaults only -- workspace overrides apply to make_llm() alone
    (eval-harness consumers depend on the packaged shape incl. sweep_candidates).

    Raises:
        KeyError: when `role` is absent from models.toml.
    """
    return _load_models_config()["roles"][role]  # KeyError if role absent
