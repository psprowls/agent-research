# Source: plugins/graph-wiki/skills/graph-wiki/SKILL.md §Page categories

PAGE_CATEGORIES = """\
## Page categories

| Category | What it documents | Directory |
|---|---|---|
| `app` | One application workspace (web, mobile, CLI) — platform, entry points, deployment | `vault_path/entities/app_<name>.md` |
| `package` | One library/service workspace — what it exports, who depends on it, key patterns | `vault_path/entities/pkg_<name>.md` |
| `concept` | Cross-cutting technical idea, pattern, or architecture synthesis. Optional `kind:` frontmatter — `concept` (default), `pattern`, or `architecture` — selects the page template. Comparisons (`<a>-vs-<b>.md`) live here too. | `vault_path/concepts/` |
| `dependency` | An external package or service the monorepo depends on — `kind:` discriminates | `vault_path/entities/dep_<name>.md` |
| `work` | Unified bug / tech-debt / feature / epic / spike — replaces issues + roadmap | `work/` (sibling of the vault; owned by the workspace manager) |
| `source` | Summary of an ingested spec, PR, article, transcript, etc. | `vault_path/sources/` |
| `adr` | Architecture Decision Record — a dated, citable decision with context + consequences | `vault_path/adrs/` |\
"""
