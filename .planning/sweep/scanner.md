# Sweep: scanner (cheap-fast tier)

## Candidates

- `us.anthropic.claude-haiku-4-5-20251001-v1:0`
- `us.amazon.nova-micro-v1:0`
- `us.amazon.nova-lite-v1:0`
- `qwen.qwen3-32b-v1:0`

## Raw Scores

| model_id | quality_mean | quality_std | cost_per_run_usd | n_cases | divergence_failures | gate1 | gate2 | qualified |
|---|---|---|---|---|---|---|---|---|
| `us.anthropic.claude-haiku-4-5-20251001-v1:0` | 0.000 | 0.000 | n/a | 12 | n/a | FAIL | PASS | NO |
| `us.amazon.nova-micro-v1:0` | 0.000 | 0.000 | n/a | 12 | n/a | FAIL | PASS | NO |
| `us.amazon.nova-lite-v1:0` | 0.000 | 0.000 | n/a | 12 | n/a | FAIL | FAIL | NO |
| `qwen.qwen3-32b-v1:0` | 0.000 | 0.000 | n/a | 12 | n/a | FAIL | PASS | NO |

## Pareto frontier

- `us.anthropic.claude-haiku-4-5-20251001-v1:0` (quality=0.00, cost=N/A)
- `us.amazon.nova-micro-v1:0` (quality=0.00, cost=N/A)
- `us.amazon.nova-lite-v1:0` (quality=0.00, cost=N/A)
- `qwen.qwen3-32b-v1:0` (quality=0.00, cost=N/A)

## Recommendation

```toml
# Sweep candidates (run 2026-05-17): pareto-frontier members
#   - us.anthropic.claude-haiku-4-5-20251001-v1:0        (cost=N/A, quality=0.00)
#   - us.amazon.nova-micro-v1:0                          (cost=N/A, quality=0.00)
#   - us.amazon.nova-lite-v1:0                           (cost=N/A, quality=0.00)
#   - qwen.qwen3-32b-v1:0                                (cost=N/A, quality=0.00)
# Previous default: us.anthropic.claude-haiku-4-5-20251001-v1:0
```

## Run Metadata

- **Date:** 2026-05-17
- **Commit SHA:** `2c7bb0a`
- **Total cost:** $0.0000
- **Cases:** 48
