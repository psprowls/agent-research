---
command: ingest
upstream_source: plugins/lattice-wiki/commands/ingest.md
port_verdict: rename
---

# /graph-wiki:ingest — Port Spec

## Shell-out contract

- **Invocation:** `uv run --project "$DEEP_AGENTS_ROOT" python3 "${CLAUDE_PLUGIN_ROOT}/skills/graph-wiki/scripts/ingest_source.py" $ARGUMENTS`
- **Target module (claude backend):** `vault_io.ingest_source.main`
- **Target subprocess (bedrock backend):** `code-wiki-agent ingest source <args>`
  - NOTE: explicitly `ingest source`, NOT `ingest work-item` — the work-item ingest subcommand is absent from graph-wiki v1.2 per C-01.
- **Args pass-through (source-ingest flags only, mapped 1:1 from upstream `ingest_source.py`):**
  - `--source <path>` (required) — path to the source file or folder to ingest
  - `--json` — emit machine-readable JSON brief instead of human-readable output
  - `--pkg-dir <path>` — vault package directory; when given, ensures api/patterns/context sub-pages exist
  - `--pkg-title <title>` — package display title for sub-page template substitution
  - No `--work-item` flag exists (work-layer dropped; see C-01 below).
- **Pre-step:** NONE — `ingest_source.py` handles workspace discovery internally via `vault_io._workspace.resolve_wiki_and_repo`.
- **Scope note:** Source-ingest only. Upstream's work-item ingest branch (`ingest_work_item.py`) is DROPPED per C-01 (work-layer out of v1.2 scope). The shim does not import or reference `vault_io.ingest_work_item`.

Reference SHELL-OUT-PATTERN.md §SO-01 for the invocation shape and §SO-02 for the shim boilerplate.

## Prose-preservation map

Section-by-section verdict for the upstream `plugins/lattice-wiki/commands/ingest.md` body:

| Section | Verdict |
|---------|---------|
| Frontmatter (`name`, `description`) | Verbatim except namespace rename: `lattice-wiki` → `graph-wiki` in the description string. |
| `# /lattice-wiki:ingest` (H1) | Rename: `# /graph-wiki:ingest`. Body prose verbatim. |
| `## Usage` | Verbatim except namespace rename in the command examples (`/lattice-wiki:ingest` → `/graph-wiki:ingest`). |
| `## Source types` | Verbatim — table rows and prose unchanged. Source types are a vault convention, not a lattice brand. |
| `## What happens` | Verbatim except step 1 renames the script reference: `scripts/ingest_source.py` stays; upstream module reference changes from `lattice_wiki_core.ingest_source` to `vault_io.ingest_source`. No work-item branch exists in this section of the upstream command file. |
| `## Sub-agent` | Verbatim except rename: `agents/ingestor.md` stays; prose inside the agent file rebranded lattice-wiki → graph-wiki (Phase 14 task). |
| `## Rules` | Verbatim except namespace rename in prose (`/lattice-wiki:lint` → `/graph-wiki:lint`, `lattice-workspace` → `workspace_io`). No work-item rules exist in this section of the upstream command file. |
| `## Skill Reference` | Rename: `lattice-wiki/SKILL.md` → `graph-wiki/SKILL.md`; `lattice-wiki/references/ingest-workflow.md` → `graph-wiki/references/ingest-workflow.md`. |

**Work-item ingest section:** Upstream `commands/ingest.md` does not have a dedicated H2 section for work-item ingest (the work-item flow is handled by the separate `ingest_work_item.py` script, not documented here). The entire `ingest_work_item.py` script is simply absent from graph-wiki — captured by its omission from `plugins/graph-wiki/skills/graph-wiki/scripts/`. DROP verdict applies at the script level, not the command-doc level.

## Agent / skill rename map

| Upstream path | graph-wiki path | Action |
|---------------|-----------------|--------|
| `agents/ingestor.md` | `agents/ingestor.md` | Name stays. Namespace prose rebranded (lattice-wiki → graph-wiki) inside the file. |
| `skills/lattice-wiki/SKILL.md` | `skills/graph-wiki/SKILL.md` | Rename directory + namespace rebrand in prose. |
| `skills/lattice-wiki/references/ingest-workflow.md` | `skills/graph-wiki/references/ingest-workflow.md` | Rename directory + namespace rebrand in prose. |
| `skills/lattice-wiki/scripts/ingest_source.py` | `skills/graph-wiki/scripts/ingest_source.py` | Rename directory; rewrite imports (`lattice_wiki_core.ingest_source` → `vault_io.ingest_source`); bedrock branch shells to `code-wiki-agent ingest source`. |
| `skills/lattice-wiki/scripts/ingest_work_item.py` | *(not ported)* | DROP — work-layer out of v1.2 per C-01. File does not appear under `plugins/graph-wiki/skills/graph-wiki/scripts/`. |

## Reshape notes

Verdict is `rename` because the source-ingest behavior is preserved byte-for-byte (modulo namespace strings). The ingestor flow — read source → discuss → confirm → write summary → update pages → propose ADR → flag contradictions → update index → append log — is unchanged.

The companion work-item ingest path (`ingest_work_item.py`) is `drop`-verdict per C-01 and does not ship in graph-wiki. This is captured by:
1. Absence of the `ingest_work_item.py` script under `plugins/graph-wiki/skills/graph-wiki/scripts/`.
2. The `code-wiki-agent ingest source` (not `ingest work-item`) target in the bedrock branch.
3. The prose omission above.

C-01 decision: "6 commands ported, 3 dropped — total: 6 in `plugins/graph-wiki/commands/`." The work-layer is explicitly out of v1.2 scope per PROJECT.md ("work/ subsystem port — GSD covers work-item lifecycle").

## Verification gate

**Positive test:** Run `/graph-wiki:ingest raw/specs/some-spec.md` (or equivalent path) against a test vault in a deep-agents-backed workspace. The resulting source summary page diff against an upstream `/lattice-wiki:ingest <same-file>` baseline should match modulo brand strings (`lattice` → `graph`, `lattice-wiki` → `graph-wiki`, module references).

**Negative test (work-item absent):** Confirm that no `ingest_work_item.py` script exists under `plugins/graph-wiki/skills/graph-wiki/scripts/`. Any attempt to invoke `code-wiki-agent ingest work-item` from the bedrock branch should either error cleanly ("not supported in graph-wiki v1.2") or be absent from the CLI surface — in either case, no silent partial execution.

**Smoke check:** `uv run --project "$DEEP_AGENTS_ROOT" python3 "<plugin>/skills/graph-wiki/scripts/ingest_source.py" --source raw/specs/test.md` exits 0 or produces a parseable brief JSON. No `ModuleNotFoundError` for `vault_io`.
