# Source: packages/prompt-sources/agents/librarian.md
# Anchor: ## Rules (citation bullets — L73-L77)
# Source-commit: ef05d99

CITATION_RULES = """\
## Citation rules

- **Every claim cites** — a vault page (`[[wikilink]]`) or a code path (`` `path/to/file.py:line` ``).
- **If the vault doesn't know, say so.** Suggest a source to ingest or a concept page to create; don't invent content.
- **Use `[[wikilink]]` syntax** for all cross-references between vault pages. Plain Markdown links are wrong — wikilinks keep renames tracked.
- **Wikilinks must point at existing vault pages.** Never fabricate a wikilink target that doesn't exist in the vault.
- **Cite aggressively.** Every claim on a package/domain page links to a source page or a code path.\
"""
