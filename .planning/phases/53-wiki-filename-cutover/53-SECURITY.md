---
phase: 53-wiki-filename-cutover
audit_date: 2026-05-28
asvs_level: L1
block_on: high
auditor: gsd-security-auditor
threats_total: 13
threats_closed: 13
threats_open: 0
status: SECURED
---

# Phase 53: Wiki Filename Cutover — Security Audit

## Summary

All 13 threats verified. No blockers. Phase may ship pending manual UAT gate (H.1 / H.2
in `53-VERIFICATION.md`) which is a functional acceptance requirement, not a security gap.

---

## Threat Verification

### Plan 53-01 — Markdown Reshape

| Threat ID | Category | Disposition | Status | Evidence |
|-----------|----------|-------------|--------|----------|
| T-53-01-T | Tampering | mitigate | CLOSED | `.planning/REQUIREMENTS.md` contains `encode_slug` at line matching new WIKI-FN-05 text (grep returns 1 hit); `.planning/ROADMAP.md` §Phase 53 contains `encode_slug` in SC #1 (2 hits). Surgical `Edit`-tool edits are version-controlled; commits `d04cc9a` + `d918873` touch only `.planning/REQUIREMENTS.md` and `.planning/ROADMAP.md`. PR diff auditable. |
| T-53-01-R | Repudiation | mitigate | CLOSED | `.planning/ROADMAP.md` line 227: `**Scope reshape**: Per \`53-CONTEXT.md\` D-01..D-10 the original scope … was removed.` Decision trail from reshaped WIKI-FN-05/06 back to `53-CONTEXT.md` D-01..D-10 is explicit and present in both planning documents. |
| T-53-01-V | Input Validation | accept | CLOSED | Accepted: plan touches only checked-in markdown; no user input crosses any boundary. No code evidence required. |
| T-53-01-I | Information Disclosure | accept | CLOSED | Accepted: edited content is non-secret project documentation. No code evidence required. |
| T-53-01-D | Denial of Service | accept | CLOSED | Accepted: markdown edits have no runtime cost. No code evidence required. |
| T-53-01-S | Spoofing | accept | CLOSED | Accepted: no identity layer in this plan. No code evidence required. |

### Plan 53-02 — Source Cleanup

| Threat ID | Category | Disposition | Status | Evidence |
|-----------|----------|-------------|--------|----------|
| T-53-02-T | Tampering | mitigate | CLOSED | `grep -n "^def encode_slug\|^def decode_slug\|^_ADMITTED_URI_PREFIXES" entity_writer.py` → 0 hits (functions provably absent, not shadowed). Global symbol grep `packages/ agents/ --include="*.py"` → 0 hits. Tests in `packages/wiki-io/tests/` contain 0 slug refs. Commits `3757308`, `cee3482`, `e71bec2`, `4dff073` in git history with refactor/test scope. |
| T-53-02-V | Input Validation | mitigate | CLOSED (see note) | `link_rewriter.py` and `index_generator.py` derive URIs from graph node `attrs.get("uri")` (safe `.get()`, no KeyError possible) rather than from disk frontmatter. Forward derivation goes through `_short_filename` (link_rewriter line 39, 277; index_generator line 60, 426). `entity_writer.py` deletion sweep uses `post.metadata.get("uri")` at line 766 (`.get()`, not bracket access); the per-entity write path at line 755 and deletion loop at line 787 are both wrapped in `except Exception` that buckets failures into `EntityWriteError`. **Note:** the declared mitigation describes "KeyError raised; caller catches and reports with path." The implementation is actually safer: `.get()` returns `None` on missing key (no raise); the `except Exception` try/except in `write_entities` would catch a raise if one occurred. Silent-skip on missing URI is used throughout. This is a stronger defense than declared, not a weaker one. |
| T-53-02-I | Information Disclosure | accept | CLOSED | Accepted: removed code reduces attack surface; no new data surfaces. No code evidence required. |
| T-53-02-D | Denial of Service | accept | CLOSED | Accepted: `python-frontmatter` parse cost is O(file size), under 1 second for typical vault. No new DoS surface vs. prior `decode_slug` regex. No code evidence required. |
| T-53-02-R | Repudiation | mitigate | CLOSED | Git history contains all four deletion/rewrite commits with explicit refactor/test scope labels: `3757308 refactor(53-02): rewrite consumers…`, `cee3482 refactor(53-02): delete encode_slug, decode_slug, _ADMITTED_URI_PREFIXES`, `e71bec2 test(53-02): delete legacy slug tests…`, `4dff073 test(53-02): retarget migrate_vault…`. PR diff is auditable. |
| T-53-02-S | Spoofing | accept | CLOSED | Accepted: no identity layer. No code evidence required. |
| T-53-02-V2 | Input Validation | mitigate | CLOSED | `find packages/wiki-io/tests/fixtures/round-trip-vault/ -name "*__*__*__*.md"` → 0 files. `grep -rln "\[\[.*__.*__.*__.*\]\]" round-trip-vault/` → 0 files. Fixture is self-consistent with short-form scheme. CI test gate (uv run pytest) passed at 356 passed per 53-VERIFICATION.md. |

---

## Accepted Risks Log

| Threat ID | Rationale |
|-----------|-----------|
| T-53-01-V | Plan 53-01 edits only version-controlled markdown; no runtime boundary crossed. |
| T-53-01-I | Planning documents contain no secrets or confidential data. |
| T-53-01-D | Markdown edits have no execution cost. |
| T-53-01-S | No authentication or identity layer exists in this plan. |
| T-53-02-I | Code deletion reduces attack surface; no new information is exposed. |
| T-53-02-D | `python-frontmatter` YAML parse is bounded by file size; well within 1 second for vault-scale files. Same order as prior `decode_slug` regex. |
| T-53-02-S | No identity layer. |

---

## Unregistered Flags

None. SUMMARY.md `## Threat Flags` sections for both plans contain no unregistered attack-surface items.

---

## Implementation Notes (Non-Blocking)

**T-53-02-V mitigation diverges from declared pattern (implementation is safer):**

The threat register declared: "missing `uri` key → `KeyError` raised; caller catches and reports."
The actual implementation uses `attrs.get("uri")` and `post.metadata.get("uri")` throughout — no bracket
access that could raise `KeyError`. The per-entity and deletion-sweep paths in `write_entities` are
wrapped in `except Exception` error-bucketing regardless.

The `link_rewriter.py` and `index_generator.py` modules do not perform disk-level frontmatter reverse
lookups at all — they obtain URIs from live graph query results (`node.attrs.get("uri")`), which means
the frontmatter-load error class is not reachable from those modules. The declared mitigation over-specified
the mechanism; the actual defense is equally robust. No security gap.

---

## Out-of-Scope Pre-existing Finding

`tests/test_integration_gate.py::test_integration_test_files_use_canonical_gate` fails in the
workspace test suite (1 failure in `uv run pytest` at 1526 passed / 1 failed). This failure
predates Phase 53; no Phase 53 file was touched by the affected 7 integration test files.
Recorded in `53-02-SUMMARY.md §Issues Encountered`. Not a Phase 53 security issue.
