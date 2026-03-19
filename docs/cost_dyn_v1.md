# cost_dyn v1 — EGO Metrology

**Cost schema version :** `cost-dyn.v1`  
**Statut :** T3 figé  
**Date :** 2026-03-19

---

## Définition

`cost_dyn` est le **coût canonique relatif d'exécution** d'un run.

Ce n'est **pas** un coût USD, ni énergétique, ni GPU.  
C'est une métrique interne comparable entre politiques sur un même benchmark.

---

## Formule v1

```
cost_dyn = w_tokens × total_tokens + w_latency × latency_ms
```

### Poids v1

| Paramètre | Valeur | Rôle |
|---|---|---|
| `w_tokens` | `1.0` | Signal dominant — proxy du coût d'usage |
| `w_latency` | `0.001` | Signal secondaire — coût opérationnel visible |

### Exemple

```
total_tokens = 935
latency_ms   = 1842.6

cost_dyn = 1.0 × 935 + 0.001 × 1842.6
         = 935 + 1.8426
         = 936.8426
```

---

## Règles

**R1 — Pas de calcul partiel**  
Si `total_tokens` ou `latency_ms` est absent → `cost_dyn = None`.

**R2 — Pas d'unité cachée**  
`cost_dyn` n'est pas des dollars, pas des joules.

**R3 — Fonction pure**  
Le calcul est déterministe, sans I/O.

**R4 — Poids publics**  
`DEFAULT_W_TOKENS = 1.0`, `DEFAULT_W_LATENCY = 0.001` — visibles dans le code.

---

## API Python

```python
from ego_metrology.cost import (
    compute_cost_dyn,
    compute_cost_dyn_from_run,
    with_computed_cost_dyn,
)

# Calcul direct
compute_cost_dyn(total_tokens=935, latency_ms=1842.6)
# → 936.8426

# Depuis un RunRecord
cost = compute_cost_dyn_from_run(record)

# Enrichir un RunRecord (immutable)
enriched = with_computed_cost_dyn(record)              # conserve si déjà renseigné
enriched = with_computed_cost_dyn(record, overwrite=True)  # recalcule
```

---

## Limites v1

- `total_tokens` reste un proxy — ne distingue pas prefill/decode
- `latency_ms` latence totale — ne distingue pas réseau/compute
- poids non calibrés sur coûts réels fournisseur

Ces dimensions viendront en `cost-dyn.v2` si nécessaire.

---

## Champs réservés pour v2+

`prefill_ms`, `decode_ms`, `tools_count`, `loops_count`, `peak_vram_gb`, coût USD provider.
