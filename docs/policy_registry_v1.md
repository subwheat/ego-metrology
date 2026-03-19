# Policy Registry v1 — EGO Metrology

**Registry version :** `policy-registry.v1`  
**Statut :** T2 figé — ne pas modifier sans bump de version  
**Date :** 2026-03-19

---

## Principe

Le registre des politiques est **déclaratif**.  
Il nomme et décrit les familles d'inférence comparées par EGO Metrology.

1 entrée = 1 politique stable identifiée par un `policy_id` canonique.

---

## Politiques v1

### `single_pass`
Génération directe sans vérification. Référence de coût minimal.

### `single_pass_verify`
Génération suivie d'une passe de vérification explicite. Test de l'apport d'une étape de contrôle bon marché.

### `cascade_small_to_large`
Première tentative légère, escalade vers un modèle ou une stratégie plus forte si nécessaire. Description offline uniquement en T2 — le câblage d'exécution vient plus tard.

---

## Schéma d'une politique

| Champ | Type | Description |
|---|---|---|
| `policy_id` | `string` | Identifiant stable, snake_case, non vide |
| `description` | `string` | Description courte de l'intention |
| `execution_mode` | `string` | `single_pass`, `verify_pass`, ou `cascade` |
| `verification_enabled` | `bool` | Passe de vérification explicite |
| `cascade_enabled` | `bool` | Escalade vers une stratégie plus forte |
| `cascade_target` | `string \| null` | Cible de cascade si applicable |
| `max_passes` | `int` | Nombre maximal de passes logiques (≥ 1) |
| `notes` | `string \| null` | Précisions libres |

---

## Cohérences croisées obligatoires

| Condition | Contrainte |
|---|---|
| `cascade_enabled = false` | `cascade_target` doit être `null` |
| `cascade_enabled = true` | `cascade_target` doit être non nul |
| `verification_enabled = true` | `max_passes >= 2` |
| `execution_mode = "single_pass"` | `max_passes == 1` |
| `execution_mode = "verify_pass"` | `max_passes >= 2` |
| `execution_mode = "cascade"` | `cascade_enabled = true` |

---

## Règles de stabilité

**R1 — `policy_id` est un contrat public**  
Une fois utilisé dans des runs, on ne le renomme pas sans vraie rupture de contrat.

**R2 — le registre est déclaratif**  
Pas de logique d'exécution dans le JSON.

**R3 — pas de champs prématurés**  
`model_name`, `context_mode`, `retrieval_mode`, `temperature`, `max_tokens` n'existent pas en v1. Ces dimensions viendront si elles deviennent nécessaires.

---

## API Python

```python
from ego_metrology.policies import (
    load_policy_registry,
    get_policy,
    list_policy_ids,
)

registry = load_policy_registry("ego_metrology/policy_registry.json")

ids = list_policy_ids(registry)
# ["single_pass", "single_pass_verify", "cascade_small_to_large"]

policy = get_policy(registry, "single_pass_verify")
# PolicySpec(policy_id="single_pass_verify", max_passes=2, ...)
```

---

## Champs réservés pour T3+

Ces dimensions **n'existent pas en v1** :

- `model_name` — lié au runner, pas à la politique
- `context_mode` / `retrieval_mode` — T4+
- `cost_dyn` / `cost_star` — T3/T6
- `routing_regret` — T7
