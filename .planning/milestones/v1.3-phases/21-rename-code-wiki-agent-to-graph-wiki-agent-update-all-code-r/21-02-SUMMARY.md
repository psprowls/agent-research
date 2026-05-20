---
phase: 21-rename-code-wiki-agent-to-graph-wiki-agent-update-all-code-r
plan: 02
subsystem: agent-pyproject-rename
tags: [rename, pyproject, uv-workspace, layer-2]
requires:
  - 21-01 (directory + module dirs renamed; agent pyproject still says name = "code-wiki-agent")
provides:
  - agents/graph-wiki-agent/pyproject.toml name + console scripts switched to graph-wiki-agent
  - eval-harness workspace dep + [tool.uv.sources] key rebound to graph-wiki-agent (B2 hard-blocker fix)
  - uv.lock regenerated; uv sync green for the renamed workspace member
affects:
  - layer-3 (import sweep) is now unblocked — uv sync resolves, but pytest will still fail until graph_wiki_agent / graph_wiki_mcp sources are swept off `from code_wiki_agent...` imports
tech-stack:
  added: []
  patterns:
    - pyproject-manifest layer-2 gate (uv sync only, per D-11 relaxation)
    - atomic rebrand across consumer pyprojects when a workspace member's `name` flips
key-files:
  modified:
    - agents/graph-wiki-agent/pyproject.toml
    - packages/eval-harness/pyproject.toml
    - packages/model-adapter/pyproject.toml
    - packages/subagent-runtime/pyproject.toml
    - packages/vault-io/pyproject.toml
    - uv.lock
decisions:
  - "CONTEXT 'Reusable Assets' bullet that other workspace pyprojects do NOT need touching was WRONG; eval-harness carried both a `dependencies = [..., 'code-wiki-agent', ...]` entry and a `[tool.uv.sources] code-wiki-agent = { workspace = true }` key — both rewritten in this commit (B2 fix)."
  - "Cosmetic `description` rebrands in model-adapter / subagent-runtime / vault-io / eval-harness rolled into the same atomic commit per D-06 staged-commits rule (the pyproject manifest is the unit of change)."
  - "Layer-2 gate is `uv sync` only per D-11 relaxation. `uv run pytest` deliberately not run here — script targets point at modules whose imports still say `from code_wiki_agent...`; layer 3 sweeps those."
metrics:
  duration: ~5 min
  completed: 2026-05-19
---

# Phase 21 Plan 02: Rename agent pyproject + consumer pyprojects → graph-wiki-agent (atomic)

D-09 layer 2 of the code-wiki → graph-wiki rename. Flips the `name` and console-script keys/targets in `agents/graph-wiki-agent/pyproject.toml`, rebinds eval-harness's workspace dep + `[tool.uv.sources]` key, sweeps cosmetic `description` strings in sibling pyprojects, regenerates `uv.lock`, and lands the whole thing as a single atomic commit.

## Commit

- **SHA:** `2abd539`
- **Subject:** `refactor(21): rename package name + console scripts + consumer pyproject deps to graph-wiki-agent`

## `git show --stat HEAD`

```
commit 2abd539dc64dfb6baaa675e49ec528e2cfad3df4
Author: Patrick Sprowls <psprowls@gmail.com>
Date:   Tue May 19 20:44:53 2026 -0600

    refactor(21): rename package name + console scripts + consumer pyproject deps to graph-wiki-agent

 agents/graph-wiki-agent/pyproject.toml   |  6 +--
 packages/eval-harness/pyproject.toml     |  6 +--
 packages/model-adapter/pyproject.toml    |  2 +-
 packages/subagent-runtime/pyproject.toml |  2 +-
 packages/vault-io/pyproject.toml         |  2 +-
 uv.lock                                  | 64 ++++++++++++++++----------------
 6 files changed, 41 insertions(+), 41 deletions(-)
```

Exactly the 6 files in `files_modified` — no collateral.

## `uv sync` (layer-2 gate)

```
Resolved 127 packages in 4ms
Checked 125 packages in 18ms
```

Exit code 0. Workspace install is coherent with the renamed agent member.

## Pre-edit grep survey

```
packages/subagent-runtime/pyproject.toml:4:description = "Async fan-out primitive for code-wiki-agent subagent dispatch"
packages/model-adapter/pyproject.toml:4:description = "AWS Bedrock model loader for code-wiki-agent"
packages/eval-harness/pyproject.toml:4:description = "Deterministic eval checks, pricing, and sweep runner for code-wiki-agent"
packages/eval-harness/pyproject.toml:11:    "code-wiki-agent",
packages/eval-harness/pyproject.toml:21:code-wiki-agent = { workspace = true }
packages/vault-io/pyproject.toml:4:description = "Vault IO for code-wiki-agent"
agents/graph-wiki-agent/pyproject.toml:2:name = "code-wiki-agent"
agents/graph-wiki-agent/pyproject.toml:19:code-wiki-agent = "code_wiki_agent.cli:app"
agents/graph-wiki-agent/pyproject.toml:20:code-wiki-mcp   = "code_wiki_mcp.server:main"
```

Matches the planner survey exactly. No additional pyproject hits surfaced.

## Post-commit residual scan

```bash
grep -lE '\bcode-wiki-agent\b|\bcode_wiki_agent\b|\bcode-wiki-mcp\b|\bcode_wiki_mcp\b' \
  packages/*/pyproject.toml agents/graph-wiki-agent/pyproject.toml pyproject.toml
```

Empty — zero `code-wiki-*` tokens remain in any `pyproject.toml`.

## B2 callout (CONTEXT correction)

The CONTEXT.md "Reusable Assets" bullet claimed:

> Other workspace members (`vault-io`, `model-adapter`, etc.) do NOT need their pyproject.toml touched.

That claim was **WRONG**. Pre-edit survey confirmed that `packages/eval-harness/pyproject.toml` carried both:

- `dependencies = [..., "code-wiki-agent", ...]`  (a name-resolved dep on the renamed workspace member)
- `[tool.uv.sources] code-wiki-agent = { workspace = true }`  (the workspace-source key)

Both MUST be rewritten in the same atomic commit, otherwise `uv sync` errors with `Package 'code-wiki-agent' is not present in the workspace` because the workspace member is now called `graph-wiki-agent`. Plan 21-02 rewrote both in this commit (the B2 fix).

The sibling packages (`model-adapter`, `subagent-runtime`, `vault-io`, `eval-harness`) all carried *cosmetic* `description` strings mentioning `code-wiki-agent` — those were also rebranded in the same commit for atomicity. Per D-06's staged-commits rule, the pyproject manifest is the unit of change, so non-functional description text rides along with the name flip rather than getting deferred.

## Pytest deferred (D-11 relaxation)

`uv run pytest` was deliberately **not run** as a gate here. The renamed console scripts (`graph-wiki-agent`, `graph-wiki-mcp`) point at module entry points (`graph_wiki_agent.cli:app`, `graph_wiki_mcp.server:main`) whose source files exist (layer 1 renamed the directories) but whose internal `import` statements still say `from code_wiki_agent...` / `from code_wiki_mcp...`. Running pytest at this layer would surface known-broken imports rather than real regressions. Per D-11 "or equivalent scope", `uv sync` is the layer-2 gate; pytest gates resume at layer 3.

## Pointer to next plan

**Plan 21-03** (next wave): sweep `from code_wiki_agent...` → `from graph_wiki_agent...` (and `code_wiki_mcp` → `graph_wiki_mcp`) inside the agent package's `src/` and `tests/` trees. This restores pytest-green and lets the console scripts actually launch.

## Deviations from Plan

None — plan executed exactly as written. The PIPESTATUS idiom from the plan's verify block returned empty in the harness's bash invocation chain due to subshell semantics; switched to direct `$?` capture which confirmed `uv sync` exit code 0. No behavioral deviation.

## Self-Check: PASSED

- `agents/graph-wiki-agent/pyproject.toml` — FOUND (modified)
- `packages/eval-harness/pyproject.toml` — FOUND (modified)
- `packages/model-adapter/pyproject.toml` — FOUND (modified)
- `packages/subagent-runtime/pyproject.toml` — FOUND (modified)
- `packages/vault-io/pyproject.toml` — FOUND (modified)
- `uv.lock` — FOUND (modified)
- Commit `2abd539` — FOUND in `git log`
- `uv sync` — exit 0
- Residual `code-wiki-*` in any pyproject — none
