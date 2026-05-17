---
title: lattice-wiki-agent — Patterns
category: package
summary: How lattice-wiki-agent composes lattice-wiki-core with LangGraph and Bedrock — agent-per-operation, structured output, per-command backend selection.
updated: 2026-05-09
tokens: 1336
---

# lattice-wiki-agent — Patterns

## Key patterns

### Imports core, doesn't shell out

Every agent imports the corresponding function directly from [[wiki/packages/lattice-wiki-core/lattice-wiki-core]] rather than spawning the equivalent `scripts/*.py` from the [[wiki/plugins/lattice-wiki/lattice-wiki]] plugin:

| Agent | Core call |
|---|---|
| `ScanAgent`   | `lattice_wiki_core.scan_monorepo.scan` (`agents/scan.py:7`) |
| `LintAgent`   | `lattice_wiki_core.lint_wiki.scan` (`agents/lint.py:8`) |
| `IngestAgent` | `lattice_wiki_core.update_index.{scan_vault, render_index}` + `lattice_wiki_core.append_log.append_log` + `lattice_wiki_core.layout_io.resolve_vault_dir` (`agents/ingest.py:19-21`) |
| `QueryAgent`  | `lattice_wiki_core.wiki_search.{load_docs, bm25_scores, snippet, tokenize}` (`agents/query.py:8`) |
| `LogAgent`    | `lattice_wiki_core.layout_io.resolve_vault_dir` (`agents/log.py:6`) |
| `InitAgent`   | `lattice_wiki_core.init_vault.init_wiki` (`agents/init.py:7`) |

This is enforced at the dependency layer — `pyproject.toml:15` lists `lattice-wiki-core`, and `[tool.uv.sources]` (`pyproject.toml:32`) pins it as an editable path-source for local dev.

### Agent-per-operation

Each wiki operation is its own class with `__init__(model, wiki_path)` and a single async `run(...)`. This makes the CLI thin — `cli.py` only chooses a backend, builds a model if needed, and calls `asyncio.run(Agent(...).run(...))`. Callers using the library directly can compose agents in any order without going through Click.

### LangGraph only where it pays

Five of six agents are linear and don't use LangGraph. Only `IngestAgent` builds a `StateGraph` (`agents/ingest.py:189`) because the workflow is six steps with shared state (`IngestState`, `agents/ingest.py:29`) and benefits from explicit node boundaries:

```
read → extract → identify → write_summary → update_refs → update_index_log → END
```

`read` and `update_index_log` are pure-Python nodes; the four middle nodes are factory-built closures (`_make_node_*`) that bind the LLM model into the node function. Every LLM node calls `model.with_structured_output(<dataclass>)` so the response shape is enforced by `langchain-core`'s structured-output adapter.

### Structured output everywhere

Every LLM call goes through `with_structured_output(<dataclass>)`:

- `IngestAgent`: `ExtractResult`, `IdentifyResult`, `SummaryResult`, `RefUpdateResult` (`agents/ingest.py:46-65`).
- `QueryAgent`: inline `Answer` dataclass (`agents/query.py:30`).
- `LintAgent`: inline `SemanticResult` dataclass (`agents/lint.py:27`).

The agents never parse free-form text. This shifts schema enforcement to `langchain-aws` / `langchain-core` and keeps the agent code linear.

### [[wiki/concepts/bedrock-langgraph-stack|Bedrock]] factory matches sibling packages

`make_bedrock(cfg)` (`bedrock.py:11`) is intentionally minimal — three lines that build a `ChatBedrockConverse` honouring `LATTICE_WIKI_MODEL` and `AWS_DEFAULT_REGION` env overrides. The source comment (`bedrock.py:1`) flags this as the same pattern used in `lattice-curator`, so callers who already have AWS env-var conventions get them for free.

### Resilient lint

`LintAgent.run` wraps the core lint scan in `try / except SystemExit` (`agents/lint.py:17`). The core script calls `sys.exit(1)` when it finds drift; the agent swallows that exit and returns `{"issues": {}}` so the headless caller still gets a result dict. This is a deliberate adaptation of a CLI-friendly behaviour into a library-friendly one.

### Vault directory resolution

Both `IngestAgent.__init__` (`agents/ingest.py:186`) and `LogAgent.run` (`agents/log.py:14`) call `lattice_wiki_core.layout_io.resolve_vault_dir` rather than hard-coding a vault path. This keeps the agent compatible with whatever `--vault-name` was passed at init.

## Conventions

- **Per-command backend selection** — `Config.backends` (`config.py:32`) is a dict keyed by command name with values in `{"claude", "bedrock"}`. Default for every command is `"claude"` (`config.py:9`), so a fresh checkout without `.lattice-wiki.json` can scan/lint/log/init headlessly but cannot ingest or query without first opting in. `ingest` and `query` hard-fail with a `ClickException` if the backend isn't `"bedrock"` (`cli.py:75`, `:94`).
- **No CLI logic in agents** — the Click layer owns flag parsing, backend selection, and `asyncio.run`; agents own only the operation logic.
- **Async everywhere** — all `run()` methods are `async def` even when the body is purely synchronous (e.g. `ScanAgent`), so callers can `await` uniformly.

## Related

- [[wiki/packages/lattice-wiki-agent/api]] — flag and signature reference.
- [[wiki/packages/lattice-wiki-agent/context]] — why this layer exists alongside the plugin skill.
- [[wiki/packages/lattice-wiki-core/lattice-wiki-core]] — the library these patterns are built on.
- [[wiki/concepts/explicit-not-magic-update-lifecycle]] — the lifecycle these agents mechanise.
