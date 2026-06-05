# Living Wiki M2d — Preserve-Then-Overwrite Merge + Reconciliation Hardening

**Date:** 2026-06-04
**Status:** Design — ready for `writing-plans`.
**Author:** Pat (with code-verified findings)
**Milestone:** Living Wiki M2d (slice of M2 — "Commit-gated incremental updates").
**Builds on:** M2a (narrative persistence + commit-gate), M2b (commit-gated file-map row re-description), and **M2c (commit-gate consolidation)** — M2c is the immediate precondition (see §1.1). M2a/M2b landed on `main` (M2b merge `7d0ac7b5`); **M2c is executing in a worktree** per `docs/superpowers/plans/2026-06-04-living-wiki-m2c-commit-gate-consolidation.md`.
**Roadmap:** `docs/superpowers/specs/2026-06-03-living-wiki-roadmap.md` (§3 D2/D3, §4 "M2").

---

## 0. One-paragraph thesis

The entity-page pipeline still carries a reset-then-restore dance: `write_entities` re-renders each page from its template and **resets the three scanner-owned sections** (`## Narrative`, `## File map`, `## Referenced in wiki`) to placeholders, and `scan.py` then snapshots-before / restores-after to put the real content back (M2a narrative restore; M2b file-map `preserved=` graft). That reset is the root of three problems M2a–M2c have been working *around*: the `updated`-churn (M2c #3 patched it with a skip-write), the snapshot/restore machinery itself, and a brief on-disk placeholder crash-window. **M2d removes the reset.** `_merge_preserved_sections` flips from *reset-to-placeholder* to **preserve-then-overwrite** (PTO): the merge keeps existing scanner section bodies, and the scan pipeline overwrites only the ones it actually regenerates this scan. That single change (a) deletes the snapshot/restore machinery, (b) eliminates the churn at its source — making M2c #3's `_equal_modulo_scanner` skip-write dead code M2d removes — and (c) closes the crash-window. Riding along: the template-reconciliation behavior that already lives in the merge (add/remove/reorder H2s) is verified, tested, and protected by a new renamed-scanner-heading lint. This is **not** new infrastructure — it net-deletes code and is the consolidation the M2c design recorded as its "next cleanup."

---

## 1. Where we are (code-verified)

Line numbers are `main` at M2b merge (`7d0ac7b5`) except where noted as post-M2c. Files: `packages/wiki-io/src/wiki_io/entity_writer.py` and `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py`.

### 1.1 M2c precondition (executing in a worktree)

M2d **depends on M2c landing first** — the two touch the same code (`write_entities` bucketing, `scan.py` anchor logic). M2c's plan self-review (plan line 1362) explicitly lists Approach-A / `_merge_preserved_sections` inversion / snapshot-restore deletion / template reconciliation as **out of M2c scope**, so the M2d surface is clean. M2d encodes the following assumptions about post-M2c `main`; **if M2c's shape changes during its run, revisit the "deletes" list below.**

**M2c artifacts M2d DELETES (they are scaffolding PTO subsumes):**
- `_equal_modulo_scanner` and `_normalize_scanner_bodies` (`entity_writer.py`, M2c Task 1) and the skip-write call wired into the `write_entities` `existed` branch (M2c Task 2 Step 3). PTO removes the reset, so a no-op rescan produces byte-identical `new_content` and the plain `old_bytes == new_bytes` compare buckets it `unchanged` — the comparison helper is no longer reachable as a deciding factor.
- `packages/wiki-io/tests/test_equal_modulo_scanner.py` (unit tests for the deleted helper).
- `_snapshot_narratives` (`scan.py:147`) + the M2a narrative-restore loop (`scan.py:926-948`), `_snapshot_file_map_descriptions` (`scan.py:112`), and the `prior_narratives` / `prior_file_map_descs` plumbing (`scan.py:789-793`, call sites in Step 10b/10b-ts).

**M2c artifacts M2d KEEPS / BUILDS ON:**
- `_scanner_section_token` (`entity_writer.py`, M2c Task 1) — **reused**, not deleted (see §1.3 / D2). It classifies a scanner heading to its type; PTO's merge needs exactly that to match existing scanner sections to template slots despite the `## File map` heading-suffix mismatch.
- **Part 3 unified anchor stamping** (M2c Task 3): `good_prose_uris`, `narrated_page_paths`, and the post-Step-10c pass that stamps `(good_prose_uris | redescribed_uris)` iff `not file_map_todo_paths(page)`. Orthogonal to the merge — untouched.
- **#4 test_suite commit-gate** (M2c Tasks 4–5): the `test_suite` entry in the `_commit_dirty_changes` kind loop and the Step 10b-ts parity branch. Untouched except the `preserved=` source swap in §3.2, applied in lockstep with Step 10b.
- `packages/graph-wiki-core/tests/unit/test_updated_churn.py` (M2c Task 2 integration tests) — **kept as a regression guard**; its assertions are precisely PTO's end-state (see §1.2 / D3).

### 1.2 The reset-then-restore dance (what PTO removes)

`_merge_preserved_sections` (`entity_writer.py:569-611`) preserves human-owned H2 sections from the existing page but, for the three **scanner-owned** headings (`_is_scanner_owned_heading`, `:532-544`), always takes the **template** chunk — i.e. resets them to placeholders (`:594-598`). The scan pipeline then puts content back:

- **Before** `write_entities`: `_snapshot_narratives` (`scan.py:147`, called `:793`) and `_snapshot_file_map_descriptions` (`scan.py:112`, called `:792`) capture prior content keyed by URI.
- **After**: the narrator inject loop re-injects fresh prose; the **M2a restore loop** (`scan.py:926-948`) puts prior prose back for entities *not* re-narrated this scan; **Step 10b / 10b-ts** re-inject the file map with `preserved=prior_file_map_descs.get(uri)` (`scan.py:1009`, `:1064` pre-M2c; the suite branch is brought to parity in M2c Task 5).

This dance exists **only** because the merge resets. Its costs:
1. **Churn:** because `new_content` has placeholder scanner sections while the on-disk page has filled ones, `old_bytes != new_bytes` for every populated page → bucketed `updated` every scan (the masking M2c #3 patched).
2. **Crash-window:** a scan that dies after `write_entities` but before the restore/inject steps leaves placeholders on disk.
3. **Machinery:** two snapshot passes + a restore loop + a `preserved=` graft, all to undo a reset the pipeline itself performed.

PTO removes the reset → all three costs go. M2c #3's skip-write was the interim guard for cost #1; M2d's structural fix makes it unnecessary. `test_updated_churn.py` keeps passing because its assertions (`entities_updated == []`, byte-identical page, descriptions survive) describe PTO's end-state directly.

### 1.3 The `## File map` heading-suffix trap (why the merge matches by type)

The M2c plan (line 19) documents a subtlety PTO must respect: the `## File map` heading carries a name suffix that **differs between the two sides**. `write_entities` renders the template token `{{PACKAGE_SLUG}}` → `## File map - <slug>` (e.g. `## File map - pkg_pkg-a`), while the injected deterministic block (`build_file_map` / `build_dir_file_map`) emits `## File map - <dir-basename>` (e.g. `## File map - pkg-a`). On disk, a populated page's file-map heading is the **basename** form (last writer = the injector).

`_merge_preserved_sections` matches existing sections to template slots by **exact heading string** (`existing_by_heading`, `:585-587`). A naive PTO ("for scanner headings, take the existing chunk if `heading in existing_by_heading`") would **fail for the file map**: the template slot heading is the slug form, the existing section heading is the basename form — no match — so it would fall back to the slug-suffixed template placeholder, re-introducing churn and discarding the filled rows. **Therefore PTO must match scanner sections by section *type*, not by literal heading**, reusing M2c's `_scanner_section_token` classifier. `## Narrative` and `## Referenced in wiki` have stable headings; only `## File map` carries the variable suffix, but matching all three by type is uniform and correct.

### 1.4 Template reconciliation is already (mostly) implemented

The roadmap's M2 bullet asks for "template reconciliation (add/remove H2s per the current template, respecting ownership)." `_merge_preserved_sections` **already does this**:
- **Adds** template H2s not on the page (loops `secs_t`, `:592`).
- **Removes** dropped *scanner-owned* H2s (a scanner heading present on the page but absent from the template is skipped by the user-section append guard at `:601-607`, because `_is_scanner_owned_heading` is true).
- **Preserves** human/user H2s the template dropped (appended as user sections, `:600-609`).
- **Orders** template sections by template order; user-added sections trail.

So M2d's reconciliation work is **verify + harden + lint**, not "build a reconciler" (decision confirmed during brainstorming): add explicit tests for add/remove/reorder under PTO, and add a lint that flags the one failure mode the merge cannot self-heal — a *renamed* scanner heading (§2 D4).

---

## 2. Architecture decisions

### D1 — Naming: call it "preserve-then-overwrite" (PTO), not "Approach A"

The M2c design names this change "Approach A." That collides with the **already-shipped** M1 merge, which is *also* labeled "Approach A" (roadmap §3 D2; `entity_writer.py:526` module comment). To avoid ambiguity in code comments, commits, and the plan, this work is **"preserve-then-overwrite" (PTO)** throughout. The M1 "Approach A" (heading-aware merge) stays as-is; PTO is the inversion of its scanner-section handling.

### D2 — `_merge_preserved_sections` preserves scanner bodies, matched by type

On re-scan the merge keeps the **existing** body for each scanner-owned section, falling back to the template placeholder only when the page has no section of that scanner type (newly-created page, or a scanner section newly added to the template). Matching is by **section type** via the reused `_scanner_section_token` (§1.3), not by literal heading. Human/user reconciliation logic is **unchanged** (§1.4). The merge stays idempotent: `_merge_preserved_sections(t, t) == t` still holds, and a populated page round-trips byte-for-byte when no scanner regeneration runs.

**Consequence for the pipeline:** entities *not* re-narrated keep their prose automatically (no restore loop); pages *not* in `fm_targets` keep their file map automatically (no re-inject); re-narrated/re-described pages are overwritten by the existing inject steps exactly as today.

### D3 — Delete the snapshot/restore machinery; re-source `preserved` from the live page

`_snapshot_narratives`, the M2a restore loop, and `_snapshot_file_map_descriptions` are deleted. Step 10b (package/app) and Step 10b-ts (test_suite) re-source surviving file-map row descriptions from the **live page** at injection time via the existing `_extract_file_map_descriptions` (`entity_writer.py:1203`) — the same function the deleted snapshot used. This is valid because under PTO `write_entities` no longer resets the file-map section, so at Step 10b time the on-disk page still holds the filled descriptions. Both branches change identically (the suite branch was brought to parity by M2c Task 5).

### D4 — Renamed/missing scanner-heading lint (flag-only)

PTO makes the D2-risk (roadmap §3 D2: "a renamed scanner-owned heading orphans its region") more visible: if a human renames `## Narrative` to e.g. `## Narrative (old)`, the merge treats the renamed heading as a *human* section (preserved forever) **and** adds a fresh `## Narrative` placeholder from the template → a duplicated/orphaned region. The merge cannot safely auto-heal this (it can't tell a rename from an intentional human section). So M2d adds a **lint check** to `graph-wiki:lint` that flags an entity page **missing an expected scanner-owned section** for its kind. Flag-only (a warning), consistent with the roadmap's propose-don't-auto-edit stance; no content migration (scoping decision — content migration was explicitly rejected for M2d).

### D5 — Execute after M2c merges; design now

M2d and M2c edit the same functions. M2d is **designed now** (this doc, then `writing-plans`) but its execution is **gated on M2c landing on `main`**. The plan will state the M2c precondition (§1.1) as its first prerequisite and target post-M2c `main`. No worktree coordination beyond "rebase onto M2c's merge before implementing."

---

## 3. The changes

### 3.1 `_merge_preserved_sections` → preserve-then-overwrite (`entity_writer.py`)

Rewrite the scanner-owned branch of the merge so a scanner section takes its body from the existing page when the page has a section of that **type** (matched via `_scanner_section_token`), else the template placeholder. Keep the human/user-section logic and the preamble-from-template rule unchanged. Net effect: scanner content is preserved across scans unless an inject step overwrites it.

### 3.2 Delete snapshot/restore; re-source `preserved` (`scan.py`)

- Remove `_snapshot_narratives` (`:147`), `_snapshot_file_map_descriptions` (`:112`), and the M2a restore loop (`:926-948`), plus the `prior_narratives` / `prior_file_map_descs` locals (`:789-793`).
- In Step 10b (package/app) and Step 10b-ts (test_suite), replace `preserved=prior_file_map_descs.get(uri)` with a per-page live read: `_extract_file_map_descriptions` over the current page's `## File map` section (mirroring the deleted snapshot helper's per-page logic at `:140-143`). The M2c preserved-drop logic (drop changed rows so they re-emerge as `— TODO`, `redescribed_uris.add(...)`, the `changed is None` drop-all branch) is **unchanged** — only the source of the initial `preserved` dict moves from snapshot to page.
- **Which pages Step 10b processes is unchanged.** `fm_targets = refreshed | commit_dirty` is the same trigger M2c established; PTO does not alter it. File-map *structure* refresh (rows added/removed from graph node paths via `build_file_map`) therefore continues to be driven by `commit_dirty` — a file add/remove is a git change since the page's anchor, so the page is commit-dirty and Step 10b re-renders its structure. PTO only changes what a *non*-target page retains (its prior file map, preserved by the merge instead of reset-then-skipped), which matches M2c #3's behavior — a structure change confined to file-map rows is normalized out of `_equal_modulo_scanner` today, so M2c already relies on the commit-gate, not the churn, for structure refresh.

### 3.3 Verify + test template reconciliation (`entity_writer` tests)

Add explicit tests for the reconciliation behavior the merge already implements, now under PTO: template-adds-H2 → appears on page; template-drops-scanner-H2 → removed; template-drops-human-H2 → preserved as user section; template-reorders → page reorders; user-added H2 → preserved and trailing.

### 3.4 Renamed/missing scanner-heading lint (`graph-wiki:lint`)

Add a check that, for each entity page, the scanner-owned sections expected for its kind are present; flag (warning) any that are missing. Surface under the existing lint report structure.

---

## 4. Scope

**In scope**
- PTO rewrite of `_merge_preserved_sections` (§3.1, D1/D2).
- Deletion of the snapshot/restore machinery + `preserved` re-sourcing (§3.2, D3).
- Removal of M2c #3's `_equal_modulo_scanner` / `_normalize_scanner_bodies` / skip-write and their unit tests (§1.1).
- Template-reconciliation verification tests (§3.3, §1.4).
- Renamed/missing scanner-heading lint (§3.4, D4).

**Out of scope (explicit boundaries)**
- **Content migration** on heading rename (lint flags only; no auto-move). Explicitly rejected for M2d.
- **Human-section drift flagging** (#2 → M2e).
- **Cross-page drift propagation** (M4).
- No new LLM roles or fan-outs; no frontmatter-schema changes; no change to the commit-gate, `needs_narrative`, or Part 3 anchor-stamping logic.

---

## 5. Tests (success criteria)

LLM fan-out mocked at the `SubagentPool.run_all` boundary (project fixture pattern; mirror `test_commit_gated_file_map.py` / `test_updated_churn.py`).

**PTO merge / churn (the structural win)**
1. **No-op rescan → zero `updated`, byte-identical** — a second scan with no repo change buckets every populated page `unchanged` and the page bytes are unchanged. (`test_updated_churn.py::test_no_op_rescan_reports_zero_updated` kept green — now via the plain compare, not skip-write.)
2. **Idempotence across all three scanner sections** — a page with filled Narrative + File map + Referenced-in-wiki rescans to `unchanged`, prose + descriptions intact. (Kept green from `test_updated_churn.py`.)
3. **File-map heading-suffix preserved** — a populated page whose `## File map - <basename>` heading differs from the template's `## File map - <slug>` slot rescans `unchanged` (guards the §1.3 trap; fails if the merge matches by literal heading).
4. **Human-section edit / frontmatter-only change still force `updated`** — kept green from `test_updated_churn.py` tests 6–7.

**PTO replaces restore (behavior parity)**
5. **Not-re-narrated page keeps prose without the restore loop** — an entity narrated on scan 1 and not re-narrated on scan 2 (no commit-dirty, no structural change) keeps its prose. (M2a behavior, now via PTO.)
6. **Re-narrate overwrites** — a commit-dirty entity re-narrates and the new prose replaces the old.
7. **File-map descriptions survive across rescan, sourced live** — a populated file map rescans with descriptions intact when the page is not in `fm_targets`; and a commit-dirty page re-describes only its changed rows. (M2b parity under live-sourced `preserved`.)

**Snapshot/restore removal (no regression)**
8. **M2a/M2b/M2c suites stay green** — `test_commit_gated_narrative.py`, `test_commit_gated_file_map.py`, `test_commit_gated_test_suite.py` all pass against PTO (anchor stamping via Part 3 unchanged; suite gate unchanged).
9. **No orphaned references** — `_snapshot_narratives`, `_snapshot_file_map_descriptions`, `prior_narratives`, `prior_file_map_descs`, `_equal_modulo_scanner`, `_normalize_scanner_bodies` are fully removed (grep clean).

**Crash-window**
10. **Mid-pipeline failure leaves real content** — simulate an inject failure after `write_entities`; the page retains its prior scanner content (no placeholder on disk).

**Template reconciliation (§3.3)**
11. add-H2 / drop-scanner-H2 / drop-human-H2 / reorder / user-added — five explicit assertions per §3.3.

**Lint (§3.4)**
12. **Missing scanner heading flagged** — a page with `## Narrative` renamed (so it's missing) produces a lint warning; a well-formed page does not.

---

## 6. Key code touchpoints

- `packages/wiki-io/src/wiki_io/entity_writer.py`
  - `_merge_preserved_sections` (`:569-611`) — PTO rewrite (§3.1).
  - `_scanner_section_token` (M2c Task 1) — **reused** as the scanner-section type classifier.
  - `_equal_modulo_scanner`, `_normalize_scanner_bodies` (M2c Task 1) — **deleted**; skip-write call in `write_entities` `existed` branch (M2c Task 2) reverted to the plain `old_bytes == new_bytes` compare.
  - `_extract_file_map_descriptions` (`:1203`) — reused for live `preserved` sourcing.
- `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py`
  - `_snapshot_narratives` (`:147`), `_snapshot_file_map_descriptions` (`:112`), M2a restore loop (`:926-948`), `prior_*` locals (`:789-793`) — **deleted**.
  - Step 10b (`:980-1037`) and Step 10b-ts (`:1038-1071`, post-M2c parity) — `preserved=` source swapped to live page read (§3.2).
  - Narrator inject loop + Part 3 stamp pass (M2c Task 3) — **unchanged**.
- `graph-wiki:lint` (lint command implementation) — add the missing-scanner-heading check (§3.4).
- Tests: delete `packages/wiki-io/tests/test_equal_modulo_scanner.py`; keep `test_updated_churn.py` as regression guard; add reconciliation + lint tests.

---

## 7. Sequencing & dependencies

**Precondition:** M2c merges to `main` (rebase onto it before implementing — D5). Then, in order:

1. **PTO merge rewrite** (§3.1) + delete `_equal_modulo_scanner`/skip-write (§1.1) — `entity_writer.py`. Verify `test_updated_churn.py` still green via the plain compare and the heading-suffix test (§5 test 3) passes.
2. **Delete snapshot/restore + re-source `preserved`** (§3.2) — `scan.py`. Verify M2a/M2b/M2c suites + parity tests (§5 tests 5–9).
3. **Reconciliation tests** (§3.3) and **lint** (§3.4).
4. **Full-suite + grep-clean verification** (§5 tests 8–12).

Steps 1 and 2 are coupled and must land together: deleting the snapshot/restore machinery (step 2) **before** PTO is in place (step 1) would leave `write_entities` resetting scanner sections to placeholders with nothing to restore them — content loss. Implement as one reviewable unit, splitting commits as the plan sees fit.

---

## 8. Open questions

None blocking. After M2d, the remaining M2 slices are **M2e** (intra-page human-section drift flagging — the cheap pilot for M4's cross-page drift) and then M3 (ingest hardening, parallel-eligible) → M4 → M5, per the re-sequenced roadmap.
