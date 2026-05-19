# Phase 15: Wiki Self-Update — Pattern Map

**Mapped:** 2026-05-18
**Files analyzed:** 2 new repo files (no `packages/` or `agents/` source changes)
**Analogs found:** 2 / 2

---

## Scope reminder (from 15-CONTEXT.md)

Phase 15 is content-only. It mutates external state (the wiki vault at `~/Personal/wiki/deep-agents/`) by driving the existing `code-wiki-agent` CLI; it does **not** edit `packages/` or `agents/` source code. The only repo files touched are:

1. `models-claude.toml` — new config at repo root (sibling of `models-qwen.toml`).
2. `.planning/phases/15-wiki-self-update/15-VERIFICATION.md` — new phase verification doc.

A third repo file (`wiki-config-claude.toml` or equivalent one-off pointing `models_path` at `models-claude.toml`) **may** be needed depending on how the executor wires the `--config` CLI flag (see Shared Pattern §CLI override wiring below). It is in the "no analog needed" bucket because it is mechanically identical to the existing `wiki-config.toml` — two lines, a `models_path` and a `vault_path`.

The remaining work (`code-wiki-agent scan`, `code-wiki-agent ingest source`, `code-wiki-agent query`, vault spot-check) is **CLI invocation against the existing CLI surface**, not file authoring. No pattern is needed for invocation; the executor reads `cli.py` argument signatures during scout.

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `models-claude.toml` (repo root, new) | config (role-overrides profile) | static TOML, read at CLI startup via `model_adapter.loader.set_models_path` | `models-qwen.toml` (repo root) | **exact** — identical TOML schema; only the per-role `model_id` values change |
| `.planning/phases/15-wiki-self-update/15-VERIFICATION.md` (new) | docs (phase verification artifact) | static markdown; transcript-in-fenced-block | `.planning/phases/14-plugin-port-m3b/14-VERIFICATION.md` | **exact** — same role (per-phase SC smoke artifact), same data flow (frontmatter + transcript fenced block + result narration) |

---

## Pattern Assignments

### `models-claude.toml` (config, static TOML)

**Analog:** `/Users/pat/Personal/deep-agents/models-qwen.toml`

**Schema is fixed.** Every TOML table is `[roles.<role_name>]` with exactly four keys: `model_id`, `region`, `max_tokens`, `max_concurrency`. The full role set is `haiku`, `sonnet`, `librarian`, `scanner`, `linter`, `ingestor`, `code_reader`, `synthesizer`, `judge_a`, `judge_b` (10 tables total — `model_adapter.loader` reads each one by role-name key). Match the analog's order and key spacing.

**Header pattern** (`models-qwen.toml:1-3`) — provenance comment block at top of file:

```toml
# Model role overrides — Qwen fan-out configuration
# Fan-out roles (scanner, linter, ingestor): Qwen3 32B (on-demand, no us. prefix)
# Reasoning roles (librarian, synthesizer): Qwen3 Coder 480B A35B
```

`models-claude.toml` must open with an equivalent 2-3 line header naming the profile and listing the role-tier split. Per CONTEXT §code_context "Provenance comments on new top-level configs", suggested header:

```toml
# Model role overrides — Claude (Phase 15 wiki self-update profile)
# Fan-out roles (scanner, linter, ingestor, code_reader): Claude Haiku 4.5
# Reasoning roles (librarian, synthesizer): Claude Sonnet 4.6
# Judge slots (judge_a, judge_b): preserved verbatim from models-qwen.toml
```

**Per-role table shape** (`models-qwen.toml:5-9`) — every role table is exactly four lines, aligned `=`:

```toml
[roles.haiku]
model_id        = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
region          = "us-east-1"
max_tokens      = 1024
max_concurrency = 10
```

**Role-by-role assignment for `models-claude.toml`** (derived from CONTEXT D-02 + `models-qwen.toml` line-by-line):

| Role | Source line(s) | `model_id` in new file | `region` / `max_tokens` / `max_concurrency` |
|------|----------------|------------------------|----------------------------------------------|
| `roles.haiku` | qwen.toml:5-9 | `us.anthropic.claude-haiku-4-5-20251001-v1:0` (already Claude in Qwen file — copy verbatim) | `us-east-1` / `1024` / `10` |
| `roles.sonnet` | qwen.toml:11-15 | `us.anthropic.claude-sonnet-4-6` (already Claude — copy verbatim) | `us-east-1` / `4096` / `3` |
| `roles.librarian` | qwen.toml:17-21 | **change** `qwen.qwen3-next-80b-a3b` → `us.anthropic.claude-sonnet-4-6` | preserve `us-east-1` / `2048` / `2` unless executor finds a Claude-specific reason (D-03 Discretion) |
| `roles.scanner` | qwen.toml:23-27 | **change** `qwen.qwen3-32b-v1:0` → `us.anthropic.claude-haiku-4-5-20251001-v1:0` | preserve `us-east-1` / `500` / `10` |
| `roles.linter` | qwen.toml:29-33 | **change** `qwen.qwen3-32b-v1:0` → `us.anthropic.claude-haiku-4-5-20251001-v1:0` | preserve `us-east-1` / `3000` / `10` |
| `roles.ingestor` | qwen.toml:35-39 | **change** `qwen.qwen3-32b-v1:0` → `us.anthropic.claude-haiku-4-5-20251001-v1:0` | preserve `us-east-1` / `2048` / `5` |
| `roles.code_reader` | qwen.toml:41-45 | **change** `qwen.qwen3-32b-v1:0` → `us.anthropic.claude-haiku-4-5-20251001-v1:0` | preserve `us-east-1` / `2048` / `3` |
| `roles.synthesizer` | qwen.toml:47-51 | **change** `qwen.qwen3-next-80b-a3b` → `us.anthropic.claude-sonnet-4-6` | preserve `us-east-1` / `4096` / `1` |
| `roles.judge_a` | qwen.toml:53-57 | **verbatim copy** (`us.anthropic.claude-sonnet-4-6`) | verbatim (D-03 explicit: judge rows preserved) |
| `roles.judge_b` | qwen.toml:59-63 | **verbatim copy** (`us.amazon.nova-pro-v1:0`) | verbatim (D-03 explicit: judge rows preserved) |

**Validation pattern:** there is no schema validator — TOML is loaded raw and indexed by role-name string in `packages/model-adapter/src/model_adapter/loader.py:38-39` (`tomllib.load(f)["roles"][role_name]`). The only correctness gate is "does every role used by a command appear as a `[roles.<name>]` table?" — copying the analog's full 10-role set guarantees this.

**Error handling pattern:** none in the config file itself. `load_role_config` raises `KeyError` if a role table is missing; `model_adapter.make_llm` raises `BedrockAccessDenied` on cred/permission failures at runtime. These are upstream — the config file just needs to be syntactically valid TOML.

**Test analog:** none. `models-qwen.toml` ships uncovered by tests (it is consumed live by the CLI). Phase 15 follows suit; SC#1/#2/#3 are the only validation.

---

### `15-VERIFICATION.md` (docs, transcript artifact)

**Analog:** `/Users/pat/Personal/deep-agents/.planning/phases/14-plugin-port-m3b/14-VERIFICATION.md`

**Frontmatter pattern** (`14-VERIFICATION.md:1-7`) — fenced YAML frontmatter at top of file:

```markdown
---
phase: 14-plugin-port-m3b
verified: 2026-05-19T02:15:00Z
status: passed
score: SC#4 smoke captured
overrides_applied: 0
---
```

`15-VERIFICATION.md` must follow the same shape. Substitute `phase: 15-wiki-self-update`, `verified:` with the actual ISO-8601 timestamp at write time, `status: passed` (or `failed` / `partial` honestly), and `score:` naming what was captured (e.g., `score: SC#1+#2+#3 captured`).

**Section ordering** (`14-VERIFICATION.md`):

1. `# Phase N: <name> — <SC> Verification` H1
2. `**Phase Goal (...):**` one-paragraph restatement of the SCs being verified
3. `**Verified:** <date>` / `**Status:** ...` / `**Vault used:** <abs path>` short metadata block
4. `## Deviation from spec` (optional — only if any) — explain any departure from the prescribed task list
5. `## Smoke transcript` — prose intro + fenced transcript block (use four-backtick fences ` ```` ` because the transcript itself contains triple-backtick code blocks, see `14-VERIFICATION.md:31` and `14-VERIFICATION.md:104` for the opening/closing fences)
6. `## Result` — one-paragraph narration of which SCs passed and which acceptance tokens are present in the transcript

**Transcript fenced-block pattern** (`14-VERIFICATION.md:31-104`) — the transcript itself is wrapped in **four-backtick** fences (not three) because the synthesized answer inside it uses triple-backtick code blocks for Python imports and citations. Phase 15 transcript will likewise contain code blocks (citations and possibly TOML excerpts), so use the same four-backtick fence convention:

````markdown
## Smoke transcript

<prose intro — 1-2 sentences naming what was invoked and what was captured>

````
User: code-wiki-agent query "what is workspace-io?"
... full transcript verbatim ...
````
````

**Per-SC mapping for Phase 15** (Phase 14 has only SC#4; Phase 15 has SC#1, SC#2, SC#3 per ROADMAP Phase 15 — all three need evidence in this single doc):

- **SC#1** — scan-log entries showing new package names, no `lattice` artifacts. Capture as a fenced block inside the transcript section showing the relevant `scan-log.md` (or equivalent log) entries appended by the Phase 15 scan run. Per D-07: only the newly-appended entries need to be free of `lattice`; pre-existing historical lines may contain `lattice` and are out of scope.
- **SC#2** — `workspace-io` package page spot-check. Capture as a sub-section recording (a) the absolute path of the page in `~/Personal/wiki/deep-agents/packages/workspace-io/`, (b) confirmation that frontmatter parses, (c) 2-3 key claims excerpted from the body, (d) at least one `[[wikilink]]` and the existence of its target. Per D-08 minimum bar.
- **SC#3** — `code-wiki-agent query "what is workspace-io?"` full transcript. Capture in a four-backtick fence following the same shape as `14-VERIFICATION.md:31-104` — user question, fan-out evidence (Read/Grep traces from the librarian subagent), synthesized answer with `[[wikilinks]]` and `code-path:line` citations.

**Result section pattern** (`14-VERIFICATION.md:106-110`):

```markdown
## Result

SC#N satisfied. <one-paragraph narration of what passed and which acceptance tokens are literally present in the transcript above>.

<closing line, e.g.: "Smoke passed — transcript captured. <REQ-ID> satisfied. Phase N closes.">
```

Phase 15 closer should read: `BRAND-03 satisfied. Phase 15 closes.`

**Optional Deviation-from-spec section** (`14-VERIFICATION.md:18-25`) — Phase 14 used this to explain that it smoked against the in-repo dogfood vault instead of `~/Personal/wiki/deep-agents`. Phase 15's spec IS `~/Personal/wiki/deep-agents`, so a Deviation section is only needed if the executor cannot run against that vault for some reason; otherwise omit.

**Error handling pattern:** none — this is a static doc. If the smoke fails, capture the failure transcript honestly with `status: failed` in frontmatter rather than fabricating a pass.

---

## Shared Patterns

### CLI override wiring (applies to all three scan/ingest/query invocations)

**Source:** `agents/code-wiki-agent/src/code_wiki_agent/cli.py:35-45`

```python
@app.callback()
def main_callback(
    config: Optional[Path] = typer.Option(None, "--config", help="Path to TOML config file"),
) -> None:
    """code-wiki-agent: AWS Bedrock-powered wiki maintenance."""
    if config is not None:
        import code_wiki_agent.config as _cfg_module
        from model_adapter.loader import set_models_path

        _cfg_module._active_config = _cfg_module.load_config(config)
        set_models_path(_cfg_module._active_config.models_path)
```

**Apply to:** every CLI invocation in the Phase 15 plan (scan, ingest source, query).

**Mechanics:** the CLI flag is `--config` (top-level callback option, applies before any subcommand), NOT `--models-config`. It accepts a `WikiConfig`-shaped TOML — same shape as `wiki-config.toml` (two-line file with `models_path` and `vault_path` keys, per `/Users/pat/Personal/deep-agents/wiki-config.toml`). The callback's `set_models_path()` call routes all subsequent model-role loads to the file pointed at by `models_path`.

**Two viable invocation shapes** (executor picks one during scout — both are confirmed-supported by the existing CLI):

1. **Sibling override-config file** (recommended; matches existing default's mechanism):
   - Create a one-off `wiki-config-claude.toml` at repo root containing exactly:
     ```toml
     models_path = "/Users/pat/Personal/deep-agents/models-claude.toml"
     vault_path  = "/Users/pat/Personal/wiki/deep-agents"
     ```
   - Invoke `code-wiki-agent --config /Users/pat/Personal/deep-agents/wiki-config-claude.toml scan ...` (and `... ingest source ...` and `... query "..."`).
   - Mirrors the existing `wiki-config.toml` pattern exactly; reusable for any future Claude-profile runs.

2. **In-place flag-only** (no second config file): not directly supported — `--config` requires a full WikiConfig TOML, not a bare `models_path`. Skip this option unless CLI is extended in a future phase.

CONTEXT §Claude's Discretion confirms executor reads `code-wiki-agent --help` or the relevant CLI source during scout to lock the exact flag — the scout step will reach line 37 of `cli.py` and confirm `--config`.

### Provenance comment header (applies to `models-claude.toml`)

**Source:** `models-qwen.toml:1-3`

```toml
# Model role overrides — Qwen fan-out configuration
# Fan-out roles (scanner, linter, ingestor): Qwen3 32B (on-demand, no us. prefix)
# Reasoning roles (librarian, synthesizer): Qwen3 Coder 480B A35B
```

**Apply to:** the new `models-claude.toml`, and to the optional `wiki-config-claude.toml` if it is committed (a one-line `# Phase 15 wiki self-update — Claude override profile` header suffices for the latter).

### Phase artifact frontmatter (applies to `15-VERIFICATION.md`)

**Source:** `14-VERIFICATION.md:1-7`

5-field YAML frontmatter: `phase`, `verified` (ISO-8601 UTC), `status` (`passed` / `partial` / `failed`), `score` (free-text SC summary), `overrides_applied` (integer, `0` when no human overrides were applied to the executor's smoke run).

---

## No Analog Found

None. Both new files have exact analogs in the repo.

**Worth noting:** the optional `wiki-config-claude.toml` (only created if the executor chooses invocation shape #1 above) has an exact analog at `/Users/pat/Personal/deep-agents/wiki-config.toml:1-2` — a two-line TOML with `models_path` and `vault_path`. No separate pattern entry is justified.

---

## External vault mutations (not repo files — for planner orientation only)

The bulk of Phase 15's "output" is changes in `~/Personal/wiki/deep-agents/` driven by the `code-wiki-agent` CLI. These are **not** in scope for pattern extraction (no repo source code is generating them in this phase — the existing CLI does), but the planner should know to orchestrate them in this order per CONTEXT D-05:

1. **Scan** appends to `~/Personal/wiki/deep-agents/scan-log.md` (or equivalent), creates `~/Personal/wiki/deep-agents/packages/workspace-io/` page set, creates `~/Personal/wiki/deep-agents/packages/prompt-sources/` page set, refreshes the four existing package pages.
2. **Ingest** updates `~/Personal/wiki/deep-agents/sources/<OTel summary>.md` from `~/Personal/wiki/raw/OTel — Story of observability.md`.
3. **Query** is read-only — no vault mutation; produces transcript captured into `15-VERIFICATION.md`.
4. **Spot-check** is read-only — produces narration captured into `15-VERIFICATION.md`.

The wiki vault has its own git repo (per CONTEXT §code_context Integration Points); any commits there are separate from this repo's commit chain and are not coordinated by the GSD plan.

---

## Metadata

**Analog search scope:**
- Repo root TOML configs (`models-qwen.toml`, `wiki-config.toml`).
- `.planning/phases/14-plugin-port-m3b/14-VERIFICATION.md` (most recent phase verification doc; structure matches what Phase 15 needs).
- `agents/code-wiki-agent/src/code_wiki_agent/cli.py` (read-only, to confirm `--config` flag wiring — no source change in Phase 15).
- `packages/model-adapter/src/model_adapter/loader.py:27-39` (read-only, to confirm `set_models_path` mechanics).
- `agents/code-wiki-agent/src/code_wiki_agent/config.py:42` (read-only, to confirm `WikiConfig.models_path` shape).

**Files scanned:** 5
**Pattern extraction date:** 2026-05-18
**Early-stop reason:** both new files have exact analogs; no broader search warranted (per execution flow §Step 4 "Stop at 3–5 analogs once you have enough strong matches").
