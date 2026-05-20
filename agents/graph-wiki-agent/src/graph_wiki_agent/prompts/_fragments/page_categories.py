# Source: packages/prompt-sources/SKILL.md
# Anchor: ## Page categories (table — L143-L155)
# Source-commit: ef05d99

PAGE_CATEGORIES = """\
## Page categories

| Category | What it documents | Directory |
|---|---|---|
| `app` | One application workspace (web, mobile, CLI) — platform, entry points, domains consumed, deployment | `vault_path/apps/<app>/<app>.md` |
| `package` | One library/service workspace — what it exports, who depends on it, key patterns | `vault_path/packages/<pkg>/<pkg>.md` |
| `domain` | A feature area spanning multiple packages (e.g. "auth", "billing") | `vault_path/domains/<domain>/<domain>.md` |
| `concept` | Cross-cutting technical idea (e.g. "GlobalContext pattern", "integration test setup"). Comparisons (`<a>-vs-<b>.md`) live here too. | `vault_path/concepts/` |
| `dependency` | An external package, package family, or service the monorepo depends on — `kind:` discriminates | `vault_path/dependencies/` |
| `work` | Unified bug / tech-debt / feature / initiative / spike — replaces issues + roadmap | `work/` (sibling of the vault; owned by the workspace manager) |
| `source` | Summary of an ingested spec, PR, article, transcript, etc. | `vault_path/sources/` |
| `architecture` | High-level synthesis — build system, module graph, request flow, deployment topology | `vault_path/architecture/` |
| `adr` | Architecture Decision Record — a dated, citable decision with context + consequences | `vault_path/adrs/` |\
"""
