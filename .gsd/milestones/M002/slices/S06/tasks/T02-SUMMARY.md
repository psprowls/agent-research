---
id: T02
parent: S06
milestone: M002
key_files:
  - .gsd/REQUIREMENTS.md
  - .gsd/gsd.db
  - .brand-grep-allow
key_decisions:
  - Reaffirmed D003: no backward-compatible `graph_wiki_agent` imports or `graph-wiki-agent` executable aliases are introduced.
  - Reaffirmed D004/R012: `graph-wiki-agent` remains the plugin identity/provenance string in vault manifests even though package/distribution/import namespaces changed.
duration: 
verification_result: passed
completed_at: 2026-05-31T18:16:20.318Z
blocker_discovered: false
---

# T02: Closed R009/R012/R013 requirement coverage gaps and re-ran the focused package-split validation suite.

**Closed R009/R012/R013 requirement coverage gaps and re-ran the focused package-split validation suite.**

## What Happened

Updated the GSD requirement records for R009, R012, and R013 with explicit validation/proof text. R009 remains deferred with proof that public PyPI metadata polish is intentionally deferred while the three split package pyprojects remain minimal until a public release is planned. R012 remains out-of-scope with proof citing D004 and the M002/S06/T01 bootstrap regression that preserves `graph-wiki-agent` manifest identity while reading version metadata from `graph-wiki-core`. R013 remains out-of-scope with proof citing the focused CLI shim, runtime-doc, package-boundary, integration-gate, brand-guard, and T01 remediation evidence showing the package rename did not redesign unrelated graph-wiki workflows. Because the `gsd_requirement_update` tool was not exposed in this harness namespace, I used the same installed GSD DB writer path (`updateRequirementInDb`) to keep `.gsd/gsd.db` and `.gsd/REQUIREMENTS.md` synchronized. During validation, `scripts/check-brand.sh` correctly flagged the new T01 bootstrap regression test as an unclassified `graph-wiki-agent` string; I added a narrow file-scoped `.brand-grep-allow` entry for that test because it is the required D004/R012 plugin-identity fixture, not executable guidance or a stale package boundary.

## Verification

Verified the rendered requirements traceability no longer leaves R009 as `unmapped` and no longer leaves R012/R013 with bare `n/a` proof. Ran the full focused closeout command chain from the task plan after the brand allowlist classification: core bootstrap/ingest tests passed, CLI Bedrock shim/runtime-doc/boundary tests passed, package split and integration gate tests passed, and the brand guard passed with zero unallowlisted hits. Final validation evidence ID: gsd_exec 53b7aa5b-d0d7-4264-9e4e-1190c5b20928. Final requirement assertion evidence ID: gsd_exec d31b13b9-a1d6-4bd5-ba4b-d4fc2666d799.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `node --input-type=module <<'NODE'
import { resolve } from 'node:path';
const basePath = process.cwd();
const dbPath = resolve(basePath, '.gsd/gsd.db');
const db = await import('file:///Users/pat/.nvm/versions/node/v24.12.0/lib/node_modules/@opengsd/gsd-pi/dist/resources/extensions/gsd/gsd-db.js');
const writer = await import('file:///Users/pat/.nvm/versions/node/v24.12.0/lib/node_modules/@opengsd/gsd-pi/dist/resources/extensions/gsd/db-writer.js');
if (!db.openDatabase(dbPath)) throw new Error(`failed to open ${dbPath}`);
// update R009/R012/R013 through updateRequirementInDb
NODE` | 0 | ✅ pass — DB-backed requirement records updated and REQUIREMENTS.md regenerated | 93ms |
| 2 | `python - <<'PY'
from pathlib import Path
text = Path('.gsd/REQUIREMENTS.md').read_text(encoding='utf-8')
trace = text[text.index('## Traceability'):]
# assert R009 proof is not unmapped and R012/R013 proofs are not n/a
PY` | 0 | ✅ pass — requirement coverage closeout assertions passed | 81ms |
| 3 | `uv run --package graph-wiki-core python -m pytest packages/graph-wiki-core/tests/unit/test_commands_bootstrap.py packages/graph-wiki-core/tests/unit/test_commands_ingest.py -q && uv run --package graph-wiki-cli python -m pytest packages/graph-wiki-cli/tests/unit/test_plugin_bedrock_shims.py packages/graph-wiki-cli/tests/unit/test_runtime_docs.py packages/graph-wiki-cli/tests/unit/test_cli_boundary.py -q && uv run python -m pytest tests/test_package_split_workspace.py tests/test_integration_gate.py -q && bash scripts/check-brand.sh` | 0 | ✅ pass — 27 core tests, 11 CLI tests, 6 boundary/integration tests, and brand guard passed | 6709ms |

## Deviations

The harness did not expose `gsd_requirement_update` directly, so requirement changes were applied via GSD's installed `updateRequirementInDb` DB writer module rather than the tool wrapper. Also added a narrow `.brand-grep-allow` entry for `packages/graph-wiki-core/tests/unit/test_commands_bootstrap.py` after the brand guard identified the intentional D004/R012 plugin-identity regression fixture.

## Known Issues

None.

## Files Created/Modified

- `.gsd/REQUIREMENTS.md`
- `.gsd/gsd.db`
- `.brand-grep-allow`
