# Sweep: synthesizer (quality tier)

## Candidates

- `global.anthropic.claude-haiku-4-5-20251001-v1:0`
- `qwen.qwen3-32b-v1:0`
- `zai.glm-5`
- `moonshotai.kimi-k2.5`
- `deepseek.v3.2`
- `qwen.qwen3-next-80b-a3b`
- `us.deepseek.r1-v1:0`
- `moonshot.kimi-k2-thinking`

## Raw Scores

| model_id | quality_mean | quality_std | cost_per_run_usd | n_cases | divergence_failures | gate1 | gate2 | qualified |
|---|---|---|---|---|---|---|---|---|
| `global.anthropic.claude-haiku-4-5-20251001-v1:0` | 0.917 | 0.276 | $0.0844 | 12 | n/a | FAIL | PASS | NO |
| `qwen.qwen3-32b-v1:0` | 1.000 | 0.000 | $0.0011 | 12 | n/a | FAIL | PASS | NO |
| `zai.glm-5` | 1.000 | 0.000 | $0.0074 | 12 | n/a | FAIL | PASS | NO |
| `moonshotai.kimi-k2.5` | 1.000 | 0.000 | $0.0048 | 12 | n/a | FAIL | PASS | NO |
| `deepseek.v3.2` | 1.000 | 0.000 | $0.0040 | 12 | n/a | FAIL | PASS | NO |
| `qwen.qwen3-next-80b-a3b` | 1.000 | 0.000 | $0.0015 | 12 | n/a | FAIL | FAIL | NO |
| `us.deepseek.r1-v1:0` | 0.000 | n/a | n/a | 0 | n/a | PASS | n/a | YES |
| `moonshot.kimi-k2-thinking` | 0.000 | n/a | n/a | 0 | n/a | PASS | n/a | YES |

## Pareto frontier

- `qwen.qwen3-32b-v1:0` (quality=1.00, cost=$0.0012)

**Cheapest on frontier:** `qwen.qwen3-32b-v1:0`

## Recommendation

```toml
# Sweep candidates (run 2026-05-29): pareto-frontier members
#   - qwen.qwen3-32b-v1:0                                (cost=$0.0012, quality=1.00)
# Previous default: global.anthropic.claude-haiku-4-5-20251001-v1:0
```

## Run Metadata

- **Date:** 2026-05-29
- **Commit SHA:** `21be485`
- **Total cost:** $1.2392
- **Cases:** 72
