<!-- Source: packages/prompt-sources/agents/ingestor.md -->
<!-- Anchor: ## Rules + ## Red flags -->
<!-- Source-commit: ef05d991a9ab1ea12b1bc7ebc1fb20ba70074030 -->

# Divergence Rubric — Ingestor

This rubric is consumed by the LLM judge (GEval via DivergenceMetric) to evaluate
whether an ingestor agent's output adheres to the skill-content expectations from
the canonical lattice-wiki ingestor spec.

## Scoring Criteria

Evaluate each criterion independently. A criterion passes if the output clearly
satisfies it; a criterion fails if there is clear evidence of violation.
Ambiguous or partially-satisfied criteria should be scored as pass.

1. **ING-005-citation-density**: Does the output body (after the frontmatter)
   cite at least one wikilink (`[[page]]`) or code path (`` `path:line` ``) for
   each substantive claim made about a package, domain, or architectural
   decision? Pure descriptive summaries with no citation targets are acceptable
   for brief overviews, but any claim linking a concept to a specific package or
   code location must include a citation. (pass/fail)

2. **ING-006-flag-contradictions**: If the source document being ingested
   contradicts a claim that would plausibly exist in an existing vault page
   (e.g. changes an API, revises an architecture decision, or supersedes a prior
   spec), does the output include an explicit contradiction flag (e.g. a
   `> ⚠️ Contradiction:` callout, or a note that the existing page should be
   updated)? If the source has no contradictions, this criterion passes
   automatically. (pass/fail)

## Scoring

Return a score between 0.0 and 1.0 representing the fraction of criteria that
pass. Score 1.0 if both criteria pass, 0.5 if one passes and one fails, 0.0 if
both fail.
