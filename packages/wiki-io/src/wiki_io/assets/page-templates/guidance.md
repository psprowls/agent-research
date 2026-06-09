---
title: <Guidance title>
category: guidance               # spine — fixed value
summary: <one-line — what to do and why, also a relevance signal>
topic: <topic>                   # taxonomy axis + folder name under wiki/guidance/
applies_when: <one-sentence prose trigger — what the curator ranks against>
triggers:                        # structured pre-filter — block + all keys optional
  globs: []                      # e.g. ['**/*.tsx']
  keywords: []                   # e.g. [ScrollView, FlatList, virtualization]
  entities: []                   # e.g. ['[[entities/pkg_...]]'] — curate by code the task touches
tags: []                         # coarse free-form filter
impact: medium                   # critical | high | medium | low
source:                          # provenance — imported skill/repo the bit came from
updated: <YYYY-MM-DD>
tokens: 0
---

# <Guidance title>

## Guidance
The prescriptive bit: how to do X correctly, and why it matters.

## Incorrect
```
# the anti-pattern this guidance steers away from
```

## Correct
```
# the recommended approach
```

## Applies to
- [[entities/<prefix>_<name>]]
