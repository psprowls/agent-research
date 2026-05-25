# Phase 24: eval-harness-workspace-rename - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-20
**Phase:** 24-eval-harness-workspace-rename
**Areas discussed:** Plan chunking, workspace_path vs wiki_path semantics, EvalWorktree source param rename, Brand-gate extension

---

## Area Selection

| Option | Description | Selected |
|--------|-------------|----------|
| Plan chunking | Big-bang single plan vs split (sweep+baseline vs divergence vs tests+README); eval-harness has no Pydantic/Typer surfaces so intermediate-state risk is lower than 22/23. | ✓ |
| workspace_path vs wiki_path semantics | REQ says 'or hashes the wiki dir specifically — choose the semantic that matches usage'. baseline._vault_content_hash rglobs *.md (operates on wiki dir, not workspace root). | ✓ |
| EvalWorktree source param rename | isolation.py:36 — `source_vault: Path`. Not in WSEVAL-04's literal list but it's a bare `vault` token. Fold into this phase or defer? | ✓ |
| Brand-gate extension | Phase 23 added 3 regex bans (Pydantic Field, Typer flag, scan JSON key). eval-harness has none of those shapes. Add eval-specific bans or skip? | ✓ |

**User's choice:** All four areas selected.

---

## workspace_path vs wiki_path semantics

| Option | Description | Selected |
|--------|-------------|----------|
| Param=workspace_path, internals derive wiki | Public param stays `workspace_path: Path`. First line: `wiki = workspace_io.paths.wiki_dir(workspace_path)`. Helper renames to `_wiki_content_hash(wiki: Path)`. Matches v1.4 milestone convention exactly. | ✓ |
| Param=wiki_path, no workspace concept inside eval | Rename `vault_path` → `wiki_path: Path` directly. Skip the workspace abstraction. Conflicts with WSEVAL-01/02 literal text. | |
| Param=workspace_path but pass-through unchanged | Rename param mechanically but don't derive wiki internally — rglob/EvalWorktree operate on whatever path the caller passes (named misleadingly). | |

**User's choice:** Param=workspace_path, internals derive wiki
**Notes:** Captured as D-01 + D-02 in CONTEXT.md. Produces clear boundary: callers think in workspaces, internals think in wikis. The `_vault_content_hash` helper renames to `_wiki_content_hash(wiki: Path)` to match the actual data it operates on; the baseline JSON output key follows for symmetry (`"wiki_content_hash"`), accepting the baseline-format breaking change.

---

## EvalWorktree source param rename

| Option | Description | Selected |
|--------|-------------|----------|
| Fold in — rename to source_wiki | Matches docstring ("copies the source wiki into a fresh tmpdir"), aligns with semantic decision, removes last `vault` reference in eval-harness src. | ✓ |
| Fold in — rename to source_workspace | Matches caller-side convention but inconsistent with docstring/semantic since EvalWorktree copies a wiki dir. | |
| Defer — leave source_vault as-is | Out of WSEVAL-04's literal scope; tackle in future cleanup. SC#5 (`grep -r 'vault:' src` returns 0) would still fail with `source_vault:` present. | |

**User's choice:** Fold in — rename to source_wiki
**Notes:** Captured as D-04 in CONTEXT.md. Deliberate scope expansion beyond WSEVAL-04's literal file list — completing the rename (zero residual vault tokens per SC#5) over strict REQ-literal interpretation.

---

## Plan chunking

| Option | Description | Selected |
|--------|-------------|----------|
| Big-bang single plan (carry forward) | One plan, one commit. WSEVAL-01..05 + EvalWorktree source_wiki + 194 test refs together. Matches 22/23 pattern. | ✓ |
| Two plans — src first, tests+README second | Plan A: src/ rename; Plan B: tests + README. Plan A's gate becomes mypy + ruff (pytest red until B). | |
| Three plans — by semantic boundary | Plan A: divergence/* `vault:` → `wiki:` (WSEVAL-03). Plan B: sweep/baseline/structural + isolation. Plan C: README + test polish. | |

**User's choice:** Big-bang single plan (carry forward)
**Notes:** Captured as D-05 + D-06 in CONTEXT.md. Mirrors Phase 22 D-03 and Phase 23 D-01 — milestone pattern. Plan gate is `uv run --package eval-harness pytest` green; optionally also workspace-wide `uv run pytest`.

---

## Brand-gate extension

| Option | Description | Selected |
|--------|-------------|----------|
| Extend — add eval-shape patterns | Add 3 regex rules to check-brand.sh: `vault_path:` as function param, bare `vault: Path`, `"--vault"` argparse literal. Scoped to packages/eval-harness. May need allowlist seeding. | ✓ |
| Extend lightly — only argparse `--vault` | Just the `"--vault"` regex. Skip bare-`vault:` and param bans (false-positive prone in tests). | |
| Skip — SC#5 grep is enough | SC#5 grep is effectively a one-shot brand-gate at phase close. A standing CI gate adds maintenance cost. | |

**User's choice:** Extend — add eval-shape patterns
**Notes:** Captured as D-07 in CONTEXT.md. Three regex bans scoped to `packages/eval-harness/{src,tests}`. Tests included because reintroducing `vault: Path` in test code would defeat the rename. `.brand-grep-allow` seeded for any unavoidable historical refs surfaced at dry-run.

---

## Claude's Discretion

- Order of file edits within the big-bang plan (mechanical).
- Exact wording of updated docstrings/comments.
- Brand-gate regex implementation details + allowlist seeds for false-positives.
- Whether `fixture_vault_path` → `fixture_wiki_path` or `fixture_workspace_path` in test_structural.py.

## Deferred Ideas

- Migrate `baseline.py` argparse → Typer (consolidation; out of scope).
- Rename `wiki-io` package directory + `wiki_io` module → `wiki-io` / `wiki_io` (locked OUT of v1.4 per Phase 22 D-10).
- `_SLUG_ONLY_RE` parity fix at `librarian.py:21` (out-of-scope observation from v1.3 Phase 19).
- Explicit unit test rejecting OLD argparse `--vault` flag (relying on no-shim posture as implicit coverage).
- Phase 25 (packages-dir-misclassification-fix) — independent of Phase 24.
