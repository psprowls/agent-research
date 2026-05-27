# Feature Research

**Domain:** Graph-grounded agent integration — wiring an existing code-graph store (graph-io) into an existing AWS Bedrock wiki-maintenance agent (graph-wiki-agent)
**Researched:** 2026-05-26
**Confidence:** HIGH (all findings derived from direct codebase inspection + first-principles analysis; no external sources required for this type of integration work)
**Milestone:** v1.7 graph-io Integration & Wiki Hygiene

---

## Feature Landscape

### Table Stakes (Users Expect These)

These are the integration features that v1.7 exists to deliver. Missing them means graph-io remains a parallel artifact that nothing consumes.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Librarian grounding tools (@tool callables over graph-io) | v1.6 built graph-io explicitly so v1.7 could wire it in; librarian currently guesses identity by name — graph provides stable URIs | MEDIUM | 5-8 tool functions wrapping `queries.py`: `find_symbol`, `list_packages`, `describe_package`, `what_tests`, `describe_domain`, `describe_repo`. Return shape must be LLM-friendly strings, not raw dataclasses. |
| Scanner consumes graph-io (URI-keyed pages) | Current scanner keys pages by package name (`unscope(pkg["name"])`); graph-io provides stable `pkg_uri` so renames don't create ghost pages | MEDIUM | Scanner reads `queries.list_packages()` + `queries.describe_package()` to determine the canonical page slug from URI rather than inferred from directory structure. Fallback path (graph not initialized) must still work. |
| Ingestor consumes graph-io (graph as manifest of what exists) | Ingestor currently reconstructs existence from filesystem; graph-io is the authoritative manifest of what packages, domains, entry points, and test suites exist | MEDIUM | See tradeoff section below — "graph as manifest" vs "graph as advisory hints." v1.7 verdict: graph as advisory manifest (preferred) with FS as fallback when graph not initialized. |
| `graph-wiki-agent graph` subcommand (`build`, `describe`, `query`) | Operators need a CLI entry point to build/inspect the graph without switching to `cg`; the agent CLI should surface the most common graph operations | SMALL | Three verbs only. `build` = `cg update --full` wrapper with cost-tracking preamble. `describe` = `cg describe-repo` + `cg describe-domain` routing. `query` = `cg find` + `cg describe-package` routing. NOT a mirror of all 25 `cg` subcommands. |
| `cg find` positional argument parsing (ergonomics fix) | `cg find --kind file --name foo.py` requires both flags; `cg find foo.py` (positional name) currently works but agent `@tool` callers always use keyword arguments so need `--name` flag | SMALL | Current `add_arguments` in `q_find.py` takes `name` as positional-only. Add `--name` as an optional named alias that maps to the same destination. Backward-compatible: `cg find foo.py` still works. |

### Differentiators (Competitive Advantage)

These features specifically address the project's core value proposition: lower-cost Bedrock-backed wiki maintenance that is *better grounded* than the current Claude Code plugin because it has structured code-graph access.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| LLM grounding via URI identity (not string matching) | Librarian resolves `pkg:org/repo/graph-wiki-agent` rather than guessing from context; eliminates hallucinated package names | MEDIUM | The key differentiator over the upstream lattice-wiki plugin is that the plugin has no code graph at all; graph-io + URI identity is a genuine capability uplift |
| Graph-as-manifest ingestor (authoritative what-exists list) | Ingestor no longer re-derives what pages must exist from filesystem heuristics; it reads the graph's canonical node list and diffs against the vault | MEDIUM | Makes ingestor's "what needs a page" decision deterministic and auditable |
| Cost-tracked `graph build` (Bedrock token usage on graph ops) | `graph-wiki-agent graph build` emits a trace record so graph update costs appear alongside wiki maintenance costs in `graph-wiki-agent trace` | SMALL | Wraps `cg update --full` but adds Bedrock CountTokens estimation pre-flight and a JSONL trace record post-completion |
| Hygiene burn-down unblocks scanner/template work | The 10 deferred quick tasks fix broken wikilinks, missing stub indexes, and file-map format — these defects would be re-introduced by any graph-io integration that touches the same templates | SMALL | Must land before or concurrent with scanner/ingestor integration to avoid merge conflicts |

### Anti-Features (Explicitly Out of Scope for v1.7)

| Feature | Why Requested | Why Out of Scope | Alternative |
|---------|---------------|-----------------|-------------|
| Mirror all 25 `cg` subcommands in `graph-wiki-agent graph` | Completeness; users already know `cg` CLI | Creates a redundant CLI surface with 2x maintenance burden; `cg` already exposes all 25 subcommands — the agent CLI should add agent-awareness (cost tracking, Bedrock pre-flight), not raw duplication | Use `cg` directly for low-level graph inspection; `graph-wiki-agent graph` surfaces only the 3 agent-workflow-relevant verbs |
| Full URI-keyed wiki rendering (flat-by-ID / by-domain / by-repo views) | Natural follow-on to having URIs | Its own milestone (v1.8); the rendering redesign is a multi-phase project that touches every wiki page template | Deferred to v1.8 |
| Scanner pipeline restructure (9-stage per ONTOLOGY-SPEC §9) | Clean architecture; makes domain-overlay re-runs cheap | Not required until domain-overlay re-runs become a real operational need; explicitly deferred in PROJECT.md | Deferred to v1.7 only if it becomes an integration blocker (it won't) |
| Graph-io schema extensions / new node types | Schema v2 has URI identity; v1.6 landed the full ontology | Scope creep — v1.7 is the consumer of v1.6's schema | Any schema gaps become v1.8 items |
| Nested subagents (graph subagent calling wiki subagent) | Might improve quality for multi-hop graph+wiki queries | Adds debugging complexity for unproven quality gain | Single-agent graph tool calls within the librarian are sufficient for v1.7 |
| Plugin changes beyond `kxi` doc fix | The `plugins/graph-wiki/` plugin runs on Claude Code inference; touching it risks breaking working workflows | Plugin is explicitly out of scope per PROJECT.md | Only the `kxi` docs-only fix touches `plugins/`; all other hygiene tasks target `packages/wiki-io` and `packages/workspace-io` |
| Wiki redesign, page-naming overhaul, flat-by-URI view | v1.8 territory | Out of v1.7 scope per PROJECT.md explicit statement | v1.8 milestone |

---

## Key Tradeoffs (Inline Analysis for Requirements Step)

### Ingestor: Graph-as-Authoritative-Manifest vs Graph-as-Advisory-Hints

Both patterns ship in production systems. The tradeoff:

**Graph as authoritative manifest ("what pages MUST exist")**
- The ingestor reads `queries.list_packages()`, `queries.list_domains()`, etc., producing a canonical list of entities that require wiki pages.
- It diffs this list against the vault filesystem to decide create/update/delete.
- Consequence: if graph-io is not initialized (`NOT_INITIALIZED` exit 4), ingest fails or degrades to FS-only mode.
- Suitable for v1.7 because: graph-io is already built and populated; the graph IS the truth about what packages exist (via `cg update`); the current FS-reconstruction approach in the ingestor is error-prone for monorepos with non-standard layouts.
- **Verdict for v1.7: use graph as authoritative manifest with graceful degradation when `NOT_INITIALIZED`.**

**Graph as advisory hints**
- The ingestor reconstructs existence from filesystem as today, but checks the graph for enrichment (URIs, domain membership, test suite counts).
- Consequence: more resilient to uninitialized graph, but misses the architectural benefit of URI-keyed identity.
- Better suited to scenarios where the graph cannot be assumed to be current (e.g., CI pipelines without a `cg update` step).
- **Not recommended for v1.7** because it leaves path-keyed identity in place, defeating the URI migration goal.

**The right approach:** authoritative manifest with a documented pre-condition (`cg update` must have been run). The `ingest` command should emit a clear error (not a silent fallback) when the graph is not initialized, encouraging users to run `cg update` first.

### Scanner: Graph as "What Changed" Hint vs Full Replacement of FS Walk

Current scanner: FS walk → discover packages → diff against vault → fan-out.
Proposed (v1.7): scanner reads graph for URI-keyed canonical package identity, then diffs against vault using URIs as the identity key (not package names).

The scanner still needs to walk the FS for actual file content (to build the stub prompt). The graph's contribution is:
1. Canonical URI per package → vault page slug derived from URI, not inferred from directory name.
2. Role flags per file (`is_test`, `is_config`, etc.) → scanner can skip test files without heuristics.
3. Domain membership → scanner can route pages to the right container directory (packages/agents/plugins/domains).

**Conclusion:** scanner does NOT replace FS walk with graph query — it still reads files. But it uses graph for identity (URI → slug) and metadata (role flags, domain). The "scanner re-reads the world but uses graph for what changed since last scan" framing is CORRECT for the file-content side; it is INCORRECT for the identity side — the graph is authoritative for URIs and domain membership, not just a "change detection" hint.

### `graph-wiki-agent graph` Subcommand: Curated vs Mirrored

The curated approach (3 verbs: `build`, `describe`, `query`) is correct for v1.7:
- `cg` already surfaces all 25 subcommands; the agent CLI adds agent-awareness (cost tracking, Bedrock pre-flight) not raw query capability.
- Typer subcommand overhead is real: each `cg` subcommand has its own argument surface and output format; mirroring all 25 would require maintaining parity with `graph-io/cli/` indefinitely.
- The three proposed verbs map to the three operator workflows: `build` (update the graph), `describe` (inspect an entity), `query` (find symbols).
- `describe` routes to the right `cg` subcommand based on the entity kind provided via named flags (`--package`, `--domain`, `--repo`, `--suite`). This is Typer-native shape — one `describe` verb with optional named flags, not 6 separate subcommands.
- The `ingest` sub-app in the existing `cli.py` is the style model: `ingest_app = typer.Typer(...)` + `app.add_typer(ingest_app, name="ingest")`.

### `cg find` Parser: CLI Convention Analysis

Existing shape: `cg find <name> [--kind KIND]` — positional name, optional kind filter.

The ergonomics issue: agent `@tool` callers always use keyword arguments (`name="foo.py"`, `kind="file"`); the positional-only `name` argument requires callers to know the positional order.

Conventions from production CLIs:
- `kubectl get pods --field-selector=name=foo` — long-form key=value filter
- `gh issue list --label bug --assignee me` — separate named flags per filter dimension
- `fd --type f --name foo.py` — named flags throughout
- `rg --type py foo` — single positional query + named filters

**Recommendation:** Add `--name` as an optional named flag aliased to the same argparse `dest` as the positional. This preserves backward compatibility (`cg find foo.py` still works) while allowing `cg find --name foo.py --kind file` from tools that always use keyword style. This is the `fd` / `gh` convention. Do NOT redesign to `find X --where name=Y` — that's a new query DSL, disproportionate to the problem.

---

## Hygiene Burn-Down: Theme Clustering and Ordering

The 10 deferred quick tasks + 2 bootstrap todos cluster into 3 themes:

### Theme A: Wiki Templates (must land before scanner integration)

These fix defects in `packages/wiki-io/` templates and scanning output. They conflict with or are undone by scanner changes if not landed first.

| Task ID | Name | Complexity | Ordering Constraint |
|---------|------|------------|---------------------|
| `hfr` | Patch scanner wikilink emission — add `wiki/` prefix to emitted wikilinks in package/domain overview templates | SMALL | Must precede scanner integration; must precede `i26` (same file) |
| `i26` | Add `{{CONTAINER_DIR}}` template variable — fix hardcoded `packages/` container in package overview template | SMALL | Depends on `hfr` (both touch `package/overview.md`) |
| `he3` | Revise file-map format — H2 + markdown tables instead of H3-H6 heading+bullet sections | SMALL | Independent of `hfr`/`i26` but touches same file; batch with template group |
| `i35` | Add `testing.md` subpage — new testing sub-page template for app/package/plugin | SMALL | Independent; touches `scan_monorepo.py` emitter |
| `iws` | Rename overview pages — emit `overview.md` not `<slug>/<slug>.md` | SMALL | Must precede scanner integration; changes `wiki_relative_path` routing in `scan_monorepo.py` |
| `gc0` | Four lint-driven fixes: repo-directory workspace config, path-qualified wikilinks, schema-file exclusion from lint, null tokens on unsupported model | SMALL | Independent; touches `workspace-io` and `wiki-io` |

**Ordering within Theme A:** `hfr` must land before `i26`. `iws` must land before scanner integration. All other Theme A tasks can run in parallel.

### Theme B: Bootstrap / Workspace (prerequisite-free, can run parallel to Theme A)

| Task ID | Name | Complexity | Ordering Constraint |
|---------|------|------------|---------------------|
| `mfm` | Self-healing uv re-exec — add `_uv_reexec.py` shim to 6 plugin scripts | SMALL | Fully independent; touches `plugins/graph-wiki/scripts/` only |
| `lj3` | workspace-io tolerates missing `plugins` key in sparse `.graph-wiki.yaml` | SMALL | Independent; 1-line fix + test in `workspace-io/init.py` |
| Bootstrap interactive flag | Add `--non-interactive` flag to `graph-wiki-agent bootstrap` | SMALL | Touches `agents/graph-wiki-agent/commands/init.py`; independent |
| Bootstrap stub category index files | `init_wiki` creates stub `index.md` in concepts/sources/adrs/architecture | SMALL | **Check overlap with `hfr` Task 2 before implementing separately** — `hfr` PLAN already includes this as Task 2 |

**Note:** The "bootstrap stub category index files" bootstrap todo overlaps with `hfr` Task 2 (which adds stub index creation to `init_vault.py`). If `hfr` is executed before this todo, the todo is already complete.

### Theme C: Test Infrastructure / Docs (fully independent)

| Task ID | Name | Complexity | Ordering Constraint |
|---------|------|------------|---------------------|
| `ans` | Strip ANSI from Typer `--help` in unit tests — pass `NO_COLOR=1, TERM=dumb, COLUMNS=200` to subprocess calls | SMALL | Fully independent; 3 test files |
| `kxi` | Fix graph-wiki plugin docs — update invocations to `uv run --project` in plugin SKILL.md and agent docs | SMALL | Touches `plugins/graph-wiki/` docs only; independent |

---

## Feature Dependencies

```
[Theme A: Wiki Templates]
    hfr (wikilink prefix)
        └──precedes──> i26 (CONTAINER_DIR var, same file)
    iws (overview.md rename)
        └──must precede──> Scanner Integration
    he3, i35, gc0
        └──independent, batch with Theme A

[Theme B: Bootstrap]
    mfm, lj3, interactive-flag, stub-indexes
        └──fully independent of Theme A

[Theme C: Test/Docs]
    ans, kxi
        └──fully independent

[Hygiene Phase] (Themes A + B + C, batched)
    └──must precede──> [Scanner Integration Phase]
                           └──must precede──> [Ingestor Integration Phase]
                                                  └──enables──> [Librarian Grounding Tools]
                                                                (grounding works better after
                                                                 scanner has URI-keyed pages,
                                                                 but tool callables can land
                                                                 in any phase)

[graph-wiki-agent graph subcommand]
    └──depends on──> graph-io store existing (cg update pre-run)
    └──independent of scanner/ingestor integration order

[cg find parser fix]
    └──independent of all agent integration work
    └──can land in any phase; do early to unblock @tool callers
```

### Dependency Notes

- **Hygiene (iws + hfr) must precede Scanner Integration:** `iws` changes the vault page slug routing in `scan_monorepo.py` (overview.md vs slug.md); `hfr` fixes template wikilink prefixes. Landing these after scanner integration would mean URI-keyed scanner outputs point to paths that don't match the new naming convention.
- **Scanner Integration must precede Ingestor Integration (for URI consistency):** Once the scanner uses URI-keyed slugs, the ingestor must also use URI-keyed slugs for its diff to be meaningful.
- **Librarian Grounding Tools are independent of scan/ingest integration:** The librarian `@tool` callables call `graph_io.queries` directly; they do not depend on vault pages being URI-keyed. They can land in the same phase as scanner integration or in its own phase.
- **`cg find` parser fix can land in any phase:** It is a 5-line change with no dependencies; land it early to unblock `@tool` callers that always use keyword-style invocation.

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| `cg find` parser ergonomics | MEDIUM | LOW (5-line change) | P1 — do first, unblocks tool callers |
| Hygiene burn-down (all 3 themes) | HIGH — clears 10 pre-existing defects | LOW — complete PLANs exist; mostly 1-3 file edits | P1 — must precede integration |
| Librarian grounding tools | HIGH — direct quality improvement | MEDIUM — ~150 LOC wrappers + tests | P1 |
| Scanner consumes graph-io | HIGH — URI identity goal | MEDIUM — scan_monorepo.py routing changes | P1 |
| Ingestor consumes graph-io | HIGH — graph-as-manifest makes ingest deterministic | MEDIUM — ingest command logic changes | P1 |
| `graph-wiki-agent graph` subcommand | MEDIUM — convenience; `cg` already works | SMALL — Typer sub-app, pattern already in cli.py | P2 (stretch) |

---

## MVP Definition for v1.7

### Must Ship

- [ ] **Hygiene Phase** — all 10 quick tasks + 2 bootstrap todos applied; zero pre-existing ANSI test failures; zero broken template wikilinks from hfr/i26/iws categories
- [ ] **Librarian grounding tools** — 5+ `@tool` callables wrapping `graph_io.queries`; librarian system prompt updated to describe available tools
- [ ] **Scanner URI-keyed pages** — `run_scan` derives vault_page_rel from graph URI; fallback to path-keyed logic when graph not initialized
- [ ] **Ingestor graph-io manifest** — `run_ingest_source` checks graph for canonical entity existence; clear error on `NOT_INITIALIZED`
- [ ] **`cg find` parser** — `--name` flag added; both `cg find foo` and `cg find --name foo --kind file` work

### Stretch (v1.7 if time permits)

- [ ] **`graph-wiki-agent graph` subcommand** — `build`, `describe`, `query` verbs with Typer sub-app; cost-tracked trace record for `graph build`

### Deferred (v1.8+)

- [ ] URI-keyed wiki redesign (flat-by-ID / by-domain / by-repo views)
- [ ] Scanner 9-stage pipeline restructure (ONTOLOGY-SPEC §9)
- [ ] Cross-repo domain scope (ONTOLOGY-SPEC §11 open questions)

---

## Sources

- Codebase inspection: `packages/graph-io/src/graph_io/queries.py` — full query API surface confirmed (find, callers, callees, imports, describe_package, describe_path, describe_repository, describe_domain, list_* functions, cross_cutting_packages, domain_references, domain_depends_on)
- Codebase inspection: `packages/graph-io/src/graph_io/cli/q_find.py` — confirmed positional-only `name` arg + `--kind` flag; ergonomics issue is real
- Codebase inspection: `agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py` — confirmed path-keyed page routing via `vault_page_rel = pkg.get("wiki_relative_path", f"packages/{pkg_name}/{pkg_name}.md")`
- Codebase inspection: `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/librarian.py` — confirmed no `@tool` callables wired today; librarian is a per-page extraction agent without structured queries
- Codebase inspection: `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py` — Typer app structure; `ingest_app = typer.Typer(...)` + `app.add_typer` is the pattern for `graph` sub-app
- Planning artifacts: All 10 quick task PLANs in `.planning/quick/260521-*/` and `.planning/quick/260523-*/` — confirmed PLANs exist and tasks are well-specified; clustering confirmed from file_modified lists
- Project context: `.planning/PROJECT.md` — v1.7 target features, explicit deferrals to v1.8, bootstrap todos listed
- Project context: `.planning/MILESTONES.md` — v1.6 shipped graph-io with no agent consumers; v1.7 is the integration milestone

---
*Feature research for: graph-io Integration & Wiki Hygiene (v1.7)*
*Researched: 2026-05-26*
