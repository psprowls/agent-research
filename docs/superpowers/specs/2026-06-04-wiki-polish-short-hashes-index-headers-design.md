# Wiki Polish — Short Commit Hashes + Per-Entity Index Headers + `updated`-Field Confirmation

**Date:** 2026-06-04
**Status:** Design — ready for `writing-plans`.
**Author:** Pat (with code-verified findings)
**Scope:** Three independent, small browsing-fixes against the `agent-research-bedrock` wiki. No milestone; purely additive polish. No migration (per `.claude/rules/backward-compatibility.md` — rebuild on schema change).

---

## 0. One-paragraph thesis

Three unrelated wiki-quality fixes, bundled because each is a few lines: (1) abbreviate the git SHAs written into entity-page frontmatter (`last_updated_commit`, and downstream `drift_checked_commit` / `detected_commit`) from full 40-char to git's canonical adaptive short form, shortening at the single write boundary so every git consumer keeps resolving them; (2) give each entity in `index.md`'s `## By Kind` section its own `####` header instead of a bare name bullet, so each entity has a TOC anchor / deep-link target; (3) confirm — and document for the record — that the workspace `CLAUDE.md` instruction to refresh the `updated:` frontmatter field is **not** stale (the field is real and consumed by lint), and leave it unchanged. Items 1 and 2 touch code + tests; item 3 is a confirmation with no code change.

---

## 1. Item 1 — Short commit hashes in wiki frontmatter

### 1.1 Where we are (code-verified)

All commit SHAs originate from `git rev-parse HEAD` (full 40-char) and reach wiki frontmatter through one path:

- `packages/graph-io/src/graph_io/update.py` stores the full HEAD SHA in the graph DB metadata key `last_indexed_commit`.
- `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py:1330-1331` stamps that value into a page's `last_updated_commit`:
  ```python
  set_frontmatter_value(
      page_path, LAST_UPDATED_COMMIT_KEY, head
  )
  ```
  where `head` is the full SHA read from the DB.
- `drift_checked_commit` (`scan.py:715`, `:720`) and the nested `detected_commit` (`scan.py:703`) are **not** computed from git — they are set to `anchor`, which is the page's own `last_updated_commit` value. So they inherit whatever form `last_updated_commit` already has.

**Consumer analysis — the blast radius:**

| Consumer | Site | Uses the SHA how | Short-safe? |
| --- | --- | --- | --- |
| Commit-gate narrative refresh | `wiki_io/git_state.py:59` `changed_files_since` → `git diff <sha>..HEAD` | git resolution | **Yes** — git resolves short SHAs |
| graph-io differential update | `graph_io/update.py` `_diff` → `git diff <prev>..HEAD` | git resolution | **Yes** |
| Drift "already-checked" guard | `scan.py:634-637` `meta.get("drift_checked_commit") == anchor` | exact string equality | **Yes, by construction** — both operands are read from the *same page's stored strings*; `drift_checked_commit` was written *as* `anchor`. Neither is re-abbreviated live, so they stay byte-identical until the narrative advances to a genuinely newer commit (the intended re-judge trigger). |

The only theoretical hazard — a page's `last_updated_commit` and `drift_checked_commit` being abbreviated to *different lengths* — cannot occur: `drift_checked_commit` is assigned the literal `anchor` string, never an independently-computed abbreviation.

### 1.2 Design

**D1 — Abbreviate at the single write boundary, via git (not slicing).**
The stamp value comes from the DB's stored *full* SHA, so naive `head[:7]` would not equal git's canonical abbreviation. Resolve it properly so the short form is canonical and unambiguous:

- **New helper** `packages/wiki-io/src/wiki_io/git_state.py`:
  ```python
  def short_commit(repo: Path, sha: str) -> str:
      """Abbreviate a SHA to git's canonical short form (adaptive length).

      Returns the input unchanged on any git failure — a full SHA is still
      git-resolvable, so callers never break."""
      out = _run(repo, "rev-parse", "--short", sha)
      if out is None or out[0] != 0 or not out[1].strip():
          return sha
      return out[1].strip()
  ```
  Mirrors the existing `_run`-based helpers (`head_commit`, `changed_files_since`).

- **Single-site change** in `scan.py`: compute `short_head = short_commit(repo, head)` **once** per scan (HEAD is the same for every page stamped in a run), and pass `short_head` to `set_frontmatter_value` at `scan.py:1331` in place of `head`. `drift_checked_commit` and `detected_commit` inherit the short form automatically via `anchor`.

**D2 — Leave the graph DB `last_indexed_commit` full.** It is internal metadata feeding `git diff prev..HEAD` (tolerates either form). Shortening it buys nothing and would add churn to a hot path. Out of scope.

**D3 — No migration.** Existing full-hash pages keep working (git resolves them); they shorten naturally on their next narrative refresh. Mixed full/short pages are harmless: the only cross-page comparison is git resolution, never equality.

### 1.3 Tests

- Unit: `short_commit(repo, full_sha)` returns a strict prefix of `full_sha`, shorter than 40, and `git rev-parse` resolves it back to `full_sha`. Failure path (bogus SHA / non-repo) returns the input unchanged.
- Integration (scan): after a scan that regenerates a narrative, the stamped `last_updated_commit` is the short form (length < 40), and `changed_files_since` still resolves it (no spurious dirty).

---

## 2. Item 2 — Per-entity headers in `index.md` (`## By Kind` only)

### 2.1 Where we are (code-verified)

`packages/wiki-io/src/wiki_io/index_generator.py` already emits, under `## By Kind` (line 751), an H3 per *kind* — `### Apps` / `### Packages` / `### Agent Plugins` (line 760, via `KIND_LABELS`). Each entity within a kind is a **bare name bullet** (line 762-763):
```python
for e in group:
    lines.append(_entity_bullet(e, collision_set, ""))   # "- [[…|name]] — summary"
    if e.kind in ("package", "app"):
        lines.extend(_render_pkg_nested(...))             # nested Test Suites / Dependencies
```
`_entity_bullet` (line 568-575) renders `- {link} — {summary}` with a collision-aware display name.

The `## Domains` tree (line 656+) nests packages under domain headers with the same `_render_pkg_nested` sub-bullets. **Per the user's decision, the Domains tree is left untouched** — extra headers there would push to H5/H6 and read as clutter.

### 2.2 Design

**D4 — In `_render_by_kind` only, replace each entity's name bullet with a `####` header (header replaces bullet).** Under the existing `### {Kind}` H3, each entity renders as:
```
#### graph-wiki-core

the hub — [[wiki/entities/pkg_graph-wiki-core|open page]]
  - Test Suites
    - [[…]]
  - Dependencies
    - [[…]]
```
Concretely, replace `scan`-of-line 762-770's body:
```python
for e in group:
    lines.append(f"#### {_entity_display_name(e, collision_set)}")
    lines.append("")
    link = _entity_pagelink(e, collision_set, label="open page")
    summary = f"{e.summary} — " if e.summary else ""
    lines.append(f"{summary}{link}")
    total += 1
    if e.kind in ("package", "app"):
        lines.extend(_render_pkg_nested(conn, e, sub_for_pkg, name_to_entity, collision_set))
    lines.append("")
```

- **Header text** uses the same collision-aware display name `_entity_bullet`/`_entity_wikilink` already compute (extract a small `_entity_display_name(entity, collision_set)` helper, or inline the existing logic — no new disambiguation rules).
- **Link label** becomes `open page` (a focused `_entity_pagelink(entity, collision_set, label=...)` helper, or pass a label through the existing `_entity_wikilink`), since the entity name now lives in the header and need not repeat in the link text.
- **Summary** moves onto the line beneath the header; omitted-summary entities render just the link line.
- **`_render_pkg_nested` is reused unchanged** (it is a shared, byte-identical-with-Domains invariant, D-01). Its sub-lists start at 2-space indent; under a `####` header markdown still renders them as a normal list. No depth-math changes, no Domains impact.
- Entities that are not `package`/`app` (e.g. `agent_plugin`) get a header + link line, no nested sub-lists — same as today minus the bullet.

**D5 — Scope guard.** No change to `_render_domain_section`, `_entity_bullet` (still used by Domains + nested sub-lists), section ordering, or `BY_KIND_ORDER`.

### 2.3 Tests

`packages/wiki-io/tests/test_index_generator.py`:
- Update the By-Kind assertions (the `### Apps` / `### Packages` / `### Agent Plugins` region, ~line 547-557) to also assert each entity now emits a `#### {name}` header followed by the summary + `|open page]]` link line, and that the old bare `- [[…|name]]` *name* bullet is **gone** for by-kind entities.
- Assert the nested `  - Test Suites` / `  - Dependencies` sub-bullets still appear under a package's header (reused `_render_pkg_nested`).
- Assert the `## Domains` tree is unchanged (no new headers there).
- Existing section-order integration test (~line 678-696) and "no flat Dependencies/Test Suites groups" (~line 760) must still pass unchanged.

---

## 3. Item 3 — `updated` frontmatter instruction (confirmation, no change)

### 3.1 Finding

`packages/workspace-io/src/workspace_io/assets/CLAUDE.md.template:48`:
```
- Update `updated:` frontmatter whenever you touch a page.
```
This is **not stale**. The `updated` field is real and consumed:
- All 16 page templates in `packages/wiki-io/src/wiki_io/assets/page-templates/` carry an `updated: <YYYY-MM-DD>` placeholder.
- `packages/graph-wiki-core/src/graph_wiki_core/commands/lint.py:257-264` reads `updated` to flag **stale pages** (and displays it at :382).
- The ingestor agent (`plugins/graph-wiki/agents/ingestor.md:50`) lists it as a required field.

The nuance: **no code auto-writes `updated`.** It is a manual-maintenance contract for human/ingest-authored pages. Scanner-owned entity pages instead track freshness via `last_updated_commit` (git SHA, item 1) and never touch `updated` — so entity pages may read as "stale" to lint, which is a known, accepted asymmetry.

### 3.2 Decision

**Leave the instruction as-is.** No code change. Documented here for the record so a future browser doesn't re-flag it as stale. (Decision per user: the generic instruction stays; entity pages' lack of a maintained `updated` field is accepted.)

---

## 4. Files touched (summary)

| Item | File | Change |
| --- | --- | --- |
| 1 | `packages/wiki-io/src/wiki_io/git_state.py` | add `short_commit(repo, sha)` helper |
| 1 | `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py` | compute `short_head` once; stamp `last_updated_commit` with it at :1331 |
| 1 | `packages/wiki-io/tests/` + core scan tests | unit + integration for short stamping |
| 2 | `packages/wiki-io/src/wiki_io/index_generator.py` | `_render_by_kind`: per-entity `####` header replaces name bullet; small display-name / page-link helpers |
| 2 | `packages/wiki-io/tests/test_index_generator.py` | update By-Kind assertions |
| 3 | — | none (confirmation only) |

## 5. Non-goals

- No migration / bulk-rewrite of existing pages (rebuild-on-change rule).
- No change to the graph DB `last_indexed_commit` form.
- No per-entity headers in the `## Domains` tree.
- No change to the `updated` field, its templates, or lint's use of it.
