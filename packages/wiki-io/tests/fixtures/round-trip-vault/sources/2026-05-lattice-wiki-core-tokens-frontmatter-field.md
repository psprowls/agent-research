---
title: "lattice-wiki-core: tokens frontmatter field (design)"
category: source
summary: Approved design spec for the v0.4.0 `tokens:` frontmatter field on every wiki page plus a dedicated `update_tokens.py` script that stamps accurate `cl100k_base` BPE counts via `tiktoken`. Adds `python-frontmatter` for robust YAML round-trip and a soft `missing_tokens` lint group (separate from required-fields). Shipped in v0.4.0.
source_path: lattice/specs/2026-05-11-lattice-wiki-core-tokens-frontmatter-field-design.md
source_type: doc
source_date: 2026-05-11
authors: []
ingested: 2026-05-11
updated: 2026-05-11
tags: [lattice-wiki-core, tokens, frontmatter, tiktoken, lint, context-budget]
tokens: 1818
---

# lattice-wiki-core: tokens frontmatter field (design)

## TL;DR

Approved design spec for stamping accurate LLM token counts on every wiki page so agents can do context-budget planning from frontmatter alone, without re-reading full files. Adds `tiktoken>=0.7` and `python-frontmatter>=1.1` as dependencies, ships a new `update_tokens.py` CLI module that walks the vault and writes `tokens: <count>` (idempotent, `--dry-run` / `--json` supported), seeds every page template with `tokens: 0`, and adds a soft `missing_tokens` lint group that nudges (but does not block) when a page is missing the field. Shipped in `lattice-wiki-core` v0.4.0.

## Key claims

1. **Motivation: context-budget planning.** Agents load wiki pages into context windows; without a stamped count they have to re-read the file to estimate cost. A frontmatter field is queryable with cheap reads.
2. **Encoding choice: `cl100k_base`.** GPT-4 BPE; offline; approximates Claude's tokenizer to ~5% for English prose. Avoids any API call.
3. **Counting scope: full raw file content (frontmatter + body).** That matches what an agent actually loads. The ~5–10 tokens contributed by the `tokens` field itself are negligible.
4. **Idempotency: re-runs are no-ops on unchanged files.** The script writes back only when the new count differs from the stored value, so re-runs don't dirty git.
5. **Dedicated module, not bolted into `update_index.py`.** Same pattern as `wiki_search.py` and `lint_wiki.py` — a CLI-shaped module under `src/lattice_wiki_core/`.
6. **All 18 page templates seed `tokens: 0`.** 11 top-level (`adr`, `app`, `architecture`, `concept`, `concept-pattern`, `dependency`, `domain`, `index`, `package`, `source`, `work`) + 7 sub-templates (`domain/{overview,details}`, `package/{overview,api,context,patterns,work}`). Placeholder is overwritten on first run.
7. **Lint integration is a soft warning, not a required field.** `missing_tokens` is collected separately from the `title`/`category`/`summary` required check, because `tokens` is computed, not authored — absence shouldn't invalidate a page, just prompt a re-run.
8. **CLI flags:** `--dry-run` (print without writing) and `--json` (machine-readable).
9. **Error handling: skip-and-warn.** Files that fail to load (encoding/permission errors) are skipped with a stderr warning; the run continues. Encoding is loaded once and reused.

## Proposed changes (as shipped)

- `packages/lattice-wiki-core/pyproject.toml` — add `tiktoken>=0.7` and `python-frontmatter>=1.1` to `dependencies`.
- `packages/lattice-wiki-core/src/lattice_wiki_core/update_tokens.py` — new module: `get_encoding()`, `count_tokens()`, `iter_pages()`, `update_page()`, `update_vault()`, `main()`.
- `packages/lattice-wiki-core/src/assets/page-templates/*.md` — add `tokens: 0` to all 19 templates, placed after `updated:`.
- `packages/lattice-wiki-core/src/lattice_wiki_core/lint_wiki.py` — collect a `missing_tokens` list; emit a lower-severity section in `print_report` pointing at `update_tokens`.
- New tests:
  - `tests/test_update_tokens.py` — token-count correctness + truncated-frontmatter guard + idempotency.
  - `tests/test_lint_missing_tokens.py` — pages without `tokens:` appear in `missing_tokens`; pages with it do not.

## Surprises and deltas from spec to shipped

Checked the shipped module at `packages/lattice-wiki-core/src/lattice_wiki_core/update_tokens.py` and `lint_wiki.py`. Implementation matches the spec on encoding, deps, lint integration, flags, and idempotency. Notable deltas worth recording:

- **Baseline stripping for stable counts.** The shipped `update_page` does not count tokens on the raw file. It strips any existing `tokens:` line from the YAML frontmatter first, then counts that stripped baseline (`update_tokens.py:84-100`). Without this, the count would shift after the first write (a circular dependency: writing `tokens: 100` changes the file, so the next count is different). The spec said "full raw file content" — the shipped behavior is "full raw file content minus the `tokens` line", which is the only formulation that is actually idempotent.
- **Files without frontmatter are skipped, not stamped.** `update_page` returns `("skipped", 0)` for any file whose first three bytes are not `---` (`update_tokens.py:81-82`). The spec listed only `index.md` / `log.md` and dotdir paths as skips; in practice this also covers ad-hoc files like `CLAUDE.md` schema loaders. Mentioned as "by design" in recent lint reports — `wiki/CLAUDE.md` shows up as one expected `missing-token` entry.
- **Truncated frontmatter is defended against.** If the split yields fewer than three parts (no closing `---`), the file is skipped with a stderr warning (`update_tokens.py:88-92`). Not in the spec, has its own regression test.
- **YAML formatting is preserved by line-level rewrite, not `frontmatter.dumps()`.** The shipped code splits on `---` and updates lines manually so the rest of the YAML formatting (quote style, key order, blank lines) is byte-stable. The spec mentioned `frontmatter.dumps(post)`; the shipped path avoids it to keep diffs minimal.
- **Walks `work/` in addition to `wiki/`.** `update_vault` processes the workspace's `work/` directory (sibling of the wiki) on top of the vault itself (`update_tokens.py:147-151`). The spec implied wiki-only; the shipped behavior matches the v0.3.2 workspace-relative lint model so work items also get token counts.

## Vault drift caught during ingest

`wiki/packages/lattice-wiki-core/lattice-wiki-core.md:76` previously described `update_tokens.py` as writing counts "based on a whitespace-split word count". The shipped implementation uses `tiktoken` with the `cl100k_base` encoding — corrected as part of this ingest.

## Touched

- [[wiki/packages/lattice-wiki-core/lattice-wiki-core]] — corrected `update_tokens.py` description (tiktoken, not whitespace word count); added source ref.
- [[wiki/packages/lattice-wiki-core/api]] — added `update_tokens` entry under Public API; noted `missing_tokens` in the lint dispatcher report shape.

## Links

- Spec: `lattice/specs/2026-05-11-lattice-wiki-core-tokens-frontmatter-field-design.md`
- Module: `packages/lattice-wiki-core/src/lattice_wiki_core/update_tokens.py`
- Lint hook: `packages/lattice-wiki-core/src/lattice_wiki_core/lint_wiki.py:190-202`
- Templates: `packages/lattice-wiki-core/src/assets/page-templates/*.md` (all 19 carry `tokens: 0`)
