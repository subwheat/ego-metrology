# routing_regret v1 — EGO Metrology

**Schema version :** `routing-regret.v1`  
**Statut :** T7 figé  
**Date :** 2026-03-19

---

## Définition

> T6 dit quel choix était optimal offline. T7 mesure combien le choix réellement évalué s'en écarte.

```
routing_regret = chosen_cost_dyn - cost_star
```

| Valeur | Interprétation |
|---|---|
| `0.0` | Choix optimal — correspond à l'oracle |
| `> 0` | Surcoût par rapport à l'oracle |
| `< 0` | Anomalie de données — à investiguer |

---

## Cas calculables

Le regret est calculable si :
- un `OracleRecord` existe pour le `task_id`
- `oracle.selection_status == "ok"`
- `oracle.cost_star is not None`
- `chosen_run.cost_dyn is not None`
- `benchmark_id` correspond entre run et oracle

---

## `regret_status`

| Valeur | Cause |
|---|---|
| `ok` | Regret calculé |
| `no_oracle` | Oracle absent ou sans cost_star |
| `chosen_cost_missing` | `cost_dyn` du run choisi est None |
| `benchmark_mismatch` | `benchmark_id` incompatible |

---

## Regrets négatifs

Un regret négatif n'est pas clampé — il est conservé et signalé dans `meta["negative_regret_detected"] = True`.

Un regret négatif indique une incohérence : oracle construit sur un sous-ensemble différent, runs versionnés différemment, ou mismatch de données.

---

## API Python

```python
from ego_metrology.regret import (
    build_regret_records,
    summarize_regret_records,
    append_regret_records_jsonl,
)

# Construire les regrets
regret_records = build_regret_records(chosen_runs, oracle_records)

# Résumé global
summary = summarize_regret_records(regret_records)
# {
#   "num_records_total": 5,
#   "num_regret_computable": 4,
#   "mean_routing_regret": 45.2,
#   "oracle_match_rate": 0.25,
#   "chosen_policy_counts": {"single_pass": 3, "single_pass_verify": 2}
# }

# Stocker
append_regret_records_jsonl("runs/regret.jsonl", regret_records)
```

---

## Format JSONL

```json
{
  "task_id": "bullshitbench_v2_software_0001",
  "benchmark_id": "bullshitbench_v2",
  "chosen_policy_id": "single_pass_verify",
  "oracle_policy_id": "single_pass",
  "chosen_cost_dyn": 412.4,
  "cost_star": 311.2,
  "routing_regret": 101.2,
  "chosen_passed_quality": true,
  "oracle_available": true,
  "regret_status": "ok",
  "schema_version": "routing-regret.v1",
  "meta": {
    "chosen_run_id": "RUN000001",
    "oracle_selection_status": "ok",
    "negative_regret_detected": false,
    "delta_vs_oracle_policy": "different_policy"
  }
}
```

---

## Limites v1

- Pas de pénalité d'échec qualité dans la formule
- Pas de regret normalisé par benchmark
- Pas de routeur online — T7 évalue des choix déjà matérialisés
- `p90_routing_regret` est une approximation simple (tri + index)
