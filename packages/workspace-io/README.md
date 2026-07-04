# workspace-io

Workspace bootstrap, manifest IO (`.graph-wiki.yaml`), and config resolution for the graph-wiki ecosystem.

## Manifest schema

The workspace manifest lives at `<workspace>/.graph-wiki.yaml` and is read/written
by `workspace_io.manifest.read()` / `write()`. The v2 envelope:

- `version: 2` — required; v1 is rejected with a clear error (D-14).
- `initialized_at: YYYY-MM-DD` — workspace creation date (string on read).
- `plugins:` — list of registered-plugin records (name/version provenance only —
  no per-plugin `roles:` key; roles live at the top level, see below).
- `plugin:` (singular, optional) — top-level routing block with `backend_default`
  and `backend_overrides`. Validated by `manifest.read()`; see `manifest.py` for
  the exact rules.
- `state_gate:` (top-level, optional) — gate that guards `last_updated_commit`
  narrative-provenance stamping. `{enabled: bool, branches: [str, ...]}`,
  defaulting to `{enabled: true, branches: [main]}` when absent. Validated and
  normalized by `manifest.read()`; read via `read_state_gate()`.
- `workflow:` (top-level, optional) — `{commit_strategy: str, model_routing: dict}`.
  `commit_strategy` is one of `per-task` / `at-end` (default `per-task`).
  `model_routing` maps tiers (`mechanical` / `standard` / `frontier`) to a
  model name/alias string. Absent → `{commit_strategy: "per-task", model_routing: {}}`.
- `roles:` (top-level, optional) — flattened per-workspace model-role overrides;
  see below.

### Top-level `roles:` mapping

`roles:` is a top-level mapping of `{role_name: field_dict}` — the
per-workspace override for model-role tiers (e.g. `preflight`, `librarian`).
Roles absent from this mapping fall back to the packaged
`graph_wiki_core/models.toml` defaults per-role (not all-or-nothing); the
resolution lives in `packages/graph-wiki-core/src/graph_wiki_core/roles.py`.

Each role dict may carry these fields:

| Field             | Type | Purpose                                     |
| ----------------- | ---- | -------------------------------------------- |
| `model_id`        | str  | Bedrock model ARN / inference profile       |
| `region`          | str  | AWS region                                  |
| `max_tokens`      | int  | passed to `ChatBedrockConverse`             |
| `max_concurrency` | int  | consumed by subagent runtime / eval harness |
| `backend`         | str  | e.g. `bedrock` / `vercel`                   |

`manifest.read()` validates the field set (unknown fields raise) but does not
otherwise interpret the values — that's `graph_wiki_core.roles`'s job.

Example:

```yaml
version: 2
initialized_at: '2026-05-18'
plugins:
- name: graph-wiki-agent
  installed_version: 0.1.1
  applied_version: 0.1.1
roles:
  preflight:
    model_id: "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    region: "us-east-1"
    max_tokens: 64
    max_concurrency: 1
  librarian:
    model_id: "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    region: "us-east-1"
    max_tokens: 2048
    max_concurrency: 5
```

## Reading roles programmatically

```python
from pathlib import Path
from workspace_io import read_roles

roles = read_roles(Path(".graph-wiki.yaml"))
# -> dict[str, dict]; {} when manifest missing or no roles key
```

`read_roles` is a thin read-only lookup — it does not decide how to merge with
packaged defaults. Callers (e.g. `graph_wiki_core.roles`) do that per-role.

## State gate

The optional top-level `state_gate:` block controls whether a scan/ingest run is
allowed to stamp `last_updated_commit` provenance:

```yaml
state_gate:           # gate that guards last_updated_commit narrative stamping
  enabled: true       # set false to disable the gate entirely (writes always allowed)
  branches:           # branches on which stamping is allowed (clean tree also required)
    - main
    - develop
```

- `enabled` (bool, default `true`) — `false` bypasses both the branch check and
  the clean-tree check; stamping is always allowed.
- `branches` (list of branch names, default `[main]`) — when enabled, stamping is
  allowed iff HEAD is on one of these branches AND the working tree is clean. A
  scalar value (`branches: main`) is coerced to a one-element list.

Read it programmatically:

```python
from pathlib import Path
from workspace_io import read_state_gate

enabled, branches = read_state_gate(Path(".graph-wiki.yaml"))
# -> (True, ["main"]) when the block / manifest is absent
```

Like the `plugin:` block, `state_gate:` is hand-edited — `manifest.write()` does
not emit it, so it survives only because `read()` round-trips disk additively.

---

Ported from `workspace-io` (`/Users/pat/Personal/lattice/packages/workspace-io/`).
See `.planning/phases/11-workspace-io-port-m1/` for the port plan and provenance.
