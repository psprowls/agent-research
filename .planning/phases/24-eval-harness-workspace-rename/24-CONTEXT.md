# Phase 24: eval-harness-workspace-rename - Context

**Gathered:** 2026-05-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Hard-rename the **eval-harness package** to the v1.4 naming convention: `workspace_path` everywhere a workspace root is meant, `wiki` everywhere the wiki directory itself is meant, and zero residual `vault_path` / `--vault` / `vault:` occurrences in `packages/eval-harness/src/`.

Surfaces in scope:

- **`sweep.py` (WSEVAL-01)** — `vault_path: Path` parameter on 7 functions (lines 231, 365, 387, 417, 442, 479, 708) → `workspace_path: Path`. Each function derives `wiki = workspace_io.paths.wiki_dir(workspace_path)` at top; existing `EvalWorktree(vault_path)` call sites (lines 260, 534) become `EvalWorktree(wiki)`; the `workspace_path=vault_path` kwargs at lines 377/403/431/468 collapse to `workspace_path=workspace_path` (no derivation needed for command-side calls because commands accept the workspace themselves).
- **`baseline.py` (WSEVAL-02)** — Module-level docstring (line 25), `_vault_content_hash(vault_path)` at line 241 → `_wiki_content_hash(wiki: Path)` operating on the wiki dir; class field `self._vault_path` (line 295) → `self._workspace_path`; argparse flag `--vault` (line 404) → `--workspace`; `vault_path=args.vault` (line 412) → `workspace_path=args.workspace`; the `"vault_content_hash"` baseline JSON output key (line 320) → `"wiki_content_hash"` (matches the helper rename and the actual semantic).
- **`structural.py` (WSEVAL-02)** — `_resolve_citation(slug, vault_path)` (line 25) + `check_structural(result, vault_path)` (line 46): public param renames to `workspace_path: Path`, derives `wiki = wiki_dir(workspace_path)` at function top, internal glob/exact-match uses `wiki / f"{slug}.md"` and `wiki.glob(f"**/{base}.md")`. Docstrings + comments cleaned.
- **`divergence/{linter,ingestor,scanner,code_reader,synthesizer,librarian,metric}.py` (WSEVAL-03)** — All bare `vault: Path` parameters in check functions and `divergence_score(..., vault: Path, ...)` (metric.py line 52, 81) → `wiki: Path`. These already semantically receive the wiki dir; this is a pure rename to match. Docstrings/comments cleaned (incl. `librarian.py:6` module docstring).
- **`isolation.py` (folded-in cleanup)** — `EvalWorktree.__init__(self, source_vault: Path)` (line 36) → `source_wiki: Path`; `self._source = source_vault` (line 37) → `self._source = source_wiki`; threat-mitigation comment (line 12) updated. Docstring already says "copies the source wiki into a fresh tmpdir laid out as a workspace" — code is just catching up.
- **Tests (WSEVAL-04)** — 194 `vault_path` / `vault:` references across `conftest.py`, `eval_helpers.py`, `test_sweep.py`, `test_baseline.py`, `test_structural.py`, `test_divergence*.py`, `test_isolation.py`, `test_two_gate_scorer.py`, `eval/test_sweep_eval.py`. `EvalWorktree` test callers update to `source_wiki=`. `fixture_vault_path` fixture in `test_structural.py` may rename to `fixture_wiki_path` (or `fixture_workspace_path` — see D-06).
- **`eval/README.md` (WSEVAL-05)** — Lines 39, 41, 50, 59, 69 use `--vault`; lines 95, 103, 104 mention `vault_content_hash`. All → `--workspace` / `wiki_content_hash`.
- **Brand-gate extension (eval-shapes)** — `scripts/check-brand.sh` gains 3 new regex bans targeted at eval-harness shapes (see D-07).

**Explicitly NOT in this phase:**
- `vault-io` package directory and `vault_io` module path — milestone-level lock (Phase 22 D-10).
- Pydantic Field name `vault_path:` — already banned by Phase 23's brand-gate; nothing in eval-harness uses Pydantic Fields.
- Typer flag `--vault` — already banned by Phase 23's brand-gate; eval-harness uses argparse, not Typer.
- Scan JSON output `"vault_path"` key — Phase 23 already cut over (`wiki_relative_path`).
- `packages/` misclassification fix — Phase 25.

</domain>

<decisions>
## Implementation Decisions

### Semantic Convention (workspace vs wiki)
- **D-01:** **Param=workspace_path, internals derive wiki via `wiki_dir()`.** Every public function in sweep/baseline/structural accepts `workspace_path: Path` (matches v1.4 milestone convention exactly — "workspace_path everywhere a workspace root is meant"). First line of each function: `wiki = workspace_io.paths.wiki_dir(workspace_path)`. The wiki-operating internals (rglob `*.md`, citation resolution, EvalWorktree copy source) all operate on `wiki`, not on `workspace_path`. This produces a clear boundary: callers think in workspaces, internals think in wikis.
- **D-02:** **`_vault_content_hash` → `_wiki_content_hash(wiki: Path)`.** Resolves the REQ's open semantic ("choose the semantic that matches usage" — WSEVAL-02). The helper operates on a wiki directory (rglobs `*.md` from the wiki root), so name it `wiki` not `workspace`. The baseline JSON output key also renames to `"wiki_content_hash"` for symmetry — this is a baseline format change, not just a Python rename.
- **D-03:** **Divergence helpers take bare `wiki: Path`** (matches WSEVAL-03 literal). Different convention from sweep/baseline (which take `workspace_path`) because divergence checks are called from within an EvalWorktree where only the wiki path is available — there's no workspace concept at that layer.

### EvalWorktree Source Param Rename (folded-in cleanup)
- **D-04:** **`source_vault` → `source_wiki`** in `isolation.py:36`. Aligns with the docstring's own description ("copies the source wiki into a fresh tmpdir"), matches D-01's semantic decision, and removes the last `vault` reference in `eval-harness/src/`. SC#5 (`grep -r "vault_path\|vault:" packages/eval-harness/src` returns 0) demands this — without it, `source_vault:` in isolation.py would still match the `vault:` pattern from SC#5.

### Plan Chunking
- **D-05:** **Big-bang single plan** — mirrors Phase 22 D-03 and Phase 23 D-01. WSEVAL-01..05 + EvalWorktree `source_wiki` + brand-gate extension + all 194 test refs land in one plan and one commit. Trade-off: large commit, bisect-hostile, but eliminates ordering risk between the API rename + test sweep + helper rename. No Pydantic/Typer surfaces to make intermediate states uncompilable — pytest is the only gate — but the test sweep is large enough that splitting would create a window where the test refs are red while the src side is already green.
- **D-06:** Plan gate is `uv run --package eval-harness pytest` green (per ROADMAP.md SC#1). Optionally also `uv run pytest` workspace-wide to confirm no cross-package regression (the rename surface is local to eval-harness, but `baseline.py` is invoked via `python -m eval_harness.baseline` and the argparse flag rename is a behavior change for any external caller).

### Brand-Gate Extension (eval-shape patterns)
- **D-07:** **Extend `scripts/check-brand.sh` with eval-shape regex bans.** Add 3 new rules scoped to packages/eval-harness:
  1. **`vault_path:` as a function parameter** — regex `def\s+\w+\([^)]*\bvault_path:\s*Path` (catches param-name reintroductions).
  2. **`vault: Path` as a bare parameter** — regex `def\s+\w+\([^)]*\bvault:\s*Path` (catches the divergence-helper shape).
  3. **`"--vault"` as an argparse literal** — regex `"--vault"` (catches the argparse flag shape; will also catch test strings asserting on the OLD name, so allowlist seeding for any such tests).
  - Scope: `packages/eval-harness/{src,tests}`. (Tests included because reintroducing `vault: Path` in test code would defeat the rename.)
  - `.planning/` excluded — historical phase docs (this CONTEXT.md, REQUIREMENTS.md, milestone summaries) legitimately reference the old name.
  - `.brand-grep-allow` seeded with any unavoidable historical refs that surface during the dry-run (e.g., a test asserting on the old argparse flag's removal would be allowlisted if needed).
  - Integrates with existing brand-gate structure (extend `check-brand.sh`, not a sibling script).

### Carried Forward (milestone-level locks — non-negotiable)
- **D-08:** Hard rename, no back-compat shims. No deprecation period for `vault_path` kwargs, `--vault` argparse, or `_vault_content_hash` helper. (Phase 22 D-07, Phase 23 D-05.)
- **D-09:** Wiki path always derived via `workspace_io.paths.wiki_dir(workspace_path)` — never string concatenation. (Phase 22 D-09, Phase 23 D-06.)
- **D-10:** `vault-io` package directory and `vault_io` module path STAY. Only nomenclature changes inside eval-harness, not module renames anywhere else. (Phase 22 D-10.)
- **D-11:** Baseline JSON output key change (`vault_content_hash` → `wiki_content_hash`) is a recording format change. Existing baseline JSON files on disk will have the OLD key. Either:
  - (a) Regenerate baselines after this phase, OR
  - (b) The baseline replay code accepts EITHER key during a short transition window.
  Default per the no-shim posture: **(a) regenerate**. Document in SUMMARY.md as a manual UAT step ("regenerate baselines via `python -m eval_harness.baseline --cases ... --workspace ...`").

### Claude's Discretion
- The order of file edits within the big-bang plan is mechanical (executor's call).
- The exact wording of updated docstrings/comments (e.g., "Path to the workspace root" vs "Path to the workspace directory") is at executor's discretion as long as the `vault` term is purged.
- Brand-gate regex implementation details (exact regex, allowlist seeds for any false-positives surfaced during dry-run) are executor's call within the constraint of D-07's three target shapes.
- Whether to rename `fixture_vault_path` → `fixture_wiki_path` or `fixture_workspace_path` in `test_structural.py` is executor's call; either is consistent (fixture semantically holds a wiki dir today, but tests pass it as the `workspace_path` kwarg post-rename — pick whichever reads cleanest at the call sites).
- Whether to migrate `baseline.py`'s argparse to Typer is OUT OF SCOPE (scope creep — argparse rename only).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Milestone requirements (locked decisions)
- `.planning/REQUIREMENTS.md` §"eval-harness Workspace Rename (WSEVAL)" — WSEVAL-01 through WSEVAL-05 acceptance criteria
- `.planning/ROADMAP.md` §"Phase 24: eval-harness-workspace-rename" — goal + 5 numbered success criteria

### Files in the rename surface
- `packages/eval-harness/src/eval_harness/sweep.py` — 7 `vault_path` parameters (lines 231, 365, 387, 417, 442, 479, 708) + 2 `EvalWorktree(vault_path)` call sites (lines 260, 534) + 4 internal `workspace_path=vault_path` kwargs (lines 377, 403, 431, 468)
- `packages/eval-harness/src/eval_harness/baseline.py` — `_vault_content_hash` (line 241) → `_wiki_content_hash`; `self._vault_path` (line 295) → `self._workspace_path`; argparse `--vault` (line 404); `"vault_content_hash"` JSON key (line 320) → `"wiki_content_hash"`
- `packages/eval-harness/src/eval_harness/structural.py` — `_resolve_citation` (line 25), `check_structural` (line 46) — both take `workspace_path`, derive `wiki = wiki_dir(workspace_path)`
- `packages/eval-harness/src/eval_harness/isolation.py` — `EvalWorktree.__init__(self, source_vault)` (line 36, 37) → `source_wiki`; threat-mitigation comment (line 12)
- `packages/eval-harness/src/eval_harness/divergence/{linter,ingestor,scanner,code_reader,synthesizer,librarian,metric}.py` — bare `vault: Path` → `wiki: Path` (per WSEVAL-03)
- `packages/eval-harness/tests/{conftest.py,eval_helpers.py,test_sweep.py,test_baseline.py,test_structural.py,test_divergence*.py,test_isolation.py,test_two_gate_scorer.py,eval/test_sweep_eval.py}` — 194 vault references
- `eval/README.md` — argparse flag + JSON key references
- `scripts/check-brand.sh` — existing brand-gate to extend (per D-07)
- `.brand-grep-allow` — allowlist file at repo root

### Helper used by all renames
- `packages/workspace-io/src/workspace_io/paths.py::wiki_dir(workspace_path) -> Path` — canonical wiki-derivation function. Every public function in sweep/baseline/structural calls this. (Already exists; no implementation work.)

### Prior phase artifacts (milestone locks + pattern alignment)
- `.planning/phases/22-workspace-api-internal-rename/22-CONTEXT.md` — milestone locks: hard rename (D-07), `wiki_dir` helper (D-09), `vault-io` stays (D-10)
- `.planning/phases/22-workspace-api-internal-rename/22-01-SUMMARY.md` — big-bang plan execution pattern
- `.planning/phases/23-workspace-api-external-rename/23-CONTEXT.md` — brand-gate D-03 precedent; bootstrap-only --repo D-02; integration test gate D-04
- `.planning/phases/23-workspace-api-external-rename/23-01-PLAN.md` — brand-gate extension implementation pattern

### Prior milestone precedent
- `.planning/milestones/v1.3-ROADMAP.md` Phase 21 (graph-wiki-agent rename) — atomic-rename pattern with brand-gate extension and allowlist
- `.planning/milestones/v1.3-ROADMAP.md` Phase 12 (lattice → graph-wiki brand) — brand-gate-driven rename precedent

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `workspace_io.paths.wiki_dir(workspace_path: Path) -> Path` — already in place; this is the same helper used by Phases 22 and 23. Every public function in eval-harness post-rename calls it at the top.
- `scripts/check-brand.sh` is the working brand-gate (post-Phase 23). Adding 3 new regex bans extends an existing structure that already takes an allowlist, walks `packages/`/`agents/`/`plugins/`, and exits non-zero on hit.
- `.brand-grep-allow` already exists at repo root with allowlist patterns from Phases 12, 21, and 23.

### Established Patterns
- All 7 `vault_path` parameters in `sweep.py` follow the same signature shape (`vault_path: Path` as kwarg). Mechanically uniform rename.
- All 5 divergence-helper modules follow the same `def _check_*(output: AgentOutputProxy, vault: Path) -> Verdict` shape. Mechanically uniform.
- Phase 22/23 set the precedent that this milestone uses big-bang plans for rename surfaces, not split plans.
- The semantic convention "param = workspace, internals derive wiki" is exactly what `agents/graph-wiki-agent/src/graph_wiki_agent/commands/*.py` already does post-Phase 22 — eval-harness aligns with that pattern.

### Integration Points
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/*.py` already accepts `workspace_path` kwarg (Phase 22 work). The sweep.py call sites at lines 377/403/431/468 currently pass `workspace_path=vault_path` — these collapse to `workspace_path=workspace_path` post-rename. (No call-edge change, only the local var name changes.)
- `EvalWorktree(self._vault_path)` at `baseline.py:342` and `EvalWorktree(vault_path)` at `sweep.py:260, 534` — these pass the source wiki, which gets copied. Post-rename: `EvalWorktree(wiki)` where `wiki = wiki_dir(workspace_path)` is computed at the top of the enclosing function.
- `baseline.py` is invoked via `python -m eval_harness.baseline` (argparse, not Typer). External callers (CI? scripts?) using `--vault` would break post-rename. Per D-08 (no shim), this is accepted. Search the repo for `--vault` literals in CI / scripts as part of execution to confirm no surprises.
- `eval/README.md` is the user-facing doc for the eval harness; the `--vault` references there are user instructions, so the rename has a documentation correctness component beyond just code.
- Existing baseline JSON files on disk have `"vault_content_hash"` as their key. Per D-11, these are regenerated post-phase, not back-compat-supported.

</code_context>

<specifics>
## Specific Ideas

- "Param = workspace_path, internals derive wiki via `wiki_dir()`" is the exact pattern Phase 22 established for the command layer — this phase aligns eval-harness with that pattern. Pat preferred this over "param=wiki_path everywhere" because the milestone's own naming rule says workspace_path goes wherever a workspace root is meant, and the eval-harness public surface is the workspace boundary even though its internals operate on the wiki dir.
- "Fold in EvalWorktree.source_vault" is a deliberate scope expansion beyond WSEVAL-04's literal file list — Pat preferred completing the rename (SC#5's "zero hits" goal) over preserving a strict REQ-literal interpretation that would have left `source_vault:` as a residual `vault:` token.
- "Wiki content hash" (not "workspace content hash") for the helper rename is the semantic match per WSEVAL-02's own escape clause ("or hashes the wiki dir specifically"). The helper actually operates on the wiki dir (`rglob *.md` from the wiki root), so naming it `wiki_content_hash` matches usage. The output JSON key follows the helper name for symmetry, accepting that this is a baseline-format breaking change.
- "Brand-gate extension with eval shapes" was a deliberate ratchet expansion — Pat preferred catching the eval-specific param shapes (bare `vault: Path`, function param `vault_path:`, argparse literal) in CI rather than relying on the one-shot SC#5 grep at phase close. The allowlist seeding handles any false positives surfaced at dry-run time.

</specifics>

<deferred>
## Deferred Ideas

### Out of v1.4 milestone (later)
- Migrate `baseline.py` argparse → Typer (consolidation opportunity; not a rename concern)
- Rename `vault-io` package directory + `vault_io` module path to `wiki-io` / `wiki_io` — explicitly locked OUT of v1.4 milestone (Phase 22 D-10)
- `_SLUG_ONLY_RE` parity fix at `librarian.py:21` — out-of-scope observation from v1.3 Phase 19 (already noted in REQUIREMENTS.md "Future Requirements")
- Add an explicit unit test asserting that the OLD argparse flag `--vault` is rejected (success-via-error) — relying on the no-shim posture as implicit coverage instead

### Phase 25 (packages-dir-misclassification-fix)
- The pending todo `2026-05-20-fix-packages-dir-misclassification` — `_classify_dir` heuristic + `--interactive` opt-in on bootstrap (independent of Phase 24)

</deferred>

---

*Phase: 24-eval-harness-workspace-rename*
*Context gathered: 2026-05-20*
