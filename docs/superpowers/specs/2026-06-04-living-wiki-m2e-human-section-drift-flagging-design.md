# Living Wiki M2e — Intra-Page Human-Section Drift Flagging

**Date:** 2026-06-04
**Status:** Design — ready for `writing-plans`.
**Author:** Pat (with code-verified findings)
**Milestone:** Living Wiki M2e (final slice of M2 — "Commit-gated incremental updates").
**Builds on:** M2a (narrative persistence + commit-gate), M2b (commit-gated file-map row re-description), M2c (commit-gate consolidation), and **M2d (preserve-then-overwrite merge)**. M2a/M2b/M2c landed on `main` (M2c merge `d2f19481`); **M2d is executing now** (spec `docs/superpowers/specs/2026-06-04-living-wiki-m2d-preserve-then-overwrite-design.md`; plan `docs/superpowers/plans/2026-06-04-living-wiki-m2d-preserve-then-overwrite.md`) and is the immediate precondition (see §7).
**Roadmap:** `docs/superpowers/specs/2026-06-03-living-wiki-roadmap.md` (§4 "M2": *"detect when human/LLM sections may have drifted … and flag for review … flag-don't-auto-edit"*; §6 Q6).

---

## 0. One-paragraph thesis

M2a–M2d made the **scanner-owned** parts of an entity page incremental: when an entity's code changes, its `## Narrative` and `## File map` refresh, gated on the commit diff since the page's `last_updated_commit` anchor. But the page's **human-owned** sections (`## Purpose`, `## Public API`, and the agent-plugin sections `## Commands` / `## Agents` / `## How it fits together`, etc.) are *preserved verbatim* across every scan (M1 ownership model; M2d PTO). Preservation is correct — we must never auto-edit curated prose — but it means a human section can silently **drift**: the code it describes moved out from under it while the prose stayed frozen. M2e closes that gap **without** breaking the preserve-only contract: when an entity's narrative regenerates (the signal that its code changed materially), a cheap-tier `drift_judge` subagent compares each human section against the freshly-regenerated narrative and, on a stale verdict, writes a **flag into the page's frontmatter** (`drift_review`) — never touching the prose. This is the deliberately small, in-page **pilot for M4's cross-page drift propagation**: same machinery (a drift-judging subagent on a cheap tier, propose-only), far fewer targets (one page's own sections vs. every backlinking concept/ADR), and ground truth already in hand (the narrative this scan regenerated — no extra code-reading fan-out). It adds one role, two frontmatter keys, one scan post-pass, and one CLI subcommand; it is purely additive and changes none of the M2a–M2d gate logic.

---

## 1. Where we are (code-verified)

Line numbers are `main` post-M2c (`d2f19481`); M2d deltas noted where relevant. Files: `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py`, `packages/wiki-io/src/wiki_io/entity_writer.py`.

### 1.1 Human sections are preserved but never checked

The section-ownership model (roadmap §2.1, `.claude/rules/backward-compatibility.md`) partitions an entity page into **scanner-owned** sections (`## Narrative`, `## File map`, `## Referenced in wiki` — regenerated each scan) and **human-owned** sections (everything else — preserved). M1's heading-aware merge and M2d's preserve-then-overwrite (PTO) guarantee human sections survive re-scan byte-for-byte. **Nothing ever asks whether a preserved human section still matches the code.** A `## Purpose` written when a package did X synchronously stays on the page unchanged after the package is rewritten to do X via async fan-out. That is the drift M2e detects.

### 1.2 The commit signal that says "the code under this page changed"

M2a established the per-entity anchor: `last_updated_commit` (preserved frontmatter key, **not** in `SCANNER_OWNED_KEYS`; scanner-stamped to HEAD when `## Narrative` is regenerated — see `.claude/rules/backward-compatibility.md`). `_commit_dirty_changes` (`scan.py:521-542`) maps URIs whose files changed since their anchor (via `wiki_io.git_state.changed_files_since`, `git_state.py:59`) to the changed-file list; its keys feed `needs_narrative` (`scan.py:773`), so a commit-dirty entity re-narrates this scan. **Narrative regeneration is therefore a precise, already-computed signal that an entity's code changed materially** — exactly the trigger M2e's structural pre-filter keys off. M2e reuses this signal; it does not add a diffing engine.

### 1.3 Targeted frontmatter writes already exist

`set_frontmatter_value(page_path, key, value)` (`entity_writer.py:686`) performs a surgical frontmatter update without re-rendering the page body — the mechanism M2a/M2c use for anchor stamping after the inject steps. M2e writes its flag keys the same way, so it never disturbs PTO'd bodies. (It currently writes scalar string values; M2e's `drift_review` is a structured list — see §6.)

### 1.4 `agent_plugin` was missed by the M2 commit-gate (separate parity plan)

`agent_plugin` is an admitted entity kind (`entity_writer.py:66`) whose template (`assets/page-templates/entity-agent-plugin.md`) is narrative-bearing and **human-section-rich** (`## Purpose`, `## Commands`, `## Agents`, `## Skills`, `## Scripts`, `## Hooks`, `## MCP servers`, `## How it fits together`) and has **no `## File map`**. But `_commit_dirty_changes` (`scan.py:542`) loops only `("package", "app", "test_suite")` — `agent_plugin` appears **nowhere in `scan.py`**. So agent-plugin pages get **no commit-gated narrative refresh** today; they were missed across M2a–M2c. M2e *includes* `agent_plugin` in its target scope (it's exactly the kind of prose-heavy page drift matters for), but agent-plugin's commit-gated coverage only **fully lights up** once a separate **agent-plugin parity plan** (§7) wires `agent_plugin` into `_commit_dirty_changes`. Until then, M2e still covers agent-plugin pages whose narrative regenerates on a *structural* change (new/changed section structure → `needs_narrative`); it just won't fire on a pure code-change-since-anchor. Including `agent_plugin` in M2e scope now means **zero further M2e changes** when parity lands.

---

## 2. Architecture decisions

### D1 — Hybrid detection: free structural pre-filter → cheap-tier LLM judge

A human section is checked for drift **only** when the page's `drift_checked_commit` lags its `last_updated_commit` (Stage 1, free). Because `last_updated_commit` advances *only* when `## Narrative` regenerates (M2a), this lag is true exactly when the narrative is newer than the last drift check — whether it regenerated this scan or an earlier one whose drift pass was skipped/crashed (the comparison is self-recovering, vs. an "in `needs_narrative` this scan" check which would miss that case). Pages whose narrative did not advance since the last check spend **zero tokens**. For each candidate section, a `drift_judge` subagent (Stage 2) judges staleness. Pure-structural detection (flag any human section on any code change, no LLM) was rejected: it flags on every change regardless of whether the change touched what the prose describes (low precision) and is not a genuine pilot for M4's LLM-heavy machinery. Stateless re-judge-every-scan was rejected on cost (§D3).

### D2 — Judge ground truth is the regenerated narrative, not re-read code

The `drift_judge` compares the human section's body against the **`## Narrative` the scanner already regenerated this scan** (plus the `## File map` where the kind has one). It does **not** spawn a code-reader to re-read the changed source. Rationale: the narrative *is* the scanner's current, code-derived understanding of the entity; if a human section contradicts it, that is precisely the drift signal — and reusing it costs no extra fan-out. Code-diff-grounded judging is more accurate but more expensive; it is deliberately deferred to **M4** (cross-page propagation), keeping M2e the cheap in-page pilot. Judge contract: input = `{heading, body, narrative, file_map?}`; output = `{stale: bool, reason: <one short line>}`.

### D3 — Two preserved frontmatter keys; judge runs once per drift event

M2e adds two scanner-managed-but-**preserved** frontmatter keys, following the exact precedent of `last_updated_commit` (scanner-stamped, preserved across re-scan, **not** in `SCANNER_OWNED_KEYS` so the merge never wipes them):

```yaml
drift_checked_commit: a1b2c3d        # commit at which drift_judge last ran for this page
drift_review:                         # omitted entirely when there are no open flags
  - section: Purpose
    detected_commit: a1b2c3d
    hash: 9f2c…                       # sha256 of the section body at flag time
    reason: "Narrative now describes async fan-out; Purpose claims synchronous processing."
```

The judge fires for a page **only when `drift_checked_commit < last_updated_commit`** (the narrative is newer than the last drift check). After it runs, `drift_checked_commit` is set to `last_updated_commit`. So the LLM cost for any (page, narrative-change) pair is incurred **once**; a flagged page sitting unaddressed across many later scans costs **zero** additional tokens.

### D4 — Auto-clear on edit (free, every scan) + explicit ack escape-hatch

Flag resolution needs no LLM and no human bookkeeping for the common case:

- **Clear pass (free, every scan).** For each `drift_review` entry, recompute the section's current body-hash; if it differs from the stored `hash`, or the section no longer exists, **drop the entry**. When `drift_review` empties, remove the key. A human who edits the flagged prose auto-resolves the flag on the next scan.
- **Ack escape-hatch.** `gw wiki ack-drift <entity>` clears all `drift_review` entries for a page without an edit — the "I reviewed it, the prose is still correct, no change needed" case. Because `drift_checked_commit` already equals `last_updated_commit` after the judge ran, the section is not re-judged until the narrative changes again. (Optionally also bumps the human `last_reviewed` date.)

No third `human_reviewed_commit` key is needed: the hash-clear handles the edit case, the ack handles the no-edit case, and `drift_checked_commit` already prevents re-judging.

### D5 — Flag-only, intra-page only; purely additive

M2e **never auto-edits** human prose (roadmap propose-don't-overwrite stance) and is **intra-page only** — it judges a page's own sections against that page's own narrative. Cross-page drift (concept/ADR pages backlinking a changed entity) is **M4**. M2e changes none of the M2a–M2d gate logic, the PTO merge, `needs_narrative`, or anchor stamping; it adds one role, two keys, one post-pass, one CLI subcommand.

---

## 3. The changes

### 3.1 Drift post-pass in `scan.py`

A new post-pass runs **after** the entity pages are written/merged (M2d PTO), narratives injected, file maps injected, and `last_updated_commit` anchors stamped — it needs the final `## Narrative` and the settled human sections on disk. Mirrors the existing anchor-stamping placement (after Step 10c). For each target-kind page (§3.4):

1. **Pre-filter (free):** skip unless `last_updated_commit` is present and `drift_checked_commit < last_updated_commit` (a missing `drift_checked_commit` counts as lagging, so a never-checked page with a narrative qualifies). This is the single authoritative gate — typically the entity was just re-narrated this scan, but it also self-recovers a page whose drift pass was skipped in a prior scan (D1).
2. **Judge pass (LLM, gated):** read the page; for each human-owned H2 section, fan out a `drift_judge` call (`SubagentPool`) with `{heading, body, narrative, file_map?}`. Collect `{stale, reason}` verdicts.
3. **Write flags:** build `drift_review` from stale verdicts (each with `section`, `detected_commit = last_updated_commit`, `hash = sha256(body)`, `reason`); set `drift_checked_commit = last_updated_commit`. Write via the frontmatter-targeted setter (§6).

### 3.2 Clear pass in `scan.py` (free, every scan)

Independent of the pre-filter, for every page that has a `drift_review` key: recompute each flagged section's body-hash from the live page; drop entries whose hash changed or whose section is gone; remove the key when empty. Runs even for pages the judge skipped this scan, so a human edit clears flags promptly.

### 3.3 `drift_judge` role

Add `drift_judge` to `models.toml` (packaged fallback) on a cheap tier, overridable via `<workspace>/.graph-wiki.yaml` `roles[]` (consumed by `make_llm` automatically) — a §5 cost-offload candidate, later validated by the `deepeval` harness. Built through `model_adapter.make_llm("drift_judge")` and run via `SubagentPool` exactly like the narrator/code_reader roles.

### 3.4 Target-kind scope

Kinds with **both** a regenerated `## Narrative` and human-owned sections: **`package`, `app`, `test_suite`, `agent_plugin`**. (`repository` / `domain` / `dependency` pages have no curated human prose to drift and are excluded.) `agent_plugin` is included now for forward-compatibility (§1.4); its commit-gated coverage completes with the agent-plugin parity plan (§7). The judge uses the narrative as ground truth for every kind; the `## File map` is passed additionally only for kinds that have one (not `agent_plugin`).

### 3.5 `gw wiki ack-drift <entity>` subcommand

A small `wiki_cli` subcommand (`packages/graph-wiki-cli/src/graph_wiki_cli/wiki_cli/main.py`) that resolves the entity URI/slug to its page, clears `drift_review`, and (optionally) bumps `last_reviewed`. No LLM.

---

## 4. Scope

**In scope**
- Drift post-pass: structural pre-filter → cheap-tier `drift_judge` fan-out (§3.1, D1/D2).
- `drift_checked_commit` / `drift_review` preserved frontmatter keys + the judge-once-per-drift-event gate (§3.1, D3).
- Free clear pass: auto-clear on section edit (§3.2, D4).
- `drift_judge` role in `models.toml` (§3.3).
- Target kinds `package` / `app` / `test_suite` / `agent_plugin` (§3.4).
- `gw wiki ack-drift` subcommand (§3.5, D4).
- The structured-frontmatter setter extension (§6).

**Out of scope (explicit boundaries)**
- **Auto-editing** human prose — never; flag-only (D5).
- **Cross-page drift** (concept/ADR/architecture pages backlinking a changed entity) — **M4**.
- **Code-diff-grounded judging** (re-reading changed source as ground truth) — M4; M2e compares against the regenerated narrative only (D2).
- **agent-plugin commit-gate parity** (wiring `agent_plugin` into `_commit_dirty_changes` and any file-map-equivalent refresh) — **separate parity plan, after M2e, before M3** (§7). M2e ships `agent_plugin` in scope but dormant for pure code-change drift until then.
- **Lint aggregation / `work/` drift-queue page** — the frontmatter key is the canonical surface; a lint roll-up is a possible later convenience, not M2e.
- No changes to the commit-gate, `needs_narrative`, M2d PTO merge, or anchor-stamping logic.

---

## 5. Tests (success criteria)

LLM fan-out mocked at the `SubagentPool.run_all` boundary (project fixture pattern; mirror `test_commit_gated_narrative.py` / `test_updated_churn.py`).

**Detection / pre-filter**
1. **Re-narrated entity + human section → judge runs, stale → flagged.** An entity commit-dirty this scan with a `## Purpose` whose mocked verdict is `stale` gets a `drift_review` entry carrying `section`/`detected_commit`/`hash`/`reason`; `drift_checked_commit` advances to `last_updated_commit`.
2. **Already-checked entity → judge skipped.** An entity whose narrative did not regenerate this scan and is already drift-checked at its current anchor (`drift_checked_commit == last_updated_commit`) produces no `drift_judge` call and no frontmatter change (pre-filter free path).
3. **Fresh verdict → no flag, but checked-commit advances.** A re-narrated entity whose section verdict is `not stale` gets no `drift_review` entry and `drift_checked_commit == last_updated_commit` (proves it won't re-judge next scan).

**Judge-once / cost gate**
4. **No re-judge when narrative unchanged.** A page with an open flag, re-scanned with no repo change (narrative not regenerated, `drift_checked_commit == last_updated_commit`) → `drift_judge` is **not called**; the flag persists byte-stable.

**Clearing**
5. **Auto-clear on edit.** A flagged section whose body is hand-edited (hash changes) → next scan drops the entry with **no `drift_judge` call**; an emptied `drift_review` key is removed.
6. **Ack clears without edit.** `gw wiki ack-drift <entity>` removes all `drift_review` entries for the page; a subsequent no-change scan does not re-flag (checked-commit already current).

**Preservation / ownership**
7. **Keys survive re-scan.** `drift_checked_commit` and `drift_review` are preserved across re-scan (not wiped by the `SCANNER_OWNED_KEYS` merge / M2d PTO) — guards the ownership classification.

**Scope**
8. **No human section / no narrative → never flagged.** A `dependency` page (no human prose) and a page with no `## Narrative` produce no judge calls and no keys.
9. **agent_plugin in scope, narrative-grounded.** An `agent_plugin` page whose narrative regenerated (structural change) has its human sections judged against its `## Narrative` (no `## File map` passed); a stale verdict flags. (Confirms forward-compatibility ahead of the parity plan.)

---

## 6. Key code touchpoints

- `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py`
  - New drift post-pass (§3.1) + free clear pass (§3.2), placed after anchor stamping; reuse `needs_narrative` / the re-narrated set for the pre-filter and `_commit_dirty_changes` outputs already in scope.
- `packages/wiki-io/src/wiki_io/entity_writer.py`
  - `set_frontmatter_value` (`:686`) — **extend** (or add a sibling `set_frontmatter_structured`) to write a structured (list-of-dict) value for `drift_review`; current impl writes scalar strings only.
  - Reuse `_split_h2_sections` + `_is_scanner_owned_heading` (the same machinery `_merge_preserved_sections` uses) to enumerate human-owned sections — a section is human-owned iff `not _is_scanner_owned_heading(heading)` — and hash their bodies.
  - `SCANNER_OWNED_KEYS` — confirm `drift_checked_commit` / `drift_review` are **not** added to it (preserved, like `last_updated_commit`).
- `packages/model-adapter` / `models.toml` — add the `drift_judge` role (cheap tier).
- `packages/graph-wiki-cli/src/graph_wiki_cli/wiki_cli/main.py` — `ack-drift` subcommand (§3.5).
- Tests: new `test_human_section_drift.py` (graph-wiki-core) for §5; `drift_judge` mocked at `SubagentPool.run_all`.

---

## 7. Sequencing & dependencies

**Precondition:** **M2d (PTO)** merges to `main` — M2d is *executing now* (plan `docs/superpowers/plans/2026-06-04-living-wiki-m2d-preserve-then-overwrite.md`), not yet merged. M2e reads the stable merged narrative + preserved human sections and adds frontmatter via the targeted setter; rebase onto M2d's merge before implementing. M2a/M2b/M2c are already landed. (M2e's commit-comparison gate reads `last_updated_commit` off the page after anchor stamping — M2d leaves M2c's anchor-stamping pass untouched and deletes the `entities_narrated` restore-loop consumer, neither of which M2e depends on.)

**After M2e:** a **separate agent-plugin parity plan** brings `agent_plugin` to M2a–M2d commit-gate parity (add it to `_commit_dirty_changes`'s kind loop; decide the file-map-equivalent story given agent-plugin has no `## File map` — its structural sections are `## Commands`/`## Agents`/etc., so this plan has its own small design surface). Sequenced **after M2e, before M3**. M2e's `agent_plugin` drift coverage lights up fully once this lands; no M2e changes are required when it does.

**Then:** M2 is complete. **M3** (ingest hardening + code-as-arbiter) is next and parallel-eligible (depends only on M1). Full order: M2c ✓ → M2d → **M2e** → agent-plugin parity → M3 → M4 → M5.

M2e is the **cheap pilot for M4**: the `drift_judge` role, the propose-only flag, and the "judge against regenerated ground truth" pattern all carry forward to M4's cross-page propagation, which swaps the in-page narrative target for the set of backlinking concept/ADR pages and adds batching/opt-in.

---

## 8. Open questions

None blocking.
- Whether the eventual M4 work promotes M2e's narrative-grounded judge to a code-diff-grounded one, or runs both (narrative-cheap pass + code-expensive pass) — deferred to M4 design (§D2).
- Whether to add an optional `graph-wiki:lint` roll-up that counts open `drift_review` flags across the vault — a convenience, evaluated after M2e ships (out of scope, §4).
