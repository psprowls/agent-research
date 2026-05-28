# Phase 50: App Reclassification (graph-io) - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-27
**Phase:** 50-App Reclassification (graph-io)
**Areas discussed:** Signal precedence order, Where classification runs in the pipeline, URI rewrite + inbound edge handling, wiki-io interaction scope

---

## Signal precedence order

| Option | Description | Selected |
|--------|-------------|----------|
| Framework > CLI (nextjs > expo > spa > cli) | Most-specific framework signal wins; a Next.js app with a bin script is `app_kind=nextjs`. Single value, no extra storage. | |
| First-match-wins by detection order | Document detection order (`pyproject.scripts → package.json.bin → next → expo → vite+html`); whichever inspects first wins. Simpler; lossy. | |
| All-signals recorded; pick one for app_kind | Store every matched signal as `app_signals: [...]`; derive `app_kind` as most-specific framework if any, else `cli`. Lossless. | ✓ |

**User's choice:** All-signals recorded; pick one for app_kind
**Notes:** Lossless option preserves the ability to answer queries like "all packages that use Next.js *and* expose a CLI" without re-parsing manifests. Tiebreak between frameworks: alphabetical-stable `nextjs > expo > spa` (frameworks are mutually exclusive in practice).

---

## Where classification runs in the pipeline

| Option | Description | Selected |
|--------|-------------|----------|
| New `classification.py` module called inline from packages.refresh | Pure function `classify(manifest_dict, pkg_dir) → (kind, app_kind, app_signals)`. Loop emits `kind='app'` or `kind='package'` directly. `index.html` check via `(pkg_dir / 'index.html').exists()`. No reclassify UPDATE. | ✓ |
| Inline in packages._read_pyproject / _read_package_json | Detect signals at manifest-parse time; smallest diff but spreads logic across two readers. | |
| Separate post-pass `reclassify.py` after packages.refresh | Emit `kind='package'` first; reclassify via SQL UPDATE on `kind`. Novel for this codebase; complicates upsert semantics. | |

**User's choice:** New `classification.py` module called inline from packages.refresh
**Notes:** Filesystem-direct `index.html` check (D-05) keeps `classification.classify()` free of a `sqlite3.Connection` parameter, so it stays purely testable. Pure function consuming the existing manifest info dict + pkg_dir.

---

## URI rewrite + inbound edge handling

| Option | Description | Selected |
|--------|-------------|----------|
| In-place UPDATE of `kind` on the existing row | Look up `(package, name, path)` and `(app, name, path)` before upsert; if other-kind row exists and classification flipped, UPDATE that row's `kind`/`uri`/`attrs_json` in place. FK refs survive. | ✓ |
| Insert new row + rewrite all inbound edges by FK | Insert App row; `UPDATE edges SET src=new_id WHERE src=old_id` for src and dst; DELETE old Package row. Explicit edge migration; novel mutation pattern. | |
| Insert+keep both rows; mark old as stale | Additive, reversible; doubles node count for reclassified packages and leaves zombies queries must filter. Overkill. | |

**User's choice:** In-place UPDATE of `kind` on the existing row
**Notes:** Preserves the row's id and therefore every inbound edge FK — no edges table mutation needed. Wikilink rewrites in the vault are deferred entirely to Phase 53 cutover; Phase 50 is graph-only.

---

## wiki-io interaction scope

| Option | Description | Selected |
|--------|-------------|----------|
| Defer entirely — Phase 50 is graph-io only | wiki-io stays untouched; `_infer_package_type` heuristic stays. The flip lands in Phase 52 when entity_writer is being reworked anyway. Smallest blast radius. | ✓ |
| Replace `_infer_package_type` heuristic with graph lookup now | Couples Phase 50 to a wiki-io change and its tests; eliminates the heuristic immediately. | |
| Add graph-backed path BUT keep heuristic as fallback | Defensive; preserves backwards compat; costs dual code path until someone removes the heuristic later. | |

**User's choice:** Defer entirely — Phase 50 is graph-io only
**Notes:** Roadmap goal says App nodes should ALLOW distinct treatment — that wording is permissive, not mandatory-this-phase. Cleanest phase boundary; Phase 52 will do the wiki-io flip naturally as part of `entity_writer` rework.

---

## Claude's Discretion

- Whether to add `_VALID_APP_KINDS = frozenset({"cli","nextjs","expo","spa"})` in `queries.py` as a Python-side gate. Default: yes, with a unit test.
- Exact `attrs_json` shape for `app_signals` (just the sorted list, or also a per-signal `signals_detail` sub-object). Default: just the sorted list (minimal-attrs convention from Phase 49 D-08).
- Whether the existing-row probe in D-06 issues a per-manifest `SELECT` or a batched pre-loop lookup. Default: per-manifest for code-locality.
- Whether `cg describe-app` surfaces `app_signals` always or only behind `--verbose`. Default: always.

## Deferred Ideas

- wiki-io consumer flip (replacing `_infer_package_type` with graph lookup) — Phase 52.
- Wikilink rewrites in the vault (`[[pkg_X]]` → `[[app_X]]`, entity-page filename moves) — Phase 53.
- `_VALID_APP_KINDS` enforcement choice — Claude's Discretion; revisit if drift becomes a problem.
- Per-signal metadata (which manifest field triggered, which version pinned `next`, etc.) — attrs_json extension later if a use case appears.
- Additional app frameworks (`remix`, `astro`, `nuxt`, FastAPI server detection) — out of scope for v1.9; signal set fixed by APP-01.
- Cross-language CLI signals beyond `[project.scripts]` / `bin` (e.g., `__main__.py` shebang, `Makefile run` target) — out of scope.
