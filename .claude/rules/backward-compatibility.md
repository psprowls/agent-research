---
description: Guidelines when considering backward compatibility
---

This is currently a personal research project with 1 developer and no production vaults.

* We do not need to consider migrations until we reach v2.0 milestones
* User will always delete and rebuild the wiki and graph when a migration is required.
* We should preserve wiki content such as `adrs`, `architecture`, `concepts`, `sources`, and `work` pages.
* `entity` content is split by ownership:
    * **scanner-owned** sections (`## Narrative`, `## File map`, `## Referenced in wiki`) and scanner-owned frontmatter keys are regenerated from the graph every scan — these can be deleted and regenerated at will.
    * **human-owned** sections (e.g. `## Purpose`, `## Public API`, any hand-added H2) and human frontmatter keys (`status`, `last_reviewed`, `owner`, `notes`) are preserved across re-scan and should be treated like other curated content.
    * **provenance** key `last_updated_commit` is scanner-stamped (the HEAD at which `## Narrative` was last regenerated) but is preserved across re-scan and is NOT in `SCANNER_OWNED_KEYS`. It gates commit-driven narrative refresh (Living Wiki M2a) — do not move it into `SCANNER_OWNED_KEYS`.

