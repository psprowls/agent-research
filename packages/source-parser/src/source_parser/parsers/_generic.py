"""Config-driven generic walker that turns a tree-sitter parse tree into a SourceNode tree."""

from __future__ import annotations

from pathlib import Path

import tree_sitter

from source_parser.grammars import get_language
from source_parser.parsers._config import LanguageConfig
from source_parser.tree import Reference, SourceNode, Span


def _span(node: tree_sitter.Node) -> Span:
    sp = node.start_point
    ep = node.end_point
    return Span(
        start_byte=node.start_byte,
        end_byte=node.end_byte,
        start_line=sp[0] + 1,
        end_line=ep[0] + 1,
        start_col=sp[1],
        end_col=ep[1],
    )


def _text(node: tree_sitter.Node, source: bytes) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _resolve_name(node: tree_sitter.Node, source: bytes, config: LanguageConfig) -> str | None:
    n = node.child_by_field_name(config.name_field)
    if n is not None:
        return _text(n, source)
    for child in node.children:
        if child.type in config.name_fallback_child_types:
            return _text(child, source)
    return None


def _resolve_body(node: tree_sitter.Node, config: LanguageConfig) -> tree_sitter.Node | None:
    b = node.child_by_field_name(config.body_field)
    if b is not None:
        return b
    for child in node.children:
        if child.type in config.body_fallback_child_types:
            return child
    return None


def _collect_parse_errors(root: tree_sitter.Node) -> list[dict]:
    errors: list[dict] = []

    def visit(node: tree_sitter.Node) -> None:
        if node.is_error or node.type == "ERROR":
            errors.append(
                {
                    "start_byte": node.start_byte,
                    "end_byte": node.end_byte,
                    "start_line": node.start_point[0] + 1,
                    "end_line": node.end_point[0] + 1,
                }
            )
        for child in node.children:
            visit(child)

    visit(root)
    return errors


def _extract_call_target(call_node: tree_sitter.Node, source: bytes, config: LanguageConfig) -> tuple[str, dict]:
    """Return (target_name, attrs) for a call expression."""
    fn = call_node.child_by_field_name(config.call_function_field)
    if fn is None:
        return ("<unknown>", {})
    if fn.type in config.call_member_node_types:
        prop = fn.child_by_field_name(config.call_member_field)
        if prop is not None:
            return (_text(prop, source), {"is_member": True})
        return (_text(fn, source), {"is_member": True})
    return (_text(fn, source), {"is_member": False})


def _extract_calls(body: tree_sitter.Node, source: bytes, config: LanguageConfig) -> list[Reference]:
    calls: list[Reference] = []

    def visit(node: tree_sitter.Node, *, inside_nested_fn: bool) -> None:
        if not inside_nested_fn and node.type in config.call_types:
            name, attrs = _extract_call_target(node, source, config)
            calls.append(
                Reference(
                    kind="call",
                    target_name=name,
                    target_module=None,
                    site=_span(node),
                    attrs=attrs,
                )
            )
        # Stop descending into nested function bodies — their calls belong to them.
        descend_marks_nested = node.type in config.function_boundary_types
        for child in node.children:
            visit(
                child,
                inside_nested_fn=inside_nested_fn or descend_marks_nested and child is not node,
            )
        # The above check is overly conservative; walk the body of nested functions
        # via their own SourceNode instead. Practical effect: top-level walk skips
        # nested function bodies' calls.

    for child in body.children:
        visit(child, inside_nested_fn=False)
    return calls


def _build_function_node(
    node: tree_sitter.Node,
    source: bytes,
    path: Path,
    language: str,
    package: str | None,
    config: LanguageConfig,
    kind: str,
) -> SourceNode:
    name = _resolve_name(node, source, config)
    body = _resolve_body(node, config)
    fn = SourceNode(
        kind=kind,
        name=name,
        span=_span(node),
        path=path,
        language=language,
        package=package,
    )
    if kind == "method" and name in ("constructor",):
        fn.attrs["is_constructor"] = True
    if body is not None:
        fn.refs.extend(_extract_calls(body, source, config))
        # Nested classes/functions inside the body become children.
        fn.children.extend(_walk_container(body, source, path, language, package, config))
    return fn


def _build_class_node(
    node: tree_sitter.Node,
    source: bytes,
    path: Path,
    language: str,
    package: str | None,
    config: LanguageConfig,
) -> SourceNode:
    name = _resolve_name(node, source, config)
    body = _resolve_body(node, config)
    cls = SourceNode(
        kind="class",
        name=name,
        span=_span(node),
        path=path,
        language=language,
        package=package,
    )
    if body is not None:
        for child in body.children:
            if child.type in config.method_types:
                cls.children.append(
                    _build_function_node(
                        child,
                        source,
                        path,
                        language,
                        package,
                        config,
                        kind="method",
                    )
                )
            elif child.type in config.class_types:
                cls.children.append(
                    _build_class_node(
                        child,
                        source,
                        path,
                        language,
                        package,
                        config,
                    )
                )
            elif child.type in config.function_types:
                cls.children.append(
                    _build_function_node(
                        child,
                        source,
                        path,
                        language,
                        package,
                        config,
                        kind="function",
                    )
                )
    return cls


def _walk_container(
    node: tree_sitter.Node,
    source: bytes,
    path: Path,
    language: str,
    package: str | None,
    config: LanguageConfig,
) -> list[SourceNode]:
    """Yield direct-child symbol nodes (classes/functions) under `node`.

    Also looks one level inside export_statement nodes so that
    `export function foo(){}` produces a function child (plus an export ref
    from _extract_exports).
    """
    out: list[SourceNode] = []
    for child in node.children:
        if child.type in config.class_types:
            out.append(_build_class_node(child, source, path, language, package, config))
        elif child.type in config.function_types:
            out.append(_build_function_node(child, source, path, language, package, config, kind="function"))
        elif child.type in config.export_types:
            # Peek inside: `export function foo(){}` or `export class Foo{}`
            for inner in child.children:
                if inner.type in config.class_types:
                    out.append(_build_class_node(inner, source, path, language, package, config))
                elif inner.type in config.function_types:
                    out.append(
                        _build_function_node(
                            inner,
                            source,
                            path,
                            language,
                            package,
                            config,
                            kind="function",
                        )
                    )
    return out


def _extract_imports(file_root: tree_sitter.Node, source: bytes, config: LanguageConfig) -> list[Reference]:
    """Pull import edges off the top level of a file."""
    refs: list[Reference] = []
    for child in file_root.children:
        if child.type not in config.import_types:
            continue
        # Module path is typically the first 'string' descendant.
        module = None
        for desc in child.children:
            if desc.type == "string":
                module = _text(desc, source).strip("'\"")
                break
        # Imported names are 'identifier' nodes inside named/namespace clauses.
        # For v1 we collect each top-level identifier as a separate import.
        seen_names: list[str] = []

        def walk_names(n: tree_sitter.Node) -> None:
            if n.type == "identifier":
                seen_names.append(_text(n, source))
                return
            for c in n.children:
                walk_names(c)

        walk_names(child)
        # Filter the module-string identifier out (rare): handled above.
        # If no names found, emit a single bare import.
        names_to_emit = seen_names or ["<module>"]
        for name in names_to_emit:
            refs.append(
                Reference(
                    kind="import",
                    target_name=name,
                    target_module=module,
                    site=_span(child),
                    attrs={},
                )
            )
    return refs


def _extract_exports(file_root: tree_sitter.Node, source: bytes, config: LanguageConfig) -> list[Reference]:
    refs: list[Reference] = []
    for child in file_root.children:
        if child.type not in config.export_types:
            continue
        # Identifier-name on the export.
        names: list[str] = []
        for desc in child.children:
            if desc.type == "identifier":
                names.append(_text(desc, source))
            elif desc.type in config.function_types or desc.type in config.class_types:
                n = _resolve_name(desc, source, config)
                if n:
                    names.append(n)
        if not names:
            # Look for export-clause -> { name, name, ... }
            def walk(n: tree_sitter.Node) -> None:
                if n.type == "identifier":
                    names.append(_text(n, source))
                for c in n.children:
                    walk(c)

            walk(child)
        for name in names:
            refs.append(
                Reference(
                    kind="export",
                    target_name=name,
                    target_module=None,
                    site=_span(child),
                    attrs={},
                )
            )
    return refs


def generic_walk(
    config: LanguageConfig,
    path: Path,
    source: bytes,
    package: str | None,
    language: str,
) -> SourceNode:
    """Parse `source` with `config.grammar_name` and walk into a SourceNode tree."""
    grammar = get_language(config.grammar_name)
    parser = tree_sitter.Parser(grammar)
    tree = parser.parse(source)
    root = tree.root_node

    file_node = SourceNode(
        kind="file",
        name=None,
        span=_span(root),
        path=path,
        language=language,
        package=package,
    )

    parse_errors = _collect_parse_errors(root)
    if parse_errors:
        file_node.attrs["parse_errors"] = parse_errors

    file_node.children.extend(_walk_container(root, source, path, language, package, config))
    file_node.refs.extend(_extract_imports(root, source, config))
    file_node.refs.extend(_extract_exports(root, source, config))
    return file_node
