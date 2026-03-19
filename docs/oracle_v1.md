# Oracle offline C* v1 — EGO Metrology

**Schema version :** `oracle.v1`  
**Statut :** T6 figé  
**Date :** 2026-03-19

---

## Définition

> T5 mesure des exécutions. T6 transforme ces exécutions en référence optimale offline.

L'oracle calcule, pour chaque tâche, la politique admissible au coût minimal parmi les runs déjà produits.

---

## Définition de C*

```
C*(task) = min cost_dyn(run)
           sur les runs tels que :
             - même task_id
             - passed_quality == True
             - cost_dyn is not None
```

La politique associée est `oracle_policy_id = argmin cost_dyn`.

---

## Critères d'admissibilité

Un run est **admissible** si :
- `passed_quality == True`
- `cost_dyn is not None`

Un run est **non admissible** si :
- `passed_quality != True` (False ou None)
- ou `cost_dyn is None`

---

## Tie-break

À coût `cost_dyn` égal :

1. Plus grand `quality_score` gagne
2. Si égalité : ordre lexicographique de `policy_id` (déterminisme final)

---

## `selection_status`

| Valeur | Sens |
|---|---|
| `ok` | Au moins un run admissible — oracle calculé |
| `no_admissible_run` | Aucun run ne passe qualité avec coût observable |

---

## API Python

```python
from ego_metrology.oracle import (
    select_oracle_run_for_task,
    build_oracle_records,
    summarize_oracle_records,
    append_oracle_records_jsonl,
    load_run_records_for_oracle,
)

# Charger les runs
runs = load_run_records_for_oracle("runs/family_a.jsonl")

# Oracle par tâche
records = build_oracle_records(runs, benchmark_id="bullshitbench_v2")

# Résumé global
summary = summarize_oracle_records(records)
# {
#   "num_tasks_total": 5,
#   "oracle_coverage": 0.8,
#   "mean_cost_star": 412.7,
#   "oracle_policy_win_counts": {"single_pass": 3, "single_pass_verify": 1}
# }

# Stocker les résultats
append_oracle_records_jsonl("runs/oracle.jsonl", records)
```

---

## Format JSONL oracle

```json
{
  "task_id": "bullshitbench_v2_software_0001",
  "benchmark_id": "bullshitbench_v2",
  "oracle_policy_id": "single_pass",
  "cost_star": 168.25,
  "oracle_quality_score": 2.0,
  "candidate_policy_ids": ["single_pass", "single_pass_verify"],
  "admissible_policy_ids": ["single_pass", "single_pass_verify"],
  "num_candidates": 2,
  "num_admissible": 2,
  "selection_status": "ok",
  "schema_version": "oracle.v1",
  "meta": {
    "selected_run_id": "RUN000001",
    "selected_model_name": "qwen2.5-14b",
    "tie_break_applied": false,
    "observed_policy_ids": ["single_pass", "single_pass_verify"]
  }
}
```

---

## Règles strictes

**R1 — Oracle offline uniquement** — T6 ne lance aucun backend.

**R2 — Admissibilité stricte** — `passed_quality=None` n'est pas admissible.

**R3 — Sélection déterministe** — même entrée → même oracle.

**R4 — Pas de score inventé** — si aucun admissible, tous les champs de sélection sont `None`.

**R5 — Une tâche = un OracleRecord** — même si plusieurs politiques ont été testées.

---

## Limites v1

- Pas d'ensemble attendu de politiques (pas de `expected_policy_ids`)
- Pas de pondération par benchmark
- Pas d'oracle multi-objectifs
- Pas de routeur online — T7 `routing_regret` vient après
