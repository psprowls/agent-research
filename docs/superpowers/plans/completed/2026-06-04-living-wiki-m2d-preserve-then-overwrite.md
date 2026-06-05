# Living Wiki M2d — Preserve-Then-Overwrite Merge + Reconciliation Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Flip `_merge_preserved_sections` from reset-to-placeholder to **preserve-then-overwrite (PTO)** so scanner-owned page sections survive across scans by default, then delete the snapshot/restore machinery and the M2c churn-mask it made redundant.

**Architecture:** On re-scan, the merge keeps each existing scanner-owned section body (matched **by type** via the M2c `_scanner_section_token`, which dodges the `## File map - <slug>` vs `- <basename>` heading-suffix mismatch). The scan pipeline then overwrites only the sections it actually regenerates this scan (narrator prose, deterministic file map). This deletes two snapshot passes + a restore loop in `scan.py`, deletes M2c's `_equal_modulo_scanner`/skip-write in `entity_writer.py`, re-sources file-map `preserved` from the live on-disk page, and closes a placeholder crash-window. A new flag-only lint surfaces the one failure mode PTO can't self-heal (a renamed scanner heading).

**Tech Stack:** Python 3.11+, `python-frontmatter`, `pytest`, `asyncio`. Packages: `packages/wiki-io` (entity writer + lint modules), `packages/graph-wiki-core` (scan command + lint command), `packages/graph-wiki-cli`, `packages/graph-wiki-mcp`. Tests mock the LLM fan-out at the `SubagentPool.run_all` boundary.

---

## Precondition & context (READ FIRST)

**M2c has already landed on `main`** (merge `d2f19481`, 2026-06-04). The spec's "execution gated on M2c" precondition is satisfied; this plan targets current `main`. No rebase coordination is needed — start from `main`.

**Source spec:** `docs/superpowers/specs/2026-06-04-living-wiki-m2d-preserve-then-overwrite-design.md`. Read §1–§5 before starting; this plan implements it.

**Two terms you must keep straight:**
- **"Approach A"** = the *shipped M1 merge* (heading-aware section preservation). Do NOT rename it. Its module comment lives at `entity_writer.py` around the `## Living Wiki M1` banner.
- **"PTO" (preserve-then-overwrite)** = this milestone's *inversion* of the scanner-section branch of that merge. Use "PTO" in all new comments/commits.

**Known pre-existing test debt (NOT introduced by this work — do not chase):** two graph-wiki-core failures predate M2 — `test_scan_decontainerize_parity::test_scan_entities_tree_snapshot` (stale syrupy snapshot) and `test_scan_graph_integration::test_file_map_injected_into_app_entity_page`. Confirm any failure you see is genuinely new against the Task 0 baseline.

**Coupling constraint (spec §7):** Task 1 (PTO rewrite) MUST land before Task 2 (delete snapshot/restore). Deleting the restore machinery while `write_entities` still resets scanner sections would cause content loss. After Task 1, the old snapshot/restore still runs but is harmless and redundant (the restore loop's `extract_narrative(...) is not None` guard skips already-preserved prose); Task 2 then removes it. Each task's commit is independently green.

---

## File Structure

Files created/modified by this plan, with their responsibility:

| File | Action | Responsibility |
|---|---|---|
| `packages/wiki-io/src/wiki_io/entity_writer.py` | Modify | PTO rewrite of `_merge_preserved_sections`; delete `_equal_modulo_scanner` + `_normalize_scanner_bodies`; revert `write_entities` skip-write to a plain `old_bytes == new_bytes` compare. |
| `packages/wiki-io/tests/test_section_merge.py` | Modify | Update M1-era merge assertions to PTO semantics; add heading-suffix + reconciliation tests (§3.3, §5 tests 3 & 11). |
| `packages/wiki-io/tests/test_equal_modulo_scanner.py` | Delete | Unit tests for the deleted helper. |
| `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py` | Modify | Delete `_snapshot_narratives`, `_snapshot_file_map_descriptions`, the M2a restore loop, and the `prior_*` plumbing; add `_live_file_map_descriptions`; re-source `preserved` from the live page in Step 10b / 10b-ts; drop the now-unused `extract_narrative` import. |
| `packages/graph-wiki-core/tests/unit/test_updated_churn.py` | Modify | Update one docstring that references the deleted helper. Tests stay green. |
| `packages/graph-wiki-core/tests/unit/test_m2d_crash_window.py` | Create | §5 test 10 — a mid-pipeline inject failure leaves real scanner content on disk. |
| `packages/wiki-io/src/wiki_io/lint/scanner_heading.py` | Create | §3.4 / D4 — flag entity pages missing an expected scanner-owned section for their kind. |
| `packages/wiki-io/tests/test_lint_scanner_heading.py` | Create | §5 test 12 — missing-heading flagged, well-formed page not. |
| `packages/graph-wiki-core/src/graph_wiki_core/commands/lint.py` | Modify | Wire `check_scanner_heading` into `_module_pass`; add `scanner_heading_drift` to `LintResult`. |
| `packages/graph-wiki-cli/src/graph_wiki_cli/wiki_cli/main.py` | Modify | Render the new lint section. |
| `packages/graph-wiki-mcp/src/graph_wiki_mcp/server.py` | Modify | Expose the new field on `WikiLintOutput`. |

---

## Task 0: Establish the baseline

**Files:** none (verification only)

- [ ] **Step 1: Confirm you are on `main` at the M2c merge**

Run:
```bash
git -C /Users/pat/Personal/agent-research log --oneline -1
```
Expected: the HEAD line shows `d2f19481 Merge living-wiki-m2c: commit-gate consolidation` (or a later commit if other work landed). If you are on a feature branch, create the M2d branch from `main` first:
```bash
git -C /Users/pat/Personal/agent-research checkout -b living-wiki-m2d main
```

- [ ] **Step 2: Record the green/known-red baseline for the two affected suites**

Run:
```bash
cd /Users/pat/Personal/agent-research
uv run pytest packages/wiki-io/tests packages/graph-wiki-core/tests/unit -q 2>&1 | tail -25
```
Expected: passes EXCEPT the two known-pre-existing failures named above (they live in `packages/graph-wiki-core/tests/` integration files, not `tests/unit/`, so this command may not even hit them — that's fine). Note the exact pass count; you will compare against it after each task.

---

## Task 1: PTO rewrite of `_merge_preserved_sections` + remove the M2c churn-mask

**Files:**
- Modify: `packages/wiki-io/src/wiki_io/entity_writer.py`
- Modify: `packages/wiki-io/tests/test_section_merge.py`
- Delete: `packages/wiki-io/tests/test_equal_modulo_scanner.py`

The merge currently lives just below the `## Living Wiki M1` banner. `_scanner_section_token` (the per-type classifier we reuse) is defined right above `_normalize_scanner_bodies`. We keep `_scanner_section_token`; we delete `_normalize_scanner_bodies` and `_equal_modulo_scanner`.

- [ ] **Step 1: Write the failing PTO unit tests**

Open `packages/wiki-io/tests/test_section_merge.py`. **Replace** the two M1-era assertion tests that PTO inverts — `test_merge_preserves_human_section_and_regenerates_scanner_section` and `test_merge_file_map_is_scanner_owned` — with the PTO versions below, and **add** the heading-suffix test. Leave `test_is_scanner_owned_heading_*`, `test_split_h2_sections_*`, `test_merge_identity_is_stable`, `test_merge_appends_user_added_custom_section`, and `test_merge_with_empty_existing_returns_template` unchanged (they still hold under PTO).

Also update the import line to pull in `_scanner_section_token` for the new test's intent comment (not strictly required, but keep imports tidy):

```python
from wiki_io.entity_writer import (
    _is_scanner_owned_heading,
    _merge_preserved_sections,
    _split_h2_sections,
)
```

Replace the two inverted tests with:

```python
def test_merge_pto_preserves_scanner_section_body_and_human_section() -> None:
    """PTO: a scanner-owned section's EXISTING body survives the merge (it is
    overwritten later only by the inject steps that regenerate it). Human
    sections are still preserved; the template placeholder is NOT re-imposed."""
    template = (
        "# T\n\n## Narrative\n_(placeholder)_\n\n## Purpose\n> TODO: fill me\n"
    )
    existing = (
        "# T\n\n## Narrative\nOLD NARRATIVE PROSE\n\n## Purpose\nReal human purpose.\n"
    )
    out = _merge_preserved_sections(template, existing)
    assert "Real human purpose." in out          # human section preserved
    assert "OLD NARRATIVE PROSE" in out           # PTO: existing scanner body kept
    assert "_(placeholder)_" not in out           # PTO: template placeholder NOT re-imposed
    assert "> TODO: fill me" not in out           # template Purpose overwritten by human


def test_merge_pto_preserves_file_map_body() -> None:
    """PTO: the existing `## File map` body is preserved across the merge."""
    template = "# T\n\n## File map - foo\n> TODO\n\n## Purpose\n> TODO\n"
    existing = "# T\n\n## File map - foo\n| a | b | c |\n\n## Purpose\nKeep me.\n"
    out = _merge_preserved_sections(template, existing)
    assert "Keep me." in out                       # human Purpose preserved
    assert "| a | b | c |" in out                  # PTO: existing file map preserved


def test_merge_pto_matches_file_map_by_type_despite_heading_suffix() -> None:
    """[spec §5 test 3] The template renders `## File map - <slug>` while the
    on-disk page carries `## File map - <basename>` (the injector's last-writer
    form). PTO must match by section TYPE, so the existing filled basename
    section is preserved and the slug-suffixed template slot is discarded."""
    template = (
        "# T\n\n## Narrative\n_(placeholder)_\n\n"
        "## File map - pkg_pkg-a\n> TODO: <Overview>\n\n"
        "### pkg_pkg-a/\n| `<file>` | file | — TODO |\n"
    )
    existing = (
        "# T\n\n## Narrative\nreal prose\n\n"
        "## File map - pkg-a\n### pkg-a/\n| `mod.py` | file | does a thing |\n"
    )
    out = _merge_preserved_sections(template, existing)
    assert "## File map - pkg-a" in out            # existing (basename) heading kept
    assert "## File map - pkg_pkg-a" not in out     # slug-suffixed template slot dropped
    assert "does a thing" in out                    # filled rows preserved
    assert "— TODO" not in out                       # template placeholder rows discarded
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run:
```bash
cd /Users/pat/Personal/agent-research
uv run pytest packages/wiki-io/tests/test_section_merge.py -q
```
Expected: FAIL — `test_merge_pto_preserves_scanner_section_body_and_human_section`, `test_merge_pto_preserves_file_map_body`, and `test_merge_pto_matches_file_map_by_type_despite_heading_suffix` fail because the current merge resets scanner sections to the template placeholder (e.g. `assert "OLD NARRATIVE PROSE" in out` fails).

- [ ] **Step 3: Rewrite `_merge_preserved_sections` for PTO**

In `packages/wiki-io/src/wiki_io/entity_writer.py`, replace the body of `_merge_preserved_sections` (keep the signature). The new version classifies existing sections into human-by-heading and scanner-by-type, and for each template scanner slot takes the existing same-type body when present:

```python
def _merge_preserved_sections(template_body: str, existing_body: str) -> str:
    """Merge an existing page's content into ``template_body`` (PTO).

    Preserve-then-overwrite: each scanner-owned section
    (``_is_scanner_owned_heading``) takes its body from the existing page when
    the page already has a section of that **type** (matched via
    ``_scanner_section_token`` — this is what dodges the `## File map - <slug>`
    vs `- <basename>` heading-suffix mismatch); otherwise it falls back to the
    template placeholder (newly-created page, or a scanner section newly added
    to the template). The scan pipeline overwrites a scanner section's body
    only when it actually regenerates it this scan.

    Human/user sections are unchanged from the M1 merge: a human heading that
    appears in ``existing_body`` replaces the template's version; sections
    present only in ``existing_body`` (user-added) are appended in their
    original order. The preamble (H1 + intro) always comes from the template.

    Idempotent: ``_merge_preserved_sections(t, t) == t`` because the split is
    lossless and each section round-trips (scanner by type, human by heading).
    """
    pre_t, secs_t = _split_h2_sections(template_body)
    _pre_e, secs_e = _split_h2_sections(existing_body)

    existing_by_heading: dict[str, str] = {}
    existing_scanner_by_token: dict[str, str] = {}
    for heading, chunk in secs_e:
        if _is_scanner_owned_heading(heading):
            existing_scanner_by_token.setdefault(
                _scanner_section_token(heading), chunk
            )  # first occurrence wins
        else:
            existing_by_heading.setdefault(heading, chunk)  # first occurrence wins

    out = [pre_t]
    template_headings: set[str] = set()
    consumed: set[str] = set()
    for heading, chunk in secs_t:
        template_headings.add(heading)
        if _is_scanner_owned_heading(heading):
            # PTO: preserve the existing same-type scanner body; else placeholder.
            token = _scanner_section_token(heading)
            out.append(existing_scanner_by_token.get(token, chunk))
        elif heading in existing_by_heading:
            out.append(existing_by_heading[heading])
            consumed.add(heading)
        else:
            out.append(chunk)

    # Preserve user-added sections the template does not define.
    for heading, chunk in secs_e:
        if (
            heading in template_headings
            or heading in consumed
            or _is_scanner_owned_heading(heading)
        ):
            continue
        consumed.add(heading)
        out.append(chunk)

    return "".join(out)
```

- [ ] **Step 4: Run the merge tests to verify they pass**

Run:
```bash
cd /Users/pat/Personal/agent-research
uv run pytest packages/wiki-io/tests/test_section_merge.py -q
```
Expected: PASS (all tests in the file).

- [ ] **Step 5: Delete `_normalize_scanner_bodies` and `_equal_modulo_scanner`**

In `entity_writer.py`, delete both functions in full. `_normalize_scanner_bodies` starts at `def _normalize_scanner_bodies(body: str) -> str:` and `_equal_modulo_scanner` is the function immediately after it (`def _equal_modulo_scanner(old_text: str, new_text: str) -> bool:`), ending just before `def _merge_preserved_sections`. Keep `_scanner_section_token` (it sits above them and is now used by the PTO merge). Remove the two functions and the blank lines between them, leaving a single blank-line gap between `_scanner_section_token` and `_merge_preserved_sections`.

- [ ] **Step 6: Revert the `write_entities` skip-write to a plain byte compare**

In `entity_writer.py`, inside `write_entities`, find the `if existed:` branch. It currently reads:

```python
                    if existed:
                        old_bytes = page_path.read_bytes()
                        # M2c #3 (Approach B): absorb scanner-body churn. The
                        # three scanner-owned sections are reset to placeholders
                        # in `new_content` and re-populated by later scan steps;
                        # a page whose only differences are inside those sections
                        # is `unchanged` — skip the write so the real on-disk
                        # body (filled by a prior scan) is left untouched.
                        if old_bytes == new_bytes:
                            unchanged.append(uri)
                            continue
                        try:
                            old_text = old_bytes.decode("utf-8")
                        except UnicodeDecodeError:
                            old_text = None
                        if old_text is not None and _equal_modulo_scanner(
                            old_text, new_content
                        ):
                            unchanged.append(uri)
                            continue
                        page_path.write_text(new_content, encoding="utf-8")
                        page_path.chmod(0o644)
                        updated.append(uri)
                        if _detect_structural_change(existing_fm, merged_fm):
                            needs_narrative.add(uri)
```

Replace it with:

```python
                    if existed:
                        old_bytes = page_path.read_bytes()
                        # PTO: write_entities no longer resets scanner sections
                        # to placeholders (the merge preserves them), so a no-op
                        # rescan renders byte-identical content and the plain
                        # compare buckets it `unchanged`. (M2c #3's
                        # _equal_modulo_scanner skip-write absorbed the reset
                        # churn; PTO removes the reset, so the helper is gone.)
                        if old_bytes == new_bytes:
                            unchanged.append(uri)
                            continue
                        page_path.write_text(new_content, encoding="utf-8")
                        page_path.chmod(0o644)
                        updated.append(uri)
                        if _detect_structural_change(existing_fm, merged_fm):
                            needs_narrative.add(uri)
```

- [ ] **Step 7: Delete the obsolete unit-test file**

Run:
```bash
cd /Users/pat/Personal/agent-research
git rm packages/wiki-io/tests/test_equal_modulo_scanner.py
```

- [ ] **Step 8: Verify the deleted symbols have no remaining references in source**

Run:
```bash
cd /Users/pat/Personal/agent-research
grep -rn "_equal_modulo_scanner\|_normalize_scanner_bodies" --include="*.py" packages | grep -v "/tests/"
```
Expected: NO output (empty). If anything prints, it is a leftover reference — remove it before continuing.

- [ ] **Step 9: Run the full wiki-io suite**

Run:
```bash
cd /Users/pat/Personal/agent-research
uv run pytest packages/wiki-io/tests -q 2>&1 | tail -15
```
Expected: PASS. (If any other test asserted the old reset behavior, update it to PTO semantics — but the grep in Task 0 confirmed `test_section_merge.py` and `test_equal_modulo_scanner.py` were the only merge-helper consumers.)

- [ ] **Step 10: Commit**

```bash
cd /Users/pat/Personal/agent-research
git add packages/wiki-io/src/wiki_io/entity_writer.py packages/wiki-io/tests/test_section_merge.py
git commit -m "feat(entity-writer): preserve-then-overwrite scanner sections (M2d §3.1)

Flip _merge_preserved_sections from reset-to-placeholder to PTO: scanner
sections take their existing body matched by type via _scanner_section_token
(dodges the File map heading-suffix mismatch). Delete _equal_modulo_scanner /
_normalize_scanner_bodies and revert the write_entities skip-write to a plain
byte compare — PTO removes the churn structurally.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Delete the snapshot/restore machinery; re-source `preserved` from the live page

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py`
- Modify: `packages/graph-wiki-core/tests/unit/test_updated_churn.py`

This task is the structural payoff. Under PTO, `write_entities` no longer wipes the File-map body, so the descriptions a prior scan filled are still on disk at Step 10b injection time. We read them live per-page instead of snapshotting all pages before the write, and we delete the narrative snapshot + restore loop entirely (PTO preserves prose for free).

- [ ] **Step 1: Verify the integration tests that pin the end-state are green BEFORE refactoring**

These tests assert PTO's end-state and must stay green through this task — run them now as the safety net:
```bash
cd /Users/pat/Personal/agent-research
uv run pytest packages/graph-wiki-core/tests/unit/test_updated_churn.py \
  packages/graph-wiki-core/tests/unit/test_commit_gated_narrative.py \
  packages/graph-wiki-core/tests/unit/test_commit_gated_file_map.py \
  packages/graph-wiki-core/tests/unit/test_commit_gated_test_suite.py -q 2>&1 | tail -15
```
Expected: PASS (`test_updated_churn.py` is already green from Task 1; the commit-gated suites are green on `main`).

- [ ] **Step 2: Add the `_live_file_map_descriptions` helper**

In `scan.py`, replace the two snapshot helpers — `_snapshot_file_map_descriptions` and `_snapshot_narratives` (they are adjacent, between `_is_init_failure_stderr` and `pick_representative`) — with the single per-page live reader below. Delete BOTH old functions and paste this in their place:

```python
def _live_file_map_descriptions(page_path: Path) -> dict[str, str]:
    """Read filled File-map descriptions from a single entity page's CURRENT
    on-disk `## File map` section, keyed by package-root path.

    Returns ``{}`` when the page is missing, malformed, or has no filled rows.
    PTO replacement for the pre-scan `_snapshot_file_map_descriptions` pass:
    under preserve-then-overwrite, `write_entities` no longer resets the
    File-map body, so at Step 10b injection time the page still holds the
    descriptions a prior scan filled — read them live here instead of
    snapshotting every page before the write.
    """
    try:
        post = frontmatter.load(page_path)
    except Exception:  # noqa: BLE001 — a missing/malformed page must not abort scan
        return {}
    section = FILE_MAP_SECTION_RE.search(post.content)
    if not section:
        return {}
    pkg_name = section.group(1).strip()
    return _extract_file_map_descriptions(section.group(2), pkg_name)
```

(`frontmatter`, `FILE_MAP_SECTION_RE`, and `_extract_file_map_descriptions` are already imported in `scan.py` — keep those imports.)

- [ ] **Step 3: Delete the `prior_*` snapshot locals and their populate block**

In `run_scan`, find this block (it sits just before the `if conn is not None:` that calls `write_entities`):

```python
        # Snapshot prior File-map descriptions BEFORE write_entities re-renders
        # entity pages from template (which wipes the injected File-map body).
        # Keyed by URI so Step 10b can merge them back into the deterministic
        # block, preserving expensive code-reader descriptions across rescans.
        prior_file_map_descs: dict[str, dict[str, str]] = {}
        prior_narratives: dict[str, str] = {}
        if conn is not None:
            prior_file_map_descs = _snapshot_file_map_descriptions(wiki)
            prior_narratives = _snapshot_narratives(wiki)

```

Delete it entirely (including the trailing blank line). The next line (`if conn is not None:` that runs `write_entities`) becomes the first statement after the `commit_dirty` pre-init comment block.

- [ ] **Step 4: Delete the M2a narrative restore loop**

In `run_scan`, find and delete the entire restore block. It begins with the comment `# M2a narrative persistence: restore prior narrative prose for entities` and is the `if conn is not None and prior_narratives:` loop that ends just before the `# Step 10b: deterministic File-map injection` comment. The full block to delete:

```python
        # M2a narrative persistence: restore prior narrative prose for entities
        # NOT re-narrated this scan. write_entities reset every `## Narrative` to
        # the template placeholder (M1 heading-aware merge); without this, prose
        # injected on a prior scan would be wiped whenever the entity is not in
        # needs_narrative. Runs in narrate and --no-narrate scans alike (D-F);
        # never clobbers fresh prose (D-G).
        if conn is not None and prior_narratives:
            narrated_set = set(entities_narrated)
            for page_path in sorted((wiki / "entities").glob("*.md")):
                try:
                    post = frontmatter.load(page_path)
                except Exception:  # noqa: BLE001
                    continue
                restore_uri = post.metadata.get("uri")
                if not restore_uri or restore_uri in narrated_set:
                    continue
                prose = prior_narratives.get(restore_uri)
                if not prose:
                    continue
                if extract_narrative(post.content) is not None:
                    continue  # already carries real prose — don't clobber (D-G)
                try:
                    inject_narrative(page_path, prose)
                except Exception as exc:  # noqa: BLE001 — non-fatal restore
                    logger.warning(
                        "narrative restore failed for %s: %s", restore_uri, exc
                    )

```

- [ ] **Step 5: Re-source `preserved` from the live page in Step 10b (package/app)**

In Step 10b, the page path (`fm_page_path`) is currently computed AFTER `preserved`. Move the slug/path computation up and read `preserved` from that path. Find:

```python
                    file_map = build_file_map(repo / node_path, max_depth=max_depth)
                    if not file_map:
                        continue
                    # M2b §3.1/§3.3: drop changed rows from preserved so they
                    # re-emerge as `— TODO` and Step 10c re-describes them. Gated
                    # on `narrate` — an LLM-free scan keeps the cost cache intact
                    # and re-describes nothing (Step 10c is narrate-gated too).
                    preserved = dict(prior_file_map_descs.get(node_uri) or {})
                    if narrate and node_uri in commit_dirty:
```

Replace with:

```python
                    file_map = build_file_map(repo / node_path, max_depth=max_depth)
                    if not file_map:
                        continue
                    slug = short_filename(node_uri, fm_collision_set)
                    fm_page_path = wiki / "entities" / f"{slug}.md"
                    # PTO: re-source surviving descriptions from the LIVE page —
                    # write_entities no longer reset the File-map body, so the
                    # filled rows are still on disk here. Then M2b's
                    # preserved-drop (below, unchanged) drops changed rows so
                    # they re-emerge as `— TODO` for Step 10c.
                    preserved = dict(_live_file_map_descriptions(fm_page_path))
                    if narrate and node_uri in commit_dirty:
```

Then DELETE the now-duplicate `slug`/`fm_page_path` lines further down in the same loop (they currently sit just before the `try:` that calls `inject_file_map`):

```python
                    slug = short_filename(node_uri, fm_collision_set)
                    fm_page_path = wiki / "entities" / f"{slug}.md"
                    try:
                        inject_file_map(
```

becomes:

```python
                    try:
                        inject_file_map(
```

- [ ] **Step 6: Re-source `preserved` from the live page in Step 10b-ts (test_suite)**

In Step 10b-ts, the suite page path (`ts_page_path`) is computed AFTER `preserved`. Move it up. Find:

```python
                    block = build_dir_file_map(repo / suite_path, max_depth=max_depth)
                    if not block:
                        continue
                    preserved = dict(prior_file_map_descs.get(suite_uri) or {})
                    if narrate and suite_uri in commit_dirty:
```

Replace with:

```python
                    block = build_dir_file_map(repo / suite_path, max_depth=max_depth)
                    if not block:
                        continue
                    ts_page_path = _entity_page_path(
                        wiki, "test_suite", node, suite_uri, fm_collision_set,
                    )
                    # PTO: live-source preserved descriptions from the suite page
                    # (mirrors Step 10b; the suite branch is at package parity).
                    preserved = dict(_live_file_map_descriptions(ts_page_path))
                    if narrate and suite_uri in commit_dirty:
```

Then DELETE the now-duplicate `ts_page_path` computation further down (just before the suite `try:`):

```python
                    ts_page_path = _entity_page_path(
                        wiki, "test_suite", node, suite_uri, fm_collision_set,
                    )
                    try:
                        inject_file_map(
```

becomes:

```python
                    try:
                        inject_file_map(
```

- [ ] **Step 7: Drop the now-unused `extract_narrative` import**

`extract_narrative` was used only by the deleted `_snapshot_narratives` and the deleted restore loop. Remove it from the `from wiki_io.entity_writer import (...)` block near the top of `scan.py` (delete the single line `    extract_narrative,`). Leave `_extract_file_map_descriptions`, `inject_narrative`, `fill_file_map_descriptions`, `file_map_todo_paths`, etc. — they are still used.

- [ ] **Step 8: Verify no references to the deleted snapshot symbols remain in source**

Run:
```bash
cd /Users/pat/Personal/agent-research
grep -rn "_snapshot_narratives\|_snapshot_file_map_descriptions\|prior_narratives\|prior_file_map_descs" --include="*.py" packages | grep -v "/tests/"
```
Expected: NO output. Also confirm the import is gone:
```bash
grep -n "extract_narrative" packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py
```
Expected: NO output (the only uses were deleted).

- [ ] **Step 9: Update the stale docstring in `test_updated_churn.py`**

In `packages/graph-wiki-core/tests/unit/test_updated_churn.py`, the docstring of `test_human_section_edit_is_preserved_not_churned` references the now-deleted helper and test file. Replace the two sentences:

```python
    The genuine anti-data-loss intent of spec test 6 — the human edit is not
    lost and not overwritten by the placeholder — is what is asserted here.
    `_equal_modulo_scanner`'s own "human section differs → not equal" contract is
    covered in `packages/wiki-io/tests/test_equal_modulo_scanner.py`.
```

with:

```python
    The genuine anti-data-loss intent of spec test 6 — the human edit is not
    lost and not overwritten by the placeholder — is what is asserted here.
    Under M2d PTO the page renders byte-identical to disk (the merge preserves
    every section), so the plain `old_bytes == new_bytes` compare buckets it
    `unchanged` and skips the write.
```

(The test body is unchanged — it still passes under PTO.)

- [ ] **Step 10: Run the affected integration suites**

Run:
```bash
cd /Users/pat/Personal/agent-research
uv run pytest packages/graph-wiki-core/tests/unit/test_updated_churn.py \
  packages/graph-wiki-core/tests/unit/test_commit_gated_narrative.py \
  packages/graph-wiki-core/tests/unit/test_commit_gated_file_map.py \
  packages/graph-wiki-core/tests/unit/test_commit_gated_test_suite.py \
  packages/graph-wiki-core/tests/unit/test_scan_narrate.py -q 2>&1 | tail -20
```
Expected: PASS. These prove behavior parity: prose persists without the restore loop (M2a), file-map descriptions survive via live-sourced `preserved` (M2b), the suite gate still fires (M2c #4), and no-op rescans stay `unchanged` (M2c #3 end-state).

- [ ] **Step 11: Commit**

```bash
cd /Users/pat/Personal/agent-research
git add packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py \
        packages/graph-wiki-core/tests/unit/test_updated_churn.py
git commit -m "refactor(scan): delete snapshot/restore; live-source preserved (M2d §3.2)

PTO makes the pre-scan narrative+file-map snapshots and the M2a restore loop
redundant: write_entities no longer resets scanner sections, so prose persists
for free and file-map descriptions are read live from the page at inject time
via _live_file_map_descriptions. Drops the prior_* plumbing and the now-unused
extract_narrative import.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Template-reconciliation verification tests

**Files:**
- Modify: `packages/wiki-io/tests/test_section_merge.py`

§1.4 / §3.3: the merge already reconciles template H2 changes (add/remove/reorder, respecting ownership). M2d's job is to pin that behavior with explicit tests now that PTO is in place — no production code changes here.

- [ ] **Step 1: Write the reconciliation tests**

Append these five tests to `packages/wiki-io/tests/test_section_merge.py`:

```python
def test_reconcile_template_adds_h2() -> None:
    """A new human-owned H2 added to the template appears on the merged page."""
    existing = "# T\n\n## Narrative\nprose\n\n## Purpose\nkept\n"
    template = (
        "# T\n\n## Narrative\n_p_\n\n## Purpose\n> TODO\n\n## Public API\n> TODO\n"
    )
    out = _merge_preserved_sections(template, existing)
    assert "## Public API" in out                 # new template section added
    assert "kept" in out                          # existing human section preserved


def test_reconcile_template_drops_scanner_h2() -> None:
    """A scanner-owned H2 dropped from the template is removed from the page
    (scanner sections are template-driven; they do not linger)."""
    existing = (
        "# T\n\n## Narrative\nprose\n\n## File map - foo\n| a | b | c |\n\n"
        "## Purpose\nkept\n"
    )
    template = "# T\n\n## Narrative\n_p_\n\n## Purpose\n> TODO\n"
    out = _merge_preserved_sections(template, existing)
    assert "## File map" not in out               # dropped scanner section removed
    assert "kept" in out


def test_reconcile_template_drops_human_h2_is_preserved() -> None:
    """A human-owned H2 the template no longer defines is preserved (appended as
    a user section) — human content is never silently dropped."""
    existing = "# T\n\n## Narrative\nprose\n\n## Purpose\nkept human content\n"
    template = "# T\n\n## Narrative\n_p_\n"   # template dropped ## Purpose
    out = _merge_preserved_sections(template, existing)
    assert "## Purpose" in out
    assert "kept human content" in out


def test_reconcile_template_reorders_sections() -> None:
    """Output section order follows the template order, not the page's."""
    existing = "# T\n\n## Purpose\np\n\n## Narrative\nprose\n"
    template = "# T\n\n## Narrative\n_p_\n\n## Purpose\n> TODO\n"
    out = _merge_preserved_sections(template, existing)
    assert out.index("## Narrative") < out.index("## Purpose")  # template order


def test_reconcile_user_added_section_trails() -> None:
    """A user-added H2 absent from the template is preserved and trails the
    template-defined sections."""
    existing = (
        "# T\n\n## Narrative\nprose\n\n## Purpose\np\n\n## My Notes\ncustom\n"
    )
    template = "# T\n\n## Narrative\n_p_\n\n## Purpose\n> TODO\n"
    out = _merge_preserved_sections(template, existing)
    assert "## My Notes" in out
    assert "custom" in out
    assert out.index("## Purpose") < out.index("## My Notes")   # trails template
```

- [ ] **Step 2: Run the reconciliation tests**

Run:
```bash
cd /Users/pat/Personal/agent-research
uv run pytest packages/wiki-io/tests/test_section_merge.py -q
```
Expected: PASS (all tests — the new five assert behavior the merge already implements under PTO).

- [ ] **Step 3: Commit**

```bash
cd /Users/pat/Personal/agent-research
git add packages/wiki-io/tests/test_section_merge.py
git commit -m "test(entity-writer): pin template reconciliation under PTO (M2d §3.3)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Crash-window regression test

**Files:**
- Create: `packages/graph-wiki-core/tests/unit/test_m2d_crash_window.py`

§5 test 10: a scan that fails mid-pipeline (during the inject steps) must leave the page's prior scanner content on disk — never a placeholder. Under PTO this holds because `write_entities` never resets the section in the first place: a no-op-frontmatter rescan buckets the page `unchanged` and skips the write, so an inject failure afterward cannot expose a placeholder.

- [ ] **Step 1: Write the crash-window test**

Create `packages/graph-wiki-core/tests/unit/test_m2d_crash_window.py`. It reuses the `churn_workspace` fixture pattern from `test_updated_churn.py` (self-contained copy — the fixture is not shared across files):

```python
"""Living Wiki M2d §5 test 10: a mid-pipeline inject failure leaves real
scanner content on disk (PTO closes the placeholder crash-window)."""

from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

import frontmatter as _fm
import graph_wiki_core.commands.scan as scan_mod
import pytest
from graph_io import exit_codes

_PKG_A = "pkg:org/repo/pkg-a"

_FILE_MAP = (
    "## File map - pkg-a\nTODO\n\n### pkg-a/\nTODO\n\n"
    "| Path | Kind | Description |\n|---|---|---|\n"
    "| `mod.py` | file | — TODO |\n"
)


def _seed_one_package(db_path: Path) -> None:
    from graph_io import schema

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        schema.apply_schema(conn)
        conn.execute(
            "INSERT INTO nodes(kind, name, path, line, attrs_json, uri) VALUES "
            "('package', 'pkg-a', 'packages/pkg-a', NULL, "
            "'{\"language\": \"python\"}', 'pkg:org/repo/pkg-a')"
        )
        conn.commit()
    finally:
        conn.close()


def _fanout_spy():
    async def _run_all(self, *, items, task, role, model_id, max_concurrency):
        from subagent_runtime.pool import FanOutResult

        result = FanOutResult()
        if role == "narrator":
            result.successes = [(it, f"PROSE for {it[0]}") for it in items]
        else:
            result.successes = [
                (it, json.dumps({p: f"desc {p}" for p in it[3]})) for it in items
            ]
        return result

    return _run_all


@pytest.fixture
def crash_workspace(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    wiki = workspace / "wiki"
    repo = workspace / "repo"
    (wiki / ".graph-wiki").mkdir(parents=True)
    (wiki / "CLAUDE.md").write_text("# Wiki\n")
    (wiki / "log.md").write_text("", encoding="utf-8")
    repo.mkdir()
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(workspace))
    _seed_one_package(workspace / ".graph" / "code.db")
    monkeypatch.setattr(
        scan_mod, "_cg_run_build",
        lambda repo, ws, *, full: (exit_codes.SUCCESS, "", ""),
    )
    monkeypatch.setattr(
        scan_mod, "make_llm", lambda role, *, model_override=None: MagicMock()
    )
    monkeypatch.setattr(
        scan_mod, "build_file_map",
        lambda path, **kw: (_FILE_MAP if str(path).endswith("pkg-a") else None),
    )
    monkeypatch.setattr(
        scan_mod, "compute_state_gate",
        lambda repo: {"allowed": True, "reason": "clean", "head_commit": "head1"},
    )
    monkeypatch.setattr(scan_mod.SubagentPool, "run_all", _fanout_spy())
    return workspace


def _page(wiki: Path) -> Path:
    return next(
        p for p in (wiki / "entities").glob("*.md")
        if _fm.load(p).metadata.get("uri") == _PKG_A
    )


def test_mid_pipeline_inject_failure_leaves_real_content(crash_workspace, monkeypatch):
    """[spec §5 test 10] After scan 1 fills the page, a scan 2 whose inject
    steps all raise must leave the scan-1 prose + descriptions intact — no
    `## Narrative` placeholder is ever exposed on disk."""
    workspace = crash_workspace
    wiki = workspace / "wiki"
    repo = workspace / "repo"

    # Scan 1: fill Narrative + File-map row.
    asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True))
    text1 = _page(wiki).read_text(encoding="utf-8")
    assert "PROSE for pkg:org/repo/pkg-a" in text1
    assert "desc mod.py" in text1

    # Scan 2: force the page commit-dirty (so the inject steps run) and make
    # BOTH inject steps raise mid-pipeline.
    monkeypatch.setattr(
        scan_mod, "changed_files_since", lambda *a: ["packages/pkg-a/mod.py"]
    )

    def _boom(*a, **k):
        raise RuntimeError("simulated mid-pipeline failure")

    monkeypatch.setattr(scan_mod, "inject_narrative", _boom)
    monkeypatch.setattr(scan_mod, "inject_file_map", _boom)

    # The scan completes (per-page failures are isolated, not fatal).
    asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True))

    text2 = _page(wiki).read_text(encoding="utf-8")
    assert "PROSE for pkg:org/repo/pkg-a" in text2          # prose survived
    assert "desc mod.py" in text2                            # description survived
    assert "_(scanner will populate on next scan)_" not in text2  # no placeholder exposed
```

- [ ] **Step 2: Run the crash-window test**

Run:
```bash
cd /Users/pat/Personal/agent-research
uv run pytest packages/graph-wiki-core/tests/unit/test_m2d_crash_window.py -q
```
Expected: PASS. (Sanity-check the closure: if you temporarily revert Task 1's PTO merge, this test fails because `write_entities` would reset the section to a placeholder before the inject failure. Do not commit that revert.)

- [ ] **Step 3: Commit**

```bash
cd /Users/pat/Personal/agent-research
git add packages/graph-wiki-core/tests/unit/test_m2d_crash_window.py
git commit -m "test(scan): mid-pipeline inject failure leaves real content (M2d §5.10)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Renamed/missing scanner-heading lint (flag-only)

**Files:**
- Create: `packages/wiki-io/src/wiki_io/lint/scanner_heading.py`
- Create: `packages/wiki-io/tests/test_lint_scanner_heading.py`
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/lint.py`
- Modify: `packages/graph-wiki-cli/src/graph_wiki_cli/wiki_cli/main.py`
- Modify: `packages/graph-wiki-mcp/src/graph_wiki_mcp/server.py`

§3.4 / D4: PTO makes a renamed scanner heading (e.g. a human renames `## Narrative` to `## Narrative (old)`) orphan its region — the merge can't tell a rename from an intentional human section, so it preserves the rename AND re-adds a fresh placeholder. The merge cannot auto-heal this safely. So we add a **flag-only** lint that warns when an entity page is missing an expected scanner-owned section for its kind. No content migration (explicitly out of scope).

Expected scanner sections per kind (verified against the templates in `packages/wiki-io/src/wiki_io/assets/page-templates/`):
- **every** admitted kind: `## Narrative`, `## Referenced in wiki`
- additionally `package`, `app`, `test_suite`: `## File map` (heading carries a `- <name>` suffix → match by prefix)

- [ ] **Step 1: Write the failing lint-module unit tests**

Create `packages/wiki-io/tests/test_lint_scanner_heading.py`:

```python
"""Living Wiki M2d §3.4 / D4: flag entity pages missing an expected
scanner-owned section for their kind (renamed/dropped heading)."""

from __future__ import annotations

from wiki_io.lint.scanner_heading import check

# A well-formed package page carries all three scanner sections.
_OK_PACKAGE = {
    "fm": {"kind": "package"},
    "text": (
        "---\nuri: pkg:org/repo/foo\nkind: package\n---\n# foo\n\n"
        "## Narrative\nprose\n\n## Referenced in wiki\n- x\n\n"
        "## File map - foo\n| a | b | c |\n"
    ),
}

# A package page whose ## Narrative was renamed -> the heading is missing.
_RENAMED_NARRATIVE = {
    "fm": {"kind": "package"},
    "text": (
        "---\nuri: pkg:org/repo/bar\nkind: package\n---\n# bar\n\n"
        "## Narrative (old)\nprose\n\n## Referenced in wiki\n- x\n\n"
        "## File map - bar\n| a | b | c |\n"
    ),
}

# A dependency page (no File map expected) that is well-formed.
_OK_DEPENDENCY = {
    "fm": {"kind": "dependency"},
    "text": (
        "---\nuri: dependency:pypi/boto3\nkind: dependency\n---\n# boto3\n\n"
        "## Narrative\nprose\n\n## Referenced in wiki\n- x\n"
    ),
}

# A non-entity page (no entity `kind`) must be ignored entirely.
_NON_ENTITY = {"fm": {"category": "concept"}, "text": "# c\n\n## Whatever\n"}


def test_well_formed_pages_produce_no_findings() -> None:
    pages = {"wiki/entities/foo": _OK_PACKAGE, "wiki/entities/boto3": _OK_DEPENDENCY}
    assert check(pages) == []


def test_renamed_narrative_is_flagged() -> None:
    pages = {"wiki/entities/bar": _RENAMED_NARRATIVE}
    issues = check(pages)
    assert len(issues) == 1
    assert "wiki/entities/bar" in issues[0]
    assert "## Narrative" in issues[0]


def test_missing_file_map_on_package_is_flagged() -> None:
    page = {
        "fm": {"kind": "package"},
        "text": (
            "---\nkind: package\n---\n# foo\n\n## Narrative\np\n\n"
            "## Referenced in wiki\n- x\n"
        ),
    }
    issues = check({"wiki/entities/foo": page})
    assert any("## File map" in i for i in issues)


def test_non_entity_pages_are_ignored() -> None:
    assert check({"concepts/c": _NON_ENTITY}) == []
```

- [ ] **Step 2: Run the lint tests to verify they fail**

Run:
```bash
cd /Users/pat/Personal/agent-research
uv run pytest packages/wiki-io/tests/test_lint_scanner_heading.py -q
```
Expected: FAIL with `ModuleNotFoundError: No module named 'wiki_io.lint.scanner_heading'`.

- [ ] **Step 3: Create the lint module**

Create `packages/wiki-io/src/wiki_io/lint/scanner_heading.py`:

```python
"""Scanner-heading drift: entity pages missing an expected scanner-owned
section for their kind (e.g. a human renamed `## Narrative`).

Flag-only (M2d D4) — PTO cannot safely auto-heal a renamed scanner heading
(it can't distinguish a rename from an intentional human section), so this
lint surfaces it as a warning. No content migration.
"""

from __future__ import annotations

import re

from wiki_io.entity_writer import ADMITTED_KINDS

GROUP = "scanner_heading"

# Scanner-owned sections each entity kind's template carries. `## File map`
# only appears on package/app/test_suite templates; `## Narrative` and
# `## Referenced in wiki` appear on all admitted kinds.
_BASE_SECTIONS = ("## Narrative", "## Referenced in wiki")
_FILE_MAP_KINDS = frozenset({"package", "app", "test_suite"})
_EXPECTED_SCANNER_HEADINGS: dict[str, tuple[str, ...]] = {
    kind: (_BASE_SECTIONS + ("## File map",) if kind in _FILE_MAP_KINDS else _BASE_SECTIONS)
    for kind in ADMITTED_KINDS
}

# Defence-in-depth: the map must cover every admitted kind so a newly-admitted
# kind cannot silently skip this lint.
assert set(_EXPECTED_SCANNER_HEADINGS) == set(ADMITTED_KINDS), \
    "scanner-heading lint map must cover every admitted kind"

_FILE_MAP_PREFIX_RE = re.compile(r"^## File map\b", re.MULTILINE)


def _heading_present(text: str, heading: str) -> bool:
    """True when ``heading`` appears as an H2 at column 0.

    `## File map` carries a `- <name>` suffix, so it is matched by prefix; the
    other scanner headings are exact (humans must not rename them — that is the
    failure mode this lint catches).
    """
    if heading == "## File map":
        return _FILE_MAP_PREFIX_RE.search(text) is not None
    pat = re.compile(r"^" + re.escape(heading) + r"[ \t]*$", re.MULTILINE)
    return pat.search(text) is not None


def check(pages: dict) -> list[str]:
    """Flag entity pages missing an expected scanner-owned section for their kind.

    ``pages`` is the lint command's page map: ``{key: {"fm": {...}, "text": str}}``.
    Only pages whose frontmatter ``kind`` is an admitted entity kind are checked;
    every other page (concepts, ADRs, etc.) is ignored. Returns a sorted list of
    warning strings.
    """
    issues: list[str] = []
    for key, page in pages.items():
        fm = page.get("fm") or {}
        kind = fm.get("kind")
        expected = _EXPECTED_SCANNER_HEADINGS.get(kind)
        if not expected:
            continue
        text = page.get("text", "")
        for heading in expected:
            if not _heading_present(text, heading):
                issues.append(
                    f"{key}: missing scanner section '{heading}' "
                    f"(renamed or dropped?)"
                )
    return sorted(issues)
```

- [ ] **Step 4: Run the lint module tests to verify they pass**

Run:
```bash
cd /Users/pat/Personal/agent-research
uv run pytest packages/wiki-io/tests/test_lint_scanner_heading.py -q
```
Expected: PASS.

- [ ] **Step 5: Wire the check into the lint command**

In `packages/graph-wiki-core/src/graph_wiki_core/commands/lint.py`:

(a) Add the import next to the other `wiki_io.lint.*` check imports:

```python
from wiki_io.lint.scanner_heading import check as check_scanner_heading
```

(b) Add a field to `LintResult` (after `dependency_layer`):

```python
    scanner_heading_drift: list[str] = field(default_factory=list)
```

(c) In `_module_pass`, compute it and add to the returned dict. After the `dependency_layer = check_dependency_layer(pages)` line, add:

```python
    scanner_heading_drift = check_scanner_heading(pages)
```

and add to the `return {...}` dict:

```python
        "scanner_heading_drift": scanner_heading_drift,
```

(d) In `run_lint`, pass it through to the `LintResult(...)` constructor (after `dependency_layer=mod["dependency_layer"],`):

```python
        scanner_heading_drift=mod["scanner_heading_drift"],
```

- [ ] **Step 6: Render the new section in the CLI**

In `packages/graph-wiki-cli/src/graph_wiki_cli/wiki_cli/main.py`, after the existing `_section("Workflow hints", result.workflow_hints)` line, add:

```python
        _section("Scanner heading drift", result.scanner_heading_drift)
```

- [ ] **Step 7: Expose the new field on the MCP output**

In `packages/graph-wiki-mcp/src/graph_wiki_mcp/server.py`:

(a) Add to the `WikiLintOutput` model (after `dependency_layer: list[str] | None`):

```python
    scanner_heading_drift: list[str]
```

(b) Add to the `WikiLintOutput(...)` construction in `wiki_lint` (after `dependency_layer=result.dependency_layer,`):

```python
        scanner_heading_drift=result.scanner_heading_drift,
```

- [ ] **Step 8: Verify the lint command + downstreams import and run cleanly**

Run:
```bash
cd /Users/pat/Personal/agent-research
uv run pytest packages/graph-wiki-core/tests/unit/test_commands_lint.py \
  packages/graph-wiki-mcp/tests/unit/test_mcp_new_tools.py -q 2>&1 | tail -20
```
Expected: PASS. If `test_mcp_new_tools.py` constructs a `WikiLintOutput` literal that now misses the required `scanner_heading_drift` field, add `scanner_heading_drift=[]` to that fixture — a field-parity fix, not a behavior change.

- [ ] **Step 9: Commit**

```bash
cd /Users/pat/Personal/agent-research
git add packages/wiki-io/src/wiki_io/lint/scanner_heading.py \
        packages/wiki-io/tests/test_lint_scanner_heading.py \
        packages/graph-wiki-core/src/graph_wiki_core/commands/lint.py \
        packages/graph-wiki-cli/src/graph_wiki_cli/wiki_cli/main.py \
        packages/graph-wiki-mcp/src/graph_wiki_mcp/server.py
git commit -m "feat(lint): flag entity pages missing scanner sections (M2d §3.4)

Flag-only lint surfacing the one failure mode PTO cannot auto-heal — a renamed
or dropped scanner-owned heading. Wired into run_lint, the CLI report, and the
MCP wiki_lint output.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Full-suite verification + grep-clean

**Files:** none (verification only)

- [ ] **Step 1: Run the full wiki-io and graph-wiki-core unit suites**

Run:
```bash
cd /Users/pat/Personal/agent-research
uv run pytest packages/wiki-io/tests packages/graph-wiki-core/tests/unit -q 2>&1 | tail -25
```
Expected: PASS, with a pass count = Task 0 baseline − 8 (the deleted `test_equal_modulo_scanner.py` tests) + the tests added in Tasks 1, 3, 4, 5. No NEW failures.

- [ ] **Step 2: Run the broader graph-wiki-core suite to catch the known-debt baseline**

Run:
```bash
cd /Users/pat/Personal/agent-research
uv run pytest packages/graph-wiki-core/tests -q 2>&1 | tail -25
```
Expected: the ONLY failures are the two known-pre-existing ones (`test_scan_decontainerize_parity::test_scan_entities_tree_snapshot`, `test_scan_graph_integration::test_file_map_injected_into_app_entity_page`). If any other test fails, it is genuinely new — debug it (use superpowers:systematic-debugging) before declaring done.

- [ ] **Step 3: Final grep-clean for all deleted symbols (spec §5 test 9)**

Run:
```bash
cd /Users/pat/Personal/agent-research
grep -rn "_snapshot_narratives\|_snapshot_file_map_descriptions\|prior_narratives\|prior_file_map_descs\|_equal_modulo_scanner\|_normalize_scanner_bodies" --include="*.py" packages
```
Expected: NO output anywhere (source AND tests — `test_equal_modulo_scanner.py` is deleted and `test_updated_churn.py`'s docstring was updated in Task 2 Step 9).

- [ ] **Step 4: Confirm the lint surfaces on a real lint run (smoke)**

Run:
```bash
cd /Users/pat/Personal/agent-research
grep -rn "scanner_heading_drift" --include="*.py" packages | grep -v "/tests/"
```
Expected: references in `commands/lint.py` (field + module pass + constructor), `wiki_cli/main.py` (render), and `graph_wiki_mcp/server.py` (output model + construction) — five locations confirming the field is computed and surfaced end-to-end.

- [ ] **Step 5: Update memory**

Update `/Users/pat/.claude/projects/-Users-pat-Personal-agent-research/memory/living-wiki-m2-roadmap-state.md`: mark M2d as LANDED (with the merge SHA once merged), note that `_merge_preserved_sections` is now PTO, the snapshot/restore machinery and `_equal_modulo_scanner`/`_normalize_scanner_bodies` are deleted, `preserved` is live-sourced via `_live_file_map_descriptions`, and the missing-scanner-heading lint exists. Also resolve the M2c open follow-up noted in that memory ("the suite branch `if fm_targets:` is NOT guarded by `no_file_map`") — confirm whether M2d's live-sourcing changed it (it did not; flag it as still-open for M2e if unaddressed). Add the one-line pointer is already present, so just edit the body.

---

## Self-Review

**1. Spec coverage** — every spec section maps to a task:
- §3.1 PTO rewrite + D1/D2 → Task 1 (Steps 1–4).
- §1.1 / §4 delete `_equal_modulo_scanner` / `_normalize_scanner_bodies` / skip-write + their unit tests → Task 1 (Steps 5–7).
- §3.2 / D3 delete snapshot/restore + re-source `preserved` live → Task 2.
- §1.3 heading-suffix match-by-type → Task 1 Step 1 (`test_merge_pto_matches_file_map_by_type_despite_heading_suffix`, spec §5 test 3).
- §3.3 / §1.4 reconciliation verify → Task 3 (spec §5 test 11).
- §3.4 / D4 lint → Task 5 (spec §5 test 12).
- §5 test 10 crash-window → Task 4.
- §5 tests 1–2, 5–9 (parity + grep-clean) → Task 2 Step 10 + Task 6.
- §5 test 4 (frontmatter/human-edit still `updated`/preserved) → kept green in `test_updated_churn.py` (Task 2 Step 1/10).

**2. Placeholder scan** — every code step contains the actual code; every command step has an expected result. No "TBD"/"add error handling"/"similar to" placeholders. Out-of-scope items (content migration, human-section drift → M2e, cross-page drift → M4) are excluded by the spec and not implemented here.

**3. Type consistency** — symbol names verified against the source: `_merge_preserved_sections`, `_scanner_section_token`, `_is_scanner_owned_heading`, `_split_h2_sections`, `_extract_file_map_descriptions`, `FILE_MAP_SECTION_RE`, `short_filename`, `_entity_page_path`, `inject_file_map`, `_live_file_map_descriptions` (new), `check`/`GROUP` (lint-module convention matching `file_map.py`), `LintResult.scanner_heading_drift`, `WikiLintOutput.scanner_heading_drift`. The lint `check(pages)` signature matches the existing `_module_pass` call convention (pages-only, like `check_domain_placement`/`check_dependency_layer`).

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-04-living-wiki-m2d-preserve-then-overwrite.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
</content>
</invoke>
