# Eval Harness

Automated evaluation harness for `graph-wiki-agent`. Compares query quality across
Bedrock model alternatives against a recorded lattice-wiki baseline.

---

## Directory Layout

```
eval/
  cases/
    query_cases.json       # Eval case definitions (case_id, query, expected_answer)
  baselines/
    <case_id>.json         # One file per case — written by baseline recording
  README.md                # This file
```

---

## Recording a Baseline

The baseline is the reference point for regression detection. It captures the
current lattice-wiki query output (via `claude -p`) for each eval case as a
reproducible oracle.

### Prerequisites

1. **`claude` CLI installed and on PATH** — the lattice-wiki plugin runs inside it.
   Verify: `claude --version`

2. **lattice-wiki plugin path configured** — either set via the `--plugin-dir` flag
   (recommended for explicit control) or via the `LATTICE_WIKI_PLUGIN_DIR` environment
   variable if your wrapper script exports it.

3. **AWS credentials configured** — Bedrock access is required for the full eval sweep
   (Plans 02-03), but baseline recording uses the claude CLI which uses its own auth.

4. **Vault path available** — point `--vault` at a local checkout of the vault you want
   to eval against. The round-trip test fixture at
   `packages/vault-io/tests/fixtures/round-trip-vault/` can be used for CI.

### Command

Run a full baseline recording (records one JSON file per case in `eval/baselines/`):

```bash
GRAPH_WIKI_RUN_EVAL=1 uv run --package eval-harness python -m eval_harness.baseline \
  --cases eval/cases/query_cases.json \
  --vault <path-to-vault> \
  --out eval/baselines/
```

With an explicit plugin directory:

```bash
GRAPH_WIKI_RUN_EVAL=1 uv run --package eval-harness python -m eval_harness.baseline \
  --cases eval/cases/query_cases.json \
  --vault <path-to-vault> \
  --out eval/baselines/ \
  --plugin-dir /path/to/lattice-wiki/plugin
```

With a non-default model ARN:

```bash
GRAPH_WIKI_RUN_EVAL=1 uv run --package eval-harness python -m eval_harness.baseline \
  --cases eval/cases/query_cases.json \
  --vault <path-to-vault> \
  --out eval/baselines/ \
  --model-arn us.anthropic.claude-sonnet-4-6
```

### Expected Output

One JSON file per `case_id` in the `--out` directory:

```
eval/baselines/
  pkg-lookup-01.json
  concept-01.json
  cross-ref-01.json
  format-01.json
```

Each file contains the 8 EVAL-08 reproducibility fields:

```json
{
  "case_id": "pkg-lookup-01",
  "query": "What does lattice-wiki-core do?",
  "answer": "lattice-wiki-core provides the core wiki maintenance logic...",
  "model_arn": "us.anthropic.claude-sonnet-4-6",
  "prompt_hash": "abc123...64-char-sha256-hex...",
  "vault_content_hash": "def456...64-char-sha256-hex...",
  "timestamp_utc": "2026-05-14T12:00:00+00:00",
  "seed": null
}
```

**Note:** `seed` is always `null` in baselines. The `claude` CLI does not expose
a seed parameter, so baseline runs are not deterministically reproducible at the
token level. The `prompt_hash` and `vault_content_hash` fields together identify
the recording conditions (same prompt text + same vault content = same oracle
population).

---

## Running the Eval Sweep

The eval sweep (Plan 02) tests multiple Bedrock model alternatives against the
recorded baselines. See `packages/eval-harness/src/eval_harness/sweep.py` for details.

```bash
GRAPH_WIKI_RUN_EVAL=1 uv run --package eval-harness pytest \
  packages/eval-harness/tests/ -m eval -v
```

---

## Running Unit Tests (No Bedrock Required)

All deterministic unit tests (pricing, structural checks, command construction):

```bash
uv run --package eval-harness pytest packages/eval-harness/tests/ -m "not eval" -x -q
```
