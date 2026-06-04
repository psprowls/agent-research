# Living Wiki — `agent_plugin` M2 Parity (Design)

**Date:** 2026-06-04
**Status:** Design spec — ready for `writing-plans`.
**Author:** Pat (enriched with code-verified findings)
**Milestone:** "agent-plugin parity" — the deferred follow-up to M2 (see the roadmap's §7 sequencing: M2a–M2e → **agent-plugin parity** → M3 → M4 → M5).
**Source roadmap:** `docs/superpowers/specs/2026-06-03-living-wiki-roadmap.md` (§4 M2).

> **Thesis.** The Living Wiki M2 work (commit-gated incremental updates: preserve human prose, refresh `## Narrative` only when code changed, regenerate scanner-owned content from the graph) was built for `package`/`app`/`test_suite` and **silently skipped `agent_plugin`**. The skip is not one gap but four, and one of them is an active correctness bug (the component tables freeze after first creation). This spec brings `agent_plugin` to full M2 parity.

---

## 1. Where we are (code-verified against `main`)

`agent_plugin` entity pages are produced by the same `write_entities` → narrator → post-pass pipeline as every other kind, but four M2 behaviors that the `package`/`app`/`test_suite` kinds received never reached `agent_plugin`:

### 1.1 Gap A — the component tables are silently frozen (active bug)

An `agent_plugin` page carries six scanner-derived data tables — `## Commands`, `## Agents`, `## Skills`, `## Scripts`, `## Hooks`, `## MCP servers` — rendered every scan by `_agent_plugin_table_variables(conn, node)` (`wiki-io/entity_writer.py:891-928`) from `describe_agent_plugin`. These are a **free, deterministic projection of the graph**: the cell text (a command's description, a skill's description, an agent's model/tools) is extracted **verbatim** from the plugin's own source frontmatter at graph-build time (`graph-io/agent_plugins.py:78-232`; `yaml.safe_load` on the `---` block → `fm.get("description")`). **No LLM is involved** at any stage — unlike the File Map, whose Description cells are genuine `code_reader` LLM output.

The bug: the M1/M2d **preserve-then-overwrite (PTO) merge** (`_merge_preserved_sections`, `entity_writer.py:588-647`) treats any heading not in the scanner-owned set (`## Narrative`, `## File map`, `## Referenced in wiki`; `_is_scanner_owned_heading`, `:533`) as **human-owned and preserves it from the on-disk page**. The six table headings are not scanner-owned, so on every re-scan the freshly-rendered tables (substituted into the template body at `entity_writer.py:1028`, then merged at `:682`) are **discarded** in favor of the stale on-disk copy (merge branch `elif heading in existing_by_heading:` → takes the existing body). There is **no post-pass** that re-injects them (unlike `## File map`, which `inject_file_map` rewrites at scan Step 10b).

**Consequence:** once an `agent_plugin` page exists, adding/removing/renaming a command, skill, or agent in the source **never updates the page's tables**. They are frozen at first-creation state. This is collateral damage from M1 introducing the heading-aware merge — the merge cannot tell a scanner-derived data table from a hand-written prose section, because both are just non-scanner-owned H2s.

### 1.2 Gap B — `## Narrative` is not commit-gated

`_commit_dirty_changes` (`scan.py:521-567`) computes which entities' files changed since their `last_updated_commit` anchor and drives commit-gated re-narration. Its kind loop hardcodes the triple:

```python
for kind in ("package", "app", "test_suite"):   # scan.py:554
```

`agent_plugin` is absent, so an `agent_plugin`'s `## Narrative` re-narrates **only** on a frontmatter structural-key change or first creation — never on a git diff of the plugin's files. It misses the entire "refresh only what changed since `last_updated_commit`" engine (M2a).

### 1.3 Gap B-prerequisite — `agent_plugin` nodes are pathless

`agent_plugin` nodes are emitted with `path=None` (`graph-io/agent_plugins.py:229`; the docstring notes "Nodes carry `path=None` (like the retired plugin nodes)"). The commit-gate diffs a node's directory via `changed_files_since(repo, anchor, node_path)`, which needs a real path. The plugin's directory **is** known at emit time (`plugin_dir = manifest_path.parent.parent`, `:208`) — it simply isn't stored. `path=None` is a stale modeling choice from before commit-gating existed; nothing depends on it (no test asserts it — `test_emit_creates_one_node_with_manifest_fields` selects only `name, attrs_json, uri`; no scan pass special-cases pathless nodes; the template never references a path).

### 1.4 Gap C — anchor stamping is unreliable

The refill-gated post-pass that stamps `last_updated_commit` (`scan.py` after Step 10c) covers `narrated_page_paths ∪ file_mapped_pages ∪ (good_prose_uris | redescribed_uris)`, gated on `not file_map_todo_paths(page)`. `agent_plugin` reaches it only via the narrator path (`narrated_page_paths` / `good_prose_uris`), which today fires only on structural/first-creation narration. Without Gap B, the commit-gate has no reliably-advancing anchor to gate against — and M2e's drift gate (`drift_checked_commit != last_updated_commit`) is therefore **inert for `agent_plugin`** even though `DRIFT_TARGET_KINDS` already lists it (`scan.py:587-589`).

### 1.5 Gap D — M2b (File-map re-description) has no analog (no work needed)

`agent_plugin` has **no `## File map`** (confirmed: `entity-agent-plugin.md` has `## Narrative`, `## Referenced in wiki`, `## Purpose`, the six data tables, and `## How it fits together` — no File map). The M2b machinery exists solely to preserve and commit-gate **expensive LLM file descriptions**; `agent_plugin`'s structural payload is the six deterministic tables, which have no LLM cost. So M2b has no analog here — the tables just need to stop being frozen (Gap A). This is a deliberate non-gap, recorded so the parity is provably complete.

### 1.6 Narrator runs blind for `agent_plugin`

`build_entity_narrative_prompt(node, kind, file_map_text, relations)` (`scan.py:315-372`) appends grounding context **only** for `kind == "package"` (the file listing). For `agent_plugin`, `generate_narrative` passes `file_map = ""` (`scan.py` Step 9b), so the narrator sees only URI + name + relations — none of the plugin's actual commands/skills/agents. The narrative is correspondingly thin, which also weakens M2e drift judging (the judge compares human sections against this narrative).

### 1.7 Incidental: the suite-branch `no_file_map` asymmetry

The Step 10b package/app File-map branch is guarded `if fm_targets and any(fm_list_fns) and not no_file_map:`, but the Step 10b-ts test-suite branch is guarded only `if fm_targets:` (`scan.py:969`) — it ignores `--no-file-map`. The M2e spec explicitly deferred this one-line cleanup "to the agent-plugin parity plan."

---

## 2. Where we want to be

An `agent_plugin` page is a first-class M2 citizen:

- Its six data tables **always reflect the current graph** (re-rendered every scan; never frozen).
- Its `## Narrative` **refreshes only when the plugin's files changed** since `last_updated_commit`, on the same commit-gate as `package`/`app`/`test_suite`.
- Its `last_updated_commit` anchor **advances reliably**, which in turn activates M2e drift flagging for the page's human sections (`## Purpose`, `## How it fits together`).
- Its narrative is **grounded in the plugin's component inventory**, so the prose is substantive and drift judging has real ground truth.

All while honoring the section-ownership model: human sections (`## Purpose`, `## How it fits together`, any user-added H2) remain preserved across re-scan.

---

## 3. Architecture decisions

### D1 — Generalize the ownership model with a **scanner-data** class (fixes Gap A)

The page-section ownership model gains a fourth class. Each entity H2 is now one of:

| Class | Headings | Refresh policy |
|---|---|---|
| **scanner-prose** | `## Narrative` | LLM-generated; preserved by the merge, overwritten by `inject_narrative` only when regenerated (commit-gated) |
| **scanner-filemap** | `## File map[ - …]` | deterministic skeleton + LLM descriptions; `inject_file_map` post-pass, M2b commit-gated descriptions |
| **scanner-backlink** | `## Referenced in wiki` | regenerated every scan by `regenerate_referenced_in_wiki` |
| **scanner-data** *(new)* | `## Commands`, `## Agents`, `## Skills`, `## Scripts`, `## Hooks`, `## MCP servers` | **deterministic graph render; regenerated every scan directly from the freshly-substituted template body — never sourced from disk** |
| **human** | `## Purpose`, `## How it fits together`, any user-added H2 | preserved from disk |

**Why "regenerate from template" and not a post-pass inject:** the tables are already rendered into the template body (token substitution at `entity_writer.py:1028` → `_render_entity_page`) before the merge runs. The only bug is the merge *discarding* that fresh render. So the fix is to make the merge **keep the template body** for scanner-data headings, rather than adding an `inject_agent_plugin_tables` scan step. No new scan plumbing; no LLM; no commit-gate.

**Why no commit-gate on the tables:** a deterministic render needs none. A no-op re-scan re-renders byte-identical tables from an unchanged graph → the page is byte-identical → `write_entities` buckets it `unchanged` (no churn). A commit-gate would add plumbing to protect content that costs nothing and could only make the page **lag** the graph (e.g. a full rebuild after a classifier change, where the plugin's own files didn't change in git). The faithful File-Map analogy supports this: the *deterministic* part of a File Map (the `build_file_map` skeleton) is also rebuilt every scan without a gate; only the *LLM* part (descriptions) is gated. `agent_plugin` tables are entirely the deterministic kind. The LLM part of an `agent_plugin` page is the `## Narrative` — and that **is** commit-gated (D2).

**The merge edit** (`_merge_preserved_sections`, `entity_writer.py:588-647`):

1. Add a module constant near `_is_scanner_owned_heading`:
   ```python
   # Living Wiki agent-plugin parity (D1): scanner-DATA sections — deterministic
   # graph projections rendered into the template every scan. Unlike scanner-prose
   # / scanner-filemap (preserved then overwritten by an inject post-pass), these
   # are template-authoritative: the merge keeps the freshly-rendered template body
   # and never sources them from disk, so they can never freeze. These headings
   # appear only on the agent_plugin template.
   SCANNER_DATA_HEADINGS: frozenset[str] = frozenset({
       "## Commands", "## Agents", "## Skills",
       "## Scripts", "## Hooks", "## MCP servers",
   })
   ```
2. In the existing-section classification loop, exclude scanner-data headings from `existing_by_heading` (so they are never treated as human / sourced from disk):
   ```python
   for heading, chunk in secs_e:
       if _is_scanner_owned_heading(heading):
           existing_scanner_by_token.setdefault(_scanner_section_token(heading), chunk)
       elif heading in SCANNER_DATA_HEADINGS:
           continue  # template-authoritative; never sourced from the on-disk page
       else:
           existing_by_heading.setdefault(heading, chunk)
   ```
3. In the template-section loop, take the freshly-rendered template chunk for scanner-data headings:
   ```python
   for heading, chunk in secs_t:
       template_headings.add(heading)
       if _is_scanner_owned_heading(heading):
           token = _scanner_section_token(heading)
           out.append(existing_scanner_by_token.get(token, chunk))
       elif heading in SCANNER_DATA_HEADINGS:
           out.append(chunk)  # always the fresh graph render
       elif heading in existing_by_heading:
           out.append(existing_by_heading[heading]); consumed.add(heading)
       else:
           out.append(chunk)
   ```
   *(Step 2 alone is technically sufficient — with scanner-data headings absent from `existing_by_heading`, they fall through to the final `else: out.append(chunk)`. The explicit branch in step 3 is belt-and-suspenders for clarity and reorder-safety.)*
4. The user-added-trailing loop already skips headings in `template_headings` (and scanner-data headings are in the agent_plugin template, hence in `template_headings`). Add `or heading in SCANNER_DATA_HEADINGS` to its skip condition for robustness.

**Idempotence & ownership-rule compatibility:** `_merge_preserved_sections(t, t) == t` still holds (scanner-data → template chunk == `t`'s chunk). This refines the backward-compat rule (`.claude/rules/backward-compatibility.md`): the six table sections are **scanner-owned** content (regenerable at will), not human-owned. The rule's wording — which currently lists `## Purpose`/`## Public API` as the human examples and "any hand-added H2" as human — should note that the agent_plugin data tables are scanner-owned despite not being in the prose/filemap set.

### D2 — Add `agent_plugin` to the commit-gate, with a real node path (fixes Gaps B + C)

1. **Give `agent_plugin` nodes their directory** (`graph-io/agent_plugins.py:229`). Replace `path=None` with the plugin dir relative to the repo root:
   ```python
   plugin_rel = plugin_dir.relative_to(repo_root).as_posix()
   nodes.append(GraphNode(kind="agent_plugin", name=name, path=plugin_rel, line=None, attrs=attrs))
   ```
   Update the docstring (drop the "Nodes carry `path=None`" note). **This requires a full graph rebuild** to backfill the path on existing graphs (consistent with the repo's "classification-logic change → full rebuild" rule); `cg update` is incremental and will not re-emit unchanged plugins.

2. **Add `agent_plugin` to the commit-dirty loop** (`scan.py:554`):
   ```python
   for kind in ("package", "app", "test_suite", "agent_plugin"):
   ```
   Now an `agent_plugin` whose files changed since its `last_updated_commit` becomes commit-dirty → enters `needs_narrative` → re-narrates, exactly the `package`/`app` path. An `agent_plugin` page with **no** anchor yet is treated as dirty (the existing unknown-anchor branch), so the first post-landing scan **self-heals**: re-narrate + stamp.

3. **Anchor stamping (Gap C) needs no new code.** `agent_plugin` has no `## File map`, so `file_map_todo_paths(page)` is always empty → the refill-gate is satisfied and the existing post-pass stamps any narrated `agent_plugin` (via `good_prose_uris` / `narrated_page_paths`). With D2.2 feeding commit-dirty plugins into the narrator, the anchor advances reliably. This is **locked by an integration test**, not changed in code.

### D3 — Ground the `agent_plugin` narrator in its component inventory (fixes Gap 1.6)

1. Extend `build_entity_narrative_prompt` (`scan.py:315`) with an optional `components_text: str = ""` parameter and an agent_plugin branch mirroring the package file-listing branch:
   ```python
   if kind == "agent_plugin" and components_text:
       lines.append("")
       lines.append("Component inventory (for reference; do NOT reproduce verbatim in your output):")
       lines.append(components_text[:2000])
   ```
2. In `generate_narrative` (`scan.py` Step 9b), build that text for an agent_plugin node by **reusing the page's own table renderer** — `_agent_plugin_table_variables(conn, node)` (imported from `wiki_io.entity_writer`, consistent with the other underscore helpers `scan.py` already imports) — joining the six tables under their headings; pass it as `components_text`. For non-agent_plugin kinds, `components_text` stays `""` and the prompt is **byte-unchanged**.

Reusing the page renderer keeps the narrator's view identical to what the page shows (DRY; no second inventory format to drift).

### D4 — Guard the suite-branch on `no_file_map` (fixes 1.7)

`scan.py:969`: change `if fm_targets:` → `if fm_targets and not no_file_map:` so the test-suite File-map branch honors `--no-file-map` like the package/app branch.

---

## 4. Scope

**In scope:** D1–D4 and their tests.

**Explicit non-goals:**
- **M2e drift *logic*** — owned by M2e (already on `main`, `DRIFT_TARGET_KINDS` already includes `agent_plugin`). This plan only makes `last_updated_commit` advance so M2e's gate fires for `agent_plugin`; it adds no drift code.
- **M2b LLM file-map analog** — N/A for `agent_plugin` (§1.5).
- **Frontmatter `STRUCTURAL_KEYS` changes** — the structural-key re-narration path is untouched; D2 *adds* the commit-gate alongside it.
- **A lint roll-up of stale tables** — not needed; tables can't go stale under D1.

---

## 5. Test cases

Unit (`packages/wiki-io/tests`):
1. **scanner-data regenerates, discards stale body** — merge a template with fresh `## Commands` (rows A,B) against an existing page whose `## Commands` has stale rows (X,Y); output contains A,B and not X,Y.
2. **human section still preserved** — same merge preserves a hand-edited `## Purpose`.
3. **user-added H2 still trails** — a user `## Notes` section survives and trails the template sections.
4. **idempotent / byte-stable** — `_merge_preserved_sections(t, t) == t` for an agent_plugin template carrying all six tables.
5. **scanner-data constant covers exactly the six table headings** (guard against a heading being added to the template without the merge knowing).

Unit (`packages/graph-io/tests/test_agent_plugins.py`):
6. **agent_plugin node carries its plugin dir** — after `emit`, the node's `path` column equals the plugin directory relative to repo root (extend `test_emit_creates_one_node_with_manifest_fields`).

Unit (`packages/graph-wiki-core/tests`):
7. **narrator prompt grounding** — `build_entity_narrative_prompt(kind="agent_plugin", components_text=…)` includes a known command/skill name; the `kind="package"` prompt is byte-unchanged when `components_text=""`.

Integration (`packages/graph-wiki-core/tests`, mocking the fan-out at `SubagentPool.run_all`):
8. **command added → table refresh + re-narrate + anchor advance** — scan 1 creates+narrates+anchors an agent_plugin at `head1`; a command is added in source and the plugin dir reports changed at `head2`; scan 2 shows the new command in `## Commands` (Gap A), re-narrated prose (Gap B), and `last_updated_commit == head2` (Gap C).
9. **no-op rescan stays `unchanged`** — with an unchanged graph, scan 2 produces a byte-identical page (tables deterministic) and does not re-narrate or re-stamp.
10. **`--no-narrate` regenerates tables but not narrative** — a `--no-narrate` scan after a source table change refreshes `## Commands` (free) and leaves `## Narrative` + `last_updated_commit` untouched.
11. **anchorless bootstrap** — an existing agent_plugin page with no `last_updated_commit` is treated commit-dirty on the next scan → re-narrated + stamped.
12. **suite-branch honors `--no-file-map`** — a `no_file_map=True` scan does not inject a test-suite File map (D4).

Cross-milestone (optional, with M2e present):
13. **drift activates for agent_plugin** — after a commit-dirty re-narrate advances `last_updated_commit`, `drift_checked_commit` lags it → the M2e `drift_judge` runs over the page's human sections.

---

## 6. Files touched

| File | Change |
|---|---|
| `packages/wiki-io/src/wiki_io/entity_writer.py` | `SCANNER_DATA_HEADINGS` constant; scanner-data branches in `_merge_preserved_sections` (D1) |
| `packages/wiki-io/tests/test_section_merge.py` | merge unit tests 1–5 |
| `packages/graph-io/src/graph_io/agent_plugins.py` | populate `node.path` with the plugin dir (D2.1); docstring update |
| `packages/graph-io/tests/test_agent_plugins.py` | path assertion (test 6) |
| `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py` | add `"agent_plugin"` to the commit-dirty tuple (D2.2); `components_text` param + agent_plugin grounding in `build_entity_narrative_prompt` / `generate_narrative` (D3); `no_file_map` guard on the suite branch (D4) |
| `packages/graph-wiki-core/tests/…` | narrator-prompt unit (test 7); scan integration tests 8–12 (+ optional 13) |
| `.claude/rules/backward-compatibility.md` | note the agent_plugin data tables are scanner-owned (D1 wording refinement) |

---

## 7. Sequencing & preconditions

- M2a–M2e are **already on `main`** (M2e merged: commit `4f2c689e` plus the `_drift_candidates`/`_drift_flag_pass`/`DRIFT_TARGET_KINDS` wiring). This plan targets current `main` directly. *(If a worktree holds M2e work beyond what's committed to `main`, rebase this plan onto it first.)*
- **Full graph rebuild required** after D2.1 to backfill `agent_plugin` node paths.
- This plan **activates** M2e drift for `agent_plugin` (turns the already-wired but inert gate live). Sequencing: agent-plugin parity → M3.

---

## 8. Open questions

None blocking. One deferred enhancement intentionally left out: feeding a **diff of the component inventory** (added/removed commands since last anchor) into the narrator or a future drift signal — premature until D1–D3 land and we see whether the verbatim inventory grounding (D3) is sufficient.
