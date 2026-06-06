# workspace-io

Workspace bootstrap, manifest IO (`.graph-wiki.yaml`), and config resolution for the graph-wiki ecosystem.

## Manifest schema

The workspace manifest lives at `<workspace>/.graph-wiki.yaml` and is read/written
by `workspace_io.manifest.read()` / `write()`. The v2 envelope:

- `version: 2` — required; v1 is rejected with a clear error (D-14).
- `initialized_at: YYYY-MM-DD` — workspace creation date (string on read).
- `plugins:` — list of registered-plugin records; see below.
- `plugin:` (singular, optional) — top-level routing block with `backend_default`
  and `backend_overrides`. Validated by `manifest.read()`; see `manifest.py` for
  the exact rules.
- `state_gate:` (top-level, optional) — gate that guards `last_updated_commit`
  narrative-provenance stamping. `{enabled: bool, branches: [str, ...]}`,
  defaulting to `{enabled: true, branches: [main]}` when absent. Validated and
  normalized by `manifest.read()`; read via `read_state_gate()`.

### Per-plugin `roles:` block

Each entry in `plugins:` may carry a nested `roles:` list. This is the
per-workspace override for the plugin's model-role tiers (e.g. `preflight`,
`librarian`). Roles absent from this list fall back to the packaged
`model_adapter/models.toml` defaults per-role (not all-or-nothing); the
resolution lives in `packages/model-adapter/`.

Each role record has exactly the four fields the loader consumes:

| Field             | Type | Purpose                                     |
| ----------------- | ---- | ------------------------------------------- |
| `name`            | str  | role identifier (e.g. `preflight`)          |
| `model_id`        | str  | Bedrock model ARN / inference profile       |
| `region`          | str  | AWS region                                  |
| `max_tokens`      | int  | passed to `ChatBedrockConverse`             |
| `max_concurrency` | int  | consumed by subagent runtime / eval harness |

Adding fields here is a code change in `model_adapter.loader` — the IO layer
does not validate or default per-role fields.

Example:

```yaml
version: 2
initialized_at: '2026-05-18'
plugins:
- name: graph-wiki-agent
  installed_version: 0.1.1
  applied_version: 0.1.1
  roles:
  - name: preflight
    model_id: "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    region: "us-east-1"
    max_tokens: 64
    max_concurrency: 1
  - name: librarian
    model_id: "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    region: "us-east-1"
    max_tokens: 2048
    max_concurrency: 5
```

## Reading roles programmatically

```python
from pathlib import Path
from workspace_io import read_roles

roles = read_roles("graph-wiki-agent", Path(".graph-wiki.yaml"))
# -> list[dict]; [] when manifest missing, plugin absent, or no roles key
```

`read_roles` is a thin read-only lookup — it does not validate role-dict field
shape. Callers (e.g. `model_adapter.loader`) decide how to merge with packaged
defaults on a per-role basis.

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
