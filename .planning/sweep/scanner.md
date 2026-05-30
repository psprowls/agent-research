# Sweep: scanner (cheap-fast tier)

## Candidates

- `global.anthropic.claude-haiku-4-5-20251001-v1:0`
- `openai.gpt-oss-20b-1:0`
- `zai.glm-4.7-flash`
- `mistral.ministral-3-14b-instruct`
- `qwen.qwen3-32b-v1:0`
- `qwen.qwen3-coder-30b-a3b-v1:0`

## Raw Scores

| model_id | quality_mean | quality_std | cost_per_run_usd | n_cases | divergence_failures | gate1 | gate2 | qualified |
|---|---|---|---|---|---|---|---|---|
| `global.anthropic.claude-haiku-4-5-20251001-v1:0` | 0.000 | 0.000 | $0.0384 | 12 | n/a | FAIL | PASS | NO |
| `openai.gpt-oss-20b-1:0` | 0.000 | 0.000 | $0.0051 | 12 | n/a | FAIL | PASS | NO |
| `zai.glm-4.7-flash` | 0.000 | 0.000 | $0.0023 | 12 | n/a | FAIL | PASS | NO |
| `mistral.ministral-3-14b-instruct` | 0.000 | 0.000 | $0.0037 | 12 | n/a | FAIL | PASS | NO |
| `qwen.qwen3-32b-v1:0` | 0.000 | 0.000 | $0.0052 | 12 | n/a | FAIL | PASS | NO |
| `qwen.qwen3-coder-30b-a3b-v1:0` | 0.000 | 0.000 | $0.0061 | 12 | n/a | FAIL | PASS | NO |

## Pareto frontier

- `zai.glm-4.7-flash` (quality=0.00, cost=$0.0023)

**Cheapest on frontier:** `zai.glm-4.7-flash`

## Recommendation

```toml
# Sweep candidates (run 2026-05-29): pareto-frontier members
#   - zai.glm-4.7-flash                                  (cost=$0.0023, quality=0.00)
# Previous default: global.anthropic.claude-haiku-4-5-20251001-v1:0
```

## Run Metadata

- **Date:** 2026-05-29
- **Commit SHA:** `21be485`
- **Total cost:** $0.7281
- **Cases:** 72
