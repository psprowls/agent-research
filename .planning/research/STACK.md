# Stack Research

**Domain:** Wiki Entity Restructure + LLM Domain Inference (v1.8 additions to existing app)
**Researched:** 2026-05-26
**Confidence:** HIGH

---

## Scope of This Document

This file covers ONLY stack additions and changes for v1.8 features. The
existing validated stack (uv workspace, langchain-aws, langchain-core,
subagent-runtime, model-adapter, graph-io, wiki-io, workspace-io, mcp, typer,
python-frontmatter, bm25s, deepeval, pytest, pytest-asyncio, syrupy) is
unchanged and is not re-researched here.

---

## Stack Verdict: No New Dependencies Required

All seven v1.8 features can be built on the existing dependency closure. The
analysis below explains why each apparent dependency need is already covered.

---

## Feature-by-Feature Analysis

### 1. `/entities/` lane with per-kind templates

**What it needs:** Template rendering with per-kind frontmatter schemas;
read/write of `kind:` discriminator in frontmatter.

**Already covered:** `python-frontmatter` (in `wiki-io`) handles round-trip
YAML frontmatter with arbitrary keys including `kind:`. The existing
`scan_monorepo.py` and `update_index.py` pattern of writing frontmatter dicts
to `.md` files via `python-frontmatter` is the integration point. No new
library needed.

**What v1.8 adds in wiki-io:** New per-kind template strings (e.g.
`entity-package.template`) and a `render_entity_page(kind, attrs)` function
that fills in a template and returns a `frontmatter.Post`. This is a code
addition to `wiki-io`, not a new dependency.

---

### 2. URI-keyed entity pages

**What it needs:** Stable filename derivation from a URI string; URI-to-slug
normalization.

**Already covered:** `graph_io.uri` already exposes `pkg_uri()`, `domain_uri()`,
`repo_uri()`, etc. (verified in `packages/graph-io/src/graph_io/uri.py`).
Slug derivation is `uri.replace(":", "-").replace("/", "-")` — stdlib string
ops. `python-frontmatter` handles writing `uri:` as a frontmatter key.

**No new library needed.**

---

### 3. Scanner-populated relation frontmatter

**What it needs:** Query graph edges for a given entity URI, coerce results
into structured frontmatter dicts, write back to an existing `.md` with
frontmatter merge logic.

**Already covered:**
- `graph_io.queries` exposes `describe_package`, `describe_domain`,
  `describe_suite` etc. that return typed dataclasses covering the key
  relation fields.
- `graph_io.store.read_only_connect()` is the established pattern for
  opening the graph in scanner context.
- `python-frontmatter` supports round-trip frontmatter update via
  `post.metadata[key] = value` + `frontmatter.dumps(post)`.

**What v1.8 adds in wiki-io:** A `merge_relation_frontmatter(post, scanner_keys, new_values)` helper that applies scanner-owned key updates without touching human-authored keys. This is ~30 LOC of Python in `wiki-io`, not a new dependency.

---

### 4. Fully scanner-generated domain-first + by-kind index

**What it needs:** Graph queries for domains and their packages; sorting;
Markdown string rendering.

**Already covered:** `queries.list_domains()`, `queries.describe_domain()`,
`queries.list_packages()`, `queries.describe_package()` already exist in
`graph_io.queries`. The existing `update_index.py` pattern (pure string
concatenation → `index_path.write_text(...)`) is the right model for the new
scanner-generated index.

**What v1.8 replaces in wiki-io:** `update_index.py`'s `render_index()` is
replaced with a new `render_entity_index(conn)` function that queries the
graph directly instead of walking frontmatter. Still plain Python + stdlib
string ops.

---

### 5. Hard-delete reconciliation

**What it needs:** Diff between graph node URIs and existing entity page
filenames; `Path.unlink()` for deletions.

**Already covered:** `graph_io.queries.find(conn, kind="package")` enumerates
all package URIs. `pathlib.Path.unlink()` is stdlib. The existing
`compute_diff()` pattern in `scan_monorepo.py` is the model.

**No new library needed.**

---

### 6. One-shot inbound-link migration

**What it needs:** Regex-based wikilink rewriting across `/concepts/` and
`/adrs/` directories.

**Already covered:** `re` (stdlib) for `\[\[packages/foo/index\]\]` pattern
matching. `python-frontmatter` for round-trip page read/write. The existing
`scan_monorepo.py` `_safe_read_text()` / `path.write_text()` pattern.

**This is a one-shot migration script (~60 LOC in wiki-io), not a new dep.**

---

### 7. `cg domain-clusters` — import-graph clustering

**The core question:** Does implementing deterministic import-graph clustering
require adding `networkx`, `igraph`, or `scipy`?

**Answer: No. In-house adjacency-list clustering is the right call at this
scale.**

**Scale argument:**
- Typical monorepo for this project: 8-15 packages (agent-research itself).
  Evaluated against: a large monorepo at the high end has 50-200 packages.
- The import graph is already materialized as `pkg_imports: dict[pkg_key ->
  set[pkg_keys]]` in `derived_edges.py` via `scan_package_imports()`.
- Directed weakly-connected components on a 200-node adjacency dict runs in
  ~1ms using stdlib `collections.deque` BFS. There is no performance argument
  for a C library at this node count.

**Algorithm:** Undirected connected components on the package import graph
(treating imports as undirected edges). This produces "co-import clusters" —
packages that form a strongly coupled group in the import graph. Output: list
of sets, each set being a cluster candidate. Packages with zero imports to
other packages form singleton clusters (cross-cutting candidates).

**Implementation:** ~50 LOC in a new `graph_io/cluster.py` module. No external
library. BFS/union-find on the adjacency dict that `derived_edges.py` already
builds.

**Why not networkx:**
- `networkx` is ~3MB installed, adds a transitive numpy dependency for some
  algorithms, and introduces 10,000+ LOC of API surface for a 50-LOC BFS.
- The connected-components algorithm networkx uses for unweighted graphs is
  identical to what stdlib `collections.deque` implements; there is no
  algorithmic advantage at this scale.
- `networkx` would be justified only if: (a) weighted shortest-path across
  1,000+ nodes, (b) spectral clustering, or (c) community detection with
  modularity optimization (Louvain/Leiden). None of these are required here.

**Why not igraph:** C binding, heavier installation, same overkill argument
as networkx but worse on the "zero new deps" dimension.

**Cluster quality note:** For the `propose-domains` LLM consumption, cluster
candidates don't need to be optimal; they need to be deterministic and
explainable. Connected-component clustering on the import graph is the most
interpretable output an LLM can reason about ("these packages cluster because
they all import each other"). Fancier community detection would produce
non-deterministic or less interpretable groupings.

**New `cg domain-clusters` command pattern:** Follows the established
`graph_io/cli/q_*.py` module pattern exactly:
- `q_domain_clusters.py` with `add_arguments(parser)` and `run(args) -> int`
- Registered in `_SUBCOMMANDS` dict in `cli/main.py`
- Opens `read_only_connect(db)`, calls `cluster.find_clusters(conn, repo_root)`,
  prints results in `human` or `json` format

---

### 8. `graph-wiki-agent graph propose-domains`

**What it needs:** (a) Call `cg domain-clusters` to get cluster data; (b)
pass cluster data + graph context to an LLM via existing `make_llm(role)`;
(c) write `domains.proposed.yaml`.

**Already covered:**
- In-process `cg` dispatch pattern: `graph.py` in `graph-wiki-agent` already
  demonstrates `_capture_run(module, args)` for in-process cg invocation.
- `make_llm(role)` for the LLM call (orchestrator or a new `domain-proposer`
  role in `models.toml`).
- `pyyaml` (already a dep of `graph-io` transitively in-scope for
  `graph-wiki-agent`) for writing `domains.proposed.yaml` via
  `yaml.dump(proposals, stream, default_flow_style=False)`.
- `graph_io.queries` for graph context passed to the LLM prompt.

**No new library needed.**

---

## Confirmed: No New Dependencies

| Feature | New Library? | Covered By |
|---------|-------------|------------|
| Per-kind entity templates | No | `python-frontmatter` (wiki-io) |
| URI-keyed filenames | No | `graph_io.uri` (graph-io) |
| Relation frontmatter merge | No | `python-frontmatter` + new wiki-io helper |
| Graph-driven index | No | `graph_io.queries` + stdlib strings |
| Hard-delete reconciliation | No | `graph_io.queries` + `pathlib.Path.unlink()` |
| Inbound-link migration | No | `re` (stdlib) + `python-frontmatter` |
| `cg domain-clusters` | No | In-house 50-LOC BFS in `graph_io/cluster.py` |
| `domains.proposed.yaml` | No | `pyyaml` (already in graph-io deps) |
| LLM domain proposals | No | `make_llm(role)` + `graph_io.queries` |

---

## Existing Dependencies Touched by v1.8

These are existing libraries whose usage expands in v1.8, but no version
changes are needed:

| Library | Existing Version | v1.8 New Usage |
|---------|-----------------|----------------|
| `python-frontmatter` | >=1.1.0 | Relation frontmatter merge on entity pages |
| `pyyaml` | >=6.0 (via graph-io) | `domains.proposed.yaml` write in graph-wiki-agent |
| `graph_io.queries` | workspace | New `list_clusters()` query; expanded calls for entity page rendering |
| `graph_io.uri` | workspace | Slug derivation for entity filenames |
| `typer` | >=0.25.1 | New `graph propose-domains` subcommand in graph-wiki-agent |

---

## New Code Additions (No New Packages)

The v1.8 feature set is implemented by adding new modules to existing packages:

**`packages/graph-io/src/graph_io/`**

- `cluster.py` — `find_clusters(conn, repo_root) -> list[frozenset[str]]`. BFS
  over package import adjacency. ~50 LOC. No external deps.
- `cli/q_domain_clusters.py` — `cg domain-clusters` command module. Follows
  existing `q_list_domains.py` pattern. ~60 LOC.

**`packages/wiki-io/src/wiki_io/`**

- `entity_page.py` — Per-kind template rendering, frontmatter merge logic,
  URI-to-filename slug derivation. ~150 LOC.
- `entity_index.py` — Graph-driven domain-first + by-kind index generation.
  Replaces `update_index.py`'s `render_index()` for the entities lane. ~120 LOC.
- `entity_reconcile.py` — Hard-delete diff: graph URIs vs. vault filenames.
  ~60 LOC.
- `migrate_inbound_links.py` — One-shot wikilink rewrite script. ~60 LOC.

**`agents/graph-wiki-agent/src/graph_wiki_agent/commands/`**

- Extension to `graph.py` — `graph propose-domains` Typer subcommand. Invokes
  `cg domain-clusters` in-process, builds LLM prompt, writes
  `domains.proposed.yaml`. ~100 LOC.

---

## Integration Points with Existing Pipeline

**Scanner integration (Q4):** The relation-frontmatter population and entity
page write/delete runs as a new stage in the existing `run_scan` dispatch in
`graph-wiki-agent`. It runs after `cg update` completes (graph is fresh) and
before the LLM scanner subagents fan out. The stage uses
`graph_io.store.read_only_connect()` — the established pattern from
`graph_tools.py` — so no new connection management pattern is needed.

**Index generation:** The new `entity_index.py` writes `wiki/entities/index.md`
(new file). The existing `update_index.py` continues to manage
`wiki/index.md` and category sub-indexes for the curated lanes. The two
generators are independent; no modification to `update_index.py` is needed.

**`make_llm(role)` for propose-domains:** Uses the existing role-model tier
pattern. A new `domain-proposer` role entry in `models.toml` (or reuse of
`orchestrator` role) routes the LLM call through `_GuardedChatBedrockConverse`
without any model-adapter changes.

---

## What NOT to Add

| Avoid | Why | Already Covered By |
|-------|-----|-------------------|
| `networkx` | 3MB+ dep, overkill for 200-node BFS; no algorithmic benefit at this scale | In-house `cluster.py` (~50 LOC stdlib BFS) |
| `igraph-python` | C binding, even heavier; same overkill argument | In-house `cluster.py` |
| `scipy` for spectral clustering | Wrong algorithm class for import-graph clustering; requires numpy; non-deterministic results | In-house connected-components |
| `ruamel.yaml` | Round-trip comment-preserving YAML; unnecessary because `domains.proposed.yaml` is scanner-generated, not human-authored | `pyyaml` (already present) |
| `jinja2` / template engine | Overkill for 7 static entity templates; string `.format()` or f-strings are sufficient | stdlib string formatting |
| New YAML parsing library | `pyyaml` already handles `domains.yaml` parsing in `graph_io/domains.py` | `pyyaml>=6.0` |

---

## Version Compatibility

No version changes required. The existing stack constraint matrix (Python
≥3.11, `uv_build >=0.11.14,<0.12`, `langchain-aws >=1.4.7`, etc.) is
unchanged.

The `tomllib` import in `scan_monorepo.py` for parsing `pyproject.toml` is
Python 3.11 stdlib — no compatibility concern for the new cluster module.

---

## Sources

- Codebase: `packages/graph-io/src/graph_io/derived_edges.py` — confirmed that
  `pkg_imports` adjacency dict is already built at update time; BFS clustering
  reuses this structure.
- Codebase: `packages/graph-io/src/graph_io/import_scan.py` — confirmed
  `scan_package_imports()` API used by both `derived_edges` and the new
  `cluster.py`.
- Codebase: `packages/graph-io/pyproject.toml` — `pyyaml>=6.0` already a dep;
  no addition needed for `domains.proposed.yaml`.
- Codebase: `agents/graph-wiki-agent/src/graph_wiki_agent/commands/graph.py` —
  confirmed `_capture_run` in-process dispatch pattern for new `propose-domains`
  command.
- Codebase: `packages/wiki-io/src/wiki_io/scan_monorepo.py` and
  `update_index.py` — confirmed `python-frontmatter` + stdlib string rendering
  is sufficient for entity page writing and index generation.
- Codebase: `packages/graph-io/src/graph_io/cli/q_list_domains.py` — confirmed
  `cg` subcommand module pattern for new `q_domain_clusters.py`.
- Complexity analysis: BFS connected-components on 50-200 node undirected graph
  is O(V+E) ≈ O(200 + 200*5) = O(1200) operations — trivially fast without a
  graph library.

---

*Stack research for: Wiki Entity Restructure + LLM Domain Inference (v1.8)*
*Researched: 2026-05-26*
