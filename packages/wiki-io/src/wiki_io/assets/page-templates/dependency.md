---
title: <library-name>
category: dependency
kind: package                    # package | service
package_name: <registry-name>    # for kind: package
ecosystem: npm                   # for kind: package — npm | pypi | cargo | go | brew | system
service_name:                    # for kind: service
provider:                        # for kind: service — aws | gcp | azure | mongodb-atlas | cloudflare | github | …
family: ""                       # free-form grouping back-pointer; empty otherwise
versions_in_use: []              # kind: package only
used_by: []
upstream_url:
load_bearing: true               # detail page exists ⇒ load_bearing
quirks: []
tags: []
updated: <YYYY-MM-DD>
tokens: 0
---

# <library-name>

## What it is
One paragraph: what this library/service does, why we use it, which surfaces.

## Versions in use
| Version | Used in | Notes |
|---|---|---|
| | | |

## Used by
- [[packages/<pkg>]]

## Key patterns in this repo
- …

## Gotchas / workarounds
- …

## Upgrade history
- **<YYYY-MM>** — note

## Decisions
- [[adrs/<id>-<slug>]]

## Related
- [[dependencies/<other>]]
- [[concepts/<concept>]]
