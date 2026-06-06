"""gw graph list --kind <kind> — dispatch to the per-kind list modules.

The per-kind ``q_list_*`` modules are kept as library helpers; this router
only selects which one's ``run(args)`` to call. ``list-entry-points`` is NOT
routed here — it has a required positional package argument and a different
``--kind`` axis, so it remains its own command.
"""

from __future__ import annotations

from typing import cast

from graph_wiki_cli.graph_cli import (
    q_list_apps,
    q_list_builtins,
    q_list_domains,
    q_list_packages,
    q_list_scripts,
    q_list_suites,
)
from graph_wiki_cli.graph_cli._args import AnyRunModule, ListArgs

_DISPATCH: dict[str, AnyRunModule] = {
    "apps": q_list_apps,
    "builtins": q_list_builtins,
    "packages": q_list_packages,
    "scripts": q_list_scripts,
    "suites": q_list_suites,
    "domains": q_list_domains,
}
LIST_KINDS = tuple(_DISPATCH)


def run(args: ListArgs) -> int:
    return _DISPATCH[cast(str, args.kind)].run(args)
