<!-- Source: cores/prompt-sources/agents/scanner.md -->
<!-- Anchor: ## Rules + ## Red flags -->
<!-- Source-commit: ef05d991a9ab1ea12b1bc7ebc1fb20ba70074030 -->

# Divergence Rubric — Scanner

This rubric is consumed by the LLM judge (GEval via DivergenceMetric) to evaluate
whether a scanner agent's stub output adheres to the skill-content expectations
from the canonical lattice-wiki scanner spec.

## Scoring Criteria

Evaluate each criterion independently. A criterion passes if the stub output
clearly satisfies it; a criterion fails if there is clear evidence of violation.
Ambiguous or partially-satisfied criteria should be scored as pass.

1. **SCN-005-no-prose-overwrite**: For delta scans (updating an existing stub
   page), does the output leave freeform prose sections intact? The scanner is
   permitted to update frontmatter fields (`exports`, `depends_on`,
   `depended_on_by`, `updated`) and replace the `## File map` section only if
   every bullet description is still the `— TODO` placeholder. Any prose content
   under sections like `## Public API`, `## Key patterns`, or `## Purpose` that
   has been filled in by a prior ingest must not be overwritten. An output that
   produces only frontmatter + structural section stubs for a brand-new package
   passes this criterion automatically. (pass/fail)

## Scoring

Return a score between 0.0 and 1.0 representing the fraction of criteria that
pass. Score 1.0 if the criterion passes, 0.0 if it fails.
