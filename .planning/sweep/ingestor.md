# Sweep: ingestor (mid tier)

## Candidates

- `us.anthropic.claude-haiku-4-5-20251001-v1:0`
- `us.amazon.nova-pro-v1:0`
- `us.amazon.nova-lite-v1:0`
- `qwen.qwen3-32b-v1:0`

## Raw Scores

| model_id | quality_mean | quality_std | cost_per_run_usd | n_cases | divergence_failures | gate1 | gate2 | qualified |
|---|---|---|---|---|---|---|---|---|
| `us.anthropic.claude-haiku-4-5-20251001-v1:0` | 0.000 | 0.000 | $0.0050 | 3 | n/a | FAIL | PASS | NO |
| `us.amazon.nova-pro-v1:0` | 0.000 | 0.000 | $0.0031 | 3 | n/a | FAIL | PASS | NO |
| `us.amazon.nova-lite-v1:0` | 0.000 | 0.000 | $0.0013 | 3 | n/a | FAIL | PASS | NO |
| `qwen.qwen3-32b-v1:0` | 0.000 | 0.000 | $0.0013 | 3 | n/a | FAIL | FAIL | NO |

## Pareto frontier

- `qwen.qwen3-32b-v1:0` (quality=0.00, cost=$0.0012)

**Cheapest on frontier:** `qwen.qwen3-32b-v1:0`

## Recommendation

```toml
# Sweep candidates (run 2026-05-17): pareto-frontier members
#   - qwen.qwen3-32b-v1:0                                (cost=$0.0012, quality=0.00)
# Previous default: us.anthropic.claude-haiku-4-5-20251001-v1:0
```

## Run Metadata

- **Date:** 2026-05-17
- **Commit SHA:** `2c7bb0a`
- **Total cost:** $0.0318
- **Cases:** 12
