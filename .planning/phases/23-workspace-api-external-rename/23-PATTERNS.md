# Phase 23: workspace-api-external-rename — Pattern Map

**Mapped:** 2026-05-20
**Files analyzed:** ~22 (6 MCP input classes, 7 Typer flags, 1 helper + 3 emit sites, 1 integration test, 10 docs/mirrors, 2 brand-gate files)
**Analogs found:** 22 / 22

This is a **mechanical rename phase**, not new-code authoring. Every file already exists and has a uniform shape; the work is a coordinated find-and-replace plus one additive brand-gate regex block. The strongest in-tree analogs are:

- **Phase 21** (`code-wiki-agent` → `graph-wiki-agent`) — extended `scripts/check-brand.sh` CHECK 1 by appending alternations to a single regex; seeded `.brand-grep-allow` with per-entry rationale comments. Closest analog for WSMCP-07.
- **Phase 18** (CMD rename — `init` → `bootstrap`) — added a *new* gate block (`CHECK 2`) to `scripts/check-brand.sh` rather than extending CHECK 1. Closest analog if the planner chooses to add a new CHECK block (e.g. `CHECK 4`) for the 3 workspace-API patterns; the regex is more structural (anchored to Pydantic-field context) than CHECK 1's free-text alternations, which favors a separate block.
- **Phase 22** (internal `vault_path` → `workspace_path` kwargs) — already shipped; established that `Path(input.vault_path)` field-reads stay at the MCP boundary while internal kwargs are `workspace_path=`. This phase is the second half of that cutover.

## File Classification

| File | Role | Data Flow | Closest Analog | Match |
|------|------|-----------|----------------|-------|
| `agents/graph-wiki-agent/src/graph_wiki_mcp/server.py` (6 input classes) | mcp-schema | request-response | self (Phase 22 left internals consistent) — mechanical rename | exact |
| `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py` (7 commands) | cli-entrypoint | request-response | self — uniform Typer shape across all 7 | exact |
| `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py::bootstrap` (additive `--repo`) | cli-entrypoint | request-response | existing `repo_path` field in `WikiScanInput` (server.py L246-249) | role-match |
| `packages/wiki-io/src/wiki_io/scan_monorepo.py::_vault_path_for` | utility/helper | transform | self — single helper rename + 3 dict-key emissions | exact |
| `agents/graph-wiki-agent/tests/integration/test_mcp_e2e.py` | test | request-response | self — 6 builder helpers with uniform payload shape | exact |
| 5 plugin docs (`plugins/graph-wiki/...`) | documentation | n/a | Phase 12 / Phase 18 doc sweeps | role-match |
| 5 prompt-source mirrors (`packages/prompt-sources/references/*.md`) | documentation (runtime-loaded) | n/a | plugin docs (file pair) | role-match |
| `scripts/check-brand.sh` (additive block) | brand-gate | batch | CHECK 2 block at L52-66 (Phase 18) **or** CHECK 1 extension at L40-43 (Phase 21) | exact |
| `.brand-grep-allow` (additive entries) | allowlist config | n/a | existing Phase 21 entries at L222+ | exact |

## Pattern Assignments

### MCP Pydantic Input Classes (WSMCP-01)

**File:** `agents/graph-wiki-agent/src/graph_wiki_mcp/server.py`

**Six classes affected (uniform shape):** `WikiQueryInput` (L103), `WikiLogInput` (L150), `WikiBootstrapInput` (L192), `WikiScanInput` (L242), `WikiIngestInput` (L299), `WikiLintInput` (L374).

**Three sub-shapes for the `vault_path` field — all three exist, all three rename identically:**

Shape A — bare default (`WikiQueryInput` L105):
```python
class WikiQueryInput(BaseModel):
    query: str
    vault_path: str = ""  # empty -> resolve from GRAPH_WIKI_WORKSPACE env var
    top_k: int = Field(default=5, ge=3, le=10)
```
→ rename to `workspace_path: str = ""` (comment retained or updated at executor's discretion per D-CtX "Claude's Discretion" — `vault` term must be purged).

Shape B — `Field(...)` with default + description (`WikiLogInput` L154; identical at L196, L243, L309, L375):
```python
vault_path: str = Field("", description="Vault path (default: GRAPH_WIKI_WORKSPACE env var)")
```
→ rename to `workspace_path: str = Field("", description="Workspace path (default: GRAPH_WIKI_WORKSPACE env var)")`.

Shape C — adjacent `repo_path` field in `WikiScanInput` (L246-249) — **keep as-is**, but update the description's internal reference to `vault_path`:
```python
repo_path: str = Field(
    "",
    description="Override repo root for scanner (default: resolved from vault_path). Use for testing.",
)
```
→ description text changes to `"... (default: resolved from workspace_path). Use for testing."`.

**Internal field reads — uniform pattern at 6 sites (L125, L169, L215, L266, L332, L411):**
```python
vault = Path(input.vault_path) if input.vault_path else None
```
→ rename to `vault = Path(input.workspace_path) if input.workspace_path else None`. (Local var name `vault` may stay or rename — executor's discretion. Phase 22's pattern was to keep the local var; the field-read is what *must* move.)

**Tool description strings referencing the field by name** (L121, L328):
```python
"vault_path defaults to GRAPH_WIKI_WORKSPACE env var."
```
→ rename to `"workspace_path defaults to GRAPH_WIKI_WORKSPACE env var."` (both `wiki_query` description and `wiki_ingest` description).

---

### Typer CLI Flags (WSMCP-02)

**File:** `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py`

**Seven commands affected (uniform shape):** `query` (L382), `log` (L420), `bootstrap` (L442), `scan` (L463), `ingest_source` (L501), `ingest_work_item` (L526), `lint` (L560).

**Uniform Typer-Option shape:**
```python
vault: str = typer.Option("", "--vault", help="Vault path (default: GRAPH_WIKI_WORKSPACE env var)"),
```
→ rename in lockstep to:
```python
workspace: str = typer.Option("", "--workspace", help="Workspace path (default: GRAPH_WIKI_WORKSPACE env var)"),
```

**Three things move together per command:**
1. Python parameter name: `vault` → `workspace`
2. Flag literal (positional arg #2 to `typer.Option`): `"--vault"` → `"--workspace"`
3. Help text: replace `Vault path` with `Workspace path`

**Per-command local-var bridge (uniform — appears in every command body):**
```python
workspace_path = Path(vault) if vault else None
```
→ rename the right-hand reference to match the new param name:
```python
workspace_path = Path(workspace) if workspace else None
```
(Local var `workspace_path` already exists from Phase 22 — only the source variable on the RHS changes.)

**The `query` command (L382-394) has one extra quirk** — a comment at L388 references state-gate logic, leave unchanged. The pattern is identical otherwise.

---

### Additive `--repo` Flag on `bootstrap` Only (WSMCP-03)

**File:** `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py` — only the `bootstrap` command (L438-458).

**Per D-02, scope is bootstrap-only.** Do NOT add `--repo` to scan/lint/ingest/query/log.

**Analog for the flag declaration shape** — existing MCP `repo_path` field in `WikiScanInput` (server.py L246-249) shows the pattern at the *MCP* layer (the MCP layer was carrying it for scan since before this phase). The Typer flag should mirror its semantics: accept a string, default empty, resolve via `Path(...).resolve()` if supplied.

**Pattern to introduce** (modeled on existing Typer `Option` shape used throughout cli.py):
```python
@app.command()
def bootstrap(
    topic: str = typer.Option(..., "--topic", help="Short description of the repository"),
    tool: str = typer.Option(..., "--tool", help="Schema file(s) to install (claude-code, codex, cursor, all, ...)"),
    force: bool = typer.Option(False, "--force", help="Overwrite non-empty target directory"),
    workspace: str = typer.Option("", "--workspace", help="Workspace path (default: GRAPH_WIKI_WORKSPACE env var)"),
    repo: str = typer.Option("", "--repo", help="Override repo root (default: CWD walk-up)"),  # <-- NEW
    json_output: bool = typer.Option(False, "--json", help="Emit InitResult as JSON"),
) -> None:
    workspace_path = Path(workspace) if workspace else None
    repo_path = Path(repo).resolve() if repo else None  # <-- NEW
    try:
        result = asyncio.run(run_init(topic=topic, tool=tool, force=force, workspace_path=workspace_path, repo_path=repo_path))  # add kwarg
    ...
```

**Caveat — verify `run_init` signature first.** Phase 22 added a `repo_path: Path | None = None` kwarg to `resolve_wiki_and_repo`, but only `run_scan` is documented to accept `repo_path` on the MCP/CLI path. If `run_init` does not accept `repo_path`, this WSMCP-03 implementation requires extending `run_init` to thread it through to `workspace_io.init.init()` — that's an implementation concern for the planner to flag.

**Default/help-text wording:** at executor's discretion per CONTEXT "Claude's Discretion".

---

### Scan JSON Output Field (WSMCP-04)

**File:** `packages/wiki-io/src/wiki_io/scan_monorepo.py`

**Helper rename — L399:**
```python
def _vault_path_for(pkg: dict, vault_dir: str | None = None) -> str:
    """Return the canonical vault page path for a discovered workspace.
```
→ rename to:
```python
def _wiki_relative_path_for(pkg: dict, vault_dir: str | None = None) -> str:
    """Return the wiki-relative page path for a discovered workspace.
```
(The `vault_dir` parameter name is OUT OF SCOPE per `wiki-io` package-name preservation D-07 carried forward — `vault_dir` is a layout-pinned schema key, not the rename target.)

**Three emission sites — uniform pattern (dict key `"vault_path"`):**

L395 (inside `scan_workspaces`, after `_vault_path_for` returns):
```python
w["vault_path"] = _vault_path_for(w, vault_dir=vault_dir)
```
→ rename to:
```python
w["wiki_relative_path"] = _wiki_relative_path_for(w, vault_dir=vault_dir)
```

L666 (inside `_load_existing_pages`, first pass):
```python
pages[name] = {
    "vault_path": str(md.relative_to(wiki)).replace("\\", "/"),
    ...
}
```
→ rename the key to `"wiki_relative_path"`.

L717 (inside `_load_existing_pages`, domains pass) — identical to L666:
```python
pages[name] = {
    "vault_path": str(md.relative_to(wiki)).replace("\\", "/"),
    ...
}
```
→ rename the key to `"wiki_relative_path"`.

**Docstring at L616 (`_load_existing_pages`):**
```python
"""Return dict of workspace name → {vault_path, package_path, category}.
```
→ rename `vault_path` to `wiki_relative_path` in the docstring.

**Downstream consumers** of these dict keys must move in lockstep. The planner needs to grep for `"vault_path"` and `["vault_path"]` and `.get("vault_path"` across `packages/` + `agents/` to find every reader. Phase 22's SUMMARY V8 already lists one consumer at `commands/scan.py` (`pkg.get("vault_path", ...)` ) — that read site moves to `pkg.get("wiki_relative_path", ...)` in lockstep.

---

### Integration Test (WSMCP-06)

**File:** `agents/graph-wiki-agent/tests/integration/test_mcp_e2e.py`

**Six payload-builder helpers (L165-258) — uniform shape with one `vault_path` key per payload:**
```python
def _send_wiki_bootstrap(request_id: int, vault_path: str) -> dict:
    return {
        ...
        "arguments": {"input": {
            "topic": "test repo",
            "tool": "claude-code",
            "vault_path": vault_path,  # <-- JSON key, must rename
        }},
    }
```
→ rename the JSON key to `"workspace_path"` in all 6 builder bodies. The Python parameter name `vault_path` (function arg) may stay or rename — executor's discretion. The MCP-payload JSON key is what *must* move because that's what the Pydantic schema parses.

**The 6 builders:** `_send_wiki_bootstrap` (L165), `_send_wiki_scan` (L181), `_send_wiki_ingest` (L197), `_send_wiki_query` (L214), `_send_wiki_lint` (L230), `_send_wiki_log` (L244).

**`_send_wiki_scan` also carries `repo_path`** (L190) — leave unchanged; that key matches the unchanged `repo_path` field on `WikiScanInput`.

**Verification gate per D-04:**
- Default `uv run pytest` (without integration env var) must remain green after rename.
- Opportunistic live run: if `GRAPH_WIKI_RUN_INTEGRATION=1` is set, run `uv run pytest agents/graph-wiki-agent/tests/integration/test_mcp_e2e.py` and treat non-zero exit as plan-level failure.
- Otherwise record UAT line in SUMMARY.md.

---

### Plugin Docs + Prompt-Source Mirrors (WSMCP-05)

**Plugin-doc files with hits (verified via `grep -lE 'vault_path|--vault'`):**
- `plugins/graph-wiki/agents/scanner.md` — L48 references `vault_path` per-workspace emission
- `plugins/graph-wiki/skills/graph-wiki/references/scan-workflow.md` — L68 + L102 reference `vault_path`

**Files claimed in scope by CONTEXT but verified to have NO current hits:**
- `plugins/graph-wiki/skills/graph-wiki/references/detection-workflow.md`
- `plugins/graph-wiki/skills/graph-wiki/references/wiki-schema.md`
- `plugins/graph-wiki/commands/scan.md`

The planner should re-grep before assuming these are out of scope — `--vault` CLI references may exist that the initial substring grep missed. Suggested verification: `grep -nE 'vault_path|--vault|"vault_path"' plugins/graph-wiki/**/*.md` before plan execution.

**Prompt-source mirror — only one file currently mirrors the affected content:**
- `packages/prompt-sources/references/scan-workflow.md` (mirror pair to `plugins/graph-wiki/skills/graph-wiki/references/scan-workflow.md`)

Per CONTEXT D-08, the mirrors are loaded into agent system prompts at runtime, so divergence is a silent behavior regression. The plan must touch both halves of each pair.

**Verification grep AFTER the sweep:**
```bash
grep -nE '\bvault_path\b|--vault\b' plugins/graph-wiki/ packages/prompt-sources/references/
```
must return zero hits.

---

### Brand-Gate Extension (WSMCP-07)

**File:** `scripts/check-brand.sh` (extend) + `.brand-grep-allow` (seed)

**Two competing structural patterns from prior phases:**

**Option A — Extend CHECK 1's existing alternation (Phase 21 precedent, commit `161a1cd`):**
```bash
# diff -U2 against current scripts/check-brand.sh L40-43
HITS=$(grep -rEl --exclude-dir=__pycache__ --exclude='*.pyc' \
    'lattice|LATTICE|lattice_workspace|lattice_wiki_core|code-wiki-agent|code_wiki_agent|code-wiki-mcp|code_wiki_mcp' \
    packages/ agents/ plugins/ .planning/ CLAUDE.md 2>/dev/null \
    | grep -vF -f <(grep -vE '^[[:space:]]*(#|$)' "$ALLOWLIST") || true)
```
This pattern works for free-text alternations. **It does NOT work for the WSMCP-07 patterns** because:
- `vault_path` as a substring appears in `.planning/` and prompt strings legitimately (D-03 says `.planning/` is excluded; tests can contain `vault_path` as a string literal).
- The three banned patterns are *contextual* (Pydantic field name, Typer flag literal, dict key) — not free substrings.

**Option B — Add a new CHECK block, anchored regexes (Phase 18 precedent, commit `97b0b44` CHECK 2 at L52-66, *strongly preferred*):**
```bash
# Existing CHECK 2 (Phase 18) — structural template to mirror for WSMCP-07
HITS2=$(grep -rEl --exclude-dir=__pycache__ --exclude='*.pyc' \
    'graph-wiki:init\b|\bwiki_init\b' \
    packages/ agents/ plugins/ .planning/ scripts/ docs/ README.md CLAUDE.md 2>/dev/null \
    | grep -vF -f <(grep -vE '^[[:space:]]*(#|$)' "$ALLOWLIST") || true)

if [ -n "$HITS2" ]; then
  echo "$HITS2"
  COUNT2=$(printf '%s\n' "$HITS2" | wc -l | tr -d ' ')
  echo "BRAND-CMD FAIL: ${COUNT2} unallowlisted hits for graph-wiki:init|wiki_init" >&2
  exit 1
fi
```

**Recommended WSMCP-07 implementation — a new CHECK 4 block, mirroring CHECK 2's structure but using extended regex and a tighter path scope:**
```bash
# CHECK 4 — Phase 23 WSMCP-07: ban reintroduction of the three workspace-API
# patterns. D-03 narrows scope to: (1) Pydantic `vault_path:` Field-name in
# class-body context, (2) `"--vault"` flag literal, (3) `"vault_path"` JSON key.
# Path scope excludes .planning/ (historic refs allowed) per D-03.
HITS4=$(grep -rEln --exclude-dir=__pycache__ --exclude='*.pyc' -E \
    '^[[:space:]]+vault_path:[[:space:]]+(str|Path|int|bool)|"--vault"|"vault_path"' \
    packages/ agents/ plugins/ 2>/dev/null \
    | grep -vF -f <(grep -vE '^[[:space:]]*(#|$)' "$ALLOWLIST") || true)

if [ -n "$HITS4" ]; then
  echo "$HITS4"
  COUNT4=$(printf '%s\n' "$HITS4" | wc -l | tr -d ' ')
  echo "BRAND-WSAPI FAIL: ${COUNT4} unallowlisted hits for vault_path Field|--vault flag|\"vault_path\" key" >&2
  exit 1
fi
```

**Important regex notes for the planner / executor:**
- `^[[:space:]]+vault_path:` anchors to indented class-body lines — catches Pydantic `vault_path: str = Field(...)` declarations but NOT bare `vault_path` references inside docstrings or comments.
- `"--vault"` (literal double-quoted) catches `typer.Option(..., "--vault", ...)` declarations. Will NOT catch `'--vault'` (single-quoted) — verify the codebase only uses double quotes (cli.py L382 confirms double quotes — uniform).
- `"vault_path"` (double-quoted) catches dict-literal keys in Python source. WILL catch `"vault_path"` inside JSON-shaped test payloads — D-03 says "Tests are NOT excluded", so this is intentional after the test sweep ships.
- Path scope is `packages/ agents/ plugins/` only — drops `.planning/`, `scripts/`, `docs/`, `README.md`, `CLAUDE.md` per D-03 narrowing.

**Header comment to add at top of script (mirrors Phase 21's L13-14 pattern, commit `161a1cd`):**
```bash
# Per Phase 23 §WSMCP-07: extended to also catch the three workspace-API
# legacy patterns — `vault_path:` Pydantic Field name, `"--vault"` flag literal,
# `"vault_path"` JSON dict key.
```

**Exit-code envelope:** keep the existing pattern — `exit 1` on FAIL, single combined `echo "BRAND-04 OK: ..."` line at the bottom updated to mention CHECK 4. Current line is L80:
```bash
echo "BRAND-04 OK: zero unallowlisted hits (BRAND-04 lattice + BRAND-CMD graph-wiki:init|wiki_init + BRAND-CMD-CLI def init( all clean)"
```
→ append `+ BRAND-WSAPI vault_path|--vault|"vault_path"` to the parenthetical.

---

### `.brand-grep-allow` Seeding

**File:** `.brand-grep-allow` at repo root.

**Existing format** (verified at L62-95) — every entry carries a `# rationale:` (or block-comment header) naming the carry-forward class. Phase 21's seeding pattern at L222+ is the closest analog.

**Per D-03, the .brand-grep-allow seeding should be NARROW.** Run the new CHECK 4 first as a red-stage dry-run; only add entries for *unavoidable* historical references that surface. Likely seed candidates (planner should verify by running the dry-run):
- `scripts/check-brand.sh` self-reference (the new regex literals appear inside the script itself — line will read e.g. `'^[[:space:]]+vault_path:`). Note: existing self-allowlist at L66 already covers this file, so no new entry needed.
- `.brand-grep-allow` self-reference (this file's own pattern documentation may contain the literals as documentation). Existing self-allowlist at L65 already covers this file.
- Anywhere the OLD MCP-error message string is asserted in a test (if any).

**Seeding pattern** (mirror Phase 21 style, e.g. L259-263 in current file):
```
# rationale: <carry-forward class or D-decision> — <one-line reason>
<path-fragment>
```

The planner should NOT pre-seed entries; instead, plan the implementation to:
1. Land the regex extension first.
2. Run `bash scripts/check-brand.sh` to surface hits.
3. Triage each hit — rename in source if rename-able; allowlist with rationale if not.
4. Re-run until exit 0.

---

## Shared Patterns

### Pattern 1: Phase 22's `Path(input.vault_path)` Boundary Convention

**Source:** `agents/graph-wiki-agent/src/graph_wiki_mcp/server.py` L125, L169, L215, L266, L332, L411 (current state after Phase 22).

**Convention preserved:** The MCP server reads the Pydantic field, immediately binds to a local `vault` variable (typed `Path | None`), then passes downstream as a `workspace_path=` kwarg.

```python
vault = Path(input.vault_path) if input.vault_path else None
await ctx.report_progress(...)
result = await run_xxx(workspace_path=vault, ...)
```

**Apply to:** all 6 MCP handlers. Only the right-hand field-read changes (`input.vault_path` → `input.workspace_path`); the local var `vault` may stay (preserves diff size) or rename to `workspace`.

### Pattern 2: Uniform Typer-Option Triple-Rename

**Source:** `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py` L382 et al.

**Three things move in lockstep per command:**
1. Python kwarg name in the function signature
2. Flag literal (positional arg #2 to `typer.Option`)
3. Help text wording

**Apply to:** all 7 Typer commands. Splitting (e.g. renaming kwarg but not flag) creates a non-compiling test stub.

### Pattern 3: Brand-Gate Block Structure

**Source:** `scripts/check-brand.sh` L52-66 (Phase 18 CHECK 2 — closest structural analog for WSMCP-07).

**Block shape:** comment header naming the phase + rationale; `HITS<N>=$(grep -rEln ... 2>/dev/null | grep -vF -f <(grep -vE '^[[:space:]]*(#|$)' "$ALLOWLIST") || true)`; `if [ -n "$HITS<N>" ]; then ... fail ... fi`.

**Apply to:** the new CHECK 4 for WSMCP-07. Don't extend CHECK 1's free-text alternation — the patterns are structurally different (contextual, not substring).

### Pattern 4: Allowlist Entry With Rationale Comment

**Source:** `.brand-grep-allow` L62-95 (multiple Phase-12/Phase-21 entries).

**Pattern:** `# rationale: <D-decision or carry-forward class> — <one-sentence reason>` immediately preceding the path-fragment line.

**Apply to:** any new allowlist entries needed after WSMCP-07 dry-run.

### Pattern 5: Plugin Doc ↔ Prompt-Source Mirror Pair

**Source:** `plugins/graph-wiki/skills/graph-wiki/references/scan-workflow.md` ↔ `packages/prompt-sources/references/scan-workflow.md`.

**Convention (per Phase 19):** the file in `plugins/graph-wiki/skills/.../references/` is mirrored 1:1 in `packages/prompt-sources/references/`. The mirror is loaded into agent system prompts at runtime. Drift between the pair = silent agent-behavior regression.

**Apply to:** every plugin-doc edit in WSMCP-05. Whenever a `plugins/graph-wiki/skills/graph-wiki/references/<X>.md` file changes, the corresponding `packages/prompt-sources/references/<X>.md` mirror must change in the same commit. Pairs verified:
- `scan-workflow.md` — both halves exist; only the plugin half currently has `vault_path` hits, but verify after the rename that mirror copy was also updated.
- `detection-workflow.md`, `wiki-schema.md` — both halves exist; verify before assuming no edit needed.

`plugins/graph-wiki/agents/scanner.md` has NO mirror in `packages/prompt-sources/references/` — the `agents/scanner.md` is a separate kind of plugin file (subagent system prompt source for the Claude Code plugin, not a reference doc).

## No Analog Found

None. Every artifact in scope has a direct in-tree precedent (Phase 12, 18, 21, or 22). The only "new" code is the additive CHECK 4 block in `scripts/check-brand.sh`, and that mirrors CHECK 2 structurally.

## Files With No Edits Likely Needed (Verify First)

These three plugin docs are named in CONTEXT but the substring-grep returned no hits. The planner should re-grep with a broader pattern (including `--vault` CLI examples and prose mentions of "vault path"):
- `plugins/graph-wiki/skills/graph-wiki/references/detection-workflow.md`
- `plugins/graph-wiki/skills/graph-wiki/references/wiki-schema.md`
- `plugins/graph-wiki/commands/scan.md`

If a re-grep confirms no hits, drop from the file list. Otherwise, the same plugin-doc + mirror-pair pattern applies.

## Metadata

**Analog search scope:** `scripts/`, `packages/wiki-io/`, `packages/prompt-sources/`, `agents/graph-wiki-agent/`, `plugins/graph-wiki/`, `.planning/phases/{12,18,21,22}/` (via git log on `check-brand.sh`).
**Key analog commits referenced:**
- `644b942` — Phase 12: initial brand-gate creation (BRAND-04)
- `97b0b44` — Phase 18: CHECK 2 block addition (closest WSMCP-07 structural analog)
- `161a1cd` — Phase 21: CHECK 1 regex extension + allowlist seeding (closest WSMCP-07 procedural analog)

**Pattern extraction date:** 2026-05-20
