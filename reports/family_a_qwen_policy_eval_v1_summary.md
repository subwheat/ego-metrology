# Family A — Qwen policy eval v1
## Verdict
- Le controller fonctionne comme infrastructure de routing/logging.
- Le cap `max_tokens` ne sépare pas le coût sur Family A.
- Family A mesure ici surtout la qualité de raisonnement, pas l'effet du controller.
- Qwen2.5-14B-Instruct est stable comme modèle intermédiaire.
- Prochaine étape recommandée : tâche à sortie plus longue ou politique multi-pass / cascade.

## Résumé par politique
| policy_id | n | accuracy | mean_cost_tokens | mean_prompt_tokens | mean_completion_tokens | mean_latency_ms |
|---|---:|---:|---:|---:|---:|---:|
| ego_controller_stub | 210 | 0.443 | 960.57 | 956.13 | 4.44 | 166.86 |
| fixed_cap_16 | 210 | 0.443 | 961.20 | 956.13 | 5.08 | 177.01 |
| fixed_cap_4 | 210 | 0.438 | 960.13 | 956.13 | 4.00 | 234.90 |
| fixed_cap_8 | 210 | 0.443 | 961.20 | 956.13 | 5.08 | 177.58 |

## Accuracy par niveau et politique
| policy_id | level | n | accuracy | mean_cost_tokens | mean_completion_tokens |
|---|---:|---:|---:|---:|---:|
| ego_controller_stub | 1 | 30 | 1.000 | 175.00 | 5.00 |
| ego_controller_stub | 2 | 30 | 0.800 | 232.87 | 5.00 |
| ego_controller_stub | 3 | 30 | 0.500 | 325.80 | 5.10 |
| ego_controller_stub | 4 | 30 | 0.200 | 516.37 | 4.00 |
| ego_controller_stub | 5 | 30 | 0.067 | 932.90 | 4.00 |
| ego_controller_stub | 6 | 30 | 0.100 | 1697.40 | 4.00 |
| ego_controller_stub | 7 | 30 | 0.433 | 2843.67 | 4.00 |
| fixed_cap_16 | 1 | 30 | 1.000 | 175.00 | 5.00 |
| fixed_cap_16 | 2 | 30 | 0.800 | 232.87 | 5.00 |
| fixed_cap_16 | 3 | 30 | 0.500 | 325.80 | 5.10 |
| fixed_cap_16 | 4 | 30 | 0.200 | 517.50 | 5.13 |
| fixed_cap_16 | 5 | 30 | 0.067 | 934.07 | 5.17 |
| fixed_cap_16 | 6 | 30 | 0.100 | 1698.50 | 5.10 |
| fixed_cap_16 | 7 | 30 | 0.433 | 2844.70 | 5.03 |
| fixed_cap_4 | 1 | 30 | 1.000 | 174.00 | 4.00 |
| fixed_cap_4 | 2 | 30 | 0.800 | 231.87 | 4.00 |
| fixed_cap_4 | 3 | 30 | 0.500 | 324.70 | 4.00 |
| fixed_cap_4 | 4 | 30 | 0.200 | 516.37 | 4.00 |
| fixed_cap_4 | 5 | 30 | 0.067 | 932.90 | 4.00 |
| fixed_cap_4 | 6 | 30 | 0.100 | 1697.40 | 4.00 |
| fixed_cap_4 | 7 | 30 | 0.400 | 2843.67 | 4.00 |
| fixed_cap_8 | 1 | 30 | 1.000 | 175.00 | 5.00 |
| fixed_cap_8 | 2 | 30 | 0.800 | 232.87 | 5.00 |
| fixed_cap_8 | 3 | 30 | 0.500 | 325.80 | 5.10 |
| fixed_cap_8 | 4 | 30 | 0.200 | 517.50 | 5.13 |
| fixed_cap_8 | 5 | 30 | 0.067 | 934.07 | 5.17 |
| fixed_cap_8 | 6 | 30 | 0.100 | 1698.50 | 5.10 |
| fixed_cap_8 | 7 | 30 | 0.433 | 2844.70 | 5.03 |
