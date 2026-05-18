# vault-io ⟷ lattice-wiki-core Drift Decisions

**Upstream:** lattice-wiki-core @ `1b45172a9900842b0f8eea525c8270e7fff50605` at 2026-05-18
**Raw diff source-of-truth:** [`DRIFT-DECISIONS-RAW.md`](./DRIFT-DECISIONS-RAW.md)
**Spike basis:** [`spikes/002-lattice-drift-inventory/README.md`](../../.planning/spikes/002-lattice-drift-inventory/README.md) §Investigation A
**Phase 12 plans:** [`12-01`](../../.planning/phases/12-drift-backport-ecosystem-rebrand-m2/12-01-drift-raw-diff-dump-PLAN.md) (raw dump) / [`12-02`](../../.planning/phases/12-drift-backport-ecosystem-rebrand-m2/12-02-verdicts-and-backports-PLAN.md) (verdicts + backports)

## Verdict Vocabulary

- **PORT** — substantive upstream change landed in vault-io as an atomic backport commit (commit SHA in row).
- **LEAVE-AHEAD** — vault-io is intentionally ahead of upstream (lib-ification, MCP error-handling, no-tiktoken, etc.). Rationale cites a Phase 11 D-ID or `WR-01`/`WR-02`.
- **LEAVE-ARCH** — upstream serves a subsystem vault-io stripped (`work-layer`, `package-family`, `CLI main()`). Rationale cites the stripped subsystem per PROJECT.md "Explicitly out of v1.2".
- **LEAVE-COSMETIC** — only comment / formatting / docstring diff; nothing observable.
- **IDENTICAL** — `diff -q` reports no difference.

The 11 rows below cover the overlapping module set from spike 002 §A. The `lint/*` row collapses 8 lint sub-files into a single verdict; per-sub-file inspection (recorded in `12-02-scratch-verdicts.md`) found no sub-file requiring a different verdict, so no row-level footnote is added.

## Verdicts

| file | upstream-commit | LOC Δ | verdict | rationale (one line) | backport-commit-sha |
|------|-----------------|-------|---------|----------------------|---------------------|
| `git_state.py` | `1b45172a9900842b0f8eea525c8270e7fff50605` | 0 | IDENTICAL | byte-equal to upstream per DRIFT-DECISIONS-RAW.md (no diff hunks) | — |
| `append_log.py` | `1b45172a9900842b0f8eea525c8270e7fff50605` | +30 | LEAVE-AHEAD | vault-io adds `raise_exception=True` (WR-01) and stderr-JSON output (WR-02) for MCP boundary error handling | — |
| `update_index.py` | `1b45172a9900842b0f8eea525c8270e7fff50605` | +29 | LEAVE-AHEAD | D-02 lib-ification: vault-io adds public `update_index(wiki)` entry point so ingest_work_item can call it without subprocess | — |
| `update_tokens.py` | `1b45172a9900842b0f8eea525c8270e7fff50605` | +6 | LEAVE-AHEAD | D-02 lib-ification with no-tiktoken (CLAUDE.md §3): replaces tiktoken/cl100k with Bedrock CountTokens + model_id/region lib params | — |
| `ingest_work_item.py` | `1b45172a9900842b0f8eea525c8270e7fff50605` | -1 | LEAVE-AHEAD | D-02 lib-ification: vault-io exposes `file_work_item(wiki, fm, body, ...)` library shape (no argparse main, no subprocess helpers) per PROJECT.md / BACKPORT-03 | — |
| `init_vault.py` | `1b45172a9900842b0f8eea525c8270e7fff50605` | -15 | LEAVE-AHEAD | D-02 lib-ification + WR-01: vault-io drops `lattice_workspace.init` dep, swaps `sys.exit` for `RuntimeError`, swaps `print` for `logger`, and strips package-family from valid container choices | — |
| `lint/*` | `1b45172a9900842b0f8eea525c8270e7fff50605` | various | LEAVE-AHEAD | D-02 lib-ification: vault-io relocates `_is_placeholder_target` from `lint_wiki.py` into `lint/common.py` and adds `if kind == "package":` guard around dep-detail-without-load-bearing in `lint/dependency.py`; no substantive upstream changes to backport | — |
| `layout_io.py` | `1b45172a9900842b0f8eea525c8270e7fff50605` | -98 | LEAVE-ARCH | package-family strip per PROJECT.md "Explicitly out of v1.2" — vault-io removes `_PACKAGE_FAMILY_FIELDS`, `ensure_package_pages`, `ensure_domain_pages` | — |
| `detect_containers.py` | `1b45172a9900842b0f8eea525c8270e7fff50605` | -129 | LEAVE-ARCH | package-family strip per PROJECT.md "Explicitly out of v1.2" — vault-io removes `_is_package_family_shape`, `_find_package_families`, package-family classification path | — |
| `scan_monorepo.py` | `1b45172a9900842b0f8eea525c8270e7fff50605` | -151 | LEAVE-ARCH | package-family strip per PROJECT.md "Explicitly out of v1.2" — vault-io removes `_collect_package_family_member`, `_iter_package_family_dirs`, package-family discovery branch | — |
| `ingest_source.py` | `1b45172a9900842b0f8eea525c8270e7fff50605` | -181 | LEAVE-ARCH | CLI main() strip — vault-io drops argparse `main()` + version-check + subprocess calls in favor of library exports only (lib-ification posture) | — |

## Summary

- **Verdict tally:** 1 IDENTICAL · 6 LEAVE-AHEAD · 4 LEAVE-ARCH · 0 PORT · 0 LEAVE-COSMETIC
- **No backport commits required at this sync** — every drift hunk is either byte-identical, an intentional vault-io divergence (lib-ification / MCP error handling / no-tiktoken), or a vault-io subsystem strip (package-family / CLI `main()`) per PROJECT.md.
- **BACKPORT-01 (lint/\*)** closed: lint sub-files share a single LEAVE-AHEAD verdict. Vault-io is ahead via the `_is_placeholder_target` relocation and the `kind == "package"` guard; the remaining sub-files differ only by import-path renames.
- **BACKPORT-02 (init_vault.py)** closed: LEAVE-AHEAD via D-02 lib-ification and WR-01 (RuntimeError vs sys.exit).
- **BACKPORT-03 (ingest_work_item.py)** closed: LEAVE-AHEAD — `file_work_item(...)` library shape fits the MCP boundary contract; upstream's argparse `main()` + subprocess helpers are intentionally absent.
- **BACKPORT-04** closed: this file documents every "leave" decision so the rationale survives the rebrand sweep in plan 12-03.

## Re-sync protocol

Future re-sync: bump `UPSTREAM_SHA` in `scripts/drift-diff.sh`, checkout that SHA in your local upstream clone, re-run the dump, then re-do the verdict pass. Update the SHA pin in this file's header.

The script honors a `UPSTREAM_REPO` env override so contributors on other hosts (and CI) do not need to edit the script:

```
UPSTREAM_REPO=/path/to/lattice bash scripts/drift-diff.sh > packages/vault-io/DRIFT-DECISIONS-RAW.md
```

If `UPSTREAM_REPO` is unset, the script falls back to `/Users/pat/Personal/lattice` (the author's local layout); the existing "FATAL: upstream repo not found" guard catches missing-path operator errors.
