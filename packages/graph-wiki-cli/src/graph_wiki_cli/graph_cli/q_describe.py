"""gw graph describe <selector> [--kind] — dispatch to the per-kind describe modules.

The per-kind ``q_describe_*`` modules are kept as library helpers; this router
selects which one's ``run(args)`` to call, copies the single ``selector`` onto
the attribute that module expects (``name`` / ``uri`` / ``path``), and — when
``--kind`` is omitted — infers the kind (see ``_resolve_kind``).
"""

from __future__ import annotations

import sys
from typing import cast

from graph_io import exit_codes, store
from workspace_io.paths import graph_dir

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

# Bare-name CLI kinds eligible for inference -> their DB node kind.
_INFER_DB_KIND = {
    "package": "package",
    "app": "app",
    "domain": "domain",
    "dependency": "dependency",
    "suite": "test_suite",
    "agent-plugin": "agent_plugin",
    "entry-point": "entry_point",
}
_DB_KIND_TO_CLI = {db: cli for cli, db in _INFER_DB_KIND.items()}


def _resolve_kind(args: MutableDescribeArgs) -> str | int:
    """Infer the describe kind from ``args.selector``.

    Returns a CLI kind string, or an int exit code on DB/ambiguity error
    (the error message is already printed to stderr).
    """
    selector = args.selector
    if selector is None:
        return "repo"
    if selector.startswith("builtin:"):
        return "builtin"
    db = graph_dir(args.workspace) / "code.db"
    try:
        conn = store.read_only_connect(db)
    except store.GraphNotInitializedError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exit_codes.NOT_INITIALIZED
    except store.SchemaMismatchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exit_codes.SCHEMA_MISMATCH
    try:
        rows = conn.execute(
            "SELECT DISTINCT kind FROM nodes WHERE name = ? AND kind IN "
            "('package','app','domain','dependency','test_suite','agent_plugin','entry_point')",
            (selector,),
        ).fetchall()
        cli_kinds = sorted({_DB_KIND_TO_CLI[r[0]] for r in rows})
        if len(cli_kinds) == 1 and cli_kinds[0] == "dependency" and getattr(args, "ecosystem", None) is None:
            eco_rows = conn.execute(
                "SELECT DISTINCT json_extract(attrs_json, '$.ecosystem') FROM nodes "
                "WHERE kind='dependency' AND name = ?",
                (selector,),
            ).fetchall()
            ecosystems = sorted(r[0] for r in eco_rows if r[0] is not None)
            if len(ecosystems) > 1:
                print(
                    f"error: ambiguous dependency {selector!r} across ecosystems: "
                    f"{', '.join(ecosystems)}; pass --ecosystem",
                    file=sys.stderr,
                )
                return exit_codes.AMBIGUOUS
            if ecosystems:
                args.ecosystem = ecosystems[0]
    finally:
        conn.close()
    if not cli_kinds:
        # Not a known entity name — fall back to a path lookup; describe_path
        # reports "path not found in graph" if it is not one.
        return "path"
    if len(cli_kinds) > 1:
        print(
            f"error: ambiguous selector {selector!r} matches kinds: {', '.join(cli_kinds)}; disambiguate with --kind",
            file=sys.stderr,
        )
        return exit_codes.AMBIGUOUS
    return cli_kinds[0]


def run(args: MutableDescribeArgs) -> int:
    kind = args.kind
    if kind in CODE_KINDS:
        # Explicit code kind: describe_symbol owns single-node resolution.
        return q_describe_symbol.run(args)
    if kind is None:
        kind = _resolve_kind(args)
        if isinstance(kind, int):
            return kind
    module, selector_attr = _DISPATCH[kind]
    if selector_attr is not None:
        setattr(args, selector_attr, args.selector)
    module = cast(AnyRunModule, module)
    return module.run(args)
