# S05 Research: Workspace integration and full verification

## Summary

S05 is targeted integration/cleanup research, not novel architecture. S01-S04 already produced the three package surfaces; the remaining work is to remove the obsolete workspace member, delete the old duplicate source/test tree, clean active stale executable guidance, and run root-level verification.

Current repo state still has `agents/graph-wiki-agent/` with 164 entries, including duplicate `src/graph_wiki_agent` code, old tests, `.pytest_cache`, and 56 `.pyc` files. Root `pyproject.toml` still declares `members = ["packages/*", "agents/*"]`, and `uv.lock` still lists `graph-wiki-agent` as a manifest member with `source = { editable = "agents/graph-wiki-agent" }`. This is the main blocker to package-only workspace acceptance.

Active requirements this slice owns/supports:
- Owns final R001 proof: the package split is real in the root workspace and no active old package remains.
- Owns R006 closeout: tests are package-colocated; old agent tests must be removed from the active tree.
- Owns R007: root sync and full test/integration verification.
- Supports already-validated R003/R004/R005/R008 by not regressing `gw`, `graph-wiki-mcp`, runtime shims, and docs guards.

Memory findings matched the plan: `graph_wiki_core` is the shared implementation; `graph_wiki_cli` and `graph_wiki_mcp` are the only presentation namespaces; no `graph_wiki_agent` shims or old script aliases should be reintroduced. A remembered gotcha says MCP tool descriptions are active runtime guidance; S04 already fixed those, but S05 stale scans should keep them in scope.

## Skill Discovery

Installed relevant skills already exist in the environment:
- `uv-package-manager` — directly relevant for workspace membership, lockfile sync, and package-scoped verification.
- `python-testing-patterns` / `test` / `verify-before-complete` — directly relevant for full pytest/integration proof.

No external skill discovery/install is needed for core technologies; this is local `uv` + `pytest` cleanup using established repo patterns.

## Implementation Landscape

### Workspace metadata and lockfile

Files:
- `pyproject.toml`
  - Currently: `[tool.uv.workspace] members = ["packages/*", "agents/*"]`.
  - Needed: package-only workspace, likely `members = ["packages/*"]`.
- `uv.lock`
  - Currently contains `graph-wiki-agent` in `[manifest].members` and an editable package block pointing at `agents/graph-wiki-agent`.
  - Needed: regenerate with `uv sync`/`uv lock` after root member change and agent deletion so no `graph-wiki-agent` package remains in the manifest.
- `agents/graph-wiki-agent/pyproject.toml`
  - Still exists and defines the obsolete `graph-wiki-agent` package with core/CLI/MCP-ish dependencies. Delete with the rest of `agents/`.

First proof should be root workspace/package resolution: after root membership changes and agent directory removal, run `uv sync`. This should rewrite `uv.lock` without `graph-wiki-agent`; if it fails, do not proceed to broad verification until dependency metadata is fixed.

### Obsolete `agents/` tree

Current old tree includes:
- `agents/graph-wiki-agent/src/graph_wiki_agent/` with duplicate core code plus old `cli.py`.
- `agents/graph-wiki-agent/tests/` with 33 remaining test files, mostly duplicated under `packages/graph-wiki-core/tests`; MCP/CLI tests from earlier slices are already deleted in git status.
- Local generated artifacts (`.pytest_cache`, `__pycache__`, `.pyc`) that should disappear with the tree.

Comparison against `packages/graph-wiki-core/src/graph_wiki_core`:
- Old source has 33 `.py` files; new core has 32; only old-only file is `cli.py`.
- 20 files are identical or rename-only after `graph_wiki_agent -> graph_wiki_core`.
- 12 files differ because S01+ changed core implementation/imports; the package tree is authoritative. Do not copy anything from `agents/` back.

Natural task: delete `agents/` completely after confirming package-local tests already cover core/CLI/MCP. This also removes many stale references and generated artifacts.

### Tests and package colocation

Current package-local test layout is in good shape:
- `packages/graph-wiki-core/tests`: 31 files; owns command/prompt/core tests.
- `packages/graph-wiki-cli/tests`: 12 files; owns CLI package, help, docs, and plugin shim tests.
- `packages/graph-wiki-mcp/tests`: 11 files; owns MCP schema/stdio/boundary tests.
- `packages/eval-harness/tests`: 21 files.
- Other library package tests remain under their packages.

Remaining non-package test:
- `tests/test_integration_gate.py` is an intentional repo-level meta-test. It still has an assertion message saying it expected `agents/graph-wiki-agent/tests/integration/*`; update that message to package-era expectations (for example package-local integration tests under `packages/*/tests/integration/*`). The logic already walks all `tests/integration/test_*.py` and currently passes.

Likely useful new/updated boundary test:
- Add or update a repo-level test (could be a new `tests/test_package_split_workspace.py`) that asserts:
  - root workspace members are exactly package-only (`packages/*`, no `agents/*`),
  - `agents/` path does not exist,
  - `uv.lock` manifest/source entries do not mention `graph-wiki-agent` or `agents/graph-wiki-agent`,
  - `graph_wiki_agent` is not importable,
  - `graph-wiki-cli` owns only `gw` and `graph-wiki-mcp` owns `graph-wiki-mcp` (existing package-local boundary tests cover much of this; root test should focus on final integration state).

### Active stale executable guidance

A broad scan of active code/config/docs (excluding historical `.planning` and `.gsd`) found only a small set of true executable-guidance leftovers:
- `packages/workspace-io/src/workspace_io/config.py:106` raises `Run: graph-wiki-agent bootstrap <path>`.
- `packages/workspace-io/tests/test_config.py` asserts the old bootstrap text.
- `packages/wiki-io/src/wiki_io/_workspace.py` docstring says workspace resolution raises a message naming `graph-wiki-agent bootstrap <path>`.
- `packages/wiki-io/tests/test_ports_importable.py` asserts old bootstrap text.

These should become `gw bootstrap <path>` because they are current user-facing recovery instructions, not plugin identity strings.

Stale string requiring classification:
- `packages/wiki-io/src/wiki_io/init_vault.py:214` writes `<!-- generated by graph-wiki-agent scan; ... -->`, and `packages/wiki-io/tests/test_init_vault.py` asserts it. This is provenance/comment text, not an executable command. It does include `graph-wiki-agent scan`, so decide explicitly whether to preserve it as plugin identity provenance or update to `graph-wiki scan`/`gw scan`. Given D004 keeps plugin identity as `graph-wiki-agent`, preserving the generator identity is defensible, but if S05 adds a strict executable regex gate it needs an allowlist/comment or a narrower pattern.

Allowed/should remain:
- `.graph-wiki.yaml` plugin identity strings and workspace-io tests around plugin name `graph-wiki-agent` (D004).
- `model-adapter` role lookup for plugin `graph-wiki-agent` (D004; model roles are read from that manifest identity).
- Graph/wiki fixture content and graph-io test fixture app names where `graph-wiki-agent` is a sample project/entity, unless the planner wants fixture modernization outside active executable scope.
- Negative boundary tests in `packages/graph-wiki-cli/tests/unit/test_cli_boundary.py` and `packages/graph-wiki-mcp/tests/unit/test_mcp_package_boundary.py`.
- Historical `.planning`, `.gsd`, and eval fixture vault snapshots unless test expectations require an update.

### Brand/gate scripts

Files:
- `scripts/check-brand.sh`
  - Scope comments and grep roots still mention/include `agents/`.
  - CHECK 3 searches `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py` for `def init(`. With agents gone this silently no-ops; update it to the current CLI file `packages/graph-wiki-cli/src/graph_wiki_cli/cli.py` so it remains a real guard.
  - Other grep roots that include `agents/` should be changed to package-only scope (`packages/ plugins/ ...`) so the script matches the new workspace shape and does not depend on a missing dir.
- `.brand-grep-allow`
  - Contains `agents/graph-wiki-agent/`; remove or replace as appropriate after script scope changes.

### Project docs/context still stale

`README.md`, `plugins/graph-wiki/README.md`, and `plugins/graph-wiki/CLAUDE.md` had no old executable hits in the focused scan.

`CLAUDE.md` at repo root still contains generated project context from earlier planning with old examples (`uv sync --package graph-wiki-agent`, `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py`). This may be regenerated from GSD project/stack artifacts rather than hand-maintained docs. Treat as lower priority than runtime source/tests, but planner should decide whether S05 updates root GSD project/stack docs or leaves historical preloaded context until a separate project-doc refresh. If a final broad active-reference gate includes `CLAUDE.md`, this will need updating.

### Integration gates

Existing integration tests use the `GRAPH_WIKI_RUN_INTEGRATION=1` gate pattern and the repo-level meta-test currently passes:
- `uv run python -m pytest tests/test_integration_gate.py -q` -> 1 passed, 1 warning.

For S05 closeout, there are two legitimate verification modes:
- Default-safe full suite: `uv run python -m pytest` (integration tests with existing skip gates may skip live Bedrock paths).
- Full integration intent: `GRAPH_WIKI_RUN_INTEGRATION=1 uv run python -m pytest` if AWS/Bedrock credentials and cost acceptance are present. If live credentials are unavailable, record skips/failures as environment-driven, not as planner/executor omission.

## Natural Seams / Suggested Task Breakdown

1. **Package-only workspace cutover**
   - Edit root `pyproject.toml` to `members = ["packages/*"]`.
   - Delete `agents/` entirely.
   - Run `uv sync` to refresh `uv.lock` and prove the workspace resolves without `graph-wiki-agent`.
   - Verify lockfile no longer contains `graph-wiki-agent` manifest/source entries.

2. **Active stale recovery text cleanup**
   - Update `workspace_io.config.resolve()` missing-manifest error from `graph-wiki-agent bootstrap <path>` to `gw bootstrap <path>`.
   - Update `wiki_io._workspace` docstrings and tests in `packages/wiki-io/tests/test_ports_importable.py` and `packages/workspace-io/tests/test_config.py`.
   - Decide and document classification for `generated by graph-wiki-agent scan` provenance comment.

3. **Repo gates and boundary tests**
   - Update `tests/test_integration_gate.py` stale failure message.
   - Update `scripts/check-brand.sh` scopes and CHECK 3 to current `graph_wiki_cli` path.
   - Update `.brand-grep-allow` to remove `agents/graph-wiki-agent/` if no longer needed.
   - Add a final package-split workspace boundary test for root pyproject + lock + no `agents/` + no importable `graph_wiki_agent`.

4. **Verification pass and reference classification**
   - Run targeted package tests first (`graph-wiki-core`, `graph-wiki-cli`, `graph-wiki-mcp`, workspace-io/wiki-io touched tests).
   - Run executable smoke checks (`gw --help`, representative `gw ... --help`, MCP stdio package tests).
   - Run full workspace tests and stale-reference scan.
   - If `GRAPH_WIKI_RUN_INTEGRATION=1` is feasible, run the full integration suite; otherwise capture existing environment-gated skips explicitly.

## First Proof

Highest-risk unblocker: prove `uv` can resolve the workspace with no `agents/` member.

Recommended first proof sequence after edits:

```bash
uv sync
python - <<'PY'
from pathlib import Path
lock = Path('uv.lock').read_text()
root = Path('pyproject.toml').read_text()
assert 'agents/*' not in root
assert not Path('agents').exists()
assert 'name = "graph-wiki-agent"' not in lock
assert 'agents/graph-wiki-agent' not in lock
print('package-only workspace metadata OK')
PY
```

Do this before broad tests; otherwise full pytest may be passing against the obsolete editable package still present in the lock/workspace.

## Verification Commands

Targeted after cleanup:

```bash
uv sync
uv run python -m pytest tests/test_integration_gate.py -q
uv run python -m pytest packages/workspace-io/tests/test_config.py packages/wiki-io/tests/test_ports_importable.py -q
uv run --package graph-wiki-core python -m pytest packages/graph-wiki-core/tests
uv run --package graph-wiki-cli python -m pytest packages/graph-wiki-cli/tests
uv run --package graph-wiki-mcp python -m pytest packages/graph-wiki-mcp/tests
NO_COLOR=1 TERM=dumb COLUMNS=200 uv run --package graph-wiki-cli gw --help
NO_COLOR=1 TERM=dumb COLUMNS=200 uv run --package graph-wiki-cli gw query --help
```

Full closeout:

```bash
uv run python -m pytest
# If environment/cost gates are satisfied:
GRAPH_WIKI_RUN_INTEGRATION=1 uv run python -m pytest
```

Static stale checks to include in closeout evidence:

```bash
python - <<'PY'
from pathlib import Path
assert not Path('agents').exists()
assert 'agents/*' not in Path('pyproject.toml').read_text()
assert 'agents/graph-wiki-agent' not in Path('uv.lock').read_text()
assert 'name = "graph-wiki-agent"' not in Path('uv.lock').read_text()
print('no old workspace package')
PY

python - <<'PY'
from pathlib import Path
patterns = ['import graph_wiki_agent', 'from graph_wiki_agent', 'graph_wiki_agent.']
for root in ['packages', 'tests', 'plugins', 'scripts']:
    p = Path(root)
    if not p.exists():
        continue
    for f in p.rglob('*.py'):
        if any(x in f.parts for x in ['__pycache__', '.pytest_cache', '.hypothesis']):
            continue
        text = f.read_text(errors='ignore')
        bad = [pat for pat in patterns if pat in text]
        if bad and 'test_cli_boundary.py' not in str(f) and 'test_mcp_package_boundary.py' not in str(f):
            raise AssertionError((str(f), bad))
print('no active old import namespace')
PY
```

## Risks / Watch-outs

- Do not reintroduce a compatibility shim to make old tests pass. D003 explicitly bans `graph_wiki_agent` imports and `graph-wiki-agent` console aliases.
- `graph-wiki-agent` plugin identity is still valid in `.graph-wiki.yaml`, model-adapter role lookup, and workspace manifest tests. Do not globally replace every string.
- S04 learned that MCP tool descriptions are active runtime guidance; keep package MCP server text in stale executable scans.
- Root `CLAUDE.md` still has old generated project context; decide whether it is in-scope for S05 final stale reference gate. Current user-facing README/plugin docs are already clean.
- There are many historical `.planning`/`.gsd` stale references. Do not churn historical artifacts unless a test or active runtime surface requires it.
- Full integration with `GRAPH_WIKI_RUN_INTEGRATION=1` may require AWS Bedrock credentials and incur cost; default skipped integration tests should be reported as existing environment gates if credentials are absent.
