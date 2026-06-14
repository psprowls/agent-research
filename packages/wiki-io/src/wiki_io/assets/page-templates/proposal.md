---
kind: adr               # adr | concept
# concept_kind: pattern # required only when kind: concept (e.g. pattern | architecture); omit for adr
mode: create_new        # create_new | update_existing
target_slug: <slug>
title: <title>
status: proposed        # proposed | approved | rejected | created
# rank / confidence are optional ranking keys set by the proposal reasoner, not by hand authors.
origins:
  - ref: sources/<slug>
    source: ingest       # ingest | drift
    rationale: <why this change is proposed>
    evidence:
      - <supporting claim>
    # Optional — each list below feeds the same-named body section in render_proposal_body():
    # existing_pages_considered:
    #   - concepts/<related-page>
    # reasoning_summary:
    #   - <one-line summary>
    # potential_conflicts:
    #   - <claim this may contradict>
    # implementation_notes:
    #   - <note for whoever applies this>
---

<!-- Body regenerated from origins[] while status: proposed. Do not edit here;
     approve via `gw wiki proposal approve <kind>-<target_slug>`. -->
<!-- render_proposal_body() emits, in order: Suggested Action, Evidence From Source,
     Existing Pages Considered, Reasoning Summary, Potential Conflicts,
     Implementation Notes, Origins. -->

## Suggested Action

<action line rendered by render_proposal_body()>

## Evidence From Source

<evidence bullets rendered from origins[].evidence>
