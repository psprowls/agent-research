"""gw graph describe <selector> [--kind] — dispatch to the per-kind describe modules.

The per-kind ``q_describe_*`` modules are library helpers; this router selects
which one's ``run(args)`` to call. With an explicit ``--kind`` it dispatches
straight to that describer (symbol describer for the code kinds). Without
``--kind`` it resolves the selector across all node kinds via
``queries.resolve_selector``: a unique match is described, multiple matches
produce a copy-paste disambiguation menu (stdout, exit 0), zero matches fall
back to the path describer.
"""

from __future__ import annotations

import sys
from typing import cast

from graph_wiki_core.commands import graph_query
from graph_wiki_core.commands.graph_query import NodeRecord, exit_codes
from graph_wiki_core.commands.graph_query import render as _render

from graph_wiki_cli.graph_cli import (
    q_describe_agent_plugin,
    q_describe_app,
    q_describe_builtin,
    q_describe_dependency,
    q_describe_domain,
    q_describe_entry_point,
    q_describe_package,
    q_describe_path,
    q_describe_repo,
    q_describe_suite,
    q_describe_symbol,
)
from graph_wiki_cli.graph_cli._args import AnyRunModule, MutableDescribeArgs

# CLI kind -> (module, name of the args attribute that module reads as its selector)
_DISPATCH: dict[str, tuple[AnyRunModule, str | None]] = {
    "package": (q_describe_package, "name"),
    "app": (q_describe_app, "name"),
    "domain": (q_describe_domain, "name"),
    "suite": (q_describe_suite, "name"),
    "dependency": (q_describe_dependency, "name"),
    "agent-plugin": (q_describe_agent_plugin, "name"),
    "entry-point": (q_describe_entry_point, "name"),
    "builtin": (q_describe_builtin, "uri"),
    "path": (q_describe_path, "path"),
    "repo": (q_describe_repo, None),
}
DESCRIBE_KINDS = tuple(_DISPATCH)

# Code-symbol CLI kinds dispatch to the symbol describer (DB kind == CLI value).
CODE_KINDS = q_describe_symbol.CODE_KINDS
DESCRIBE_KINDS = (*DESCRIBE_KINDS, *CODE_KINDS)

# DB node kind -> the dispatch key in _DISPATCH used to describe it.
# Keep in sync with queries._CLI_KIND (the inverse map used to build menu
# commands): a new entity kind needs adding to both.
_DB_KIND_TO_DISPATCH = {
    "package": "package",
    "app": "app",
    "domain": "domain",
    "dependency": "dependency",
    "test_suite": "suite",
    "agent_plugin": "agent-plugin",
    "entry_point": "entry-point",
    "file": "path",
    "repository": "repo",
}

# Tailored stderr for bare-name describe of structural / placeholder kinds that
# have no spine describer (builtin is reachable only via its `builtin:` URI).
_NON_DESCRIBABLE_MESSAGES = {
    "builtin": "error: describe builtins by URI: gw graph describe builtin:<lang>/<module>",
    "subpackage": "error: structural node (sub-package); describe its package or a file instead",
    "unresolved_symbol": "error: placeholder for an unresolved reference; not a real node",
}


def _describe_one(match: NodeRecord, args: MutableDescribeArgs) -> int:
    """Dispatch a single resolved match to the right describer."""
    if match.kind in CODE_KINDS:
        args.kind = match.kind
        # Pin the exact resolved node so a path:line selector (or any resolved
        # match) describes THIS node rather than re-resolving by the raw selector.
        args.selector = match.name
        if match.path is not None:
            args.path = match.path
        args.line = match.line
        return q_describe_symbol.run(args)
    dispatch_key = _DB_KIND_TO_DISPATCH.get(match.kind)
    if dispatch_key is None:
        # Kinds absent from _DB_KIND_TO_DISPATCH (builtin, subpackage,
        # unresolved_symbol) intentionally land here: builtins are reached via the
        # `builtin:` prefix, the others are structural/placeholder nodes. Each gets
        # a tailored hint; anything else falls back to a generic message.
        msg = _NON_DESCRIBABLE_MESSAGES.get(match.kind, f"error: cannot describe {match.kind}: {args.selector}")
        print(msg, file=sys.stderr)
        return exit_codes.GENERIC
    if match.kind == "dependency" and args.ecosystem is None:
        args.ecosystem = match.attrs.get("ecosystem")
    module, selector_attr = _DISPATCH[dispatch_key]
    if selector_attr is not None:
        setattr(args, selector_attr, args.selector)
    return cast(AnyRunModule, module).run(args)


def run(args: MutableDescribeArgs) -> int:
    kind = args.kind
    selector = args.selector

    # Fast paths: explicit code kind, explicit entity kind, no-selector repo,
    # builtin: prefix.
    if kind in CODE_KINDS:
        return q_describe_symbol.run(args)
    if kind is not None:
        module, selector_attr = _DISPATCH[kind]
        if selector_attr is not None:
            setattr(args, selector_attr, args.selector)
        return cast(AnyRunModule, module).run(args)
    if selector is None:
        return _DISPATCH["repo"][0].run(args)
    if selector.startswith("builtin:"):
        args.uri = selector
        return _DISPATCH["builtin"][0].run(args)

    # Inference across all kinds via resolve_selector.
    reader, code, err = graph_query.connect_or_error(args.workspace)
    if reader is None:
        print(err, file=sys.stderr)
        return code
    try:
        matches = reader.resolve_selector(selector=selector, in_package=args.in_package)
        if not matches:
            # Historical fallback: a bare selector matching no node name may still
            # be a file path — hand it to the path describer, which renders the
            # file or reports "path not found in graph" (GENERIC) for a miss.
            args.path = selector
            return _DISPATCH["path"][0].run(args)
        if len(matches) == 1:
            return _describe_one(matches[0], args)
        capped = matches[:50]
        menu = reader.build_menu(capped)
    finally:
        reader.close()

    print(_render.format_matches(menu, fmt=args.fmt))
    if len(matches) > 50:
        print(f"... showing 50 of {len(matches)} (truncated)", file=sys.stderr)
    return exit_codes.SUCCESS
