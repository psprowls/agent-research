# Source: cores/prompt-sources/SKILL.md
# Anchor: ## Iron rules (L193-L201)
# Source-commit: ef05d99

IRON_RULES = """\
## Iron rules

1. **The code is the source of truth.** If the vault contradicts the code, the code wins — update the vault.
2. **The LLM never edits files in `raw/`.** Sources are immutable.
3. **All LLM writes for the wiki go under the vault path.** No exceptions.
4. **Every vault page has YAML frontmatter** with `title`, `category`, `summary`, `updated`.
5. **Every ingest or scan touches ≥3 files:** the changed/new page(s), `index.md`, `log.md`.
6. **Every claim on a package/domain page cites** either a source page (`[[sources/xxx]]`) or a code path (`packages/foo/src/bar.ts`).
7. **Good query answers get filed back** — explorations compound.\
"""
