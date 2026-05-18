---
phase: 11
slug: workspace-io-port-m1
status: verified
threats_open: 0
asvs_level: 1
created: 2026-05-18
---

# Phase 11 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.
>
> Phase 11 ports `lattice-workspace` (workspace bootstrap, manifest IO, config
> resolution) into `packages/workspace-io/` and turns `vault-io._workspace`
> into a delegation shim. The phase is a port + delegation refactor of code
> that already shipped in `lattice-wiki-core`, so all threats reduce to: same
> trust boundaries, same controls, no new attack surface.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| env (`GRAPH_WIKI_WORKSPACE`) → `workspace_io.config` | Untrusted env path supplies the workspace root | Filesystem path (string) |
| filesystem → `workspace_io.manifest` | `.graph-wiki.yaml` content parsed at read time | YAML structured data |
| filesystem → `workspace_io._local_config` | `.graph-wiki.local.yaml` user-supplied paths | YAML structured data |
| MCP client → `vault_io._workspace.resolve_wiki_and_repo` | `vault_path` arg from MCP tool call | Filesystem path (string) |
| CLI user → `code_wiki_agent init` → `workspace_io.init` | `--vault` arg, current cwd | Filesystem path (string) |
| `code_wiki_agent` ↔ MCP Field descriptions | User-visible tool schema | Static documentation strings |
| filesystem → asset template (`CLAUDE.md.template`) | Template shipped inside wheel | Static text |
| pytest tmp_path → tests | Test fixtures in pytest-managed temp dirs | Synthetic test data |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-11-01 | Tampering | hatchling build backend | accept | Upstream-recommended PEP 517 backend; same backend used elsewhere in the workspace (`model-adapter`) | closed |
| T-11-02 | Tampering | `GRAPH_WIKI_WORKSPACE` env value | mitigate | `Path(env).expanduser().resolve()` — preserved verbatim from lattice source at `packages/workspace-io/src/workspace_io/config.py:62` | closed |
| T-11-03 | Tampering | `.graph-wiki.yaml` parsing | mitigate | `yaml.safe_load(...) or {}` only (never `yaml.load`); v1-format raises `RuntimeError` instead of silent coercion (D-14) | closed |
| T-11-04 | Tampering | `manifest.write()` writing outside workspace | mitigate | `path.parent.mkdir(parents=True, exist_ok=True)` only creates dirs under the caller-supplied manifest path; no traversal because caller controls the path | closed |
| T-11-05 | Information Disclosure | Asset template (`CLAUDE.md.template`) | accept | Template ships inside the wheel; contains no secrets; identical risk profile to lattice source | closed |
| T-11-06 | Tampering | Test fixture files in `tmp_path` | accept | Tests are hermetic; `tmp_path` is pytest-managed and isolated per test | closed |
| T-11-07 | Tampering | `vault_path` arg from MCP | mitigate | `vault_path.resolve()` normalizes the explicit path branch; behavior bit-identical to pre-port — no regression introduced by the delegation shim | closed |
| T-11-08 | Information Disclosure | Bootstrap error message (D-03 strict-raise) | accept | Error message names the bootstrap command (necessary UX); no sensitive paths leaked | closed |
| T-11-09 | Information Disclosure | MCP `Field` description text | accept | Field descriptions only name an env var (`GRAPH_WIKI_WORKSPACE`); same risk profile as the previous text — no sensitive data | closed |
| T-11-10 | Tampering | `workspace_io.init` call from CLI | mitigate | `repo_root` is `vault_path.parent` (CLI-provided) or `Path.cwd()`; `workspace_io.init` does its own `Path.resolve()` and only writes inside `repo_root/graph-wiki` | closed |
| T-11-11 | Information Disclosure | WS-10 decision body in PROJECT.md | accept | Decision text references public file names (`wiki-config.toml`, `.graph-wiki.yaml`); no secrets | closed |
| T-11-SC | Tampering | Supply-chain (pip installs) | accept | No new third-party packages introduced. `pyyaml>=6.0` was already in the workspace closure; `hatchling` was already a transitive build dep of `model-adapter`. `workspace-io` itself is a workspace member, not an external dep | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| R-11-01 | T-11-01 | hatchling is the upstream-recommended PEP 517 backend and already in-workspace via `model-adapter`; adopting it for `workspace-io` introduces no new build-time attack surface | Pat | 2026-05-18 |
| R-11-02 | T-11-05 | Asset templates (`CLAUDE.md.template`) ship inside the wheel; identical to lattice source; no secrets | Pat | 2026-05-18 |
| R-11-03 | T-11-06 | Hermetic pytest `tmp_path` isolation is the standard test-fixture pattern; no security-relevant data crosses the boundary | Pat | 2026-05-18 |
| R-11-04 | T-11-08 | Bootstrap-command name in error message is required UX (tells the user how to recover); no path leakage beyond what is already in the user's own shell | Pat | 2026-05-18 |
| R-11-05 | T-11-09 | MCP `Field` description text references only the `GRAPH_WIKI_WORKSPACE` env var name; same risk profile as the prior `LATTICE_WORKSPACE` text | Pat | 2026-05-18 |
| R-11-06 | T-11-11 | WS-10 decision body references public filenames only; published as part of `.planning/PROJECT.md` already | Pat | 2026-05-18 |
| R-11-07 | T-11-SC | No new third-party packages introduced; `pyyaml` and `hatchling` already resolved in the workspace closure prior to this phase | Pat | 2026-05-18 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-05-18 | 12 | 12 | 0 | /gsd:secure-phase (short-circuit: register_authored_at_plan_time=true, threats_open=0) |

**Audit notes:**

- All 6 PLAN.md files contain `<threat_model>` blocks authored at plan time.
- All 6 SUMMARY.md files contain `## Threat Flags` sections explicitly affirming each disposition holds in the delivered code (e.g., `T-11-02 mitigated — Path().expanduser().resolve() preserved in config.py:62`, `T-11-04 mitigated — mkdir scoped under caller-supplied path`, `T-11-07 mitigated — .resolve() preserved bit-identically in shim`).
- No new threats surfaced during execution; phase is a port + delegation refactor of code that already shipped under `lattice-wiki-core`.
- Short-circuit rule applied per workflow: `register_authored_at_plan_time: true` AND `threats_open: 0` → skip auditor spawn, mark all plan-time threats CLOSED.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-05-18
