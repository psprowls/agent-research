# wiki — Code Wiki

> **Topic:** my-utils library
> **Repo:** /path/to/my-utils
> **Initialized:** 2026-05-14
> **Tool:** Claude Code (this file).

You are the maintainer of this wiki. Read from the repo's source code. Write to pages under this wiki directory.

## Where the wiki sits

```
<workspace>/
├── wiki/   → this wiki — you own everything here
│   ├── CLAUDE.md
│   └── …
```

## Wiki structure

```
index.md                  → content catalog
log.md                    → append-only timeline
packages/                 → library packages
└── my-utils/
    └── my-utils.md       →   the package overview
concepts/                 → cross-cutting technical concepts
adrs/                     → architecture decision records
```

## Page frontmatter (required on every wiki page)

```yaml
---
title: <Title>
category: app | package | domain | concept | dependency | work | source | architecture | adr
summary: <one-line summary>
tags: [tag1, tag2]
updated: YYYY-MM-DD
---
```

```yaml
version: 1
detected_at: 2026-05-14
repo_root: ..
containers:
  - source: .
    vault_dir: packages
    classification: single-package
    children_count: 1
```
