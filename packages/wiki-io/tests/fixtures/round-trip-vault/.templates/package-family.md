---
title: <Family Name>
category: dependency
kind: package-family
family_name: <family-slug>
members:                          # packages shipped under the family's brand
  - <member-package>
co_required: []                   # tooling that travels with the family in practice
load_bearing: true
upstream_url:
tags: []
updated: <YYYY-MM-DD>
---

# <Family Name>

## What it is
One paragraph: what this family covers, why we treat it as a unit, where it shows up.

## Members
- `<member-package>` — short note on its role in the family

## Co-required tooling
- `<tool>` — why it travels with the family

## Key patterns in this repo
- …

## Gotchas / workarounds
- …

## Decisions
- [[adrs/<id>-<slug>]]

## Related
- [[dependencies/<member>]]
- [[concepts/<concept>]]
