---
title: Curator Source interface
category: concept
summary: A pluggable adapter contract (`catalog()` + `load(path)`) that turns any markdown knowledge directory into a flat catalog of `{path, title, description, tags}` entries the curator can pick from. Adding a knowledge surface (wiki vault, expert rules, future per-project rule packs) is one new file implementing the interface.
tags: [pattern, adapter, lattice-curator, sources, knowledge]
sources: 1
updated: 2026-05-09
tokens: 1223
---

# Curator Source interface

## Definition

A **Source** is a TypeScript adapter that exposes a markdown knowledge directory to the curator's [[wiki/concepts/two-pass-context-curation|two-pass retriever]] through two methods:

```ts
export interface CatalogEntry {
  source: 'wiki' | 'experts' | string;
  path: string;            // absolute or repo-relative
  title: string;
  description: string;     // from frontmatter
  tags: Record<string, string | string[]>;  // domain, impact, kind, etc.
}

export interface Source {
  readonly name: string;
  catalog(): Promise<CatalogEntry[]>;
  load(path: string): Promise<string>;
}
```

`catalog()` walks a directory once per fire, parses frontmatter, and returns one entry per navigable page (pages without a `description:` are excluded — they're not pickable). `load(path)` reads the full text of a path on demand, called only after Pass 1 selects it.

## Motivation

The curator's value comes from breadth — the more knowledge surfaces it can pick from, the better its briefs. But each surface has its own conventions:

- The [[wiki/plugins/lattice-wiki/lattice-wiki|wiki]] vault uses `category`, `kind`, and per-page `description:` frontmatter.
- The lattice-experts rule library uses `{domain, impact}` frontmatter with `_shared/` collapsed to `domain: shared`.
- A future per-project rule pack might use neither.

Hardcoding the directory walks into the retriever would couple the agent to current vault and rules layouts forever. The `Source` interface inverts the dependency: ==the retriever knows nothing about wiki or experts conventions; it sees only `CatalogEntry[]`==.

## Shape

```
disk layout                      adapter                      retriever input
───────────                      ───────                      ───────────────
wiki/lattice-vault/**/*.md   →   wiki.ts (Source)        ┐
                                                          ├──► flat CatalogEntry[]  →  pass1Pick
experts/rules/<domain>/*.md  →   experts.ts (Source)     ┘    (deduped by path)
```

`buildCatalog` (the first node in the curator's `StateGraph`) fans out to every enabled `Source`, awaits all `catalog()` calls, merges the entries, and dedupes by path. The retriever then reasons over the merged list without knowing which source each entry came from — except via the `source` field, which the brief can cite for provenance.

## Implementation rules

- **Walk once per fire, no caching across fires.** The vault and rules dirs are small (50–500 markdown files); walking is cheap. Caching introduces invalidation bugs.
- **Frontmatter parsing via `gray-matter`.** Malformed-frontmatter files are skipped with a logged path; the catalog continues. One bad file does not poison the fire.
- **Missing source dirs return empty.** If `wiki/` or `rules/` doesn't exist on a project, that source returns `[]`; the retriever continues with the others. Logged with `outcome: 'empty_catalog'` only when *all* sources are empty.
- **Adding a new source = a new file.** No retriever changes, no config schema migration beyond adding the source key.

## Configuration

Per-project `.lattice-curator.json`:

```jsonc
{
  "sources": {
    "wiki":    { "enabled": true, "vaultDir": "wiki" },
    "experts": { "enabled": true, "rulesDir": "plugins/lattice-experts/rules" }
  }
}
```

Source toggles are coarse (whole-source on/off). Finer-grained filtering (e.g. "only `domain: react-native` from experts") is handled inside the LLM picks via Pass 1 prompt instructions — not at the source level, to keep the adapters dumb.

## Used in

- [[wiki/packages/lattice-curator-core/lattice-curator-core]] — defines the interface in `src/sources/types.ts`; ships `wiki.ts` and `experts.ts` adapters. New sources slot in without retriever edits.

## Related patterns

- [[wiki/concepts/two-pass-context-curation]] — the consumer of the catalog the `Source` produces.
- [[wiki/concepts/lattice-cross-plugin-contract]] — the broader "plugins consume each other through narrow interfaces, not imports" posture the curator honors.

## Sources

- 2026-05-context-curation-agent-design — introduces the `Source` interface, the `wiki.ts` and `experts.ts` adapters, and the "adding a source = one new file" guarantee.

## Open questions / gotchas

- **Per-project rule includes.** A project's `CLAUDE.md` occasionally references rules not in `lattice-experts`. v1 has no `Source` for these; the spec notes the interface admits adding one later.
- **The user's `~/.claude/CLAUDE.md`.** Out of v1 scope; could be a `Source` if the curation surface ever expands beyond per-repo.
- **Generic third-party plugin skills.** Same posture as above — extensible, but not in v1.
