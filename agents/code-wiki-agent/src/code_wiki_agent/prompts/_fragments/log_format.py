# Source: packages/prompt-sources/wiki-claude-md-template.md
# Anchor: ## Log format (L124-L133)
# Source-commit: ef05d991a9ab1ea12b1bc7ebc1fb20ba70074030

LOG_FORMAT = """\
## Log format

```
## [YYYY-MM-DD] <op> | <title>
<optional detail — which pages touched, what changed>
```

Valid ops: `scan`, `ingest`, `query`, `lint`, `create`, `update`, `delete`, `note`.

Grep the log: `grep "^## \\[" log.md | tail -10`\
"""
