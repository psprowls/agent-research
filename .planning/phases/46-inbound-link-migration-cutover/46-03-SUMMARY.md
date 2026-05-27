---
phase: 46-inbound-link-migration-cutover
plan: 03
type: execute
status: complete
completed_at: 2026-05-27
requirements:
  - MIGRATION-03
  - MIGRATION-05
key-files:
  created:
    - agents/graph-wiki-agent/src/graph_wiki_agent/commands/migrate_vault.py
    - agents/graph-wiki-agent/tests/test_migrate_vault.py
  modified:
    - agents/graph-wiki-agent/src/graph_wiki_agent/cli.py
commits:
  - 670fd15 feat(46-03): add graph-wiki-agent migrate-vault — 7-step atomic cutover
---

# Plan 46-03 Summary: graph-wiki-agent migrate-vault CLI + 7-step cutover

## What Shipped

1. **`run_migrate_vault(dry_run, force, write_marker, *, workspace_path)`** in
   `agents/graph-wiki-agent/src/graph_wiki_agent/commands/migrate_vault.py`:

   - **Step 0** Idempotency guard — reads `.graph-wiki/manifest.json`; if
     `migrated_to == 'v1.8-entity-restructure'`, prints already-migrated
     message and returns 0 without touching the filesystem (D-09). `--force`
     bypasses this check; `--force` on a clean post-migration state (marker
     present + no old dirs) is a no-op (D-10).
   - **Step 1** `write_entities(conn, wiki_root, ADMITTED_KINDS_V18)` — populates
     `wiki/entities/`.
   - **Step 2** `rewrite_vault(wiki_root, table, log_path=log_path)` — rewrites
     wikilinks across all 5 curated lanes (D-13).
   - **Step 3** `git rm -r` over `OLD_LAYOUT_ROOTS` (packages, dependencies,
     domain, plugin, package-family) — package-family IS removed per D-05.
   - **Step 4** `generate_index(conn, wiki_root)` — Phase 44 surface.
   - **Step 5** `update_index(wiki_root)` — Phase 45 surgical form.
   - **Step 6** `_write_manifest(manifest_path, rewrite_result)` — writes the
     marker JSON (skipped under `--no-write-marker` for testing).
   - **Step 7** `git commit -m "feat(46): v1.8 entity restructure cutover"`.

   On ANY exception/CalledProcessError between steps 1 and 6, the function
   prints `[error] <step> failed: <e>` to stderr and returns 2 — abort BEFORE
   the commit (D-07). The graph connection is always closed in `finally`.

2. **Dry-run preview (D-12)** — plain-text stdout with sections: header line
   `Vault migration preview — <project>`, entity counts (5 kinds),
   wikilink-rewrites sample (first 10), unresolvable list (first 5),
   directories-to-remove with optional `⚠ human content detected` warning
   surfaced via `_human_content_warning` + lazy `python-frontmatter` import,
   marker-write note, run-instruction footer.

3. **CLI registration** in `cli.py`:
   - Import: `from graph_wiki_agent.commands.migrate_vault import run_migrate_vault`
   - Command: `@app.command(name="migrate-vault")` with `--dry-run`,
     `--force`, `--no-write-marker` (hidden). Sits next to `scan` per D-15
     (flat command, not subapp).

4. **13 tests** in `agents/graph-wiki-agent/tests/test_migrate_vault.py`,
   each using a tmpdir vault + `_git_init` + `_seed_graph_db` (uses
   `graph_io.schema.apply_schema` + INSERTs 1 package + 1 domain). Covers:
   - `test_migrate_vault_dry_run_makes_no_changes`
   - `test_migrate_vault_dry_run_output_sections` (D-12 section presence)
   - `test_migrate_vault_full_cutover_writes_manifest`
   - `test_migrate_vault_full_cutover_removes_old_dirs`
   - `test_migrate_vault_full_cutover_populates_entities`
   - `test_migrate_vault_single_commit` (rev-list count + subject line)
   - `test_migrate_vault_second_run_no_op`
   - `test_migrate_vault_force_recovery` (partial-cutover state)
   - `test_migrate_vault_force_no_effect_on_clean_state`
   - `test_migrate_vault_no_write_marker`
   - `test_migrate_vault_unresolvable_target_left_alone` (+ migration.log
     entry assertion)
   - `test_migrate_vault_aborts_before_commit_on_failure` (monkeypatched
     `generate_index` → exit 2 + no new commit)
   - `test_migrate_vault_help_exits_zero` (subprocess `uv run
     graph-wiki-agent migrate-vault --help`)

## Tests Green

```
agents/graph-wiki-agent/tests/test_migrate_vault.py: 13 passed
Full graph-wiki-agent suite:                         328 passed, 11 skipped
Full wiki-io regression:                             343 passed, 2 skipped, 1 xfailed
```

## Decisions Honored

- **D-05** Package-family IS removed (OLD_LAYOUT_ROOTS already includes it
  from Plan 02; Step 3 includes it in the `git rm -r` set).
- **D-06** 7-step composition implemented as a linear function with try/except
  per step.
- **D-07** Abort BEFORE commit on any failure; tested via monkeypatched
  `generate_index` failure assertion.
- **D-08** Marker shape: `{migrated_to, migrated_at, rewrite_count,
  rewrite_unresolved}` — single JSON object (not JSONL), pretty-printed and
  sort_keys=True for stability.
- **D-09** Idempotency check is the FIRST step; runs before opening the graph
  DB to keep the no-op path zero-cost.
- **D-10** `--force` bypasses the check; clean-post-migration short-circuits
  with "no effect" message.
- **D-11** Three flags: `--dry-run`, `--force`, `--no-write-marker` (hidden).
- **D-12** Dry-run output is plain text to stdout (no ANSI), with all
  required sections; assertions cover each one.
- **D-15** Command sits as a flat `@app.command(name="migrate-vault")` next
  to `scan` — NOT a sub-app.
- **D-16** Migration log JSONL shape consumed via Plan 02's `_append_migration`
  (the cutover passes `log_path=workspace_root/".graph-wiki"/"migration.log"`).

## Deviations

1. **CLI binary name** — the plan referenced `cg migrate-vault` but `cg` is
   the graph-io companion tool. The canonical name is `graph-wiki-agent
   migrate-vault` (per `agents/graph-wiki-agent/pyproject.toml`
   `project.scripts`). The test + help invocations use the canonical name.

2. **monkeypatch target for failure test** — `monkeypatch.setattr(
   index_generator, "generate_index", boom)` patches the source module but
   not the symbol our command holds via `from wiki_io.index_generator import
   generate_index`. The test patches `mv_module.generate_index` instead,
   which is the bound name our command actually invokes.

3. **`workspace` parameter** — the plan's `@app.command` example omits the
   `--workspace` option. I followed the example exactly; the command relies
   on `resolve_wiki_and_repo`'s `GRAPH_WIKI_WORKSPACE` env var path, which
   matches every existing test pattern (`monkeypatch.setenv` in the
   `vault` fixture).

## Self-Check: PASSED

- [x] Task 1 acceptance — `run_migrate_vault` defined; `MIGRATION_MARKER_VALUE`
      and `v1.8-entity-restructure` constants resolve; all 5 wiki-io imports
      present.
- [x] Task 2 acceptance — `from graph_wiki_agent.commands.migrate_vault import
      run_migrate_vault` import added; `@app.command(name="migrate-vault")`
      registration present; `graph-wiki-agent migrate-vault --help` exits 0.
- [x] Task 3 acceptance — 13 tests defined and pass; full graph-wiki-agent
      suite green (no regression); real subprocess git ops used for commit
      assertions.
- [x] Plan-level verification — all imports succeed; both regression suites
      green; CLI smoke and import smoke pass.

## Next Steps (User-Gated)

The Phase 46 EXECUTION phase is complete — the CODE is shipped and tested.
The actual cutover against the live `agent-research` vault is a USER-GATED
manual step:

```
# Preview what will change:
uv run graph-wiki-agent migrate-vault --dry-run

# Execute the atomic cutover commit:
uv run graph-wiki-agent migrate-vault
```

This is intentional — no autonomous executor runs the destructive cutover
against the production vault. The orchestrator landed the enabling code and
ran every test against fixture vaults under `tmp_path`; the live `wiki/`
directory is untouched by this phase's execution.
