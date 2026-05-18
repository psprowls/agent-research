# Phase 12 Drift Verdict Scratch (pre-fill — fill `Verdict` + `Rationale` columns inline)

Source-of-truth row list: spike 002 §A "Overlapping modules" (11 rows; `lint/*` collapsed).
Verdict vocabulary (SR-03 — fixed set): PORT | LEAVE-AHEAD | LEAVE-ARCH | LEAVE-COSMETIC | IDENTICAL.

| # | Module (relpath) | Spike Verdict | LOC Δ | Hint (operator priors — not pre-assignment) | Verdict | Rationale (one line) | Backport SHA |
|---|------------------|---------------|-------|---------------------------------------------|---------|----------------------|--------------|
| 1 | `git_state.py` | IDENTICAL (byte-equal) | 0 | IDENTICAL |  |  | — |
| 2 | `append_log.py` | DRIFTED-COMPATIBLE | +30 | LEAVE-AHEAD (WR-01/WR-02) |  |  | — |
| 3 | `update_index.py` | DRIFTED-COMPATIBLE | +29 | LEAVE-AHEAD (lib-ification, public `update_index(wiki)`) |  |  | — |
| 4 | `update_tokens.py` | DRIFTED-COMPATIBLE | +6 | LEAVE-AHEAD (no-tiktoken project rule per CLAUDE.md §3) |  |  | — |
| 5 | `ingest_work_item.py` | DRIFTED-INCOMPATIBLE-API | -1 | LEAVE-AHEAD (`file_work_item` lib shape — PROJECT.md recommendation) |  |  | — |
| 6 | `init_vault.py` | DRIFTED-COMPATIBLE | -15 | TBD — body-diff determines PORT vs LEAVE-COSMETIC |  |  | — |
| 7 | `lint/*` | DRIFTED-COMPATIBLE | various | TBD per-file inside row — likely PORT for each (BACKPORT-01); if sub-files diverge add footnote |  |  | — |
| 8 | `layout_io.py` | DRIFTED-FEATURE-LOSS | -98 | LEAVE-ARCH (package-family strip — out of v1.2) |  |  | — |
| 9 | `detect_containers.py` | DRIFTED-FEATURE-LOSS | -129 | LEAVE-ARCH (package-family strip) |  |  | — |
| 10 | `scan_monorepo.py` | DRIFTED-FEATURE-LOSS | -151 | LEAVE-ARCH (package-family strip) |  |  | — |
| 11 | `ingest_source.py` | DRIFTED-CLI-STRIPPED | -181 | LEAVE-ARCH (CLI `main()` strip) |  |  | — |
