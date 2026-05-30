# Sweep: code_reader (cheap-fast tier)

## Candidates

- `global.anthropic.claude-haiku-4-5-20251001-v1:0`
- `qwen.qwen3-coder-30b-a3b-v1:0`
- `qwen.qwen3-coder-next`
- `mistral.devstral-2-123b`
- `openai.gpt-oss-120b-1:0`
- `minimax.minimax-m2.5`

## Raw Scores

| model_id | quality_mean | quality_std | cost_per_run_usd | n_cases | divergence_failures | gate1 | gate2 | qualified |
|---|---|---|---|---|---|---|---|---|
| `global.anthropic.claude-haiku-4-5-20251001-v1:0` | 0.889 | 0.314 | $0.1180 | 18 | n/a | FAIL | PASS | NO |
| `qwen.qwen3-coder-30b-a3b-v1:0` | 0.944 | 0.229 | n/a | 18 | n/a | FAIL | PASS | NO |
| `qwen.qwen3-coder-next` | 0.944 | 0.229 | n/a | 18 | n/a | FAIL | PASS | NO |
| `mistral.devstral-2-123b` | 0.944 | 0.229 | n/a | 18 | n/a | FAIL | PASS | NO |
| `openai.gpt-oss-120b-1:0` | 1.000 | 0.000 | n/a | 18 | n/a | FAIL | PASS | NO |
| `minimax.minimax-m2.5` | 0.944 | 0.229 | n/a | 18 | n/a | FAIL | PASS | NO |

## Pareto frontier

- `global.anthropic.claude-haiku-4-5-20251001-v1:0` (quality=0.00, cost=$0.1103)
- `qwen.qwen3-coder-30b-a3b-v1:0` (quality=0.00, cost=N/A)
- `qwen.qwen3-coder-next` (quality=0.00, cost=N/A)
- `mistral.devstral-2-123b` (quality=0.00, cost=N/A)
- `openai.gpt-oss-120b-1:0` (quality=1.00, cost=N/A)
- `minimax.minimax-m2.5` (quality=0.00, cost=N/A)

**Cheapest on frontier:** `global.anthropic.claude-haiku-4-5-20251001-v1:0`

## Recommendation

```toml
# Sweep candidates (run 2026-05-29): pareto-frontier members
#   - global.anthropic.claude-haiku-4-5-20251001-v1:0    (cost=$0.1103, quality=0.00)
#   - qwen.qwen3-coder-30b-a3b-v1:0                      (cost=N/A, quality=0.00)
#   - qwen.qwen3-coder-next                              (cost=N/A, quality=0.00)
#   - mistral.devstral-2-123b                            (cost=N/A, quality=0.00)
#   - openai.gpt-oss-120b-1:0                            (cost=N/A, quality=1.00)
#   - minimax.minimax-m2.5                               (cost=N/A, quality=0.00)
# Previous default: global.anthropic.claude-haiku-4-5-20251001-v1:0
```

## Run Metadata

- **Date:** 2026-05-29
- **Commit SHA:** `21be485`
- **Total cost:** $2.1241
- **Cases:** 108
