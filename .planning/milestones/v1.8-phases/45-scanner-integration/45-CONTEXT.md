# Phase 45: Scanner Integration - Context

**Gathered:** 2026-05-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Wire the Phase-43 entity writer + Phase-44 index generator into the agent-research `scan` command's `run_scan` loop. After Phase 45 lands, every scan against the agent-research vault produces entity pages at `wiki/entities/` (graph-driven), a consolidated `wiki/index.md` (graph-entities + curated lanes), and per-folder curated sub-indexes (`wiki/concepts/index.md`, etc.). Legacy `wiki/packages/<name>/<name>.md` writes are removed in this phase; stale legacy pages from prior scans linger until Phase 46 cutover deletes the directories.

**Code surface modified:**
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py::run_scan` — Step 5 (load), Step 7 (diff), Step 9 (splits into 9a/9b), Step 10 (write narrative), Step 11 (deletion branching), Step 12 (index regeneration).
- `packages/wiki-io/src/wiki_io/entity_writer.py` — adds `inject_narrative(page_path, prose)` helper.
- `packages/wiki-io/src/wiki_io/update_index.py` — surgical change: skip the `wiki/index.md` write (now owned by `generate_index`); continues writing per-folder `*/index.md` sub-indexes.
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py` — new `build_entity_narrative_prompt(entity_node, file_map_text)` helper.
- `agents/graph-wiki-agent/models.toml` (or equivalent) — new `narrator` role (separate from existing `scanner` role).
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py::ScanResult` — likely needs an `entity_added: list[str]` / `entity_updated: list[str]` field for URI-keyed reporting (Claude's discretion on exact shape).

**Code surface NOT modified:**
- `plugins/graph-wiki/scan_monorepo.py` — the legacy plugin's scan stays on the legacy layout in Phase 45. Two independent code paths during transition. Future-phase TBD.
- `packages/wiki-io/src/wiki_io/scan_monorepo.py` — separate from the agent command's scan; not in Phase 45 scope unless `_load_existing_pages` lives there (verify in research).

**Phase 44 D-02 partial supersedence.** Phase 44 CONTEXT.md D-02 said "ONE index, no per-folder `*/index.md` sub-indexes; `update_index.py` deleted in Phase 46 cutover." Phase 45 D-01/D-02 (below) revise this: `update_index.py` survives, its `wiki/index.md` write is removed, but per-folder sub-indexes remain. Phase 46 cutover does NOT delete `update_index.py` or per-folder `*/index.md` files. `wiki/index.md` content (graph entities + full curated listings) remains as Phase 44 specified.

**Phase 46 ripple (must record in Phase 46 CONTEXT.md when discussed):**
- Cutover deletes `wiki/packages/`, `wiki/dependencies/`, `wiki/domain/`, `wiki/plugin/`, `wiki/package-family/` directories (stale entity-equivalents only — curated lanes preserved).
- Cutover does NOT delete `wiki/concepts/index.md`, `wiki/adrs/index.md`, `wiki/sources/index.md`, `wiki/architecture/index.md`, `wiki/dependencies/index.md` — those still flow through `update_index.py` per Phase 45 D-02 (overrides Phase 44 D-02).
- Cutover does NOT delete `update_index.py`.
- Plugin's `plugins/graph-wiki/scan_monorepo.py` is still on legacy layout; cutover-time decision pending.

**Not in scope (Phase 45):**
- Inbound wikilink rewriting (Phase 46).
- Old-directory removal (Phase 46 cutover commit).
- LLM narrator prompt-engineering iteration on real entity pages — the prompt is a viable v1, refinement is a v1.9 task.
- New evals for narrator quality — current scanner eval scaffolding is reused.

</domain>

<decisions>
## Implementation Decisions

### Index wiring (Step 12)

- **D-01:** **Step 12 calls two writers, on disjoint file scopes.**
  ```python
  # Step 12: regenerate indexes
  index_generator.generate_index(conn, wiki)   # writes wiki/index.md (graph + curated full listings)
  update_index.update_index(wiki)              # writes per-folder concepts/index.md, adrs/index.md, ...
  ```
  Order: `generate_index` first (deterministic + write-if-changed per Phase 44 D-15/D-16). `update_index` second (legacy logic; its wiki/index.md write is removed). Both invocations stay; SCANINT-04 is rewritten to reflect this dual-call shape.

- **D-02:** **`update_index.py` surgical change in Phase 45.** Remove (or conditionally skip) the `wiki/index.md` write block inside `update_index(wiki)`. The function continues to write `concepts/index.md`, `adrs/index.md`, `sources/index.md`, `architecture/index.md`, `dependencies/index.md`. This is the minimum change to avoid two writers fighting over the same file. **Reverses Phase 44 D-02's "delete update_index.py in Phase 46"** — `update_index.py` survives indefinitely (or until a future phase replaces it).

- **D-03:** **SCANINT-04 rewritten (REQUIREMENTS.md update in this phase):**
  > Step 12 calls `index_generator.generate_index` to produce `wiki/index.md` (graph-entity sections + full curated-lane listings, per Phase 44 D-02/D-11/D-12) AND `update_index.update_index(wiki)` to produce per-folder `*/index.md` sub-indexes only. The `update_index` module's prior `wiki/index.md` write is removed.

  REQUIREMENTS.md edit must land as part of Phase 45 plan-01 task list (alongside the scan.py modifications).

### Entity page write path (Step 9 split)

- **D-04:** **Step 9 splits into 9a + 9b.**
  ```python
  # Step 9a: graph-driven entity page writes
  result = write_entities(conn, wiki, ADMITTED_KINDS_V18)
  # result.created, result.updated, result.deleted, result.unchanged, result.needs_narrative, result.errors

  # Step 9b: LLM narrator fan-out for entity URIs needing prose
  narrator_items = [entity_node_for(uri) for uri in sorted(result.needs_narrative)]
  pool = SubagentPool(trace_dir=wiki / ".graph-wiki" / "traces")
  narrator_llm = make_llm("narrator")  # new role
  narrator_result = await pool.run_all(items=narrator_items, task=generate_narrative, ...)
  ```
  Step 9a is synchronous, fast, deterministic. Step 9b is async, LLM-bound, gated on `needs_narrative_set`. Pool concurrency tuned per `narrator` role config.

- **D-05:** **`build_entity_narrative_prompt(entity_node, file_map_text)` — new prompt builder in `scan.py`.** Output spec: prose only (no frontmatter, no H1 — just the narrative body that lives between `## Narrative` and the next H2). Includes the entity's URI, kind, current graph-derived relations (depends_on, test_suites, etc.) as context; includes file_map_text for `package` kinds where available. The narrator's system prompt explicitly bans frontmatter emission. ~80–120 LOC.

- **D-06:** **New `narrator` role in `models.toml`.** Separate role per CLAUDE.md §2 (`model_adapter.make_llm(role)`); allows tuning narrator independently from `scanner` (e.g., cheaper model since it generates short prose). Initial config: same model as `scanner` for v1.8; revisit cost/quality in v1.9 eval.

- **D-07:** **`entity_writer.inject_narrative(page_path: Path, prose: str) -> None` helper.** Reads the entity page; locates the `## Narrative` heading; replaces the body up to the next H2 (or EOF) with `prose`; writes back. Idempotent: subsequent calls overwrite the prior narrative. Page-format knowledge stays in `entity_writer.py` (consistent with Phase 42 D-16). Step 10 calls this for each successful narrator response.

- **D-08:** **Step 10 (legacy package-page write block) is removed.** The current `Step 10: write successful stub pages` loop writing `wiki / vault_page_rel = packages/<name>/<name>.md` is deleted. Only entity pages are written from Phase 45 onward. Stale legacy pages remain on disk from earlier scans until Phase 46 deletes them.

### Deletion handling (Step 11)

- **D-09:** **Implicit deletion split via `write_entities`.** Step 9a's `write_entities.result.deleted` already covers entity-page hard-deletes for vanished graph nodes (Phase 43 D-16 / D-17 logic). Step 11's existing stale-tag loop (`for pkg_name in diff["deleted"]`) is left in place but becomes nearly a no-op for v1.8: most kinds the loop sees are entity-managed and have already been hard-deleted. Loop only fires for non-entity-kind names (scripts, entry_points if not entitified — none in v1.8 ADMITTED_KINDS_V18). No code change needed; the loop naturally degrades.

- **D-10:** **Renamed-package stale-tag loop kept as-is.** Phase 45 doesn't change rename handling. Renames in entity-land are NOT special: a renamed package = deleted-old-URI + created-new-URI in graph terms; `write_entities` handles each side independently (hard-delete old slug, create new). Step 11's existing "stale-tag renamed (old side)" loop continues to fire for the legacy-layout path until Phase 46 cutover.

### Load + diff (Step 5 / Step 7) — SCANINT-05

- **D-11:** **`_load_existing_pages` extended to walk `wiki/entities/`** with URI keying. Return shape becomes:
  ```python
  @dataclass(frozen=True)
  class ExistingPages:
      legacy: dict[str, dict]   # workspace-name → {wiki_relative_path, frontmatter, ...} (existing shape)
      entities: dict[str, dict] # URI → {path, frontmatter, ...} (new in Phase 45)
  ```
  Entity-side keys are URI strings (decoded from slug). Legacy-side keys remain workspace names. Two sub-dicts so `compute_diff` and downstream loops know which lane they're operating in.

- **D-12:** **`compute_diff` is NOT modified to compute entity diffs.** Entity-page lifecycle is owned by `write_entities` (Step 9a) — it queries the graph and the filesystem independently and produces its own `created/updated/deleted/unchanged` lists in `EntityWriteResult`. Phase 45's `compute_diff` continues to produce legacy diffs (`new/unchanged/deleted/renamed`) over workspace names. The two diff sources flow side-by-side in scan.py; no merge. This honors SCANINT-05's "entity pages key off URI, not filesystem path" without entangling the legacy diff machinery.

### Plugin smoke test (SCANINT-06)

- **D-13:** **Plugin (`plugins/graph-wiki/`) stays on legacy layout in Phase 45.** Its `scan_monorepo.py` and skill are NOT modified. The smoke test runs the plugin's scan against a legacy-layout fixture vault and asserts unchanged behavior (no entity pages produced; `wiki/packages/<name>/<name>.md` written; stale-tag on deletion). Two independent scan code paths during the transition.

- **D-14:** **No "plugin asserts new layout" test in Phase 45.** Acceptance is: plugin smoke (legacy layout) still passes; agent-research scan (entity layout) produces expected entity vault. The two test suites are independent. Future-phase decision (post-Phase-46) on whether the plugin gets upgraded or retired.

### ScanResult shape

- **D-15:** **`ScanResult` gains URI-keyed fields for entity reporting.** Current shape has `added/updated/deleted/renamed` as workspace-name strings. Phase 45 adds:
  ```python
  @dataclass
  class ScanResult:
      # Existing legacy fields (workspace names) — unchanged
      added: list[str]
      updated: list[str]
      deleted: list[str]
      renamed: list[tuple[str, str]]
      errors: list[str]
      state_gate: ...
      # New in Phase 45 (URIs):
      entities_created: list[str]      # from EntityWriteResult.created
      entities_updated: list[str]      # from EntityWriteResult.updated
      entities_deleted: list[str]      # from EntityWriteResult.deleted
      entities_narrated: list[str]     # URIs the narrator successfully generated prose for
      entity_errors: list[str]         # repr'd EntityWriteError + narrator errors
  ```
  Backward compatibility: legacy fields stay populated for any non-entity workspace processed (none in v1.8 ADMITTED_KINDS_V18 — these become empty lists in v1.8 unless `--legacy-only` is somehow invoked, which it isn't). CLI / downstream consumers that read `added`/`updated` get empty lists; they need to also check `entities_created` / `entities_updated`.

- **D-16:** **CLI output updates.** Step 13's final log entry / CLI summary updated to print both legacy and entity counts:
  ```
  scan complete: legacy +0 ~0 -0  |  entities +5 ~12 -1  (narrated: 8 of 17)
  ```
  Exact format is Claude's discretion. The point is both counts surface.

### Concurrency + locking

- **D-17:** **`write_entities`'s scan.lock (Phase 43 D-19) is acquired inside Step 9a.** scan.py does NOT add a top-level lock; `write_entities` already does. If two scans run concurrently, the second one hits `WriteLockHeldError` and aborts at Step 9a. No change to scan.py's lock handling needed.

- **D-18:** **`index_generator.generate_index` does NOT need the scan.lock** (Phase 44 D-20). It's read-only on the graph and the write target is `wiki/index.md`, which write_entities does not touch. Step 12 runs after Step 9a has released the lock; concurrency is fine.

### Module touch summary

- **D-19:** **Files modified in Phase 45:**
  - `agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py` — main wiring changes (Steps 5, 7, 9, 10, 11, 12, ScanResult, CLI output).
  - `packages/wiki-io/src/wiki_io/entity_writer.py` — adds `inject_narrative`.
  - `packages/wiki-io/src/wiki_io/update_index.py` — surgical: skip `wiki/index.md` write.
  - `agents/graph-wiki-agent/models.toml` — add `narrator` role.
  - `.planning/REQUIREMENTS.md` — rewrite SCANINT-04 per D-03.
  - Tests: new `agents/graph-wiki-agent/tests/test_scan_integration.py` (new), updates to existing scan tests for the new flow.

- **D-20:** **No new third-party dependencies.** All needed primitives exist (`langchain-aws`, `model_adapter`, `subagent_runtime`, `wiki_io.entity_writer`, `wiki_io.index_generator`).

### Claude's discretion

- Exact shape of `narrator` role config in `models.toml` (model_id, max_tokens, max_concurrency tuning).
- Whether `narrator` errors abort the scan or accumulate into `entity_errors` (lean: accumulate; partial-success per Phase 43 D-21 precedent).
- Exact word/format of CLI summary line (D-16).
- Whether the surgical `update_index.py` change uses a conditional flag (e.g., `write_main_index=False` parameter) or unconditionally drops the `wiki/index.md` block (lean: drop unconditionally — keeps `update_index.py` purely a sub-index writer).
- Exact prompt wording for `build_entity_narrative_prompt` (this is a prompt-engineering exercise; v1.8 needs a viable v1, not optimal).
- Whether `inject_narrative` reads the page via `python-frontmatter` or raw bytes (lean: raw bytes — frontmatter is preserved verbatim since we only touch the body).
- How file_map is sourced for non-`package` entity kinds in `build_entity_narrative_prompt` (lean: `package` only gets a file_map; other kinds get URI + graph relations only).
- Whether `ExistingPages` is a dataclass or two separate dicts returned via tuple (lean: dataclass, per Phase 43 / Phase 44 precedent).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Direct predecessors
- `.planning/phases/43-entity-writer/43-CONTEXT.md` — `write_entities` signature + return shape; `EntityWriteResult.needs_narrative`; scan.lock semantics; deletions.log. Phase 45 calls `write_entities` in Step 9a.
- `.planning/phases/44-scanner-generated-index/44-CONTEXT.md` — `generate_index` signature + return shape; consolidated `wiki/index.md` semantics. Phase 45 calls `generate_index` in Step 12. **Note D-02 partial supersedence per Phase 45 D-01/D-02 above.**
- `.planning/phases/42-uri-slug-scheme-per-kind-templates/42-CONTEXT.md` — `## Narrative` H2 convention (D-16); narrator prompt must produce content respecting this boundary.

### Milestone-level
- `.planning/REQUIREMENTS.md` §SCANINT — SCANINT-01..SCANINT-06. SCANINT-04 is rewritten in this phase per D-03.
- `.planning/ROADMAP.md` Phase 45 — Goal + 6 success criteria.
- `.planning/STATE.md` — Pitfall 9 (concurrent scan race) is handled by inheriting Phase 43's scan.lock (D-17). The Phase 44 blocker logged during execute attempt is informational; will clear once Phase 43 lands.

### Existing code (must be read by planner/researcher)
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py` — `run_scan` main flow; `build_stub_prompt` (template for the new narrator prompt builder); `_load_existing_pages`, `compute_diff`, `_add_stale_tag` patterns; `SubagentPool` fan-out usage.
- `packages/model-adapter/src/model_adapter/loader.py` — `make_llm(role)` pattern; how to wire the new `narrator` role.
- `packages/subagent-runtime/src/subagent_runtime/pool.py` — `SubagentPool.run_all` shape; narrator fan-out reuses this.
- `packages/wiki-io/src/wiki_io/entity_writer.py` (post-Phase 43) — `write_entities`, `EntityWriteResult`, `WriteLockHeldError`; new `inject_narrative` lands here.
- `packages/wiki-io/src/wiki_io/index_generator.py` (post-Phase 44) — `generate_index`, `IndexWriteResult`.
- `packages/wiki-io/src/wiki_io/update_index.py` — surgical edit target; the `wiki/index.md` write block is identified and removed.
- `plugins/graph-wiki/scan_monorepo.py` — NOT modified; reference only for understanding what stays on legacy layout.
- `agents/graph-wiki-agent/models.toml` — pattern for adding the new `narrator` role.

### Research baseline
- `.planning/research/ARCHITECTURE.md` §scan flow, §scanner role definitions.
- `.planning/research/PITFALLS.md` Pitfall 9 (concurrent scan) addressed by D-17.
- `.planning/research/FEATURES.md` §F4 (scanner frontmatter), §F5 (narrative LLM gating).

### Tests (where new Phase 45 tests land)
- `agents/graph-wiki-agent/tests/test_scan_integration.py` (new) — end-to-end Step-9a + Step-9b + Step-12 sequencing, using fixture graphs.
- Existing scan tests may need updating for the new flow — Phase 45 plan must enumerate.
- `plugins/graph-wiki/tests/` (or wherever the plugin smoke test lives) — verify it still passes unmodified (acceptance for SCANINT-06).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`scan.py::run_scan`** Step 9 fan-out pattern (`SubagentPool.run_all` + `make_llm("scanner")`) — Phase 45's Step 9b reuses the exact same pattern with `make_llm("narrator")` and a different prompt builder.
- **`scan.py::build_stub_prompt`** — template for `build_entity_narrative_prompt`. The new function is structurally similar (string template + workspace metadata) but emits prose-only instructions and a tighter output constraint.
- **`scan.py::_add_stale_tag`** — left untouched in Phase 45 (still fires for non-entity-kind deletions, per D-09); no changes needed.
- **`scan.py::_load_existing_pages`** — extended in Phase 45 to also walk `wiki/entities/`; existing legacy walk is preserved (D-11).
- **`update_index.py`** — surgical edit removes its `wiki/index.md` write; the function's per-folder sub-index logic (the `CATEGORY_INDEX_FILES` loop) is preserved.
- **`SubagentPool.run_all`** — generic fan-out primitive; reused for narrator without modification.

### Established Patterns
- **CLAUDE.md §2 — `make_llm(role)` returns `_GuardedChatBedrockConverse`.** New `narrator` role is added to models.toml (or equivalent) — Phase 45 inherits existing model-adapter machinery.
- **CLAUDE.md §8 — pytest + pytest-asyncio + syrupy.** Phase 45 tests are async (Step 9b LLM fan-out is async); reuse the project's async test conventions.
- **Phase 43 partial-success pattern (`EntityWriteResult.errors`).** Narrator failures should follow the same shape — append to `ScanResult.entity_errors` and continue.
- **Atomic write pattern** (Phase 44 D-16) — `inject_narrative` should also use temp-file + `os.replace` for the page rewrite.

### Integration Points
- **Step 9a → Step 9b handoff** is the `needs_narrative_set` returned by `write_entities`. This is the contract Phase 43 D-10 specified (page newly-created OR any STRUCTURAL_KEYS value changed).
- **Step 9b → Step 10 handoff** is `narrator_result.successes` — pairs of (entity_node, prose). Step 10 calls `inject_narrative` for each pair.
- **Step 12 ordering** is `generate_index` then `update_index` per D-01. No race because they touch disjoint files.
- **`write_entities` lock** is held only during Step 9a (D-17); Step 9b through Step 13 run outside the lock.

</code_context>

<specifics>
## Specific Ideas

- **Integration test on `agent-research` itself**: run the modified `scan` against the live agent-research vault; assert (a) every admitted graph node has a `wiki/entities/<slug>.md` page, (b) `wiki/index.md` has full graph + curated sections, (c) per-folder `concepts/index.md` etc. still exist and are updated, (d) no `wiki/packages/<name>/<name>.md` page is newly written (only stale pages from prior scans remain).
- **Plugin smoke regression**: run `plugins/graph-wiki/`'s smoke test against a fresh fixture vault; assert the legacy layout is produced as before (SCANINT-06 acceptance).
- **Narrator gating test**: fixture graph with 10 admitted nodes; first scan needs_narrative = 10 (all newly-created); second scan against same graph needs_narrative = 0; third scan after mutating one node's domain edge needs_narrative = {that one URI}. Verifies SCANINT-01 + Phase 43 D-10.
- **No-frontmatter narrator test**: mock narrator returns `---\nuri: hacked\n---\n\n## Narrative\n...`; assert `inject_narrative` discards the frontmatter region and only injects the body. Or even simpler: prompt-test that narrator's typical output doesn't include frontmatter (snapshot test against fixture entity input).
- **Concurrent-scan test (SCANINT inheriting Phase 43)**: spawn two scans simultaneously; assert second fails fast with `WriteLockHeldError`.
- **Two-writer index test (D-01)**: run Step 12; assert `wiki/index.md` exists (generate_index output) AND `wiki/concepts/index.md` exists (update_index output); assert their contents are coherent (the per-folder index matches the curated-section content in wiki/index.md).
- **ScanResult contract test**: ScanResult includes both `added` (legacy, empty in v1.8) and `entities_created` (URIs, populated). Snapshot the dataclass to lock the shape.

</specifics>

<deferred>
## Deferred Ideas

- **Upgrade `plugins/graph-wiki/scan_monorepo.py` to entity layout** — decision deferred to post-Phase-46 or v1.9. Two scan paths during transition is acceptable. The plugin may be retired if the agent-research scan covers all use cases.
- **Narrator quality eval / prompt tuning** — v1.9. Phase 45 ships a viable v1 prompt; refinement is post-restructure.
- **`narrator` cheaper-model exploration** — v1.9. Initial config uses same model as `scanner`; revisit when the eval scaffolding is updated for entity-page narration.
- **`compute_diff` graph-aware entity diff** — Phase 45 leaves `compute_diff` legacy-only; entity diffing lives inside `write_entities`. Could unify later if needed, but the two-source model is simpler in v1.8.
- **CLI flag to opt out of entity writes** (`--no-entities`) — not added in Phase 45. The hard cutover is intentional; coexistence-rollback is "git revert the scan.py changes" + delete `wiki/entities/`.
- **`update_index.py` retirement** — Phase 44 D-02 originally said delete in Phase 46. Phase 45 D-02 supersedes: `update_index.py` survives, just narrower. Future retirement (v1.9+) when per-folder sub-indexes can be generated from graph or dropped entirely.
- **`ScanResult.entities_*` field renames** — current shape (legacy + entities prefixes) is awkward; a future major version could collapse to a single `EntityRunReport` field. Not load-bearing in v1.8.

</deferred>

---

*Phase: 45-Scanner Integration*
*Context gathered: 2026-05-27*
