---
command: query
upstream_source: plugins/lattice-wiki/commands/query.md
port_verdict: rename
---

# /graph-wiki:query — Port Spec

## Shell-out contract

**Primary path — LLM-driven (no shell-out):**

Primary path is in-session Claude Code inference per P-01; the librarian sub-agent (`agents/librarian.md`) runs synthesis inside the Claude Code host session. No `uv run` invocation on the primary path. The librarian reads `index.md`, drills into 3–10 relevant pages, follows wikilinks opportunistically, synthesizes an answer, and offers to file the answer back — all via Claude Code's own inference, exactly as upstream lattice-wiki does today.

**Fallback path — BM25 search (shells out to Python):**

The BM25 fallback fires only when the LLM-driven primary path is insufficient (vault doesn't cover the question). Invocation:

```bash
uv run --project "$DEEP_AGENTS_ROOT" python3 "${CLAUDE_PLUGIN_ROOT}/skills/graph-wiki/scripts/wiki_search.py" $ARGUMENTS
```

- **Target module (claude backend, fallback only):** `vault_io.wiki_search.main`
  - **NOTE (VP-01 prerequisite):** `wiki_search.py` (~194 LOC) must be ported from `lattice_wiki_core` to `vault_io` as Phase 14 Plan 2 before this shim's fallback path works. The module does not exist in `vault_io` today.
- **Target subprocess (bedrock backend):** `code-wiki-agent query <args>` — note the bedrock branch covers the entire query flow (LLM synthesis included), not just the fallback, since `code-wiki-agent query` already contains both search and synthesis internally.

**Args pass-through:**

| Upstream flag | Ported flag | Notes |
|---|---|---|
| `--query "<terms>"` | `--query "<terms>"` | Passed verbatim to `wiki_search.py` on the fallback path |
| `--limit N` | `--limit N` | Passed verbatim; controls BM25 result count |
| (positional question) | (positional question) | The slash command's first argument; handled by the librarian agent on primary path |

**VP-01 callout:**

> **Prerequisite** — `wiki_search.py` (~194 LOC) must be ported from `lattice_wiki_core` to `vault_io` as Phase 14 Plan 2 before this shim's BM25 fallback path works. Until that port lands, the fallback branch will fail with an `ImportError` on `vault_io.wiki_search`. The primary LLM-driven path is unaffected.

## Prose-preservation map

Walk of every H2 section in upstream `commands/query.md`:

| Upstream section | Verdict | Notes |
|---|---|---|
| `## Usage` | verbatim except namespace rename | `/lattice-wiki:query` → `/graph-wiki:query` in all example invocations |
| `## What happens` | verbatim except step 4 wording | Step 4 `scripts/wiki_search.py` path updated to `skills/graph-wiki/scripts/wiki_search.py`; all other steps are identical |
| `## Output formats` | verbatim | No behavior change; table content is query-shape-agnostic |
| `## Sub-agent` | verbatim except agent reference prose | Agent file stays `agents/librarian.md`; internal prose rebranded (lattice-wiki → graph-wiki namespace strings only) |
| `## Rules` | verbatim | Iron rules unchanged per P-03 |
| `## Skill Reference` | namespace rename only | `lattice-wiki/SKILL.md` → `graph-wiki/SKILL.md`; `lattice-wiki/references/query-workflow.md` → `graph-wiki/references/query-workflow.md` |

## Agent / skill rename map

| Asset | From | To | Touch |
|---|---|---|---|
| Librarian agent | `agents/librarian.md` | `agents/librarian.md` | Name stays; internal namespace prose rebranded (lattice-wiki → graph-wiki; `/lattice-wiki:query` → `/graph-wiki:query`); shim invocation in step 4 updated to graph-wiki path |
| Skill index | `skills/lattice-wiki/SKILL.md` | `skills/graph-wiki/SKILL.md` | Rename + namespace rebrand (boilerplate inherited; not query-specific) |
| Query reference doc | `skills/lattice-wiki/references/query-workflow.md` | `skills/graph-wiki/references/query-workflow.md` | Rename + namespace rebrand |
| BM25 shim script | `skills/lattice-wiki/scripts/wiki_search.py` | `skills/graph-wiki/scripts/wiki_search.py` | Retarget import from `lattice_wiki_core.wiki_search` → `vault_io.wiki_search`; bedrock branch shells to `code-wiki-agent query` instead of `lattice_wiki_agent.agents.query.QueryAgent` |

## Reshape notes

Verdict is `rename` because user-facing behavior is preserved byte-for-byte. The only structural difference from upstream is in the shim's bedrock branch: upstream routes into `lattice_wiki_agent.QueryAgent` (a Bedrock-backed in-process agent), whereas the ported shim routes into `code-wiki-agent query` as a subprocess. This is an implementation detail invisible to the user — both paths produce the same synthesized answer output.

The shell-out invocation fires only on the BM25-fallback branch of the primary LLM-driven flow. The primary path (librarian sub-agent doing synthesis inside Claude Code) stays inside the Claude Code host session per P-01. This mirrors upstream exactly: upstream's `agents/librarian.md` step 4 says "Fall back" to `scripts/wiki_search.py` only if the vault doesn't cover the question.

**Prerequisite:** VP-01 wiki_search.py port (Phase 14 Plan 2) must land before the fallback path works end-to-end.

## Verification gate

**Primary path smoke:**

Run `/graph-wiki:query "what is workspace-io?"` inside a Claude Code session in a workspace that has a populated `wiki/` tree (e.g., `~/Personal/wiki/deep-agents`). Expected: the librarian sub-agent reads `wiki/index.md`, selects relevant pages, synthesizes an answer with `[[wikilinks]]` citations, and offers to file the answer back. Output should match the Phase 14 SC#4 smoke test behavior — a librarian answer citing graph-wiki code paths, modulo brand strings versus upstream.

**Fallback path smoke (requires VP-01 to be complete):**

Trigger a no-LLM path by testing `wiki_search.py` directly:

```bash
uv run --project "$DEEP_AGENTS_ROOT" python3 "${CLAUDE_PLUGIN_ROOT}/skills/graph-wiki/scripts/wiki_search.py" --query "workspace-io" --limit 5
```

Confirm: BM25 results surface relevant wiki pages. Match upstream output modulo brand strings (`graph-wiki` where upstream had `lattice-wiki`; `vault_io` where upstream had `lattice_wiki_core`).

**Namespace smoke:**

Confirm the command responds to `/graph-wiki:query` (not `/lattice-wiki:query`) in the Claude Code plugin autocomplete.

See SHELL-OUT-PATTERN.md §SO-01 for the invocation shape and §SO-02 for the shim pattern. See CONTEXT.md §P-01 for the inference-path reframe and §VP-01 for the wiki_search.py prerequisite.
