# Design: three-arm wiki-context eval for `claude-code-evals`

**Date:** 2026-06-07
**Status:** approved (brainstorm) → ready for implementation plan
**Package:** `packages/claude-code-evals` (CLI: `cc-eval`); eval plans in repo-root `eval/`

## Problem

`claude-code-evals` measures whether **Graph Wiki context improves Claude Code's
behavior** on a real codebase (the mono-repo). The harness is fixed and has a working
**no-wiki control arm** (`base.yaml`), but **no positive arm**. Before we can write one
we must decide *how the wiki reaches the agent* and *what "the wiki helped" means*.

Two findings from exploration frame the work:

1. **There is no wiki to measure against yet.** `mono-repo/.graph-wiki.local.yaml`
   points at `~/Personal/graph-wiki/mono-repo-live`, which is **empty** (zero files).
2. **A pure correctness rubric is blind to efficiency wins.** The existing
   `wiki-api-client` scenario *passed* correctness in the no-wiki arm by brute force
   (read 29 files across 80 turns, 44 tool calls before first edit) — so correctness
   alone scores the wiki's value there at zero.

## Goals

- Measure wiki value while **separating knowledge value from agentic discovery cost**.
- Make "the wiki helped" a **measured verdict**, not a judgment call.
- Prove the method end-to-end on a **tight, curated** scenario set, with a template so
  the portfolio can grow later.

## Non-goals

- Large scenario portfolios (6–8+). Deferred until the method is validated on real data.
- Parallel runset execution. Noted as an optimization; serial is fine for iteration 1.
- Migrations / backward-compat machinery (single-dev research repo; rebuild on change).
- MCP surface (`graph-wiki-mcp`) evaluation. We evaluate the **CC plugin** surface; MCP
  is a possible future arm.

---

## Decision 1 — Three arms

Three configs in `eval/configs/`, each a different way the wiki reaches the agent:

| Arm | Config | Wiki delivery | Measures |
|-----|--------|---------------|----------|
| `base` | `base.yaml` (exists) | nothing — no plugins, no injected text | control |
| `injected` | `injected.yaml` (new) | relevant wiki page(s) placed directly in context | **ceiling** — value of the knowledge if retrieval were perfect |
| `plugin` | `plugin.yaml` (new) | `plugins/graph-wiki` loaded + `GRAPH_WIKI_WORKSPACE` → frozen wiki; agent chooses to `/graph-wiki:query` | **realistic** — end-to-end incl. discovery |

**Derived signals:**
- `injected − base` = the value of the knowledge itself (ceiling).
- `plugin − base` = the value the product actually delivers today.
- `injected − plugin` = **the agentic discovery cost** (knowledge present but the agent
  didn't retrieve/use it).

**The `injected` arm doubles as a scenario-quality gate.** A scenario is only admitted
to the suite once `injected` measurably beats `base`. If injecting the relevant page
doesn't help, the scenario isn't measuring wiki value — it's broken.

### Step zero — freeze the mono-repo wiki at the baseline SHA (hard prerequisite)

All arms require a wiki that describes the **same commit** the worktrees check out
(`baseline_sha: 551f7ed8b9c0b4f51a4000302548e24284729652`). Otherwise the comparison is
unfair (wiki describing different code than the agent sees).

- Build the wiki (`gw scan` / graph build) against `~/Personal/mono-repo` **at that SHA**
  into a **frozen** workspace dir, e.g. `~/Personal/graph-wiki/mono-repo-eval-551f7ed8/`.
- Freeze it (snapshot/commit) so re-runs are reproducible; it must not drift like the
  `-live` workspace would.
- The empty `mono-repo-live` workspace is **not** used.
- This step is operational (a runbook), not code — but it must be written down to be
  reproducible. See "Artifacts" below.

---

## Decision 2 — Per-scenario discriminator type

Each `scenario.yaml` declares a `discriminator` block; the report judges "wiki helped"
against the declared type.

| Type | "Wiki helped" verdict | Seed scenario |
|------|----------------------|---------------|
| `correctness-gated` | `base` **fails** rubric, wiki arm **passes** | `wiki-design-tokens` |
| `efficiency-gated` | both **pass**, wiki arm cuts a declared metric past a threshold | `wiki-api-client` |
| `impossible-without-wiki` | `base` **cannot** pass — knowledge exists *only* in the wiki (a decision/convention not derivable from reading the repo) | new (chosen after step zero) |

Efficiency thresholds are declared in the scenario so they are not arbitrary per-report:

```yaml
discriminator:
  type: efficiency-gated
  metric: files_read_count      # or turn_count / output_tokens / tool_calls_before_first_edit
  min_improvement_pct: 40       # wiki arm must read >=40% fewer files than base
```

For `correctness-gated` and `impossible-without-wiki`, the `discriminator` block carries
only `type:` (the rubric pass/fail is the verdict input). All candidate efficiency
metrics are **already recorded** by `metrics.py` — no new instrumentation needed.

---

## Decision 3 — Tight portfolio (one per type) + template

1. **`wiki-design-tokens`** — keep; classify `correctness-gated`. Proven discriminator
   (base used `text-white` / delegated to shared `Badge`; rubric 0.2).
2. **`wiki-api-client`** — keep; **reclassify** `efficiency-gated`. Weak correctness
   discriminator (base brute-forced the right answer) but a strong efficiency one —
   exactly the case the `efficiency-gated` type exists for. Set `metric` +
   `min_improvement_pct` from the recorded base run (29 files / 80 turns as the baseline
   to beat).
3. **One new `impossible-without-wiki` scenario** — the highest-value kind. Requires
   knowledge living **only** in the wiki: a tribal decision / deprecation / "we do X not
   Y because Z" that the code itself does not disambiguate (ideally the repo shows *both*
   competing patterns, so reading code cannot pick the sanctioned one). The concrete
   scenario is chosen **after** step zero, grounded in what the frozen wiki actually
   contains (ADR/concept pages), rather than guessed up front.
4. **`eval/scenarios/TEMPLATE/`** — skeleton `scenario.yaml` + `prompt.md` + `rubric.md`
   + `verify.sh` + `preflight.sh`, including the `discriminator` block and authoring
   notes, so the portfolio grows cheaply.

A full sweep is then 3–4 scenarios × 3 arms ≈ 9–12 runs.

---

## Decision 4 — Reporting: arm-comparison diff view

`report.py` currently renders row-per-`(scenario, config)`. Add a **scenario × arm
matrix** with a computed verdict:

```
scenario            base       injected    plugin     verdict
wiki-design-tokens  x 0.2      v 1.0       v 0.8      WIKI HELPED (correctness)
wiki-api-client     v 29f/80t  v 8f/22t    v 11f/31t  WIKI HELPED (efficiency -62% files)
<impossible-one>    x 0.0      v 1.0       x 0.4      CEILING v / PLUGIN MISS (no query)
```

- The verdict is computed from each scenario's `discriminator` type against the three
  arms' metrics.
- The `injected − plugin` gap is surfaced explicitly (agentic discovery cost).
- JSON output carries the same matrix for programmatic diffing across sweeps.

---

## Decision 5 — Operations

- **OAuth token for unattended runs.** `CLAUDE_CODE_OAUTH_TOKEN` currently lives in
  `~/.zshrc` (interactive shells only); batch/cron non-interactive shells won't see it.
  **Decision:** the orchestrator loads it from a **git-ignored file** (e.g.
  `eval/.secrets` or `~/.config/cc-eval/token`) rather than relying on shell env. This
  scopes the subscription token to the harness and avoids `~/.zshenv` (which would leak
  it into *every* non-interactive process). Existing env var remains a fallback.
- **Cost/time.** ~5 min + subscription tokens per run; a full sweep ≈ 9–12 runs ≈ 45–60
  min wall serial. Runs are independent → a bounded-concurrency runset is a future
  optimization, not built in iteration 1.

---

## Code changes (scoped)

1. **`schemas.py`**
   - `Scenario`: add a `discriminator` block (`type` + optional `metric`,
     `min_improvement_pct`).
   - Injected context: add a **per-scenario** `inject:` list of wiki page paths (which
     page is relevant is scenario-specific, so it belongs on the scenario, not the
     config). Paths resolve relative to the frozen wiki workspace's `wiki/` dir (e.g.
     `entities/...md`, `adrs/...md`). The `injected` arm consumes it; other arms ignore it.
2. **`runner.py` / `orchestrator.py`**
   - `injected` arm: prepend the resolved wiki page text to context via
     `--append-system-prompt` concatenation (guarantees in-context — the clean ceiling).
   - `plugin` arm: add the frozen wiki dir to `--add-dir` and set
     `GRAPH_WIKI_WORKSPACE` in the subprocess env (because `.graph-wiki.local.yaml` is
     **not committed at the pinned SHA**, the worktree cannot self-resolve the workspace).
   - Token loading: read the git-ignored secrets file if env var is unset.
3. **`report.py` + `templates/report.md.j2`** — scenario × arm matrix + verdict column;
   matching JSON.
4. **`eval/`** — `configs/injected.yaml`, `configs/plugin.yaml`; reclassify the two
   existing scenarios (`discriminator` blocks); add the new `impossible-without-wiki`
   scenario; add `scenarios/TEMPLATE/`.
5. **Runbook doc** — "freeze the mono-repo wiki at the baseline SHA" (step zero),
   reproducible.

## Artifacts produced

- Frozen wiki workspace at `~/Personal/graph-wiki/mono-repo-eval-551f7ed8/`.
- `eval/configs/{injected,plugin}.yaml`.
- Updated `eval/scenarios/{wiki-design-tokens,wiki-api-client}/scenario.yaml`.
- New `eval/scenarios/<impossible-without-wiki-name>/`.
- `eval/scenarios/TEMPLATE/`.
- Runbook for freezing the wiki.
- A runset that runs the curated scenarios × three arms and emits the matrix report.

## Success criteria for the spec's implementation

- `cc-eval` runs a full three-arm sweep over the curated scenarios and emits the
  arm-comparison matrix with a computed per-scenario verdict.
- Each scenario's `injected` arm beats `base` (scenario-quality gate passes).
- At least one scenario of each discriminator type is present and produces a clean
  verdict.
- Existing test suite stays green; new behavior (discriminator parsing, verdict
  computation, injected/plugin wiring) is covered by tests.

## Open items deferred (not blocking)

- Concrete `impossible-without-wiki` scenario content — chosen after step zero.
- Runset parallelism.
- MCP-surface arm.
- Whether to push `develop` / branch strategy (operational, decided at implementation).
