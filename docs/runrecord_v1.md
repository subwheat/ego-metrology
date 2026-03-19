# RunRecord v1 — Schéma canonique EGO Metrology

**Schema version :** `runrecord.v1`  
**Statut :** T1 figé — ne pas modifier sans bump de version  
**Date :** 2026-03-19

---

## Principe

1 ligne JSONL = 1 exécution de `task × policy × model`.

Le `RunRecord` est l'unité atomique de mesure du projet.  
Tous les runners produisent ce format. Toutes les analyses le consomment.

---

## Champs

### A. Identité (tous requis)

| Champ | Type | Description |
|---|---|---|
| `run_id` | `string` | Identifiant unique du run (ex: ULID) |
| `timestamp_utc` | `string` | ISO-8601 UTC — ex: `2026-03-19T16:42:31Z` |
| `task_id` | `string` | Identifiant de la tâche dans le benchmark |
| `benchmark_id` | `string` | Identifiant du benchmark (ex: `bullshitbench_v2`) |
| `model_name` | `string` | Nom du modèle (ex: `mistralai/Mistral-7B-Instruct-v0.2`) |
| `policy_id` | `string` | Identifiant de la politique (ex: `single_pass`) |

### B. Qualité (nullable)

| Champ | Type | Description |
|---|---|---|
| `quality_score` | `float \| null` | Score de qualité observé |
| `quality_threshold` | `float \| null` | Seuil minimal acceptable |
| `passed_quality` | `bool \| null` | `true` si `score >= threshold` |

### C. Usage / coût (nullable)

| Champ | Type | Description |
|---|---|---|
| `prompt_tokens` | `int \| null` | Tokens en entrée |
| `completion_tokens` | `int \| null` | Tokens en sortie |
| `total_tokens` | `int \| null` | Somme des deux si disponibles |
| `latency_ms` | `float \| null` | Latence totale en ms |
| `cost_dyn` | `float \| null` | Coût dynamique réel (calcul = Ticket 3) |

### D. Exécution / provenance (requis)

| Champ | Type | Valeurs |
|---|---|---|
| `backend_name` | `string` | `openai_compat`, `anthropic_api`, `local_vllm`, `offline_import` |
| `manifest_hash` | `string` | Hash SHA-256 du CalibrationManifest |
| `calibration_status` | `string` | `experimental`, `candidate`, `frozen` |

### E. Reproductibilité

| Champ | Type | Description |
|---|---|---|
| `seed` | `int \| null` | Graine aléatoire si applicable |
| `runner_version` | `string` | Ex: `ego-metrology/0.3.0-dev` |
| `schema_version` | `string` | Toujours `runrecord.v1` |

### F. Extension

| Champ | Type | Description |
|---|---|---|
| `meta` | `object` | Infos non stables — aucun champ critique ici |

---

## Règles strictes

**R1 — Aucun champ implicite**  
Si une info n'existe pas → `null`. Pas de calcul implicite.

**R2 — `total_tokens`**  
Si `prompt_tokens` et `completion_tokens` sont présents :  
`total_tokens = prompt_tokens + completion_tokens`  
Sinon `null`.

**R3 — `passed_quality`**  
- `true` si `quality_score >= quality_threshold`  
- `false` si score existe, threshold existe, et seuil non atteint  
- `null` si score ou threshold absent

**R4 — `cost_dyn`**  
Champ présent dans le schéma, valeur `null` autorisée. Calcul réel = Ticket 3.

**R5 — `meta`**  
Réservé aux infos non stables (raw ids, judge labels, tags).  
Aucun champ critique ne doit vivre uniquement dans `meta`.

---

## Exemple canonique

```json
{
  "run_id": "01HRYV8ST0FK8Q6M7N0K6Y4F3A",
  "timestamp_utc": "2026-03-19T16:42:31Z",
  "task_id": "bullshitbench_v2_software_0042",
  "benchmark_id": "bullshitbench_v2",
  "model_name": "mistralai/Mistral-7B-Instruct-v0.2",
  "policy_id": "single_pass",
  "quality_score": 2.0,
  "quality_threshold": 2.0,
  "passed_quality": true,
  "prompt_tokens": 814,
  "completion_tokens": 121,
  "total_tokens": 935,
  "latency_ms": 1842.6,
  "cost_dyn": null,
  "backend_name": "local_vllm",
  "manifest_hash": "sha256:5c8c8db1d8d7b8c2d6d5d3a9161d2c8f0e7f0d7f8e7c5b6a4d9e1f2c3b4a5d6e",
  "calibration_status": "experimental",
  "seed": 42,
  "runner_version": "ego-metrology/0.3.0-dev",
  "schema_version": "runrecord.v1",
  "meta": {
    "judge_source": "bullshitbench_import",
    "raw_label": "clear_pushback"
  }
}
```

---

## API Python

```python
from ego_metrology.logging_schema import (
    RunRecord,
    make_run_record,
    append_run_record_jsonl,
    load_run_records_jsonl,
)

# Création avec auto-calculs
r = make_run_record(
    run_id="...",
    prompt_tokens=814,
    completion_tokens=121,   # → total_tokens=935 auto
    quality_score=2.0,
    quality_threshold=2.0,   # → passed_quality=True auto
    ...
)

# Écriture append-only
append_run_record_jsonl("runs/family_a.jsonl", r)

# Chargement
records = load_run_records_jsonl("runs/family_a.jsonl")
```

---

## Champs réservés pour T2+

Ces champs **n'existent pas encore** dans `runrecord.v1` :

- `oracle_policy_id` — T6
- `cost_star` — T6
- `routing_regret` — T7
- `alpha_s_ctx` — T5
- `recoverability_eps` — T5

Toute extension passe par un nouveau `schema_version`.
