---
title: lattice-wiki-agent — Work
category: package
summary: Open issues, gaps, and tech debt in lattice-wiki-agent — surfaced from reading the code on 2026-05-09.
updated: 2026-05-09
tokens: 1623
---

# lattice-wiki-agent — Work

The package is at version `1.0.0` (`packages/lattice-wiki-agent/pyproject.toml:7`) but several agents are placeholder-thin and the test suite is light (3 test files, ~174 lines of test code). Treat the agent as **functional but lightly battle-tested**; the LLM-driven `IngestAgent` is the most complete piece, the others are scaffolding.

## Bugs

### Region default disagrees between the dataclass and the defaults dict

`packages/lattice-wiki-agent/src/lattice_wiki_agent/config.py:19` sets the dict default `region: "us-east-1"`, but `packages/lattice-wiki-agent/src/lattice_wiki_agent/config.py:27` sets `BedrockConfig.region: str = "us-west-2"`. Effect:

- No `.lattice-wiki.json` file → `Config()` uses dataclass defaults → region is `us-west-2`.
- `.lattice-wiki.json` exists with no `bedrock.region` key → defaults dict merge wins → region is `us-east-1`.

These should agree. Likely fix: pick one region and update both. Until then, callers should set `AWS_DEFAULT_REGION` explicitly.

### `Path(wiki).parent` is wrong for nested wiki layouts

`cli.py:59`, `cli.py:73`, `cli.py:92` infer the repo root from the wiki path with `repo = Path(wiki).parent`. This is correct only when the wiki sits exactly one directory below the repo root (e.g. `<repo>/wiki/`). It is wrong for this very repo, where the wiki lives at `lattice/wiki/` — `Path(wiki).parent` resolves to `<repo>/lattice`, not the actual repo root. `load_config(repo)` then looks for `.lattice-wiki.json` in the wrong place. The `init` and `scan` subcommands avoid this by taking `--repo` explicitly; `lint`, `ingest`, `query` should follow suit.

## Tech debt

- **No README inside the package.** New contributors land on `pyproject.toml` and have to infer the surface from the agents folder.
- **Test coverage is shallow.** `test_cli.py` only checks that `--help` mentions each flag. `test_agents.py` (65 lines) and `test_ingest.py` (66 lines) cover the happy path with a mock model. There are no tests for the `Path(wiki).parent` heuristic, the `SystemExit` swallow in `LintAgent`, or the `ClickException` branches in `cli.py:75` / `cli.py:94`.
- **No integration with [[wiki/concepts/explicit-not-magic-update-lifecycle]] guarantees.** Nothing verifies that `update_index_log` actually ran after `update_refs` — if the LLM rate-limits, the vault can end up with a new source page but no index/log update.
- **Hard-coded `stale_days=90, log_gap_days=14`** in `LintAgent.run()` (`agents/lint.py:18`). These should come from `Config` or be flag-overridable on the CLI.

## Features

### `ScanAgent` accepts a model but never uses it

`packages/lattice-wiki-agent/src/lattice_wiki_agent/agents/scan.py:11` takes `model: Any | None` and stores it on `self._model`, but `run()` (`scan.py:15`) only calls the mechanical `discover_workspaces`. The CLI builds a [[wiki/concepts/bedrock-langgraph-stack|Bedrock]] client when the scan backend is `"bedrock"` (`cli.py:45`), pays the AWS overhead, and discards it. Either drop the `model` parameter or wire up an LLM-driven post-processing step (e.g. propose stub package pages with semantic descriptions, the way the plugin's `lattice-wiki:scanner` sub-agent does).

### `InitAgent` ignores its `model` parameter

`packages/lattice-wiki-agent/src/lattice_wiki_agent/agents/init.py:12` accepts `model` but never reads it. Same pattern as `ScanAgent`. The CLI's `init` subcommand similarly builds a model when `backends.init = "bedrock"` (`cli.py:27`) only to discard it.

### `InitAgent.run()` has a `tool` parameter the CLI never sets

`packages/lattice-wiki-agent/src/lattice_wiki_agent/agents/init.py:19` defaults `tool="all"`, but `cli.py:28` doesn't pass `tool` at all. So the only reachable value is `"all"`. Either expose `--tool` on the CLI or drop the parameter from the agent.

### `IngestAgent` never creates wikilinks back to its own output

The ingest pipeline writes a source summary at `<vault>/sources/<stem>.md` (`agents/ingest.py:114-117`) and updates referenced pages (`agents/ingest.py:130-148`), but the prompt for `update_refs` (`agents/ingest.py:140`) doesn't instruct the LLM to add a `[[wiki/sources/<stem>]]` wikilink to the page being updated. The plugin's interactive ingest workflow does this manually. Result: the headless ingest can produce technically-correct page edits that don't link back to the source, partially defeating the index.

### `IngestAgent` doesn't capture ADRs

The interactive ingest workflow asks "is this a decision worth an ADR?" and creates `<vault>/adrs/<NNNN>-<slug>.md` if so. The headless agent has no equivalent step. Decisions buried in source summaries stay buried.

### `IngestAgent` doesn't flag contradictions

Same gap — the interactive flow inserts `> ⚠️ Contradiction:` callouts when the source disagrees with code or with another vault page. The agent's `update_refs` step has no contradiction-detection prompt.

### `LintAgent` semantic pass returns only a `summary` string

`agents/lint.py:28` declares `SemanticResult { summary: str, issues: list[str] }` but `_semantic_pass` (`agents/lint.py:36`) returns only `r.summary` and discards the issues list. Either return both or drop `issues` from the schema.

## Open questions

- Should `ScanAgent` get an LLM step that proposes stub package pages, mirroring `lattice-wiki:scanner`? Or stay mechanical and let `IngestAgent` handle every LLM-driven update?
- Should the agent emit machine-readable artifacts (e.g. JSON-formatted ingest reports) so a CI pipeline can comment on a PR with "this ingest touched pages X, Y, Z"? Today only `scan` and `lint` JSON-print their result.
- Is Bedrock the right long-term backend, or should the config grow a `provider:` key (Anthropic API, OpenAI, Bedrock) and dispatch?

## Related

- [[wiki/packages/lattice-wiki-agent/lattice-wiki-agent]] — overview.
- [[wiki/packages/lattice-wiki-agent/api]] — surface details.
- [[wiki/packages/lattice-wiki-agent/patterns]] — design conventions.
- [[wiki/packages/lattice-wiki-core/lattice-wiki-core]] — the underlying library; some gaps could be fixed there instead.
