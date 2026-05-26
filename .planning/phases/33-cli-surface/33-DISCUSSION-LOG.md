# Phase 33: CLI Surface - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-25
**Phase:** 33-cli-surface
**Areas discussed:** what-tests dispatch (CLI-07/08), Empty-state messaging, list-scripts annotation (CLI-04), Output verbosity defaults

---

## what-tests dispatch

### Q1: Disambiguation strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Probe both, error on ambiguity | Package first, Domain fallback, error if both | ✓ |
| Explicit --kind required when ambiguous | Less ergonomic | |
| Always prefer Package | Hides Domain matches | |
| Two separate subcommands | Loses natural-language ergonomics | |

**User's choice:** Probe both, error on ambiguity.
**Notes:** D-01 in CONTEXT.md.

### Q2: --kind flag

| Option | Description | Selected |
|--------|-------------|----------|
| Add optional --kind {package,domain} flag | Short-circuits probe; helps scripts | ✓ |
| No flag | Force rename on conflicts | |
| Required from start | Removes ergonomics | |

**User's choice:** Add optional --kind {package,domain} flag.
**Notes:** D-02 in CONTEXT.md.

---

## Empty-state messaging

### Q1: --fmt human empty result

| Option | Description | Selected |
|--------|-------------|----------|
| Print nothing, exit 0 | Clean for scripting | |
| Print informational stderr message, empty stdout | Best of both | ✓ |
| Print '(no results)' to stdout | Friendly but breaks pipes | |

**User's choice:** Print informational stderr message, empty stdout.
**Notes:** D-03 in CONTEXT.md.

### Q2: --fmt json empty result

| Option | Description | Selected |
|--------|-------------|----------|
| Empty array/object on stdout, no stderr | Standard JSON conventions | ✓ |
| Empty array + stderr message | Mirror human path | |
| Suppress both streams entirely | Hostile to JSON consumers | |

**User's choice:** Empty array/object on stdout, no stderr.
**Notes:** D-03 in CONTEXT.md.

### Q3: Uniform across all list-*/describe-*?

| Option | Description | Selected |
|--------|-------------|----------|
| Uniform across all list-*/describe-* CLIs | Predictable | ✓ |
| Only domain CLIs per SC#2 strict reading | Asymmetric | |
| describe-* exits 1 on missing; list-* exits 0 | Differentiates missing-target | |

**User's choice:** Uniform across all list-*/describe-* CLIs.
**Notes:** D-03 in CONTEXT.md.

### Q4: describe-* with missing target

| Option | Description | Selected |
|--------|-------------|----------|
| Exit 1, stderr 'not found: <name>' | Matches existing q_describe_package.py | ✓ |
| Exit 0, empty result like no-domains case | Loses signal | |
| Exit 1 only in JSON, 0 in human | Inconsistent across formats | |

**User's choice:** Exit 1, stderr 'not found: <name>'.
**Notes:** D-04 in CONTEXT.md.

---

## list-scripts annotation

### Q1: Output format

| Option | Description | Selected |
|--------|-------------|----------|
| Annotated lines, dedup by file path | [declared: ...] / [conventional] tags | ✓ |
| Two sections | ## Declared then ## Conventional | |
| Plain paths, no annotation | Loses why | |

**User's choice:** Annotated lines, dedup by file path.
**Notes:** D-05 in CONTEXT.md.

### Q2: Sort order

| Option | Description | Selected |
|--------|-------------|----------|
| Alphabetical by file path | Predictable, grep-friendly | ✓ |
| Declared first then conventional | Surface 'real' scripts first | |
| By package then alphabetical | Group by directory | |

**User's choice:** Alphabetical by file path.
**Notes:** D-06 in CONTEXT.md.

---

## Output verbosity defaults

### Q1: list-* command human format

| Option | Description | Selected |
|--------|-------------|----------|
| One name per line, no header | Greppable, pipe-friendly | ✓ |
| Columnar with header | Readable; breaks scripts | |
| Indented tree-ish | Visual but separate mode | |

**User's choice:** One name per line, no header.
**Notes:** D-08 in CONTEXT.md.

### Q2: describe-* human format

| Option | Description | Selected |
|--------|-------------|----------|
| Compact key-value lines | Matches q_describe_package.py | ✓ |
| Indented multi-section blocks | Richer; more elaborate | |
| YAML-like text mirroring json | Tight coupling; heavyweight | |

**User's choice:** Compact key-value lines.
**Notes:** D-10/D-11 in CONTEXT.md.

### Q3: cross-cutting output shape

| Option | Description | Selected |
|--------|-------------|----------|
| name + score columns aligned | Visible score, greppable | ✓ |
| Just names sorted by score | Loses score in human | |
| Verbose: name + score + distinct + which-domains | Most informative; noisy | |

**User's choice:** name + score columns aligned.
**Notes:** D-12 in CONTEXT.md.

### Q4: domain-refs / domain-deps output

| Option | Description | Selected |
|--------|-------------|----------|
| Three columns for refs, two for deps | Both metrics visible | ✓ |
| Just name + total_usage_count for both | Hides distinct count | |
| Name only, sorted by usage | Minimum signal | |

**User's choice:** Three columns for domain-refs, two for domain-deps.
**Notes:** D-13/D-14 in CONTEXT.md.

### Q5: cg status extension (CLI-14)

| Option | Description | Selected |
|--------|-------------|----------|
| Prepend 'repository: <uri>' line | Visible at top; minimal disruption | ✓ |
| Append at bottom | Less prominent | |
| --verbose flag opt-in | Diverges from CLI-14 intent | |

**User's choice:** Prepend 'repository: <uri>' line.
**Notes:** D-15 in CONTEXT.md.

---

## Claude's Discretion

- Exact stderr wording per empty-state command
- Column padding strategy (fixed, tab-stop, longest-key-aligned)
- Whether list-entry-points adds optional --package flag for all-package listing
- Internal _resolve_node helper shape for what-tests probe
- describe-suite accepts name or URI (recommend name)
- argparse help strings per subcommand
- argparse subgroup help formatting deferred to v1.7

## Deferred Ideas

- cg list-repositories CLI binding (v1.7)
- --fmt yaml mode
- argparse subgroup help in --help
- Shell completion (zsh/bash/fish)
- cg what-uses inverse query
- Pagination / --limit on large repos
- Output coloring / ANSI formatting
- JSON streaming for large results
- cg find --domain filter
- cg describe-entry-point binding
