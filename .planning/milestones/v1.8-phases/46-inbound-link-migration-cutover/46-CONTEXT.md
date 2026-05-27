# Phase 46: Inbound-Link Migration + Cutover - Context

**Gathered:** 2026-05-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Two coupled deliverables shipped in one atomic cutover commit:

1. **`wiki_io/link_rewriter.py`** — Markdown-aware wikilink rewriter. Tokenizes documents into prose vs code regions (fenced + inline + indented), rewrites only in prose. Mapping from old-layout paths to new entity slugs is derived from a triple-source pipeline: convention templates per kind + scan-and-match over old layout directories + grep over curated lanes. Unresolvable references are logged but not silently dropped.

2. **The cutover itself** — a single atomic git commit that:
   - Populates `wiki/entities/` via `write_entities` (final pass against the production graph).
   - Rewrites inbound wikilinks across all 5 curated lanes (`concepts/`, `adrs/`, `architecture/`, `sources/`, `work/`).
   - `git rm -r` removes the 5 old layout directories: `wiki/packages/`, `wiki/dependencies/`, `wiki/domain/`, `wiki/plugin/`, `wiki/package-family/`.
   - Regenerates `wiki/index.md` via `generate_index` (consolidated entity + curated listings).
   - Writes the idempotency marker `migrated_to: "v1.8-entity-restructure"` to `.graph-wiki/manifest.json`.

   Pre-flight gate: a `--dry-run` mode that previews all planned changes without touching the filesystem. User reviews dry-run output, then runs the cutover for the atomic commit.

**Code surface modified:**
- `packages/wiki-io/src/wiki_io/link_rewriter.py` — new module, primary deliverable.
- `packages/wiki-io/src/wiki_io/lint/common.py` — possibly extended (additional code-mask helpers; non-breaking).
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/` — new CLI subcommand (e.g., `cg migrate-vault` or `graph-wiki-agent vault migrate`) that orchestrates the cutover.
- `.planning/ROADMAP.md` — amend Phase 46 SC#1 to include `/sources/` and `/work/` (currently lists only concepts/adrs/architecture per discussion).
- `.planning/REQUIREMENTS.md` — possibly clarify MIGRATION-05 cutover composition language.

**Code surface NOT modified:**
- Phase 43's `entity_writer.write_entities` — used as-is.
- Phase 44's `index_generator.generate_index` — used as-is.
- Phase 45's `scan` wiring — used as-is (a normal scan run produces the entity vault; cutover does a final scan run).
- `plugins/graph-wiki/scan_monorepo.py` — explicitly left on legacy layout per Phase 45 D-13. Post-cutover, the plugin's tests may need a separate fixture vault (TBD post-v1.8).

**Phase 43 override.** Phase 43 CONTEXT.md noted "the cutover phase will NOT remove `wiki/package-family/` in v1.8." Phase 46 D-03 reverses this: `wiki/package-family/` IS removed per ROADMAP SC#4. Phase 43's note was wrong; user explicitly chose unconditional removal during Phase 46 discussion.

**Not in scope (Phase 46):**
- LLM-narrator prompt refinement — v1.9.
- Plugin (`plugins/graph-wiki/`) migration to entity layout — TBD post-v1.8.
- Phase 47/48 cluster commands — those are in flight, independent.
- v1.9 follow-ups: package_family ingestion, sub-domain ingestion, `update_index.py` retirement.

</domain>

<decisions>
## Implementation Decisions

### Rewriter strategy

- **D-01:** **Regex with position-aware code-region masking.** Extends `FENCED_CODE_RE` (` ``` ... ``` `) and `INLINE_CODE_RE` (`` `...` ``) from `packages/wiki-io/src/wiki_io/lint/common.py`. Algorithm:
  1. Identify all code-region spans `(start, end)` in one pass — fenced first (greedy), then inline within non-fenced regions.
  2. Also detect indented code blocks: 4-space-or-tab-indented lines following a blank line.
  3. Iterate matches of the existing `WIKILINK_RE` (also in `lint/common.py`).
  4. Skip any wikilink whose start position falls inside any code-region span.
  5. Build rewritten output by string-splice: walk the file, for each non-code wikilink whose target is in the mapping, replace target with new slug, preserving alias (`|alias`) and anchor (`#anchor`) suffixes.
  
  No new third-party dependencies. Reuses tested regex patterns. ~80–120 LOC for the rewriter core + ~40 LOC for code-region detection.

- **D-02:** **Edge cases documented + tested with explicit fixtures.** Phase 46's fixture set must include:
  - Wikilink inside fenced block (`` ```\n[[old/path]]\n``` ``) — must be byte-identical after migration.
  - Wikilink inside inline code (`` `[[old/path]]` ``) — must be byte-identical.
  - Wikilink inside indented code block (4-space indent following blank line) — must be byte-identical.
  - Nested fences (` ```` ` ` ```` `) — tested separately; the lint code does NOT handle these perfectly, so the fixture documents v1.8 behavior + a known-limitation note in the rewriter docstring.
  - Lazy-continuation prose (a wikilink on a line that follows a fenced block without a blank line) — tested.
  - Wikilink with anchor preserved: `[[packages/graph-io/index#api]]` → `[[entities/pkg__agent-research__graph-io#api]]`.
  - Wikilink with alias preserved: `[[packages/graph-io/index|graph-io]]` → `[[entities/pkg__agent-research__graph-io|graph-io]]`.
  - Wikilink with both: `[[packages/graph-io/index#api|graph-io API]]` → rewritten target, preserved both suffixes.

### Mapping derivation (old layout → new slug)

- **D-03:** **Three-source mapping pipeline.** `build_rewrite_table(conn, wiki_root)` runs three sources, merges, deduplicates, returns `dict[str, str]` (old-target → new-slug).
  
  **Source 1 — Convention templates per kind.** For each admitted graph entity from `list_*` queries, generate the conventional old-layout target:
  ```python
  CONVENTION_TEMPLATES = {
      "package":    "packages/{name}/index",
      "dependency": "dependencies/{ecosystem}/{name}/overview",
      "domain":     "domain/{name}/index",
      "plugin":     "plugin/{name}/overview",
      "test_suite": "test-suites/{name}/index",
      # repository is the wiki root; no old-layout path to rewrite.
      # package_family — see D-04.
  }
  ```
  New slug derived via `entity_writer.encode_slug(uri)`.
  
  **Source 2 — Scan-and-match over old layout directories.** Walk `wiki/packages/`, `wiki/dependencies/`, `wiki/domain/`, `wiki/plugin/`, `wiki/package-family/`. For each `.md` file under these roots: derive its old-layout target string (path-without-`.md`); look up the corresponding graph entity by name and kind; if matched, add `(old_target, new_slug)` to the table. If no match, leave the entry uncovered — `wiki/package-family/` files may not match because package_family ingestion is deferred to v1.9; that's expected.
  
  **Source 3 — Grep curated lanes for inbound link prefixes.** For each of `wiki/concepts/`, `wiki/adrs/`, `wiki/architecture/`, `wiki/sources/`, `work/`: scan files for wikilink targets matching prefixes `packages/`, `dependencies/`, `domain/`, `plugin/`, `package-family/`, `test-suites/`. For each match, attempt to resolve to a new slug via graph entity lookup (name extracted from the target's path). Unresolvable targets are logged to `.graph-wiki/migration.log` (one line per unresolvable target) and left in the table as `(target, None)` — the rewriter SKIPS rewriting these (preserving broken links for manual fix, not silently rewriting to a wrong destination).

- **D-04:** **`package_family` entries in the mapping.** `package_family` is deferred to v1.9 (Phase 43 D-07). Phase 46:
  - Source 1: NO convention template for `package_family` (kind is dormant in v1.8).
  - Source 2: any `wiki/package-family/*.md` files encountered are listed in the dry-run as "unmatched legacy files — directory removal will delete them." Phase 46's cutover removes the directory unconditionally (D-05) so any human content there is lost (recoverable via git history).
  - Source 3: any `[[package-family/...]]` inbound links in curated content are logged as unresolvable and skipped — broken links left for manual fix in a future v1.9 phase.

### Cutover composition

- **D-05:** **`wiki/package-family/` IS removed in v1.8.** Honors ROADMAP SC#4. Overrides Phase 43 CONTEXT.md's "do not remove" note. The dry-run preview surfaces this clearly so the user sees what's being deleted before the commit lands. Curated content lost is recoverable via `git log --follow` on the removed paths.

- **D-06:** **Atomic cutover commit composition.** Single git commit titled `feat(46): v1.8 entity restructure cutover` (or similar). Contents:
  1. **Entity pages produced** — run the same `write_entities` pass that Phase 45's normal scan does. (May already be in place from a Phase 45 scan run; if so, this is a no-op verification step.)
  2. **Wikilinks rewritten** — `link_rewriter.rewrite_vault(wiki_root, rewrite_table)` walks `wiki/concepts/`, `wiki/adrs/`, `wiki/architecture/`, `wiki/sources/`, `work/`; rewrites in-place per D-01; logs per-file change counts to `.graph-wiki/migration.log`.
  3. **Old directories removed** — `git rm -r wiki/packages/ wiki/dependencies/ wiki/domain/ wiki/plugin/ wiki/package-family/`. Done via `subprocess.run(["git", "rm", "-r", ...])` (not `shutil.rmtree` — the removal must be staged for the same commit).
  4. **Index regenerated** — call `index_generator.generate_index(conn, wiki_root)`. Writes `wiki/index.md`.
  5. **Per-folder sub-indexes regenerated** — call `update_index.update_index(wiki_root)` (post-Phase-45 surgical version that only writes per-folder files). Writes `wiki/concepts/index.md`, etc.
  6. **Idempotency marker written** — append/update `.graph-wiki/manifest.json` with `migrated_to: "v1.8-entity-restructure"` plus timestamp.
  7. **Commit** — staged files become the atomic commit. Pre-commit hooks run normally.

- **D-07:** **No partial-cutover state allowed.** If any step in D-06 fails, the cutover script aborts before commit. The user sees the failure, fixes it, re-runs. Failure modes:
  - `write_entities` raises → entity pages are partial → script exits non-zero with stderr message; nothing committed.
  - `link_rewriter` raises mid-file → re-raises; user inspects, fixes, re-runs the cutover from scratch.
  - `git rm` fails → halt; user resolves git state.
  - Marker write fails → halt; cutover commit not made.
  
  Recovery for all cases: `git status` + `git restore --staged .` + `git restore .` to clean working tree.

### Idempotency

- **D-08:** **Idempotency marker = `.graph-wiki/manifest.json`.** New file (or augmented if it already exists for other state — Phase 46 plan must check). Shape:
  ```json
  {
    "migrated_to": "v1.8-entity-restructure",
    "migrated_at": "2026-05-27T18:00:00Z",
    "rewrite_count": 47,
    "rewrite_unresolved": 2
  }
  ```
  Future migrations can add a separate `migrations: [...]` list field if needed; v1.8 only has one migration so the flat key is enough.

- **D-09:** **Idempotency check is the FIRST step of the cutover script.** Before running any analysis or write:
  ```python
  manifest = read_manifest(wiki_root)
  if manifest.get("migrated_to") == "v1.8-entity-restructure":
      print("Vault is already migrated. Use --force to re-run (not recommended).")
      sys.exit(0)
  ```
  Idempotency guard means re-running the cutover is a no-op (MIGRATION-03 acceptance).

- **D-10:** **`--force` flag bypasses idempotency check** but does NOT re-run if the vault is in a clean post-migration state (no old directories present, marker present). Force is intended for "the marker was wrongly written but the cutover never finished" recovery — that situation is detected by: marker present AND any of `wiki/packages/`, `wiki/dependencies/`, `wiki/domain/`, `wiki/plugin/`, `wiki/package-family/` still exist on disk.

### Dry-run

- **D-11:** **`--dry-run` mode required.** CLI subcommand surface:
  ```
  cg migrate-vault --dry-run    # preview only, no writes
  cg migrate-vault              # atomic cutover commit
  cg migrate-vault --force      # bypass idempotency check (for recovery scenarios)
  ```
  Exact CLI name TBD (planner discretion, see existing `cg` subcommand patterns).

- **D-12:** **`--dry-run` output format.** Human-readable plain text to stdout. Sections:
  ```
  Vault migration preview — agent-research
  
  Entities (from graph):
    • 14 packages (4 to be created, 10 already present)
    • 9 dependencies (9 to be created)
    • 3 domains (3 to be created)
    • 1 plugin (1 to be created)
    • 7 test_suites (7 to be created)
  
  Wikilink rewrites (47 total):
    • wiki/concepts/per-repo-layout.md: 3 rewrites
        [[packages/graph-io/index]] → [[entities/pkg__agent-research__graph-io]]
        [[domain/billing/index]] → [[entities/domain__agent-research__billing]]
        ...
    • wiki/adrs/2026-05-billing-split.md: 2 rewrites
    ...
  
  Unresolvable (2 — will be left as-is):
    • [[package-family/aws]] in wiki/concepts/foo.md  (no graph entity)
    • [[packages/old-removed/index]] in wiki/sources/legacy.md  (no graph entity)
  
  Directories to remove (git rm -r):
    • wiki/packages/  (18 files; 0 with human-authored content per frontmatter check)
    • wiki/dependencies/  (9 files)
    • wiki/domain/  (3 files)
    • wiki/plugin/  (1 file)
    • wiki/package-family/  (1 file; ⚠ human content detected: status: draft in foo.md)
  
  Idempotency marker would be written to .graph-wiki/manifest.json
  Estimated post-cutover diff: +N files, -M files, ~K wikilinks rewritten
  
  Run without --dry-run to execute as one atomic commit.
  ```
  The `⚠ human content detected` warnings surface the package-family removal risk for user awareness (D-05).

### Curated lane scope

- **D-13:** **All 5 curated lanes get rewriter pass.** `wiki/concepts/`, `wiki/adrs/`, `wiki/architecture/`, `wiki/sources/`, `work/`. ROADMAP SC#1 lists only the first three; Phase 46 plan includes a ROADMAP edit task to add the other two. (`work/` is workspace-rooted, sibling of `wiki/` — the rewriter must handle the different root path.)

- **D-14:** **`wiki/` root files are NOT rewritten.** `wiki/index.md`, `wiki/log.md`, and any other top-level `wiki/*.md` are owned by `generate_index` / `update_index` / scan logging — they're regenerated, not rewritten. Plan includes a sanity test that runs the rewriter on `wiki/index.md` and confirms it's a no-op (no changes).

### CLI

- **D-15:** **CLI subcommand integrated into `cg` per existing patterns.** Phase 43 D-06 already added `cg describe-dependency` / `cg describe-plugin`. Phase 46 adds `cg migrate-vault`. Same Typer-based structure. Implementation lives in `agents/graph-wiki-agent/src/graph_wiki_agent/commands/migrate_vault.py` (or equivalent path matching existing `commands/` layout).

- **D-16:** **Migration log = JSONL at `.graph-wiki/migration.log`.** Mirrors Phase 43's deletions.log shape (one JSON object per line, append-only). Fields:
  ```json
  {"timestamp": "...", "phase": "rewrite", "file": "wiki/concepts/foo.md", "from": "packages/graph-io/index", "to": "entities/pkg__agent-research__graph-io"}
  {"timestamp": "...", "phase": "unresolved", "file": "wiki/concepts/bar.md", "target": "packages/old-removed/index"}
  {"timestamp": "...", "phase": "remove", "path": "wiki/packages/graph-io/index.md", "had_human_content": false}
  ```
  Survives cutover (not deleted in the cutover commit) — provides post-mortem visibility.

### Claude's discretion

- Exact CLI command name (`cg migrate-vault` vs `cg migrate` vs `graph-wiki-agent vault migrate`).
- Whether the cutover script lives in `agents/graph-wiki-agent/commands/` or as a wiki-io CLI entry point (lean: agents/, mirrors other one-shot cg commands).
- Exact `--dry-run` output formatting / coloration (lean: plain text, no ANSI colors, easy to redirect).
- Whether to inline the `--force` flag's "marker present but old dirs still exist" detection or split into two flags (lean: one flag, branch internally).
- Whether to subprocess.run `git rm -r` or use a GitPython-like wrapper (lean: subprocess; one-shot cutover).
- Exact regex tweaks needed for indented code block detection (lean: 4-space-or-tab indent + preceding blank line, the CommonMark rule; document edge cases in fixtures).
- Whether to support `--no-write-marker` for testing (lean: yes; tests need to run the cutover without polluting STATE).
- Whether the rewriter exposes a public `rewrite_text(text, table) -> text` helper alongside `rewrite_vault` (lean: yes; tests + future callers benefit).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Direct predecessors
- `.planning/phases/43-entity-writer/43-CONTEXT.md` — `write_entities` signature; `encode_slug` (used in rewrite table); deletions.log JSONL shape (template for migration.log). **D-07 ("Phase 46 will NOT remove wiki/package-family/") is OVERRIDDEN by Phase 46 D-05.**
- `.planning/phases/44-scanner-generated-index/44-CONTEXT.md` — `generate_index` is called inside the cutover commit (D-06 step 4).
- `.planning/phases/45-scanner-integration/45-CONTEXT.md` — Phase 45's `update_index.py` surgical change ("skip wiki/index.md write") is a prerequisite; Phase 46 calls the post-Phase-45 form of `update_index.update_index`. **Phase 45 D-02 reverses Phase 44 D-02's "delete update_index.py in Phase 46" — that deletion is NOT done in this phase.**

### Milestone-level
- `.planning/REQUIREMENTS.md` §MIGRATION — MIGRATION-01..MIGRATION-05. Phase 46 plan includes a task to update SC#1 wording (concepts/adrs/architecture → all 5 lanes) per D-13.
- `.planning/ROADMAP.md` Phase 46 — Goal + 5 success criteria. Phase 46 plan includes a task to update SC#1 wording and SC#4 (already lists package-family for removal — keep, per D-05).
- `.planning/STATE.md` — Pitfalls 4 (migration regex over-matching — addressed by D-01 + D-02 fixtures) and 10 (migration re-run artifacts — addressed by D-08..D-10 idempotency guard).

### Existing code (must be read by planner/researcher)
- `packages/wiki-io/src/wiki_io/lint/common.py` — `WIKILINK_RE`, `FENCED_CODE_RE`, `INLINE_CODE_RE`. Rewriter reuses these patterns. Note: nested-fence handling is incomplete in the lint code; Phase 46 documents the v1.8 limitation rather than fully solving it.
- `packages/wiki-io/src/wiki_io/entity_writer.py` (post-Phase 43) — `encode_slug` is called for every new slug in the rewrite table. `_acquire_scan_lock` is held during the cutover's `write_entities` invocation.
- `packages/wiki-io/src/wiki_io/index_generator.py` (post-Phase 44) — called inside the cutover.
- `packages/wiki-io/src/wiki_io/update_index.py` (post-Phase 45) — called inside the cutover for per-folder sub-indexes.
- `packages/graph-io/src/graph_io/queries.py` — `list_packages`, `list_dependencies`, `list_plugins`, `list_domains`, `list_test_suites`. Source for convention-template population (D-03 source 1).
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/` — existing `cg` subcommand patterns; `migrate_vault.py` follows the same structure.
- `packages/wiki-io/src/wiki_io/layout_io.py` — layout-block format (referenced for context; not directly modified).

### Research baseline
- `.planning/research/ARCHITECTURE.md` §migration flow, §curated lanes.
- `.planning/research/PITFALLS.md` Pitfall 4 (migration regex over-matching — addressed by D-01 + D-02), Pitfall 10 (migration re-run artifacts — addressed by D-08..D-10).
- `.planning/research/FEATURES.md` §F8 (inbound link migration).

### Tests (where new Phase 46 tests land)
- `packages/wiki-io/tests/test_link_rewriter.py` (new) — code-region exclusion fixtures (fenced, inline, indented, nested), alias/anchor preservation, byte-identical-after-migration assertions.
- `packages/wiki-io/tests/integration/test_link_rewriter_integration.py` (new) — agent-research vault end-to-end: build rewrite table, rewrite all curated lanes, assert known wikilinks are rewritten correctly, assert code-block fixtures unchanged.
- `agents/graph-wiki-agent/tests/test_migrate_vault.py` (new) — CLI tests: `--dry-run` produces expected output sections; full cutover writes manifest marker; second run is a no-op; `--force` works as specified.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`lint/common.py::WIKILINK_RE`** — already parses `[[target]]`, `[[target#anchor]]`, `[[target|alias]]`. Rewriter reuses this regex; the target capture group is what we replace.
- **`lint/common.py::FENCED_CODE_RE` and `INLINE_CODE_RE`** — code-region detection patterns. Rewriter uses these to mask out non-rewritable regions.
- **`entity_writer.encode_slug`** — pure function from URI → filename. Used to derive new slugs for the rewrite table.
- **`graph_io.queries.list_*`** — five list functions covering all v1.8 admitted kinds (post-Phase 43). Source for the rewrite-table population.
- **`subprocess.run(["git", ...])`** — Phase 43 already uses this pattern for git operations; no new dependency.
- **`pathlib.Path.write_text` + atomic temp-replace** — Phase 44 introduced atomic writes; Phase 46 link_rewriter follows the same pattern.

### Established Patterns
- **CLAUDE.md §8 — pytest fixtures for vault content.** Phase 46 tests follow Phase 42/43/44's fixture conventions (tmpdir + builder helpers).
- **JSONL append-only logs** — Phase 43's deletions.log is the template for migration.log (D-16).
- **`@dataclass(frozen=True)` returns from public functions** — Phase 43/44/45 precedent; Phase 46's `MigrationResult` follows the same pattern.
- **Atomic file rewrite (write to .tmp + os.replace)** — Phase 44 D-16 pattern; link_rewriter uses it for in-place file rewrites.

### Integration Points
- **Cutover orchestration lives in the CLI command, NOT in `link_rewriter.py`.** `link_rewriter.py` is the pure migration library (rewrite_text, rewrite_vault, build_rewrite_table). The CLI assembles them with `write_entities`, `generate_index`, `update_index`, `git rm`, marker write, dry-run printing.
- **The cutover does NOT use the regular scan path.** It runs `write_entities` + `generate_index` + `update_index` directly. The legacy package-page write logic (already removed in Phase 45) does not run.
- **Marker file in `.graph-wiki/manifest.json` is a new file in v1.8.** Phase 46 plan must check if `.graph-wiki/` has other manifest-like files to coalesce into; if not, this is a new dedicated file. (Phase 43's deletions.log is JSONL, different shape; Phase 45's scan.lock is binary fcntl lock — neither is the manifest.)

</code_context>

<specifics>
## Specific Ideas

- **Run dry-run against agent-research itself as a manual gate.** Before the user runs the actual cutover, they run `cg migrate-vault --dry-run` and visually verify the rewrite table covers what they expect. The dry-run output IS the user-facing acceptance gate.
- **Code-region edge-case fixture suite.** Hand-author 8–10 minimal markdown files exercising fenced/inline/indented/nested-fence cases, each with a known expected post-migration output. Snapshot via syrupy (Phase 42/43 pattern).
- **Property-based test for byte-preservation in code blocks.** Hypothesis fixture: random prose + random wikilink targets + random code-fence positions; assert that any wikilink inside a code-fence span is preserved byte-identically after migration.
- **Idempotency test.** Run cutover; assert manifest written, dirs removed, wikilinks rewritten. Run cutover again; assert second invocation exits cleanly with "already migrated" message and zero file changes (`git status` shows no modifications).
- **Alias/anchor preservation tests.** Per D-02 fixture list — explicit each-case tests.
- **`--force` recovery test.** Manually corrupt the marker file (write marker but leave `wiki/packages/` on disk). Run cutover without `--force` → exits saying "already migrated." Run with `--force` → completes cleanup.
- **Unresolvable-target test.** Build a vault with an inbound wikilink `[[packages/totally-fake-package/index]]` (no matching graph entity). Run migration. Assert: link is NOT rewritten; migration.log has an "unresolved" entry for it.

</specifics>

<deferred>
## Deferred Ideas

- **Full CommonMark-compliant rewriter (markdown-it-py)** — D-01 chose regex. Pure-Python pre-built tokenizer would be more robust on nested-fence + lazy-continuation edge cases, but adds a dep and round-trip whitespace risk. Re-evaluate if v1.8 surfaces a regression the regex misses.
- **Package-family v1.9 ingestion** — once `package_family` becomes a real kind with curation source, a v1.9 mini-migration may need to re-create curated content from git history of the removed `wiki/package-family/` files.
- **Plugin (`plugins/graph-wiki/`) migration to entity layout** — explicitly out of scope. Plugin stays on legacy layout until a post-v1.8 phase decides whether to upgrade or retire it.
- **Per-rewrite preview diff** — `--dry-run --verbose` could show full unified diff per file. v1.8 ships with summary-only output; verbose mode is a v1.9 polish item.
- **Atomic rollback command** — `cg migrate-vault --rollback` would `git revert <cutover-commit>` + clear the marker. Not needed in v1.8; `git revert` works directly without a wrapper.
- **Migration log rotation** — Phase 43's deletions.log has a 10 MB rotation. migration.log is a one-shot file (only the cutover writes to it). No rotation needed.
- **Backup snapshot before cutover** — could `git stash` or tarball the vault before mutation. v1.8 skips this; git itself is the safety net (`git reset --hard HEAD~1` after a bad cutover commit).
- **Wikilink target normalization** — wikilinks can use `[[wiki/packages/foo/index]]` or `[[packages/foo/index]]` interchangeably depending on viewer. v1.8 rewriter handles both via pattern matching; documented in D-03's grep step.

</deferred>

---

*Phase: 46-Inbound-Link Migration + Cutover*
*Context gathered: 2026-05-27*
