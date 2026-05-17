<!-- Source: packages/prompt-sources/agents/librarian.md -->
<!-- Anchor: ## Rules + ## Red flags -->
<!-- Source-commit: ef05d991a9ab1ea12b1bc7ebc1fb20ba70074030 -->

# Divergence Rubric — Librarian

This rubric is consumed by the LLM judge (GEval via DivergenceMetric) to evaluate
whether a librarian agent's answer adheres to the skill-content expectations from
the canonical lattice-wiki librarian spec.

## Scoring Criteria

Evaluate each criterion independently. A criterion passes if the answer clearly
satisfies it; a criterion fails if there is clear evidence of violation.
Ambiguous or partially-satisfied criteria should be scored as pass to reduce
false-positive noise on soft checks.

1. **LIB-005-refusal-pattern**: When the vault does not contain relevant
   information about the query, does the answer either (a) respond with the
   sentinel string `NO_RELEVANT_CONTENT`, or (b) explicitly state that the vault
   does not know (e.g. "the vault doesn't cover this", "I couldn't find
   relevant pages")? An invented answer that is not supported by cited vault
   content counts as a failure. (pass/fail)

2. **LIB-006-no-invention**: Does the answer reference only symbols, file paths,
   wikilinks, and claims that plausibly appear in the supplied vault excerpts?
   Fabricated package names, invented file paths, or non-existent wikilink
   targets that were not in the excerpts count as failures. A single uncertain
   reference does not fail this criterion — only clear invention does. (pass/fail)

## Scoring

Return a score between 0.0 and 1.0 representing the fraction of criteria that
pass. Score 1.0 if both criteria pass, 0.5 if one passes and one fails, 0.0 if
both fail.
