# Runner canonique v1 — EGO Metrology

**Statut :** T5 figé  
**Date :** 2026-03-19

---

## Rôle

Le runner est le **point d'entrée unique** qui exécute :

```
task × policy × model → RunRecord
```

> T5 n'évalue pas encore la meilleure politique.  
> Il exécute proprement une politique donnée et enregistre le résultat canonique.

---

## Flux nominal

1. Charger la tâche (`BenchmarkTask`)
2. Charger la policy depuis le registry (`PolicySpec`)
3. Vérifier que la policy est exécutable
4. Appeler le backend (ou dry_run)
5. Construire le `RunRecord`
6. Calculer `cost_dyn` via T3
7. Append JSONL si demandé
8. Retourner le record

---

## Politiques supportées

| `policy_id` | Mode réel | Mode dry_run |
|---|---|---|
| `single_pass` | ✅ | ✅ |
| `single_pass_verify` | ❌ `NotImplementedError` | ✅ |
| `cascade_small_to_large` | ❌ `NotImplementedError` | ✅ |

---

## API Python

```python
from ego_metrology.runners.run_benchmark import run_task_with_policy, run_task_id_with_policy
from ego_metrology.backends.base import FakeBackend

# Exécution directe
record = run_task_with_policy(
    task=task,
    model_name="qwen2.5-14b",
    policy_id="single_pass",
    backend_name="local_vllm",
    manifest_hash="sha256:...",
    calibration_status="experimental",
    runner_version="ego-metrology/0.3.0-dev",
    backend=FakeBackend(),
    output_jsonl_path="runs/sample.jsonl",
)

# Résolution par task_id
record = run_task_id_with_policy(
    task_id="bullshitbench_v2_software_0001",
    tasks=tasks,
    registry=registry,
    ...
)
```

---

## CLI

```bash
python -m ego_metrology.runners.run_benchmark \
  --tasks-path tests/fixtures/bullshitbench_sample_tasks.json \
  --task-id bullshitbench_v2_software_0001 \
  --policy-id single_pass \
  --model-name qwen2.5-14b \
  --backend-name fake_backend \
  --output runs/sample.jsonl
```

Flags :
- `--dry-run` : pas d'appel backend réel
- `--seed INT` : graine aléatoire
- `--registry-path PATH` : chemin du policy_registry.json

---

## Règles strictes

**R1 — JSONL append-only**  
`output_jsonl_path` est toujours en mode append. Jamais de rewrite implicite.

**R2 — Pas de backend fantôme**  
`dry_run=False` sans backend → `ValueError` explicite.

**R3 — Pas de qualité inventée**  
`quality_score`, `quality_threshold`, `passed_quality` restent `None` sans jugement importé.

**R4 — cost_dyn depuis observables uniquement**  
Pas de coût calculé si tokens ou latence manquent.

**R5 — Pas d'oracle**  
Une exécution = une policy choisie, point.

---

## Meta du RunRecord produit

```json
{
  "domain": "software",
  "technique": "plausible_nonexistent_framework",
  "source_ref": "sample_0001",
  "benchmark_adapter": "bullshitbench_v2",
  "policy_execution_mode": "single_pass",
  "dry_run": false,
  "response_text": "This framework does not appear to exist...",
  "backend_meta": {
    "backend": "fake",
    "model_name": "qwen2.5-14b"
  }
}
```

---

## Limites v1

- `single_pass_verify` et `cascade_small_to_large` ne sont pas encore exécutables
- Pas d'API HTTP (T6+)
- Pas de panel de jugement automatique
- Pas de parallélisme
- Pas de retries réseau
