# Index Repository Grouping — Design

**Date:** 2026-06-12
**Status:** Approved
**Scope:** `packages/wiki-io/src/wiki_io/index_generator.py` and its tests; `IndexWriteResult` consumers.

## Problem

`wiki/index.md` currently renders entities in two top-level sections: `## Domains`
(entities with exactly one qualifying domain) and `## By Kind` (the zero/multi-domain
fallback, with flat `### Apps` / `### Packages` / `### Agent Plugins` groups). The
`## By Kind` name is opaque, the flat kind groups add a navigation layer that carries
no information the headings couldn't, and nothing in the structure anticipates a
workspace whose graph spans multiple repositories.

## Decision summary

Replace `## Domains` + `## By Kind` with one `## Repository: <name>` section per
repository node. Domains nest inside their repository; every entity renders as a
kind-prefixed heading. The flat kind groups are removed.

- **D-R1 — Repo sections own everything.** Each repository node renders one
  `## Repository: <repo-node-name>` section (alphabetical by repo name). All
  package/app/agent_plugin entities render inside their repo's section.
- **D-R2 — Domains nest inside the repo.** Top-level domains render as
  `### Domain: <X>` inside their repository section; sub-domains recurse one
  heading level deeper (`#### Sub-Domain: <Y>`, …). Domain repo membership comes
  from the domain's own `domain:{org}/{repo}/{name}` URI.
- **D-R3 — Single-placement rule (D-04) survives unchanged.** Exactly one
  qualifying domain → that domain's block; zero or multiple → directly under the
  repo header. The evaluation logic in `_compute_qualifying_domains` is untouched.
- **D-R4 — Headings everywhere.** Every entity is a kind-prefixed heading one
  level below its container: `### Package: graph-io` directly under the repo,
  `#### Package: graph-io` inside a `### Domain:` block. The body is the existing
  shape: `summary — [[entities/<stem>|open page]]` line plus the
  `_render_pkg_nested` sub-lists (Test Suites / Dependencies / Internal
  dependencies — untouched).
- **D-R5 — Singular kind labels.** `App:`, `Package:`, `Agent Plugin:`
  (matching the `agent_plugin` kind name).
- **D-R6 — Kind-major ordering.** Within any container (direct-under-repo or a
  domain block): apps first, then packages, then agent plugins; alphabetical by
  URI within each kind. Preserves today's `BY_KIND_ORDER` semantics.
- **D-R7 — Repo membership via URI parsing.** A helper parses the
  `{org}/{repo}` segment from entity URIs (`pkg:`, `app:`, `agent_plugin:`,
  `test_suite:`, `domain:` all share the shape, locked since Phase 28). This is
  the only derivation that covers agent plugins, which have no graph edges by
  design. `physically_contains` edges are NOT consulted.
- **D-R8 — `IndexWriteResult` field rename.** `by_kind_count` → `direct_count`
  (entities rendered directly under a repo header); new `repo_count` field;
  `domain_count` keeps its meaning. Clean break per the no-migrations
  convention; all consumers updated in the same change.

## Rendered structure

Section order replaces D-03's `## Domains` → `## By Kind` slot; curated lanes
(Architecture/ADRs/Concepts/Sources/Guidance/Work) are unchanged and follow after.

```markdown
# Index — <topic>

_Auto-generated YYYY-MM-DD • N entities • M curated pages_

## Repository: agent-research

### Domain: graph                  <!-- only when domains exist -->

#### Package: graph-io

SQLite code-graph store — [[entities/pkg_graph-io|open page]]
  - Test Suites
    - [[entities/unit_tests_graph-io|graph-io-unit-tests]] — …
  - Dependencies
    - …
  - Internal dependencies
    - …

#### Sub-Domain: storage           <!-- recursion, when present -->

##### Package: …

### App: graph-wiki-cli            <!-- zero/multi-domain: direct under repo -->

Focused gw Typer CLI — [[entities/app_graph-wiki-cli|open page]]
  - …

### Package: wiki-io
…

### Agent Plugin: graph-wiki
…

## Repository: other-repo          <!-- when a second repo exists -->
…

## ADRs                            <!-- curated lanes unchanged -->
…
```

Removed: the `## Domains — <repo>` header suffix, the `## By Kind` header, and
the flat `### Apps` / `### Packages` / `### Agent Plugins` groups.

## Code changes

All in `wiki_io/index_generator.py` (plus tests). No graph-io or schema changes.

1. **URI repo parsing helper** — extract `(org, repo)` from a URI of shape
   `<scheme>:{org}/{repo}/...`. Returns `None` for `dependency:`/`builtin:`
   (ecosystem-scoped) and malformed URIs.
2. **`_place_entities`** — return shape becomes per-repo:
   `dict[repo_name, (domain_buckets, direct_entities)]` plus the same global
   `name_to_entity`. Placement rule per entity is unchanged (D-R3).
3. **`_render_repository_section`** — replaces `_render_domains` and
   `_render_by_kind`. Per repo: nested domain blocks first (alphabetical,
   reusing `_list_subdomains` / `_is_top_level_domain`, filtered to the repo's
   domains by URI), then direct entities kind-major.
4. **`_render_entity_heading`** — one shared entity renderer:
   `{heading-prefix} {KindLabel}: {name}`, summary + `open page` link line,
   then `_render_pkg_nested` (unchanged).
5. **`IndexWriteResult`** — field rename per D-R8; update `run_scan` / CLI /
   MCP summary consumers.

`sub_for_pkg` (the global dep/suite-under-package grouping) remains built once
over all placed entities and shared across all repo sections, so nesting
behavior is identical to today.

## Edge cases

- **Unparseable entity URI, exactly one repository node:** entity falls into
  that repo's section (defensive; matches current single-repo reality).
- **Unparseable entity URI, zero or multiple repository nodes:** render-time
  error — all-or-nothing (D-19) stays; no silent drops.
- **Zero repository nodes:** no entity sections render; curated lanes still do.
- **Empty repo section / empty domain block:** omitted entirely (D-08).
- **Unchanged invariants:** full-rewrite ownership (D-02), write-if-changed +
  atomic replace (D-16), all-or-nothing (D-19), lock-agnostic (D-20), entity
  links via `short_filename` + collision set (Phase 53).

## Testing

- **Rewrite existing assertions** in `packages/wiki-io/tests/test_index_generator.py`
  that reference `## By Kind`, flat kind groups, `#### <name>` headings, or
  `by_kind_count`.
- **New tests:**
  - Single repo, no domains: one `## Repository:` section, kind-major direct
    entities, kind-prefixed `###` headings (today's real-data shape).
  - Single repo with domains: single-domain entity → `#### Package:` inside
    `### Domain:`; zero/multi-domain entity → direct `###`; sub-domain depth.
  - Multi-repo: two repository nodes, entities split by URI → two alphabetical
    self-contained `## Repository:` sections.
  - Edge cases: empty repo omitted; unparseable URI with one repo falls in;
    zero repos → curated lanes only.
- **Ripple:** grep `by_kind_count` / `domain_count` consumers; run
  `uv run --package wiki-io pytest`, then `graph-wiki-core` and
  `graph-wiki-cli` suites (`-m "not integration"`).
- **End-to-end:** rescan the real workspace and diff `wiki/index.md` against
  the approved mock-up.

## Out of scope

- The duplicated dependency bullets visible in the current real index (e.g.
  `deepeval` listed twice under claude-code-evals) — pre-existing nesting-data
  bug, to be filed separately.
- Multi-repo *scanning* (the graph currently only ever contains one repository
  node); this design only makes the renderer ready for it.
