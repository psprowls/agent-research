# Phase 52 Discussion Log

**Phase:** 52 — Wiki Filename Slimdown — Core
**Discussed:** 2026-05-28
**Mode:** default (single-pass)

---

## Gray Areas Presented

1. **Collision detection scope & timing** — pre-pass vs. lazy vs. side-table.
2. **Hash format & length for colliders** — algorithm, length, and one-vs-all-colliders semantics.
3. **Dependency naming** — URI prefix rename (`dependency:` → `dep:`) vs. filename-layer alias only.
4. **`decode_slug` fate** — drop / collision-aware / side-manifest.

User selected: ALL FOUR for discussion.

---

## Discussion

### Area 1: Collision detection scope & timing

**Claude recommended:** Pre-pass at write time, computed once per `write_entities` invocation. Pure helper `short_filename(uri, collision_set, suite_kind=None)` consumes the pre-computed set. Property-testable in isolation; no persistent state; O(N) dwarfed by per-entity I/O.

**User decision:** Accepted.

**Captured as:** D-01, D-02.

---

### Area 2: Hash format & length

**Claude recommended:** sha256 of full URI, first 6 hex chars, `<stem>__<6hex>.md` format. **Diverged from the roadmap's literal "only the collider receives a suffix" wording** — recommended applying the suffix to ALL members of any colliding set (symmetric, pure, time-stable; adding a 3rd colliding URI later doesn't shift which existing entity has the plain name).

**User decision:** Accepted, including the divergence from the roadmap text.

**Captured as:** D-03, D-04. CONTEXT.md explicitly notes the divergence and rationale.

---

### Area 3: Dependency naming

**Claude recommended:** Filename-layer alias only. Add `_URI_PREFIX_BY_KIND["dependency"] = "dep"` in `entity_writer.py:78-86`. Graph URIs stay `dependency:langchain-aws`. Mirrors the existing `repository → repo`, `package → pkg` aliases. Avoids the much-larger blast radius of touching graph-io URI builders.

**User decision:** Accepted.

**Captured as:** D-05, D-06 (extends to App + Builtin confirmation).

---

### Area 4: `decode_slug` fate

**Claude recommended:** Drop `decode_slug` from the new write path; reverse lookups go through `frontmatter.uri` reads. Function itself stays until Phase 53 cutover cleanup (rewriter needs old-long → URI mapping for one phase). Property test for WIKI-FN-04 only covers the forward direction.

**User decision:** Accepted.

**Captured as:** D-08, D-09.

---

## Scope Creep Redirected

None.

## Deferred Ideas

- Vault wikilink rewrites + atomic cutover commit → Phase 53.
- Deletion of `encode_slug` / `decode_slug` functions → Phase 53 cleanup plan.
- Cross-vault collision policy (multi-vault index) → defer until use case emerges.
- Hash length tuning (6 hex → 8 hex bump) → not needed at personal-vault scale.
- `hashlib.blake2b` swap → speed differential irrelevant; sha256 stays.

## Claude's Discretion (left to planner)

- Pre-pass SQL shape (plain Python grouping vs. window function).
- Property test framework choice (`hypothesis` strongly recommended).
- Whether to extract `_compute_collision_set(conn)` helper or inline.
- Whether to touch the stale-file cleanup glob loop at entity_writer.py:577 (default: leave untouched).
- Import location for `hashlib` (default: top-of-file).

---

*See `52-CONTEXT.md` for the canonical decision record consumed by downstream agents.*
