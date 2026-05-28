# Phase 51 Discussion Log

**Phase:** 51 — package-family Removal + Divergence Rule Cleanup
**Discussed:** 2026-05-28
**Mode:** default (single-pass)

---

## Gray Areas Presented

1. **Vault directory removal scope** — Phase 51 vs. Phase 53 cutover.
2. **Pre-v1.9 graph compatibility** — SCHEMA_VERSION bump vs. `_VALID_KINDS` rejection.
3. **Test fixture & V18 alias cleanup** — surgical edits + alias deletion policy.
4. **Divergence baseline regeneration** — hand-edit vs. tooling regen.

User selected: ALL FOUR for discussion.

---

## Discussion

### Area 1: Vault directory removal scope

**Claude recommended:** Defer to Phase 53 cutover. Phase 51 ships graph-io + wiki-io code removal only; `wiki/package-family/` deletion happens alongside wikilink rewrites in Phase 53. Mirrors Phase 50 D-08 ("wiki-io untouched; vault writes deferred to Phase 53"). PKGFAM-03 "removed during migration" wording is satisfied by Phase 53's `migrate-vault` operation.

**User decision:** Accepted.

**Captured as:** D-01.

---

### Area 2: Pre-v1.9 graph compatibility

**Claude recommended:** Bump `SCHEMA_VERSION` to 3 + explicit version-mismatch check at read time. Argued that Phase 51 *retracts* an admitted kind (vs. Phases 49/50 which *added* kinds), so the schema-version policy logic differs — stale graphs may have `package_family` rows that would explode in queries with cryptic errors.

**User decision:** REJECTED. User chose "Hold SCHEMA_VERSION at 2" — explained: "It doesn't matter, I will regenerate. This is a personal project at this point and I will just delete the graph and regenerate it with full."

**Follow-up question:** Where should the error surface if no schema bump?

**User answer:** Doesn't matter — manual regen via `cg update --full` is the workflow. No pre-flight check needed.

**Captured as:** D-02. PKGFAM-01's literal `SCHEMA_MISMATCH` wording is reinterpreted as "any error is acceptable; user manually regenerates."

---

### Area 3: Test fixtures + `ADMITTED_KINDS_V18` alias

**Claude recommended:** (a) Surgical fixture edits to round-trip-vault and lattice-wiki — golden snapshots preserved minus package-family entries; regen `vocab.index.json` via existing test tooling, not hand-edit. (b) Delete `ADMITTED_KINDS_V18` alias outright; rewrite the two call sites to plain `ADMITTED_KINDS`. No deprecation grace — single-developer project.

**User decision:** Accepted.

**Captured as:** D-03 (fixtures), D-04 (alias).

---

### Area 4: Divergence baseline regeneration

**Claude recommended:** Regenerate `baselines/divergence-librarian.json` via existing eval-harness tooling rather than hand-edit. Avoids drift risk between registered checks and the baseline. Hand-edit is fallback only.

**User decision:** Accepted.

**Captured as:** D-05.

---

## Scope Creep Redirected

None.

## Deferred Ideas

- Vault `wiki/package-family/` directory deletion → Phase 53 cutover.
- Pre-flight schema-mismatch check / migration command → out of scope (personal project; manual regen workflow).
- `ADMITTED_KINDS_V18` deprecation grace pattern → explicitly skipped; if needed in future, build with `__deprecated__` shim.

## Claude's Discretion (left to planner)

- Whether to delete `package-family.md` alongside `entity-package-family.md` in the same plan.
- Whether `dependency.py` / `link_rewriter.py` `package_family` references are code or comment-only.
- Order of CLI removal (`cg describe-package-family` / `cg list-package-families`) — slot with `package_family_uri` deletion.
- Whether divergence baseline regen runs before or after the LIB-003 code deletion.

---

*See `51-CONTEXT.md` for the canonical decision record consumed by downstream agents.*
