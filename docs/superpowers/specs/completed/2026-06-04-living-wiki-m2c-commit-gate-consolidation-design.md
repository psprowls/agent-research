# Living Wiki M2c — Commit-Gate Consolidation

**Date:** 2026-06-04
**Status:** Design — approved, ready for `writing-plans`.
**Author:** Pat (with code-verified findings)
**Milestone:** Living Wiki M2c (slice of M2 — "Commit-gated incremental updates").
**Builds on:** M2a (narrative persistence + commit-gate) and M2b (commit-gated file-map row re-description), both landed on `main` (M2b merge `7d0ac7b5`, incl. review-fix `f74e8e36`).
**Roadmap:** `docs/superpowers/specs/2026-06-03-living-wiki-roadmap.md` (§3 D3, §4 "M2").

---

## 0. One-paragraph thesis

M2a built the commit-gate spine (re-narrate a `package`/`app` page when its files changed since the page's `last_updated_commit` anchor); M2b finished it at file-row granularity (re-describe a changed `## File map` row). But two things keep that gate from being the *actual* driver in a normal scan, and a third is a latent correctness bug the gate's anchor logic introduced. M2c consolidates all three: **(#4)** extend the commit-gate to `test_suite` entities — the one admitted kind M2b deliberately skipped; **(#3)** stop the *updated-churn* that marks essentially every populated page `updated` every scan, which currently masks the gate by routing every page into `refreshed` regardless of `commit_dirty`; and **(Part 3)** unify anchor stamping so a re-described row whose describer fails cannot be stranded behind an advanced anchor via the narrator stamp path. None of this is new infrastructure — it reuses M2a/M2b's `changed_files_since` + `last_updated_commit` exactly.

---

## 1. Where we are (code-verified)

All line numbers are `main` at M2b merge (`packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py` unless noted).

- **`_commit_dirty_changes`** (`scan.py:562-608`) maps `package`/`app` URIs whose files changed since their anchor to the changed-file list. Its kind loop is `for kind in ("package", "app")` (`:583`); it reads each node's anchor and calls `changed_files_since(repo, anchor, node.path)`.
- **`_changed_rel_paths(changed, node_path)`** (`scan.py:542`) relativizes repo-relative changed paths to package-root-relative keys for the preserved-drop.
- **Step 10b — package/app file map** (`scan.py:980-1037`): trigger is `fm_targets = refreshed | set(commit_dirty)` (`:982`); for each commit-dirty page it drops changed rows from `preserved` (`:1010-1023`) so they re-emerge as `— TODO`, and records the page in `redescribed_uris` (`:973`).
- **Step 10b-ts — test_suite file map** (`scan.py:1038-1071`): triggered **only** on `if refreshed:` (`:1044`); grafts `preserved=prior_file_map_descs.get(suite_uri)` (`:1064`) with **no** preserved-drop and **no** `commit_dirty` consultation. This is gap #4.
- **Step 10c — describer fan-out** (`scan.py:1093-1167`): fills only `— TODO` rows (`file_map_todo_paths`, `:1097`).
- **Narrator stamp loop** (`scan.py:902-924`): after `inject_narrative`, stamps the anchor to HEAD `if head and prose.strip()` and records the URI in `narr_stamped` (`:912-916`). This runs **before** Step 10b/10c.
- **Shared-anchor restamp** (`scan.py:1169-1193`): stamps `(uri in redescribed_uris) and (uri not in narr_stamped) and (not file_map_todo_paths(page))` — i.e. only once the dropped rows are refilled (review-fix `f74e8e36`).
- **`write_entities`** (`packages/wiki-io/src/wiki_io/entity_writer.py:896-1062`): per page, renders `new_content` via `_render_entity_page(..., existing_body=...)` → `_merge_preserved_sections` (`:569-611`), then compares `old_bytes == new_bytes` (`:999-1013`) to bucket the page as `unchanged` / `updated` / `created`.
- **`_merge_preserved_sections`** (`:569-611`) preserves human sections but resets the three **scanner-owned** sections — `## Narrative`, `## File map[ - <name>]`, `## Referenced in wiki` (`_is_scanner_owned_heading`, `:540-544`) — to their template placeholders. Later steps re-populate them.

### 1.1 The updated-churn (root of #3)

Because `_merge_preserved_sections` resets all three scanner-owned sections to placeholders, `new_content` differs from the on-disk page for **every page that has any real Narrative / File map / Referenced-in-wiki content** — so `old_bytes != new_bytes` and the page is bucketed `updated` on every scan. The page is then physically rewritten (placeholder) and re-populated by the M2a restore loop / Step 10b / the referenced-in-wiki regen.

Consequences:
1. The scan report's `updated` count is meaningless (≈ all populated pages, every scan).
2. Unchanged pages are needlessly rewritten twice (mtime churn; a brief on-disk placeholder window).
3. **The commit-gate is masked.** `refreshed = created | updated` already contains essentially every page, so Step 10b's `fm_targets = refreshed | commit_dirty` is dominated by `refreshed`; the `commit_dirty` union only changes the outcome when `updated` is forced empty (which is why M2b's trigger-gap test monkeypatches `write_entities`). Fixing the churn is what makes `commit_dirty` the real trigger for content-changed-but-structurally-unchanged pages.

The narrator LLM is **not** churned: `needs_narrative` only gains an `updated` page when `_detect_structural_change` is also true (`entity_writer.py:1007`), so the churn wastes deterministic file-map work, not model calls.

### 1.2 The narrator-path residual (Part 3 bug)

The restamp's refill-gate (`f74e8e36`) closed the *file-map* stamp path but not the *narrator* stamp path. A commit-dirty page can:
1. re-narrate with good prose → narrator loop stamps anchor = HEAD and adds the URI to `narr_stamped` (`:912-916`), **and**
2. drop a changed file-map row to `— TODO` (`redescribed_uris`), then
3. have Step 10c **fail** to refill that row (e.g. a Bedrock describer error; cf. the Haiku daily-token-quota throttling).

The restamp skips the page (it's in `narr_stamped`), but the anchor already advanced via step 1. Next scan: `changed_files_since(repo, HEAD, …)` returns `[]` → page not commit-dirty → the `— TODO` is stranded permanently. The narrator stamp advances the anchor without checking `file_map_todo_paths`; #3 makes this combination the common case on commit-dirty pages, so it must be fixed here.

---

## 2. Architecture decisions

### D1 — #4 reuses M2b's mechanism verbatim, with `node.path` as the suite base

`test_suite` nodes populate the `path` column (`packages/graph-io/src/graph_io/test_suites.py:347,358`) and `_list_by_kind` reads it via the 6-column projection, so `node.path` == the suite's repo-relative root == the `sub_path` `changed_files_since` expects and the base `build_dir_file_map(repo / node.path)` already uses. Suite `## File map` Description rows are keyed package-root-relative to that same root (`_extract_file_map_descriptions`/`_section_path_context`, `entity_writer.py:1188-1247`). Therefore `_changed_rel_paths(changed, node.path)` matches suite rows with **no new transform** — #4 is M2b with `test_suite` added to the kind loop and the suite file-map branch brought up to parity. (No attrs fallback needed; `node.path` is authoritative.)

### D2 — #4 keeps suites identical to package/app; no suite-specific gate

Suites carry `## Narrative` (template `entity-test-suite.md:15`) and are narrated through the same `needs_narrative` path, so they already receive a `last_updated_commit` anchor. Anchorless suites (never narrated) stay on the structural gate (M2a D-C); unknown-anchor suites drop all preserved rows and re-describe once, then re-stamp (M2a/M2b D-D). Same semantics as package/app — no divergence.

### D3 — #3 fix: surgical comparison + skip-write (Approach B), all three scanner sections

In `write_entities`, change only the bucketing decision: compare frontmatter in full and the body **modulo scanner-owned section bodies** (the bodies of `## Narrative`, `## File map`, `## Referenced in wiki` are normalized out of both sides; preamble + human sections + structure compared in full). When `existed` and the comparison is equal → `unchanged` and **skip the write entirely** (leave the real on-disk content untouched). Otherwise → `updated`/`created` and write as today; the M2a restore loop, Step 10b preserved-drop, and the referenced-in-wiki regen all run unchanged.

- Covers all three scanner sections (chosen scope) with one comparison helper that reuses `_split_h2_sections` + `_is_scanner_owned_heading`.
- M2a snapshot/restore and M2b preserved-drop are **untouched** — B coexists with the landed M2b code and needs no coordination.
- **Approach A** (stop resetting scanner sections in `_merge_preserved_sections`; preserve-then-overwrite; *delete* the snapshot/restore machinery and remove the placeholder crash-window) is the cleaner end-state but rewrites where M2b sources its `preserved` descriptions. **Rejected for M2c; recorded as a planned post-M2c consolidation follow-up** (§4) — it net-deletes code, so it ages well as a later cleanup.

### D4 — Part 3 fix: one refill-gated anchor-stamp pass after Step 10c

Stop stamping in the narrator inject loop. Instead, the narrator loop only **records** good-prose URIs (preserving the empty-prose guard's intent: empty narration alone records nothing). After Step 10c, a single pass stamps each page in `(good_prose_uris | redescribed_uris)` to HEAD **iff `not file_map_todo_paths(page)`**. This makes the refill-gate apply uniformly to both the narrative-driven and file-map-driven stamp reasons, closing the stranded-TODO path. A page with good prose but an unrefilled dropped row stays unstamped → commit-dirty next scan → describer retried. (A purely-narrated page with no file-map work has no TODO rows, so the gate is a no-op for it and behavior is unchanged.)

---

## 3. The changes

### 3.1 Part 1 — test_suite commit-gated re-description (#4)

1. **`_commit_dirty_changes`** (`scan.py:583`): extend the kind loop to `("package", "app", "test_suite")`. Everything else in the helper is kind-agnostic (`node.path`, anchor read, `changed_files_since`, `_entity_page_path`). Suite URIs now appear in the returned dirty map and flow into `needs_narrative` via the existing `needs_narrative.update(commit_dirty.keys())` — so a content-changed suite re-narrates and re-stamps like a package.
2. **Step 10b-ts** (`scan.py:1044`): bring the suite branch to package/app parity — change the trigger from `if refreshed:` to the suite slice of `fm_targets` (`refreshed | commit_dirty`), apply the preserved-drop using `_changed_rel_paths(changed, node.path)` (with the `changed is None` → drop-all branch), and add re-described suite URIs to `redescribed_uris`. Suites are already appended to `file_mapped_pages` (`:1067`), so Step 10c and the (Part-3-unified) restamp pick them up unchanged.

### 3.2 Part 2 — updated-churn reduction (#3, Approach B)

In `write_entities` (`entity_writer.py:999-1013`):
- Add a helper `_equal_modulo_scanner(old_text, new_text) -> bool` (reusing `_split_h2_sections` + `_is_scanner_owned_heading`): equal iff the two pages have identical frontmatter, identical preamble, identical non-scanner sections, and identical scanner-section **headings** (bodies ignored).
- When `existed`: if `_equal_modulo_scanner(old, new_content)` → `unchanged.append(uri); continue` **without writing**. Else write `new_content` and `updated.append(uri)` as today (structural-change → `needs_narrative` logic unchanged).

Frontmatter changes still force `updated` (compared in full). Human-section or structural edits still force `updated`. Only differences confined to scanner-owned section bodies are absorbed.

### 3.3 Part 3 — unified anchor stamping (residual fix)

In `scan.py`:
- Narrator inject loop (`:912-916`): drop the inline `set_frontmatter_value(...)`; instead add the URI to a `good_prose_uris: set[str]` when `head and prose.strip()`. (Keep `entities_narrated` tracking.) `narr_stamped` is removed in favor of the unified pass.
- Replace the restamp block (`:1169-1193`) with a single post-Step-10c pass over `file_mapped_pages` **and** any narrated-only pages: for each page whose URI is in `good_prose_uris | redescribed_uris`, stamp `last_updated_commit = head` iff `not file_map_todo_paths(page_path)`. (Narrated-only pages with no file-map injection have no TODO rows → always stamp, preserving M2a behavior.)

Implementation note: the unified pass must reach narrated pages that were *not* file-mapped this scan. Either iterate a combined `{uri: page_path}` map built from both the narrator loop and `file_mapped_pages`, or resolve narrated page paths via `_entity_page_path`. The plan picks the concrete shape; the rule is invariant: **stamp HEAD iff (good prose OR re-described) AND no remaining file-map TODO.**

---

## 4. Scope

**In scope**
- #4: commit-gated file-map re-description + re-narration for `test_suite` (§3.1).
- #3: updated-churn reduction via Approach B over all three scanner sections (§3.2).
- Part 3: unified, refill-gated anchor stamping closing the narrator-path stranded-TODO bug (§3.3).

**Out of scope (explicit boundaries)**
- **Approach A** (invert `_merge_preserved_sections` to preserve-then-overwrite; delete the M2a snapshot/restore + the M2b pre-write file-map snapshot; remove the placeholder crash-window). Rejected for M2c (collides with landed M2b internals); recorded here as the **next consolidation follow-up** once M2c is stable — it net-deletes code.
- **Template reconciliation** (#1, → M2d) and **human-section drift flagging** (#2, → M2e).
- **Content-hash ledger** — rejected (M2b D1).
- No new LLM roles or fan-outs; no frontmatter-schema changes.

---

## 5. Tests (success criteria)

`code_reader`/narrator mocked at the `SubagentPool.run_all` boundary (project fixture pattern; mirror `test_commit_gated_file_map.py`).

**Part 1 — test_suite (#4)**
1. **Suite re-describe on change** — anchored suite with a filled file map; one tracked file under the suite root changes since the anchor → that row resets to `— TODO` and is re-described; unchanged suite rows keep their prior descriptions.
2. **Suite trigger-gap regression** — a commit-dirty suite that `write_entities` reports as **unchanged** (force `refreshed` empty) still gets its file map re-injected and the changed row re-described. Fails without the `commit_dirty` extension on the suite branch.
3. **Suite path-namespace** — a changed file nested under the suite root matches and re-describes (guards the repo-relative vs suite-root-relative transform).
4. **Suite `--no-narrate`** — file-map structure refreshes but no suite row is re-described and no suite anchor is stamped.

**Part 2 — churn (#3)**
5. **No-op rescan reports zero `updated`** — a second scan with no repo change buckets every populated page `unchanged`; the page files are byte-identical and not rewritten (assert mtime/`unchanged` count).
6. **Human-section edit forces `updated`** — hand-edit a `## Purpose` body → that page is `updated`; scanner-only pages stay `unchanged`.
7. **Frontmatter-only change forces `updated`** — a scanner-frontmatter delta buckets the page `updated` even with identical bodies.
8. **Idempotence across all three scanner sections** — a page with filled Narrative + File map + Referenced-in-wiki rescans to `unchanged`.

**Part 3 — unified stamping (residual)**
9. **Describer failure does not strand a TODO** — commit-dirty page re-narrates with good prose **and** drops a row; Step 10c describer returns nothing for that row → anchor is **not** advanced (page stays commit-dirty); next scan retries and (describer succeeds) refills + stamps. Fails against current `main` (narrator path stamps regardless).
10. **Narrated-only page still stamps** — a structurally-changed page that re-narrates (good prose) with no dropped file-map rows advances its anchor to HEAD (M2a behavior preserved).
11. **Empty narration alone still does not stamp** — preserved from M2b §3.4.

---

## 6. Key code touchpoints

- `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py`
  - `_commit_dirty_changes` (`:562-608`, loop `:583`) — add `test_suite`.
  - Step 10b-ts suite branch (`:1038-1071`) — trigger extension + preserved-drop + `redescribed_uris`.
  - Narrator inject loop (`:902-924`) — record `good_prose_uris`; remove inline stamp.
  - Restamp block (`:1169-1193`) — replace with the unified refill-gated pass (§3.3).
- `packages/wiki-io/src/wiki_io/entity_writer.py`
  - `write_entities` bucketing (`:999-1013`) — `_equal_modulo_scanner` + skip-write (§3.2).
  - `_split_h2_sections` (`:547`), `_is_scanner_owned_heading` (`:540`) — reused by the comparison helper.
- `packages/wiki-io/src/wiki_io/git_state.py` — `changed_files_since` (consumed; no change).
- `packages/graph-io/src/graph_io/test_suites.py:347,358` — confirms suite `node.path`.

---

## 7. Sequencing & dependencies

M2c depends on M2b (landed). Implement in order: **#3 first** (unmasks the gate — makes #4's integration behavior observable without monkeypatching, and makes the residual common), **then Part 3** (unify stamping on the now-load-bearing gate), **then #4** (extend to suites on top of the unified stamping). Each part is independently testable; #3 and Part 3 touch disjoint code (`entity_writer.write_entities` vs `scan.py` anchor logic), and #4 is additive to the suite branch.

---

## 8. Open questions

None blocking. The Approach-A consolidation (§4) is the recorded next cleanup; its trigger is M2c landing and M2b settling.
