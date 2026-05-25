---
title: lattice-wiki-agent — API
category: package
summary: CLI subcommands, agent classes, configuration, and Bedrock model factory exposed by lattice-wiki-agent.
updated: 2026-05-09
tokens: 1962
---

# lattice-wiki-agent — API

This page enumerates the public surface. Source of truth: the code under `packages/lattice-wiki-agent/src/lattice_wiki_agent/`.

## Public API

All agents live in `lattice_wiki_agent.agents.*`. Each exposes an async `run(...)` coroutine; callers wrap it in `asyncio.run` (CLI does this) or `await` it from another async context.

### `IngestAgent`

```python
IngestAgent(model: ChatBedrockConverse, wiki_path: Path)
await agent.run(source_path: Path) -> dict
```

Source: `packages/lattice-wiki-agent/src/lattice_wiki_agent/agents/ingest.py:180`.

Six-node LangGraph (`ingest.py:189`):

1. `read` (`ingest.py:73`) — read source bytes; no LLM.
2. `extract` (`ingest.py:80`) — structured output `ExtractResult{tldr, key_claims}`.
3. `identify` (`ingest.py:92`) — structured output `IdentifyResult{pages: list[str]}`.
4. `write_summary` (`ingest.py:104`) — structured output `SummaryResult{content}`; writes `<vault>/sources/<stem>.md`.
5. `update_refs` (`ingest.py:123`) — for each identified page that exists, structured output `RefUpdateResult{updated_page, content}`; overwrites the page.
6. `update_index_log` (`ingest.py:155`) — re-renders `index.md` via `lattice_wiki_core.update_index.{scan_vault, render_index}` and appends a log line via `lattice_wiki_core.append_log.append_log`. No LLM.

`run()` returns the final `IngestState` dict (`ingest.py:29`) including `tldr`, `key_claims`, `pages_to_touch`, `summary_content`, `updated_pages`.

### `QueryAgent`

```python
QueryAgent(model: ChatBedrockConverse, wiki_path: Path)
await agent.run(question: str) -> {"answer": str, "sources": list[str]}
```

Source: `packages/lattice-wiki-agent/src/lattice_wiki_agent/agents/query.py:11`. Pulls top-5 BM25 hits from `lattice_wiki_core.wiki_search.bm25_scores` (`query.py:22`), assembles a context block, and calls the model once with `with_structured_output(Answer)`.

### `ScanAgent`

```python
ScanAgent(model: Any | None, wiki_path: Path)
await agent.run(repo_path: Path) -> {"packages": list, "count": int}
```

Source: `packages/lattice-wiki-agent/src/lattice_wiki_agent/agents/scan.py:10`. Calls `lattice_wiki_core.scan_monorepo.scan` and wraps the result. The `model` parameter is currently unused — see [[wiki/packages/lattice-wiki-agent/work]].

### `LintAgent`

```python
LintAgent(model: Any | None, wiki_path: Path)
await agent.run(semantic: bool = False) -> {"issues": dict, "semantic_summary"?: str}
```

Source: `packages/lattice-wiki-agent/src/lattice_wiki_agent/agents/lint.py:11`. Runs `lattice_wiki_core.lint_wiki.scan` with `stale_days=90, log_gap_days=14` (`lint.py:18`). Catches `SystemExit` so a failing core lint doesn't crash the agent (`lint.py:19`). When `semantic=True` and a model is supplied, calls `with_structured_output(SemanticResult)` for a one-shot summary.

### `LogAgent`

```python
LogAgent(wiki_path: Path)
await agent.run() -> str
```

Source: `packages/lattice-wiki-agent/src/lattice_wiki_agent/agents/log.py:9`. No model parameter, no LLM. Resolves the vault via `lattice_wiki_core.layout_io.resolve_vault_dir` and returns the contents of `<vault>/log.md` (or a placeholder if missing).

### `InitAgent`

```python
InitAgent(model: Any | None, wiki_path: Path)
await agent.run(repo_path: Path, topic: str, tool: str = "all", vault_name: str | None = None) -> None
```

Source: `packages/lattice-wiki-agent/src/lattice_wiki_agent/agents/init.py:10`. Calls `lattice_wiki_core.init_vault.init_wiki` with `non_interactive=True, force=False`. The CLI never passes `tool`, so it defaults to `"all"` (`init.py:19`).

### `make_bedrock`

```python
make_bedrock(cfg: BedrockConfig) -> ChatBedrockConverse
```

Source: `packages/lattice-wiki-agent/src/lattice_wiki_agent/bedrock.py:11`. Honours environment overrides:

- `LATTICE_WIKI_MODEL` overrides `cfg.model`.
- `AWS_DEFAULT_REGION` overrides `cfg.region`.

Returns a `langchain_aws.ChatBedrockConverse` instance — every agent that needs an LLM uses `model.with_structured_output(<dataclass>).ainvoke([...])` against this client.

### `load_config`

```python
load_config(project_root: Path) -> Config
```

Source: `packages/lattice-wiki-agent/src/lattice_wiki_agent/config.py:39`. Reads `<project_root>/.lattice-wiki.json` if present, merging onto `_DEFAULTS` (`config.py:8`).

## CLI

Console script declared at `packages/lattice-wiki-agent/pyproject.toml:22` → `lattice_wiki_agent.cli:main`.

The CLI is a Click `@click.group()` (`cli.py:13`). Every subcommand calls `load_config(repo)` to determine which backend (`"claude"` or `"bedrock"`) to use, then invokes the matching agent via `asyncio.run`.

| Subcommand | Required flags | Optional flags | Backend gate | Source |
|---|---|---|---|---|
| `init`   | `--wiki`, `--repo` | `--topic`, `--vault-name` | none — runs even without [[wiki/concepts/bedrock-langgraph-stack|Bedrock]] | `cli.py:22` |
| `scan`   | `--wiki`, `--repo` | — | none | `cli.py:38` |
| `lint`   | `--wiki` | `--semantic` | `--semantic` requires `bedrock` | `cli.py:53` |
| `ingest` | `--wiki`, positional `SOURCE_FILE` | — | hard-fails unless `backends.ingest = "bedrock"` (`cli.py:75`) | `cli.py:69` |
| `query`  | `--wiki`, positional `QUESTION` | — | hard-fails unless `backends.query = "bedrock"` (`cli.py:94`) | `cli.py:88` |
| `log`    | `--wiki` | — | none | `cli.py:106` |

For `lint`, `ingest`, `query`, `log`, the repo path is inferred as `Path(wiki).parent` (`cli.py:59`, `:73`, `:92`). See [[wiki/packages/lattice-wiki-agent/work]] — this is brittle for nested wikis.

### Configuration — `.lattice-wiki.json`

```json
{
  "backends": {
    "scan": "claude",
    "lint": "claude",
    "ingest": "bedrock",
    "query": "bedrock",
    "init": "claude",
    "log": "claude"
  },
  "bedrock": {
    "model": "us.amazon.nova-pro-v1:0",
    "region": "us-east-1"
  }
}
```

- `backends.<command>` ∈ `{"claude", "bedrock"}` — `"claude"` means "no Bedrock model is built; agent runs mechanically only". Default is `"claude"` for every command (`config.py:9`).
- `bedrock.model` — Bedrock inference profile id; default `us.amazon.nova-pro-v1:0` (`config.py:18`).
- `bedrock.region` — AWS region; default `us-east-1` from the dict (`config.py:19`) but `BedrockConfig.region` dataclass default is `"us-west-2"` (`config.py:27`). See [[wiki/packages/lattice-wiki-agent/work]] — these disagree.

## Related

- [[wiki/packages/lattice-wiki-agent/patterns]] — how the agents compose around `lattice-wiki-core`.
- [[wiki/packages/lattice-wiki-agent/context]] — why the agent layer exists.
- [[wiki/packages/lattice-wiki-core/lattice-wiki-core]] — the library every agent delegates to.
