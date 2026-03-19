# Reporting v1 — EGO Metrology Sprint Report

**Schema version :** `reporting.v1`  
**Statut :** T8 figé  
**Date :** 2026-03-19

---

## Rôle

> T8 ne mesure pas plus. T8 rend la mesure exploitable.

Le module de reporting transforme les artefacts du sprint (RunRecord, OracleRecord, RegretRecord) en un rapport d'aide à la décision.

**Question centrale :**
> Quelle politique doit être la politique par défaut, sur quel critère, et avec quel compromis coût/qualité ?

---

## Règle de recommandation

La politique par défaut est sélectionnée par ordre de priorité :

1. Maximiser `quality_pass_rate`
2. À égalité : minimiser `mean_routing_regret`
3. À égalité : minimiser `mean_cost_dyn`
4. À égalité : ordre lexicographique de `policy_id`

---

## Champs du `PolicySummaryRecord`

| Champ | Source | Description |
|---|---|---|
| `num_runs` | RunRecord | Nombre total de runs |
| `num_quality_passed` | RunRecord | Runs avec `passed_quality=True` |
| `quality_pass_rate` | RunRecord | `num_quality_passed / num_runs` |
| `mean_quality_score` | RunRecord | Moyenne des scores |
| `mean_cost_dyn` | RunRecord | Coût moyen |
| `median_cost_dyn` | RunRecord | Coût médian |
| `mean_routing_regret` | RegretRecord | Regret moyen calculable |
| `median_routing_regret` | RegretRecord | Regret médian calculable |
| `oracle_match_rate` | RegretRecord | Proportion de choix = oracle |

---

## API Python

```python
from ego_metrology.reporting import (
    build_policy_summary_records,
    summarize_sprint_outcome,
    render_markdown_report,
    write_markdown_report,
    write_policy_summary_csv,
)

# Agréger
summaries = build_policy_summary_records(runs, regrets, benchmark_id="bullshitbench_v2")

# Résumé sprint
sprint = summarize_sprint_outcome(summaries)

# Rapport Markdown
md = render_markdown_report(summaries, sprint, benchmark_id="bullshitbench_v2")
write_markdown_report("reports/sprint_report_bullshitbench_v2.md", md)

# CSV
write_policy_summary_csv("reports/policy_summary_bullshitbench_v2.csv", summaries)
```

---

## Fichiers de sortie recommandés

```
reports/sprint_report_bullshitbench_v2.md
reports/policy_summary_bullshitbench_v2.csv
```

---

## Limites v1

- Rapport sur un seul benchmark à la fois
- `cost_dyn` v1 est un proxy tokens+latence, pas un coût fournisseur réel
- `routing_regret` non calculable si `cost_dyn` ou oracle manquant
- `single_pass_verify` et `cascade_small_to_large` pas encore exécutables en mode réel
- Pas de graphiques ni de dashboard
