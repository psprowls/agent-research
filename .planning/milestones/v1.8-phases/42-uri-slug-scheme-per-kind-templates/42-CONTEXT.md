# Phase 42: URI Slug Scheme + Per-Kind Templates - Context

**Gathered:** 2026-05-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Lock the two load-bearing v1.8 design contracts as **code constants with property-tested helpers**, before any entity-writing code (Phase 43+) runs:

1. **D1 — URI-to-filename slug encoding** (`encode_slug` / `decode_slug` in `wiki_io/entity_writer.py`) — collision-free, round-trip stable across all 7 admitted kinds, including the three v1.8-new kinds whose URI builders this phase adds to `graph_io/uri.py`.
2. **D2 — Scanner-owned frontmatter whitelist** (`SCANNER_OWNED_KEYS` frozenset in `wiki_io/entity_writer.py`) — reconciled single source of truth for which frontmatter keys the scanner may overwrite; everything else is human-territory and preserved on merge.

Provisioned alongside the design lock:
- `ADMITTED_KINDS` frozenset (7 v1.8 wiki entity kinds, underscore-form matching `graph_io._VALID_KINDS`).
- Three new URI builders in `graph_io/uri.py` (`package_family_uri`, `plugin_uri`, `dependency_uri`).
- Seven `entity-*.md` templates under `packages/wiki-io/src/wiki_io/assets/page-templates/` (one per admitted kind).
- `wiki/entities/` lane added to `init_vault.py`'s `FIXED_VAULT_DIRS` with a sentinel-comment `_index.md`.

**Not in scope (Phase 42):** the `write_entities()` function body, `merge_frontmatter()` logic, hard-delete reconciliation, lock-file acquisition, LLM narrative generation, scanner integration. Those land in Phases 43–45.

**No new capabilities.** This is a foundation lock — every decision is constrained by the milestone goal (`/entities/` lane driven by graph-io as the curated human-readable projection).

</domain>

<decisions>
## Implementation Decisions

### Slug encoding (D1)

- **D-01:** **Encoding scheme = kind-prefix preserved + `__` (double-underscore) separator** for both `:` and `/`.
  - `pkg:agent-research/graph-io` → `pkg__agent-research__graph-io.md`
  - `domain:agent-research/billing` → `domain__agent-research__billing.md`
  - `test_suite:agent-research/eval-harness/unit` → `test_suite__agent-research__eval-harness__unit.md`
  - `repo:agent-research/agent-research` → `repo__agent-research__agent-research.md`
  - `package_family:aws` → `package_family__aws.md`
  - `plugin:graph-wiki` → `plugin__graph-wiki.md`
  - `dependency:pypi/boto3` → `dependency__pypi__boto3.md`
  - Provably injective: the kind segment uses single-underscore (`test_suite`, `entry_point`, `package_family`) and the path separator is double-underscore — they cannot collide.
- **D-02:** **Kind values are snake_case (underscore-form), matching `graph_io._VALID_KINDS`.** v1.8 ADMITTED_KINDS = `frozenset({"repository", "domain", "package", "package_family", "plugin", "dependency", "test_suite"})`. This corrects the milestone-roadmap text where some places write `test-suite` / `package-family` with hyphens — the canonical form is underscores throughout (frontmatter, slug, ROADMAP usage going forward). Reconciliation lives in this phase.
- **D-03:** **`decode_slug(encode_slug(uri)) == uri` is required for all 7 admitted kinds.** This is enforced by the Hypothesis property test. Round-trip works because the encoder is a simple `s.replace(":", "__").replace("/", "__")` and the decoder splits on `__` and rebuilds via the kind-specific URI builder.
- **D-04:** **Three new URI builders go into `graph_io/uri.py` in this phase:** `package_family_uri(name: str) -> str`, `plugin_uri(name: str) -> str`, `dependency_uri(ecosystem: str, name: str) -> str`. Ecosystem is required for `dependency` (avoids future cross-ecosystem collision); `package_family` and `plugin` take only a name (no org/repo, since these are concept-level, not repo-scoped). Mechanical addition (~10–15 LOC) alongside the existing seven builders.
- **D-05:** **Collision policy = fail loudly.** `encode_slug` is a pure function with no runtime collision table. The Hypothesis property test asserts injectivity; if the test ever fails after a future kind addition, the developer fixes the encoding rather than silently appending a hash suffix. No fallback path.

### Whitelist (D2)

- **D-06:** **`SCANNER_OWNED_KEYS` is a single flat `frozenset[str]`** (not a per-kind dict). Matches roadmap success criterion #5 verbatim. Merge invariant for Phase 43: `key in SCANNER_OWNED_KEYS` ⇒ the scanner may overwrite; otherwise the existing value is preserved as-is.
- **D-07:** **Whitelist content baseline = ARCHITECTURE.md union** (broader of the two research sources). Includes graph-edge-derived fields AND graph-node-attr-derived fields (e.g. `language`, `version`, `file_count`, `ecosystem`). Concrete initial set (subject to mechanical cleanup in Phase 43):
  ```python
  SCANNER_OWNED_KEYS: frozenset[str] = frozenset({
      # Universal
      "uri", "kind", "graph_name", "last_scan_at",
      # Edge-derived (package)
      "domains", "depends_on", "test_suites", "entry_points",
      # Node-attr-derived (package)
      "language", "version",
      # Edge-derived (domain)
      "parent_domain", "sub_domains", "packages",
      # Edge-derived (test_suite)
      "tested_packages", "suite_kind", "file_count",
      # Edge-derived (dependency)
      "ecosystem", "used_by", "versions_in_use",
      # Edge-derived (package_family)
      "members",
      # Edge-derived (repository)
      "package_count",
  })
  ```
  Phase 43 may add fields here as graph queries are wired in; Phase 42 locks the shape and the principle. The constant has a module-level docstring listing the four explicit human-only keys (`status`, `last_reviewed`, `owner`, `notes`) for documentation.
- **D-08:** **Naming convention for whitelist keys = snake_case, plural for collections, matches graph-io node attrs.** Edge `belongs_to_domain` surfaces as `domains: [...]` on the page (not `belongs_to_domain`). Edge `covered_by` surfaces as `test_suites: [...]` on packages and `tested_packages: [...]` on suites (direction-aware). Reads naturally on rendered pages.
- **D-09:** **No separate `HUMAN_OWNED` constant.** Whitelist is the sole source of truth; everything outside it is human territory by definition. A unit test in Phase 42 asserts `{"status", "last_reviewed", "owner", "notes"} & SCANNER_OWNED_KEYS == set()` to catch accidental drift. Examples of human-only keys documented in the module docstring.

### Module placement

- **D-10:** **Phase 42 creates `packages/wiki-io/src/wiki_io/entity_writer.py`** containing only:
  1. `ADMITTED_KINDS` frozenset
  2. `SCANNER_OWNED_KEYS` frozenset
  3. `encode_slug(uri: str) -> str`
  4. `decode_slug(slug: str) -> str`
  5. Module docstring documenting the human-only-key convention
  
  Phase 43 expands this module with `EntityWriteResult` dataclass, `merge_frontmatter()`, `write_entities()`, hard-delete logic. The module IS the scaffold from day one — no separate `slug.py` or `entity_kinds.py`.
- **D-11:** **Hypothesis added to `packages/wiki-io`'s test dependency group** (PEP 735 `[dependency-groups].dev` per CLAUDE.md). One new dev dep is acceptable; Hypothesis is the canonical Python property-testing library and is the right tool here.

### Test corpus

- **D-12:** **Property test uses Hypothesis composite strategies, one per admitted kind**, fanned out via `@given(uri=admitted_uri_strategy())`. Per-kind strategies use the URI builders (`pkg_uri`, `domain_uri`, etc.) with `text(alphabet=characters(...))` for org/repo/name fragments. Hypothesis defaults give us minimal failing examples on regression and natural coverage of edge cases (long names, separator-adjacent chars, mixed casing). Target ≥1,000 generated URIs across all kinds (Hypothesis `@settings(max_examples=...)`).
- **D-13:** **Single property test asserts BOTH injectivity AND round-trip:** for any generated URI, (a) `encode_slug(uri)` produces a unique slug across a sampled batch, and (b) `decode_slug(encode_slug(uri)) == uri`. Combined into one test for cohesion.

### Vault scaffolding

- **D-14:** **`init_vault.py`'s `FIXED_VAULT_DIRS` adds `"entities"`.** Behavior on a partially-bootstrapped vault: idempotent (`Path.mkdir(exist_ok=True)`).
- **D-15:** **`wiki/entities/_index.md` is created at bootstrap as a sentinel-comment placeholder** (single line: `<!-- generated by graph-wiki-agent scan; see ../index.md for the canonical listing -->`). No structural content. The real entity index lives at `wiki/index.md` (Phase 44 generator). `_index.md` exists only so the directory is non-empty under git and so Obsidian surfaces the folder.

### Templates (per-kind, 7 files)

- **D-16:** **Narrative-region marker = explicit `## Narrative` H2 section.** No HTML-comment sentinels (departure from v1.7 `layout_io.py` precedent — chosen for cleaner rendered output). Phase 45's LLM scanner targets the region under `## Narrative` and stops at the next H2. Phase 43's `merge_frontmatter` writes ONLY frontmatter; it never touches body content. The H2 contract is documented as a hard convention in `entity_writer.py`'s module docstring — humans must not rename the heading.
- **D-17:** **Template body shape = H1 + `## Narrative` placeholder + canonical section list per kind.** Each template carries:
  1. YAML frontmatter with the scanner-owned keys populated as placeholders (`uri: <pkg-uri>`, `kind: package`, `domains: []`, etc.)
  2. H1 title (placeholder, e.g. `<Package Name>`)
  3. `## Narrative` followed by `_(scanner will populate on next scan)_`
  4. Per-kind canonical sections below (human-authored — scanner does NOT touch). Mirrors the structure of existing `dependency.md` and `package-family.md` templates.
  
  Canonical sections per kind (initial draft — Phase 42 finalizes during template authoring):
  - **entity-package.md:** `## Key patterns`, `## Gotchas`, `## Related`
  - **entity-domain.md:** `## Why this domain exists`, `## Contained packages`, `## Decisions`
  - **entity-test-suite.md:** `## Coverage notes`, `## Gotchas`
  - **entity-repository.md:** `## Overview`, `## Layout`
  - **entity-dependency.md:** `## Why we depend on this`, `## Gotchas / workarounds`
  - **entity-plugin.md:** `## What it is`, `## How we use it`
  - **entity-package-family.md:** `## What this family covers`, `## Gotchas`
- **D-18:** **All 7 templates declare `kind:` in frontmatter** at template-author time, with the underscore-form value (`kind: test_suite`, `kind: package_family`, etc.). This is the runtime fingerprint Phase 43 uses to pick the right template.

### Folded Todos

None — the one candidate (`2026-05-26-fix-scanner-treats-import-root-as-subpackage.md`, score 0.2) is about scanner package-import-root vs sub-package handling, not URI/template work. Reviewed but not folded — see deferred section.

### Claude's Discretion

- Exact docstring wording on `entity_writer.py` and the URI builders.
- Hypothesis strategy alphabet (whether to allow Unicode in fragments — defaulting to ASCII alphanumeric + `-` + `.` + `_` per real-world package names; can expand if a failing case emerges).
- Whether `entity_writer.py`'s module docstring uses example URIs from `agent-research` itself (recommended — readers can verify against the real graph).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Milestone direction & locked decisions
- `.planning/PROJECT.md` — Core value, v1.8 disposable-vault policy, project constraints
- `.planning/REQUIREMENTS.md` §URI — URI-01..URI-06 (Phase 42's six requirements)
- `.planning/ROADMAP.md` — Phase 42 goal + 5 success criteria (slug encoder property test, round-trip, 7 templates, FIXED_VAULT_DIRS update, frozenset constants)
- `.planning/STATE.md` — Key decisions section (D1 lock to `__` separator, D2 lock to frozenset, hard-delete-with-log policy, active pitfall guards)

### Research baseline (v1.8 synthesis)
- `.planning/research/SUMMARY.md` — Executive summary; phase ordering rationale; D1/D2 gap analysis
- `.planning/research/ARCHITECTURE.md` §Component Boundaries, §New Files Map (`entity_writer.py`), §Relation Frontmatter, §Anti-Patterns (1, 2, 3, 4)
- `.planning/research/FEATURES.md` §Key Design Decisions D1, D2, D4 — flat-list whitelist baseline (broadened to ARCHITECTURE.md union per D-07)
- `.planning/research/PITFALLS.md` Pitfall 1 (URI slug collisions — directly addressed by D-01..D-05); Pitfall 2 (frontmatter key collision — addressed by D-06..D-09); Pitfall 9 (concurrent scan race — relevant to Phase 43, not 42, but lock-file constant lives here later)
- `.planning/notes/wiki-entity-restructure-design.md` — Entity boundary policy (admitted kinds), edges-as-frontmatter contract

### Existing code (must be read by planner/researcher)
- `packages/graph-io/src/graph_io/uri.py` — Existing URI builders; new builders (package_family_uri, plugin_uri, dependency_uri) added here in Phase 42
- `packages/graph-io/src/graph_io/queries.py` §`_VALID_KINDS` — Source-of-truth for kind names; v1.8 ADMITTED_KINDS aligns to this (underscore form)
- `packages/wiki-io/src/wiki_io/init_vault.py` — `FIXED_VAULT_DIRS` constant (Phase 42 adds `"entities"`)
- `packages/wiki-io/src/wiki_io/assets/page-templates/` — Existing template directory; 7 new `entity-*.md` files land here
- `packages/wiki-io/src/wiki_io/assets/page-templates/package-family.md` — Reference layout for single-file template body shape (D-17 follows this pattern)
- `packages/wiki-io/src/wiki_io/layout_io.py` — Existing v1.7 sentinel pattern (REJECTED for entity templates per D-16 — entity templates use H2 convention instead; documented as deliberate departure)

### Ecosystem & process
- `CLAUDE.md` §1 (uv workspace), §2 (langchain-core scope), §8 (pytest stack — adding Hypothesis per D-11)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`graph_io/uri.py` URI builders:** Already provide `pkg_uri`, `domain_uri`, `test_suite_uri`, `repo_uri`, `entry_point_uri`, `subpkg_uri`, `file_uri`, `RepoContext`. Phase 42 extends with three new builders following the same `def <kind>_uri(...) -> str: return f"<kind>:..."` pattern.
- **`graph_io/queries.py::_VALID_KINDS`:** Existing frozenset of graph-side kinds. v1.8 `ADMITTED_KINDS` is a curated subset/extension with underscore form, matching this constant's casing.
- **`wiki_io/init_vault.py::FIXED_VAULT_DIRS`:** Existing list of bootstrap dirs (`concepts`, `adrs`, `architecture`, etc.). Adding `"entities"` is a one-line change with no schema implications.
- **`wiki_io/assets/page-templates/package-family.md` and `dependency.md`:** Existing single-file templates with frontmatter + H1 + per-kind H2 sections. D-17's template body shape mirrors these.

### Established Patterns
- **Single-line type annotations on URI builders** (`def pkg_uri(ctx: RepoContext, name: str) -> str: ...`) — new builders match this style.
- **`from __future__ import annotations` at the top of every graph-io module** — preserved in the URI-builder additions.
- **`@dataclass(frozen=True)` for value-object context (RepoContext)** — not needed for the three new builders since they don't take org/repo, just name (+ ecosystem for dependency).
- **CLAUDE.md test stack: pytest + pytest-asyncio + syrupy.** Hypothesis is a clean addition — no conflict with the existing async/snapshot patterns. Property tests are sync.
- **CLAUDE.md package layout:** `packages/<name>/src/<name>/`; tests live in `packages/<name>/tests/`. Phase 42 adds `packages/wiki-io/src/wiki_io/entity_writer.py` + `packages/wiki-io/tests/test_entity_writer.py`.

### Integration Points
- **`entity_writer.py` is the central artifact** — Phase 42 creates the scaffolded module; Phases 43–45 expand it. Downstream agents (`scan.py`, `index_generator.py`, `link_rewriter.py`) all import constants from here.
- **`init_vault.py` is the only existing module modified in Phase 42** (FIXED_VAULT_DIRS extended, _index.md sentinel write added). All other code is new.
- **`graph_io/uri.py` is the only graph-io module modified in Phase 42** (three new builder functions appended). Mechanical addition; existing tests untouched.

</code_context>

<specifics>
## Specific Ideas

- **Slug invariant statement embedded in `entity_writer.py` module docstring** (so future readers don't need to chase the CONTEXT.md): "Slug encoding is `s.replace(':', '__').replace('/', '__')`. The kind segment uses single-underscore (`test_suite`); the path separator uses double-underscore (`__`). Injectivity holds because no admitted kind contains `__`. Round-trip via `decode_slug` requires splitting on `__` and the first segment matching `ADMITTED_KINDS`."
- **Three new URI builders use minimal signatures:** `package_family_uri(name)`, `plugin_uri(name)`, `dependency_uri(ecosystem, name)`. No `RepoContext` parameter — these kinds are concept-level (not repo-scoped) and the URI shape is intentionally simpler.
- **Hypothesis `@settings(max_examples=500, deadline=None)`** on the property test — 500 examples × 2+ kinds per test = ≥1000 URIs total. `deadline=None` because slug encoding is fast but Hypothesis' default deadline can be flaky in CI.
- **Test file naming:** `packages/wiki-io/tests/test_entity_writer.py` for the slug + whitelist tests; `packages/graph-io/tests/test_uri.py` (existing file, if present) extended for the three new builders.

</specifics>

<deferred>
## Deferred Ideas

- **`merge_frontmatter()` implementation and tests** — Phase 43. Phase 42 only locks the keyset; the merge function uses it.
- **`scan.lock` file logic** — Phase 43 (entity writer phase). The lock-file constant could live in `entity_writer.py` but the acquisition logic is part of `write_entities()`.
- **Per-kind whitelist validation** — Phase 43 may choose to enforce "kind=package only writes package-relevant keys" at runtime. Phase 42's flat frozenset is the gate; Phase 43 owns the finer-grained policy if needed.
- **LLM narrative prompt design** — Phase 45 (scanner integration). Phase 42's `## Narrative` H2 contract is the boundary; the prompt that drives the LLM lives downstream.
- **Migration of existing entity-like data from old `wiki/packages/*` etc.** — Phase 46 (cutover commit). Phase 42 only creates the new lane.
- **Template body section finalization for kinds I haven't touched extensively** — section lists in D-17 are an initial draft; Phase 42 implementer may tune them during template authoring.

### Reviewed Todos (not folded)
- **`.planning/todos/pending/2026-05-26-fix-scanner-treats-import-root-as-subpackage.md` (score 0.2)** — Bug fix for scanner package-import-root vs sub-package handling. Not URI/template work; doesn't intersect Phase 42 scope. Belongs to a graph-io scanner bug-fix phase (possibly v1.9, or fold into Phase 45 if it surfaces during scanner-integration work).

</deferred>

---

*Phase: 42-URI Slug Scheme + Per-Kind Templates*
*Context gathered: 2026-05-26*
