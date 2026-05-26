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


def subpkg_uri(ctx: RepoContext, pkg_name: str, dotted_path: str) -> str:
    return f"subpkg:{ctx.org}/{ctx.repo}/{pkg_name}/{dotted_path}"


def file_uri(ctx: RepoContext, rel_path: str) -> str:
    return f"file:{ctx.org}/{ctx.repo}/{rel_path}"


def entry_point_uri(ctx: RepoContext, pkg_name: str, ep_name: str) -> str:
    return f"entry_point:{ctx.org}/{ctx.repo}/{pkg_name}/{ep_name}"


def test_suite_uri(ctx: RepoContext, suite_name: str) -> str:
    return f"test_suite:{ctx.org}/{ctx.repo}/{suite_name}"


def domain_uri(name: str) -> str:
    return f"domain:{name}"


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
