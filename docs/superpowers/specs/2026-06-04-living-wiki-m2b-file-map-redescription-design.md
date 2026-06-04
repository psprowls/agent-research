# Living Wiki M2b — Commit-Gated File-Map Re-Description

**Date:** 2026-06-04
**Status:** Design — approved, ready for `writing-plans`.
**Author:** Pat (with code-verified findings)
**Milestone:** Living Wiki M2b (slice of M2 — "Commit-gated incremental updates").
**Builds on:** M2a (narrative persistence + commit-gate), landed on `main` 2026-06-03, commits `4c58f9bd`…`161472e4`.
**Roadmap:** `docs/superpowers/specs/2026-06-03-living-wiki-roadmap.md` (§3 D3, §4 "M2").

---

## 0. One-paragraph thesis

M2a built the commit-gate spine at **package/app narrative** granularity: `_commit_dirty_uris` calls `changed_files_since(repo, anchor, node_path)` and, if anything changed since the page's `last_updated_commit` anchor, re-narrates the page. That call already returns the **exact list of changed files** — M2a collapses it to a boolean. M2b finishes the spine by consuming that same list at **file-row** granularity: when a tracked file changes, its `## File map` Description row is re-described. The mechanism is one filtering step riding the **existing** `code_reader` describer pass — not a new fan-out, not a new change-detection engine, and (per the project's `## File map`-is-scanner-owned rule) not a new ownership model.

---

## 1. Where we are (code-verified)

The file-map description pipeline in `run_scan` (`packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py`):

1. **`_snapshot_file_map_descriptions(wiki)`** (`scan.py:112`) — *before* `write_entities` resets page bodies — captures filled Description cells into `prior_file_map_descs = {uri: {package_root_path: description}}`. This is a **cost cache**, not a human-authorship guarantee: it exists so an expensive `code_reader` description survives the M1 heading-aware re-render.
2. **Step 10b** (`scan.py:936-976`) — for each `package`/`app` in `refreshed = created | updated`, `inject_file_map(fm_page_path, file_map, preserved=prior_file_map_descs.get(uri))`. Preserved descriptions graft back onto rows whose paths still exist; every other row shows `— TODO`. (A parallel Step 10b-ts does the same for `test_suite` pages.)
3. **Step 10c** (`scan.py:1024+`) — `code_reader` fan-out fills **only** `— TODO` rows (`file_map_todo_paths(page_path)`); preserved descriptions are never overwritten. Steady-state cost is zero: a fully-described package has no TODO rows and dispatches no model call.

**The gap.** A file whose *content changed* keeps its preserved (now stale) description. It still has a path → it's grafted back by Step 10b → it's not a `— TODO` → Step 10c skips it. The description never refreshes.

### 1.1 The signal already exists

`changed_files_since(repo, since_sha, sub_path)` (`packages/wiki-io/src/wiki_io/git_state.py:59`):

```
Return repo-relative paths under sub_path that changed between since_sha and HEAD.
- Returns []   when there are no changes.
- Returns None when git is unavailable, the SHA is unknown, or sub_path isn't tracked.
```

M2a's `_commit_dirty_uris` (`scan.py:542`) already calls this per package/app and uses only its truthiness (`if changed is None or changed: dirty.add(uri)`). M2b consumes the **returned list**. Same call, finer granularity — this is why M2b is "finishing the spine," not a new mechanism.

---

## 2. Architecture decisions

### D1 — Change-detection signal: reuse the M2a anchor, not a content-hash ledger

The roadmap (§3 D3) named the embedding index's SHA256 content-hash pattern (`commands/query.py:768-806`) as the precedent for "changed materially." That guidance predates M2a. Now that every package/app page carries a `last_updated_commit` anchor, **git-diff-since-anchor is the more cohesive signal**:

- It's literally M2a's `changed_files_since` call, already wired and tested.
- One per-page anchor gives a single coherent semantics: *"this page (narrative **and** file map) reflects the repo as of commit X."*
- No new sidecar/ledger to populate, invalidate, or keep consistent with the markdown.

A content-hash ledger would be a parallel mechanism solving an already-solved problem. **Rejected.**

### D2 — Ownership: `## File map` descriptions are scanner-owned; re-describe freely

`.claude/rules/backward-compatibility.md` already classifies `## File map` as a **scanner-owned** section. Under that rule there is no human-authored content to protect in a file-map row: the snapshot/restore is a *cost cache*, not a durability guarantee. So on content change we **overwrite** the row with a fresh `code_reader` pass — no ownership marker, no flag-and-wait. Durable human notes belong in human-owned H2 sections (`## Purpose`, etc.), which are untouched by this slice.

(Considered and rejected: an ownership marker to preserve hand-edited rows — contradicts the scanner-owned classification and adds per-cell provenance state; flag-don't-edit — adds review surface and leaves rows stale until acted on.)

### D3 — Re-description rides the existing describer pass (drop-from-preserved)

Rather than a new "re-describe" fan-out parallel to Step 10c, M2b **drops changed paths from the `preserved` dict** before `inject_file_map`. The changed rows re-emerge as `— TODO` and Step 10c's existing fan-out re-fills them. One code path fills rows; M2b just controls which rows are TODO. (A separate re-describe fan-out was rejected — it duplicates the describer wiring for no benefit.)

---

## 3. The change

### 3.1 Core (D3) — one filtering step

For each `package`/`app` page being file-mapped this scan, compute the changed set and remove it from `preserved`:

```
anchor  = <page's last_updated_commit>
changed = changed_files_since(repo, anchor, node_path)   # repo-relative paths, or None
# relativize repo-relative changed paths to package-root-relative (see 3.3)
changed_rel = { relativize(p, node_path) for p in (changed or []) }
preserved   = prior_file_map_descs.get(uri) or {}
preserved   = { p: d for p, d in preserved.items() if p not in changed_rel }
inject_file_map(fm_page_path, file_map, preserved=preserved)
```

**`changed is None`** (anchor unknown to the repo / untracked) mirrors M2a's self-correcting stance, where an unknown anchor counts as dirty. Here it means no preserved row can be trusted, so **drop all preserved rows** — every row becomes a TODO and is re-described. A stale/unknown anchor thus forces one full re-describe, then re-stamps to HEAD.

Pages with **no anchor** (never narrated) are left on the existing structural gate — preserved grafts back as today; no re-description. (Matches M2a D-C.)

### 3.2 Load-bearing trigger extension (the part without which 3.1 is inert)

Step 10b currently runs only for `refreshed = created | updated` (write_entities' structural delta). A package whose **source changed with no structural/frontmatter change** is **not** in `refreshed` — M2a routes it only into `needs_narrative` (via `_commit_dirty_uris`), never into `updated`. So today its file map is never re-injected and 3.1 can't fire.

**M2b extends the file-map injection trigger to `refreshed | commit_dirty`** (package/app), reusing the very `commit_dirty` set M2a computes at `scan.py:787`. This mirrors what M2a did for the narrator gate (`needs_narrative.update(commit_dirty)`); M2b additionally lets `commit_dirty` drive file-map injection. **This is the load-bearing change.**

For a commit-dirty-but-not-refreshed page, `write_entities` did not reset its body, so the page still holds its prior file map on disk; re-injecting (with changed paths dropped from `preserved`) is what converts the changed rows to TODO. Structure (adds/removes) is re-derived by `build_file_map` from graph node paths regardless, so a non-refreshed page's structure is unchanged by definition and only descriptions move.

### 3.3 Path-namespace reconciliation

`changed_files_since` returns **repo-relative** paths; `preserved` keys are **package-root-relative** (`_extract_file_map_descriptions` keys off `package_root_path`). The drop step must relativize changed paths against `node_path` before set-matching. Without this, nothing matches and every changed row is silently preserved-stale. Pinned as an explicit, tested transform (paths outside `node_path` simply don't match and are ignored).

### 3.4 Shared-anchor stamping + the empty-prose guard (required rider)

The anchor (`last_updated_commit`) is the baseline 3.1 diffs against. Today it is stamped only in the narrator inject loop after `inject_narrative` (`scan.py:880-883`). Two coupled facts:

- commit-dirty packages are already in `needs_narrative` → they re-narrate → the anchor advances in the **same** scan they're re-described. Narrative and file map share **one anchor**.
- The deferred **empty-prose stamp guard** (`if head and prose.strip():`) skips the stamp when narration returns empty. If that scan *also* re-described file-map rows, the baseline would not advance, so the next scan re-describes the same files again (cost churn + non-idempotence).

**Rule:** stamp the anchor to HEAD when **either** non-empty narration **or** a file-map re-description happened this scan. This preserves the guard's intent (empty narration *alone* cannot mint a sticky "up-to-date" anchor) while ensuring real re-description advances the baseline. The empty-prose guard is therefore an **in-scope, required rider** — it is entangled with the anchor that gates re-description, not an independent cleanup.

Implementation note: the inject loop currently stamps per-narrated-page. M2b needs the stamp to also fire for pages that were re-described but produced empty/no narration. Track the set of pages whose file map was re-described this scan and ensure each gets a HEAD stamp, deduped against the narrator stamp.

---

## 4. Scope

**In scope**
- Commit-gated file-map row re-description for `package` / `app` entities (D1–D3, §3.1–3.3).
- Empty-prose stamp guard + shared-anchor stamp rule (§3.4).

**Out of scope (explicit boundaries)**
- **`test_suite` re-description.** `_commit_dirty_uris` covers only package/app; suites re-describe only on structural refresh today. Extending commit-dirty to suites is a clean follow-up — keeping M2b's gate identical to M2a's avoids scope creep. Step 10b-ts is left as-is.
- **Updated-churn reduction (#4).** M2a's reset-then-restore of `## Narrative` makes `write_entities` mark every narrated page `updated`, inflating `refreshed`. It does **not** break M2b (preserved still grafts unchanged rows; no spurious re-description) — it only over-includes pages in file-map injection, which is wasteful, not incorrect. Its fix lives in the narrative reset path, not the file-map path. **Deferred to its own quick task.**
- **Template reconciliation (#2)** and **human-section drift flagging (#3)** — separate M2 slices.
- **Content-hash ledger** — rejected (D1).

---

## 5. Tests (success criteria)

Verifiable end-to-end with `code_reader` mocked at the LangChain boundary (project fixture pattern):

1. **Re-describe on change** — anchored package with a filled file map; mutate + commit one tracked file; re-scan → that row resets to `— TODO` and the mocked describer re-fills it; **unchanged rows keep their prior descriptions** (cost cache intact).
2. **Trigger-gap regression (§3.2)** — a package that is commit-dirty but **not** structurally `updated` still gets its file map re-injected and the changed row re-described. Fails without the `commit_dirty` trigger extension.
3. **Path-namespace (§3.3)** — a changed file nested under the package root matches and re-describes; guards against the repo-relative vs package-root-relative bug silently preserving stale rows.
4. **Shared-anchor advance (§3.4)** — after a re-description scan, `last_updated_commit` advances to HEAD; a no-op re-scan re-describes nothing (idempotence).
5. **Empty-prose guard (§3.4)** — empty narration *alone* does not stamp the anchor; a scan that re-describes file-map rows *does* advance it.
6. **Unknown anchor self-corrects (§3.1)** — a page whose anchor SHA is unknown to the repo drops all preserved rows and re-describes fully once, then re-stamps.
7. **`--no-narrate`** — file-map structure refreshes but no rows are re-described and no anchor is stamped (LLM-free path unchanged; Step 10c is already `narrate`-gated).

---

## 6. Key code touchpoints

- `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py`
  - `_commit_dirty_uris` (`:542`) — already computes the per-package changed signal; M2b needs the **changed-file list**, not just the boolean (extract or recompute per page).
  - Step 10b file-map injection (`:936-976`) — extend trigger to `refreshed | commit_dirty`; apply the preserved-drop (§3.1, §3.3).
  - Narrator inject / stamp loop (`:865-891`) — empty-prose guard + shared-anchor stamp for re-described pages (§3.4).
- `packages/wiki-io/src/wiki_io/git_state.py:59` — `changed_files_since` (consumed as a list; no change expected).
- `packages/wiki-io/src/wiki_io/entity_writer.py` — `inject_file_map`, `file_map_todo_paths`, `set_frontmatter_value`, `_extract_file_map_descriptions` (path-namespace source of truth).

---

## 7. Open questions

None blocking. Deferred items (test_suite re-description, #4 churn) are scoped out in §4 and tracked as follow-ups.
