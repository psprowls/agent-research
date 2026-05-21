# Phase 25: packages-dir-misclassification-fix - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-21
**Phase:** 25-packages-dir-misclassification-fix
**Areas discussed:** Majority threshold rule, Loose-.md interaction, --interactive CLI surface, Test coverage scope

---

## Majority threshold rule

Initial framing offered the user a choice between proportional (≥80%) and structural (`manifested >= children - 1`) rules. After the user asked "what does the current implementation do?" and was shown the all-or-nothing gate plus the loose-.md gate, the user rejected the threshold framing entirely.

| Option (offered) | Description | Selected |
|--------|-------------|----------|
| All-but-one (`manifested >= children - 1`) | Forgiving on small dirs (3/4, 2/3 pass) | |
| ≥80% (proportional) | Stricter; matches todo phrasing | |
| Both | Union of the two | |
| ≥80% with min children ≥ 4 | Conservative; leaves small dirs ambiguous | |
| **(User override)** — kill `ambiguous` for the mixed-manifest case entirely; if ≥1 manifested kid, return `package` and silently exclude non-manifested siblings | | ✓ |

**User's choice:** *"I think we should get rid of the ambiguous classification altogether. If there are packages in the directory, create package pages for them and skip the rest."*

**Notes:** This collapses three originally-separate gray areas into one decision: it kills the threshold debate (≥1 → package), kills the loose-.md gate (no longer relevant), and removes the original reason for `--interactive` (no `ambiguous` from this code path to prompt on).

---

## Loose-.md interaction

Implicitly resolved by the threshold-rule decision above. The user's "skip the rest" framing applies to loose `.md` files at the container root just as it does to non-manifested sibling directories — both are silently excluded; the container still classifies as `package`.

| Option | Description | Selected |
|--------|-------------|----------|
| Loose .md still flips to `ambiguous` | Preserves today's gate | |
| **Loose .md silently excluded; container still `package`** | Matches user's "skip the rest" framing | ✓ |

**Notes:** No separate AskUserQuestion was needed; the decision fell out of the threshold area.

---

## --interactive CLI surface

Asked in two sub-questions after the threshold decision rewrote the scope. First sub-question: how the fallback "no clear pattern" cases (lines 132-145 in `detect_containers.py`) should be handled. Second sub-question: what happens to the `--interactive` flag itself.

### Fallback handling

| Option | Description | Selected |
|--------|-------------|----------|
| Drop from records entirely | Cleanest but loses diagnostic visibility on misconfigured monorepos | |
| Keep as `skip` classification | Visible but no wiki page | |
| **Keep `ambiguous` only for the fallback branches** | Mixed-manifest case becomes `package`; truly unrecognized dirs stay `ambiguous` for `--interactive` future use | ✓ |

### --interactive flag

| Option | Description | Selected |
|--------|-------------|----------|
| Drop --interactive from Phase 25 | Wontfix the bonus consideration; smallest scope | |
| --interactive = print summary + confirm | Sanity-check UX without disambiguation prompts | |
| **Defer --interactive to a later phase** | Land the classifier fix now; open a follow-up for the interactive UX (real design question, not a one-liner) | ✓ |

**Notes:** Choosing "defer" means ROADMAP.md success criterion 4 for Phase 25 needs to be removed (D-12 in CONTEXT.md) and a backlog item opened. The fallback decision preserves `ambiguous` as a meaningful classification for the future `--interactive` feature to act on.

---

## Test coverage scope

| Option | Description | Selected |
|--------|-------------|----------|
| Minimum: 5/6 → package + 1/3 → package | Two tests, trust existing coverage | |
| Minimum + loose-.md fixture | Adds a test pinning the new behavior | |
| **Minimum + loose-.md + fallback-ambiguous** | Three tests; locks the boundary between "has manifests" and "no rule matches" | ✓ |
| + plugin shim integration test | Probably overkill given the shim is 9 lines | |

**Notes:** The fallback-ambiguous test is important because the fallback branches in `_classify_dir:132-145` are the only place `ambiguous` can still come from after this phase — pinning that contract keeps `--interactive` (deferred) meaningful when it lands.

---

## Docs sync (`detection-workflow.md`)

| Option | Description | Selected |
|--------|-------------|----------|
| **Yes — update the rule description in this phase** | Lockstep with code per plugin CLAUDE.md invariant | ✓ |
| Yes — only if the doc currently describes the rule | Conditional edit | |
| No — defer to follow-up | Faster phase, slight drift risk | |

**Notes:** Plugin CLAUDE.md explicitly mandates this: "changing one without the other produces drift." The planner should treat `detection-workflow.md` as a required-touch file, not optional.

---

## Claude's Discretion

- Exact `reason` string format for the new `package` classification — Claude proposes `"5/6 children have manifests; 1 skipped"` but the planner/implementer can refine wording.
- Whether to keep or remove the `len(manifest_kids) < len(children)` annotation in the `reason` field after the rule simplifies — minor.
- Exact wording of the "Rules" subsection added to `detection-workflow.md` (D-08) — Claude drafts; user reviews at execute time.

## Deferred Ideas

- **`graph-wiki-agent bootstrap --interactive` flag** — full UX design (what gets prompted, how layout is confirmed, whether MCP path stays non-interactive). Open a backlog item; revisit after Phase 25 ships.
- **MCP `bootstrap` tool interactive semantics** — companion deferral; probably the answer is "MCP stays non-interactive forever" but the decision belongs with the `--interactive` work.
- **Roadmap-level edit** — Phase 25's success criteria 4 and 5 need updating in ROADMAP.md when the planner drafts the plan. Not a separate phase; just a small mutation as part of Phase 25.
