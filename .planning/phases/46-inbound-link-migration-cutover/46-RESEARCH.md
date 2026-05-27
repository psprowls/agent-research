---
phase: 46
phase_slug: inbound-link-migration-cutover
researched: 2026-05-27
status: complete
---

# Phase 46 Research — Inbound-Link Migration + Cutover

> Grounded in code that exists today (Phases 42 + 43 landed; Phase 44 plans committed but executor not yet run; Phase 45 planner running in parallel). Where Phase 46 calls into Phase 44/45 surfaces, the contract from `.planning/phases/44-scanner-generated-index/44-CONTEXT.md` and `.planning/phases/45-scanner-integration/45-CONTEXT.md` is authoritative — those phases' executors deliver the surfaces Phase 46 depends on. Phase 46 itself ships in a separate commit downstream of both.

## RESEARCH COMPLETE

---

## 1. Code surface that Phase 46 must build

### 1.1 New module: `packages/wiki-io/src/wiki_io/link_rewriter.py`

Primary deliverable. ~250–350 LOC total, split across:

- `build_rewrite_table(conn: sqlite3.Connection, wiki_root: Path, *, log_path: Path | None = None) -> dict[str, str | None]`
  Three-source mapping pipeline (CONTEXT D-03). Returns mapping `old_target -> new_slug` where `None` value = "discovered as inbound but unresolvable; rewriter SKIPS rather than rewriting to a wrong destination."

- `rewrite_text(text: str, table: dict[str, str | None]) -> tuple[str, int]`
  Pure function — position-aware code-mask + wikilink rewrite. Returns `(new_text, rewrite_count)`. Importable for tests and future callers.

- `rewrite_vault(wiki_root: Path, table: dict[str, str | None], *, log_path: Path | None = None, lanes: list[Path] | None = None) -> RewriteResult`
  Walks the 5 curated lanes (default: `wiki/concepts/`, `wiki/adrs/`, `wiki/architecture/`, `wiki/sources/`, workspace-rooted `work/`); applies `rewrite_text` per file; writes atomically via temp-file + `os.replace`. Logs per-file change counts to `.graph-wiki/migration.log` (JSONL). `lanes` override is for tests; production passes None and uses the default list. **(CONTEXT D-13.)**

- `@dataclass(frozen=True) class RewriteResult`
  `files_scanned: int`, `files_modified: int`, `rewrites_total: int`, `unresolved_total: int`, `per_file: dict[str, int]`. Matches Phase 43/44/45 result-dataclass convention (CONTEXT §code_context).

- Module-level constants:
  `CURATED_LANES_REL: tuple[str, ...] = ("wiki/concepts", "wiki/adrs", "wiki/architecture", "wiki/sources", "work")` — workspace-rooted relative paths.
  `OLD_LAYOUT_PREFIXES: tuple[str, ...] = ("packages/", "dependencies/", "domain/", "plugin/", "package-family/", "test-suites/", "wiki/packages/", "wiki/dependencies/", "wiki/domain/", "wiki/plugin/", "wiki/package-family/", "wiki/test-suites/")` — both `wiki/`-prefixed and bare forms per CONTEXT deferred §"Wikilink target normalization."

### 1.2 New CLI subcommand: `agents/graph-wiki-agent/src/graph_wiki_agent/commands/migrate_vault.py`

Path matches existing `commands/` layout (CONTEXT D-15; mirrors `commands/init.py`, `commands/scan.py`). Registered in `cli.py` as `@app.command("migrate-vault")` (mirrors how `scan`, `init`, `lint` are registered as flat top-level commands — NOT a Typer subapp). Flags:

- `--dry-run` (bool, default False) — print preview; touch no files.
- `--force` (bool, default False) — bypass idempotency check.
- `--no-write-marker` (bool, default False, hidden) — testing only; suppresses manifest write so a real cutover can be exercised end-to-end against a throwaway vault without polluting STATE.
- No other flags. Workspace is resolved via `wiki_io._workspace.resolve_wiki_and_repo` (same as `scan.py`).

CLI command body is a thin shell over `run_migrate_vault(dry_run, force, write_marker, *, workspace_path=None) -> int` (exit code) in `commands/migrate_vault.py`. The function is async-free (sync subprocess + sync filesystem). All exit codes follow `graph_io.exit_codes` conventions:
- 0 — success, or already-migrated no-op
- 1 — pre-flight failure (no graph DB, no wiki dir, etc.)
- 2 — runtime failure mid-cutover (write_entities raised, link_rewriter raised, git rm failed, etc.) — aborts BEFORE commit per CONTEXT D-07.

### 1.3 Possibly extended: `packages/wiki-io/src/wiki_io/lint/common.py`

CONTEXT mentions `lint/common.py` may be extended with additional code-mask helpers (non-breaking). Existing patterns already cover most cases:

- `FENCED_CODE_RE = re.compile(r"```.*?```", re.DOTALL)` — greedy match on triple-backtick fences.
- `INLINE_CODE_RE = re.compile(r"\`[^\`\n]*\`")` — single-line inline-code.
- `WIKILINK_RE = re.compile(r"\[\[((?:(?!\\\|)[^\]|#])+)(?:#[^\]|]*)?(?:\\?\|[^\]]*)?\]\]")` — captures target as group(1); anchor/alias are non-capturing in group form. Note the table-cell escape handling — this matters: rewriter must preserve the `\|` form when alias is escaped (table contexts).

**Gap to fill:** lint/common.py has NO indented-code-block detector. Plan adds:
- `INDENTED_CODE_RE = re.compile(r"(?m)^(?: {4}|\t).*$")` paired with a small helper to merge runs of consecutive indented lines preceded by a blank line. This is a NEW helper in `lint/common.py`; named `indented_code_spans(text: str) -> list[tuple[int, int]]`.

This is the only addition to lint/common.py. It is non-breaking: existing lint callers (`lint_wiki.py`, `lint_wiki_table.py`) don't import the new helper.

### 1.4 ROADMAP.md amendment

ROADMAP.md Phase 46 SC#1 currently reads:
> Wikilinks in `/concepts/`, `/adrs/`, and `/architecture/` that reference old layout paths (...) are rewritten to new entity slugs (...) with display aliases preserved

Per CONTEXT D-13, plan must amend SC#1 to add `/sources/` and `/work/`:
> Wikilinks in `/concepts/`, `/adrs/`, `/architecture/`, `/sources/`, and `/work/` that reference old layout paths (...) are rewritten to new entity slugs (...) with display aliases preserved

SC#4 already lists package-family for removal — keep unchanged per CONTEXT D-05.

### 1.5 REQUIREMENTS.md possible clarification

REQUIREMENTS.md MIGRATION-05 currently:
> Cutover commit consolidates: `write_entities` populates `wiki/entities/`, `rewrite_links` rewrites `/concepts/`, `/adrs/`, `/architecture/` wikilinks, old directories (...) are removed via `git rm -r`, and `generate_index` produces the new index — all in a single atomic commit

Per CONTEXT D-06, the cutover has 7 ordered steps; D-13 expands lanes to 5; D-06 step 5 adds `update_index.update_index(wiki_root)` for per-folder sub-indexes. Plan rewrites MIGRATION-05 to:
> Cutover commit consolidates: (1) `write_entities` populates `wiki/entities/`, (2) `link_rewriter.rewrite_vault` rewrites wikilinks in all 5 curated lanes (`/concepts/`, `/adrs/`, `/architecture/`, `/sources/`, `/work/`), (3) old directories (`wiki/packages/`, `wiki/dependencies/`, `wiki/domain/`, `wiki/plugin/`, `wiki/package-family/`) are removed via `git rm -r`, (4) `generate_index.generate_index` produces `wiki/index.md`, (5) `update_index.update_index` regenerates per-folder sub-indexes, (6) `.graph-wiki/manifest.json` idempotency marker is written — all in a single atomic commit. The cutover script aborts before commit if any step fails.

### 1.6 Tests (new files)

- `packages/wiki-io/tests/test_link_rewriter.py` — unit tests for `rewrite_text` (code-region exclusion fixtures, alias/anchor preservation, byte-identical assertions). ~12–15 tests.
- `packages/wiki-io/tests/test_link_rewriter_build_table.py` — unit tests for `build_rewrite_table` (three-source merging, dedup, unresolvable handling).
- `packages/wiki-io/tests/integration/test_link_rewriter_integration.py` — end-to-end against a fixture vault: build table, rewrite all curated lanes, assert known wikilinks rewritten correctly, assert code-block fixtures unchanged.
- `agents/graph-wiki-agent/tests/test_migrate_vault.py` — CLI tests: `--dry-run` output sections, full cutover writes manifest marker, second run is a no-op, `--force` recovery, `--no-write-marker` works.

---

## 2. Validation Architecture

This section is consumed by step 5.5 to create `46-VALIDATION.md`. It defines the per-task validation contract.

### 2.1 Test framework

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + syrupy 5.x (snapshot for `--dry-run` output) |
| **Config file** | `pyproject.toml` per package (existing) |
| **Quick run command** | `uv run --package wiki-io pytest packages/wiki-io/tests -x -k link_rewriter` |
| **Full suite command** | `uv run pytest` (root, all workspace members) |
| **Estimated runtime** | ~10 seconds quick, ~3 minutes full |

### 2.2 Sampling rate

- After every task commit: `uv run --package <pkg> pytest <focused_test_file> -x`
- After every plan wave: quick suite for changed packages
- Before `/gsd:verify-work`: full suite green
- Max feedback latency: ~10s for unit tests, ~45s for integration suite

### 2.3 Wave 0 test files

Every new test file is created in Wave 0 within the same task that adds the production code (TDD pattern matches Phase 45). No separate Wave 0 wave needed; pytest infrastructure already present.

- `packages/wiki-io/tests/test_link_rewriter.py` — Plan 01
- `packages/wiki-io/tests/test_link_rewriter_build_table.py` — Plan 02
- `packages/wiki-io/tests/integration/test_link_rewriter_integration.py` — Plan 02
- `agents/graph-wiki-agent/tests/test_migrate_vault.py` — Plan 03

### 2.4 Manual-only verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Dry-run preview against live `agent-research` vault | MIGRATION-05 (qualitative) | Visual gate before the actual cutover; output is the user-facing acceptance gate per CONTEXT §specifics | Run `cg migrate-vault --dry-run` in `agent-research` root; visually verify rewrite table covers expected entities (14 packages, 9 deps, 3 domains, 1 plugin, 7 suites approx); confirm 1 package-family file flagged with `⚠ human content detected` warning |
| Real cutover ships in a single atomic commit | MIGRATION-05 | The cutover IS the user's commit; cannot automate the "did this commit ship" assertion in CI | Run `cg migrate-vault` (no `--dry-run`); inspect `git log -1 --stat`; verify single commit titled `feat(46): v1.8 entity restructure cutover` with files added/removed/modified as described in dry-run preview |

---

## 3. Mapping derivation pipeline (CONTEXT D-03 in detail)

### 3.1 Source 1 — Convention templates per kind

For each admitted kind in v1.8 (5 kinds — `package_family` deferred per D-04, `repository` is wiki-root with no old-layout path):

```python
CONVENTION_TEMPLATES = {
    "package":    "packages/{name}/index",
    "dependency": "dependencies/{ecosystem}/{name}/overview",
    "domain":     "domain/{name}/index",
    "plugin":     "plugin/{name}/overview",
    "test_suite": "test-suites/{name}/index",
}
```

For each `kind` in CONVENTION_TEMPLATES:
- Call `list_fn(conn)` from `graph_io.queries` (e.g. `list_packages`, `list_dependencies`).
- For each node: extract `name = node.name`. For `dependency`, also extract `ecosystem = node.attrs.get("ecosystem")` (NodeRecord.attrs is the dict per Phase 43 query schema).
- Build `old_target = template.format(name=name, ecosystem=ecosystem)`.
- Build `uri = node.attrs.get("uri")` (URI is folded into attrs per `_row_to_node` 6-column path; see queries.py:144-162). The 5 list_* functions all hit the 6-column row shape via `_list_by_kind`, so `uri` is always present.
- Build `new_slug = "entities/" + encode_slug(uri)`.
- Add `(old_target, new_slug)` to the table.
- ALSO add the `wiki/`-prefixed form: `(f"wiki/{old_target}", new_slug)` — wikilinks in some vaults use the absolute form per CONTEXT deferred §"Wikilink target normalization."

### 3.2 Source 2 — Scan-and-match over old layout directories

Walk the 5 old-layout roots under `wiki/`:

```python
OLD_LAYOUT_ROOTS = ("packages", "dependencies", "domain", "plugin", "package-family")
```

For each `.md` file under `wiki/<root>/`:
- Compute `old_target = str(path.relative_to(wiki_root).with_suffix(""))` — e.g. `packages/graph-io/index`.
- Extract entity name. For `packages/`: name is `path.parent.name` (e.g. `graph-io` from `packages/graph-io/index.md`). For `dependencies/`: name is `path.parent.name`, ecosystem is `path.parent.parent.name`. For `domain/`: name is `path.parent.name`. For `plugin/`: name is `path.parent.name`. For `package-family/`: skip per D-04 (no graph entity match expected).
- Look up the graph entity by `(kind, name[, ecosystem])`:
  - Use `_list_by_kind` directly OR iterate the kind's list output and match by `node.name` (+ ecosystem for deps).
  - In-memory map built once at start: `by_kind_name = {kind: {name: node for node in list_fn(conn)}}`.
- If matched, add `(old_target, new_slug)` to the table.
- If NOT matched (orphan vault page with no corresponding graph entity), leave the entry uncovered. Source 3 may pick it up via inbound links; if not, the page is in a doomed directory anyway (Step 3 of cutover removes the dir).

The wiki/-prefixed and bare forms are BOTH added.

### 3.3 Source 3 — Grep curated lanes for inbound links

For each curated lane (`wiki/concepts/`, `wiki/adrs/`, `wiki/architecture/`, `wiki/sources/`, `work/`):

- Walk all `.md` files.
- For each file, `text = path.read_text(encoding="utf-8")`.
- Mask code regions (D-01) — same algorithm as `rewrite_text` but discard output; we want non-code regions only.
- Iterate `WIKILINK_RE` matches in non-code regions.
- For each match, extract `target = m.group(1).strip()`.
- If `target` starts with any of the OLD_LAYOUT_PREFIXES (see §1.1), try to look up its new slug:
  - If already in table from Source 1 or 2: skip (already covered).
  - Else, attempt to derive name from path (best-effort, same logic as Source 2). If derivation finds a graph entity, add `(target, new_slug)`.
  - Else, add `(target, None)` to the table — marks it as "discovered as inbound but unresolvable" — AND log a JSONL line to migration.log with `{"phase": "unresolved", "file": <file>, "target": <target>}`.

### 3.4 Merge + dedup + return

The final `dict[str, str | None]` is the merged table. Source 1 + Source 2 entries should never conflict (both derive from the same graph + filesystem). If they do (defensive), Source 1 wins (graph-canonical). Source 3 fills gaps and adds None entries for unresolvable.

---

## 4. `rewrite_text` algorithm (CONTEXT D-01 in detail)

```python
def rewrite_text(text: str, table: dict[str, str | None]) -> tuple[str, int]:
    """Rewrite old-layout wikilinks to new-layout slugs in `text`.

    Returns (new_text, rewrite_count).
    Wikilinks inside code regions (fenced, inline, indented) are NOT rewritten.
    Wikilinks whose target maps to None in `table` are NOT rewritten (logged elsewhere).
    Alias (`|alias`) and anchor (`#anchor`) suffixes are preserved verbatim.
    """
    # 1. Build code-region spans (sorted by start).
    spans = _code_region_spans(text)  # list[tuple[int, int]]

    # 2. Walk WIKILINK_RE matches; for each non-code match whose target is in table,
    #    splice replacement.
    parts: list[str] = []
    cursor = 0
    count = 0
    for m in WIKILINK_RE.finditer(text):
        if _is_inside_any_span(m.start(), spans):
            continue
        target = m.group(1).strip()
        new_slug = table.get(target)
        if new_slug is None:  # missing key OR explicit None (unresolvable)
            continue
        # Splice up to match start, then rebuilt link, then advance cursor.
        parts.append(text[cursor:m.start()])
        # Reconstruct: [[<new_slug><preserved-anchor><preserved-alias>]]
        rebuilt = _rebuild_wikilink(m.group(0), target, new_slug)
        parts.append(rebuilt)
        cursor = m.end()
        count += 1
    parts.append(text[cursor:])
    return ("".join(parts), count)
```

Helpers:
- `_code_region_spans(text)`: union of fenced, inline, and indented-code regions. Algorithm:
  1. Find all `FENCED_CODE_RE` matches → spans.
  2. From the inverted text (non-fenced regions only), find `INLINE_CODE_RE` matches → translate back to absolute positions → spans.
  3. Find indented-code spans (consecutive lines starting with 4-space-or-tab indent, preceded by a blank line) — new helper `indented_code_spans` from §1.3.
  4. Merge overlapping spans, sort by start.
- `_is_inside_any_span(pos, spans)`: binary-search or linear-scan. Linear is fine for short docs.
- `_rebuild_wikilink(original, old_target, new_slug)`: take the original `[[...]]` string, replace `old_target` with `new_slug` while preserving everything else. Implementation: `original.replace(old_target, new_slug, 1)` works because the match guarantees `old_target` appears exactly once in the wikilink (anchors and aliases don't overlap).

### Code-region edge cases

| Case | Behavior |
|------|----------|
| Wikilink inside fenced block | Skipped — byte-identical after migration |
| Wikilink inside inline code | Skipped — byte-identical |
| Wikilink inside indented code block (4-space/tab, preceded by blank line) | Skipped — byte-identical |
| Nested fences (e.g. ` ```` ` outer with `` ``` `` inner) | LIMITED handling: outer fence is detected; inner content masked along with outer. Documented v1.8 limitation per CONTEXT D-02 |
| Lazy-continuation prose (wikilink on line immediately after fence close, no blank line) | Tested — wikilink IS rewritten (CommonMark says line is paragraph continuation, not code) |
| Wikilink with anchor: `[[packages/foo/index#api]]` | Anchor preserved: `[[entities/pkg__org__foo#api]]` |
| Wikilink with alias: `[[packages/foo/index\|foo]]` | Alias preserved: `[[entities/pkg__org__foo\|foo]]` |
| Wikilink with both: `[[packages/foo/index#api\|foo API]]` | Both preserved |
| Wikilink with escaped table-cell alias: `[[packages/foo/index\\\|foo]]` | The escaped `\|` form is preserved verbatim (WIKILINK_RE handles this) |

---

## 5. Cutover orchestration (CONTEXT D-06 + D-07 in detail)

The 7-step composition lives in `commands/migrate_vault.py::run_migrate_vault`. Implementation skeleton:

```python
def run_migrate_vault(
    dry_run: bool,
    force: bool,
    write_marker: bool,
    *,
    workspace_path: Path | None = None,
) -> int:
    wiki_root, repo_root = resolve_wiki_and_repo(workspace_path)
    workspace_root = wiki_root.parent
    manifest_path = workspace_root / ".graph-wiki" / "manifest.json"
    log_path = workspace_root / ".graph-wiki" / "migration.log"

    # Step 0: Idempotency guard (CONTEXT D-09) — FIRST step.
    if not force:
        if _is_already_migrated(manifest_path):
            print("Vault is already migrated. Use --force to re-run (not recommended).")
            return 0
    else:
        # --force "marker present but dirs still exist" detection (D-10).
        if _is_clean_post_migration(manifest_path, wiki_root):
            print("Vault is already cleanly migrated. --force has no effect.")
            return 0

    # Step 0.5: Open DB conn (read-only).
    conn = _open_graph_db(workspace_root)

    # Step 1: Build rewrite table.
    table = link_rewriter.build_rewrite_table(conn, wiki_root, log_path=log_path)

    # Pre-flight dry-run output (always computed; printed iff --dry-run).
    preview = _build_preview(conn, wiki_root, table)
    if dry_run:
        _print_preview(preview)
        return 0

    # Step 2: write_entities (CONTEXT D-06 step 1).
    try:
        write_result = entity_writer.write_entities(conn, wiki_root, ADMITTED_KINDS_V18)
    except Exception as e:
        print(f"[error] write_entities failed: {e}", file=sys.stderr)
        return 2

    # Step 3: link_rewriter.rewrite_vault (CONTEXT D-06 step 2).
    try:
        rewrite_result = link_rewriter.rewrite_vault(wiki_root, table, log_path=log_path)
    except Exception as e:
        print(f"[error] link_rewriter failed: {e}", file=sys.stderr)
        return 2

    # Step 4: git rm -r old directories (CONTEXT D-06 step 3).
    try:
        _git_rm_old_dirs(repo_root, wiki_root)
    except subprocess.CalledProcessError as e:
        print(f"[error] git rm failed: {e}", file=sys.stderr)
        return 2

    # Step 5: generate_index (CONTEXT D-06 step 4).
    try:
        index_generator.generate_index(conn, wiki_root)
    except Exception as e:
        print(f"[error] generate_index failed: {e}", file=sys.stderr)
        return 2

    # Step 6: update_index for per-folder sub-indexes (CONTEXT D-06 step 5).
    try:
        update_index.update_index(wiki_root)
    except Exception as e:
        print(f"[error] update_index failed: {e}", file=sys.stderr)
        return 2

    # Step 7: Manifest marker (CONTEXT D-06 step 6).
    if write_marker:
        try:
            _write_manifest(manifest_path, rewrite_result)
        except Exception as e:
            print(f"[error] manifest write failed: {e}", file=sys.stderr)
            return 2

    # Step 8: Commit (CONTEXT D-06 step 7).
    try:
        _git_commit_cutover(repo_root)
    except subprocess.CalledProcessError as e:
        print(f"[error] git commit failed: {e}", file=sys.stderr)
        return 2

    print(f"Cutover complete: {rewrite_result.files_modified} files modified, "
          f"{rewrite_result.rewrites_total} wikilinks rewritten, "
          f"{rewrite_result.unresolved_total} unresolvable (logged).")
    return 0
```

### Failure semantics (CONTEXT D-07)

Each step's exception causes immediate abort with exit code 2. NO partial commit — `_git_commit_cutover` is the LAST step. If step 4 (`git rm`) succeeds but step 5 (`generate_index`) fails, the working tree has staged deletions + no `wiki/index.md` regen; the script exits 2 without committing; user runs `git restore --staged .` and `git restore .` to recover, then re-runs the cutover.

For step 7 (manifest write failure), the working tree is already fully prepared; recovery is trivial (`git restore --staged .graph-wiki/manifest.json` if it was staged; the cutover hasn't committed yet).

For step 8 (commit failure — pre-commit hook rejection, etc.), staged tree is intact; user can fix the hook issue and re-run `git commit` manually OR run `cg migrate-vault --force` to redo from scratch.

### `_git_rm_old_dirs` details

```python
def _git_rm_old_dirs(repo_root: Path, wiki_root: Path) -> None:
    targets = []
    for dir_name in ("packages", "dependencies", "domain", "plugin", "package-family"):
        dir_path = wiki_root / dir_name
        if dir_path.exists():
            targets.append(str(dir_path.relative_to(repo_root)))
    if not targets:
        return  # nothing to remove (already removed by a prior run that crashed mid-cutover)
    subprocess.run(
        ["git", "rm", "-r", *targets],
        cwd=repo_root,
        check=True,
    )
```

`check=True` raises `CalledProcessError` on non-zero exit — caller catches and returns exit code 2.

### `_git_commit_cutover` details

```python
COMMIT_MESSAGE = """feat(46): v1.8 entity restructure cutover

Atomic vault migration:
- Populate wiki/entities/ via write_entities
- Rewrite inbound wikilinks across 5 curated lanes
- Remove wiki/packages/, wiki/dependencies/, wiki/domain/, wiki/plugin/, wiki/package-family/
- Regenerate wiki/index.md (generate_index) + per-folder sub-indexes (update_index)
- Write .graph-wiki/manifest.json migration marker

Refs: MIGRATION-01, MIGRATION-02, MIGRATION-03, MIGRATION-04, MIGRATION-05
"""

def _git_commit_cutover(repo_root: Path) -> None:
    # Stage everything that was modified/created since the cutover started.
    subprocess.run(["git", "add", "-A"], cwd=repo_root, check=True)
    subprocess.run(
        ["git", "commit", "-m", COMMIT_MESSAGE],
        cwd=repo_root,
        check=True,
    )
```

Pre-commit hooks run normally (no `--no-verify`). If a hook fails, `commit` exits non-zero → `CalledProcessError` → exit code 2.

---

## 6. Idempotency marker (CONTEXT D-08, D-09, D-10)

### 6.1 File shape

`.graph-wiki/manifest.json` — new file in v1.8. Phase 43 has `deletions.log` (JSONL, different shape); Phase 45 has `scan.lock` (binary fcntl lock); neither is the manifest. Phase 46 creates the manifest fresh.

```json
{
  "migrated_to": "v1.8-entity-restructure",
  "migrated_at": "2026-05-27T18:00:00Z",
  "rewrite_count": 47,
  "rewrite_unresolved": 2
}
```

Future migrations can add a separate `migrations: [...]` list field if needed; v1.8 only has one migration so the flat key is enough (CONTEXT D-08).

### 6.2 Idempotency check (Step 0)

```python
def _is_already_migrated(manifest_path: Path) -> bool:
    if not manifest_path.exists():
        return False
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False  # treat corrupt manifest as "not migrated" so re-run can fix it
    return manifest.get("migrated_to") == "v1.8-entity-restructure"
```

### 6.3 `--force` detection (CONTEXT D-10)

```python
def _is_clean_post_migration(manifest_path: Path, wiki_root: Path) -> bool:
    """True when marker is present AND no old layout dirs remain on disk.
    --force is a no-op in this state."""
    if not manifest_path.exists():
        return False
    old_dirs = ("packages", "dependencies", "domain", "plugin", "package-family")
    any_remain = any((wiki_root / d).exists() for d in old_dirs)
    return not any_remain  # clean iff manifest present AND no old dirs
```

If marker present BUT old dirs exist (partial-cutover recovery scenario), `--force` proceeds with the cutover. The `link_rewriter` step will be a near-no-op (entities already match graph), `git rm` will clean up the leftover dirs, and the manifest is rewritten.

---

## 7. Dry-run output format (CONTEXT D-12)

Plain text to stdout, no ANSI colors (per Claude's-Discretion). Sections:

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

### 7.1 "Human content detected" heuristic

For each `.md` file in the dirs-to-remove list, parse frontmatter and check if any of the following keys are present with non-empty values: `status`, `notes`, `last_reviewed`, `owner`. If yes, surface `⚠ human content detected: <key>: <value> in <file>`. This is best-effort; user is still responsible for the removal (git history is the safety net per CONTEXT §deferred).

### 7.2 Snapshot testing

Dry-run output is snapshotted via syrupy (Phase 42/43 pattern). Fixture vault has deterministic content; snapshot is regenerated with `pytest --snapshot-update` if the format changes.

---

## 8. Migration log shape (CONTEXT D-16)

`.graph-wiki/migration.log` — JSONL, append-only. Mirrors `.graph-wiki/deletions.log` (Phase 43). Three record types:

```json
{"timestamp": "2026-05-27T18:00:01Z", "phase": "rewrite", "file": "wiki/concepts/foo.md", "from": "packages/graph-io/index", "to": "entities/pkg__agent-research__graph-io"}
{"timestamp": "2026-05-27T18:00:01Z", "phase": "unresolved", "file": "wiki/concepts/bar.md", "target": "packages/old-removed/index"}
{"timestamp": "2026-05-27T18:00:01Z", "phase": "remove", "path": "wiki/packages/graph-io/index.md", "had_human_content": false}
```

Reuse Phase 43's `_append_deletion`-style helper. Specifically: a new `_append_migration(log_path, record)` helper in `link_rewriter.py` (or hoist `_append_deletion` to a shared module). Lean: **duplicate the helper** in `link_rewriter.py` — Phase 43's helper is private to `entity_writer.py`; a 10-line copy keeps the contract local and avoids a refactor that's out of scope. (If a future phase introduces a third JSONL log, then hoist.)

No rotation needed for migration.log — it's a one-shot file (only the cutover writes to it); CONTEXT §deferred confirms this.

---

## 9. Test surface details

### 9.1 `test_link_rewriter.py` — unit tests for `rewrite_text`

| Test name | What it asserts |
|-----------|-----------------|
| `test_rewrite_text_basic` | Simple `[[packages/foo/index]] → [[entities/pkg__org__foo]]` works |
| `test_rewrite_text_with_alias` | `[[packages/foo/index\|foo]] → [[entities/pkg__org__foo\|foo]]` |
| `test_rewrite_text_with_anchor` | `[[packages/foo/index#api]] → [[entities/pkg__org__foo#api]]` |
| `test_rewrite_text_with_alias_and_anchor` | Both preserved |
| `test_rewrite_text_skips_fenced_code` | `[[packages/foo/index]]` inside `` ``` `` block — byte-identical |
| `test_rewrite_text_skips_inline_code` | `` `[[packages/foo/index]]` `` — byte-identical |
| `test_rewrite_text_skips_indented_code` | 4-space-indented block preceded by blank line — byte-identical |
| `test_rewrite_text_lazy_continuation_rewrites` | Wikilink on line after fence close with no blank line — IS rewritten |
| `test_rewrite_text_unresolvable_target_skipped` | `table[target] = None` → not rewritten |
| `test_rewrite_text_unknown_target_skipped` | `target not in table` → not rewritten |
| `test_rewrite_text_returns_count` | Count matches number of actual rewrites |
| `test_rewrite_text_wiki_prefix_form` | `[[wiki/packages/foo/index]]` rewrites via the wiki/-prefixed table entry |
| `test_rewrite_text_nested_fence_known_limitation` | Documents v1.8 behavior; either passes or is `xfail` with a clear reason — NOT a hard requirement |
| `test_rewrite_text_idempotent` | Calling `rewrite_text` twice on already-rewritten text — second call rewrites 0 |
| `test_rewrite_text_escaped_alias_pipe` | `[[packages/foo/index\\\|foo]]` (table-cell escape) preserved |

### 9.2 `test_link_rewriter_build_table.py`

| Test name | What it asserts |
|-----------|-----------------|
| `test_build_table_source1_packages` | Fixture graph with 2 packages → table contains both convention-template entries (bare + wiki/-prefixed forms) |
| `test_build_table_source1_dependencies` | Dependencies include ecosystem in path |
| `test_build_table_source1_all_kinds` | All 5 admitted-kind list functions called; package_family NOT in table (per D-04) |
| `test_build_table_source2_scan_match` | Fixture vault has `wiki/packages/foo/index.md`; if foo is in graph, entry added; if not, no entry (and Source 3 may pick it up) |
| `test_build_table_source3_unresolvable_logged` | Fixture vault has `[[packages/totally-fake/index]]` in `wiki/concepts/foo.md`; not in graph → table has `(target, None)`; migration.log has `unresolved` line |
| `test_build_table_dedup_source1_source2` | Same entity surfaces in Source 1 and Source 2 → one entry, no conflict |
| `test_build_table_returns_dict_str_optional_str` | Type contract: `dict[str, str \| None]` |
| `test_build_table_ignores_package_family_directory` | Files under `wiki/package-family/` don't add entries (D-04) |
| `test_build_table_uri_handling` | `node.attrs["uri"]` is consumed correctly; URIs missing from attrs are skipped without error |

### 9.3 `test_link_rewriter_integration.py`

| Test name | What it asserts |
|-----------|-----------------|
| `test_integration_full_rewrite_vault` | Fixture vault with realistic content; build_rewrite_table + rewrite_vault end-to-end; assert known wikilinks rewritten and known code-block fixtures byte-identical |
| `test_integration_logs_per_file_change_counts` | migration.log has one `rewrite` record per actual rewrite |
| `test_integration_returns_RewriteResult_with_correct_counts` | RewriteResult dataclass fields match the actual outcome |
| `test_integration_handles_work_dir_workspace_rooted` | `work/` is at workspace root, not under wiki/; rewriter still finds and rewrites files there |
| `test_integration_wiki_root_files_not_rewritten` | `wiki/index.md` and `wiki/log.md` are NOT in the lane list; running `rewrite_text` on them would be a no-op but `rewrite_vault` doesn't even touch them |

### 9.4 `test_migrate_vault.py` — CLI tests

| Test name | What it asserts |
|-----------|-----------------|
| `test_migrate_vault_dry_run_output_sections` | snapshot test (syrupy): all expected sections present in dry-run output |
| `test_migrate_vault_dry_run_makes_no_changes` | `git status --porcelain` after `--dry-run` is empty |
| `test_migrate_vault_full_cutover_writes_manifest` | After full cutover, `.graph-wiki/manifest.json` exists with `migrated_to: v1.8-entity-restructure` |
| `test_migrate_vault_full_cutover_removes_old_dirs` | After full cutover, `wiki/packages/` etc. are gone |
| `test_migrate_vault_full_cutover_populates_entities` | After full cutover, `wiki/entities/<slug>.md` files exist for all admitted nodes |
| `test_migrate_vault_full_cutover_single_commit` | After full cutover, `git log -1` shows exactly one new commit with the expected title |
| `test_migrate_vault_second_run_no_op` | Run cutover twice; second invocation prints "already migrated" and exits 0 with no file changes |
| `test_migrate_vault_force_recovery` | Manually write marker but leave `wiki/packages/` present; run without `--force` → exits saying "already migrated"; run with `--force` → completes cleanup |
| `test_migrate_vault_no_write_marker` | `--no-write-marker` runs full cutover but does NOT create `.graph-wiki/manifest.json` |
| `test_migrate_vault_unresolvable_target_left_alone` | Fixture vault has `[[packages/totally-fake/index]]`; after cutover, the wikilink is still there (not rewritten); migration.log has the unresolved entry |
| `test_migrate_vault_aborts_before_commit_on_failure` | Force a mid-cutover failure (e.g. monkeypatch `generate_index` to raise); assert no commit was created and exit code is 2 |
| `test_migrate_vault_help_exits_zero` | `cg migrate-vault --help` exits 0; `--dry-run`, `--force`, `--no-write-marker` flags listed |

---

## 10. Existing project conventions to follow

Per `agent-research/CLAUDE.md` §8 (testing):
- pytest 8.x as runner; `pytest-asyncio` only where the SUT is async (this phase is sync — no async tests needed).
- `syrupy` for snapshot tests (dry-run output).
- Fixture vaults use `tmp_path` per Phase 42/43/44 conventions.
- `@dataclass(frozen=True)` for result types — applies to `RewriteResult`.
- Atomic file writes via temp-file + `os.replace` per Phase 44 D-16.

Per CLAUDE.md §3 (Bedrock integration):
- This phase invokes ZERO LLM calls. No Bedrock dependency. No model-adapter usage.

Per CLAUDE.md §6 (CLI):
- Typer is the CLI framework. `cg` subcommands are registered via `@app.command(...)` decorators on the Typer app in `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py`.
- The `cg` console entry point is defined in `agents/graph-wiki-agent/pyproject.toml` as `[project.scripts]`.

Per project-wide pattern:
- Decision IDs from CONTEXT.md (D-01..D-16) appear in `must_haves.truths` of the relevant plan as `"D-NN: <one-line summary>"` — Phase 45 PLAN files use this format.
- `requirements_addressed` frontmatter lists the MIGRATION-XX IDs each plan addresses.

---

## 11. Plan partitioning recommendation

Three plans, two waves:

- **Wave 1**
  - **Plan 01** — `link_rewriter.py` core (`rewrite_text` + helpers) + `lint/common.py` indented-code helper + unit tests. Pure-function work; no graph or vault dependency. Addresses MIGRATION-01, MIGRATION-04 (code-block exclusion). ~250 LOC + tests.
  - **Plan 02** — `link_rewriter.py` table builder (`build_rewrite_table`) + `rewrite_vault` + JSONL migration log + integration test against fixture vault + REQUIREMENTS.md MIGRATION-05 rewrite + ROADMAP.md SC#1 amendment. Depends on graph queries (read-only). Addresses MIGRATION-02. ~150 LOC + tests + docs.

- **Wave 2**
  - **Plan 03** — `commands/migrate_vault.py` CLI subcommand + cutover orchestration + manifest marker + dry-run preview + CLI tests + register in `cli.py`. Depends on Plan 01 and Plan 02. Addresses MIGRATION-03, MIGRATION-05. ~300 LOC + tests.

Wave-1 plans can run in parallel: Plan 01 touches only `link_rewriter.py` private/pure helpers; Plan 02 adds the table builder + vault walker. They share the file but the additions are in distinct sections; the executor handles the merge by both plans appending into the same module sequentially (no file conflict since the additions are non-overlapping function definitions). Optionally Plan 01 can ship `link_rewriter.py` as a skeleton with `rewrite_text` defined and Plan 02 appends `build_rewrite_table` + `rewrite_vault` below — that's the cleanest sequencing if parallelism causes friction. **The planner picks: serial Wave 1 (01 → 02) OR parallel Wave 1 with shared file.** Recommendation: serial (Plan 01 in Wave 1, Plan 02 in Wave 2, Plan 03 in Wave 3) is safest for the 1-developer-no-team case; revisit if execution lag is a concern.

**Final recommendation:** 3 plans, 3 waves (serial) — each plan ships an internally consistent and independently testable surface. Wave 3 is the integration that pulls Plans 01 + 02 together via the CLI.

---

## 12. Cross-references

- CONTEXT.md `<canonical_refs>` lists the predecessor phases and existing code surfaces — re-read before planning.
- `.planning/research/PITFALLS.md` Pitfalls 4 + 10 (regex over-match; re-run artifacts) — addressed by D-01 + D-02 fixtures and D-08..D-10 idempotency.
- `agent-research/CLAUDE.md` §1, §2, §7, §8 — applicable; this phase introduces NO new third-party deps (D-01 chose regex over markdown-it-py).
