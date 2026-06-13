# Index Repository Grouping Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use graph-wiki:subagent-driven-development (recommended) or graph-wiki:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `## Domains` + `## By Kind` in `wiki/index.md` with one `## Repository: <name>` section per repository node, domains nested inside, every entity as a kind-prefixed heading.

**Architecture:** All changes live in `packages/wiki-io/src/wiki_io/index_generator.py` and its test file. A new URI parser derives `{org}/{repo}` repo membership (D-R7); `_place_entities` reshapes to a per-repo dict; `_render_repository_section` + `_render_entity_heading` replace `_render_domains`/`_render_by_kind`; `IndexWriteResult` renames `by_kind_count` → `direct_count` and adds `repo_count` (D-R8, clean break — no migrations). The single external consumer (`scan.py:2340`) reads only `.changed`/`.bytes_written`, so no core/CLI/MCP code changes — just suite verification.

**Tech Stack:** Python 3.11, pytest, uv workspace. Spec: `docs/superpowers/specs/2026-06-12-index-repository-grouping-design.md`.

**Reference — locked URI shapes** (`packages/graph-io/src/graph_io/uri.py`, Phase 28):

```
repo:{org}/{repo}                                          (exactly 2 segments)
pkg: app: agent_plugin: domain: test_suite:  {org}/{repo}/{...}   (>= 3 segments)
dependency:{ecosystem}/{name}   builtin:{lang}/{module}    (repo-less by design)
```

**Reference — target rendered shape** (from the spec):

```markdown
## Repository: agent-research

### Domain: graph                  <!-- only when domains exist -->

#### Package: graph-io

SQLite code-graph store — [[entities/pkg_graph-io|open page]]
  - Test Suites
    - …

#### Sub-Domain: storage           <!-- recursion -->

##### Package: …

### App: graph-wiki-cli            <!-- zero/multi-domain: direct under repo -->
### Package: wiki-io
### Agent Plugin: graph-wiki
```

Heading levels: repo `##`, domain `###`, sub-domain `####` (one deeper per level), entity = one level below its container. Singular kind labels: `App:`, `Package:`, `Agent Plugin:`.

---

### Task 1: `_parse_repo_key` URI parsing helper

**Goal:** Add the pure helper that extracts the `{org}/{repo}` key from any graph URI (D-R7), with tests.

**Files:**
- Modify: `packages/wiki-io/src/wiki_io/index_generator.py` (add constant + function after the module-constants block, around line 125)
- Test: `packages/wiki-io/tests/test_index_generator.py` (new `TestParseRepoKey` class)

**Acceptance Criteria:**
- [ ] `_parse_repo_key("pkg:local/agent-research/pkg-a")` → `"local/agent-research"` (same for `app:`, `agent_plugin:`, `domain:`, `test_suite:` with ≥3 segments)
- [ ] `_parse_repo_key("repo:local/agent-research")` → `"local/agent-research"` (repo scheme: exactly 2 segments)
- [ ] `_parse_repo_key("dependency:pypi/boto3")` and `_parse_repo_key("builtin:python/os")` → `None` (repo-less schemes)
- [ ] Malformed → `None`: `""`, `"no-colon"`, `"pkg:pkg-a"` (1 segment), `"pkg:agent-research/pkg-a"` (2 segments, non-repo scheme), `"repo:agent-research"` (1 segment), `"repo:a/b/c"` (3 segments)
- [ ] Existing wiki-io suite still green

**Verify:** `uv run --package wiki-io pytest tests/test_index_generator.py -v` → all pass

**Steps:**

- [ ] **Step 1: Write the failing tests**

Add to `packages/wiki-io/tests/test_index_generator.py` after `TestIndexWriteResult`, and add `_parse_repo_key` to the `from wiki_io.index_generator import (...)` block at the top:

```python
class TestParseRepoKey:
    """D-R7 — extract '{org}/{repo}' from the Phase-28 URI shapes."""

    @pytest.mark.parametrize(
        "uri",
        [
            "pkg:local/agent-research/pkg-a",
            "app:local/agent-research/myapp",
            "agent_plugin:local/agent-research/graph-wiki",
            "domain:local/agent-research/core",
            "test_suite:local/agent-research/unit",
            "test_suite:local/agent-research/packages/alpha/tests",
        ],
    )
    def test_repo_scoped_schemes(self, uri):
        assert _parse_repo_key(uri) == "local/agent-research"

    def test_repo_scheme_exactly_two_segments(self):
        assert _parse_repo_key("repo:local/agent-research") == "local/agent-research"

    @pytest.mark.parametrize("uri", ["dependency:pypi/boto3", "builtin:python/os"])
    def test_repo_less_schemes_return_none(self, uri):
        assert _parse_repo_key(uri) is None

    @pytest.mark.parametrize(
        "uri",
        [
            "",
            "no-colon",
            "pkg:",
            "pkg:pkg-a",                  # 1 segment — no org/repo
            "pkg:agent-research/pkg-a",   # 2 segments — ambiguous, malformed
            "repo:agent-research",        # repo scheme needs exactly 2
            "repo:a/b/c",                 # repo scheme needs exactly 2
        ],
    )
    def test_malformed_return_none(self, uri):
        assert _parse_repo_key(uri) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --package wiki-io pytest tests/test_index_generator.py::TestParseRepoKey -v`
Expected: FAIL with `ImportError: cannot import name '_parse_repo_key'`

- [ ] **Step 3: Implement the helper**

In `packages/wiki-io/src/wiki_io/index_generator.py`, after the `FRONTMATTER_RE` line (end of the module-constants block):

```python
# 2026-06-12 repository grouping D-R7: schemes that are ecosystem-scoped
# rather than repo-scoped — they never carry an {org}/{repo} segment.
_REPO_LESS_SCHEMES: frozenset[str] = frozenset({"dependency", "builtin"})


def _parse_repo_key(uri: str) -> str | None:
    """Extract the '{org}/{repo}' segment from a graph URI (D-R7).

    URI shapes locked since Phase 28 (`graph_io.uri`):

      repo:{org}/{repo}                            -> exactly 2 segments
      pkg:/app:/agent_plugin:/domain:/test_suite:  -> {org}/{repo}/{...}, >= 3 segments
      dependency:{ecosystem}/{name}, builtin:{lang}/{module} -> repo-less

    Returns None for repo-less schemes and malformed URIs (no scheme,
    too few segments).
    """
    scheme, sep, rest = uri.partition(":")
    if not sep or not scheme or not rest:
        return None
    if scheme in _REPO_LESS_SCHEMES:
        return None
    parts = [p for p in rest.split("/") if p]
    if scheme == "repo":
        return "/".join(parts) if len(parts) == 2 else None
    if len(parts) >= 3:
        return f"{parts[0]}/{parts[1]}"
    return None
```

Add `"_parse_repo_key"` to `__all__` (alphabetical position, after `"_parse_frontmatter"`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --package wiki-io pytest tests/test_index_generator.py -v`
Expected: PASS (whole file — nothing else touched)

- [ ] **Step 5: Commit**

```bash
git add packages/wiki-io/src/wiki_io/index_generator.py packages/wiki-io/tests/test_index_generator.py
git commit -m "feat(wiki-io): add _parse_repo_key URI repo parsing helper (D-R7)"
```

---

### Task 2: Per-repo `_place_entities`

**Goal:** Reshape `_place_entities` to return `(per_repo, name_to_entity, domain_repo)` with repo resolution + edge-case errors, keeping the OLD render output byte-identical via a temporary flatten shim in `_render`.

**Files:**
- Modify: `packages/wiki-io/src/wiki_io/index_generator.py` (`_place_entities` ~line 348, `_render` ~line 876, imports ~line 47)
- Test: `packages/wiki-io/tests/test_index_generator.py` (`_place` helper, `TestPlacement`, repo-node additions to render fixtures)

**Design decisions locked here:**
- Repo resolution per entity: parse URI → match a repository node's own `repo:{org}/{repo}` URI. Unresolvable (repo-less scheme, malformed, or unmatched key): exactly one repository node → that repo (defensive, spec edge case 1); zero or multiple → `ValueError` (spec edge case 2, all-or-nothing D-19).
- Entity with exactly one qualifying domain lands in that domain's bucket **in the domain's repo** (D-R2 — domain URI decides); zero/multi-domain entities land in `direct` **in the entity's repo** (D-R7). D-04 evaluation (`_compute_qualifying_domains`) untouched (D-R3).
- `domain_repo` (domain name → repo name) is a third return value — `_render_repository_section` needs it in Task 3 to filter top-level domains per repo (including ancestors of bucketed sub-domains).
- Test fixtures that render entities but have no repository node now raise — they gain a repository node in this task.

**Acceptance Criteria:**
- [ ] `_place_entities` returns `per_repo: dict[repo_name, (domain_buckets, direct)]` + global `name_to_entity` + `domain_repo`
- [ ] Single-placement rule unchanged per entity; per-repo sorting identical to today (buckets by URI; direct by `(_PLACEABLE_KINDS index, uri)`)
- [ ] Multi-repo graphs split entities by URI; unparseable URI + 1 repo falls in; unparseable + 0 or ≥2 repos raises `ValueError`; empty graph → `{}`
- [ ] Rendered index output is byte-identical to before this task (shim) — all render/integration tests pass unmodified except added repository nodes
- [ ] Full wiki-io suite green

**Verify:** `uv run --package wiki-io pytest` → all pass

**Steps:**

- [ ] **Step 1: Rewrite the `_place` test helper and `TestPlacement`**

Replace the `_place` helper (top of test file) with:

```python
def _place(conn):
    """Call _place_entities with a no-pages wiki_root + empty collision_set.

    Repository grouping (2026-06-12): _place_entities returns
    (per_repo, name_to_entity, domain_repo). These placement tests only care
    about the per-repo buckets; with no entity pages on disk all summaries
    degrade to "".
    """
    per_repo, _name_to_entity, _domain_repo = _place_entities(conn, Path("/nonexistent-wiki-root"), frozenset())
    return per_repo
```

Replace the entire `TestPlacement` class with (note the module-level `REPO_NODE` just above the class):

```python
REPO_NODE = ("repository", "agent-research", {"uri": "repo:local/agent-research"})


class TestPlacement:
    def test_single_domain_goes_to_section(self, make_index_fixture_graph):
        spec = {
            "nodes": [
                REPO_NODE,
                ("domain", "core", {"uri": "domain:local/agent-research/core"}),
                ("package", "pkg-a", {"uri": "pkg:local/agent-research/pkg-a"}),
            ],
            "edges": [
                ("package", "pkg-a", "domain", "core", "belongs_to_domain", {}),
            ],
        }
        conn = make_index_fixture_graph(spec)
        per_repo = _place(conn)
        assert list(per_repo) == ["agent-research"]
        buckets, direct = per_repo["agent-research"]
        assert "core" in buckets
        assert len(buckets["core"]) == 1
        assert buckets["core"][0].kind == "package"
        assert buckets["core"][0].name == "pkg-a"
        assert direct == []

    def test_zero_domain_goes_direct(self, make_index_fixture_graph):
        spec = {
            "nodes": [
                REPO_NODE,
                ("package", "pkg-cross", {"uri": "pkg:local/agent-research/pkg-cross"}),
            ],
            "edges": [],
        }
        conn = make_index_fixture_graph(spec)
        buckets, direct = _place(conn)["agent-research"]
        assert buckets == {}
        assert len(direct) == 1
        assert direct[0].kind == "package"
        assert direct[0].name == "pkg-cross"

    def test_multi_domain_goes_direct(self, make_index_fixture_graph):
        spec = {
            "nodes": [
                REPO_NODE,
                ("domain", "d1", {"uri": "domain:local/agent-research/d1"}),
                ("domain", "d2", {"uri": "domain:local/agent-research/d2"}),
                ("package", "pkg-1", {"uri": "pkg:local/agent-research/pkg-1"}),
                ("package", "pkg-2", {"uri": "pkg:local/agent-research/pkg-2"}),
                ("test_suite", "suite", {"uri": "test_suite:local/agent-research/suite"}),
            ],
            "edges": [
                ("package", "pkg-1", "domain", "d1", "belongs_to_domain", {}),
                ("package", "pkg-2", "domain", "d2", "belongs_to_domain", {}),
                ("test_suite", "suite", "package", "pkg-1", "tests", {}),
                ("test_suite", "suite", "package", "pkg-2", "tests", {}),
            ],
        }
        conn = make_index_fixture_graph(spec)
        buckets, direct = _place(conn)["agent-research"]
        suite_direct = [e for e in direct if e.name == "suite"]
        assert len(suite_direct) == 1
        for d in buckets.values():
            assert not any(e.name == "suite" for e in d)

    def test_agent_plugin_always_direct(self, make_index_fixture_graph):
        # agent_plugin URI parses to "o/r" which matches no repo node —
        # exercises the defensive single-repo fallback too.
        spec = {
            "nodes": [
                REPO_NODE,
                ("agent_plugin", "graph-wiki", {"uri": "agent_plugin:o/r/graph-wiki", "ecosystem": "claude-code"}),
            ],
            "edges": [],
        }
        conn = make_index_fixture_graph(spec)
        buckets, direct = _place(conn)["agent-research"]
        assert any(e.kind == "agent_plugin" and e.name == "graph-wiki" for e in direct)
        assert buckets == {}

    def test_direct_sort_order(self, make_index_fixture_graph):
        spec = {
            "nodes": [
                REPO_NODE,
                # insertion order intentionally not matching _PLACEABLE_KINDS
                ("agent_plugin", "graph-wiki", {"uri": "agent_plugin:o/r/graph-wiki", "ecosystem": "claude-code"}),
                ("package", "pkg-cross", {"uri": "pkg:local/agent-research/pkg-cross"}),
                ("dependency", "boto3", {"uri": "dependency:pypi/boto3", "ecosystem": "pypi"}),
            ],
            "edges": [],
        }
        conn = make_index_fixture_graph(spec)
        _buckets, direct = _place(conn)["agent-research"]
        kinds = [e.kind for e in direct if e.name in ("graph-wiki", "pkg-cross", "boto3")]
        assert kinds == ["package", "dependency", "agent_plugin"]

    def test_intra_domain_parent_pkgs_populated(self, make_index_fixture_graph):
        spec = {
            "nodes": [
                REPO_NODE,
                ("domain", "core", {"uri": "domain:local/agent-research/core"}),
                ("package", "pkg-a", {"uri": "pkg:local/agent-research/pkg-a"}),
                ("package", "pkg-b", {"uri": "pkg:local/agent-research/pkg-b"}),
                ("dependency", "boto3", {"uri": "dependency:pypi/boto3", "ecosystem": "pypi"}),
            ],
            "edges": [
                ("package", "pkg-a", "domain", "core", "belongs_to_domain", {}),
                ("package", "pkg-b", "domain", "core", "belongs_to_domain", {}),
                ("package", "pkg-a", "dependency", "boto3", "used_by", {}),
                ("package", "pkg-b", "dependency", "boto3", "used_by", {}),
            ],
        }
        conn = make_index_fixture_graph(spec)
        buckets, _direct = _place(conn)["agent-research"]
        deps = [e for e in buckets["core"] if e.kind == "dependency"]
        assert len(deps) == 1
        assert deps[0].parent_pkg_names == ("pkg-a", "pkg-b")

    # --- 2026-06-12 repository grouping: repo resolution ---

    def test_multi_repo_split_by_uri(self, make_index_fixture_graph):
        spec = {
            "nodes": [
                ("repository", "repo-alpha", {"uri": "repo:local/repo-alpha"}),
                ("repository", "repo-beta", {"uri": "repo:local/repo-beta"}),
                ("package", "pkg-one", {"uri": "pkg:local/repo-alpha/pkg-one"}),
                ("package", "pkg-two", {"uri": "pkg:local/repo-beta/pkg-two"}),
            ],
            "edges": [],
        }
        conn = make_index_fixture_graph(spec)
        per_repo = _place(conn)
        assert sorted(per_repo) == ["repo-alpha", "repo-beta"]
        _, direct_alpha = per_repo["repo-alpha"]
        _, direct_beta = per_repo["repo-beta"]
        assert [e.name for e in direct_alpha] == ["pkg-one"]
        assert [e.name for e in direct_beta] == ["pkg-two"]

    def test_domain_repo_membership_from_domain_uri(self, make_index_fixture_graph):
        # D-R2: the DOMAIN's own URI decides where its block lives — an
        # entity placed in that domain follows the domain, not its own URI.
        spec = {
            "nodes": [
                ("repository", "repo-alpha", {"uri": "repo:local/repo-alpha"}),
                ("repository", "repo-beta", {"uri": "repo:local/repo-beta"}),
                ("domain", "core", {"uri": "domain:local/repo-beta/core"}),
                ("package", "pkg-one", {"uri": "pkg:local/repo-alpha/pkg-one"}),
            ],
            "edges": [
                ("package", "pkg-one", "domain", "core", "belongs_to_domain", {}),
            ],
        }
        conn = make_index_fixture_graph(spec)
        per_repo = _place(conn)
        buckets_beta, _ = per_repo["repo-beta"]
        assert [e.name for e in buckets_beta["core"]] == ["pkg-one"]
        assert "repo-alpha" not in per_repo

    def test_unparseable_uri_with_single_repo_falls_in(self, make_index_fixture_graph):
        spec = {
            "nodes": [
                REPO_NODE,
                ("package", "pkg-x", {"uri": "pkg:pkg-x"}),  # 1 segment — malformed
            ],
            "edges": [],
        }
        conn = make_index_fixture_graph(spec)
        _buckets, direct = _place(conn)["agent-research"]
        assert [e.name for e in direct] == ["pkg-x"]

    def test_unparseable_uri_with_multi_repo_raises(self, make_index_fixture_graph):
        spec = {
            "nodes": [
                ("repository", "repo-alpha", {"uri": "repo:local/repo-alpha"}),
                ("repository", "repo-beta", {"uri": "repo:local/repo-beta"}),
                ("package", "pkg-x", {"uri": "pkg:pkg-x"}),
            ],
            "edges": [],
        }
        conn = make_index_fixture_graph(spec)
        with pytest.raises(ValueError, match="cannot resolve repository"):
            _place(conn)

    def test_zero_repos_with_entity_raises(self, make_index_fixture_graph):
        spec = {
            "nodes": [
                ("package", "pkg-x", {"uri": "pkg:local/agent-research/pkg-x"}),
            ],
            "edges": [],
        }
        conn = make_index_fixture_graph(spec)
        with pytest.raises(ValueError, match="cannot resolve repository"):
            _place(conn)

    def test_zero_repos_zero_entities_empty(self, make_index_fixture_graph):
        conn = make_index_fixture_graph({"nodes": [], "edges": []})
        assert _place(conn) == {}
```

- [ ] **Step 2: Add repository nodes to render fixtures that lack one**

These fixtures render entities but have no repository node — they would now raise. Add the node line `("repository", "agent-research", {"uri": "repo:agent-research"}),` as the FIRST entry of `spec["nodes"]` in each of:

- `TestRenderDomainTree.test_empty_domain_omitted`
- `TestRenderByKind.test_by_kind_section_order`
- `TestRenderByKind.test_by_kind_entity_summary_renders_before_open_page_link`
- `TestRenderByKind.test_empty_by_kind_omitted`
- `TestRenderByKind.test_test_suites_subheading`
- `test_app_zero_domain_renders_in_by_kind_apps_first`

(The deliberately unparseable `repo:agent-research` URI matches the rest of the file and exercises the single-repo defensive count fallback. All other assertions in these tests stay untouched in this task.)

- [ ] **Step 3: Run tests to verify the new placement tests fail**

Run: `uv run --package wiki-io pytest tests/test_index_generator.py::TestPlacement -v`
Expected: FAIL — `_place_entities` still returns a 3-tuple of `(buckets, by_kind, name_to_entity)`, so unpacking/`per_repo["agent-research"]` breaks.

- [ ] **Step 4: Rewrite `_place_entities`**

Add `list_repositories` to the `from graph_io.queries import (...)` block (alphabetical: after `list_packages`). Replace `_place_entities` entirely with:

```python
def _place_entities(
    conn: sqlite3.Connection,
    wiki_root: Path,
    collision_set: frozenset[str],
) -> tuple[
    dict[str, tuple[dict[str, list[PlacedEntity]], list[PlacedEntity]]],
    dict[str, PlacedEntity],
    dict[str, str],
]:
    """Walk all placeable kinds. Return (per_repo, name_to_entity, domain_repo).

    2026-06-12 repository grouping (D-R1/D-R3/D-R7):
      per_repo[repo_node_name] = (domain_buckets, direct_entities)

    The D-04 single-placement rule is unchanged per entity (D-R3):
      qualifying_count == 1 -> domain_buckets[that_domain] (in the DOMAIN's repo, D-R2)
      qualifying_count != 1 -> direct_entities             (in the ENTITY's repo, D-R7)

    Repo resolution: parse `{org}/{repo}` from the URI (`_parse_repo_key`)
    and match a repository node's own `repo:` URI. Unresolvable URIs
    (repo-less schemes, malformed, or no matching repository node) fall
    into the single repository when exactly ONE repository node exists
    (defensive — matches the single-repo reality); with zero or multiple
    repository nodes they raise ValueError (all-or-nothing D-19, no silent
    drops).

    `domain_repo` maps every domain name to its repo (from the domain's own
    URI, D-R2) so `_render_repository_section` can filter top-level domains
    per repo. `name_to_entity` keeps its global meaning (D-09/D-11).

    Iterates `_PLACEABLE_KINDS` (NOT the heading-kind order) so test_suites
    and dependencies are discovered and can nest (D-01 crux).
    """
    repos = list_repositories(conn)
    repo_key_to_name: dict[str, str] = {}
    for r in repos:
        key = _parse_repo_key(r.attrs.get("uri") or "")
        if key:
            repo_key_to_name[key] = r.name

    def _repo_for(uri: str, *, kind: str, name: str) -> str:
        key = _parse_repo_key(uri)
        if key and key in repo_key_to_name:
            return repo_key_to_name[key]
        if len(repos) == 1:
            return repos[0].name
        raise ValueError(
            f"cannot resolve repository for {kind} {name!r} (uri={uri!r}): "
            f"{len(repos)} repository nodes and no URI match"
        )

    domain_repo: dict[str, str] = {}
    for d in list_domains(conn):
        domain_repo[d.name] = _repo_for(d.attrs.get("uri") or "", kind="domain", name=d.name)

    per_repo: dict[str, tuple[dict[str, list[PlacedEntity]], list[PlacedEntity]]] = {}
    name_to_entity: dict[str, PlacedEntity] = {}

    def _buckets_for(repo_name: str) -> tuple[dict[str, list[PlacedEntity]], list[PlacedEntity]]:
        if repo_name not in per_repo:
            per_repo[repo_name] = ({}, [])
        return per_repo[repo_name]

    kind_to_list_fn = {
        "app": list_apps,
        "package": list_packages,
        "test_suite": list_test_suites,
        "dependency": list_dependencies,
        "agent_plugin": list_agent_plugins,
    }
    for kind in _PLACEABLE_KINDS:
        list_fn = kind_to_list_fn[kind]
        for node in list_fn(conn):
            uri = node.attrs.get("uri") or ""
            qualifying = _compute_qualifying_domains(conn, kind=kind, name=node.name, uri=uri)
            # D-01: populate parent_pkg_names with the DOMAIN-AGNOSTIC consumer
            # set for every dep/test_suite (not only single-domain ones), so a
            # direct-placed dep/suite still nests under its consumer packages.
            # For test_suite: pass entity_uri (unique, stable); for dependency:
            # pass entity_name (D-08).
            parent_pkgs: tuple[str, ...] = ()
            if kind == "test_suite":
                parent_pkgs = _consumer_pkgs(conn, kind=kind, entity_uri=uri)
            elif kind == "dependency":
                parent_pkgs = _consumer_pkgs(conn, kind=kind, entity_name=node.name)
            suite_kind: str | None = None
            pkg_for_suite: str | None = None
            if kind == "test_suite":
                attrs = node.attrs if isinstance(node.attrs, dict) else {}
                suite_kind = attrs.get("suite_kind") or None
                suite_path = attrs.get("path")
                if suite_path:
                    pkg_for_suite = Path(suite_path).parent.name or None
                if not pkg_for_suite:
                    pkg_for_suite = None
            entity = PlacedEntity(
                kind=kind,
                name=node.name,
                uri=uri,
                parent_pkg_names=parent_pkgs,
                suite_kind=suite_kind,
                pkg_for_suite=pkg_for_suite,
            )
            entity = dataclasses.replace(
                entity,
                summary=_read_entity_summary(wiki_root, entity, collision_set),
            )
            if kind in ("package", "app"):
                name_to_entity[entity.name] = entity
            if len(qualifying) == 1:
                the_domain = next(iter(qualifying))
                domain_buckets, _ = _buckets_for(domain_repo[the_domain])
                domain_buckets.setdefault(the_domain, []).append(entity)
            else:
                _, direct = _buckets_for(_repo_for(uri, kind=kind, name=node.name))
                direct.append(entity)

    for domain_buckets, direct in per_repo.values():
        for d in domain_buckets:
            domain_buckets[d].sort(key=lambda e: e.uri)
        direct.sort(key=lambda e: (_PLACEABLE_KINDS.index(e.kind), e.uri))
    return per_repo, name_to_entity, domain_repo
```

- [ ] **Step 5: Add the temporary flatten shim in `_render`**

In `_render`, replace the two lines

```python
    domain_buckets, by_kind, name_to_entity = _place_entities(conn, wiki_root, collision_set)
    entity_count = sum(len(v) for v in domain_buckets.values()) + len(by_kind)
```

with:

```python
    per_repo, name_to_entity, _domain_repo = _place_entities(conn, wiki_root, collision_set)
    # TEMPORARY shim (removed by the repository-section render change in the
    # same feature): flatten per-repo placement back to the old
    # (domain_buckets, by_kind) shape so the existing `## Domains` /
    # `## By Kind` render path stays byte-identical for this commit.
    domain_buckets: dict[str, list[PlacedEntity]] = {}
    by_kind: list[PlacedEntity] = []
    for buckets, direct in per_repo.values():
        for dname, ents in buckets.items():
            domain_buckets.setdefault(dname, []).extend(ents)
        by_kind.extend(direct)
    for dname in domain_buckets:
        domain_buckets[dname].sort(key=lambda e: e.uri)
    by_kind.sort(key=lambda e: (_PLACEABLE_KINDS.index(e.kind), e.uri))
    entity_count = sum(len(v) for v in domain_buckets.values()) + len(by_kind)
```

- [ ] **Step 6: Run the full wiki-io suite**

Run: `uv run --package wiki-io pytest`
Expected: PASS — placement tests green, all render/integration output unchanged.

- [ ] **Step 7: Commit**

```bash
git add packages/wiki-io/src/wiki_io/index_generator.py packages/wiki-io/tests/test_index_generator.py
git commit -m "feat(wiki-io): per-repo entity placement in index generator (D-R1/D-R2/D-R7)"
```

---

### Task 3: Repository-section rendering + `IndexWriteResult` rename

**Goal:** Replace `_render_domains`/`_render_by_kind` with `_render_repository_section` + `_render_entity_heading`, rename `by_kind_count` → `direct_count`, add `repo_count` (D-R8), and rewrite all affected tests.

**Files:**
- Modify: `packages/wiki-io/src/wiki_io/index_generator.py` (docstring, `IndexWriteResult`, `KIND_LABELS` → `KIND_HEADING_LABELS`, new renderers, `_render`, `generate_index`, `__all__`)
- Test: `packages/wiki-io/tests/test_index_generator.py` (rewrite all assertions referencing the old structure; new repo-section tests)

**Acceptance Criteria:**
- [ ] One `## Repository: <name>` section per repository node WITH content, alphabetical by repo name; empty repo sections omitted (D-08)
- [ ] Domains nest as `### Domain: <X>` / `#### Sub-Domain: <Y>` inside their repo (D-R2); entities are kind-prefixed headings one level below their container (D-R4) with singular labels (D-R5)
- [ ] Entity body: `{summary} — [[entities/<stem>|open page]]` line + unchanged `_render_pkg_nested` sub-lists
- [ ] Kind-major order in any container: apps, packages, agent plugins; alphabetical by URI within kind (D-R6)
- [ ] `## Domains`, `## By Kind`, flat `### Apps`/`### Packages`/`### Agent Plugins`, and the `— <repo>` header suffix no longer render
- [ ] `IndexWriteResult` has `direct_count` + `repo_count`; `by_kind_count` gone; `domain_count` keeps its meaning
- [ ] Zero repository nodes + empty graph → curated lanes only; unchanged invariants (D-02/D-16/D-19/D-20, Phase 53 links) still hold
- [ ] Full wiki-io suite green

**Verify:** `uv run --package wiki-io pytest` → all pass

**Steps:**

- [ ] **Step 1: Rewrite the affected tests (red)**

All edits in `packages/wiki-io/tests/test_index_generator.py`.

1a. In the import block: replace `KIND_LABELS` with `KIND_HEADING_LABELS`.

1b. `TestIndexWriteResult.test_shape` / `test_frozen` / `test_module_constants` — replace with:

```python
class TestIndexWriteResult:
    def test_shape(self):
        r = IndexWriteResult(
            path=Path("/tmp/wiki/index.md"),
            bytes_written=1234,
            changed=True,
            entity_count=10,
            curated_count=5,
            domain_count=2,
            direct_count=3,
            repo_count=1,
        )
        assert r.path == Path("/tmp/wiki/index.md")
        assert r.bytes_written == 1234
        assert r.changed is True
        assert r.entity_count == 10
        assert r.curated_count == 5
        assert r.domain_count == 2
        assert r.direct_count == 3
        assert r.repo_count == 1

    def test_frozen(self):
        r = IndexWriteResult(
            path=Path("/x"),
            bytes_written=0,
            changed=False,
            entity_count=0,
            curated_count=0,
            domain_count=0,
            direct_count=0,
            repo_count=0,
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.changed = True  # type: ignore[misc]

    def test_module_constants(self):
        # D-R6: BY_KIND_ORDER survives as the kind-major heading order.
        assert BY_KIND_ORDER == ("app", "package", "agent_plugin")
        # D-R5: singular kind heading labels.
        assert KIND_HEADING_LABELS == {"app": "App", "package": "Package", "agent_plugin": "Agent Plugin"}
        assert len(CURATED_LANES) == 3
        assert CURATED_LANES[0] == ("adrs", "adrs", "ADRs")
        assert CURATED_LANES[1] == ("concepts", "concepts", "Concepts")
        assert CURATED_LANES[2] == ("sources", "sources", "Sources")
        assert "architecture/index.md" not in GENERATED_FILES
        assert "index.md" in GENERATED_FILES
        assert "concepts/index.md" in GENERATED_FILES

    def test_entry_link_wiki_vs_work(self):
        from wiki_io.wikilinks import vault_wikilink

        assert vault_wikilink("work/foo.md", "Foo") == "[[work/foo|Foo]]"
        assert vault_wikilink("concepts/foo.md", "Foo") == "[[concepts/foo|Foo]]"
```

1c. `TestRenderDomainTree` — replace the three tests' assertion blocks (fixtures keep their Task-2 shape):

```python
    # test_single_domain_with_one_package — after `text, *_ = _render(conn, wiki_root)`:
        assert "\n## Repository: agent-research" in text
        assert "## Domains" not in text
        assert "\n### Domain: core" in text
        assert "\n#### Package: pkg-a" in text
        assert "[[entities/pkg_pkg-a|open page]]" in text

    # test_sub_domain_nesting — after `text, *_ = _render(conn, wiki_root)`:
        assert "\n### Domain: core" in text
        assert "\n#### Sub-Domain: billing" in text
        assert "\n### Domain: billing" not in text
        assert "\n#### Package: pkg-core" in text
        assert "\n##### Package: pkg-billing" in text

    # test_empty_domain_omitted — after `text, *_ = _render(conn, wiki_root)`:
        assert "Domain: empty-domain" not in text
        # repo has no entities at all -> whole repo section omitted (D-08)
        assert "## Repository:" not in text
```

1d. Rename class `TestRenderByKind` → `TestRenderDirectEntities` and replace its tests:

```python
class TestRenderDirectEntities:
    def test_direct_entities_kind_major_order(self, tmp_path, make_index_fixture_graph):
        # D-R6: apps first, then packages, then agent plugins — as `###`
        # kind-prefixed headings directly under the repo header. A dependency
        # used by a direct package nests UNDER that package (no flat groups).
        spec = {
            "nodes": [
                ("repository", "agent-research", {"uri": "repo:agent-research"}),
                ("app", "myapp", {"uri": "app:agent-research/myapp", "app_kind": "cli"}),
                ("package", "pkg-cross", {"uri": "pkg:pkg-cross"}),
                ("dependency", "boto3", {"uri": "dependency:pypi/boto3", "ecosystem": "pypi"}),
                ("agent_plugin", "graph-wiki", {"uri": "agent_plugin:o/r/graph-wiki", "ecosystem": "claude-code"}),
            ],
            "edges": [
                ("package", "pkg-cross", "dependency", "boto3", "used_by", {}),
            ],
        }
        conn = make_index_fixture_graph(spec)
        wiki_root = tmp_path / "wiki"
        wiki_root.mkdir(parents=True, exist_ok=True)
        text, *_ = _render(conn, wiki_root)
        assert "\n## Repository: agent-research" in text
        app_idx = text.find("\n### App: myapp")
        pkg_idx = text.find("\n### Package: pkg-cross")
        plug_idx = text.find("\n### Agent Plugin: graph-wiki")
        assert app_idx > -1 and pkg_idx > -1 and plug_idx > -1
        assert app_idx < pkg_idx < plug_idx
        assert "[[entities/pkg_pkg-cross|open page]]" in text
        assert "[[entities/app_myapp|open page]]" in text
        assert "[[entities/agent-plugin_graph-wiki|open page]]" in text
        # Removed structure never renders.
        assert "## By Kind" not in text
        assert "### Apps" not in text
        assert "### Packages" not in text
        assert "### Agent Plugins" not in text
        # No flat dependency group; boto3 still nests under pkg-cross (bullet).
        assert "  - Dependencies" in text
        assert "[[entities/dep_boto3|boto3]]" in text

    def test_direct_entity_summary_renders_before_open_page_link(self, tmp_path, make_index_fixture_graph):
        """A direct entity with a `summary:` renders `{summary} — [[…|open page]]`
        on the line beneath its kind-prefixed heading (summary-first ordering)."""
        spec = {
            "nodes": [
                ("repository", "agent-research", {"uri": "repo:agent-research"}),
                ("package", "pkg-cross", {"uri": "pkg:pkg-cross"}),  # zero domains
            ],
            "edges": [],
        }
        conn = make_index_fixture_graph(spec)
        wiki_root = tmp_path / "wiki"
        wiki_root.mkdir(parents=True, exist_ok=True)
        _write_curated_page(
            wiki_root / "entities" / "pkg_pkg-cross.md",
            title="pkg-cross",
            summary="Cross summary",
        )
        text, *_ = _render(conn, wiki_root)
        assert "\n### Package: pkg-cross" in text
        assert "Cross summary — [[entities/pkg_pkg-cross|open page]]" in text

    def test_no_direct_entities_no_stray_headings(self, tmp_path, make_index_fixture_graph):
        # All entities placed in domains -> repo section contains only the
        # domain block; no level-3 entity headings, no `## By Kind`.
        spec = {
            "nodes": [
                ("repository", "agent-research", {"uri": "repo:agent-research"}),
                ("domain", "core", {"uri": "domain:core"}),
                ("package", "pkg-a", {"uri": "pkg:pkg-a"}),
            ],
            "edges": [
                ("package", "pkg-a", "domain", "core", "belongs_to_domain", {}),
            ],
        }
        conn = make_index_fixture_graph(spec)
        wiki_root = tmp_path / "wiki"
        wiki_root.mkdir(parents=True, exist_ok=True)
        text, *_ = _render(conn, wiki_root)
        assert "## By Kind" not in text
        assert "\n### Domain: core" in text
        assert "\n#### Package: pkg-a" in text
        assert "\n### Package:" not in text

    def test_test_suites_subheading(self, tmp_path, make_index_fixture_graph):
        spec = {
            "nodes": [
                ("repository", "agent-research", {"uri": "repo:agent-research"}),
                ("domain", "d1", {"uri": "domain:d1"}),
                ("domain", "d2", {"uri": "domain:d2"}),
                ("package", "pkg-1", {"uri": "pkg:pkg-1"}),
                ("package", "pkg-2", {"uri": "pkg:pkg-2"}),
                ("test_suite", "suite", {"uri": "test_suite:suite"}),
            ],
            "edges": [
                ("package", "pkg-1", "domain", "d1", "belongs_to_domain", {}),
                ("package", "pkg-2", "domain", "d2", "belongs_to_domain", {}),
                ("test_suite", "suite", "package", "pkg-1", "tests", {}),
                ("test_suite", "suite", "package", "pkg-2", "tests", {}),
            ],
        }
        conn = make_index_fixture_graph(spec)
        wiki_root = tmp_path / "wiki"
        wiki_root.mkdir(parents=True, exist_ok=True)
        text, *_ = _render(conn, wiki_root)
        # No flat `### Test Suites` group. The multi-domain suite nests under
        # both pkg-1 (domain d1) and pkg-2 (domain d2) per D-10.
        assert "### Test Suites" not in text
        assert "  - Test Suites" in text
        assert text.count("[[entities/tests_suite|suite]]") == 2
```

1e. `test_generate_index_against_fixture_graph` — replace the assertions after `result = generate_index(conn, wiki_root)` (fixture spec unchanged):

```python
    assert result.changed is True
    assert result.entity_count == 6  # 3 pkgs + 1 ts + 1 dep + 1 agent_plugin
    assert result.curated_count == 2
    assert result.domain_count == 2
    assert result.repo_count == 1
    # D-R8: direct_count = heading entities rendered directly under a repo
    # header. boto3 (multi-domain dependency) only nests under its consumers,
    # so pkg-cross (package) + graph-wiki (agent_plugin) remain.
    assert result.direct_count == 2

    text = (wiki_root / "index.md").read_text(encoding="utf-8")
    assert "\n## Repository: agent-research" in text
    assert "## Domains" not in text
    assert "## By Kind" not in text
    assert "\n### Domain: billing" in text
    assert "\n### Domain: core" in text
    # Single-domain entities are `####` headings inside their domain block …
    assert "\n#### Package: pkg-a" in text
    assert "\n#### Package: pkg-b" in text
    # … and zero/multi-domain entities are `###` headings under the repo.
    assert "\n### Package: pkg-cross" in text
    assert "\n### Agent Plugin: graph-wiki" in text
    assert "\n### Package: pkg-a" not in text
    # Domains render before direct entities (spec section order); billing < core.
    billing_idx = text.find("\n### Domain: billing")
    core_idx = text.find("\n### Domain: core")
    cross_idx = text.find("\n### Package: pkg-cross")
    assert -1 < billing_idx < core_idx < cross_idx
    # Flat kind groups are gone.
    assert "### Apps" not in text
    assert "### Packages" not in text
    assert "### Agent Plugins" not in text
    assert "### Dependencies" not in text
    # boto3 nests under pkg-a (core) and pkg-b (billing) as bullets (D-10).
    assert "  - Dependencies" in text
    assert "[[entities/dep_boto3|boto3]]" in text
    assert "[[entities/pkg_pkg-a|open page]]" in text
    assert "## ADRs" in text
    assert "## Concepts" in text
    assert "## Sources" not in text
    assert "## Architecture" not in text
    assert "## Work" not in text

    # No per-folder index files written (D-14)
    assert not (wiki_root / "concepts" / "index.md").exists()
    assert not (wiki_root / "adrs" / "index.md").exists()
```

1f. `test_cross_cutting_in_by_kind_only` — rename to `test_cross_cutting_renders_direct_under_repo` and replace the assertions after `text, *_ = _render(conn, wiki_root)`:

```python
    cross_link = "[[entities/pkg_pkg-cross|open page]]"
    assert text.count(cross_link) == 1
    assert "\n### Package: pkg-cross" in text
    core_idx = text.find("\n### Domain: core")
    billing_idx = text.find("\n### Domain: billing")
    cross_idx = text.find("\n### Package: pkg-cross")
    assert core_idx > -1 and billing_idx > -1 and cross_idx > -1
    # Domain blocks render before direct entities inside the repo section.
    assert core_idx < cross_idx
    assert billing_idx < cross_idx
```

1g. `test_multi_domain_entity_in_by_kind` — rename to `test_multi_domain_entity_nests_only_under_consumers`; keep all assertions, they remain valid (`"tests_cross"` count == 2, no flat `### Test Suites`, `  - Test Suites` present). Update the docstring's "by_kind" wording to "placed direct under the repo".

1h. `test_sub_domain_nesting` (module-level) — replace assertions after `text, *_ = _render(conn, wiki_root)`:

```python
    assert "\n### Domain: core" in text
    assert "\n#### Sub-Domain: billing" in text
    assert "\n### Domain: billing" not in text
    assert "\n#### Package: pkg-core" in text
    assert "\n##### Package: pkg-billing" in text
    core_idx = text.find("\n### Domain: core")
    sub_idx = text.find("\n#### Sub-Domain: billing")
    assert core_idx < sub_idx
```

1i. `test_empty_sections_omitted` — replace assertions after `text, *_ = _render(conn, wiki_root)`:

```python
    assert "\n### Domain: active-domain" in text
    assert "\n#### Package: pkg-solo" in text
    assert "[[entities/pkg_pkg-solo|open page]]" in text
    # pkg-solo has no suites/deps -> no nested sub-lists anywhere (D-08).
    assert "Test Suites" not in text
    assert "Dependencies" not in text
    assert "Domain: empty-domain" not in text
```

1j. `test_agent_plugin_always_by_kind` — rename to `test_agent_plugin_always_direct_under_repo`; replace assertions after `text, *_ = _render(conn, wiki_root)`:

```python
    agent_plugin_slug = "agent-plugin_graph-wiki"
    assert text.count(agent_plugin_slug) == 1
    assert "\n### Agent Plugin: graph-wiki" in text
    core_idx = text.find("\n### Domain: core")
    plug_idx = text.find("\n### Agent Plugin: graph-wiki")
    assert -1 < core_idx < plug_idx
```

1k. `test_app_zero_domain_renders_in_by_kind_apps_first` — rename to `test_app_zero_domain_renders_direct_apps_first`; replace assertions after `text, *_ = _render(conn, wiki_root)`:

```python
    app_idx = text.find("\n### App: myapp")
    pkg_idx = text.find("\n### Package: pkg-cross")
    assert app_idx > -1
    assert pkg_idx > -1
    assert app_idx < pkg_idx  # apps listed first (D-R6)
    assert "[[entities/app_myapp|open page]]" in text
```

1l. `test_app_single_domain_renders_under_its_domain` — replace assertions after `text, *_ = _render(conn, wiki_root)`:

```python
    assert "\n### Domain: core" in text
    assert "\n#### App: myapp" in text
    assert "[[entities/app_myapp|open page]]" in text
    assert "\n### App:" not in text  # not a direct entity
```

1m. `test_inline_summary_from_entity_page_frontmatter` — replace assertions after `text, *_ = _render(conn, wiki_root)`:

```python
    # pkg-a renders its summary before the open-page link (D-R4 body shape).
    assert "\n#### Package: pkg-a" in text
    assert "Some summary — [[entities/pkg_pkg-a|open page]]" in text
    # pkg-b (no entity page) renders the bare link with NO summary prefix.
    assert "\n#### Package: pkg-b" in text
    assert "[[entities/pkg_pkg-b|open page]]\n" in text
    assert "— [[entities/pkg_pkg-b|open page]]" not in text
```

1n. Add the new repo-section tests after `test_agent_plugin_always_direct_under_repo`:

```python
def test_multi_repo_renders_two_alphabetical_sections(tmp_path, make_index_fixture_graph):
    """D-R1 — two repository nodes render two self-contained, alphabetical
    `## Repository:` sections with entities split by URI (D-R7), domains
    nested in their own repo's section (D-R2)."""
    spec = {
        "nodes": [
            ("repository", "repo-alpha", {"uri": "repo:local/repo-alpha"}),
            ("repository", "repo-beta", {"uri": "repo:local/repo-beta"}),
            ("domain", "core", {"uri": "domain:local/repo-beta/core"}),
            ("package", "pkg-one", {"uri": "pkg:local/repo-alpha/pkg-one"}),
            ("package", "pkg-two", {"uri": "pkg:local/repo-beta/pkg-two"}),
            ("package", "pkg-three", {"uri": "pkg:local/repo-beta/pkg-three"}),
        ],
        "edges": [
            ("package", "pkg-two", "domain", "core", "belongs_to_domain", {}),
        ],
    }
    conn = make_index_fixture_graph(spec)
    wiki_root = tmp_path / "wiki"
    wiki_root.mkdir(parents=True, exist_ok=True)
    text, *_ = _render(conn, wiki_root)
    a_idx = text.find("\n## Repository: repo-alpha")
    b_idx = text.find("\n## Repository: repo-beta")
    assert -1 < a_idx < b_idx
    one_idx = text.find("\n### Package: pkg-one")
    dom_idx = text.find("\n### Domain: core")
    two_idx = text.find("\n#### Package: pkg-two")
    three_idx = text.find("\n### Package: pkg-three")
    # pkg-one inside alpha; beta holds its domain (with pkg-two) then pkg-three.
    assert a_idx < one_idx < b_idx
    assert b_idx < dom_idx < two_idx < three_idx


def test_empty_repo_section_omitted(tmp_path, make_index_fixture_graph):
    """D-08 — a repository node with no placed entities renders no section."""
    spec = {
        "nodes": [
            ("repository", "repo-alpha", {"uri": "repo:local/repo-alpha"}),
            ("repository", "repo-empty", {"uri": "repo:local/repo-empty"}),
            ("package", "pkg-one", {"uri": "pkg:local/repo-alpha/pkg-one"}),
        ],
        "edges": [],
    }
    conn = make_index_fixture_graph(spec)
    wiki_root = tmp_path / "wiki"
    wiki_root.mkdir(parents=True, exist_ok=True)
    text, *_ = _render(conn, wiki_root)
    assert "\n## Repository: repo-alpha" in text
    assert "Repository: repo-empty" not in text


def test_zero_repos_curated_lanes_only(tmp_path, make_index_fixture_graph):
    """Edge case — zero repository nodes (empty graph): no entity sections,
    curated lanes still render."""
    wiki_root = tmp_path / "wiki"
    _write_curated_page(wiki_root / "concepts" / "foo.md", title="Foo Concept")
    conn = make_index_fixture_graph({"nodes": [], "edges": []})
    result = generate_index(conn, wiki_root)
    text = (wiki_root / "index.md").read_text(encoding="utf-8")
    assert "## Repository:" not in text
    assert "## Concepts" in text
    assert result.repo_count == 0
    assert result.direct_count == 0
    assert result.domain_count == 0
```

- [ ] **Step 2: Run tests to verify the rewritten tests fail**

Run: `uv run --package wiki-io pytest tests/test_index_generator.py -x -q`
Expected: FAIL — `IndexWriteResult` has no `direct_count`, `KIND_HEADING_LABELS` import error, old `## Domains`/`## By Kind` still rendered.

- [ ] **Step 3: Implement the render change in `index_generator.py`**

3a. Replace the `KIND_LABELS` constant with:

```python
# D-R5: singular kind labels for entity headings. Only heading kinds appear —
# test_suite/dependency render exclusively as nested sub-list bullets.
KIND_HEADING_LABELS: dict[str, str] = {
    "app": "App",
    "package": "Package",
    "agent_plugin": "Agent Plugin",
}
```

3b. Replace the `IndexWriteResult` dataclass body:

```python
@dataclass(frozen=True)
class IndexWriteResult:
    """Return value of `generate_index` (D-18; fields per 2026-06-12 D-R8).

    `direct_count` = heading entities rendered directly under a repo header
    (the old `by_kind_count` slot); `repo_count` = rendered `## Repository:`
    sections; `domain_count` keeps its meaning (rendered top-level domains).
    """

    path: Path
    bytes_written: int
    changed: bool
    entity_count: int
    curated_count: int
    domain_count: int
    direct_count: int
    repo_count: int
```

3c. In the module docstring, replace the D-03 bullet's section order with:

```
- D-03 (amended 2026-06-12 — repository grouping): rendered section order is
  H1 → banner → one `## Repository: <name>` section per repository node
  (domains nested inside, entities as kind-prefixed headings; replaces the
  old `## Domains` → `## By Kind` slot) → `## ADRs` → `## Concepts` →
  `## Sources` → `## Work`.
```

3d. Add the kind-major helper and entity-heading renderer after `_build_sub_for_pkg`:

```python
def _kind_major(entities: list[PlacedEntity]) -> list[PlacedEntity]:
    """Heading entities in kind-major order (D-R6): apps, then packages, then
    agent plugins (`BY_KIND_ORDER`), alphabetical by URI within each kind.
    Non-heading kinds (test_suite/dependency — they only nest) are dropped."""
    return sorted(
        (e for e in entities if e.kind in BY_KIND_ORDER),
        key=lambda e: (BY_KIND_ORDER.index(e.kind), e.uri),
    )


def _render_entity_heading(
    conn: sqlite3.Connection,
    entity: PlacedEntity,
    *,
    level: int,
    collision_set: frozenset[str],
    name_to_entity: dict[str, PlacedEntity],
    sub_for_pkg: dict[str, dict[str, list[PlacedEntity]]],
) -> list[str]:
    """Render one entity as a kind-prefixed heading block (D-R4/D-R5).

    `level` is the markdown heading depth: 3 directly under the repo header,
    4 inside a `### Domain:` block, one deeper per sub-domain level. Body is
    the `{summary} — [[entities/<stem>|open page]]` line plus the
    `_render_pkg_nested` sub-lists (packages/apps only — unchanged shape).
    """
    label = KIND_HEADING_LABELS[entity.kind]
    lines = [f"{'#' * level} {label}: {entity.name}", ""]
    link = _entity_wikilink(entity, collision_set, label="open page")
    summary = f"{entity.summary} — " if entity.summary else ""
    lines.append(f"{summary}{link}")
    if entity.kind in ("package", "app"):
        lines.extend(_render_pkg_nested(conn, entity, sub_for_pkg, name_to_entity, collision_set))
    lines.append("")
    return lines
```

3e. Replace `_render_domain_section` with:

```python
def _render_domain_section(
    conn: sqlite3.Connection,
    domain_buckets: dict[str, list[PlacedEntity]],
    *,
    domain_name: str,
    depth: int,
    collision_set: frozenset[str],
    name_to_entity: dict[str, PlacedEntity],
    sub_for_pkg: dict[str, dict[str, list[PlacedEntity]]],
) -> list[str]:
    """Recursively render one domain block inside a repository section (D-R2).

    `depth == 0` -> `### Domain: X`; deeper -> `#### Sub-Domain: Y`, ….
    Entities render as kind-prefixed headings one level below the domain
    heading (D-R4), kind-major (D-R6). Returns [] (D-08 fully-empty
    omission) when the block has zero heading entities AND every sub-domain
    block is also empty.
    """
    level = 3 + depth
    label = f"Domain: {domain_name}" if depth == 0 else f"Sub-Domain: {domain_name}"

    entity_lines: list[str] = []
    for e in _kind_major(domain_buckets.get(domain_name, [])):
        entity_lines.extend(
            _render_entity_heading(
                conn,
                e,
                level=level + 1,
                collision_set=collision_set,
                name_to_entity=name_to_entity,
                sub_for_pkg=sub_for_pkg,
            )
        )

    sub_domain_blocks: list[str] = []
    for sub_name in _list_subdomains(conn, domain_name):
        sub_domain_blocks.extend(
            _render_domain_section(
                conn,
                domain_buckets,
                domain_name=sub_name,
                depth=depth + 1,
                collision_set=collision_set,
                name_to_entity=name_to_entity,
                sub_for_pkg=sub_for_pkg,
            )
        )

    if not entity_lines and not sub_domain_blocks:
        return []  # D-08 fully-empty omission
    return [f"{'#' * level} {label}", "", *entity_lines, *sub_domain_blocks]
```

3f. DELETE `_render_domains` and `_render_by_kind`. Add in their place:

```python
def _render_repository_section(
    conn: sqlite3.Connection,
    *,
    repo_name: str,
    domain_buckets: dict[str, list[PlacedEntity]],
    direct: list[PlacedEntity],
    repo_domains: list[str],
    collision_set: frozenset[str],
    name_to_entity: dict[str, PlacedEntity],
    sub_for_pkg: dict[str, dict[str, list[PlacedEntity]]],
) -> tuple[list[str], int, int]:
    """Render one `## Repository: <name>` section (D-R1).

    Nested domain blocks first (alphabetical top-level domains of THIS repo
    per `repo_domains`, D-R2), then direct entities kind-major (D-R6).
    Returns (lines, rendered_domain_count, direct_heading_count) —
    ([], 0, 0) when the whole section is empty (D-08).
    """
    lines: list[str] = []
    domain_count = 0
    for d in repo_domains:
        if not _is_top_level_domain(conn, d):
            continue
        section = _render_domain_section(
            conn,
            domain_buckets,
            domain_name=d,
            depth=0,
            collision_set=collision_set,
            name_to_entity=name_to_entity,
            sub_for_pkg=sub_for_pkg,
        )
        if section:
            lines.extend(section)
            domain_count += 1
    direct_count = 0
    for e in _kind_major(direct):
        lines.extend(
            _render_entity_heading(
                conn,
                e,
                level=3,
                collision_set=collision_set,
                name_to_entity=name_to_entity,
                sub_for_pkg=sub_for_pkg,
            )
        )
        direct_count += 1
    if not lines:
        return [], 0, 0
    return [f"## Repository: {repo_name}", "", *lines], domain_count, direct_count
```

3g. In `_render`: delete the Task-2 shim and replace the placement + entity-section block. The function signature return type becomes `tuple[str, int, int, int, int, int]` and the docstring's Returns line becomes `Returns (text, entity_count, curated_count, domain_count, direct_count, repo_count).` Replace from the `_place_entities` call through the `lines.extend(by_kind_lines)` block with:

```python
    per_repo, name_to_entity, domain_repo = _place_entities(conn, wiki_root, collision_set)

    all_placed: list[PlacedEntity] = []
    for buckets, direct in per_repo.values():
        for ents in buckets.values():
            all_placed.extend(ents)
        all_placed.extend(direct)
    entity_count = len(all_placed)

    # D-01/D-10: one global dep/suite-under-package grouping over ALL placed
    # entities, shared across all repo sections, so nesting behavior is
    # identical regardless of which repo/domain a consumer renders in.
    sub_for_pkg = _build_sub_for_pkg(all_placed)
```

(keep the existing `workspace_root` / curated-scan / banner block exactly as-is, then where `_render_domains`/`_render_by_kind` were called:)

```python
    repo_count = 0
    domain_count = 0
    direct_count = 0
    for repo_name in sorted(per_repo):
        buckets, direct = per_repo[repo_name]
        repo_domains = sorted(d for d, r in domain_repo.items() if r == repo_name)
        section, d_count, dir_count = _render_repository_section(
            conn,
            repo_name=repo_name,
            domain_buckets=buckets,
            direct=direct,
            repo_domains=repo_domains,
            collision_set=collision_set,
            name_to_entity=name_to_entity,
            sub_for_pkg=sub_for_pkg,
        )
        if section:
            lines.extend(section)
            repo_count += 1
            domain_count += d_count
            direct_count += dir_count
```

…and the final return becomes:

```python
    text = "\n".join(lines).rstrip("\n") + "\n"  # POSIX trailing newline
    return text, entity_count, curated_count, domain_count, direct_count, repo_count
```

3h. Update `generate_index` to unpack and forward the new fields (both `IndexWriteResult(...)` constructions):

```python
    text, entity_count, curated_count, domain_count, direct_count, repo_count = _render(conn, wiki_root, display_name)
```

…and in both constructor calls replace `by_kind_count=by_kind_count,` with:

```python
            direct_count=direct_count,
            repo_count=repo_count,
```

3i. Update `__all__`: remove `"KIND_LABELS"`, `"_render_by_kind"`, `"_render_domains"`; add `"KIND_HEADING_LABELS"`, `"_kind_major"`, `"_render_entity_heading"`, `"_render_repository_section"` (keep alphabetical order).

- [ ] **Step 4: Run the full wiki-io suite**

Run: `uv run --package wiki-io pytest`
Expected: PASS. If a blank-line/spacing assertion fails, fix the renderer (every entity-heading block must end with one `""` line so consecutive sections stay separated), not the test.

- [ ] **Step 5: Lint the touched files**

Run: `uv run ruff check packages/wiki-io/src/wiki_io/index_generator.py packages/wiki-io/tests/test_index_generator.py`
Expected: no new errors (the src tree has pre-existing noise elsewhere — do NOT run `ruff format` over it; match surrounding style).

- [ ] **Step 6: Commit**

```bash
git add packages/wiki-io/src/wiki_io/index_generator.py packages/wiki-io/tests/test_index_generator.py
git commit -m "feat(wiki-io): render per-repository index sections; IndexWriteResult direct_count/repo_count (D-R1..D-R8)"
```

---

### Task 4: Ripple check across consumers and suites

**Goal:** Prove no consumer references the old names or structure, and that the dependent suites stay green.

**Files:**
- Verify only (no expected edits): `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py:2336-2340`, core/CLI test suites. Fix anything the greps/suites surface.

**Acceptance Criteria:**
- [ ] `grep` finds zero remaining references to `by_kind_count`, `_render_by_kind`, `_render_domains`, or `KIND_LABELS` outside historical docs/specs
- [ ] `uv run --package wiki-io pytest` green
- [ ] `uv run --package graph-wiki-core pytest -m "not integration"` green
- [ ] `uv run --package graph-wiki-cli pytest -m "not integration"` green
- [ ] `uv run pyright` reports no new errors in the touched files

**Verify:** the three pytest commands above + the grep below → clean

**Steps:**

- [ ] **Step 1: Grep for stragglers**

Run:
```bash
grep -rn "by_kind_count\|_render_by_kind\|_render_domains\b\|KIND_LABELS\b" packages/ plugins/ --include="*.py"
```
Expected: no output. (`KIND_GROUP_LABELS` in `concept_kinds.py` is a different constant — the `\b` word boundaries keep it out; if it shows up anyway, it is NOT a straggler.)

- [ ] **Step 2: Run the three suites**

```bash
uv run --package wiki-io pytest
uv run --package graph-wiki-core pytest -m "not integration"
uv run --package graph-wiki-cli pytest -m "not integration"
```
Expected: all PASS. `scan.py` only reads `index_result.changed` / `.bytes_written`, and the core scan tests monkeypatch `generate_index`, so failures here mean an unintended behavior change — debug before proceeding (use graph-wiki:systematic-debugging).

- [ ] **Step 3: Type check**

Run: `uv run pyright packages/wiki-io/src/wiki_io/index_generator.py`
Expected: 0 errors.

- [ ] **Step 4: Commit (only if fixes were needed)**

```bash
git add -A && git commit -m "fix(wiki-io): ripple fixes for index repository grouping"
```
If nothing changed, skip the commit.

---

### Task 5: End-to-end — rescan the real workspace and verify `wiki/index.md`

**Goal:** Rescan the real agent-research workspace and verify the regenerated `wiki/index.md` matches the spec's approved mock-up structure, with captured evidence.

> **USER-ORDERED GATE — NON-SKIPPABLE.** This task was requested by the user in the current conversation. It MUST NOT be closed by walking around it, by declaring it "verified inline", or by substituting a cheaper check. Close only after every item in `acceptanceCriteria` has been re-validated independently, with output captured.

**Files:**
- No repo files. Regenerates `/Users/pat/Personal/workspaces/agent-research/claude-code/wiki/index.md` (scanner-owned, full-rewrite — D-02).

**Acceptance Criteria:**
- [ ] `gw scan --no-narrate` completes without error from the repo root
- [ ] `grep -c "^## Repository: " <workspace>/wiki/index.md` → `1` (section is `## Repository: agent-research`)
- [ ] `grep -n "^## Domains\|^## By Kind\|^### Apps$\|^### Packages$\|^### Agent Plugins$" <workspace>/wiki/index.md` → no output (old structure gone)
- [ ] Entities render as kind-prefixed headings (`^### Package: `, `^### App: `, `^### Agent Plugin: ` present; `^### Domain: ` present iff domains exist in the graph), matching the spec's "Rendered structure" mock-up
- [ ] Curated lanes (`## ADRs`, `## Concepts`, …) still render after the repository section
- [ ] The structural diff summary is shown to the user

**Verify:**
```bash
uv run --package graph-wiki-cli gw scan --no-narrate
grep -c "^## Repository: " /Users/pat/Personal/workspaces/agent-research/claude-code/wiki/index.md   # -> 1
grep -n "^## Domains\|^## By Kind\|^### Apps$\|^### Packages$\|^### Agent Plugins$" /Users/pat/Personal/workspaces/agent-research/claude-code/wiki/index.md   # -> no output
grep -n "^### \|^#### " /Users/pat/Personal/workspaces/agent-research/claude-code/wiki/index.md | head -40   # -> kind-prefixed headings
```

**Steps:**

- [ ] **Step 1: Snapshot the current index for the diff**

```bash
cp /Users/pat/Personal/workspaces/agent-research/claude-code/wiki/index.md /tmp/index-before.md
```

- [ ] **Step 2: Rescan (structural only, no Bedrock)**

Run from the repo root: `uv run --package graph-wiki-cli gw scan --no-narrate`
Expected: scan completes; output includes `index: wiki/index.md changed=True`.

- [ ] **Step 3: Run the verification greps**

Run the four commands from **Verify** above and capture their output. Then eyeball the new structure against the spec mock-up:

```bash
diff /tmp/index-before.md /Users/pat/Personal/workspaces/agent-research/claude-code/wiki/index.md | head -80
```

- [ ] **Step 4: Report to the user**

Present the captured grep output and a short before/after structural summary (old `## Domains`/`## By Kind` headers → new `## Repository: agent-research` tree). Note any surprises (e.g. the known pre-existing duplicated-dependency-bullets bug is OUT of scope per the spec — do not fix it here, just confirm it's pre-existing if visible).

---

## Out of scope (from the spec)

- The duplicated dependency bullets in the current real index — pre-existing nesting-data bug, file separately if confirmed in Task 5.
- Multi-repo *scanning* — the renderer is made ready; the graph still only ever contains one repository node.
- Note: with multiple repository nodes, ecosystem-scoped `dependency:` entities that are zero/multi-domain would raise (their URIs are repo-less by design). This is the spec's all-or-nothing edge case behaving as written; revisit when multi-repo scanning lands.
