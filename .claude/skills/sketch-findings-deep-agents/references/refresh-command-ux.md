# Refresh Command UX

Design decisions for `/graph-wiki:refresh` — the command that fleshes out under-filled wiki package/domain pages and re-syncs stale pages by writing a diff doc to `raw/diffs/` and dispatching `/graph-wiki:ingest`.

Synthesized from sketches 001, 002, 003. Source HTML in `sources/`.

## Command shape

```
/graph-wiki:refresh                          # sweep mode — every package/domain
/graph-wiki:refresh packages/vault-io        # targeted mode — one package
```

- **Autonomous** — no per-page prompts during the run. User reviews after.
- **Both modes share the same report format.** Targeted mode is a one-block subset of the sweep report.
- **Sync-state semantics** — `last_sync_commit` bumps per-package on ingest success, gated on clean working tree + HEAD on `main` (same gate `/graph-wiki:scan` already enforces).

## Decision 1 — Output cadence: streaming log

**Chosen:** every event on its own line as it happens (`✓ packages/vault-io   up-to-date`), grouped under stage headers (`→ scan`, `→ fill`, `→ diff`, `→ ingest`, `→ sync-state`, `→ log`). Final report block at the end with totals + cost + flagged-for-review callout.

**Rejected:**
- *Live status block with progress bar* — gave a dashboard feel but lost linear history during the run; requires a real TTY (breaks in CI / non-interactive contexts).
- *Quiet during run, structured report at end* — highest signal-to-noise but loses the in-flight "what is it doing right now" feeling on multi-minute runs.

**Why streaming won:** trust comes from watching it work. Scrollback is the audit trail. Pat watches refresh runs personally — this is a writer's tool, not a CI dashboard.

**Stage progression in the log:**

```
→ scan        vault for under-filled pages and last_sync drift
→ fill        TODO placeholders from source analysis
→ diff        stale packages, write to raw/diffs/
→ ingest      dispatch /graph-wiki:ingest on each diff
→ sync-state  bump last_sync_commit on refreshed pages
→ log         appended refresh entry
```

**Per-line glyphs** (consistent across the run):
- `✓` success
- `~` partial / drafted with low confidence / needs review
- `!` attention required (drift detected, stubs found)
- `…N more X elided` for elision of long lists

**Closing block** must always include:
1. Big-number summary: `15 pages updated · 2 diffs ingested · 3.4 min · $0.12`
2. **Explicit "wants your eyes" callout** — any page marked `~` (low-confidence draft) gets re-listed by path so the user can't miss it
3. Workspace and model attribution in the dim/muted color

## Decision 2 — Per-package result block: counted summary

**Chosen:** boxed block per package with structured counts (`filled`, `range`, `diff`, `ingest`, `flagged`). Top-right status badge: `[filled]` / `[synced]` / `[unchanged]`. Sweep view leads with a totals block, then per-package detail underneath.

**Rejected:**
- *Terse one-liner per package* — scans fast like `git status` but loses the audit detail (how much actually changed). Forces opening Obsidian to verify.
- *Full wikilink dump per package* — highest fidelity, mirrors `/graph-wiki:ingest`'s existing report style — but verbose for 12-package sweeps and overweights the names of touched pages over the shape of what happened.

**Why counted summary won:** middle density. Shows "filled 4 subpages, ingested 6 pages, 1 flagged" without enumerating page names that the user can find in Obsidian. Big sweeps stay scannable; targeted runs read naturally.

**Block structure:**

```
┌─ packages/vault-io                                         [synced]
│  range    30058ee..4656429  (82 commits · 47 files · ~1.8k LOC)
│  filled   —             (stubs already populated)
│  diff     1 doc         raw/diffs/vault-io-30058ee..HEAD.md
│  ingest   6 pages       api, patterns, context + 2 concepts + 1 adr
│  flagged  0
└─
```

- **`filled`**, **`diff`**, **`ingest`**, **`flagged`** are the four invariant rows; `range` only present when there was prior sync state to diff from.
- A short prose hint after the count (`api, patterns, context + 2 concepts + 1 adr`) gives shape without dumping every wikilink.
- Sweep prelude block (`packages scanned 12 · filled 4 pages · diffed 2 docs · ingested 9 pages · unchanged 7`) lets the user audit the totals before reading individual blocks.

## Decision 3 — Diff doc shape: hybrid

**Chosen:** `raw/diffs/<pkg>-<from>..<to>.md` is a markdown file with frontmatter and a fixed section order:

```
---
source_type: diff
package: packages/vault-io
from_commit: 30058ee
to_commit:   4656429
generated_by: graph-wiki:refresh
synthesized_by: qwen3-32b
commits: 82
files_changed: 47
sections:
  - machine: [commits, stat, exports, files, surface_diffs]
  - llm:     [summary, decisions, contradictions]
---

## Summary                  (LLM)
## Exports                   (machine — added/removed table with file:line)
   ### Added
   ### Removed
## Files touched             (machine — git --stat with surface-change markers)
## Commits                   (machine — git log --oneline)
## Decisions captured        (LLM — ADR-worthy items)
## Contradictions to verify  (LLM — wiki↔code drift)
## Surface-change diffs      (machine — inlined diff for 1-3 largest +/- files)
```

**Rejected:**
- *Raw `git diff` wrapped in markdown* — lossless and mechanical (no LLM in the loop) but expensive: ~18k tokens for the example package, paid on every ingest. The ingestor then has to do its own diff-summarization.
- *Pure LLM-curated semantic delta* — compact (~1.8k tokens) but single-pass loss: anything the synthesizer misses, the ingestor can't recover. Citations soften into prose.

**Why hybrid won:**

1. **Citations need to be ground truth.** Iron rule #5 ("every claim cites a source page or a code path") and the `api.md` template (`exportName(args) — src/path/to/file.ts:line`) need verbatim file:line refs. Machine-extracted Exports tables give those refs straight from the source tree.
2. **Judgment work stays with the LLM.** "What does this mean?" / "Is this ADR-worthy?" / "Does this contradict the wiki?" — that's where the model adds value. Listing which symbols moved doesn't need a model.
3. **Cost ends up between A and B.** ~6k tokens vs raw's ~18k. Two model passes per stale package (synthesizer → ingestor), but the second pass reads the cheaper artifact.
4. **Audit & recovery story.** When you open the diff doc in Obsidian, machine sections are verifiable against `git log`. If the LLM narrative drifts, structural sections still anchor the ingestor.

**Critical tweak applied to the original sketch C variant:** dropped the `## Pointers to original` section (the "tell the ingestor to shell out for more diff context" pattern doesn't fit the current ingestor — it doesn't autonomously call git). Replaced with an inlined `## Surface-change diffs` section containing the actual `git diff` for the 1-3 files with the largest `+/-` count. Gives the ingestor real code to anchor to without paying for all 47 files.

**File selection heuristic for `surface_diffs`:**
- Top 3 files by `|adds| + |removes|`
- Skip files with `<5` LOC change (noise)
- Always include a file if its diff caused an entry in the Exports table (so adds/removes can be cross-referenced)

## Iron-rule alignment

- **Rule 1** (code is source of truth) — the machine sections of the diff doc are *literally* the code. LLM prose only annotates, never invents.
- **Rule 2** (LLM never writes to raw/) — *refresh writes to raw/, not the LLM that runs inside it.* The synthesizer is invoked as a tool by the refresh runner, which writes the artifact. Document this in the command spec to avoid confusion.
- **Rule 4** (every ingest/scan touches ≥3 files) — refresh's per-package operation touches the page(s) being refreshed, plus `index.md` and `log.md`, so this is satisfied trivially.
- **Rule 5** (every claim cites a source or code path) — directly motivates the hybrid diff doc's structural sections.

## Open questions deferred to plan-phase

- **Per-subpage fill strategy.** Refresh autonomously fills what's mechanically possible. `api.md` (extract exports), `overview.md` File map (tree walk), and `context.md` cross-links (find wiki pages tagged with this package) are clean. `patterns.md` is hard — pattern extraction from source is judgment-heavy. Sketches assumed `patterns.md` may always end up flagged for review. Validate during plan-phase.
- **Targeted mode affordances.** Sketches assumed identical format to sweep. If single-package mode wants more detail per block (e.g., full wikilink dump since there's only one), revisit.
- **When `last_sync_commit` bumps.** Sketches assumed per-package on ingest success. Could also be deferred until end-of-sweep with a transaction-like rollback if any package fails. Per-package is simpler.

## Origin

Synthesized from:
- `sources/001-refresh-sweep-output/index.html` — sweep output cadence
- `sources/002-refresh-result-block/index.html` — per-package report density
- `sources/003-refresh-diff-doc/index.html` — diff artifact shape

Each source HTML preserves all 2-3 variants so the rejected directions are reachable for context.
