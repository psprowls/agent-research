# Cleanup audit: library packages

Read-only review of the workspace's library packages across four dimensions:
executable `main()`/CLI entry points, dead code, environment-variable usage, and
coding-style consistency. **Nothing in this document has been changed** — it is a
backlog of cleanup candidates.

Covered: **Part 1** — `workspace-io`, `wiki-io`, `graph-io`. **Part 2** —
`model-adapter`, `subagent-runtime`, `source-parser`, `eval-harness`. **Part 3** —
`graph-wiki-core`, `graph-wiki-cli`, `graph-wiki-mcp`.

> Note: the request named `workflow-io`, which does not exist. The intended target
> is **`workspace-io`** (audited in Part 1).
>
> `eval-harness`, `graph-wiki-cli`, and `graph-wiki-mcp` are **allowed** to contain
> executable code; their entry points are inventoried for completeness, not flagged
> as violations. `graph-wiki-core` is a **library** — executable surface there IS a
> violation.

## Ground rule being enforced

The only modules permitted to contain executable code — a `main()` function and/or
an `if __name__ == "__main__":` block — live in `graph-wiki-cli`, `graph-wiki-mcp`,
and the scripts in the `graph-wiki` plugin. The reference example of a **violation**
is `packages/wiki-io/src/wiki_io/update_index.py` (`def main()` at L321 +
`if __name__ == "__main__":` at L413). Library packages should be import-only.

## Summary

| Package | `main()`/CLI | Dead-code candidates | Env vars |
|---|---|---|---|
| `graph-io` | none (clean) | 1 function + 3 unused params | 1 (`GRAPH_WIKI_LOCK_TIMEOUT_MS`) — OK |
| `wiki-io` | **8 violating modules** | 1 orphaned module + several test-only symbols | 0 (correctly delegated) |
| `workspace-io` | **1 violating module** | 1 orphaned module + 3 unused accessors | 1 (`GRAPH_WIKI_WORKSPACE`) — OK |
| `model-adapter` | none (clean) | none | 0 |
| `subagent-runtime` | none (clean) | none | 0 |
| `source-parser` | none (clean) | 1 dead method (+ public-but-unused API) | 0 |
| `eval-harness` | allowed — 1 CLI + 1 interactive (inventory only) | 1 dead alias + 3 dead re-exports | 4 (`baseline.py`) + 1 (`sweep.py`) — OK |
| `graph-wiki-core` | **2 violating modules** (embedded Typer apps) | 2 orphaned modules + 3 dead symbols | 0 (delegated) |
| `graph-wiki-cli` | allowed — `gw` console script (inventory only) | 4 dead re-exports + 2 unwired shims | 1 (`GRAPH_WIKI_BOOTSTRAP_REEXEC`) — OK |
| `graph-wiki-mcp` | allowed — MCP server + console script (inventory only) | none | 0 (delegated) |

---

## 1. Executable `main()` / CLI entry points (rule violations)

### wiki-io — 8 violating modules

Every one has both `def main()` and `if __name__ == "__main__":`, all using `argparse`.
They split into two cleanup classes:

**Class A — pure dead executable code (no shim, no `[project.scripts]`, no caller).**
Safe to delete the `main()` + `__main__` blocks outright. Also drop their now-inaccurate
`python … --dry-run` usage docstrings.

| Module | `main` | `__main__` | Library logic still used? |
|---|---|---|---|
| `update_index.py` | L321 | L413 | Yes — `update_index()` used by `ingest.py`, `scan.py`, `ingest_work_item.py`. Keep the function, drop the CLI. |
| `update_tokens.py` | L225 | L247 | Yes — `count_tokens()` used by `query.py`. |
| `append_log.py` | L132 | L149 | Yes — `append_log()` used by ingest/log/scan paths. |

**Class B — plugin shim depends on `main`.** Each has a shim under
`plugins/graph-wiki/skills/graph-wiki/scripts/<mod>.py` doing
`from wiki_io.<mod> import main as _core_main`. Cleanup means **inverting the shim
contract**: move the `argparse` body into the shim (or the CLI package), leaving wiki-io
import-only. Requires editing both files per module — not a pure deletion.

| Module | `main` | `__main__` | Shim |
|---|---|---|---|
| `init_vault.py` | L258 | L305 | `scripts/init_vault.py` imports `main as _core_main` |
| `ingest_source.py` | L227 | — | `scripts/ingest_source.py` imports `main` |
| `wiki_search.py` | L153 | L191 | `scripts/wiki_search.py` imports `main` |
| `lint_wiki.py` | L491 | L534 | `scripts/lint_wiki.py` imports `main` |
| `graph_analyzer.py` | L176 | L208 | `scripts/graph_analyzer.py` imports `main` |

`graph_analyzer.py` is special: its library functions (`analyze`, `build_graph`,
`connected_components`) have **zero production consumers** (test-only), so it is a script,
not a library module — relocate it wholesale to the CLI/plugin layer.

### workspace-io — 1 violating module

`config.py:113-119`:
```python
def _main() -> int:
    print(resolve().workspace)
    return 0

if __name__ == "__main__":
    sys.exit(_main())
```
The library functions (`resolve`, `GraphWikiConfig`, etc.) are heavily imported and must
stay. Only the executable block must go. Its **sole exerciser** is the test
`test_cli_prints_workspace_to_stdout` (`tests/test_config.py:106-117`), which runs
`python -m workspace_io.config`. Removing the block also orphans `import sys`
(`config.py:21`), so delete that import and update/remove the test.

### graph-io — clean

No `main()`, `__main__`, `argparse`, `typer`, or `sys.argv` in any module. Pure library.
`exit_codes.py` defines a code table (`SUCCESS=0` … `AMBIGUOUS=7`) but **never `sys.exit()`s**
inside the library — codes are returned and surfaced by CLI callers. This is the correct
pattern; no action.

---

## 2. Dead code

### wiki-io

- **`link_rewriter.py` — orphaned production module (strongest signal).** Public surface
  (`rewrite_text`, `build_rewrite_table`, `rewrite_vault`, `RewriteResult`) has zero
  non-test usage. The module docstring promises wiring into a `cg migrate-vault` CLI
  subcommand that **was never built** (no `migrate-vault` symbol anywhere). Either finish
  the wiring or delete the module + `test_link_rewriter.py` + `test_link_rewriter_build_table.py`.
- **`graph_analyzer.py`** — library functions test-only (see Class B above).
- **Test-only public symbols** (not dead, but flag): `wiki_search.py`
  (`bm25_scores`, `load_docs`, `snippet`, `tokenize`); `update_index.py`
  (`render_index`, `scan_vault`); `index_generator.py` (`IndexWriteResult`, `PlacedEntity`).
- **Stale docstrings asserting a false state**: `update_index.py:3-4` and
  `index_generator.py:3` claim "Phase 46 cutover deletes `update_index.py`." That deletion
  never happened — `update_index()` is still live (per-folder sub-indexes at `scan.py:1366`).

### graph-io

- **`queries.list_entry_points` (`queries.py:895`) — dead in production.** Referenced only
  by `test_queries.py`. The CLI command uses `entry_points_for_package` instead. All sibling
  `list_*` helpers have real callers; this is the lone exception. Remove function + its test
  block (unless kept for symmetric public surface).
- **Unused `ctx` parameters** (surgical, signature-only):
  - `derived_edges._compute_references_and_depends_on(conn, repo_root, ctx)` — `ctx` unused (L70-73)
  - `derived_edges._compute_testsuite_domain(conn, ctx)` — `ctx` unused (L171-173)
  - `test_suites._emit_tests_edges(..., ctx, ...)` — `ctx` unused (L425-428)
- *False-positive guard:* the `*Description`/`*Record` dataclasses in `queries.py` look
  unused by name-grep but are query return contracts consumed structurally via
  `dataclasses.asdict()` — **keep them**. `internal_dependencies_of` is used by
  `wiki-io/index_generator.py:613` (bare import) — **keep**.

### workspace-io

- **`versions.py` — orphaned module.** `PendingUpdate`, `pending_updates`, `warn_if_stale`
  (all re-exported in `__init__.py`) have **zero non-test consumers** repo-wide. Remove the
  module + its three `__init__.py` re-exports, or document the intended-but-unshipped consumer.
- **Three unused path accessors in `paths.py`** (test-only): `raw_dir` (L19),
  `work_dir` (L23), `knowledge_dir` (L27). Low priority (one-line pure accessors).

---

## 3. Environment-variable usage

All env-var usage is consistent, centralized, and well-guarded. No cleanup required.

| Env var | Location | Purpose |
|---|---|---|
| `GRAPH_WIKI_WORKSPACE` | `workspace-io/config.py:87` | Workspace override; sole source of truth for workspace discovery. |
| `GRAPH_WIKI_LOCK_TIMEOUT_MS` | `graph-io/update.py:154` | SQLite busy-timeout for the write lock; defaults to 30 000 ms, parsed defensively. |

- **wiki-io reads no env vars directly** — all resolution delegates through
  `_workspace.resolve_wiki_and_repo` → `workspace_io.config.resolve()`. Correct.
- Minor docstring fix only: `wiki-io/graph_analyzer.py:6` and `append_log.py:9` imply the
  module reads `GRAPH_WIKI_WORKSPACE` itself; it does not (it delegates).

---

## 4. Coding-style consistency

### Convention upheld everywhere (no action)
- **Docstring before `from __future__ import annotations`** — compliant across all three
  packages (future-first would null out `__doc__`).
- **pathlib throughout** — no `os.path` usage in any package.

### wiki-io
- **`print` vs `logging` mix.** The 8 `main()`-bearing modules are `print`-heavy (CLI output);
  `entity_writer.py` is logging-only; `init_vault.py` mixes **both** `print` and `logging` in
  one file (the concrete inconsistency to flag). Once the CLI bodies move out (§1), the library
  modules become logging-only naturally.
- **Type-hint coverage split.** Legacy ports (`append_log`, `update_index`, `wiki_search`,
  `graph_analyzer`, `lint_wiki`) are largely untyped; newer modules (`drift`, `entity_writer`,
  `index_generator`, `backlink_index`, all `lint/`) are fully typed.
- **Vestigial shebangs** (`#!/usr/bin/env python3`) on the older modules only — meaningless for
  a library and correlated 1:1 with the §1 violations.
- **Duplicated frontmatter parsers**: `update_index.py:83` and `lint/common.py:108` both define
  independent regex `parse_frontmatter` of the same format — consolidation opportunity.

### graph-io
- **Warning channel split** (most notable divergence): `domains.py` is the only module using
  `logging`; five others (`packages.py`, `entry_points.py`, `test_suites.py`, `sync_wiki.py`,
  `update.py`) use `print(..., file=sys.stderr)` with ad-hoc prefixes. Pick one — for a library,
  prefer `logging`.
- **Mid-file import**: `import_scan.py:204` does `import sqlite3` ~200 lines in; hoist to the
  top import block.
- **Aliased import outlier**: `render.py:14` does `import json as _json`; every other module uses
  plain `import json`. Normalize (verify no local shadow first).

### workspace-io
- **`config.py:101-107`** — over-indented / double-nested strict-manifest branch using the
  `if require_manifest is True:` idiom; collapse to a single condition with plain truthiness.
- **Import-style outlier**: `versions.py:7` uses `import workspace_io.manifest as manifest`
  while `init.py`/`render.py` use `from workspace_io import manifest`.
- **Cross-package private reach** (coupling smell, outside this package): `wiki-io/_workspace.py:20`
  imports the underscore-private `_find_repo_root` / `_repo_directory_override` from
  `workspace_io.config`. Consider promoting to a public wrapper.

---

## Prioritized cleanup backlog (Part 1)

**High (rule violations / clear dead code)**
1. wiki-io: delete `main()` + `__main__` from `update_index.py`, `update_tokens.py`, `append_log.py`
   (Class A — no callers). Drop their `--dry-run` usage docstrings.
2. wiki-io: invert the shim contract for `init_vault`, `ingest_source`, `wiki_search`, `lint_wiki`,
   `graph_analyzer` (Class B) — move argparse bodies to the plugin scripts / CLI.
3. workspace-io: remove `_main()` + `__main__` from `config.py:113-119`; drop orphaned `import sys`;
   update/remove `test_cli_prints_workspace_to_stdout`.
4. graph-io: remove `queries.list_entry_points` (`queries.py:895`) + its test references.

**Medium (orphaned modules)**
5. wiki-io: resolve `link_rewriter.py` — wire up `cg migrate-vault` or delete module + 2 tests.
6. wiki-io: relocate `graph_analyzer.py` wholesale to CLI/plugin (no library consumers).
7. workspace-io: remove `versions.py` + its 3 `__init__.py` re-exports (zero non-test consumers).

**Low (style / surgical)**
8. graph-io: drop unused `ctx` params in `derived_edges` (×2) and `test_suites._emit_tests_edges`.
9. graph-io: unify warning channel (prefer `logging`); hoist `import_scan.py:204` sqlite3 import;
   normalize `render.py:14` json alias.
10. workspace-io: simplify `config.py:101-107`; align `versions.py:7` import style.
11. wiki-io: fix stale "Phase 46 deletes update_index.py" docstrings; add type hints to legacy ports;
    resolve `init_vault.py` print+logging mix; drop vestigial shebangs; consolidate `parse_frontmatter`.

---

# Part 2: `model-adapter`, `subagent-runtime`, `source-parser`, `eval-harness`

Same four dimensions. Two of these packages (`model-adapter`, `subagent-runtime`) are
essentially clean; `source-parser` has one dead method; `eval-harness` is the one package
where executable code is **expected and acceptable** — its entry points are inventoried
below, not flagged.

## P2.1 — Executable `main()` / CLI entry points

### model-adapter, subagent-runtime, source-parser — clean
No `def main(`, `if __name__ == "__main__":`, `argparse`, `typer`, or `sys.argv` in any
module of these three. All pure libraries.

- `source-parser` note: `parsers/python.py:216` `_has_main_block()` detects
  `if __name__ == "__main__":` in *parsed target files* as a parser feature (consumed by
  `graph-io/structural_nodes.py:621`). That's data extraction about other code, not an
  executable block in source-parser itself. Not a violation.

### eval-harness — executable code is ALLOWED (inventory only, not cleanup)

| Module | Entry point | What it does |
|---|---|---|
| `baseline.py` | `def _main()` L407 + `if __name__ == "__main__":` L441 (argparse L409-427, `sys.exit` L419) | CLI `python -m eval_harness.baseline --cases … --workspace … --out …`. Gated behind `GRAPH_WIKI_RUN_EVAL`; runs `BaselineRecorder.record_all()`, spawning `claude -p` per case to snapshot baseline answers. |
| `preflight.py` | interactive `input()` L135 | Not a CLI, but `preflight_check()` prompts `"…proceed? [y/N] "` for human confirmation unless `auto_confirm=True`. Noted as interactive I/O. |
| `sweep.py` | none | No entry point, but `run_full_matrix()` prints recommendation blocks to stdout (L1028-1030) as its human-facing output. |

All acceptable for this package — no action.

## P2.2 — Dead code

### model-adapter — none
Every public symbol (`make_llm`, `load_role_config`, `BedrockAccessDenied`) has production
consumers in `graph-wiki-core` commands and `eval-harness`. All private helpers are reachable.

### subagent-runtime — none
`SubagentPool`, `FanOutResult`, `PerItemError`, `TaskResult`, `write_trace_record`,
`render_trace_record` all consumed by `graph-wiki-core` (scan/lint/query/propose_domains/ingest),
`graph-wiki-cli` (trace viewer), and `eval-harness`. No dead code.

### source-parser
- **Dead method: `LanguageParser.resolve_call_target` (`parsers/_base.py:34`)** — default no-op
  hook, never called, never overridden by any parser, never referenced in tests. Speculative
  extension point with zero users. Strongest signal — delete the method (keep the class).
- **Public-but-externally-unused API** (in `__init__.py.__all__`, exercised only by source-parser's
  own tests; production `graph-io` never imports them): `parse_file` (`parse.py:12`),
  `Reference` (`tree.py:20`), `Span` (`tree.py:10`), `SourceNode` (`tree.py:29`),
  `UnsupportedLanguageError` (`errors.py:8`). These are the documented public surface — flag as
  "public but externally unused," do NOT delete without a decision to narrow the public API.
  Production consumes only `projections.graph` (`GraphNode/GraphEdge/GraphRecords/to_graph_records/NodeKey`),
  `parse_bytes`, and `EXTENSIONS`.
- Parser classes (`PythonParser`, `JavaScriptParser`, `TypeScriptParser`) are wired via the
  `PARSERS`/`EXTENSIONS` registry in `parsers/__init__.py:11-17`, not direct import — **not dead**.

### eval-harness
- **Dead public alias: `resolve_citation` (`structural.py:56`)** — its comment says "other modules
  should import this name, not the private `_resolve_citation`," but **nothing imports it**. Worse,
  `divergence/librarian.py:17-47` needed exactly this and reimplemented it as private
  `_resolve_in_wiki`. Either wire librarian to the alias or delete the alias + comment.
- **Three dead re-exports in `sweep.py:48`** (`# noqa: F401`-masked, never used in body or imported
  via `eval_harness.sweep` by any test): `HARD_CAP_USD`, `estimate_sweep_cost`, `preflight_bed01`.
  (`preflight_check` on the same line IS used — keep it.)
- **Stale docstring (not dead code): `metric.py:24-25,33`** claims `make_judge`/`JUDGE_PANEL_CONFIG`
  are "re-exported from eval_harness.judge for test import verification." No test imports them from
  `metric`; they're genuinely used internally by `run_judge`. Only the docstring is wrong.
- Most other public symbols are **test-only**, which is the expected consumption pattern for an eval
  package — not dead. `pricing.cost_for_usage` / `UnknownModelError` have a real cross-package
  consumer (`subagent-runtime/trace_io.py:142`).

## P2.3 — Environment-variable usage

| Package | Env var | Location | Purpose |
|---|---|---|---|
| model-adapter | — | — | None. (Workspace resolution delegates to `workspace_io`; AWS creds consumed transitively by boto3.) |
| subagent-runtime | — | — | None. |
| source-parser | — | — | None. |
| eval-harness | `GRAPH_WIKI_RUN_EVAL` | `baseline.py:412` | Gate: baseline CLI exits 1 unless set (guards expensive runs). |
| eval-harness | `GRAPH_WIKI_RUN_JUDGES` | `sweep.py:693, 740` | Gate: skips LLM judge-panel scoring unless set. |
| eval-harness | `CLAUDE_CODE_DISABLE_AUTO_MEMORY` | `baseline.py:170` (set) | Disables auto-memory in the headless `claude -p` subprocess. |
| eval-harness | `ANTHROPIC_API_KEY` | `baseline.py:171` (popped) | Removed from subprocess env to force Bedrock routing. |
| eval-harness | (full env) `os.environ.copy()` | `baseline.py:169` | Base env passed to the `claude -p` subprocess. |

All consistent and well-guarded — no cleanup. (Minor: `GRAPH_WIKI_RUN_JUDGES` is read via a
deferred `import os` in two functions — see style note below.)

## P2.4 — Coding-style consistency

### Convention upheld
- model-adapter, subagent-runtime (after fixing the items below), source-parser, and 16/18
  eval-harness modules follow docstring-before-`from __future__ import annotations`.
- pathlib throughout all four packages; no `os.path` usage.

### subagent-runtime — docstring AFTER `__future__` (runtime-observable)
- **`pool.py:1-3` and `trace_io.py:1-3`** place `from __future__ import annotations` on line 1 and
  the module docstring on line 3 → **`pool.__doc__` / `trace_io.__doc__` are `None`.** This is the
  one finding in Part 2 with a runtime-observable effect (the rich docstrings are unreachable).
  Highest-value fix in this package. (`__init__.py` has no docstring at all — optional to add.)
- Cosmetic: `__init__.py:3` re-export list is not alphabetized while every production consumer
  imports the names sorted.

### eval-harness — docstring AFTER `__future__` (2 modules) + import ordering
- **`baseline.py:1-3` and `divergence/metric.py:1-3`** put the future import before the docstring —
  diverges from the other 16 modules and the global convention. (CPython still resolves `__doc__`
  here because the docstring remains the first statement after the future import, but normalize it.)
- `preflight.py` places module constants (`HARD_CAP_USD`, `_TIER_TOKENS`, `_ROLE_TIER`; L12-28)
  ABOVE its imports (L30-32) — every other module imports first.
- Repeated function-local `import os` (`sweep.py:691,738`; `baseline.py:167,410`) instead of one
  module-level import. (Some deferred imports — lazy `deepeval`/`boto3` in `metric.py:143-144` — are
  intentional and documented; the `import os` repetition is not.)
- `print` vs `logging` mix is defensible (CLI/user-facing stdout vs library loops) — no action.

### model-adapter — minor
- Bare `-> dict` return hints on `_load_models_config` (`loader.py:31`) and `load_role_config`
  (`loader.py:211`) while the rest of the module uses parameterized hints. Cosmetic.

### source-parser — minor
- **`TypeScriptParser.parse` (`parsers/typescript.py:41`)** is the lone unannotated parser override:
  `def parse(self, path, source, *, package=None):` vs the fully-typed `PythonParser.parse`
  (`python.py:302`) and `JavaScriptParser.parse` (`javascript.py:48`). Add annotations for parity.
- `_span`/`_text`/`_collect_parse_errors` are duplicated byte-for-byte between `parsers/python.py:18-44`
  and `parsers/_generic.py:14-68` (the custom-walker split is intentional, but these 3 pure helpers
  could be shared).
- Inert/misleading guard + comment in `_extract_calls` (`_generic.py:99-108`): the `child is not node`
  clause is always true, and the trailing comment contradicts the code. Verify against fixtures, then
  simplify to the python-walker style.
- Bare `dict`/`list[dict]` hints (`_generic.py:51,71,424`; `python.py:27`); stale "lattice" /
  `plugins/lattice-graph/` naming in `__init__.py:1`, `projections/graph.py:1`, and the package
  `CLAUDE.md` (the real consumer is `graph-io`) — doc-only.

## Prioritized cleanup backlog (Part 2)

**High (clear dead code)**
1. source-parser: remove `LanguageParser.resolve_call_target` (`parsers/_base.py:34`) — zero users.
2. eval-harness: resolve `resolve_citation` dead alias (`structural.py:56`) — wire `librarian.py`
   to it or delete the alias + comment (removes a duplicated-logic trap).
3. eval-harness: drop the 3 dead re-exports from `sweep.py:48` (`HARD_CAP_USD`, `estimate_sweep_cost`,
   `preflight_bed01`); keep `preflight_check`.

**Medium (style / correctness)**
4. subagent-runtime: move module docstrings above `from __future__ import annotations` in `pool.py`
   and `trace_io.py` (currently `__doc__` is `None`).
5. eval-harness: same docstring/`__future__` reorder in `baseline.py` and `divergence/metric.py`;
   fix the stale "re-exported for tests" docstring in `metric.py:24-25`.
6. source-parser: annotate `TypeScriptParser.parse` (`typescript.py:41`); resolve the misleading
   `_extract_calls` guard/comment (`_generic.py:99-108`) after fixture verification.

**Low (cosmetic)**
7. eval-harness: hoist `preflight.py` imports above its constants; consolidate the repeated
   function-local `import os` (`sweep.py`, `baseline.py`).
8. source-parser: de-dup or share `_span`/`_text`/`_collect_parse_errors`; parameterize bare
   `dict`/`list[dict]` hints; refresh stale "lattice" naming to `graph-io` (doc-only).
9. subagent-runtime: alphabetize `__init__.py:3` re-exports (+ optional module docstring).
10. model-adapter: parameterize the two bare `-> dict` return hints (`loader.py:31,211`).

**Clean — no cleanup:** `model-adapter` and `subagent-runtime` have no dead code, no env vars, and
no `main()` violations (only the subagent-runtime docstring placement above). `eval-harness`
executable entry points are acceptable and intentionally retained.

---

# Part 3: `graph-wiki-core`, `graph-wiki-cli`, `graph-wiki-mcp`

Same four dimensions. `graph-wiki-core` is a **library** (executable surface = violation);
`graph-wiki-cli` and `graph-wiki-mcp` are the **allowed executable packages** — their entry
points are inventoried below, not flagged.

## P3.1 — Executable `main()` / CLI entry points

### graph-wiki-core — 2 violations (library package with embedded Typer apps)

No `def main(`/`__main__`/`argparse`, but two modules embed full Typer CLI surfaces, which a
library package should not have (the command modules are meant to be *library* functions invoked
by graph-wiki-cli / graph-wiki-mcp):

- **`commands/graph.py`** — embeds `graph_app = typer.Typer(...)` (L348), a `graph_describe_app`
  subapp (L354), and 8 `@command`-decorated `*_cmd` functions (`graph_build_cmd` L412,
  `describe_*_cmd` L480-559, `graph_query_cmd` L580) + `_describe_cli` (L368). **The Typer surface
  is consumed only by core's own test** `test_commands_graph.py`. graph-wiki-mcp imports only the
  *library* functions `run_build`/`run_describe`/`run_query` + trace helpers; graph-wiki-cli has its
  own independent `graph_app` and imports nothing from this module. → Cleanup: remove the Typer
  surface only (apps, `*_cmd`, `_describe_cli`, `import typer`, the propose-domains registration at
  L634-646); keep the `run_*` library functions (live MCP API).
- **`commands/propose_domains.py`** — `propose_domains_cmd` (L584) is a Typer command body, wired
  only onto core's orphaned `graph_app` (graph.py:646). **No CLI or MCP anywhere exposes a
  `propose-domains` command.** → The whole module is dead in production: either give it a real
  entry point in graph-wiki-cli/mcp, or remove it + its registration.
- **Softer: `commands/query.py:995`** calls `sys.exit(BUDGET_EXCEEDED_EXIT_CODE)` from inside the
  library coroutine `run_query` — a library terminating the host process. Should raise a typed
  exception and let the entry point map it to an exit code (as other commands do via `*Result`).

### graph-wiki-cli — allowed (inventory only)

- **Console script:** `gw = graph_wiki_cli.cli:app` (`pyproject.toml`).
- **Root Typer app** (`cli.py:71`) mounts two sub-apps: `graph_app` (`graph_cli/main.py`, `gw graph …`,
  33 subcommands each delegating to a `q_*`/`ops_*` module's `run(args)`) and `wiki_app`
  (`wiki_cli/main.py`, `gw wiki …`: `query`/`log`/`lint`/`ack-drift` + nested `gw wiki ingest`).
- **Root commands on `app`:** `help`, `version`, `trace <file>`, `bootstrap` (→ `run_init`),
  `scan` (→ `run_scan`), plus the `_root` `--verbose` callback. `cli.py:616` `app()` under `__main__`.
- **Unwired convenience shims:** `graph_cli/main.py:334 main()` + `:338 __main__` and
  `wiki_cli/main.py:252 main()` + `:256 __main__` are NOT referenced by any console script or test
  (only reachable via `python -m …`). See dead-code below.
- The 33 `q_*`/`ops_*` modules expose only `run(args) -> int` — pure delegation targets, no entry points.

### graph-wiki-mcp — allowed (inventory only)

- **Console script:** `graph-wiki-mcp = graph_wiki_mcp.server:main` (`pyproject.toml`).
- **`main()`** (`server.py:637`) → `mcp.run(transport="stdio")` (explicit stdio per research note);
  `if __name__ == "__main__":` at L642. FastMCP app at `server.py:81`.
- **`_StdoutGuard`** (L28-51) rebinds `sys.stdout` at import time so stray stdout writes raise — a
  deliberate stdio-MCP safety mechanism, not cleanup.
- **10 registered `@mcp.tool()` tools**, each delegating to a graph-wiki-core command:
  `wiki_ping` (self-contained), `wiki_query`→`run_query`, `wiki_log`→`run_log`,
  `wiki_bootstrap`→`run_init`, `wiki_scan`→`run_scan`, `wiki_ingest`→`run_ingest_source`/`run_ingest_work_item`,
  `wiki_lint`→`run_lint`, `graph_build`→`run_build`, `graph_describe`→`run_describe`,
  `graph_query`→`run_query`. (`_pack_output` L494 is a shared helper, not a tool.)

## P3.2 — Dead code

### graph-wiki-core
- **`commands/propose_domains.py` (whole module)** — `propose_domains_cmd` + all its private helpers
  and `ProposedDomain`/`ProposeResult` dataclasses are reachable only via the orphaned `graph_app`
  registration; no production CLI/MCP exposure. Strongest signal (see P3.1).
- **`prompts/scanner.py` (whole module)** — neither `SCANNER_SYSTEM` (L91) nor `build_scanner_system`
  (L65) is imported by any production code; `scan.py` builds prompts locally. Test- and docstring-only.
- **`uri_slug.py` (whole module, `slug_from_uri`)** — superseded by `wiki_io.entity_lookup` (which
  states it "replaced the legacy `slug_from_uri`"); imported only by its own test.
- **`scan.py:231 build_stub_prompt`** — defined, never called anywhere (no production, no test).
- **`prompts/drift_judge.py:17 DRIFT_JUDGE_SYSTEM`** — zero references; production uses
  `build_drift_judge_prompt`.
- **Test-only pre-built prompt constants** (not dead, but no production consumer — production uses the
  builder functions): `INGESTOR_SYSTEM`, `LINTER_PAGE_QUALITY_SYSTEM`/`_ADR_CHAIN_SYSTEM`/`_STALE_CLAIMS_SYSTEM`,
  `LINT_PRIORITY_ORDER`; and inversely `build_librarian_system` is test-only while `LIBRARIAN_SYSTEM`
  is the live one — the builder-vs-constant convention is mixed across prompt roles (pick one).
- The `prompts/__init__.py` docstring "Exports" list is partly stale (lists `SCANNER_SYSTEM`).

### graph-wiki-cli
- **4 unused re-exports in `graph_cli/_format.py:11-17`** — `_importer_human`, `_importer_json`,
  `_is_importer_batch`, `_to_dict` have zero consumers repo-wide; only `render` is used (by the 6
  importer modules). Drop the 4; the module exists only for `render`.
- **2 unwired `main()`+`__main__` shims** — `graph_cli/main.py:334-338` and `wiki_cli/main.py:252-256`
  are not referenced by any console script or test. Remove, or document as intentional `python -m` hooks.
- All 33 `q_*`/`ops_*` modules are imported AND registered (verified — none orphaned); all `cli.py`
  helpers and `logging_config` functions are live.

### graph-wiki-mcp
- **None.** Every helper, import, and Pydantic model is reachable; all 10 tools are registered;
  `_pack_output`, `_StdoutGuard`, `main` all live. Deferred per-tool imports are all used.

## P3.3 — Environment-variable usage

| Package | Env var | Location | Purpose |
|---|---|---|---|
| graph-wiki-core | — | — | None directly; `GRAPH_WIKI_WORKSPACE` resolved downstream via `wiki_io._workspace` in `commands/_paths.py`. |
| graph-wiki-cli | `GRAPH_WIKI_BOOTSTRAP_REEXEC` | `cli.py:31` (read), `cli.py:54` (set in child env) | Loop-guard so the self-healing `uv run` re-exec in `_ensure_uv_workspace` fires at most once. |
| graph-wiki-mcp | — | — | None directly; `GRAPH_WIKI_WORKSPACE` only appears in tool/field descriptions; empty `workspace_path` passes `None` to core, which resolves it. |

All consistent and well-guarded — no cleanup. (`GRAPH_WIKI_WORKSPACE` in cli `--workspace` help text is
doc-only; the read happens in `workspace_io`.)

## P3.4 — Coding-style consistency

### graph-wiki-core
- **Docstring AFTER `from __future__ import annotations` in 14 files** (nulls `__doc__`): `config.py`,
  7 `prompts/*` modules (`scanner`, `ingestor`, `librarian`, `synthesizer`, `file_describer`,
  `code_reader`, `linter`), and 5 `commands/*` (`ingest`, `query`, `log`, `scan`, `init`, `lint`).
  ~50/50 split with the compliant files — the package's biggest style inconsistency.
- **`Optional[X]` vs `X | None`**: only the two Typer files (`graph.py`, `propose_domains.py`) use
  `Optional[...]`; every other module uses `X | None`. (Disappears if the Typer surface is removed.)
- **Command modules not parallel in shape**: `run_init`/`run_log` are declared `async` but contain no
  `await` (gratuitous — callers wrap in `asyncio.run`); `run_ack_drift` is sync; `graph.py` library
  fns return `tuple[int,str,str]` while all others return a `*Result` dataclass with no shared base
  (some carry `status`, some don't).
- `__init__.py` and `commands/__init__.py` are 0 bytes (no declared `__all__`).

### graph-wiki-cli
- **`logging_config.py:1-3`** — docstring after `from __future__` (the one clear convention violation;
  `__doc__` is `None`). Every other module places the docstring first or has none.
- **Half-finished `_format` migration**: the 6 importer modules call `_format.render` (a shim) while
  describe/list modules import `render` directly from `graph_io`. Finishing the migration lets
  `_format.py` be deleted entirely.
- **`q_find.py` diverges from the `q_*` cohort**: silent `GENERIC` returns with no stderr message
  (others emit error text), and a unique `render(..., cap=50)` truncation path. The cohort is otherwise
  very disciplined (byte-identical DB-open/error-code boilerplate, consistent stderr error convention).
- **`wiki_cli/main.py:113`** — function-local `import dataclasses as _dc` shadows the module-level
  `import dataclasses` (L12).
- Minor: per-module hand-rolled table alignment (no shared helper); `import json as _json` in graph
  modules vs plain `import json` in the Typer layer (consistent within each surface).

### graph-wiki-mcp
- **`PingInput`/`PingOutput` (L84-90)** lack `model_config = ConfigDict(extra="forbid")` that all 9
  other input models set — the one tool that silently accepts extra fields (behavioral inconsistency).
- **Mixed quote style** in `ConfigDict(extra=…)`: `'forbid'` (wiki models) vs `"forbid"` (graph models).
- **Inconsistent error-surfacing**: most `wiki_*` tools raise raw; `wiki_ingest` wraps into
  `RuntimeError`; `graph_*` tools return a structured `GraphCommandOutput(status="error", …)`. Three
  conventions in one file — hosts get inconsistent failure semantics.
- **`ctx: Context` used inconsistently**: `wiki_query`/`wiki_scan`/`wiki_ingest`/`wiki_lint` call
  `ctx.report_progress`; `wiki_log`/`wiki_bootstrap`/`graph_build`/`graph_describe`/`graph_query` declare
  `ctx` but never use it (some equally long-running).
- **Inconsistent inline `# noqa: E402` import placement**, and bare `list`/`dict` hints on a few output
  fields (L114, L209, L211, L391) vs the parameterized norm.
- Good: module docstring correctly precedes `from __future__`; no `print`; pathlib throughout.

## Prioritized cleanup backlog (Part 3)

**High (rule violations / clear dead code)**
1. graph-wiki-core: remove the Typer surface from `commands/graph.py` (apps, 8 `*_cmd`, `_describe_cli`,
   `import typer`, propose-domains registration L634-646); keep the `run_*` library functions.
2. graph-wiki-core: resolve `commands/propose_domains.py` — give it a real CLI/MCP entry point or remove
   the whole module + its graph.py registration (whole-module dead in production).
3. graph-wiki-cli: drop the 4 unused re-exports in `graph_cli/_format.py:11-17` (keep `render`).
4. graph-wiki-core: delete `prompts/scanner.py`, `uri_slug.py`, `scan.py:231 build_stub_prompt`, and
   `prompts/drift_judge.py:17 DRIFT_JUDGE_SYSTEM` (all unconsumed in production); fix the stale
   `prompts/__init__.py` Exports list.

**Medium (style / correctness)**
5. graph-wiki-core: make `run_query` raise a typed budget-exceeded exception instead of `sys.exit()`
   (`query.py:995`); let the entry point map it to an exit code.
6. graph-wiki-core: move module docstrings above `from __future__ import annotations` in the 14 files
   listed in P3.4.
7. graph-wiki-cli: same docstring/`__future__` reorder in `logging_config.py`; finish the `_format` →
   `graph_io.render` migration for the 6 importer modules so `_format.py` can be deleted.
8. graph-wiki-mcp: add `ConfigDict(extra="forbid")` to `PingInput`; unify the three error-surfacing
   conventions across the wiki/graph tool families.

**Low (cosmetic)**
9. graph-wiki-core: drop gratuitous `async` on `run_init`/`run_log`; normalize `Optional[X]`→`X | None`
   (if the Typer files survive); give the `*Result` dataclasses a shared base/`status` convention.
10. graph-wiki-cli: remove the 2 unwired `main()`+`__main__` shims (or document them); drop the
    shadowing `import dataclasses as _dc` (`wiki_cli/main.py:113`); reconcile `q_find.py`'s silent
    `GENERIC` guards with the cohort convention.
11. graph-wiki-mcp: unify `ConfigDict` quote style; either use or drop the unused `ctx` params;
    normalize inline-import placement; parameterize bare `list`/`dict` output hints.

**Clean — no cleanup:** `graph-wiki-mcp` has no dead code and no env-var issues (style-only findings);
its server/tool entry points are acceptable and intentionally retained.

---

# Cross-cutting: ruff is configured but unenforced, and the tree has drifted

Separate from the per-package audits above — this is a repo-wide tooling finding. Captured
2026-06-05; **nothing decided yet**, deferred for a later pass.

## What's true (verified, ruff 0.15.12 — the pinned pre-commit rev)

- **Nothing enforces ruff.** `.pre-commit-config.yaml` declares `ruff` + `ruff-format`, but
  `pre-commit install` was never run (no hook in the git common dir), and there is **no CI**
  (`.github/workflows/` is empty). So ruff has never gated a commit. This is why the tree drifted.
- **The tree has drifted hard, under the *correct* config:**
  - `ruff format --check .` → **281 of 461 files** would be reformatted.
  - `ruff check .` → **989 lint errors**.
- **Genuine style conflict with the formatter.** The committed code is hand-curated — column-aligned
  tuples, compact multi-element collections, deliberate multi-line signatures. `ruff format` is
  Black-style: it explodes every trailing-comma collection one-per-line and collapses signatures that
  fit in 120. It will **never** reproduce the existing alignment. "Just run `ruff format`" means
  accepting that churn and losing the hand-alignment permanently. (`skip-magic-trailing-comma = true`
  would kill the per-element explosion — the single biggest churn driver — but format still collapses
  aligned tuples.)

## Corrects a prior misconception

The memory note `ruff-format-discovery-88-vs-120` claimed that passing explicit
`packages/<pkg>/src/...` paths makes ruff fall back to **line-length 88** (because the per-package
`pyproject.toml`s have no `[tool.ruff]`). **That mechanism is wrong.** `ruff check --show-settings`
resolves `line_length = 120` whether you pass a nested package path or the repo root — ruff walks up
to the root config correctly. The note's *conclusion* ("the tree is already format-dirty; don't run
`ruff format` to fix your diff") is right, and bigger than stated: the drift is real under 120, not an
artifact of an 88 fallback. (Memory note to be corrected/retired.)

## The 989 `ruff check` errors, triaged by rule

| Rule | Count | Nature |
|---|---|---|
| E402 import-not-at-top | 431 | mostly the guarded/deferred-import + docstring-first convention — largely intentional |
| I001 unsorted imports | 247 | auto-fixable, low-risk |
| E501 line-too-long | 180 | real long lines |
| F401 unused import | 95 | some are `__init__` re-exports, some genuinely dead |
| F841 unused local | 20 | smells |
| E741 ambiguous name (`l`/`I`/`O`) | 10 | style |
| **F821 undefined name** | **4** | **likely real bugs** — see below |
| F811 redefinition | 1 | `test_scan_parity.py:67` redefines `patch` |
| F541 f-string w/o placeholders | 1 | trivial |

~87% (E402 + I001 + E501 = 858) is style/noise. The F-codes are the only smell/bug signal.

**F821 detail (the only likely-real bugs):**
- `packages/graph-wiki-core/tests/unit/test_query_search.py:174-175` — `hashlib` used but never imported (×3).
- `packages/eval-harness/tests/eval/test_sweep_dry_run.py:58` — `SweepResult` undefined.
- Both are in test files (may be masked by being skipped / star-imports) — confirm before assuming green.

## Decision options (for the return pass)

1. **Lint-only, curated + enforce.** Drop `ruff-format` (formatting stays human-owned). Tune
   `ruff check` to ignore the rules that fight the style (E402, E501), keep I001 + the F-codes, fix the
   real smells, then actually `pre-commit install` so it gates going forward. Small diff, real signal.
   *(This was the leaning recommendation.)*
2. **Submit to the formatter.** One big `ruff format` + `ruff check --fix` commit across all 461 files;
   accept the 281-file churn and loss of manual alignment; then install pre-commit. Conventional and
   fully enforced, but a massive one-time diff.
3. **Just fix the real bugs.** Fix only F821/F811/F841/F401; leave config + enforcement alone; correct
   the memory note; defer the rest.

## When picking up

Re-run the numbers first (`uv run ruff check .` and `uv run ruff format --check .`) — the tree may have
drifted further. The fastest concrete win regardless of direction is the 4 F821 + 1 F811 (likely real),
which are independent of the formatting-philosophy decision.
