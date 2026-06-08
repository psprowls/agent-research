#!/usr/bin/env python3
"""Migrate bare-slug wikilinks in mono-repo curated pages to the current entities/ schema.

Edits concepts/adrs/architecture/sources/work pages in place. Idempotent (skips links
already in entities/ form). Prints a dispositioned report and exits non-zero if any link
is left unresolved.
"""

import glob
import os
import re
import sys
from collections import defaultdict

WIKI = os.path.expanduser("~/Personal/mono-repo/graph-wiki/wiki")
CURATED = ["concepts", "adrs", "architecture", "sources", "work"]
# A bare slug colliding across kinds resolves to the FIRST prefix here (pkg/app over tests).
PREFIX_PRIORITY = ["app_", "pkg_", "dep_", "repo_", "unit_tests_"]
# Bare domain names -> authored domain concept pages (Task 2). Rewritten as pass-through links.
DOMAIN_MAP = {
    d: f"domain-{d}" for d in ["location", "healthkit", "timeline", "device", "reference", "shared", "financial"]
}
# No entity, no curated page, not a domain -> demote to plain text and log.
UNRESOLVABLE = {
    "location-legacy-py",
    "autogen-dev-team-py",
    "source-code-tools-py",
    "populate-endpoints-and-data-models",
    "coding",
}


def entity_index():
    idx = defaultdict(dict)  # bare-slug -> {prefix: full-stem}
    for fn in os.listdir(os.path.join(WIKI, "entities")):
        if not fn.endswith(".md") or fn == "index.md":
            continue
        stem = fn[:-3]
        for p in PREFIX_PRIORITY:
            if stem.startswith(p):
                idx[stem[len(p) :]][p] = stem
                break
    return idx


def curated_set():
    s = set()
    for d in CURATED:
        for fp in glob.glob(os.path.join(WIKI, d, "*.md")):
            b = os.path.basename(fp)[:-3]
            if b != "index":
                s.add(b)
    # the domain pages from Task 2 are real curated targets too
    s.update(DOMAIN_MAP.values())
    return s


ENT = entity_index()
CUR = curated_set()
LINK = re.compile(r"\[\[([^\]]+)\]\]")
report = defaultdict(list)
counts = {"passthrough": 0}


def split(inner):
    raw, alias = (inner.split("|", 1) + [""])[:2]
    raw, anchor = (raw.split("#", 1) + [""])[:2]
    return raw.strip(), ("#" + anchor if anchor else ""), ("|" + alias if alias else "")


def replace(m):
    inner = m.group(1)
    slug, anchor, alias = split(inner)
    if slug.startswith("entities/"):  # already migrated -> idempotent
        return m.group(0)
    if slug in DOMAIN_MAP:  # bare domain -> domain-<name>
        report["domain"].append(slug)
        return f"[[{DOMAIN_MAP[slug]}{anchor}{alias}]]"
    if slug in CUR:  # curated page -> unchanged
        counts["passthrough"] += 1
        return m.group(0)
    if slug in ENT:  # code entity -> entities/<stem> (prefix priority)
        for p in PREFIX_PRIORITY:
            if p in ENT[slug]:
                report["rewritten"].append(slug)
                return f"[[entities/{ENT[slug][p]}{anchor}{alias}]]"
    if slug in UNRESOLVABLE:  # demote to plain text
        report["demoted"].append(slug)
        return alias[1:] if alias else slug  # drop the brackets; keep alias text or the word
    report["unresolved"].append(slug)  # gate failure
    return m.group(0)


for d in CURATED:
    for fp in glob.glob(os.path.join(WIKI, d, "*.md")):
        txt = open(fp).read()
        new = LINK.sub(replace, txt)
        if new != txt:
            open(fp, "w").write(new)

print("REWRITTEN code-entity :", len(report["rewritten"]), "links")
print("DOMAIN -> domain-*    :", len(report["domain"]), "links", sorted(set(report["domain"])))
print("PASS-THROUGH curated  :", counts["passthrough"], "links")
print("DEMOTED to plaintext  :", sorted(set(report["demoted"])))
print("UNRESOLVED (GATE)     :", sorted(set(report["unresolved"])))
sys.exit(1 if report["unresolved"] else 0)
