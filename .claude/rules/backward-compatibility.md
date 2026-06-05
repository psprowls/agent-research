---
description: Guidelines when considering backward compatibility
---

This is currently a personal research project with 1 developer and no production vaults.

* We do not need to consider migrations until we reach v2.0 milestones
* User will always delete and rebuild the wiki and graph when a migration is required.
* We should preserve wiki content such as `adrs`, `architecture`, `concepts`, `sources`, and `work` pages.
* `entity` content is split by ownership:
    * **scanner-owned** sections (`## Narrative`, `## File map`, `## Referenced in wiki`) and scanner-owned frontmatter keys are regenerated from the graph every scan — these can be deleted and regenerated at will.
    * **scanner-data** sections (`## Commands`, `## Agents`, `## Skills`, `## Scripts`, `## Hooks`, `## MCP servers`) appear only on `agent_plugin` pages. They are deterministic graph projections rendered from the template every scan and are always template-authoritative — never sourced from the on-disk page. These are an exception to the "any hand-added H2 is human-owned" rule: edits to these sections will be overwritten on the next scan.
    * **human-owned** sections (e.g. `## Purpose`, `## Public API`, any hand-added H2) and human frontmatter keys (`status`, `last_reviewed`, `owner`, `notes`) are preserved across re-scan and should be treated like other curated content.
    * **provenance** key `last_updated_commit` is scanner-stamped (the HEAD at which `## Narrative` was last regenerated) but is preserved across re-scan and is NOT in `SCANNER_OWNED_KEYS`. It gates commit-driven narrative refresh (Living Wiki M2a) — do not move it into `SCANNER_OWNED_KEYS`.
    * **provenance** key `drift_propagated_commit` is scanner-stamped (the entity's `last_updated_commit` at which M4's drift producer last proposed against the curated pages backlinking it) and is preserved across re-scan. Like `last_updated_commit` and `drift_checked_commit` it is NOT in `SCANNER_OWNED_KEYS` — it gates the M4 cross-page drift pass (proposal ledger) and must survive re-scan to keep repeat runs idempotent.

