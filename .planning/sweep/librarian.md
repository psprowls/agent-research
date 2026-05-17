# Sweep: librarian (quality tier)

## Candidates

- `us.anthropic.claude-sonnet-4-6`
- `us.anthropic.claude-haiku-4-5-20251001-v1:0`
- `us.amazon.nova-pro-v1:0`
- `qwen.qwen3-32b-v1:0`

## Raw Scores

| model_id | quality_mean | quality_std | cost_per_run_usd | n_cases | divergence_failures | gate1 | gate2 | qualified |
|---|---|---|---|---|---|---|---|---|
| `us.anthropic.claude-sonnet-4-6` | 1.000 | 0.000 | $0.1197 | 12 | n/a | FAIL | PASS | NO |
| `us.anthropic.claude-haiku-4-5-20251001-v1:0` | 1.000 | 0.000 | $0.0237 | 12 | n/a | FAIL | PASS | NO |
| `us.amazon.nova-pro-v1:0` | 0.833 | 0.373 | $0.0176 | 12 | n/a | FAIL | PASS | NO |
| `qwen.qwen3-32b-v1:0` | 0.917 | 0.276 | $0.0074 | 12 | n/a | FAIL | PASS | NO |

## Pareto frontier

- `us.anthropic.claude-haiku-4-5-20251001-v1:0` (quality=1.00, cost=$0.0204)
- `qwen.qwen3-32b-v1:0` (quality=0.00, cost=$0.0095)

**Cheapest on frontier:** `qwen.qwen3-32b-v1:0`

## Recommendation

```toml
# Sweep candidates (run 2026-05-17): pareto-frontier members
#   - us.anthropic.claude-haiku-4-5-20251001-v1:0        (cost=$0.0204, quality=1.00)
#   - qwen.qwen3-32b-v1:0                                (cost=$0.0095, quality=0.00)
# Previous default: us.anthropic.claude-sonnet-4-6
```

## Run Metadata

- **Date:** 2026-05-17
- **Commit SHA:** `2c7bb0a`
- **Total cost:** $2.0210
- **Cases:** 48
