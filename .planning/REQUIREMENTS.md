# Requirements: Milestone v1.9 — Graph Refinements & Wiki Filename Slimdown

**Created:** 2026-05-27
**Milestone goal:** Tighten the graph-build pipeline (built-in handling, app classification) and slim the wiki projection (shorter human-readable filenames, drop dormant `package-family`) — so the graph admits noisy stdlib calls cleanly without leaking them into the wiki, packages that are really apps get classified as such, and entity pages get human-readable filenames instead of fully-qualified URI slugs.

---

## v1.9 Requirements

### Built-in / stdlib handling (`graph-io`)

- [ ] **BUILTIN-01**: Scanner classifies imports of Python stdlib modules (`builtins`, `pathlib`, `os`, `sys`, `re`, `json`, `typing`, etc. — full stdlib list) as a new `Builtin` node kind in the graph instead of as unresolved `Symbol` / `Function` nodes.
- [ ] **BUILTIN-02**: Scanner classifies imports of Node.js / browser standard-library modules (`fs`, `path`, `crypto`, `http`, `os`, `util`, `stream`, etc. — full Node built-ins list) as the same `Builtin` node kind.
- [ ] **BUILTIN-03**: npm packages remain classified as `dependency` (no change). Bare-name resolution distinguishes Node built-ins from npm packages via Node's documented built-in module list.
- [ ] **BUILTIN-04**: `Builtin` nodes carry a `language` attribute (`python` or `javascript`) and a `module_name` attribute; URI scheme `builtin:<language>/<module_name>` (e.g. `builtin:python/pathlib`, `builtin:javascript/fs`).
- [ ] **BUILTIN-05**: Edges into `Builtin` nodes use the existing `used_by` relation; usage count derivable from edge multiplicity. No `requires` / `imports` edges are added for `Builtin`.
- [ ] **BUILTIN-06**: `cg list-builtins` CLI surface for inspection (mirrors `cg list-dependencies`); `cg describe-builtin <uri>` shows packages that use it.

### Package → App classification (`graph-io`)

- [x] **APP-01**: Scanner reclassifies a `Package` node as an `App` node when manifest signals indicate it is an application rather than a library: Python `pyproject.toml [project.scripts]` non-empty → CLI app; JS/TS `package.json bin` field present → CLI app; `next` in `package.json` dependencies → Next.js app; `expo` in `package.json` dependencies → Expo app; `vite` in dependencies + `index.html` at package root → SPA.
- [x] **APP-02**: `App` is a graph kind separate from `Package` (not just an attribute flag), so domain projections and wiki rendering can treat apps distinctly. App nodes participate in the same edges packages do (`belongs_to_domain`, `depends_on`, `physically_contains`, etc.).
- [x] **APP-03**: When no manifest signal matches, the node remains a `Package` (no false-positive reclassification). When multiple signals match (e.g., a CLI built on Next.js), the most-specific signal wins via documented precedence order.
- [x] **APP-04**: `App` nodes carry an `app_kind` attribute (`cli`, `nextjs`, `expo`, `spa`) recording which signal matched, for downstream rendering decisions.
- [x] **APP-05**: `cg list-apps` CLI surface; `cg describe-app <uri>` mirrors the existing `cg describe-package` shape with `app_kind` surfaced.
- [x] **APP-06**: URI scheme for apps preserves the package URI form so existing inbound references survive reclassification (e.g., `pkg:org/repo/eval-harness` becomes `app:org/repo/eval-harness` only when reclassified; the migration is a one-time scanner-driven rewrite).

### Wiki entity filename slimdown (`wiki-io`)

- [ ] **WIKI-FN-01**: Entity filenames switch from URI-fully-qualified (`pkg__org__repo__name.md`) to a short human-readable form: `<kind-prefix>_<name>.md` for the common case (e.g. `pkg_eval-harness.md`, `app_graph-wiki-agent.md`, `dep_langchain-aws.md`, `plugin_graph-wiki.md`, `repo_agent-research.md`, `domain_observability.md`, `builtin_pathlib.md` — though `builtin` pages are not rendered per BUILTIN below).
- [x] **WIKI-FN-02**: Test-suite filenames use a framework-aware prefix: `unit_tests_<pkg>.md` for unit suites and `int_tests_<pkg>.md` for integration suites, derived from the suite's `kind` attribute on the `TestSuite` graph node. Disambiguates the common case where multiple suites are literally named `tests`.
- [ ] **WIKI-FN-03**: When two entities would produce the same short filename (cross-repo, cross-org), append a short repo/org hash suffix only to the collider (e.g., `pkg_utils__a3f7c1.md`). Hash derived deterministically from the full URI; length tuned to keep collision-prevention while staying readable.
- [x] **WIKI-FN-04**: Filename derivation is a pure function of the entity URI + collision set, exposed in `wiki_io.entity_writer` as a testable helper. Property test confirms idempotence and collision-resistance.
- [ ] **WIKI-FN-05**: `migrate-vault` (or equivalent one-shot cutover command) rewrites existing inbound `[[…]]` wikilinks in curated lanes (`/concepts/`, `/adrs/`, `/architecture/`, `/work/`, `/sources/`) from the old URI-fully-qualified filenames to the new short filenames, in a single atomic commit on the vault repo. CommonMark-aware tokenizer (code-block / inline-code excluded) per v1.8 precedent.
- [ ] **WIKI-FN-06**: `generate_index()` writes the new short filenames in `wiki/index.md`. Existing exploratory `~/Personal/graph-wiki/agent-research` vault is re-scanned + migrated as part of milestone close.

### `package-family` removal

- [ ] **PKGFAM-01**: `package_family` kind removed from `_VALID_KINDS` in `graph-io`. Scanner no longer ingests `[tool.graph-wiki.package-family]` (or equivalent) sections. Reads against pre-v1.9 graphs error with `SCHEMA_MISMATCH` until rebuilt.
- [ ] **PKGFAM-02**: `package_family_uri` builder removed from `graph_io.uri`. Any code that imported it deleted or rewritten.
- [ ] **PKGFAM-03**: `entity-package-family.template` deleted from `wiki-io`. `ADMITTED_KINDS - {"package_family"}` narrow in `wiki_io.entity_writer` simplifies to just `ADMITTED_KINDS` (no exclusion). `wiki/package-family/` directory removed from the existing vault during migration.
- [ ] **PKGFAM-04**: `cg describe-package-family` / `cg list-package-families` subcommands removed (if they exist).
- [ ] **PKGFAM-05**: `domain_contains_domain` edges and the domain layer in general are **not** affected by this removal (orthogonal mechanism).

### Cleanup

- [ ] **CLEANUP-01**: Delete `_SLUG_ONLY_RE` and `_check_no_slug_only_wikilinks` (LIB-003) from `packages/eval-harness/src/eval_harness/divergence/librarian.py`. Update divergence rule registry, fixture expectations, and divergence eval baseline so LIB-003 is no longer expected to fire. LIB-001 (`_check_wikilink_resolves`) remains as the real safety net.

---

## Future Requirements (Deferred)

- **Dependency-family / dependency clustering** — re-introduce a `package-family`-like mechanism for grouping related dependencies (e.g. the `langchain-*` family) modeled on domain clustering rather than the old `package_family` kind. Defer until a concrete render need surfaces.
- **Optional novel-pattern inference for app classification** — extension to APP if the manifest-signal rules under-classify in practice (e.g., apps without a clear manifest signal but with an obvious `apps/` directory convention, custom build scripts, etc.). LLM-driven inference step similar to `graph propose-domains`.

## Out of Scope (this milestone)

- **Scanner pipeline 9-stage restructure** — per ONTOLOGY-SPEC §9; deferred until domain-overlay re-runs need to be cheap.
- **Open questions §11 of ONTOLOGY-SPEC** — tagging mechanism, cross-repo domain scope, role-flag confidence metadata, etc.
- **Backwards-compatible URI aliases** — old `pkg__org__repo__name.md` filenames are not retained as redirects. Single-user repo, no external consumers, wipe-and-rebuild is acceptable.
- **`one_liner:` write-time enforcement** — GSD-tool debt, not graph-wiki-agent code; filed separately.
- **Formal v1.6 / v1.8 milestone audits** — process debt, separate decision.
- **Nyquist retro-validation** — long-standing process decision, not v1.9 work.

---

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| BUILTIN-01 | Phase 49 | Pending |
| BUILTIN-02 | Phase 49 | Pending |
| BUILTIN-03 | Phase 49 | Pending |
| BUILTIN-04 | Phase 49 | Pending |
| BUILTIN-05 | Phase 49 | Pending |
| BUILTIN-06 | Phase 49 | Pending |
| APP-01 | Phase 50 | Complete |
| APP-02 | Phase 50 | Complete |
| APP-03 | Phase 50 | Complete |
| APP-04 | Phase 50 | Complete |
| APP-05 | Phase 50 | Complete |
| APP-06 | Phase 50 | Complete |
| PKGFAM-01 | Phase 51 | Pending |
| PKGFAM-02 | Phase 51 | Pending |
| PKGFAM-03 | Phase 51 | Pending |
| PKGFAM-04 | Phase 51 | Pending |
| PKGFAM-05 | Phase 51 | Pending |
| CLEANUP-01 | Phase 51 | Pending |
| WIKI-FN-01 | Phase 52 | Pending |
| WIKI-FN-02 | Phase 52 | Complete |
| WIKI-FN-03 | Phase 52 | Pending |
| WIKI-FN-04 | Phase 52 | Complete |
| WIKI-FN-05 | Phase 53 | Pending |
| WIKI-FN-06 | Phase 53 | Pending |
