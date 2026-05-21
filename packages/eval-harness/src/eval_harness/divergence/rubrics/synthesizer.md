<!-- Source: agents/graph-wiki-agent/src/graph_wiki_agent/prompts/sources/synthesizer.md §Rules, §Red flags -->

# Divergence Rubric — Synthesizer

This rubric is consumed by the LLM judge (GEval via DivergenceMetric) to evaluate
whether a synthesizer agent's answer adheres to the contract from
`agents/graph-wiki-agent/src/graph_wiki_agent/prompts/sources/synthesizer.md`. The judge complements the
programmatic SYN-001..SYN-004 checks with semantic rules that string-matching
cannot capture.

## Scoring Criteria

Evaluate each criterion independently. A criterion passes if the answer clearly
satisfies it; a criterion fails if there is clear evidence of violation.
Ambiguous or partially-satisfied criteria should be scored as pass to reduce
false-positive noise on soft checks.

1. **SYN-005-grounded-in-excerpts**: Does every substantive claim, file path,
   function/class/symbol name, and wikilink target in the answer plausibly
   trace back to one of the supplied librarian (or code-reader) excerpts?
   Inventing claims, paths, or wikilink targets that did not appear in any
   excerpt counts as a failure. A claim phrased with appropriate hedging that
   is not directly supported by an excerpt is still a failure when presented
   as fact. (pass/fail)

2. **SYN-006-acknowledges-gaps**: When the supplied excerpts do not cover some
   aspect of the query, does the answer explicitly acknowledge the gap (e.g.
   "the vault does not document X") rather than filling it with plausible-
   sounding prose? Filling a gap silently with invented prose counts as a
   failure. If the excerpts cover the query fully, this criterion passes
   trivially. (pass/fail)

## Scoring

Return a score between 0.0 and 1.0 representing the fraction of criteria that
pass. Score 1.0 if both criteria pass, 0.5 if one passes and one fails, 0.0 if
both fail.
