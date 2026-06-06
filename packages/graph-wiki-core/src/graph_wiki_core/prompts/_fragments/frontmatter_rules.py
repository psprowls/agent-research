# Source: plugins/graph-wiki/agents/ingestor.md §4. Write the source summary

FRONTMATTER_RULES = """\
## Frontmatter rules

Every vault page must have YAML frontmatter (between `---` delimiters) with the
required fields for its role.  Not all fields apply to every role — use the
subset appropriate to the page being written.

**Ingestor source-summary pages** require:
- `title`: descriptive title for the page
- `category`: one of the page category values (`source`, `concept`, `adr`, …)
- `source_type`: classification from the closed enum (`spec`, `article`, `pr`, `ticket`, `transcript`, `example`, `doc`, `note`); classify from content, default `note` when unsure. Files under `raw/<type>/` take the type from the folder. Does NOT control routing — every ingested doc lands under `sources/`
- `target_slug`: URL-safe slug for the output filename (e.g. `auth-design`)
- `summary`: one-line description of the source's main contribution
- `tags`: list of relevant tags (or empty list)

**Scanner stub pages** require:
- `title`: package name
- `category`: `package` (or `app` for applications)
- `summary`: one-line description of what the package does
- `package_path`: relative path of the package in the repo
- `language`: primary language (`python`, `typescript`, `javascript`, `rust`, `go`, `unknown`)

Both roles must include `updated` (today's date) so drift detection can compare timestamps.\
"""
