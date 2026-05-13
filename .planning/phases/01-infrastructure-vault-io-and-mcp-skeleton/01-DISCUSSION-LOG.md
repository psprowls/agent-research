# Phase 1: Infrastructure, Vault IO, and MCP Skeleton - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-13
**Phase:** 1-Infrastructure, Vault IO, and MCP Skeleton
**Areas discussed:** Workspace tier naming + vault-IO home, Round-trip fixture strategy, Bedrock IAM verification artifact, MCP skeleton shape

---

## Workspace tier naming + vault-IO home

### Q1: Top-level workspace directory name for the shared (non-agent) tier?

| Option | Description | Selected |
|--------|-------------|----------|
| cores/ | Matches every planning doc except CLAUDE.md. Reads as "shared building blocks". Means updating CLAUDE.md to align. | ✓ |
| packages/ | Matches CLAUDE.md and most public uv workspace examples. More conventional but loses the cores/agents semantic split. | |
| Other | Different name entirely (e.g., libs/, shared/). | |

**User's choice:** `cores/`
**Notes:** Resolves the CLAUDE.md vs ROADMAP/REQUIREMENTS conflict in favor of the planning docs. CLAUDE.md gets updated as part of Phase 1.

### Q2: Where should vault IO live in v1?

| Option | Description | Selected |
|--------|-------------|----------|
| Shared core: cores/vault-io | Future-proofs for a 2nd agent (V2-AGENT-01). One extra workspace member. | ✓ |
| Inside agents/code-wiki-agent/ | YAGNI; refactor when a 2nd consumer exists. Risk of leaked couplings later. | |
| Other | Split layout_io into core, keep higher-level stuff in agent. | |

**User's choice:** `cores/vault-io`

### Q3: Which workspace members should Phase 1 scaffold?

| Option | Description | Selected |
|--------|-------------|----------|
| Only what Phase 1 needs | vault-io + model-adapter + code-wiki-agent. Defer subagent-runtime + eval-harness. | ✓ |
| All five cores up front | Lock tier shape early, but ships empty placeholders. | |
| Vault-io + agent only | Even leaner; BED-01 as a script. Contradicts model-adapter scaffold. | |

**User's choice:** Only what Phase 1 needs
**Notes:** `cores/subagent-runtime` is owned by Phase 2; `cores/eval-harness` by Phase 4. Owning phase creates the member.

### Q4: How to port lattice-wiki-core modules?

| Option | Description | Selected |
|--------|-------------|----------|
| Copy files into cores/vault-io/src/ | True verbatim port; no source-repo coupling. Accept upstream drift. | ✓ |
| Path-dep on lattice-wiki-core | Auto-syncs updates; couples to ~/Personal/lattice path. | |
| Git submodule | Frozen-pin without path coupling; submodules are friction. | |

**User's choice:** Copy files into `cores/vault-io/src/`

---

## Round-trip fixture strategy

### Q1: Where does the round-trip golden test get its vault pages from?

| Option | Description | Selected |
|--------|-------------|----------|
| Committed snapshot + env-var override for real vault | tests/fixtures/round-trip-vault/ in repo; CODE_WIKI_REAL_VAULT_PATH for local rich runs. | ✓ |
| Committed snapshot only | Pure hermetic; may miss real-vault edge cases. | |
| Env-var path only, no fixtures | CI can't run; on-clone contributors can't either. | |

**User's choice:** Committed snapshot + env-var override

### Q2: How are pages chosen for the committed snapshot?

| Option | Description | Selected |
|--------|-------------|----------|
| Hand-curated edge-case set | ~10-30 pages exercising frontmatter/layout/wikilink edge cases. | |
| Sanitized copy of full real vault | Higher coverage; sanitization script becomes maintained. | ✓ |
| Synthetic generated pages | Hermetic but won't catch real-vault weirdness. | |

**User's choice:** Sanitized copy of full real vault (then immediately revisited in Q3)

### Q3: How does the sanitization step work?

| Option | Description | Selected |
|--------|-------------|----------|
| Manual one-time redact + commit | Simple, predictable, no automation. | |
| Scripted sanitization | Repeatable script, shape-preserving lorem-ipsum. | |
| No sanitization, commit real vault as-is | Simplest. Wiki content isn't sensitive. | ✓ |

**User's choice:** No sanitization, commit as-is
**Notes:** Q2's "sanitized copy" effectively collapsed to "full copy" once the sanitization question came up. Final state: committed real-vault copy at `tests/fixtures/round-trip-vault/` with env-var override for live runs.

### Q4: Truncated-frontmatter (VAULT-05) test placement?

| Option | Description | Selected |
|--------|-------------|----------|
| Dedicated test case | Separate test asserts stderr warning + skip, matches lattice-wiki-core commit ae6872e. | ✓ |
| Folded into main round-trip test | Smaller surface but tangles concerns. | |

**User's choice:** Dedicated test case

---

## Bedrock IAM verification artifact

### Q1: What artifact ships for BED-01?

| Option | Description | Selected |
|--------|-------------|----------|
| Both: pytest integration test + standalone diag script | Test catches regressions; script is what Pat runs first. | ✓ |
| Pytest integration test only | Cleaner, but pytest output is noisy for a "is my account set up" run. | |
| Standalone script only | No permanent regression coverage. | |
| README docs only | Smallest surface; doesn't actually call make_llm() as criterion 2 requires. | |

**User's choice:** Both

### Q2: How is the "actionable ARN" error constructed?

| Option | Description | Selected |
|--------|-------------|----------|
| Catch ClientError, format with the ARN we tried | Self-contained; no extra AWS calls. | ✓ |
| Pre-flight ListInferenceProfiles | Better specificity but adds a second AWS call + IAM requirement. | |
| Plain pass-through of botocore error | Cheapest; doesn't satisfy criterion 2. | |

**User's choice:** Catch ClientError + format

### Q3: Minimal model-adapter shape in Phase 1?

| Option | Description | Selected |
|--------|-------------|----------|
| Tiny models.toml (haiku + sonnet) + lookup function | Phase 2 extends same file; no rewrite. Forces BED-04 from day one. | ✓ |
| Hardcoded ARNs as Python constants | Faster Phase 1; Phase 2 refactors every call site. | |
| Defer model-adapter entirely | Contradicts Area 1 scaffold decision. | |

**User's choice:** Tiny models.toml + lookup function

### Q4: Which Bedrock model IDs ship in Phase 1 models.toml?

| Option | Description | Selected |
|--------|-------------|----------|
| us.anthropic.claude-haiku-4-5-* + us.anthropic.claude-sonnet-4-6-* | Current Haiku 4.5 + Sonnet 4.6 inference profiles. | |
| Haiku only | Tightens scope; Phase 2 immediately needs a 2nd entry. | |
| You decide | Defer exact IDs to research/planning; lock only the structure. | ✓ |

**User's choice:** You decide — Claude discretion
**Notes:** Researcher confirms current cross-region inference-profile ARNs for Haiku 4.5 + Sonnet 4.6 against Pat's account.

---

## MCP skeleton shape

### Q1: MCP skeleton scope for Phase 1?

| Option | Description | Selected |
|--------|-------------|----------|
| FastMCP server + wiki_ping | Drives a tools/call round-trip; proves more wiring. Tiny code cost. | ✓ |
| Empty FastMCP server, zero tools | Minimal; doesn't exercise tools/call path. | |
| Empty server + smoke test | Compromise; no toy tool, more wiring exercised. | |

**User's choice:** FastMCP server + wiki_ping

### Q2: How is the stdout-only-JSON-RPC test built?

| Option | Description | Selected |
|--------|-------------|----------|
| pytest subprocess + parse-every-line + drive tools/call | Asserts every stdout line is JSON. Runs in CI by default. | ✓ |
| Use mcp.client to connect | Idiomatic but hides stdout inspection. | |
| Manual stdout capture, no protocol drive | Cheapest; doesn't exercise tools/call. | |

**User's choice:** pytest subprocess + parse-every-line

### Q3: How is stderr-only logging enforced beyond the subprocess test?

| Option | Description | Selected |
|--------|-------------|----------|
| Module-init guard rebinding sys.stdout | Belt + suspenders with subprocess test. | ✓ |
| Lint rule + convention only | Relies on humans noticing; third-party prints slip through. | |
| Runtime guard + ruff rule | Most defensive (both). | |

**User's choice:** Module-init guard

### Q4: Entry point name + wiki_ping lifecycle?

| Option | Description | Selected |
|--------|-------------|----------|
| code-wiki-agent-mcp + wiki_ping moves to tests/ in Phase 3 | Matches MCP-07 verbatim. | |
| code-wiki-mcp + keep wiki_ping shipped as debug tool | Shorter; wiki_ping stays in production tool list. | ✓ |

**User's choice:** `code-wiki-mcp` + wiki_ping stays shipped
**Notes:** Conflicts with REQUIREMENTS.md MCP-07 (says `code-wiki-agent-mcp`). Planner task in Phase 1: amend MCP-07.

---

## Claude's Discretion

- D-12: Exact Bedrock inference-profile ARNs in `models.toml` — researcher confirms current Haiku 4.5 + Sonnet 4.6 cross-region naming.
- Pre-commit tool combo (ruff + black vs ruff alone vs ruff + ruff-format) — researcher picks based on current consensus.
- `wiki_ping`'s schema shape (free-form input vs fixed enum) — planner decides for exemplary tool wiring.
- CI matrix breadth (3.11 only vs 3.11 + 3.12, linux only vs linux + mac) — planner picks.

## Deferred Ideas

- Full `ModelRegistry` with 7 logical roles + per-role `max_tokens`/`max_concurrency` — Phase 2.
- Token + cost accounting per invocation (BED-05) — Phase 2.
- Pre-flight `bedrock:ListInferenceProfiles` for richer IAM diagnostics — not v1; revisit on demand.
- Vault sanitization script — not adopted; revisit only if a privacy concern emerges.
- CI multi-Python-version matrix — planner's call.
- `bedrock:ListInferenceProfiles` as a startup probe in MCP server — out of v1 scope.
