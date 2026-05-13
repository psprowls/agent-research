---
title: LanguageParser abstraction
category: concept
summary: Each language is a self-contained module under lib/parsers/ implementing a stable LanguageParser interface; per-language detail in attrs_json keeps the core graph language-agnostic.
tags: [code-graph, parsers, languages, tree-sitter, abstraction]
sources: 3
updated: 2026-05-09
tokens: 1747
---

# LanguageParser abstraction

## Definition
A stable Python interface that each language module under `lib/parsers/` implements. The interface owns its grammar binding, its tree-sitter query patterns, and its attribute extraction. Cross-module behavior (registry, file-extension dispatch, upsert layer) lives in the parser-agnostic core.

## Shape

```python
# lib/parsers/_base.py
class LanguageParser(ABC):
    name: str                      # 'typescript', 'javascript', 'python'
    file_extensions: list[str]     # ['.ts', '.tsx'] etc.
    grammar: tree_sitter.Language

    @abstractmethod
    def parse(self, file_path: Path, source: bytes, package: str | None) -> ParseResult:
        """Walk the AST and emit nodes + edges. Returns (nodes, edges) lists."""

    # Optional helpers shared by some parsers, override-able:
    def detect_language_specific_imports(self, tree, source: bytes) -> Iterable[ImportEdge]: ...
    def extract_signature(self, function_node, source: bytes) -> str: ...
```

Source: `raw/specs/architecture/3.5-language-support.md:39-57`. `ParseResult` carries node/edge records that match the [[wiki/concepts/code-graph-schema|SQLite schema]]; the core handles batching, transaction management, and `attrs_json` serialization.

## Registry

```python
# lib/parsers/__init__.py
PARSERS: dict[str, LanguageParser] = {
    "typescript": TypeScriptParser(),
    "javascript": JavaScriptParser(),
    "python": PythonParser(),
}

EXTENSIONS: dict[str, LanguageParser] = {
    ext: parser for parser in PARSERS.values() for ext in parser.file_extensions
}
```

## v1 language scope

| Language | File extensions | Tree-sitter grammar |
|---|---|---|
| **TypeScript** | `.ts`, `.tsx` | `tree-sitter-typescript` |
| **JavaScript** | `.js`, `.jsx`, `.mjs`, `.cjs` | `tree-sitter-javascript` |
| **Python** | `.py` | `tree-sitter-python` |

C# committed for v1.1 (not v2). Rust, Go, Java/Kotlin, Swift speculative post-v1.1; added when a real consumer needs each.

## `attrs_json` convention

- **Common fields** (every language): `end_line`, `end_column`, `start_column`, `is_exported`, `language`.
- **Per-kind × per-language fields**: present when meaningful in the language; absent otherwise. Consumers do `attrs.get("type_params", [])`.
- Full per-kind × per-language table at `raw/specs/architecture/3.5-language-support.md:96-152`.

## Name resolution — best-effort

Tree-sitter gives a syntax tree, not a semantic name-resolution layer. The graph is a *best-effort* index.

**Handled at v1:**
- Direct calls to imported symbols (`import { foo } from './bar'; foo();`).
- Calls within the same file.
- Method calls when the receiver type is statically declarable (TS only).
- Re-export chains, capped at depth 3.
- Default exports (resolved across import-renames).

**NOT handled at v1:**
- Dynamic dispatch through interfaces / protocols (call goes to interface method only; not concrete implementations).
- `eval`, `Function`, `__import__`, `getattr` — out of scope.
- Dynamic property access (`obj[methodName]()`).
- Decorator metaprogramming that changes function identity.
- TypeScript ambient declarations (`declare module`, `.d.ts` types without implementation).
- Python late binding (transitive callers may overshoot).

Skill content (per §3.6) tells the agent: "the call graph is best-effort; verify with `cg_query` or a quick read when the answer matters."

## Additivity contract

Adding a new language is **additive** (no core changes):

1. Add tree-sitter grammar to plugin deps.
2. Create `lib/parsers/<lang>.py` implementing `LanguageParser`.
3. Decide per-kind `attrs_json` for the language.
4. Implement name resolution at the v1 level (direct + same-module).
5. Add fixtures at `fixtures/<lang>/<n>.<ext>` + `<n>.expected.json`.
6. Register in `lib/parsers/__init__.py`.
7. Update `cg_status.languages_indexed` to surface the new language.

## Tree-sitter distribution

v1 leans on **`tree-sitter-language-pack`** — pre-compiled wheels for macOS/Linux/Windows; pip-installable. This is the local stdlib break per §3.1; isolated to `lattice-graph` so [[wiki/plugins/lattice-wiki/lattice-wiki]] keeps its pure-stdlib invariant.

Fallback if the package goes unmaintained: bundle `.so`/`.dylib`/`.dll` per platform with the plugin (more work but already-known-feasible).

## Test fixtures

Each parser ships with fixture files under `fixtures/<language>/`. Each fixture exercises one feature; each has a corresponding `.expected.json` listing expected nodes and edges. Tests via `python -m unittest discover` (matching `lattice-wiki`'s pattern).

## Used in
- [[wiki/plugins/lattice-graph/lattice-graph]] — owns the parser tier

## Related patterns
- [[wiki/concepts/code-graph-schema]] — what `ParseResult` materializes into
- [[wiki/concepts/code-graph-mcp-surface]] — `cg_status.languages_indexed` surfaces the registry

## Two implementation strategies (config-driven vs. custom)

The `lattice-source-parser` design adds an explicit asymmetry under the same interface:

- **Config-driven** (`parsers/_generic.py` + a `LanguageConfig` per language) for C-family languages (JavaScript, TypeScript, future Java/Kotlin/Scala/C#). Each language module declares node types, field names, and call/import shapes; the generic walker turns that into a `SourceNode`.
- **Custom walk** (e.g. `parsers/python.py`) for outliers whose AST shape diverges enough that a config-driven approach gets tortured. Python's import variants (`from X import Y as Z`), decorator handling, `__all__`, and `_name`/`__name` visibility convention earn it a custom walker.

Both strategies emit identical `SourceNode` shape — the asymmetry is internal. Lifted from `~/Personal/research/graphify-extraction/`. Source: 2026-05-lattice-source-parser-design §6.1.

## Tolerant parsing

Tree-sitter `ERROR` nodes never abort the parse. The walker emits a partial tree and records offending spans in `file_node.attrs['parse_errors']`. Consumers choose how to react. Matches graphify's pattern. Source: 2026-05-lattice-source-parser-design §6.

## Sources
- 2026-05-architecture-3.5-language-support — original §3.5 design defining the interface
- 2026-05-lattice-source-parser-readme — README confirms v1 language scope (Python/JavaScript/TypeScript) and the per-language module shape behind a single graph projection
- 2026-05-lattice-source-parser-design — authoritative design; locks in the config-driven vs. custom-walk asymmetry, tolerant parsing, and that the parser package owns the interface (lifted out of `lib/parsers/` in the plugin)

## Open questions / gotchas
- C# `kind: namespace` — new node kind (lean: yes; bumps schema_version) vs. namespace as edge attribute. Resolved at v1.1 implementation time.
- C# partial classes — parse-time merge (lean) vs. multi-node per partial.
- `using X = Y` aliases (C#) — lean: skip at v1.1.
