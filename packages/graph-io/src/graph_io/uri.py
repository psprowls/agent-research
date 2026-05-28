"""URI composition surface locked in Phase 28 (CONTEXT.md D-06..D-08)."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class RepoContext:
    org: str
    repo: str


def repo_uri(ctx: RepoContext) -> str:
    return f"repo:{ctx.org}/{ctx.repo}"


def pkg_uri(ctx: RepoContext, name: str) -> str:
    return f"pkg:{ctx.org}/{ctx.repo}/{name}"


def app_uri(ctx: RepoContext, name: str) -> str:
    """Phase 50 D-07: app URI for scanner-classified application packages."""
    return f"app:{ctx.org}/{ctx.repo}/{name}"


def subpkg_uri(ctx: RepoContext, pkg_name: str, dotted_path: str) -> str:
    return f"subpkg:{ctx.org}/{ctx.repo}/{pkg_name}/{dotted_path}"


def file_uri(ctx: RepoContext, rel_path: str) -> str:
    return f"file:{ctx.org}/{ctx.repo}/{rel_path}"


def entry_point_uri(ctx: RepoContext, pkg_name: str, ep_name: str) -> str:
    return f"entry_point:{ctx.org}/{ctx.repo}/{pkg_name}/{ep_name}"


def test_suite_uri(ctx: RepoContext, suite_name: str) -> str:
    return f"test_suite:{ctx.org}/{ctx.repo}/{suite_name}"


def domain_uri(ctx: RepoContext, name: str) -> str:
    return f"domain:{ctx.org}/{ctx.repo}/{name}"


# v1.8 concept-level kinds (Phase 42 D-04): not repo-scoped, so no RepoContext.
def package_family_uri(name: str) -> str:
    return f"package_family:{name}"


def plugin_uri(name: str) -> str:
    return f"plugin:{name}"


def dependency_uri(ecosystem: str, name: str) -> str:
    return f"dependency:{ecosystem}/{name}"


def builtin_uri(language: str, module_name: str) -> str:
    return f"builtin:{language}/{module_name}"


_SSH_REMOTE_RE = re.compile(r"^git@[^:]+:([^/]+)/([^/]+?)(?:\.git)?$")
_HTTPS_REMOTE_RE = re.compile(r"^https?://[^/]+/([^/]+)/([^/]+?)(?:\.git)?/?$")


def parse_remote_url(url: str) -> tuple[str, str] | None:
    m = _SSH_REMOTE_RE.match(url)
    if m is not None:
        return m.group(1), m.group(2)
    m = _HTTPS_REMOTE_RE.match(url)
    if m is not None:
        return m.group(1), m.group(2)
    return None
