---
status: diagnosed
phase: 06-prompt-content-port-divergence-eval
source:
  - 06-VERIFICATION.md (human_needed items)
started: 2026-05-16T00:00:00Z
updated: 2026-05-16T00:00:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Live Query Citation Quality
expected: |
  `graph-wiki-agent query "..."` against the fixture corpus returns an answer with
  wikilinks that resolve in the vault, cites sources per citation rules, and uses
  the `NO_RELEVANT_CONTENT` sentinel rather than hallucinating when nothing matches.
result: pass
notes: |
  Ran against freshly-scanned vault (stub pages only, no ingested content). Librarian
  drilled 5 pages, found nothing substantive, code-fallback hit the documented v1
  repo-root resolver limitation (vault and repo are siblings, not parent/child), and
  the response was a clean refusal: "The vault does not document this and source code
  did not yield a relevant match." No hallucinated wikilinks. Iron-rule behavior
  confirmed. Citation-quality vs real content remains to be exercised after ingest.

### 2. Live Ingest Page-Type Routing
expected: |
  `graph-wiki-agent ingest <sample source>` generates frontmatter with title,
  category, page_type, target_slug, and summary; page_type is routed correctly
  (source docs → `source`, work-item subjects → `package|concept|adr`); the output
  passes ING-001..004 checks.
result: issue
reported: |
  Multiple divergences on a real ingest of an OTel article:
    - ING-001 FAIL: frontmatter wrapped in ```yaml ... ``` code fence instead of starting with `---`
    - Routing/frontmatter disagreement: frontmatter declares `page_type: source, category: source`;
      CLI output and on-disk placement say `concept` — file landed at concepts/otel-story-of-observability.md
      while sources/ is empty. A source document was routed as a concept.
    - target_slug mismatch: frontmatter says `otel-story-observability`, file is `otel-story-of-observability.md`
    - Hallucinated wikilinks: `[[Krishnan Sriram]]` (no page exists), `[[sources/otel-story-observability]]`
      (broken — sources/ empty, slug also disagrees with target_slug)
  Passing: ING-002 (required fields present), ING-003 (page_type in valid set), ING-004 (internal
  page_type/category match).
severity: major

### 3. End-to-End Divergence Eval Run
expected: |
  `GRAPH_WIKI_RUN_EVAL=1 uv run --package eval-harness pytest cores/eval-harness/tests/test_divergence.py -s --accept-divergence-baseline`
  runs for all 4 roles (librarian, ingestor, linter, scanner); per-role divergence
  counts and accepted_failures excerpts print to stdout; baseline JSON files update
  with real run data; no AssertionError for hard-severity rules.
result: pass
notes: |
  Initial run failed with ModuleNotFoundError: 'aiobotocore' (DeepEval AmazonBedrockModel
  hard-requires it; missing from eval-harness pyproject deps). Fixed by adding
  aiobotocore>=2.13 to cores/eval-harness/pyproject.toml and re-syncing.
  Re-run: 3 passed, 1 skipped, exit 0, 217s wall time (real Bedrock judge panel).
  Baselines updated at 2026-05-16 for librarian/ingestor/linter at agent_commit=cc6c67c.
  Scanner SKIPPED — fixture-design issue: round-trip-vault has no resolvable monorepo
  sibling, so scanner produces no added/updated stubs to score. Same shape as Test 1's
  repo-root resolver limitation. Logged as a follow-on gap, not a Phase 6 defect.

## Summary

total: 3
passed: 2
issues: 1
pending: 0
skipped: 0

## Gaps

- truth: "Live ingest produces frontmatter starting with `---` (ING-001 compliant), not wrapped in a markdown code fence"
  status: failed
  reason: "User reported: ingestor LLM emitted ```yaml ... ``` code-fenced frontmatter; ING-001 would fail because text does not startswith('---')"
  severity: major
  test: 2
  artifacts: []
  missing: []

- truth: "Live ingest routes source documents to sources/ (page_type=source), not concepts/"
  status: failed
  reason: "User reported: OTel source article routed as page_type=concept on disk, but frontmatter self-declares page_type=source — post-LLM routing decision disagrees with LLM's self-declared type; sources/ left empty"
  severity: major
  test: 2
  artifacts: []
  missing: []

- truth: "target_slug in frontmatter matches the on-disk filename slug"
  status: failed
  reason: "User reported: frontmatter target_slug=otel-story-observability, filename=otel-story-of-observability.md"
  severity: minor
  test: 2
  artifacts: []
  missing: []

- truth: "Wikilinks in generated pages resolve to existing vault pages or use NO_RELEVANT_CONTENT sentinel"
  status: failed
  reason: "User reported: page contains [[Krishnan Sriram]] (no page exists) and [[sources/otel-story-observability]] (sources/ empty, slug also mismatched) — both hallucinated"
  severity: major
  test: 2
  artifacts: []
  missing: []

- truth: "GRAPH_WIKI_RUN_EVAL=1 pytest test_divergence.py runs end-to-end for all 4 roles with judge panel against live Bedrock; baseline JSON files update; no AssertionError on hard-severity rules"
  status: resolved
  reason: "Initial blocker: ModuleNotFoundError 'aiobotocore' — DeepEval AmazonBedrockModel hard-requires it but it was missing from eval-harness deps. Fixed inline by adding aiobotocore>=2.13 to cores/eval-harness/pyproject.toml. Re-run: 3 passed, 1 skipped, exit 0, 217s. Librarian/ingestor/linter baselines refreshed; scanner skipped due to fixture limitation (separate gap)."
  severity: blocker
  test: 3
  artifacts:
    - cores/eval-harness/pyproject.toml
  missing: []

- truth: "Scanner role exercises against the divergence eval fixture corpus"
  status: failed
  reason: "Scanner test skipped at eval_helpers.py:241 — fixture round-trip-vault has no resolvable monorepo sibling, so scanner produces no added/updated package stubs to score. Fixture-design gap, not a Phase 6 runtime defect. Same shape as Test 1's repo-root resolver fallback in real-world vault layout."
  severity: minor
  test: 3
  artifacts:
    - cores/eval-harness/tests/eval_helpers.py:241
    - cores/vault-io/tests/fixtures/round-trip-vault
  missing:
    - monorepo sibling in fixture vault OR scanner adaptation for vault-only execution
