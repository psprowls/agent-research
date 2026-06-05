# M4 — Drift Propagation to Backlinks (design)

**Date:** 2026-06-05
**Status:** Design — ready for `writing-plans`.
**Author:** Pat (brainstormed + code-verified against `main`)
**Milestone:** Living Wiki **M4** — the scan-time **drift producer** that writes into the shared proposal ledger. The second producer on top of the ledger foundation (M3's ingest producer is the first).
**Depends on:** the **curated-page proposal ledger foundation** (`docs/superpowers/specs/2026-06-05-curated-page-proposal-ledger-design.md`, executing in a parallel session) — specifically `wiki_io.proposals.upsert_proposal` and the per-note lifecycle. M4 calls that API and adds **zero foundation changes**.
**Roadmap:** `docs/superpowers/specs/2026-06-03-living-wiki-roadmap.md` §M4, open-question #6.

> **Goal:** on re-scan, for every entity whose code changed, find the **curated** pages (`concepts/`, `adrs/`, `architecture/`) that backlink it and **propose** updates where their claims may have gone stale — recording each as a `source: drift` note in the shared ledger. Propose only; never auto-edit a curated page. M4 is a **thin producer**: it reuses the existing changed-entity signal, the existing backlink map, the existing fan-out pattern, and the ledger's `upsert_proposal` — adding one new orchestration command, one new model role, and one extracted helper.

---

## 0. One-paragraph thesis

The roadmap calls M4 the "most expensive, LLM-heaviest, highest-false-positive" step. The design therefore spends its effort on **not doing work** — every lever is about narrowing what gets judged and grounding the judge in a clean signal. The gating mirrors M2e's proven within-page drift pattern: a **per-entity anchor** (`drift_propagated_commit`, the M4 analog of M2e's `drift_checked_commit`) makes the trigger "narrative refreshed since we last propagated" — computed identically off disk by both execution surfaces, and idempotent on repeat runs. The backlink lookup is the inverse map the backlink indexer **already builds**; the fan-out is the `SubagentPool` pattern the M2e drift pass **already uses**; the output is the ledger note the foundation **already defines**. M4 adds exactly three new things: a `propagate_drift` orchestration command (callable from both a standalone CLI surface and an opt-in scan flag), a cheap-tier `drift_propagator` model role, and a pure `build_entity_backlink_map` helper extracted from the backlink indexer. Everything else is composition. The false-positive risk is managed by feeding the judge a **noise-free** change signal (git-derived changed files + the current narrative — deliberately **not** a narrative-text diff, which is polluted by narrator rephrasing), a **ledger pre-filter** that skips human-settled pages, and **dry-run / scoped / always-reported** guardrails.

---

## 1. Where we are (code-verified, `main`)

- **Changed-files git helper already exists.** `_commit_dirty_changes()` (`commands/scan.py:554-600`) maps each `package`/`app`/`test_suite`/`agent_plugin` URI whose files changed since the commit on its page to its changed-file list, via the underlying `changed_files_since(repo, anchor, node_path)`. That git helper is M4's change signal — but keyed off **M4's own anchor**, not `last_updated_commit` (see §3.1: the narration anchor advances during scan, so reusing it would make a standalone post-scan run see nothing).
- **The per-entity drift anchor pattern is the model.** M2e stores `drift_checked_commit` per entity page and gates re-judging on `drift_checked_commit != last_updated_commit` (string inequality; `_drift_candidates`, `scan.py:613-645`), advancing it on every candidate so clean entities aren't re-judged. M4 mirrors this with a parallel anchor `drift_propagated_commit` (see §3.1).
- **Backlink inverse map already exists, internally.** `regenerate_referenced_in_wiki()` (`wiki_io/backlink_index.py:100-142`) builds `refs: dict[stem -> list[(category, slug, post)]]` (`:114`) by walking `_PRESERVED_WIKI_DIRS = ("sources","concepts","adrs","architecture")` (`:68-84`) for `[[entities/<stem>]]` wikilinks (`_ENTITY_LINK_RE`). It only renders the per-entity `## Referenced in wiki` section and discards the map. M4 needs that map as a reusable value.
- **The within-page drift pass is the template.** M2e's `_drift_flag_pass()` (`commands/scan.py:648-725`) gates candidates via `_drift_candidates()` (`:613-645`), iterates human sections (`wiki_io.drift.iter_human_sections`), fans out one judgement per `(section, narrative)` over a `SubagentPool`, and writes `drift_review` / `drift_checked_commit` frontmatter. It uses `build_drift_judge_prompt` / `parse_drift_verdict` (`prompts/drift_judge.py`) and **fails safe to not-stale** on unparseable replies. M4 is the **cross-page** analog (a curated page's claims vs. a *changed entity's* new state) rather than the within-page analog (a human section vs. *its own* entity's narrative).
- **Fan-out pattern.** `SubagentPool.run_all(items, task, role, model_id, max_concurrency)` returning `.successes`/`.errors`, with `TaskResult(value, response)` for token accounting (`subagent_runtime/pool.py`). Concrete precedent: the narrator fan-out at `scan.py:972-1030` (`load_role_config(role)` → `make_llm(role, model_override)` → build items → `run_all`).
- **Model roles.** Per-role tiers + `sweep_candidates` live in `model_adapter/models.toml`; `make_llm(role)` returns the guarded Bedrock client.
- **The ledger (foundation, in flight).** `wiki_io.proposals`: `upsert_proposal(wiki, proposal) -> dict`, `list_proposals(wiki, status=, kind=) -> list[dict]`, `proposal_path`, `set_proposal_status`. Identity = `proposals/<kind>-<target_slug>.md`; `status ∈ {proposed, approved, rejected, created}` with `HUMAN_DECIDED = {approved, rejected, created}` left untouched by upsert; `origins[]` keyed by `ref`, with the **M4-reserved** `detected_commit` / `hash` keys already accommodated in the schema.
- **Provenance helpers.** `wiki_io.drift.section_hash` (sha256 of a chunk); `LAST_UPDATED_COMMIT_KEY = "last_updated_commit"` (`entity_writer.py:505`).
- **Ack precedent.** `commands/ack_drift.py` / `gw wiki ack-drift` clears `drift_review` via `update_frontmatter(delete=[...])` — the convenience-write precedent the ledger's `proposal approve|reject` already follows.

---

## 2. The model — one producer, the shared ledger, a deferred consumer

M4 is the **drift producer** in the ledger's three-role flow (produce → dispose → create). It runs at scan time, proposes `update_existing` changes to curated pages backlinking changed entities, and calls `upsert_proposal` with `source: drift` origins. The **human disposes** (`gw wiki proposal approve|reject`, foundation), and a **deferred creation consumer** (a later spec) acts on `approved` notes. M4 writes **nothing** under `concepts/`/`adrs/`/`architecture/`.

Two facts shape every decision below:

1. **The page exists by definition.** A curated page only enters M4's scope because it *backlinks* a changed entity — so the target always exists. M4 therefore **only ever produces `mode: update_existing`**; `create_new` stays M3-ingest territory.
2. **The signal is git, not prose.** The change driver is the git-derived changed-file list (the files changed between the entity's `drift_propagated_commit` and its current `last_updated_commit`) plus the entity's current narrative — **not** an old→new narrative diff. Narratives are LLM-generated; a text diff is polluted by rephrasing churn that isn't real change. The changed-file list is a precise, noise-free signal at zero extra cost (no snapshot, no wiki-git recovery, identical across both execution surfaces).

---

## 3. Design

### 3.1 Trigger set — M4's own anchor (D1)

M4 owns a per-entity frontmatter anchor **`drift_propagated_commit`**, the analog of M2e's `drift_checked_commit`. An entity is a **propagation candidate** when its narrative has been refreshed since M4 last propagated it:

```
drift_propagated_commit != last_updated_commit   # string inequality, M2e-style
```

(absent `drift_propagated_commit` ⇒ candidate). This is the load-bearing fix for the **standalone surface**: the narration anchor `last_updated_commit` advances to HEAD when the scan refreshes a narrative, so a standalone `propagate-drift` run *after* a scan must **not** key off it (it would see nothing). M4's own anchor instead records "the narrative state we last propagated," and **both surfaces compute the candidate set identically off the just-written entity pages on disk** — no in-memory thread-through, no dependence on when the scan ran.

A single pure helper drives it:

```python
def propagation_candidates(wiki, repo, conn) -> list[PropagationCandidate]:
    """Entity pages where drift_propagated_commit != last_updated_commit.
    Each candidate carries: uri, page_path, stem, narrative, last_updated_commit,
    drift_propagated_commit, changed_files (= changed_files_since(repo,
    drift_propagated_commit, node_path))."""
```

The change signal per candidate = `changed_files_since(repo, drift_propagated_commit, node_path)` — the git-derived files that moved since the last propagation. After M4 processes a candidate (stale or not), it **stamps `drift_propagated_commit = last_updated_commit`** on that entity page (§3.5), so the entity is not reconsidered until its narrative changes again — the negative cache that makes repeat runs idempotent on both surfaces.

### 3.2 Backlink lookup — extract a reusable helper (D2)

Extract a pure helper from `regenerate_referenced_in_wiki`:

```python
# wiki_io/backlink_index.py
def build_entity_backlink_map(wiki: Path) -> dict[str, list[tuple[str, str, Path]]]:
    """entity_stem -> [(category, slug, page_path)] for every [[entities/<stem>]]
    wikilink across the preserved wiki dirs. The inverse map regenerate_referenced
    _in_wiki builds internally, exposed as a value."""
```

`regenerate_referenced_in_wiki` is refactored to call this helper (no behavior change; its existing tests guard that). M4 **filters the map to curated kinds only** — `category ∈ {concepts, adrs, architecture}`. `sources/` is excluded (Source pages are refreshed by M3 re-ingestion, not drift-flagged); `work/` is excluded (transient).

### 3.3 Pre-filter against the ledger (D3)

Before judging, drop any target curated page that already has a ledger note at a **human-decided** status:

```python
settled = {  # (kind, target_slug) the human already disposed of
    (rec["kind"], rec["target_slug"])
    for rec in list_proposals(wiki)
    if rec["status"] in HUMAN_DECIDED
}
```

A page maps to `(kind, target_slug)` from its category + slug. Pages with no note, or a still-`proposed` note, **are** judged (a re-judge refreshes the open proposal in place via the ledger's per-`ref` origin merge). This is the cost gate on top of the commit-gate: only changed entities trigger judging, and only un-settled pages are judged.

### 3.4 The judge — per-page batch, kind-aware (D4)

**Unit of judgment = one curated page** (entities batched). For each affected curated page, a single `drift_propagator` call sees:

- the **full page body**, and
- for each changed entity that backlinks it: the entity's **current `## Narrative`** + its **changed-file list** (the candidate's `changed_files`, §3.1).

The prompt is **kind-aware**:

- `concept` / `architecture` — stale when the page's described behavior no longer matches the entity's current state.
- `adr` — **annotate-only**: stale when the decision's `Status` / `Consequences` / `Supersedes` have been overtaken by code reality — *not* when prose describing the original decision changed. The judge frames an ADR finding as a supersede/annotate candidate, never a rewrite of decision history.

**Structured output** (mirroring `parse_drift_verdict`, fail-safe to not-stale on parse miss):

```json
{ "stale": true,
  "findings": [
    { "entity_stem": "pkg_wiki_io",
      "stale_claim": "ADR assumes synchronous narration",
      "rationale": "Narrative now describes async fan-out; the Consequences section is overtaken." }
  ] }
```

One `findings[]` entry per triggering entity gives precise origin attribution. The fan-out mirrors `_drift_flag_pass`: build `items` of `(page_path, kind, target_slug, [(entity_stem, narrative, changed_files), ...])`, `SubagentPool.run_all(role="drift_propagator", ...)`, collect `successes`.

### 3.5 Produce + stamp the anchor (D5)

For each page judged `stale`, call `upsert_proposal` **once per finding** (each call merges one origin); the ledger's identity collapse means the per-finding calls accrue into **one note per target**, with one drift origin per triggering entity:

```python
for finding in verdict["findings"]:
    upsert_proposal(wiki, {
        "kind": kind,                      # concept | adr | architecture
        "mode": "update_existing",         # M4 is always update_existing (§2)
        "target_slug": target_slug,        # the existing curated page's slug
        "title": page_title,
        "origin": {
            "ref": f"entities/{finding['entity_stem']}",
            "source": "drift",
            "detected_commit": last_updated_commit[stem],  # narrative state propagated
            "hash": narrative_hash[stem],   # sha256 of the entity's current narrative
            "rationale": finding["rationale"],
        },
    })
```

The reserved keys carry meaning under M4:

- **`detected_commit`** = the candidate's `last_updated_commit` (the code-repo commit the propagated narrative was regenerated at; updates in place when the same entity re-fires the same target).
- **`hash`** = `section_hash` of the entity's current `## Narrative` (records the narrative state the drift was judged against; lets future tooling tell whether the proposal's basis has since moved).

The ingest producer never sets these (foundation §3.1); M4 always does.

**Anchor stamping.** After processing each candidate entity — **stale or not, and even if all its backlinkers were pre-filtered out** — stamp `drift_propagated_commit = last_updated_commit` on that entity page (`update_frontmatter`, the M2e `drift_checked_commit` precedent). This is what closes the loop: the entity is not reconsidered until its narrative changes again. **`--dry-run` skips both the upserts and the stamping** (zero side effects).

### 3.6 The orchestration command (D6)

New `packages/graph-wiki-core/src/graph_wiki_core/commands/propagate_drift.py`:

```python
@dataclass
class PropagateDriftResult:
    pages_judged: int
    entities_considered: int
    notes_written: int          # created or refreshed this run
    pages_stale: int
    pages_skipped_settled: int  # dropped by the ledger pre-filter
    dry_run: bool
    proposals: list[dict]       # report rows (kind/target_slug/origins) for --json

async def run_propagate_drift(
    *, wiki: Path, repo: Path, conn: Any,
    dry_run: bool = False, only: str | None = None,
    model_override: str | None = None,
) -> PropagateDriftResult: ...
```

Pure orchestration over §3.1–§3.5: compute `propagation_candidates` off disk (the anchor delta), build the backlink map and filter to curated kinds, apply `--only`, pre-filter against the ledger, fan out the judge, and (unless `dry_run`) `upsert_proposal` per finding **and** stamp `drift_propagated_commit` per candidate. Always returns the summary fields. Both surfaces call this one function — the scan flag at the end of scan (pages already written), the standalone command anytime.

### 3.7 Surfaces — shared core, two entry points (D7)

- **`gw wiki propagate-drift`** (+ MCP twin) — standalone, always explicit. Flags: `--dry-run`, `--only <entity-or-page>`, `--workspace`, `--json`. Resolves wiki/repo, opens the graph, calls `run_propagate_drift` (which computes its own candidates off the on-disk anchors).
- **`gw scan --propagate-drift`** — **off by default**. After the narrator refresh (narratives fresh, pages written and `last_updated_commit` advanced), calls the same `run_propagate_drift`. Because the pass reads anchors off disk, no in-memory state is threaded in. Gated alongside `narrate=True` (it needs the Bedrock stack).
- **Always-on summary report** (both surfaces): pages judged, entities considered, notes written/refreshed, stale-rate, skipped-settled count, and SubagentPool trace count. `--json` serializes `PropagateDriftResult`.

### 3.8 Guardrails (D8)

- **Propose-only** — never writes curated dirs. (Locked.)
- **Opt-in** — scan flag off by default; standalone always explicit. (Locked.)
- **`--dry-run`** — judges and reports exactly what *would* be proposed (target page, triggering entities, rationale); writes zero notes.
- **`--only <entity-or-page>`** — restrict the pass to a specific entity URI/stem or curated page, for targeted re-checks.
- **Summary cost report** — always on (§3.7), so cost is visible regardless of the other rails.
- **No hard per-run cap** — deliberately omitted; visibility (report) + targeting (`--only`) preferred over silent throttling.

### 3.9 Deliberate non-changes (D9)

- **No ledger-schema change.** M4 only *calls* `upsert_proposal`; the `source: drift` shape and `detected_commit`/`hash` keys are already accommodated by the foundation.
- **ADR annotate-only needs no new field.** The note's `kind: adr` is the signal; the future creation-consumer applies supersede/annotate handling on `kind`, and the judge's rationale frames it. No new `mode`/flag.
- **`proposals/` is still not a backlink source.** M4's `origins[]` carry `entities/<stem>` refs, but `proposals/` stays out of `_PRESERVED_WIKI_DIRS`, so drift notes never generate `## Referenced in wiki` backlinks (foundation §3.8 guard holds).
- **M2e within-page drift is untouched.** `_drift_flag_pass` / `drift_review` / `ack-drift` keep their job (a human section vs. its own entity). M4 is additive and orthogonal — and its anchor `drift_propagated_commit` is a new provenance key alongside `drift_checked_commit`: scanner-stamped, preserved across re-scan, and (like `last_updated_commit` / `drift_checked_commit`) **not** in `SCANNER_OWNED_KEYS`. No backward-compat rule change beyond noting the new key.

---

## 4. Components & boundaries

| Unit | Responsibility | Depends on |
|---|---|---|
| `wiki_io.backlink_index.build_entity_backlink_map` (extracted) | pure inverse backlink map | `wiki_io` frontmatter helpers |
| `propagate_drift.propagation_candidates` | anchor-delta candidate set (`drift_propagated_commit != last_updated_commit`) + changed files | `wiki_io` frontmatter, `changed_files_since` |
| `propagate_drift.run_propagate_drift` | orchestrate candidates → backlink → pre-filter → judge → upsert → stamp anchor | candidate helper, backlink helper, `wiki_io.proposals`, `SubagentPool`, `drift_propagator` role |
| `prompts/drift_propagator` (new) | kind-aware cross-page judge prompt + verdict parse | — |
| `drift_propagator` role (models.toml) | cheap-tier model + sweep candidates | `model_adapter` |
| `gw wiki propagate-drift` + MCP twin | standalone surface over the core fn | `propagate_drift` |
| `gw scan --propagate-drift` | opt-in in-scan surface over the core fn | `propagate_drift`, scan pipeline |

Each unit is independently testable: the backlink helper is pure (dir in, map out); the judge is mockable at the `make_llm("drift_propagator")` boundary exactly as M2e's drift tests mock `drift_judge`; the orchestration is pure over those plus the ledger calls.

---

## 5. Testing (success criteria)

LLM mocked at the `make_llm("drift_propagator")` boundary; ledger and backlink helpers exercised directly.

**Backlink helper**
1. `build_entity_backlink_map` returns `stem -> [(category, slug, path)]` for `[[entities/<stem>]]` links across preserved dirs; `regenerate_referenced_in_wiki` still produces identical `## Referenced in wiki` output (refactor is behavior-preserving).
2. M4 filtering keeps only `concepts`/`adrs`/`architecture`; `sources`/`work` backlinks are excluded from the trigger join.

**Gating / anchor / pre-filter**
3. `propagation_candidates` yields exactly the entities where `drift_propagated_commit != last_updated_commit` (absent anchor ⇒ candidate); an entity whose anchors are equal is not a candidate.
4. After a run, every processed candidate's `drift_propagated_commit` is stamped to its `last_updated_commit`; a second `run_propagate_drift` with no further code change judges **nothing** (idempotent — the standalone-after-scan case).
5. `--dry-run` leaves `drift_propagated_commit` unstamped (re-runnable).
6. A target with a `rejected` or `created` ledger note is skipped (not judged); a target with no note or a `proposed` note is judged.

**Judge → produce**
7. Per-page batching: a page backlinked by two changed entities, both stale, yields **one** ledger note with **two** `source: drift` origins (`detected_commit`/`hash` set, ingest never sets them).
8. A re-fire of the same entity on the same target updates that origin in place (no duplicate); `detected_commit` advances; status stays `proposed`.
9. ADR finding is annotate-framed (`kind: adr`, rationale references supersede/Consequences, never "rewrite"); `mode` is `update_existing`.
10. Non-stale page → no note written.
11. Parse-miss / judge error → fail-safe to not-stale, zero notes, run non-fatal.

**Surfaces / guardrails**
12. `--dry-run` judges and populates the report but writes zero notes (and, per test 5, no anchor stamp).
13. `--only <entity>` restricts the candidate set; `--only <page>` restricts the target set.
14. `PropagateDriftResult` / `--json` exposes pages-judged, entities-considered, notes-written, stale-rate, skipped-settled.
15. `gw scan --propagate-drift` runs the pass after narration and writes notes; without the flag, no drift notes appear (default off).

---

## 6. Scope

**In scope:** the per-entity `drift_propagated_commit` anchor + `propagation_candidates` helper (§3.1); the `build_entity_backlink_map` extraction (§3.2); `run_propagate_drift` orchestration (§3.6) with the per-page kind-aware judge (§3.4), ledger production, and anchor stamping (§3.5); the `drift_propagator` role + prompt; `gw wiki propagate-drift` + MCP twin + `gw scan --propagate-drift` (§3.7); the `--dry-run` / `--only` / summary-report guardrails (§3.8); the M4-reserved origin keys (`detected_commit`, `hash`).

**Out of scope:**
- **Creation/update consumer** — acting on `approved` notes to edit/annotate curated pages and flip to `created` (M3's deferred creation spec).
- **Any write** under `concepts/`/`adrs/`/`architecture/`.
- **Old→new narrative diff** and any narrative snapshot / wiki-git-history recovery (rejected §2: noisy + fragile).
- **Per-run hard cap** (visibility + `--only` preferred).
- **The `created`-reopen lifecycle** (§7 open-q #1) — owned by the future creation-consumer spec.
- **Ledger-schema changes** — M4 is a pure caller.
- **Semantic near-dup** of proposals (inherited foundation limitation).

---

## 7. Sequencing & open questions

**Order:** M3 ✓ → ledger foundation (+ M3 retrofit, in flight) → **this M4 drift producer** → M3 creation consumer (deferred) → M5 context curation.

**Open questions**
1. **`created`-reopen.** A curated page whose update was already `created` and that *later* genuinely re-drifts is never re-flagged (the pre-filter skips `created`). No `created` notes exist until the creation consumer ships, so this is **owned by that future spec**, not solved here. The likely shape: stamp a `created_commit` on the note at consumption and reopen to `proposed` when an entity drifts it beyond that commit.
2. **Judge prompt tuning vs. false-positive budget.** The `drift_propagator` tier and prompt rubric are first-draft; the eval harness (`deepeval`, `sweep_candidates`) measures quality-per-dollar. Settle the default tier after a sweep.
3. **Multi-origin rationale rendering** in the note body — inherited foundation open-q; one block per origin is the default.
