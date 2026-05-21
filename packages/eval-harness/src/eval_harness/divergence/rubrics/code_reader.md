<!-- Source: agents/graph-wiki-agent/src/graph_wiki_agent/prompts/sources/code_reader.md §Rules, §Red flags -->

# Divergence Rubric — Code Reader

This rubric is consumed by the LLM judge (GEval via DivergenceMetric) to evaluate
whether a code_reader agent's output adheres to the contract from
`agents/graph-wiki-agent/src/graph_wiki_agent/prompts/sources/code_reader.md`. The judge complements the
programmatic CR-001..CR-004 checks with semantic rules that string-matching
cannot capture.

## Scoring Criteria

Evaluate each criterion independently. A criterion passes if the output clearly
satisfies it; a criterion fails if there is clear evidence of violation.
Ambiguous or partially-satisfied criteria should be scored as pass to reduce
false-positive noise on soft checks.

1. **CR-005-verbatim-quoting**: When the output quotes code, does the quoted
   text plausibly come from the file named in the `path:line` annotation, with
   no paraphrasing, no reformatting, and no invented symbols? Paraphrased code
   that is presented as a verbatim quote counts as a failure. A short narrative
   gloss ALONGSIDE a verbatim quote is fine — only paraphrase-as-quote fails.
   (pass/fail)

2. **CR-006-no-invention**: Does the output reference only file paths and line
   numbers that plausibly exist for the query at hand? Made-up paths under
   reasonable-sounding directories (e.g. citing `packages/missing-pkg/foo.py`
   when no such file plausibly exists), or implausible line numbers (e.g. `:1`
   for content that is clearly mid-file), count as failures. A single uncertain
   reference does not fail this criterion — only clear invention does.
   (pass/fail)

## Scoring

Return a score between 0.0 and 1.0 representing the fraction of criteria that
pass. Score 1.0 if both criteria pass, 0.5 if one passes and one fails, 0.0 if
both fail.
