# Feature Research — v1.6 graph-io Ontology CLI Surface

**Domain:** Code graph CLI — new node/edge types surfaced as user-facing queries
**Researched:** 2026-05-25
**Confidence:** HIGH (spec §10 is the authoritative source of truth; all features mapped directly to its example queries)

---

## Ontology Bucketing

All features are grouped by the seven ontology categories the milestone introduces. The §10 example queries are the canonical "what users want to ask" checklist; every query is mapped below.

---

## 1. Repository

### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| `cg describe-repo` | Repository is a first-class node; users need basic inspection | S | Show URI, URL, default branch, owner, package count. Read from `Repository` node attrs. |
| `cg status` extension: repo URI in output | `cg status` is already shipped; now that a `Repository` node exists, its URI should appear in status | S | Additive — append `repo_uri` field to existing status output. No breaking change. |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| `cg list-packages` (repo-scoped) | "What packages does this repo contain?" — now derivable from `physically_contains` edges from Repository | S | Currently `cg status` shows node_counts but not the package list. Expose as a lightweight list command. |

### §10 Mapping

None of the §10 example queries target Repository directly. The `Repository` node is load-bearing infrastructure for `TestSuite → Repository` tests edges and for multi-repo future scope, but no standalone CLI query was requested in the spec. `cg describe-repo` is an inference from "Repository is a first-class node" — it would be conspicuously absent.

---

## 2. Package + SubPackage

### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| `cg describe-package` — extend to show domains | Package is now a member of 0..N domains; this is the most common "what is this package?" question | S | Additive to existing output. Append `domains: [billing, auth]` or `domains: []` (cross-cutting). |
| `cg describe-package` — extend to show entry points | §10: "What can I run from this package?" and "What does this package export?" both start at the package | S | Append `entry_points: [{name, kind, source}]` block. Requires EntryPoint nodes (stage 2 of scanner). |
| `cg describe-package` — extend to show suites | "What tests cover this package?" starts at the package | S | Append `test_suites: [{name, kind}]` block — suite names only, not file lists. Deep traversal lives in `cg what-tests`. |
| `cg describe-path` — extend to show File role flags | `File` nodes now carry `is_test`, `is_executable`, `is_importable`, `is_config`, etc. | S | Additive to existing output. Append `role_flags: {is_test: false, is_executable: true, ...}` block. |

### SubPackage Notes

`SubPackage` nodes are Python-only and live inside the physical containment tree. No dedicated `cg describe-subpackage` command is needed in v1.6 — `cg describe-path` already handles file-level inspection, and `cg find <name> --kind subpackage` covers discovery. The subpackage layer is structural scaffolding that enriches existing commands rather than requiring new ones.

### §10 Mapping

- "Give me the production code surface of this package, excluding tests." → `cg describe-package <name>` already lists files; after v1.6 the `physically_contains` subtree excludes test files by construction. The command output changes (fewer files listed) but no new command is needed.

---

## 3. EntryPoint

### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| `cg list-entry-points <package>` | §10: "What can I run from this package?" and "What does this package export?" are explicit example queries | S | Filter by `kind: executable` or `kind: library` via `--kind` flag. Default shows both. Human output: name, kind, source, implementing file path. |
| `cg describe-package` extension (see §2) | Entry points surfaced at the package level | S | Already captured above; cross-listed here for clarity. |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| `cg find --kind entry-point` | Repo-wide search for all declared entry points | S | Extends existing `cg find` with the new node kind. Zero new code beyond registering the kind. |
| `cg list-scripts` | §10: "What scripts exist in this repo (declared or conventional)?" — union of `EntryPoint kind:executable` + `File is_executable:true` | M | Requires a two-source query: `EntryPoint` nodes and `File` nodes with `is_executable` flag. Returns name + path + source (declared vs. conventional). |

### §10 Mapping

- "What can I run from this package?" → `cg list-entry-points <package> --kind executable` (table stakes)
- "What does this package export?" → `cg list-entry-points <package> --kind library` (table stakes)
- "What scripts exist in this repo (declared or conventional)?" → `cg list-scripts` (differentiator — the union query)

---

## 4. TestSuite

### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| `cg list-suites` | Discovery: "what test suites exist in this repo?" Every user will need this after the schema shifts | S | List TestSuite nodes: name, kind, framework, parent (Package or Repository), targets. |
| `cg describe-suite <name>` | "What tests cover this package?" and "What integration tests touch the Billing domain?" require suite detail | M | Show: name, kind, framework, physically_contains files, `tests` edges (package/domain/repo targets). |
| `cg what-tests <package>` | §10: "What tests cover this package?" is an explicit example query | M | Traverse: `tests → Package` edges, collect suites. Also traverse `tests → Domain` for suites where the package's domain matches. Output: suite names + kinds + file counts. |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| `cg what-tests <domain>` (domain variant) | §10: "What integration tests touch the Billing domain?" — domain-level test coverage | M | Same traversal but anchor on Domain node. Output: suites with `tests → Domain(X)` + suites with multiple `tests → Package` where packages belong to the domain. Requires Domain nodes. |
| `cg what-tests <path>` (file variant) | Advisory file-level test coverage via `File → File` tests edges | L | Best-effort only (advisory per spec §4.3). Lower priority than suite-level. Mark output as advisory. |

### §10 Mapping

- "What tests cover this package?" → `cg what-tests <package>` (table stakes)
- "What integration tests touch the Billing domain?" → `cg what-tests <domain>` (differentiator variant of same command)
- "Give me the production code surface of this package, excluding tests." → structural consequence of re-parenting test files to suites; no new command, `cg describe-package` automatically excludes them

---

## 5. Domain

### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| `cg describe-domain <name>` | Domain is a first-class node; users need basic inspection | M | Show: URI, description, member packages (via `belongs_to_domain`), sub-domains (via `domain_contains_domain`), derived `references` edges, derived `depends_on` edges. |
| `cg list-domains` | Discovery: "what domains exist?" — prerequisite for all domain queries | S | List all Domain nodes with member package count and sub-domain count. |
| `cg domain-refs <name>` | §10: "What does the Billing domain depend on (outside of itself)?" | S | Read `references` edges from the Domain node. Output: package name, domain membership of that package, usage count. |
| `cg domain-deps <name>` | §10: "Does Billing depend on Auth?" | S | Read `depends_on` edges from the Domain node to other Domain nodes. |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| `cg cross-cutting` | §10: "Which utility packages are most widely used?" — packages with zero `belongs_to_domain` edges, ranked by incoming `references` count | M | Two-part query: find packages with no `belongs_to_domain` edges, then rank by count of distinct domains with `references → Package` edges. |
| `cg domain-tree` | Visualize nested domain hierarchy for orientation in large repos | M | Walk `domain_contains_domain` edges recursively, print as indented tree. Only useful when domains are nested; gracefully shows flat list when no nesting exists. |
| `cg domain-callers <name>` | §10: "What functions in the Auth domain call into the Billing domain?" | L | Requires join: `belongs_to_domain` (package → domain), `physically_contains` (transitively to function), `calls` (cross-domain). High implementation cost relative to query frequency. Flag as "needs deeper investigation" — recursive containment traversal. |

### §10 Mapping

- "What packages are in the Billing domain (including sub-domains)?" → `cg describe-domain billing` shows members + sub-domains; or `cg list-domains` then drill. No separate command needed beyond `describe-domain`.
- "What does the Billing domain depend on (outside of itself)?" → `cg domain-refs billing` (table stakes)
- "Does Billing depend on Auth?" → `cg domain-deps billing` — check if Auth appears in output (table stakes)
- "What functions in the Auth domain call into the Billing domain?" → `cg domain-callers` (differentiator, HIGH complexity — see note)
- "Which utility packages are most widely used?" → `cg cross-cutting` (differentiator)

---

## 6. Derived Edges (references, depends_on)

### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Derived edges computed on `cg update` | §4.5 specifies these as cached in DB (not recomputed on query) — users expect `cg domain-refs` to be fast | M | Re-run scanner stage 8 (derived edge computation) every time `cg update` runs. Store `references` and `depends_on` in the edges table with `attrs_json` carrying `usage_count`. |
| `cg update` reruns derived edges without full AST re-parse | Domain overlay (stage 7) and derived edges (stage 8) must be re-runnable cheaply | M | After `domains.yaml` edits, users should be able to run `cg update --domains-only` (or equivalent) to recompute without re-scanning AST. The spec identifies this as a key design goal (§9: "domain assignment can be re-run without re-parsing code"). |

### Anti-Features

| Feature | Why Problematic | Alternative |
|---------|-----------------|-------------|
| Recomputing `references`/`depends_on` on every query | Expensive cross-join at query time; defeats the purpose of a cached graph | Compute in `cg update` stage 8, cache in `edges` table, read at query time |
| Separate `cg recompute-domains` command | Creates a two-command workflow when `domains.yaml` changes; confusing for users | `cg update --domains-only` (or just `cg update` which is cheap if AST is unchanged) |

### §10 Mapping

Derived edges are the backing store for `cg domain-refs`, `cg domain-deps`, and `cg cross-cutting`. They have no direct CLI surface beyond those commands, but they must exist in the DB or those commands degrade to expensive live queries.

---

## 7. Brand Sweep (lattice → graph-wiki)

### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| `README.md` — "lattice-graph-core" → graph-wiki phrasing | README currently says "lattice-graph-core" and `~/.lattice/graph/code.db`; inconsistent with the rest of the rebranded repo | S | Rename package description, update path references to canonical graph-wiki path. |
| `cli/main.py` — argparse description "lattice code graph CLI" → "graph-wiki code graph CLI" | Visible in `cg --help` output | S | One-line change. |
| DB path references in docs/comments | `~/.lattice/graph/code.db` appears in README and possibly inline comments | S | Update to the canonical graph-wiki path wherever it appears. |
| Exit-code doc string in README | Already references lattice; align with graph-wiki | S | Part of the same README sweep. |

---

## Feature Dependencies

```
Schema v2 + URI identity
    └──required-by──> cg describe-repo
    └──required-by──> cg describe-domain
    └──required-by──> cg list-domains
    └──required-by──> cg domain-refs
    └──required-by──> cg domain-deps
    └──required-by──> cg cross-cutting
    └──required-by──> cg list-suites
    └──required-by──> cg describe-suite
    └──required-by──> cg what-tests
    └──required-by──> cg list-entry-points
    └──required-by──> cg list-scripts

Scanner stage 1-3 (structural nodes + EntryPoint + TestSuite)
    └──required-by──> cg list-entry-points
    └──required-by──> cg list-scripts
    └──required-by──> cg list-suites
    └──required-by──> cg describe-suite
    └──required-by──> cg what-tests (suite-level)
    └──required-by──> describe-package extension (entry points + suites)
    └──required-by──> describe-path extension (File role flags)

Scanner stage 7 (domain assignment / domains.yaml)
    └──required-by──> cg describe-domain
    └──required-by──> cg list-domains
    └──required-by──> cg domain-refs
    └──required-by──> cg domain-deps
    └──required-by──> cg cross-cutting
    └──required-by──> cg what-tests (domain variant)
    └──required-by──> cg domain-callers

Scanner stage 8 (derived edges: references, depends_on)
    └──required-by──> cg domain-refs  (reads references edges)
    └──required-by──> cg domain-deps  (reads depends_on edges)
    └──required-by──> cg cross-cutting (reads references edge counts)
    └──required-by──> cg domain-callers (joins calls + belongs_to_domain)

Domain nodes (stage 7)
    └──required-by──> cg what-tests --kind domain (differentiator)
    └──required-by──> cg domain-callers (differentiator)
    └──enhances──> cg describe-package (domain membership display)

TestSuite nodes (stage 3)
    └──required-by──> cg what-tests
    └──required-by──> cg list-suites
    └──required-by──> cg describe-suite

EntryPoint nodes (stage 2)
    └──required-by──> cg list-entry-points
    └──required-by──> cg list-scripts (declared half)

File role flags (stage 1)
    └──required-by──> cg list-scripts (is_executable conventional half)
    └──required-by──> describe-path extension
    └──required-by──> describe-package (test file exclusion from production surface)
```

### Dependency Notes

- `cg domain-callers` requires Domain nodes AND a recursive `physically_contains` traversal AND the `calls` edge graph. This is the most expensive query in the §10 set. Mark as "needs deep investigation" before implementation — may require a WITH RECURSIVE join that is non-trivial to write correctly.
- `cg what-tests <domain>` requires Domain nodes. Since Domain nodes depend on domains.yaml being configured, this command gracefully returns empty results when domains are unconfigured (not an error).
- All domain commands gracefully degrade: if `domains.yaml` is absent or empty, `cg list-domains` returns an empty list, `cg describe-domain` returns not-found. Zero-domain is acceptable per spec §4.4.
- `cg list-scripts` is the one command that joins across two node types (EntryPoint + File). Implementable as a UNION query; medium complexity.

---

## Anti-Features (Do Not Build in v1.6)

| Feature | Why Not v1.6 | What to Do Instead |
|---------|-------------|---------------------|
| Wiki render commands (`cg sync-wiki` extensions for new node types) | Wiki redesign is v1.7 scope; existing `sync-wiki` stays unchanged | Leave `ops_sync_wiki.py` as-is; the new node types are in the graph but not rendered to wiki pages yet |
| Agent integration helpers (`cg` as a grounding tool for `graph-wiki-agent`) | Agent integration is explicitly v1.7 scope; graph-io-only milestone | No MCP exposure, no `graph-wiki-agent graph` subcommand, no tool wrappers in v1.6 |
| `tagged_with` mechanism | Open question §11 item 2; explicitly deferred per spec | Do not add `tagged_with` edges or `cg tag` commands; use zero-domain as the cross-cutting signal |
| Cross-repo domain queries | Open question §11 item 3; single-repo is the v1.6 scope | Domain nodes are scoped to one repo; note as a v1.7+ extension point |
| `cg domain-callers` (Function-level cross-domain join) | Extremely high implementation complexity for a rarely-used query; recursive traversal of `physically_contains` + `calls` edges | Defer to v1.7; users can approximate with `cg callers` manually today |
| File-level `tests` edges in `cg what-tests` | Best-effort advisory per spec §4.3; high complexity for uncertain quality | Surface suite-level `tests` edges only in v1.6; file-level is v1.7+ |
| `cg domains-only` update flag (re-run only stages 7-8) | Valuable optimization but requires pipeline architecture (§9 decomposed stages) which is deferred to v1.7 | v1.6 runs stages 7-8 as part of the normal `cg update` full-rebuild; optimization deferred |
| Import-graph clustering or LLM-proposed domain groupings (spec §9 domain inference strategies 3+4) | v1.6 supports only explicit config + convention (strategies 1+2) | `domains.yaml` explicit config + top-level folder convention is sufficient for v1.6 |
| `cg domain-import-graph` or raw domain edge dump | Too raw; CLI consumers want the derived summary, not raw edge lists | `cg domain-refs` and `cg domain-deps` provide the right level of abstraction |

---

## §10 Example Query Coverage Matrix

Every example query from spec §10 mapped to a planned command, a deferral, or a "not yet."

| §10 Example Query | CLI Command | Status |
|-------------------|-------------|--------|
| "What packages are in the Billing domain (including sub-domains)?" | `cg describe-domain billing` (walks `domain_contains_domain` + `belongs_to_domain`) | v1.6 table stakes |
| "What does the Billing domain depend on (outside of itself)?" | `cg domain-refs billing` | v1.6 table stakes |
| "Does Billing depend on Auth?" | `cg domain-deps billing` (check Auth in output) | v1.6 table stakes |
| "What functions in the Auth domain call into the Billing domain?" | `cg domain-callers` | v1.7 — deferred (HIGH complexity, recursive join) |
| "Which utility packages are most widely used?" | `cg cross-cutting` | v1.6 differentiator |
| "What can I run from this package?" | `cg list-entry-points <pkg> --kind executable` | v1.6 table stakes |
| "What does this package export?" | `cg list-entry-points <pkg> --kind library` | v1.6 table stakes |
| "What scripts exist in this repo (declared or conventional)?" | `cg list-scripts` | v1.6 differentiator |
| "What tests cover this package?" | `cg what-tests <package>` | v1.6 table stakes |
| "What integration tests touch the Billing domain?" | `cg what-tests <domain>` (domain variant) | v1.6 differentiator (requires Domain nodes) |
| "Give me the production code surface of this package, excluding tests." | `cg describe-package <name>` (test files excluded by construction post-v1.6) | v1.6 — structural consequence, not a new command |

---

## Existing Command Changes

Commands that must change in v1.6 to reflect the new schema (additive only — no breaking changes).

| Command | Change | Breaking? |
|---------|--------|-----------|
| `cg describe-package <name>` | + domains list, + entry points list, + test suites list | No — new fields appended |
| `cg describe-path <path>` | + File role flags block | No — new field appended |
| `cg status` | + repo URI, updated node/edge kind lists in counts | No — new fields appended |
| `cg find --kind <X>` | Register new node kinds: `repository`, `subpackage`, `entry-point`, `test-suite`, `domain` | No — new valid values for existing flag |
| `cg update` | Run scanner stages 7-8 (domain assignment + derived edges) as part of existing update flow | No — internally extended |

---

## Domain Config: domains.yaml

**Location:** `<repo-root>/domains.yaml` — checked into version control alongside code. Single-repo scope in v1.6.

**Format (minimal):**
```yaml
domains:
  billing:
    description: "Payment processing and invoicing"
    packages:
      - billing-service
      - invoice-worker
    subdomains:
      - subscriptions

  auth:
    description: "Authentication and authorization"
    packages:
      - auth-service
      - token-lib

  subscriptions:
    parent: billing
    packages:
      - subscription-manager
```

**Who edits it:** Pat (or the developer). The file is manually curated. Convention-based inference (top-level named folders treated as domain candidates) bootstraps an initial assignment without requiring `domains.yaml` to exist. Empty domains (no `domains.yaml`) is acceptable — all packages show as zero-domain (cross-cutting). No error is raised.

**Bootstrap flow:** `cg update --full` runs stage 7 (domain assignment). If `domains.yaml` is absent, the convention-based inference runs (strategy 2 from spec §9). If the top-level folder has no named subfolders that look like domain candidates, all packages get zero `belongs_to_domain` edges. The user can then create `domains.yaml` and re-run `cg update` to populate domain membership.

**Multi-repo:** Deferred to v1.7+. In v1.6, `domains.yaml` is scoped to one repo root.

---

## Feature Prioritization Summary

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Schema v2 + URI identity | HIGH | HIGH | P1 — foundation for everything |
| `cg describe-package` extension (domains + entry points + suites) | HIGH | LOW | P1 — most-used existing command |
| `cg describe-path` extension (File role flags) | MEDIUM | LOW | P1 — low-cost, high clarity |
| `cg list-entry-points <package>` | HIGH | LOW | P1 — explicit §10 query |
| `cg list-suites` | HIGH | LOW | P1 — discovery primitive |
| `cg describe-suite <name>` | HIGH | MEDIUM | P1 — explicit §10 query |
| `cg what-tests <package>` | HIGH | MEDIUM | P1 — explicit §10 query |
| `cg list-domains` | HIGH | LOW | P1 — domain discovery primitive |
| `cg describe-domain <name>` | HIGH | MEDIUM | P1 — explicit §10 query |
| `cg domain-refs <name>` | HIGH | LOW | P1 — reads cached derived edges |
| `cg domain-deps <name>` | HIGH | LOW | P1 — reads cached derived edges |
| Derived edge computation in `cg update` | HIGH | MEDIUM | P1 — all domain queries depend on it |
| Brand sweep (README + CLI strings) | MEDIUM | LOW | P1 — cleanliness, brand gate compliance |
| `cg describe-repo` | MEDIUM | LOW | P2 — structural completeness |
| `cg list-packages` | MEDIUM | LOW | P2 — convenience |
| `cg list-scripts` | MEDIUM | MEDIUM | P2 — union query, useful but not blocking |
| `cg cross-cutting` | MEDIUM | MEDIUM | P2 — §10 query, requires derived edges |
| `cg what-tests <domain>` (domain variant) | MEDIUM | MEDIUM | P2 — requires Domain nodes first |
| `cg domain-tree` | LOW | MEDIUM | P3 — useful only for deeply nested domains |
| `cg domain-callers` | MEDIUM | HIGH | P3 (v1.7) — recursive join complexity |

---

## Sources

- `.planning/research/ONTOLOGY-SPEC.md` §10 "Example Queries Enabled" — canonical source of user query requirements
- `.planning/research/ONTOLOGY-SPEC.md` §4 "Edge Types" — backing store for each CLI command
- `.planning/research/ONTOLOGY-SPEC.md` §7 "Test Suite Layout and Detection" — TestSuite command design
- `.planning/research/ONTOLOGY-SPEC.md` §9 "Scanner Pipeline" — update flow and re-runnability design
- `.planning/research/ONTOLOGY-SPEC.md` §11 "Open Questions" — anti-feature justifications
- `.planning/PROJECT.md` "Current Milestone: v1.6" — explicit v1.7 deferral list
- `packages/graph-io/src/graph_io/cli/main.py` — existing subcommand registry (13 commands)
- `packages/graph-io/src/graph_io/queries.py` — existing query layer (find, callers, callees, imports, describe_package, describe_path, imported_by, exports, exported_by)
- `packages/graph-io/README.md` — brand sweep targets identified
- `packages/graph-io/src/graph_io/schema.py` — current SCHEMA_VERSION = 1, two-table structure

---
*Feature research for: graph-io v1.6 ontology CLI surface*
*Researched: 2026-05-25*
