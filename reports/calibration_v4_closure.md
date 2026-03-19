# EGO Metrology — Rapport de clôture calibration v4
*Date : 2026-03-19*

## Benchmark

- **Protocole** : v4.4 — conditional retrieval / reasoning
- **Familles** : A (count+bind), B (color+section→protocol), C (date+role→auth)
- **Corpus figé** : `data/family_a_fixed_v1.json` — 210 items (30/niveau × 7 niveaux)
- **Bruit** : décontaminé v1 (sans Vega, sans Manager, sans dates 2025)

## Modèles testés

| Modèle | Statut | Raison |
|--------|--------|--------|
| Mistral-7B-Instruct | ❌ écarté | plancher sur A, retrieval pur trop facile |
| DeepSeek-coder-6.7B | ❌ écarté | bascule mode code, instable |
| Claude Haiku | ✓ contrôle positif | 100% L1 toutes familles, plafond sur B/C |
| **Qwen2.5-14B-Instruct** | ✓ **retenu** | modèle intermédiaire stable, signal réel sur A |

## Familles

| Famille | Statut | Raison |
|---------|--------|--------|
| **A** | ✓ **retenue** | seule famille avec gradient utile sur Qwen |
| B | ⚠ non calibrante | plafond Haiku, instable DeepSeek |
| C | ⚠ non calibrante | plafond Qwen, bruit résiduel Manager |

## Accuracy Qwen par niveau — Family A (corpus propre, 10 runs)

| Niveau | Bruit | Accuracy |
|--------|-------|----------|
| L1 | 0 | ~100% |
| L2 | 3 | ~100% |
| L3 | 8 | ~70% |
| L4 | 18 | ~40% |
| L5 | 40 | ~20% |
| L6 | 80 | ~10% |
| L7 | 140 | ~20% |

Signal présent, courbe non monotone — variance trop élevée à 10 runs pour fitter a_secteur/beta_secteur.

## Politiques testées

| Politique | Accuracy | Statut |
|-----------|----------|--------|
| fixed_cap_4/8/16 | 44% | non discriminantes — completion ~4 tokens quelle que soit la cap |
| qwen_single_pass | 44% | baseline de référence |
| qwen_verify_pass_always | ~44% | trop coûteux pour gain limité |
| qwen_verify_if_invalid | ~44% | mal ciblée — mode d'échec est sémantique, pas format |

## Mode d'échec dominant

**wrong_condition / binding** — le modèle choisit un distracteur plausible,
pas un problème de format. La réponse est bien formée mais fausse.

Politique candidate pour phase suivante :
`verify_if_wrong_condition_or_invalid` — 2ème pass ciblé sur les cas parsables mais faux.

## Conclusion

- a_secteur / beta_secteur : **non calibrés** — signal insuffisant pour fit fiable
- Modèle retenu : **Qwen2.5-14B-Instruct**
- Famille retenue : **Family A**
- Phase suivante : stabiliser le protocole, augmenter les runs, tester verify_if_wrong_condition

## Fichiers produits
```
data/family_a_fixed_v1.json
runs/family_a_qwen_policy_eval_v1.jsonl
runs/family_a_qwen_verify_eval_v1.jsonl
reports/family_a_qwen_policy_eval_v1_summary.json
reports/family_a_qwen_policy_eval_v1_summary.md
reports/calibration_v4_closure.md
calibrate_mistral_v4.py
calibrate_haiku_v4_full.py
calibrate_deepseek_v4_full.py
calibrate_qwen_v4_clean.py
```
