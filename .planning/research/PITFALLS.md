# Pitfalls Research

**Domain:** deepagents-based MCP server on AWS Bedrock with parallel subagents and cost-frontier eval harness
**Researched:** 2026-05-13
**Confidence:** HIGH (issues confirmed via official deepagents GitHub issues and AWS docs) / MEDIUM (eval methodology from research literature)

---

## Top-5 Highest-Risk Pitfalls

These are the five pitfalls most likely to cause a rewrite, data corruption, or a weeks-long debugging spiral:

1. **Parallel subagent cancellation cascade** — one subagent failure silently kills all siblings (confirmed GitHub issue #694)
2. **Bedrock burst-throttling from max_tokens over-reservation** — parallel fan-out causes TPM spike even when long-run usage is within quota
3. **Wikilink placeholder false positives in lint** — the original tool shipped a dedicated fix for this; reimplementing naively will regress
4. **Truncated frontmatter crash** — a real failure mode in the source vault; naive YAML parsing will IndexError on pages with a missing closing `---`
5. **LLM-judge self-preference corrupts eval baseline** — using the same model family as judge and examinee inflates quality scores and hides regressions

---

## Critical Pitfalls

### Pitfall 1: Parallel Subagent Cancellation Cascade

**What goes wrong:**
When the agent invokes multiple subagents simultaneously (e.g., the librarian drilling 5 wiki pages in parallel), a single subagent failure causes `asyncio.gather()` to immediately cancel all sibling coroutines. The parent receives a `CancelledError` or a partial result set with no indication of which subagent failed or which succeeded. Multi-page query results are silently truncated.

**Why it happens:**
deepagents' `SubAgentMiddleware` uses `asyncio.gather()` without `return_exceptions=True` (confirmed issue #694 on `langchain-ai/deepagents`). This is the Python default behavior: the first exception cancels the remaining tasks in the gather group.

**How to avoid:**
- Wrap each subagent call in a try/except before returning results to the coordinator; do not let individual failures propagate uncaught.
- Until the upstream fix lands, implement a wrapper around the subagent invocation that uses `asyncio.gather(*tasks, return_exceptions=True)` at the fan-out site and promotes partial results to the coordinator with a warning.
- Add an integration test: spawn 4 parallel subagents where 1 intentionally raises; assert the other 3 complete and their results are preserved.

**Warning signs:**
- Query results are shorter than expected without any error message.
- Log shows `CancelledError` or `asyncio.exceptions.CancelledError` during fan-out.
- Subagent count in telemetry is lower than the number of pages requested.

**Phase to address:** Phase 2 (Subagent Fan-out Foundations) — before any command uses parallel subagents. The integration test must pass before the scanner, librarian, or linter fan-out is wired.

---

### Pitfall 2: Subagent Recursion Limit Not Propagated (Silent GraphRecursionError)

**What goes wrong:**
The parent agent is invoked with `recursion_limit=150`. Subagents silently use LangGraph's hardcoded default of 25. A librarian subagent drilling a complex page with 13+ tool calls hits the 25-step ceiling and raises `GraphRecursionError`, which surfaces as a `CancelledError` in the parent (due to Pitfall 1 interaction). The agent appears to time out rather than producing an error.

**Why it happens:**
`SubAgentMiddleware.ainvoke()` calls `subagent.ainvoke(subagent_state)` with no `config=` parameter. LangGraph uses its hardcoded default (confirmed issue #1698 on `langchain-ai/deepagents`). No per-subagent override field exists on the `SubAgent` TypedDict.

**How to avoid:**
- Pass config explicitly when invoking subagents: `subagent.ainvoke(state, config={"recursion_limit": 150})`.
- Until the upstream fix lands, monkey-patch or subclass `SubAgentMiddleware` to forward the parent config.
- Set a default recursion limit of 100+ at all invocation sites (deepagents docs recommend starting at 100 instead of the default 25 for workflows with subgraphs).
- Add a test where a subagent must perform 30 tool calls; it should not crash.

**Warning signs:**
- Subagents complete successfully in isolation but fail when invoked from the parent coordinator.
- `GraphRecursionError: Recursion limit of 25 reached` in tracebacks.
- Log output cuts off mid-page for complex wiki pages.

**Phase to address:** Phase 2 (Subagent Fan-out Foundations) — set and verify this at the runtime layer before wiring any command.

---

### Pitfall 3: Bedrock TPM Burst Throttling from max_tokens Over-Reservation

**What goes wrong:**
Fan-out launches 5 subagents simultaneously. Each subagent call to `ChatBedrockConverse` reserves `input_tokens + max_tokens` from the TPM quota at request start, not at completion. If `max_tokens` is not set (defaulting to 64K for Claude Sonnet 4), five simultaneous requests reserve 5 × 64K = 320K output tokens' worth of quota in one burst window (Claude Sonnet 4 output tokens count at 5× burndown rate, so effectively 1.6M quota tokens). This exceeds the per-minute quota even though actual output is tiny, producing `ThrottlingException`.

**Why it happens:**
AWS Bedrock reserves quota upfront based on the `max_tokens` parameter before output is generated. The burndown rate for Claude Sonnet 4+ is 5× output tokens (confirmed AWS docs on token burndown). Parallel fan-out amplifies the burst. This is a documented gotcha in AWS re:Post: "throttling was caused by peak in-flight token reservation, not by total tokens burned per minute."

**How to avoid:**
- Always set `max_tokens` to a realistic upper bound for the specific role (librarian answer: 2000, scanner stub: 500, linter report: 3000). Never leave it at model maximum.
- Implement a token-aware rate limiter with a sliding 60-second window before the fan-out site; only launch the next subagent when enough budget remains.
- Use cross-region inference profiles (e.g., `us.anthropic.claude-sonnet-4-5-20250929-v1:0`) to multiply effective throughput by up to 2× without provisioned throughput costs.
- For the eval harness, stagger parallel model comparisons rather than firing all models simultaneously.

**Warning signs:**
- `ThrottlingException` or `ServiceUnavailableException` from botocore during fan-out even when total token usage appears low.
- CloudWatch `EstimatedTPMQuotaUsage` metric spikes to 100% momentarily.
- Errors correlate with concurrency level, not with total token count.

**Phase to address:** Phase 2 (Subagent Fan-out Foundations) — the rate limiter and `max_tokens` discipline must be in the shared Bedrock adapter before any command uses fan-out.

---

### Pitfall 4: Wikilink Placeholder False Positives Corrupt Lint State

**What goes wrong:**
The linter walks vault pages, extracts `[[wikilinks]]`, and checks whether the target page exists. Template tokens like `[[wiki/...]]`, `[[work/<slug>]]`, and `[[wiki/<container>/<name>]]` are not real wikilinks — they are placeholder patterns used in page stubs and ingest outputs. Treating them as broken links produces hundreds of false-positive `broken_links` violations on a fresh vault, making the lint report useless.

**Why it happens:**
A naive wikilink regex extracts every `[[...]]` pattern. The lattice-wiki-core codebase shipped a specific fix for this (commits `9502c45` and `9388cdd`: "skip placeholder wikilink tokens like `[[wiki/...]]` and `[[work/<slug>]]`"). This knowledge is not in any spec document — it exists only as a fix in the source code and tests.

**How to avoid:**
- Adopt the exact placeholder-filtering logic from `lattice_wiki_core/lint_wiki.py` before writing the linter subagent. Copy the `_is_placeholder_target()` predicate and its associated tests.
- Include tests that exercise: a page with `[[wiki/...]]` placeholder (should produce zero broken-link violations), a page with `[[work/<slug>]]` placeholder (same), and a page with a genuinely broken `[[NonexistentPage]]` (should produce one violation).

**Warning signs:**
- Lint report shows dozens of broken wikilinks on pages that clearly have valid structure.
- Broken links include patterns with `/...` or `/<slug>` suffixes.
- Running lint on the existing lattice-wiki vault produces violations the old tool does not.

**Phase to address:** Phase 3 (Lint Command) — at the start, before implementing the wikilink resolver, verify the placeholder filter is in place and tests pass on the existing vault.

---

### Pitfall 5: Truncated Frontmatter Causes IndexError on Real Vault Pages

**What goes wrong:**
Some wiki pages in the existing vault have a missing closing `---` frontmatter fence (e.g., a file was written mid-operation and the write was interrupted). Any code that does `text.split("---")` and then indexes `parts[2]` will raise `IndexError` on these pages, crashing the command entirely.

**Why it happens:**
The source tool shipped a dedicated fix for this (commit `ae6872e`: "guard truncated frontmatter and tighten tokens: prefix match"). The fix adds `if len(parts) < 3: warn and skip`. This is not in any spec document — it is undocumented vault reality.

**How to avoid:**
- Use `python-frontmatter` library for all frontmatter parsing; it handles malformed frontmatter gracefully.
- Add a guard wherever raw frontmatter splitting is done: check `len(parts) >= 3` before accessing `parts[2]`, log a warning to stderr, and skip the file.
- Include a test fixture with a truncated-frontmatter file; verify the command skips it without crashing.

**Warning signs:**
- `IndexError: list index out of range` in stack traces that pass through frontmatter parsing.
- Crash occurs only on specific vault files but passes on clean test fixtures.
- Error is not reproducible with synthetic test data (synthetic fixtures have correct frontmatter).

**Phase to address:** Phase 1 (Core Vault IO) — the vault reader must handle this before any command uses it.

---

### Pitfall 6: LLM-Judge Self-Preference Inflates Eval Scores

**What goes wrong:**
The eval harness uses Claude Sonnet (via Bedrock) as the judge. When evaluating Claude Sonnet outputs against Llama or Nova outputs, the judge systematically prefers the Claude output — not because it is better, but because of self-preference bias (confirmed: GPT-4 exhibits significant self-preference; LLMs favor outputs with lower perplexity relative to their own distribution). This makes the cost-frontier chart show Claude winning on quality even when a cheaper model produces equivalent results for this task.

**Why it happens:**
LLM-as-judge self-preference bias is well-documented in the research literature (arXiv 2410.21819). The model scoring the comparison has implicit preference for outputs generated by models in the same family.

**How to avoid:**
- Use a heterogeneous judge panel: at minimum one Claude judge and one non-Claude judge (e.g., Nova Pro or Llama 3 70B). Average their scores and report disagreement rate.
- Blind the judge to which model produced which output — strip any model-identifying tokens from the answer before scoring.
- Score against a rubric (does the answer cite the correct pages? does it include the correct wikilinks? are all required sections present?) rather than asking for a freeform quality rating.
- For the baseline corpus, record both a Sonnet output and a human-verified "ground truth" edit of that output so the baseline is not purely model-generated.
- Pin judge model versions using explicit ARNs rather than alias IDs (alias IDs resolve to different checkpoints over time, causing baseline drift).

**Warning signs:**
- Eval consistently ranks Claude models 10-15%+ above non-Claude models on subjective quality with no corresponding difference on rubric-based checks.
- Judge scores and rubric scores diverge systematically by model family.
- Re-running eval with models in different positions (A vs B order swapped) changes scores.

**Phase to address:** Phase 4 (Eval Harness) — design the judge architecture before recording any baseline.

---

### Pitfall 7: Eval Baseline Drift (Sonnet Output Is Not Ground Truth)

**What goes wrong:**
The eval records lattice-wiki Sonnet outputs as the baseline corpus and uses them as ground truth for all future comparisons. When Bedrock updates the Sonnet model checkpoint (or when Sonnet's behavior drifts), the new Sonnet output is scored as a regression against the old Sonnet output — even though both are correct. The cost-frontier curve becomes a measurement of model version drift, not quality.

**Why it happens:**
Model aliases on Bedrock (e.g., `anthropic.claude-sonnet-4-5-v1:0`) resolve to the latest checkpoint within a model generation. The underlying checkpoint can change without a version bump. A baseline recorded in month 1 may be different from what the same alias produces in month 3.

**How to avoid:**
- Pin baselines to concrete model ARNs, not aliases (e.g., `anthropic.claude-sonnet-4-5-20250929-v1:0`), and record the ARN alongside each baseline output.
- Store baselines in a content-addressed format so changes are detectable (hash each output).
- Write rubric-based checks in addition to baseline-comparison checks: the rubric checks (correct wikilinks cited, correct page count, required frontmatter preserved) do not drift with model version.
- Treat the baseline as a reference corpus for regression detection, not as the definition of correctness.

**Warning signs:**
- Eval scores for the same model drop between runs without any code changes.
- The baseline hash changes when you re-record with the same alias.
- Quality differences between Sonnet v1 and Sonnet v2 appear as large regressions in existing tests.

**Phase to address:** Phase 4 (Eval Harness) — store model ARN and output hash as first-class metadata in the corpus format before recording any baselines.

---

### Pitfall 8: MCP Stdout Contamination Breaks the Protocol Stream

**What goes wrong:**
Any `print()` statement, logging handler, or library debug output written to `stdout` corrupts the MCP JSON-RPC framing. The host (DeepAgents CLI) receives malformed messages, fails to parse them, and either drops the tool entirely or raises a connection error. The bug is silent when running the server standalone but appears immediately under a real host.

**Why it happens:**
MCP over stdio uses stdout as the exclusive protocol channel. All message framing is newline-delimited JSON. A single rogue `print("loaded config")` in server startup is enough to break the parser on the host side.

**How to avoid:**
- Redirect all logging to stderr from day one: `logging.basicConfig(stream=sys.stderr)`. Never use bare `print()` in any code path that runs in MCP server mode.
- Add a startup self-test: launch the MCP server as a subprocess and verify its stdout output is valid JSON-RPC (no extra lines).
- Use the MCP Python SDK's `StdioServerTransport` rather than rolling message framing manually.

**Warning signs:**
- DeepAgents CLI reports "failed to parse server message" or "unexpected EOF" on the MCP connection.
- Server works when run in headless CLI mode but fails when hosted via MCP.
- Errors are intermittent (only trigger when a code path hits a `print`).

**Phase to address:** Phase 1 (MCP Server Skeleton) — enforce stderr-only logging before any tool is registered.

---

### Pitfall 9: Cross-Region Inference IAM Missing the Third ARN

**What goes wrong:**
IAM policy grants `bedrock:InvokeModel` on the foundation model ARN (`arn:aws:bedrock:us-east-1::foundation-model/MODEL`). Cross-region inference profiles require a third ARN: the inference profile ARN (`arn:aws:bedrock:REGION:ACCOUNT:inference-profile/us.MODEL`). Omitting it produces `AccessDeniedException` even though the policy looks correct. For global inference profiles, the condition must include `aws:RequestedRegion: unspecified` — restrictive SCPs that deny all non-approved regions will block this.

**Why it happens:**
Cross-region inference is a separate resource type from foundation models. The IAM permission model requires explicit allow on both the inference-profile resource and the underlying foundation model resource in each destination region. This is documented but easy to miss when copying existing Bedrock IAM policies that predate cross-region support (confirmed AWS re:Post: "the part `arn:aws:bedrock:...:inference-profile/*` is new and may well be what's missing").

**How to avoid:**
- Use the three-resource IAM statement from AWS docs: (1) regional inference profile ARN, (2) regional foundation model ARN, (3) global foundation model ARN (no account/region for global profiles).
- Add `aws:RequestedRegion: unspecified` to the SCP allow list if using global cross-region profiles.
- Test IAM by attempting an actual inference call from the target machine/role before writing any application code — catch this at infra setup, not mid-implementation.

**Warning signs:**
- `AccessDeniedException` on `bedrock:InvokeModel` even though the model ARN is listed in the policy.
- Error includes an inference-profile ARN that is not in the IAM policy resource list.
- Works in the home region but fails when routed to a destination region.

**Phase to address:** Phase 1 (Infrastructure Setup) — verify cross-region IAM before writing a single line of application code.

---

### Pitfall 10: uv Workspace pytest Test Collision Across Members

**What goes wrong:**
`pytest` discovers test files across the entire workspace when run from the root. If two workspace members (e.g., `code-wiki-agent` and a future `shared-eval`) both have a `tests/test_utils.py`, pytest may load `conftest.py` from the wrong package root, producing import errors or silently running the wrong tests with the wrong fixtures.

**Why it happens:**
uv creates a unified virtual environment and installs all members as editable packages. `pytest` traverses the monorepo tree and can find same-named test files in multiple packages. `conftest.py` loading is path-based, so the first one found may shadow others.

**How to avoid:**
- Set `testpaths = ["tests"]` in each member's `pyproject.toml` `[tool.pytest.ini_options]` and run per-member tests with `uv run --package <name> pytest`.
- Use unique test file names across members or namespace test directories: `tests/code_wiki_agent/` not just `tests/`.
- Add a root-level `conftest.py` that explicitly lists excluded packages to prevent accidental cross-member discovery.

**Warning signs:**
- `ImportError` in pytest that references a module from a different workspace member.
- Test counts differ depending on which directory `pytest` is invoked from.
- Fixtures leak between packages (a fixture defined in package A is unexpectedly available in package B's tests).

**Phase to address:** Phase 1 (Monorepo Setup) — set `testpaths` in `pyproject.toml` for each member before writing any tests.

---

### Pitfall 11: uv Workspace Single-Version Enforcement Blocks Mixed Library Versions

**What goes wrong:**
uv enforces a single resolved version per package across all workspace members. If `code-wiki-agent` requires `langchain>=0.3` and a future `eval-harness` member pins `langchain==0.2.x`, uv will refuse to resolve or silently upgrade one to satisfy the other, breaking the member that expected the older version.

**Why it happens:**
uv's workspace lock file is global — it solves a single SAT problem across all members. Member-level version constraints in sub-`pyproject.toml` files cannot override the global resolution.

**How to avoid:**
- Pin all shared library versions in the root `pyproject.toml` via `[tool.uv.constraint-dependencies]` and keep members' version ranges loose (`>=X`).
- Add a CI check that runs `uv lock --check` after every dependency change to catch resolution failures early.
- For packages that truly need different versions, use a separate uv workspace (not a member of this one).

**Warning signs:**
- `uv sync` produces `ResolutionError: no solution found` after adding a new workspace member.
- A library that worked in one member stops working after adding another member with a conflicting version pin.

**Phase to address:** Phase 1 (Monorepo Setup) — establish the version constraint strategy in the root `pyproject.toml` before adding more than one member.

---

### Pitfall 12: Vault Write-Compatibility: Format Drift Under Round-Trip

**What goes wrong:**
The reimplementation reads a vault page with `python-frontmatter`, modifies a field, and writes it back. The YAML emitter normalizes values — booleans become `true/false` (YAML canonical), bare strings become quoted, multiline strings get folded. The original vault uses a hand-rolled emitter that preserves specific formatting (e.g., `updated: 2026-04-30` stays unquoted). After one round-trip, `git diff` shows dozens of formatting changes on every page. Obsidian still reads it, but `git blame` is destroyed and the old tool's lint detects "drift."

**Why it happens:**
`python-frontmatter` uses PyYAML's `Dumper`, which re-normalizes YAML on write. The original tool uses a hand-rolled minimal emitter (`layout_io._emit_yaml()`) precisely to avoid this. This tradeoff is not documented in any spec — it is visible only in the implementation.

**How to avoid:**
- For any field that must be preserved verbatim (dates, slugs, summary strings), write the frontmatter back using a targeted string-replacement approach rather than full YAML round-trip: parse the raw text, find the field line with regex, replace only that line.
- Alternatively, use `ruamel.yaml` in round-trip mode (preserves comments and formatting) instead of PyYAML/`python-frontmatter`.
- Add a vault round-trip test: read every page in the fixture vault, write it back unchanged, and assert `git diff` is empty.

**Warning signs:**
- `git diff` shows frontmatter changes after running any command on a clean vault.
- Fields that were unquoted are now quoted, or vice versa.
- Boolean values change between `True` and `true`.

**Phase to address:** Phase 1 (Core Vault IO) — validate round-trip fidelity on the real vault before implementing any command.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Use model aliases (`anthropic.claude-sonnet-4-5-v1:0`) instead of pinned ARNs | No config maintenance | Eval baselines drift silently when checkpoint changes under alias | Never for eval corpus; aliases are fine for non-baseline commands |
| Skip `max_tokens` sizing per role, use model maximum | No upfront analysis | Burst TPM throttling on every fan-out; wastes quota | Never |
| Use bare `print()` for server-mode debug output | Quick debugging | Corrupts MCP stdout channel; hard to trace | Never in server-mode code paths; fine in headless CLI only |
| Global `pytest` discovery without per-member `testpaths` | No config needed | Test collisions and conftest bleed across members | Never once there are 2+ workspace members |
| Single Sonnet output as eval ground truth | No human review needed | Self-preference bias inflates Claude scores; regression against model updates | Acceptable as starting corpus if augmented with rubric-based checks |
| `asyncio.gather()` without `return_exceptions=True` for subagent fan-out | Library default | Single subagent failure silently cancels all siblings | Never |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Bedrock cross-region inference | IAM policy lists only foundation model ARN | Include inference-profile ARN, regional FM ARN, and global FM ARN as three separate resource entries |
| deepagents subagent config | Invoke subagent with no `config=` parameter | Explicitly pass `config={"recursion_limit": 150}` at every subagent invocation site |
| MCP stdio transport | `print()` calls in server startup or tool code | `logging.basicConfig(stream=sys.stderr)` from process start; zero stdout writes outside the MCP SDK |
| Bedrock ConversAPI + Nova | Using same tool schema as Claude | Nova uses a different `toolConfig` structure in the request body; use `ChatBedrockConverse` with Converse API which normalizes this |
| uv workspace + Docker | Editable install references source directory via absolute path | Build wheels (`uv build`) and install from wheel in Docker, not editable; or copy the entire workspace into the image |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Unbounded `max_tokens` in fan-out | `ThrottlingException` even at low total usage | Set role-specific `max_tokens` ceilings; add burst limiter | First run with 3+ parallel subagents |
| Synchronous vault IO blocking the event loop | Fan-out latency dominated by file reads rather than model calls | Use `asyncio.to_thread()` for all `Path.read_text()` calls inside async subagent tools | Vaults with 200+ pages |
| tiktoken BPE encoding on every page at lint time | Lint takes 30s+ on a large vault | Cache encoding object; reuse across pages; skip if `tokens:` frontmatter is fresh | Vaults with 100+ pages without cached token counts |
| LangGraph subgraph streaming with `streamSubgraphs: True` | Memory grows with message history per subagent | Use `filterSubagentMessages: True` at the UI/orchestration layer to prune coordinator message interleaving | Deep workflows with 5+ subagents each making 10+ tool calls |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Storing AWS credentials in `.env` or project config | Credential leak in git history | Use IAM roles (instance profile or assumed role); never store key/secret in files |
| MCP server executing arbitrary vault paths passed from host | Path traversal if host is compromised | Validate all vault paths are inside the configured repo root before any file operation |
| DeepAgents `--trust-project-mcp` in CI without review | Project MCP config can execute arbitrary local commands | Never pass `--trust-project-mcp` in automated pipelines; pin trusted server configs explicitly |

---

## "Looks Done But Isn't" Checklist

- [ ] **Subagent fan-out:** test with one intentionally failing subagent — verify the other N-1 complete and results are preserved, not silently dropped.
- [ ] **Frontmatter round-trip:** run the vault reader + writer on the real vault and assert `git diff` is empty on all pages.
- [ ] **Wikilink placeholder filter:** run lint on the real vault and verify `[[wiki/...]]` and `[[work/<slug>]]` patterns produce zero false-positive broken-link violations.
- [ ] **MCP stdout cleanliness:** launch the MCP server as a subprocess, capture stdout, and assert every line is valid JSON-RPC (no startup prints, no library debug output).
- [ ] **Bedrock IAM:** attempt an actual `InvokeModel` call via the cross-region inference profile ARN from the deployment machine/role before writing application code.
- [ ] **Eval judge diversity:** verify the judge panel includes at least one non-Claude model; confirm that swapping answer position changes scores by less than 5% (no significant position bias).
- [ ] **Token budget per role:** every subagent invocation site has an explicit `max_tokens` argument; grep for any call with `max_tokens` unset or set to model maximum.
- [ ] **Recursion limit propagation:** every subagent invocation site passes `config={"recursion_limit": N}`; write a subagent that requires 30 tool calls and verify it completes.

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Parallel cancellation cascade discovered in production | MEDIUM | Add `return_exceptions=True` at gather site; redeploy; replay failed commands |
| Vault format drift from bad round-trip | HIGH | `git checkout -- wiki/` to restore originals; fix emitter; re-run only modified pages |
| Eval baseline poisoned by self-preference | MEDIUM | Re-record baselines with heterogeneous judge panel; invalidate existing scores |
| IAM cross-region access denied in CI | LOW | Add inference-profile ARN resource to IAM policy; wait for propagation (~60s) |
| uv lock conflict from new member | LOW | Remove conflicting pin from member `pyproject.toml`; move to root constraints |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Parallel subagent cancellation cascade | Phase 2: Subagent Fan-out Foundations | Integration test: 4 parallel subagents, 1 fails, 3 results returned |
| Recursion limit not propagated | Phase 2: Subagent Fan-out Foundations | Subagent completes 30-step tool chain without `GraphRecursionError` |
| Bedrock burst throttling | Phase 2: Subagent Fan-out Foundations | No `ThrottlingException` when 5 parallel subagents run with role-sized `max_tokens` |
| Wikilink placeholder false positives | Phase 3: Lint Command | Zero broken-link violations on placeholder patterns in real vault |
| Truncated frontmatter crash | Phase 1: Core Vault IO | Test with truncated fixture; command skips and logs warning, does not raise |
| LLM-judge self-preference | Phase 4: Eval Harness | Heterogeneous judge panel; position-swap produces <5% score variance |
| Eval baseline drift | Phase 4: Eval Harness | Baseline metadata includes concrete ARN + output hash; re-recording with same ARN is idempotent |
| MCP stdout contamination | Phase 1: MCP Server Skeleton | Subprocess capture of server stdout contains only valid JSON-RPC lines |
| Cross-region IAM missing ARN | Phase 1: Infrastructure Setup | `aws bedrock invoke-model` succeeds with cross-region profile ARN before any code is written |
| uv pytest test collision | Phase 1: Monorepo Setup | `uv run --package code-wiki-agent pytest` uses only that package's tests |
| uv single-version enforcement | Phase 1: Monorepo Setup | `uv lock --check` passes in CI after adding each workspace member |
| Vault format drift on round-trip | Phase 1: Core Vault IO | `git diff` empty after write-back on real vault fixture |

---

## Sources

- deepagents issue #694 — parallel subagent cancellation: https://github.com/langchain-ai/deepagents/issues/694
- deepagents issue #1698 — recursion_limit not propagated: https://github.com/langchain-ai/deepagents/issues/1698
- deepagents docs — subagent streaming best practices: https://docs.langchain.com/oss/python/deepagents/frontend/subagent-streaming
- AWS Bedrock token burndown rates: https://docs.aws.amazon.com/bedrock/latest/userguide/quotas-token-burndown.html
- AWS re:Post — parallel LangGraph throttling from TPM reservation: https://repost.aws/questions/QU41JbEn0NStC1P3KB6cd5UA/understanding-bedrock-tpm-deductions-getting-too-many-tokens-with-parallel-langgraph-workflows
- AWS Bedrock on-demand max_tokens limits for Claude Sonnet: https://repost.aws/questions/QUmhH3_oqCTRm1PlshqIWqEg/aws-bedrock-max-tokens-for-claude-models-are-much-lower-when-using-on-demand-throughput
- AWS cross-region inference IAM requirements: https://docs.aws.amazon.com/bedrock/latest/userguide/inference-profiles-prereq.html
- AWS re:Post — access denied with cross-region inference: https://repost.aws/questions/QUapQTuwWdRaKPgojCPts4vg/got-access-deny-in-bedrock-agent-with-cross-region-inference
- Nearform — MCP implementation pitfalls: https://nearform.com/digital-community/implementing-model-context-protocol-mcp-tips-tricks-and-pitfalls/
- LLM-as-judge self-preference bias: https://arxiv.org/abs/2410.21819
- uv workspace gotchas — lock file path collapse: https://github.com/astral-sh/uv/issues/6371
- uv workspace — 3 things I wish I knew: https://dev.to/aws/3-things-i-wish-i-knew-before-setting-up-a-uv-workspace-30j6
- lattice-wiki-core source — truncated frontmatter fix: commit `ae6872e` in `/Users/pat/Personal/lattice/packages/lattice-wiki-core`
- lattice-wiki-core source — placeholder wikilink fix: commits `9502c45`, `9388cdd` in `/Users/pat/Personal/lattice/packages/lattice-wiki-core`
- lattice-wiki-core source — token idempotency and prefix match fix: commit `ae6872e`

---
*Pitfalls research for: deepagents MCP server / AWS Bedrock / parallel subagents / cost-frontier eval / lattice-wiki port*
*Researched: 2026-05-13*
