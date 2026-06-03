# Source: plugins/graph-wiki/skills/graph-wiki/SKILL.md §Page categories

PAGE_CATEGORIES = """\
## Page categories

| Category | What it documents | Directory |
|---|---|---|
| `app` | One application workspace (web, mobile, CLI) — platform, entry points, domains consumed, deployment | `vault_path/entities/app_<name>.md` |
| `package` | One library/service workspace — what it exports, who depends on it, key patterns | `vault_path/entities/pkg_<name>.md` |
| `domain` | A feature area spanning multiple packages (e.g. "auth", "billing") | `vault_path/entities/domain_<name>.md` |
| `concept` | Cross-cutting technical idea (e.g. "GlobalContext pattern", "integration test setup"). Comparisons (`<a>-vs-<b>.md`) live here too. | `vault_path/concepts/` |
| `dependency` | An external package or service the monorepo depends on — `kind:` discriminates | `vault_path/entities/dep_<name>.md` |
| `work` | Unified bug / tech-debt / feature / initiative / spike — replaces issues + roadmap | `work/` (sibling of the vault; owned by the workspace manager) |
| `source` | Summary of an ingested spec, PR, article, transcript, etc. | `vault_path/sources/` |
| `architecture` | High-level synthesis — build system, module graph, request flow, deployment topology | `vault_path/architecture/` |
| `adr` | Architecture Decision Record — a dated, citable decision with context + consequences | `vault_path/adrs/` |\
"""
