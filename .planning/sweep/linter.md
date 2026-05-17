# Sweep: linter (mid tier)

## Candidates

- `us.anthropic.claude-haiku-4-5-20251001-v1:0`
- `us.amazon.nova-pro-v1:0`
- `us.amazon.nova-lite-v1:0`
- `qwen.qwen3-32b-v1:0`

## Raw Scores

| model_id | quality_mean | quality_std | cost_per_run_usd | n_cases | divergence_failures | gate1 | gate2 | qualified |
|---|---|---|---|---|---|---|---|---|
| `us.anthropic.claude-haiku-4-5-20251001-v1:0` | 0.000 | 0.000 | $0.0220 | 12 | n/a | FAIL | PASS | NO |
| `us.amazon.nova-pro-v1:0` | 0.000 | 0.000 | $0.0118 | 12 | n/a | FAIL | PASS | NO |
| `us.amazon.nova-lite-v1:0` | 0.000 | 0.000 | $0.0048 | 12 | n/a | FAIL | PASS | NO |
| `qwen.qwen3-32b-v1:0` | 0.000 | 0.000 | $0.0060 | 12 | n/a | FAIL | PASS | NO |

## Pareto frontier

- `us.amazon.nova-lite-v1:0` (quality=0.00, cost=$0.0046)

**Cheapest on frontier:** `us.amazon.nova-lite-v1:0`

## Recommendation

```toml
# Sweep candidates (run 2026-05-17): pareto-frontier members
#   - us.amazon.nova-lite-v1:0                           (cost=$0.0046, quality=0.00)
# Previous default: us.anthropic.claude-haiku-4-5-20251001-v1:0
```

## Run Metadata

- **Date:** 2026-05-17
- **Commit SHA:** `2c7bb0a`
- **Total cost:** $0.5350
- **Cases:** 48
