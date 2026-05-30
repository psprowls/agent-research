# Sweep: linter (mid tier)

## Candidates

- `global.anthropic.claude-haiku-4-5-20251001-v1:0`
- `qwen.qwen3-32b-v1:0`
- `openai.gpt-oss-120b-1:0`
- `deepseek.v3.2`
- `minimax.minimax-m2.5`
- `zai.glm-4.7-flash`

## Raw Scores

| model_id | quality_mean | quality_std | cost_per_run_usd | n_cases | divergence_failures | gate1 | gate2 | qualified |
|---|---|---|---|---|---|---|---|---|
| `global.anthropic.claude-haiku-4-5-20251001-v1:0` | 0.000 | 0.000 | $0.0210 | 12 | n/a | PASS | n/a | YES |
| `qwen.qwen3-32b-v1:0` | 0.000 | 0.000 | $0.0024 | 12 | n/a | PASS | n/a | YES |
| `openai.gpt-oss-120b-1:0` | 0.000 | 0.000 | $0.0037 | 12 | n/a | PASS | n/a | YES |
| `deepseek.v3.2` | 0.000 | 0.000 | $0.0102 | 12 | n/a | PASS | n/a | YES |
| `minimax.minimax-m2.5` | 0.000 | 0.000 | $0.0069 | 12 | n/a | PASS | n/a | YES |
| `zai.glm-4.7-flash` | 0.000 | 0.000 | $0.0012 | 12 | n/a | PASS | n/a | YES |

## Pareto frontier

- `zai.glm-4.7-flash` (quality=0.00, cost=$0.0011)

**Cheapest on frontier:** `zai.glm-4.7-flash`

## Recommendation

```toml
# Sweep candidates (run 2026-05-29): pareto-frontier members
#   - zai.glm-4.7-flash                                  (cost=$0.0011, quality=0.00)
# Previous default: global.anthropic.claude-haiku-4-5-20251001-v1:0
```

## Run Metadata

- **Date:** 2026-05-29
- **Commit SHA:** `21be485`
- **Total cost:** $0.5462
- **Cases:** 72
