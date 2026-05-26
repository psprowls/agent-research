# Phase 33: CLI Surface - Context

**Gathered:** 2026-05-25
**Status:** Ready for planning

<domain>
## Phase Boundary

After Phase 33, the `cg` CLI exposes the full v1.6 graph surface via 13 new subcommands + 1 extension. All new subcommands follow the existing pattern in `packages/graph-io/src/graph_io/cli/`: one Python module per subcommand with `add_arguments(parser: argparse.ArgumentParser) -> None` and `run(args: argparse.Namespace) -> int`, registered in `_SUBCOMMANDS` dict in `main.py`. Each subcommand opens a read-only DB connection via `store.read_only_connect`, dispatches to a Phase 32 query helper, and renders output in `--fmt human` (default) or `--fmt json`. The pre-existing 13 subcommands continue working unchanged (SC#5 anti-regression).

**New subcommands (mapping to CLI-* requirements + Phase 32 helpers):**

| Subcommand                              | Req      | Phase 32 helper                  |
|-----------------------------------------|----------|----------------------------------|
| `cg describe-repo`                      | CLI-01   | `describe_repository`            |
| `cg list-packages`                      | CLI-02   | `list_packages`                  |
| `cg list-entry-points <pkg> [--kind X]` | CLI-03   | `entry_points_for_package`       |
| `cg list-scripts`                       | CLI-04   | `list_scripts`                   |
| `cg list-suites`                        | CLI-05   | `list_test_suites`               |
| `cg describe-suite <name>`              | CLI-06   | `describe_test_suite`            |
| `cg what-tests <name> [--kind X]`       | CLI-07/8 | `tests_for_package` OR `tests_for_domain` (probe + dispatch) |
| `cg list-domains`                       | CLI-09   | `list_domains`                   |
| `cg describe-domain <name>`             | CLI-10   | `describe_domain`                |
| `cg domain-refs <name>`                 | CLI-11   | `domain_references`              |
| `cg domain-deps <name>`                 | CLI-12   | `domain_depends_on`              |
| `cg cross-cutting`                      | CLI-13   | `cross_cutting_packages`         |
| **Extended `cg status`**                | CLI-14   | `describe_repository` (URI only) |

Phase 33 does NOT ship `list-repositories` even though Phase 32 has it — there's exactly one Repository per DB per Phase 29 D-01, so `describe-repo` covers the surface. Phase 32's `list_repositories` helper sits unused at the CLI layer (could be wired in v1.7 if multi-repo support lands).

**Strictly NOT in this phase:**
- Brand sweep (`lattice` → `graph-wiki`) → Phase 34
- New Phase 32 query helpers (CLI is read-only over what Phase 32 already exposes)
- Anti-regression SC#5 covers the 7 listed subcommands; Phase 33 does NOT regress the other 6 (`callees`, `imports`, `imported-by`, `exports`, `exported-by`, `dump`, `sync-wiki`) — they're not mentioned in SC#5 but still must work
- Performance/perf tuning of the CLI dispatch
- `--fmt yaml` or other output formats beyond human + json
- Multi-repo support, cross-DB queries

Requirements addressed: CLI-01 through CLI-14.

</domain>

<decisions>
## Implementation Decisions

### `cg what-tests <name>` dispatch (CLI-07 + CLI-08 share name)

- **D-01:** **Probe-both + error on ambiguity**:
  - Look up `<name>` first as a Package node; if found, dispatch to `queries.tests_for_package(conn, name)`.
  - If not found as Package, look up as Domain node; if found, dispatch to `queries.tests_for_domain(conn, name)`.
  - If BOTH exist (same name used for a Package AND a Domain — rare but possible): exit `EXIT_AMBIGUOUS=2` (new constant in `exit_codes`) with stderr message: `"error: ambiguous: '<name>' is both a Package and a Domain. Use --kind package or --kind domain."`.
  - If NEITHER exists: exit `exit_codes.GENERIC` (existing) with stderr message: `"error: no Package or Domain named '<name>'"`.

- **D-02:** **Optional `--kind {package,domain}` flag** on `cg what-tests`:
  - When `--kind` is provided, skip the probe and dispatch directly. This both short-circuits the ambiguity check and gives scripts a clear contract.
  - Without `--kind`, the probe path (D-01) runs.
  - argparse: `parser.add_argument("--kind", choices=("package", "domain"), default=None)`.

### Empty-state messaging (SC#2 generalised across the CLI)

- **D-03:** **Uniform empty-state convention across all list-* and describe-* subcommands**:

  **`--fmt human`, empty result:**
  - stdout: empty (no output)
  - stderr: one-line informational message describing why the result is empty
  - exit: 0 (per SC#2 — graceful degradation)
  - Wording per subcommand (`No domains configured (domains.yaml missing).` / `No TestSuites in graph.` / `Package '<name>' has no declared entry points.` etc.). Planner picks per-command wording with the same shape: `"No <thing>: <reason>"` or `"No <thing> in graph."`

  **`--fmt json`, empty result:**
  - stdout: empty payload appropriate to the shape — `[]` for list-*, `null` for describe-* targets that don't exist, `{}` for describe-* of an existing-but-empty resource (e.g. a Package with no entry points → `{"name": "...", "entry_points": [], ...}` from describe_package).
  - stderr: NO message (JSON consumers don't expect mixed streams; the empty payload IS the signal)
  - exit: 0

- **D-04:** **describe-\* with MISSING target** (e.g. `cg describe-domain nonexistent`):
  - Exit: `exit_codes.GENERIC` (non-zero)
  - stderr: `"error: not found: <name>"` (matches existing `q_describe_package.py` pattern)
  - stdout: empty (both `--fmt human` and `--fmt json`)
  - Distinguishes "user typed a wrong name" (exit 1) from "the resource exists but is empty" (exit 0 per D-03).
  - This convention is **already used by `q_describe_package.py`** (line ~33: `print(f"error: package not found: {args.name}"); return exit_codes.GENERIC`). Phase 33 extends to all new describe-\* subcommands uniformly.

### `cg list-scripts` annotation (CLI-04)

- **D-05:** **Annotated lines, dedup by file path**:
  ```
  packages/billing-service/src/billing/cli.py  [declared: billing-service=billing.cli:main]
  packages/scripts/migrate.py                  [conventional]
  packages/utils/run.py                        [declared: utils-run=utils:main, conventional]
  ```
  - Each distinct file path appears once. Annotations to the right indicate the signal source(s).
  - `[declared: <pkg>=<callable>]` for files that are an `implemented_by` target of an `EntryPoint(kind=executable)`. If multiple EntryPoints implement the same file, list them comma-separated inside the bracket.
  - `[conventional]` for files where `File.is_executable=true` (no EntryPoint).
  - Files matching BOTH carry both annotations: `[declared: ..., conventional]`.
  - Columns are aligned via tab-stop or simple ` ` padding (planner picks; readable + grep-friendly).

- **D-06:** **Sort alphabetically by file path**. Predictable, grep-friendly, stable across runs. Matches existing CLI convention.

- **D-07:** **`--fmt json` for list-scripts**: each entry is an object with `path`, `declared: list[{package, callable}]` (empty list if not declared), `conventional: bool`. Dedup at the file-path level same as human. Example:
  ```json
  [
    {"path": "packages/billing-service/src/billing/cli.py",
     "declared": [{"package": "billing-service", "callable": "billing.cli:main"}],
     "conventional": false},
    {"path": "packages/scripts/migrate.py",
     "declared": [],
     "conventional": true}
  ]
  ```

### Output verbosity conventions

- **D-08:** **`list-*` commands in `--fmt human`**: one name per line, no header, no annotation columns (except `list-scripts` per D-05 and `list-entry-points` per D-09). Sort alphabetically.
  ```
  $ cg list-domains
  auth
  billing
  payments
  ```

- **D-09:** **`cg list-entry-points <pkg>`** with optional `--kind {executable,library}`:
  - Default (no filter): print all entry points. Format: `<entry-name>  [<kind>]  -> <implemented_by_path>` (with NULL implemented_by shown as `(unresolved)`).
  - With `--kind`: filter to only entries of that kind, print just `<entry-name>` per line (no annotation).
  - argparse: `parser.add_argument("--kind", choices=("executable", "library"), default=None)`.
  - Sort alphabetically.

- **D-10:** **`describe-*` commands in `--fmt human`**: compact key-value lines, matching the existing `q_describe_package.py` pattern. Example:
  ```
  $ cg describe-repo
  repository:     agent-research
  uri:            repo:psprowls/agent-research
  url:            git@github.com:psprowls/agent-research.git
  default_branch: main
  package_count:  12
  ```
  Field names lowercase, colon-separated, padded to roughly the longest field name. Match q_describe_package.py styling so existing users feel at home.

- **D-11:** **`cg describe-domain` extended format** — describe-domain has more nested data (packages list, subdomain list). Use compact key-value PLUS bullet-list sub-blocks:
  ```
  $ cg describe-domain billing
  domain:        billing
  uri:           domain:psprowls/agent-research/billing
  parent:        financial
  description:   Invoice generation and dunning
  packages:
    - billing-service
    - billing-models
  subdomains:
    (none)
  ```
  `(none)` marker for empty sub-blocks (NOT empty stderr message — describe-* of an EXISTING target with empty sub-fields is not the SC#2 graceful-degradation case).

- **D-12:** **`cg cross-cutting`** output: `<name>  score=<N>` columns. Sorted by score descending, ties alphabetical.
  ```
  $ cg cross-cutting
  logging        score=47
  shared-utils   score=23
  telemetry      score=18
  ```
  Score is Phase 32 D-11's sum of usage_count. `--fmt json` returns `[{"name": "...", "score": 47, "package": {...PackageDescription...}}, ...]` (the full PackageDescription nested inside, matching Phase 32 D-12 return type).

- **D-13:** **`cg domain-refs <domain>`** output: three columns `package | usage | domains`:
  ```
  $ cg domain-refs billing
  package         usage  domains
  shared-utils    12     3
  logging         8      2
  ```
  Phase 32 D-08 returns rows with `total_usage_count` + `distinct_domain_count` — both visible in human output. JSON returns the dataclass shape with both metrics + the bubbled-up source domains for verbosity.

- **D-14:** **`cg domain-deps <domain>`** output: two columns `domain | usage`:
  ```
  $ cg domain-deps billing
  domain    usage
  auth      5
  payments  3
  ```
  Phase 32 D-08's `total_usage_count` is the single metric. JSON: `[{"domain": "...", "total_usage_count": 5}, ...]`.

- **D-15:** **`cg status` extension (CLI-14)**:
  - Prepend a single line to the existing `cg status` output: `repository: <uri>`.
  - Existing lines (DB-freshness, file counts, etc.) print unchanged AFTER the new line.
  - JSON shape: add a top-level `"repository"` field with the URI string; existing JSON fields unchanged.
  - Anti-regression: any script that parses the LAST line(s) of `cg status` output still works; scripts parsing the first line break (acceptable — `cg status`'s parse contract has never been documented).

### Anti-regression smoke test (SC#5)

- **D-16:** **SC#5 smoke test** lives in `packages/graph-io/tests/test_cli_anti_regression.py`:
  - For each of the 7 SC#5-listed pre-existing subcommands (`update`, `find`, `status`, `describe-package`, `describe-path`, `callers`, `callees`), assert `cg <cmd> [reasonable-args]` exits 0 against the same fixture (`tests/fixtures/sample_monorepo/` post-Phase-31 with domains.yaml). Each subcommand's "reasonable args" is hand-picked (e.g. `describe-package graph-io`, `find --kind file --name update.py`).
  - The test runs once after Phase 33 ships and provides the strongest signal that Phase 33's CLI registration didn't break the existing subcommand parsing or argparse dispatch.
  - SC#5 explicitly lists 7 subcommands; the OTHER pre-existing 6 (`callees` is in SC#5, but `imports`, `imported-by`, `exports`, `exported-by`, `dump`, `sync-wiki` are not) get coverage as a bonus assertion at the END of the same test file — same shape, lower priority (could relax if any is genuinely undocumented).

### CLI module organisation

- **D-17:** **Module naming convention** for new subcommands (consistent with existing `q_*`/`ops_*` split):
  - `q_describe_repo.py`, `q_list_packages.py`, `q_list_entry_points.py`, `q_list_scripts.py`, `q_list_suites.py`, `q_describe_suite.py`, `q_what_tests.py`, `q_list_domains.py`, `q_describe_domain.py`, `q_domain_refs.py`, `q_domain_deps.py`, `q_cross_cutting.py`. All are queries → `q_*` prefix.
  - `ops_status.py` is extended in place (D-15) — not renamed.
  - All 12 new `q_*` modules import from `graph_io.queries` (Phase 32 helpers), `graph_io.exit_codes`, `graph_io.store`, `workspace_io.paths.graph_dir`. The pattern from `q_describe_package.py` (open conn, call helper, render, close) is the template.

- **D-18:** **Registration in `main.py`** — add 12 new entries to `_SUBCOMMANDS` dict:
  ```python
  _SUBCOMMANDS = {
      # ... existing 13 ...
      "describe-repo": q_describe_repo,
      "list-packages": q_list_packages,
      "list-entry-points": q_list_entry_points,
      "list-scripts": q_list_scripts,
      "list-suites": q_list_suites,
      "describe-suite": q_describe_suite,
      "what-tests": q_what_tests,
      "list-domains": q_list_domains,
      "describe-domain": q_describe_domain,
      "domain-refs": q_domain_refs,
      "domain-deps": q_domain_deps,
      "cross-cutting": q_cross_cutting,
  }
  ```
  `cg --help` will list these automatically via argparse subparsers (SC's "cg --help lists them" requirement satisfied by registration).

### `cg --help` ordering and grouping

- **D-19:** **No special grouping in `cg --help`** in v1.6 — argparse renders the subcommand list in `_SUBCOMMANDS` dict insertion order. Group conceptually-related commands by listing them together in the dict definition (per D-18: ops first, then existing queries, then new queries grouped by feature: repo, package-related, scripts, suites, tests, domain queries, cross-cutting). User skimming `cg --help` sees a sensible order without argparse subgroups. v1.7 could add explicit groups if needed.

### Exit codes

- **D-20:** **New exit code**: `exit_codes.AMBIGUOUS = 2` for D-01 ambiguous `cg what-tests` lookup. Add to `packages/graph-io/src/graph_io/exit_codes.py`. Other Phase 33 subcommands reuse existing codes (`SUCCESS=0`, `GENERIC=1`, `NOT_INITIALIZED`, `SCHEMA_MISMATCH`).

### Claude's Discretion

- Exact stderr wording per empty-state command (D-03) — planner picks human-readable variants of `"No <thing>: <reason>"`.
- Column padding strategy (fixed width, tab-stop, longest-key-aligned) — planner picks readable + grep-friendly approach.
- Whether `list-entry-points` requires `<pkg>` arg or accepts no-arg form (across all packages) — CLI-03 spec says `<pkg> [--kind ...]` so arg is required; planner can add an optional `--package` flag for completeness if useful but the required positional is canonical.
- Internal `_resolve_node` helper for D-01 probe-both — planner picks shape (function vs inline).
- Whether `cg describe-suite <name>` accepts `<name>` as suite-name OR suite-URI — recommend suite-name (matches all other describe-* commands using name).
- argparse help strings per subcommand — planner writes short, action-oriented help.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Source-of-truth ontology spec
- `.planning/research/ONTOLOGY-SPEC.md` §11 (Sample queries — each `cg` subcommand corresponds to a sample query)

### Phase 32 prior context (the helpers Phase 33 wires)
- `.planning/phases/32-query-layer-extensions/32-CONTEXT.md` — D-01 (PackageDescription with new fields), D-02 (Description dataclass shapes), D-04 (list_* returns list[NodeRecord]), D-05 (PathDescription.role_flags), D-06 (which helpers bubble), D-08 (usage_count + distinct_domain_count exposed), D-09 (tests_for_domain UNION), D-11 (cross_cutting_packages ranking by SUM(usage_count) — divergence from spec §11.4)

### Phase 31 prior context
- `.planning/phases/31-domain-layer-derived-edges/31-CONTEXT.md` — D-01 (domains.yaml schema; describe-domain renders these fields), D-15 (cycle warning output format precedent — Phase 33 stderr messages follow similar style), D-17 (delete-all-then-recompute; CLI just reads), D-18 (usage_count in attrs_json)

### Phase 30 prior context
- `.planning/phases/30-entry-points-test-suites/30-CONTEXT.md` — D-08 (EntryPoint source values; CLI describe-suite renders these), D-12 (TestSuite→Repository edges at K=5; tests_for_package needs to handle this), D-17 (TestSuite.kind heuristics; describe-suite renders this)

### Phase 29 prior context
- `.planning/phases/29-structural-nodes-containment-tree/29-CONTEXT.md` — D-09 amended by Phase 30 D-01 (role flags; relevant for `cg describe-path` if PathDescription.role_flags wired by Phase 32 D-05)

### Requirements + roadmap
- `.planning/REQUIREMENTS.md` — CLI-01..14 (lines 81–94); pending-phase mapping lines 223–236
- `.planning/ROADMAP.md` — Phase 33 block + SC#1–5

### Existing CLI code (read before extending)
- `packages/graph-io/src/graph_io/cli/main.py` — `_build_parser` + `_SUBCOMMANDS` dict; D-18 adds 12 entries here
- `packages/graph-io/src/graph_io/cli/q_describe_package.py` — **canonical template** for new `q_*` modules. Existing pattern: `add_arguments(parser)` + `run(args) -> int`, opens read-only conn, calls Phase 32 helper, renders via `--fmt`, returns exit code.
- `packages/graph-io/src/graph_io/cli/q_find.py` — for the `--kind` filter pattern (Phase 33 D-09 list-entry-points reuses this)
- `packages/graph-io/src/graph_io/cli/ops_status.py` — extended in place by D-15
- `packages/graph-io/src/graph_io/cli/_format.py` — shared formatting helpers (if any); planner reuses + extends
- `packages/graph-io/src/graph_io/exit_codes.py` — D-20 adds `AMBIGUOUS=2`

### Existing test patterns
- `packages/graph-io/tests/test_cli.py` (if exists) or new — D-16 anti-regression smoke test lives in a dedicated `test_cli_anti_regression.py` to keep failure attribution clear

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`q_describe_package.py` as template** — every new `q_*` module follows its shape: argparse arg → read-only conn → Phase 32 helper → human/json render → close conn → return exit code.
- **`q_find.py` `--kind` filter pattern** — D-09 `list-entry-points --kind {executable,library}` reuses this. Phase 32 D-19 extends `find` with new kinds; D-09 here is a separate filter dimension on a different helper.
- **`store.read_only_connect`** — every new subcommand uses this. Same exception handling (NotInitialized, SchemaMismatch → distinct exit codes).
- **`workspace_io.paths.graph_dir`** — already imported by existing q_* modules; same pattern.
- **`exit_codes`** module — extended by D-20 (new `AMBIGUOUS=2`); existing codes (SUCCESS, GENERIC, NOT_INITIALIZED, SCHEMA_MISMATCH) cover most paths.
- **Phase 32 dataclasses + dataclasses.asdict()** — JSON rendering is one-line (`print(json.dumps(asdict(desc), default=str))`).

### Established Patterns
- **argparse subparsers with `set_defaults(_module=mod)`** — `main.py:67-68` dispatches via the per-subcommand module's `run(args)`.
- **`--fmt human | json` flag at the top-level parser** — propagated to `args.fmt` in every subcommand.
- **Read-only DB connection per command** — open, dispatch, close. No connection caching.
- **Human format: compact key-value lines** for describe-*; one-per-line for list-*.
- **JSON format: full dataclass via asdict()** — supports `default=str` for datetimes and Path objects.
- **stderr for human informational/error output, stdout for data** — applies to D-03/D-04 empty-state and not-found handling.

### Integration Points
- **Phase 32 → Phase 33 is the primary seam** — every Phase 33 subcommand binds 1:1 to one Phase 32 helper. If Phase 32 helper changes signature, Phase 33 module updates.
- **Phase 34 brand sweep depends on Phase 33's `cg --help` text** — SC#5 of Phase 34 says `cg --help` must contain "graph-wiki", not "lattice". Phase 33's `cg`'s `description` string (`packages/graph-io/src/graph_io/cli/main.py:45`: "lattice code graph CLI") gets touched in Phase 34; Phase 33 leaves it alone.
- **SC#5 anti-regression covers `cg callers` and `cg callees` and `cg find`** — these existing subcommands could break if `_SUBCOMMANDS` dict mutation or argparse subparser registration accidentally shadows their names. The anti-regression test (D-16) catches this.

</code_context>

<specifics>
## Specific Ideas

- D-05 list-scripts output prototype:
  ```
  $ cg list-scripts
  packages/billing-service/src/billing/cli.py    [declared: billing-cli=billing.cli:main]
  packages/scripts/migrate.py                    [conventional]
  packages/utils/run.py                          [declared: utils-run=utils:main, conventional]
  ```

- D-10 describe-repo prototype (matches `q_describe_package.py` styling):
  ```
  $ cg describe-repo
  repository:     agent-research
  uri:            repo:psprowls/agent-research
  url:            git@github.com:psprowls/agent-research.git
  default_branch: main
  package_count:  12
  ```

- D-11 describe-domain prototype:
  ```
  $ cg describe-domain billing
  domain:        billing
  uri:           domain:psprowls/agent-research/billing
  parent:        financial
  description:   Invoice generation and dunning
  packages:
    - billing-service
    - billing-models
  subdomains:
    - billing-events
    - billing-reports
  ```

- D-12 cross-cutting prototype (Phase 32 D-11 deliberate divergence — score is sum of usage_count, NOT distinct-domain count):
  ```
  $ cg cross-cutting
  logging        score=47
  shared-utils   score=23
  telemetry      score=18
  ```

- D-15 cg status extension prototype:
  ```
  $ cg status
  repository:    repo:psprowls/agent-research
  database:      /Users/pat/.graph-wiki/agent-research/code.db
  last_update:   2026-05-25T14:30:12Z
  files_stale:   3
  ```
  (existing fields after the new top line)

- D-01 ambiguity message:
  ```
  $ cg what-tests billing
  error: ambiguous: 'billing' is both a Package and a Domain. Use --kind package or --kind domain.
  $ echo $?
  2
  ```

- D-03 empty-state message variants per command:
  - `cg list-domains` (no domains.yaml): `"No domains configured (domains.yaml missing)."`
  - `cg list-suites` (no test files): `"No TestSuites in graph."`
  - `cg list-entry-points <pkg>` (package exists, no entries): `"Package '<pkg>' declares no entry points."`
  - `cg list-scripts` (no scripts): `"No declared or conventional scripts in graph."`
  - `cg cross-cutting` (no cross-cutting packages): `"No zero-domain packages in graph."`
  - `cg domain-refs <domain>` (domain exists, no refs): `"Domain '<domain>' has no incoming references."`
  - `cg domain-deps <domain>` (domain exists, no deps): `"Domain '<domain>' has no outgoing dependencies."`
  - `cg what-tests <name>` (resolved but no suites): `"No TestSuites cover <kind> '<name>'."`

- D-16 anti-regression smoke test sketch:
  ```python
  @pytest.fixture(scope="module")
  def post_phase33_fixture(tmp_path_factory):
      repo_dir = tmp_path_factory.mktemp("anti_regression") / "repo"
      shutil.copytree("tests/fixtures/sample_monorepo", repo_dir)
      _run_cli(["cg", "update", "--full"], cwd=repo_dir)
      return repo_dir

  @pytest.mark.parametrize("cmd_args", [
      ["update", "--full"],
      ["find", "--kind", "file", "--name", "update.py"],
      ["status"],
      ["describe-package", "graph-io"],
      ["describe-path", "packages/graph-io/src/graph_io/update.py"],
      ["callers", "graph_io.update.run"],
      ["callees", "graph_io.update.run"],
  ])
  def test_pre_existing_subcommand_exits_zero(post_phase33_fixture, cmd_args):
      result = _run_cli(["cg", *cmd_args], cwd=post_phase33_fixture)
      assert result.returncode == 0, f"cg {' '.join(cmd_args)} regressed: {result.stderr}"
  ```

</specifics>

<deferred>
## Deferred Ideas

- **`cg list-repositories` subcommand** — Phase 32 ships the helper but Phase 33 omits the CLI binding (single-repo per DB in v1.6). Add in v1.7 if multi-repo support lands.
- **`--fmt yaml` output mode** — only human + json in v1.6.
- **argparse subgroup help formatting** (`cg --help` with sections like "Repository:", "Domain:", "Tests:") — D-19 defers; v1.7 if it gets unwieldy.
- **Shell completion** (zsh/bash/fish completion files) — out of scope; could be a workshop project.
- **`cg what-uses <package>`** — could be a useful inverse of `cg domain-refs`; not in CLI-01..14 scope.
- **Pagination / `--limit` flag** for list-* commands on large repos — defer until measured.
- **Output coloring / formatting** (ANSI colors for stderr, bold for headers) — out of scope; CLI is plain text.
- **JSON streaming output** for very large result sets — defer.
- **`cg find` extension with `--domain <name>`** filter — natural pairing with new Domain nodes; CLI-01..14 doesn't ask for it; defer to v1.7.
- **`cg describe-entry-point <pkg> <name>`** — Phase 32 ships the helper; Phase 33 doesn't bind it (callable from describe-package output). v1.7 if a user needs it.

</deferred>

---

*Phase: 33-cli-surface*
*Context gathered: 2026-05-25*
