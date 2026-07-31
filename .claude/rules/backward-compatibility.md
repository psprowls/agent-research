---
description: Guidelines when considering backward compatibility
---

This is currently a personal research project with 1 developer and no production vaults.

* We do not need to consider migrations until we reach v2.0 milestones
* User will always delete and rebuild the wiki and graph when a migration is required.
* We should preserve wiki content such as `adrs`, `architecture`, `concepts`, `sources`, and `work` pages.
* `entity` content is split into two classes by how it's produced, not by who may overwrite it:
    * **deterministic** sections (`## Referenced in wiki`, the `## File map` row set, and — on `agent_plugin` pages only — `## Commands`, `## Agents`, `## Skills`, `## Scripts`, `## Hooks`, `## MCP servers`) are pure graph projections, re-rendered from the template on every scan at zero model cost. They can be deleted and regenerated at will and are always template/graph-authoritative — never sourced from the on-disk page, even if hand-edited.
    * **prose** sections (`## Narrative`, `## Purpose`, `## Public API`, the File map description column, and any other H2) are model-maintained: written when the page is born, then updated only by the diff-driven refresh pass when the commit range since `last_updated_commit` touches the entity's files. No section is mechanically protected — the refresh prompt treats current page text as ground truth to preserve unless the code diff contradicts it. Human-preserved frontmatter keys (`status`, `last_reviewed`, `owner`, `notes`, and any key outside `DATA_KEYS`) follow the same "respected as input" rule.
    * **provenance** key `last_updated_commit` is scanner-stamped (the HEAD at which prose sections were last refreshed) but is preserved across re-scan and is NOT in `DATA_KEYS`. It gates the diff-driven prose-refresh pass — do not move it into `DATA_KEYS`.
    * **provenance** key `drift_propagated_commit` is scanner-stamped (the entity's `last_updated_commit` at which M4's drift producer last proposed against the curated pages backlinking it) and is preserved across re-scan. Like `last_updated_commit`, it is NOT in `DATA_KEYS` — it gates the M4 cross-page drift pass (proposal ledger) and must survive re-scan to keep repeat runs idempotent.

