# Pitfalls Research

**Domain:** Wiki Entity Restructure — adding /entities/ lane, URI-as-filename keying, scanner-populated relation frontmatter, hard-delete reconciliation, one-shot inbound-link migration, scanner-generated index, import-graph clustering, LLM domain proposals to a graph-driven wiki system.
**Researched:** 2026-05-26
**Confidence:** HIGH — grounded in existing codebase (scan.py, layout_io.py, ONTOLOGY-SPEC.md, v1.7 pitfalls, retrospective lessons from v1.0–v1.7)

---

## Critical Pitfalls

### Pitfall 1: URI-to-Filename Slug Collisions

**What goes wrong:**
Two distinct graph URIs produce identical filenames when normalized to filesystem-safe slugs. The collision classes for this codebase are:

- `pkg:agent-research/graph-io` vs `pkg:agent-research/graph_io` — underscore-to-hyphen normalization maps both to `pkg-agent-research-graph-io.md`.
- `pkg:org/foo/bar` vs `pkg:org/foo-bar` — forward-slash encoding and separator encoding collide when the separator character is reused (e.g., both use `-` as the delimiter after encoding `:`).
- `domain:billing-ops` vs `pkg:billing-ops` — the `kind:` prefix differentiates in the URI namespace but if the slug encoder drops the prefix, both become `billing-ops.md`.

The collision is silent: the second write overwrites the first. No error is raised because the filesystem allows it.

**Why it happens:**
URI characters that are illegal on filesystems (`:`, `/`) must be encoded or replaced. Naive implementations pick a single separator (e.g., replace `:` with `-`, replace `/` with `-`) and end up with a non-injective mapping. The more separator characters that get flattened to the same replacement, the larger the collision space.

**How to avoid:**
Use a slug scheme that preserves the URI structure in a collision-free way. Recommended encoding:

```
pkg:org/repo/name  →  entities/pkg__org__repo__name.md
                       (replace `:` with `__`, `/` with `__`)
```

This keeps the prefix (kind) + separator (`__`) + segments distinct. An alternative: use the URI verbatim as a key in a lookup table and generate a short hash suffix only on collision: `{normalized-slug}-{sha256(uri)[:6]}.md`. Either approach must be implemented as a pure function and tested against the full set of URIs produced by `graph_io.uri.*` (specifically `pkg_uri`, `subpkg_uri`, `domain_uri`, `repo_uri`, `entry_point_uri`, `test_suite_uri`) before the entity writer is wired into the scanner pipeline.

Add a property test: generate 1,000 synthetic URIs covering all admitted kinds and assert all slugs are unique.

**Warning signs:**
- Running two scan cycles on a repo with `foo/bar` and `foo-bar` packages produces one fewer entity file than expected.
- A `git diff` after scan shows a page content that mixes metadata from two different graph nodes.
- An existing entity page for `domain:core` is replaced silently after adding a package named `core`.

**Phase to address:**
URI-keying phase (the phase that introduces `/entities/` layout and the entity writer). This check must pass before any other entity-writer logic is tested. Build the slug encoder as a standalone function with a full test suite first.

---

### Pitfall 2: Frontmatter Key Collision Between Scanner-Owned and Human-Authored Keys

**What goes wrong:**
The scanner populates relation frontmatter on entity pages — keys like `covered_by`, `belongs_to_domain`, `depends_on`, `entry_points`. Human authors may write `status:`, `last_reviewed:`, `notes:`, `owner:` on the same page. If the scanner's update logic rewrites the entire frontmatter block (easy path: read page → discard frontmatter → write new frontmatter + body), human-authored keys are silently deleted.

A subtler failure: `status:` is a likely human key, but the graph also has a notion of `stale: true` that the v1.7 scanner writes. If the v1.8 entity writer introduces its own `status:` key (e.g., `status: active`) to reflect graph node status, it silently overwrites `status: deprecated` that a human set.

**Why it happens:**
Round-trip frontmatter preservation is not the default behavior when the writer reconstructs the YAML block from scratch. The existing `layout_io.py` pattern (which the scanner currently uses for the layout block) is an injection into an HTML-comment delimited region — it does not touch the rest of the frontmatter. The entity writer has no such region to inject into; it owns the full frontmatter.

**How to avoid:**
Define a canonical **scanner-owned key whitelist** before writing any entity pages. Only keys on the whitelist may be written or overwritten by the scanner. All other keys on existing pages must be preserved as-is via a merge strategy:

```python
def update_entity_frontmatter(existing_fm: dict, scanner_updates: dict, owned_keys: set[str]) -> dict:
    merged = dict(existing_fm)           # start with all human-authored keys
    for k, v in scanner_updates.items():
        assert k in owned_keys           # enforce at write time
        merged[k] = v                    # scanner overrides its own keys
    return merged
```

Proposed initial whitelist: `kind`, `uri`, `graph_updated_at`, `covered_by`, `belongs_to_domain`, `depends_on`, `entry_points`, `domain_children`, `domain_refs`. Do NOT put `status:`, `last_reviewed:`, `owner:`, `notes:`, `tags:` on the whitelist.

Write a test: create an entity page with human `status: deprecated`, run the entity writer, assert `status: deprecated` is preserved.

**Warning signs:**
- After a scan cycle, `git diff` shows `status:` or `last_reviewed:` disappearing from entity pages that had them.
- A page that a human had annotated with `owner: pat` loses the annotation after the next scan.
- The lint command reports "required field `status` missing" on entity pages that previously had it.

**Phase to address:**
Scanner relation-frontmatter phase. The whitelist must be in code (as a frozenset constant) and enforced at write time before any entity pages are written to disk. Include the merge test in the phase's acceptance criteria.

---

### Pitfall 3: Hard-Delete Losing Unsynced Human Edits

**What goes wrong:**
When a graph node disappears (package deleted, dependency dropped from manifest), the entity page is deleted on the next scan (per the Q2 hard-delete decision). If a human had added narrative prose or annotations to that entity page after the last scan, those edits are lost. There is no dirty-check before deletion.

The v1.7 scan.py already handles the "stale package" case by writing `stale: true` to the frontmatter and logging — it does NOT delete. The v1.8 restructure's Q2 decision is to hard-delete (acceptable because the vault is disposable). The pitfall is that this decision, if naively applied, deletes pages even when a human edited them since the last scan.

**Why it happens:**
The scanner's deletion path checks only "does this URI still exist in the graph?" — it does not check "has this page been modified since it was last written by the scanner?" Filesystem mtime is unreliable (git checkout resets it). A `graph_updated_at:` frontmatter timestamp is the only reliable marker if the page was last written by the scanner.

**How to avoid:**
Before deleting any entity page, check if the page's body content (everything after the frontmatter block) is non-empty and differs from the template default. If it is non-empty, emit a warning to stderr and write `stale: true` instead of deleting. Only delete pages where the body is empty or identical to the kind's default template body.

Alternatively: since the vault is fully disposable, make the hard-delete unconditional but log every deletion to the wiki append-log so the user can see what was lost. Document this behavior explicitly in the command's `--help` text.

The choice (warn-and-stale vs. hard-delete-with-log) must be locked in the phase spec before implementation. The v1.8 PROJECT.md says "dangling-link risk is accepted" — that is a policy decision about broken wikilinks, not about human edit loss. Clarify this before the delete logic is written.

**Warning signs:**
- After a scan following a package removal, a git diff shows a page deletion where the diff body contained non-template prose.
- The user reports "I added notes to the graph-io entity page and they disappeared after I removed a test suite."

**Phase to address:**
Hard-delete reconciliation phase (Q2). The deletion policy must be documented as a `must_have` in the phase plan. Whichever policy is chosen, the test must cover the "human had edited the page body" case.

---

### Pitfall 4: Inbound-Link Migration Regex Over-Matching

**What goes wrong:**
The one-shot migration script (Q3) rewrites wikilinks in `/concepts/`, `/adrs/`, `/architecture/` from old package-folder paths to new entity URIs. A regex like:

```python
re.sub(r'\[\[packages/([^/]+)/[^\]]+\]\]', r'[[entities/pkg__...\1...]]', text)
```

will also match wikilinks inside fenced code blocks (` ```markdown `) and inside inline code spans (`` `[[packages/foo/bar]]` ``). Obsidian renders these as wikilinks; the wiki's own examples may reference the old format in code blocks as documentation. Rewriting them changes the semantics of documentation pages.

A second failure mode: the regex matches a wikilink alias `[[packages/foo/bar|display name]]` and drops the alias portion in the replacement.

**Why it happens:**
Simple regex substitution on raw text does not understand Markdown structure — code fences, inline code, and link aliases are invisible to it.

**How to avoid:**
Use a Markdown-aware rewrite that:
1. Tokenizes the document into code spans/fences (which must be skipped) and prose regions (which are rewritten).
2. Preserves the `|alias` portion of wikilinks: `[[old-path|display]]` → `[[new-path|display]]`.

A pragmatic implementation: split on ```` ``` ```` fences and `` ` `` spans, apply the regex only to prose regions, rejoin. Test against a page that has a wikilink inside a fenced code block AND a wikilink in prose — verify only the prose link is rewritten.

The migration script must also be idempotent: running it twice must produce the same result as running it once. This means the regex must not match entity-format links that have already been rewritten.

Test cases to write before execution:
1. Prose wikilink: `[[packages/graph-io/index]]` → gets rewritten.
2. Code fence wikilink: ```` ```\n[[packages/foo/bar]]\n``` ```` → NOT rewritten.
3. Inline code wikilink: `` `[[packages/foo/bar]]` `` → NOT rewritten.
4. Aliased wikilink: `[[packages/foo/bar|graph-io package]]` → rewritten with alias preserved.
5. Already-migrated link: `[[entities/pkg__agent-research__graph-io]]` → unchanged on second run.

**Warning signs:**
- After migration, a concepts page that was documenting the old format now shows broken examples (the documentation example got rewritten).
- A `git diff` shows more lines changed than expected (code blocks were touched).
- A wikilink that had a display alias now renders as the raw entity slug.

**Phase to address:**
One-shot inbound-link migration phase (Q3). Write the tokenizer and all five test cases before writing the migration runner. Do not run the migration on the live vault until all tests pass.

---

### Pitfall 5: Index Regeneration Churning Git History

**What goes wrong:**
The scanner-generated index (Q5) is fully regenerated on every scan, even when no entities changed. This means every `graph-wiki-agent scan` produces a diff on the index file — typically hundreds of lines of wikilinks rearranged. Over 30 scans, the index file contributes 30 commits with mechanical diffs that make `git log` useless for understanding what actually changed.

A related problem: if the index generation is non-deterministic (e.g., domain sections are sorted by insertion order in the graph, which depends on scan sequence), the diff varies between runs even when the underlying graph is identical. This is the "churn" problem that the v1.6 `regenerate_dependencies_index` already suffers from (see scan.py line 639 — `regenerate_dependencies_index` runs unconditionally).

**Why it happens:**
Fully generated artifacts naturally change on every run if the generator is not deterministic or if the caller does not compare the current content before writing.

**How to avoid:**
1. **Deterministic generation**: sort domain sections by `domain.name`, sort entities within each section by `uri` (not by insertion order). The same graph always produces the same index content.
2. **Write-if-changed**: after generating the new index content, compare it to the current on-disk content. Only write (and thus dirty the file for git) if the content differs.

```python
new_content = render_index(graph)
if index_path.exists() and index_path.read_text() == new_content:
    return  # no change — skip the write
index_path.write_text(new_content)
```

The determinism requirement must be a test: generate the index twice from the same graph (with entities inserted in different orders) and assert byte-identical output.

**Warning signs:**
- `git log --oneline wiki/index.md` shows a new commit on every scan.
- `git diff` after two consecutive scans with no code changes shows the index changed.
- The index file's domain section order changes between runs.

**Phase to address:**
Scanner-generated index phase (Q5). Add the determinism test before adding the index generator. Add the write-if-changed guard before the first integration test.

---

### Pitfall 6: Import-Graph Clustering Producing Degenerate Clusters

**What goes wrong:**
The `cg domain-clusters` command uses import-graph connectivity to suggest domain candidates. On small or sparse monorepos (the primary target: `agent-research` has 7–8 workspace members with low inter-package import density), the clustering algorithm produces one of two degenerate results:

- **One giant blob**: every package imports from `model-adapter` or `subagent-runtime` (the shared infrastructure), so all packages cluster together via transitivity.
- **N singletons**: packages that don't import each other (e.g., `eval-harness` has no callers inside the repo) become their own clusters of size 1. With 8 packages, this might produce 8 singleton clusters, which is useless as a domain suggestion.

**Why it happens:**
Standard graph clustering (connected components, Louvain, etc.) is designed for large sparse graphs. On a small graph with high-degree hub nodes (shared infrastructure packages), standard algorithms collapse everything into one component. On a disconnected graph, they produce singletons.

**How to avoid:**
Use a clustering strategy designed for small graphs with hub nodes:

1. **Hub-node exclusion**: before clustering, exclude packages with in-degree above a threshold (configurable, default: used by >50% of other packages). These are cross-cutting packages and should not be domain anchors. After clustering the remainder, re-attach hub-excluded packages as "cross-cutting" candidates.

2. **Minimum cluster size gate**: discard clusters of size 1. Report them separately as "unclustered packages" — candidates for manual domain assignment.

3. **Maximum cluster size gate**: if a single cluster contains >80% of packages, emit a warning: "clustering produced one large group; try adjusting hub exclusion threshold or use LLM proposal mode."

4. **Output format**: `cg domain-clusters` should output a YAML structure, not a domain assignment, so the human can see which packages grouped together and decide whether the grouping makes sense as a domain.

The degenerate cluster warning must be present in the command's output, not just in documentation.

**Warning signs:**
- `cg domain-clusters` outputs one cluster containing all packages.
- `cg domain-clusters` outputs N clusters each with one package.
- The proposed clusters don't map to any recognizable feature boundary.

**Phase to address:**
`cg domain-clusters` implementation phase. The hub-exclusion and degenerate-cluster detection logic must be part of the initial implementation, not a v1.9 improvement. Test with the `agent-research` monorepo itself — it is a known-small sparse graph.

---

### Pitfall 7: LLM Domain Proposals Hallucinating Package Names

**What goes wrong:**
The `graph-wiki-agent graph propose-domains` subcommand passes the import-graph cluster output and current graph context to an LLM and asks it to propose domain groupings for `domains.proposed.yaml`. The LLM hallucinates:

- Package names that don't exist (e.g., suggests `packages/auth-core` when the actual name is `packages/core-bedrock`).
- Domain names that duplicate existing authored domains with slightly different spelling (e.g., proposes `domain: monitoring` when the authored `domains.yaml` has `domain: observability`).
- Circular containment: proposes `domain_contains_domain: [[core, infrastructure], [infrastructure, core]]` which would create a cycle and fail graph validation.

**Why it happens:**
The LLM generates plausible-sounding names from its training distribution. Without a strict grounding constraint (every name in the output must appear verbatim in the provided package list), the LLM freely invents names. Circular domain containment is a constraint the LLM cannot reason about structurally.

**How to avoid:**
1. **Package name grounding**: pass the LLM the exact list of package URIs from the graph (not names — URIs, since names may be ambiguous). Require that every package referenced in `domains.proposed.yaml` appears in that list. Post-process: validate each proposed package name against the ground-truth list, log any that don't match, strip invalid proposals before writing the YAML.

2. **Existing domain deduplication**: pass the current `domains.yaml` content alongside the cluster output. Instruct the LLM to reuse existing domain names when a proposed grouping substantially overlaps an existing domain.

3. **Cycle detection before write**: after the LLM response is received and parsed, run cycle detection on the proposed `domain_contains_domain` edges before writing `domains.proposed.yaml`. If a cycle is detected, log a warning and strip the offending edges (keeping the domain nodes and their package membership).

4. **Clearly mark the file as proposals**: the YAML file must have a header comment: `# PROPOSED DOMAIN GROUPINGS — for human review. Do not apply directly.` Do not use the same schema as `domains.yaml` — use a distinct key (`proposed_domains:` vs `domains:`) so tooling cannot accidentally parse it as authoritative.

**Warning signs:**
- `domains.proposed.yaml` contains a package name that doesn't exist in `graph_io.queries.list_packages`.
- The `cg update` command fails with "unknown package in domains.yaml" after a human applies the proposal without validating it.
- `domains.proposed.yaml` proposes `infrastructure: contains: [core]` and separately `core: contains: [infrastructure]`.

**Phase to address:**
`graph propose-domains` phase. The validation layer (grounding check + cycle detection) must be implemented in the same phase as the LLM call. Do not ship a proposal generator without the post-processing validation.

---

### Pitfall 8: `domains.proposed.yaml` Being Auto-Applied

**What goes wrong:**
The `domains.proposed.yaml` file is intended as a human-review artifact only. However:

- A developer writes a git hook or CI step that runs `cg update` on every commit. If `cg update` scans for domain config files and finds `domains.proposed.yaml` alongside `domains.yaml`, and the code reads both, the proposals are silently applied.
- The `graph propose-domains` command is run in a CI context where no human review is possible, and the consumer reads whatever is in the repo.
- A future developer sees `domains.proposed.yaml` and, not knowing its intent, renames it to `domains.yaml` (the authoritative file).

**Why it happens:**
YAML files with similar names in the same directory invite confusion. The graph-io codebase already reads `domains.yaml` — if `domains.proposed.yaml` uses the same schema and `graph_io.packages.refresh` is updated to also read it (by mistake or by a well-meaning "let's auto-apply safe proposals" change), proposals become authoritative silently.

**How to avoid:**
1. `graph_io.packages.refresh` must have an explicit allowlist of config filenames it reads. `domains.proposed.yaml` must not be on that list. This is a hard constraint in the `graph_io` package, not a documentation-only rule.
2. Add a test: place a `domains.proposed.yaml` next to `domains.yaml` in a fixture; assert that `cg update` produces the same graph as with only `domains.yaml` present — the proposals have no effect.
3. Use a clearly differentiated schema in the proposed file: `proposed_domains:` key, not `domains:`, so even if a parser accidentally reads it, the schema mismatch produces a load error rather than silent misinterpretation.
4. Add a README note in the workspace root alongside the file explaining why it must not be renamed to `domains.yaml` without review.

**Warning signs:**
- Running `cg list-domains` after saving `domains.proposed.yaml` shows more domains than were in `domains.yaml`.
- A domain appears in the wiki index that was only in the proposed file.
- `git log domains.yaml` shows a commit that "renames domains.proposed.yaml" without any human-review step.

**Phase to address:**
`graph propose-domains` phase. The allowlist constraint in `graph_io.packages.refresh` must be added in the same commit that introduces `domains.proposed.yaml` generation. Add the isolation test before the command ships.

---

### Pitfall 9: Concurrent Scan Processes Racing on /entities/ Writes

**What goes wrong:**
Two `graph-wiki-agent scan` processes run in quick succession (or in parallel in a CI fan-out). Both read the current entity set from the graph, both compute diffs, both write to `/entities/`. The second write can overwrite the first's output, or both can write the same entity file simultaneously, producing a torn write or a file containing a mixture of the two outputs.

The existing `SubagentPool` concurrency is within-command (multiple scanner subagents within one scan call, each writing to different pages). The race here is between two separate `run_scan` calls.

**Why it happens:**
The SQLite graph DB uses `GRAPH_WIKI_LOCK_TIMEOUT_MS` to serialize concurrent `cg update` writes. But the entity-page writes happen after the graph read, in the Python layer, without any filesystem-level lock. Two processes can both open the same entity `.md` file for writing without knowing about each other.

**How to avoid:**
The simplest mitigation for a single-user project: document that `run_scan` must not be called concurrently from the same workspace. The existing `append_log` call at scan start provides a lightweight in-process record but does not prevent concurrent external invocations.

A stronger mitigation: acquire a workspace-scoped lock file (`.graph-wiki/scan.lock`) at the start of `run_scan` using `fcntl.flock` (POSIX) with a `LOCK_EX | LOCK_NB` flag. If the lock is already held, fail immediately with a clear error: "Another scan is in progress for this workspace."

Since this is a single-user personal project and the vault is disposable, the lightweight mitigation (document + lock file) is acceptable. The lock file prevents accidental double-invocation (e.g., from a watcher script and a manual run) without requiring heavy coordination.

**Warning signs:**
- An entity page content is truncated or contains mixed content from two different scan outputs.
- `git diff` after a scan shows a file that was written but immediately overwritten by a second write in the same second (mtime collision).

**Phase to address:**
Entity writer phase. Add the lock file as a must_have in the phase plan. Keep it simple: `fcntl.flock` or equivalent, fail-fast on contention, no retry.

---

### Pitfall 10: One-Shot Migration Script Leaving Artifacts on Re-Run

**What goes wrong:**
The inbound-link migration script (Q3) is designed to run once at vault cutover. If it is re-run accidentally (e.g., after a git reset to before the migration, or by a user who forgot it had already run), it:

- Rewrites already-migrated links a second time, producing double-encoded paths: `[[entities/entities/pkg__agent-research__graph-io]]`.
- Inserts duplicate migration log entries into the wiki append-log.
- Attempts to rewrite wikilinks that a human manually adjusted after migration (their manual corrections get overwritten by the "original path → entity URI" mapping which is no longer correct).

**Why it happens:**
Migration scripts that are "run once" are rarely defended against re-runs in initial implementations, because the happy path is the only path tested.

**How to avoid:**
The migration script must be idempotent by design:
1. The rewrite regex must only match the old format (paths starting with `packages/`, `concepts/`, etc.), not the new entity format. Links that have already been migrated (`[[entities/...]]`) must not match.
2. Before writing any file, check if the page already contains any `[[entities/` links. If it does, log "already migrated, skipping" and skip the file rather than re-processing it.
3. Write a migration state marker: after completing the migration, write a `migration_completed_at:` key to the wiki manifest (`.graph-wiki.yaml`). The script reads this key at startup and aborts with "already run on {date}" if it is present.

Test: run the migration twice on a vault with both migrated and unmigrated pages; assert the second run is a no-op (no file changes, no manifest changes beyond idempotent re-writes).

**Warning signs:**
- After re-running the script, `git diff` shows double-encoded entity paths: `[[entities/entities/...]]`.
- The wiki append-log has two "migration completed" entries with different timestamps.

**Phase to address:**
One-shot inbound-link migration phase (Q3). Idempotency must be in the acceptance criteria. Write the re-run test before the migration runner.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Rewrite full frontmatter block on every scan | Simple implementation | Silently destroys human-authored keys (Pitfall 2) | Never — the whitelist merge adds ~10 lines and prevents data loss |
| Use regex substring match for wikilink rewrite without Markdown tokenization | Simple one-liner | Rewrites links inside code blocks, breaks documentation examples (Pitfall 4) | Never — code-block exclusion is non-negotiable |
| Generate index without write-if-changed guard | Simpler writer | Every scan dirtied git history even when nothing changed (Pitfall 5) | Never — 3-line guard prevents it |
| Skip cycle detection on LLM domain proposals | Simpler output processing | LLM-generated cycles crash `cg update` when a human applies the proposals (Pitfall 7) | Never — cycle detection is a unit test, not a big-bang effort |
| Slug encode by replacing `:` and `/` with `-` | Human-readable slugs | Collision space across URI kinds (Pitfall 1) | Only if a collision-free proof exists for the actual URI namespace in use |
| Hard-delete without checking if human has edited the page body | Cleaner implementation | Permanently loses human-authored narrative (Pitfall 3) | Only with explicit user-facing warning and append-log record of every deletion |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| graph-io URI → entity filename | Naive separator replacement causes collisions | Collision-free encoding using `__` for `:` and `/`, with property test over all URI kinds |
| Scanner relation frontmatter + human frontmatter | Full-block rewrite discards human keys | Merge strategy: only overwrite scanner-owned keys (frozenset constant); preserve all others |
| `domains.proposed.yaml` + `cg update` | Parser reads both proposed and authored files | Hard allowlist in `graph_io.packages.refresh`; schema-level differentiation (`proposed_domains:` vs `domains:`) |
| Migration script + git history | Re-run produces double-encoded links | Idempotency guard: manifest marker + regex that only matches old-format links |
| Index generation + git | Unconditional write churns history | Write-if-changed guard + deterministic sort order |
| `cg domain-clusters` + small sparse graph | Standard clustering produces one blob | Hub-exclusion pre-processing + degenerate cluster warning output |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Entity writer reads every existing entity file on each scan to merge frontmatter | Scan time scales linearly with vault size | Cache the entity frontmatter read in a single pass at scan start; only write pages that changed | At ~500 entity pages (not an issue for this repo today, but addressable from the start) |
| Index generator walks the entire graph on every call | Index update takes longer than the scan itself | Generate index in the same graph connection used for entity writes; no separate graph open | Immediately noticeable if graph has more than a few hundred nodes |
| Migration script reads every Markdown file in vault sequentially | Migration takes minutes on large vaults | Not a v1.8 concern (agent-research vault is small), but document the O(n) complexity | At ~2000 pages |

---

## "Looks Done But Isn't" Checklist

- [ ] **Slug encoder:** Property test with 1,000 synthetic URIs from all admitted kinds asserts all slugs are unique — run before any entity writer code is called.
- [ ] **Frontmatter merge:** Test that writes a page with human `status: deprecated`, runs the entity updater, and asserts `status: deprecated` is preserved.
- [ ] **Hard-delete policy:** Phase plan spec explicitly states the deletion behavior (hard-delete with log, or warn-and-stale) and the test covers the "human-edited body" case.
- [ ] **Migration idempotency:** Second run of the migration script produces zero file changes (verified by `git diff` returning empty).
- [ ] **Index determinism:** Two calls to the index generator with the same graph data but different entity-insertion order produce byte-identical output.
- [ ] **`domains.proposed.yaml` isolation:** `cg list-domains` after placing a `domains.proposed.yaml` in the workspace root returns the same result as with only `domains.yaml`.
- [ ] **Degenerate cluster warning:** Running `cg domain-clusters` on the `agent-research` monorepo itself (known-small sparse graph) either produces meaningful clusters or emits the "cluster degenerated" warning — it never silently produces a useless single-cluster result.
- [ ] **Proposal grounding check:** Every package name in `domains.proposed.yaml` appears in `graph_io.queries.list_packages` output — validated before the file is written.
- [ ] **Migration code-block exclusion:** Test page with a wikilink inside a fenced code block is left unchanged after migration.
- [ ] **Workspace lock:** Running two `graph-wiki-agent scan` calls simultaneously from the same workspace produces a clear error on the second call, not a silent race.

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Slug collision silently overwrites entity page | MEDIUM | Detect: count entity pages < expected graph node count. Recover: delete `/entities/`, re-run scan with corrected slug encoder. |
| Human frontmatter keys deleted by scanner | LOW (vault is disposable) | Recover: `git checkout HEAD~1 -- wiki/entities/` to restore last pre-scan state, then re-run with corrected merge logic. |
| Hard-delete destroys human-edited narrative | LOW (vault is disposable, but the prose is gone) | Recover: `git log --follow wiki/entities/<page>.md` to find the last commit before deletion; `git show <sha>:wiki/entities/<page>.md` to retrieve prose. Document: always commit before scan. |
| Migration double-encodes links | LOW | Detect: grep for `[[entities/entities/` in vault. Recover: run the inverse regex pass to undo double-encoding. |
| `domains.proposed.yaml` accidentally applied | LOW | Detect: `cg list-domains` shows unexpected domains. Recover: `git checkout domains.yaml` to restore authored file; `cg update --full` to rebuild graph. |
| LLM proposal contains hallucinated package names | NEGLIGIBLE | Detect: validation layer rejects before writing. Recover: re-run `graph propose-domains` with corrected grounding. |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| URI slug collisions (P1) | URI-keying / entity writer phase | Property test: 1,000 URIs → all slugs unique |
| Frontmatter key collision (P2) | Scanner relation-frontmatter phase | Merge test: human keys survive entity update cycle |
| Hard-delete losing human edits (P3) | Hard-delete reconciliation phase (Q2) | Test: page with human body content — deletion behavior matches spec |
| Migration regex over-matching (P4) | Inbound-link migration phase (Q3) | Code-block exclusion test; alias preservation test; idempotency test |
| Index churn (P5) | Scanner-generated index phase (Q5) | Determinism test; write-if-changed test |
| Degenerate import clusters (P6) | `cg domain-clusters` phase | Test on `agent-research` itself; degenerate warning test |
| LLM hallucinating package names (P7) | `graph propose-domains` phase | Grounding check test; cycle detection test |
| `domains.proposed.yaml` auto-applied (P8) | `graph propose-domains` phase (same commit) | Isolation test: proposed file doesn't affect `cg list-domains` |
| Concurrent scan race (P9) | Entity writer phase | Lock file test: second scan returns error |
| Migration script re-run artifacts (P10) | Inbound-link migration phase (Q3) | Re-run test: second invocation is a no-op |

---

## Sources

- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py` — existing scan pipeline shape, stale-tag behavior, graph connection lifetime pattern, `ScanAbortedError` / `NOT_INITIALIZED` fallback paths
- `packages/wiki-io/src/wiki_io/layout_io.py` — existing sentinel-delimited injection pattern for layout blocks; coexistence model with surrounding frontmatter content; hand-rolled YAML emitter/parser shape
- `.planning/research/ONTOLOGY-SPEC.md` — §9 scanner pipeline (9 stages), domain inference strategies (strategies 3 & 4), URI identity principle (§8), cycle detection constraint for `domain_contains_domain`
- `.planning/research/questions.md` — Q1 (URI keying), Q2 (reconciliation), Q3 (migration), Q4 (pipeline scope), Q5 (index generation) as the load-bearing pre-research inputs
- `.planning/milestones/v1.7-research/PITFALLS.md` — Pitfall 4 (URI identity drift), Pitfall 12 (orphaned pages on URI change), Pitfall 3 (ToolMessage serialization) as prior-milestone context; not restated here since they are resolved concerns
- `.planning/notes/wiki-entity-restructure-design.md` — two-lane layout (entities + curated), edges-as-frontmatter design, per-kind templates, Q2 policy ("dangling-link risk accepted"), disposable vault constraint
- `.planning/PROJECT.md` — v1.8 target features 1-10, `domains.yaml` remains authoritative, `domains.proposed.yaml` never auto-applied policy, format-compatibility constraint relaxed, wipe-and-rebuild acceptable
- `.planning/RETROSPECTIVE.md` — v1.0 "port verbatim" lesson; v1.2 "spec-only phase catches foundational reframe before port"; v1.1 "architectural restraint — smallest delta that closes gap"; v1.2 Phase 15 "discovered stale `cores/` reference by running the agent, not by memory"

---
*Pitfalls research for: v1.8 Wiki Entity Restructure*
*Researched: 2026-05-26*
