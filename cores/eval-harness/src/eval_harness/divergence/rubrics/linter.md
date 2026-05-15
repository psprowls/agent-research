<!-- Source: cores/prompt-sources/agents/linter.md -->
<!-- Anchor: ## Rules + ## Red flags -->
<!-- Source-commit: ef05d991a9ab1ea12b1bc7ebc1fb20ba70074030 -->

# Divergence Rubric — Linter

This rubric is consumed by the LLM judge (GEval via DivergenceMetric) to evaluate
whether a linter agent's findings report adheres to the skill-content expectations
from the canonical lattice-wiki linter spec.

## Scoring Criteria

Evaluate each criterion independently. A criterion passes if the findings report
clearly satisfies it; a criterion fails if there is clear evidence of violation.
Ambiguous or partially-satisfied criteria should be scored as pass to reduce
false-positive noise on soft checks.

1. **LNT-004-semantic-completeness**: Does the findings report cover the major
   categories of issues that are actually present in the vault? The linter is
   expected to check multiple categories (code drift, contradictions, broken
   links, orphan pages, stale claims, roadmap staleness, ADR chain health,
   concept gaps). A report that only covers one or two categories while the
   vault clearly has issues in other categories is incomplete. Allow for a
   report that notes "no issues found" in a category rather than requiring
   every finding to be substantive. (pass/fail)

2. **LNT-005-suggestions-present**: Does each finding include at least one
   concrete remediation suggestion (e.g. "run wiki_scan", "re-ingest the
   source", "archive the orphan page", "update the ADR status")? A findings
   list that only enumerates problems without suggesting actions is a violation.
   A single combined "Suggested actions" section at the end is acceptable as
   long as it covers the listed findings. (pass/fail)

## Scoring

Return a score between 0.0 and 1.0 representing the fraction of criteria that
pass. Score 1.0 if both criteria pass, 0.5 if one passes and one fails, 0.0 if
both fail.
