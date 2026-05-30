# Sweep: ingestor (mid tier)

## Candidates

- `global.anthropic.claude-haiku-4-5-20251001-v1:0`
- `qwen.qwen3-32b-v1:0`
- `openai.gpt-oss-120b-1:0`
- `minimax.minimax-m2.5`
- `qwen.qwen3-next-80b-a3b`
- `zai.glm-4.7-flash`
- `qwen.qwen3-vl-235b-a22b`

## Raw Scores

| model_id | quality_mean | quality_std | cost_per_run_usd | n_cases | divergence_failures | gate1 | gate2 | qualified |
|---|---|---|---|---|---|---|---|---|
| `global.anthropic.claude-haiku-4-5-20251001-v1:0` | 0.000 | 0.000 | $0.0062 | 3 | n/a | FAIL | PASS | NO |
| `qwen.qwen3-32b-v1:0` | 0.000 | 0.000 | $0.0007 | 3 | n/a | FAIL | PASS | NO |
| `openai.gpt-oss-120b-1:0` | 0.000 | n/a | n/a | 0 | n/a | PASS | n/a | YES |
| `minimax.minimax-m2.5` | 0.000 | n/a | n/a | 0 | n/a | PASS | n/a | YES |
| `qwen.qwen3-next-80b-a3b` | 0.000 | 0.000 | $0.0010 | 3 | n/a | FAIL | PASS | NO |
| `zai.glm-4.7-flash` | 0.000 | 0.000 | $0.0004 | 3 | n/a | FAIL | PASS | NO |
| `qwen.qwen3-vl-235b-a22b` | 0.000 | 0.000 | $0.0029 | 3 | n/a | FAIL | PASS | NO |

## Pareto frontier

- `zai.glm-4.7-flash` (quality=0.00, cost=$0.0004)

**Cheapest on frontier:** `zai.glm-4.7-flash`

## Recommendation

```toml
# Sweep candidates (run 2026-05-29): pareto-frontier members
#   - zai.glm-4.7-flash                                  (cost=$0.0004, quality=0.00)
# Previous default: global.anthropic.claude-haiku-4-5-20251001-v1:0
```

## Run Metadata

- **Date:** 2026-05-29
- **Commit SHA:** `21be485`
- **Total cost:** $0.0336
- **Cases:** 15
