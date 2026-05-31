# Decisions Register

<!-- Compact projection restored for M001/S04 readiness verification. Do not edit rows manually when adding new decisions; use the GSD decision tool so the DB-backed register remains canonical. -->

| # | When | Scope | Decision | Choice | Rationale | Revisable? | Made By |
|---|------|-------|----------|--------|-----------|------------|---------|
| D001 | M001 initialization | gsd-initialization | Initialize GSD from current truth and high-value legacy notes, not from a full `.planning` conversion. | Lean current-truth initialization | The legacy archive is large and mixed with stale, shipped, deferred, and superseded work; copying it wholesale would make `.gsd/` noisy and risk treating old plans as active commitments. | Yes | collaborative |
| D002 | M001 initialization | migration-approach | Use manual curation for M001 rather than reusable `.planning` migration or backfill tooling. | Manual curation over migration tooling | The user confirmed manual curation is sufficient, and the immediate goal is usable `.gsd/` state rather than converter infrastructure for an already-backed-up archive. | Yes | collaborative |
| D003 | M001 initialization | archive-boundary | Preserve high-value caveats and deferred work as labeled context without promoting them to active M001 execution. | Preserve caveats without activating deferred work | Deferred cost-frontier sweep work, stale snapshot maintenance, and process-debt notes matter for future planning, but they carry separate cost/risk and should only become active after fresh scoping. | Yes | collaborative |
