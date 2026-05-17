# Sweep: code_reader (cheap-fast tier)

## Candidates

- `us.anthropic.claude-haiku-4-5-20251001-v1:0`
- `us.amazon.nova-micro-v1:0`
- `us.amazon.nova-lite-v1:0`
- `qwen.qwen3-32b-v1:0`

## Raw Scores

| model_id | quality_mean | quality_std | cost_per_run_usd | n_cases | divergence_failures | gate1 | gate2 | qualified |
|---|---|---|---|---|---|---|---|---|
| `us.anthropic.claude-haiku-4-5-20251001-v1:0` | 0.889 | 0.314 | $0.0167 | 9 | n/a | n/a | PASS | YES |
| `us.amazon.nova-micro-v1:0` | 0.778 | 0.416 | n/a | 9 | n/a | n/a | PASS | YES |
| `us.amazon.nova-lite-v1:0` | 0.778 | 0.416 | n/a | 9 | n/a | n/a | PASS | YES |
| `qwen.qwen3-32b-v1:0` | 0.778 | 0.416 | n/a | 9 | n/a | n/a | PASS | YES |

## Pareto frontier

- `us.anthropic.claude-haiku-4-5-20251001-v1:0` (quality=0.00, cost=$0.0174)
- `us.amazon.nova-micro-v1:0` (quality=0.00, cost=N/A)
- `us.amazon.nova-lite-v1:0` (quality=0.00, cost=N/A)
- `qwen.qwen3-32b-v1:0` (quality=0.00, cost=N/A)

**Cheapest on frontier:** `us.anthropic.claude-haiku-4-5-20251001-v1:0`

## Recommendation

```toml
# Sweep candidates (run 2026-05-17): pareto-frontier members
#   - us.anthropic.claude-haiku-4-5-20251001-v1:0        (cost=$0.0174, quality=0.00)
#   - us.amazon.nova-micro-v1:0                          (cost=N/A, quality=0.00)
#   - us.amazon.nova-lite-v1:0                           (cost=N/A, quality=0.00)
#   - qwen.qwen3-32b-v1:0                                (cost=N/A, quality=0.00)
# Previous default: us.anthropic.claude-haiku-4-5-20251001-v1:0
```

## Run Metadata

- **Date:** 2026-05-17
- **Commit SHA:** `2c7bb0a`
- **Total cost:** $0.1502
- **Cases:** 36
