# Sweep: librarian (quality tier)

## Candidates

- `global.anthropic.claude-haiku-4-5-20251001-v1:0`
- `qwen.qwen3-32b-v1:0`
- `qwen.qwen3-next-80b-a3b`
- `deepseek.v3.2`
- `moonshotai.kimi-k2.5`
- `zai.glm-5`

## Raw Scores

| model_id | quality_mean | quality_std | cost_per_run_usd | n_cases | divergence_failures | gate1 | gate2 | qualified |
|---|---|---|---|---|---|---|---|---|
| `global.anthropic.claude-haiku-4-5-20251001-v1:0` | 1.000 | 0.000 | $0.0745 | 12 | n/a | FAIL | PASS | NO |
| `qwen.qwen3-32b-v1:0` | 1.000 | 0.000 | $0.0043 | 12 | n/a | FAIL | FAIL | NO |
| `qwen.qwen3-next-80b-a3b` | 1.000 | 0.000 | $0.0040 | 12 | n/a | FAIL | FAIL | NO |
| `deepseek.v3.2` | 0.917 | 0.276 | $0.0595 | 12 | n/a | FAIL | PASS | NO |
| `moonshotai.kimi-k2.5` | 1.000 | 0.000 | $0.0245 | 12 | n/a | FAIL | PASS | NO |
| `zai.glm-5` | 0.917 | 0.276 | $0.0286 | 12 | n/a | FAIL | FAIL | NO |

## Pareto frontier

- `qwen.qwen3-32b-v1:0` (quality=1.00, cost=$0.0036)

**Cheapest on frontier:** `qwen.qwen3-32b-v1:0`

## Recommendation

```toml
# Sweep candidates (run 2026-05-29): pareto-frontier members
#   - qwen.qwen3-32b-v1:0                                (cost=$0.0036, quality=1.00)
# Previous default: global.anthropic.claude-haiku-4-5-20251001-v1:0
```

## Run Metadata

- **Date:** 2026-05-29
- **Commit SHA:** `21be485`
- **Total cost:** $2.3447
- **Cases:** 72
