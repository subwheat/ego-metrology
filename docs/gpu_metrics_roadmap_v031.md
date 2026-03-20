# GPU Metrics — Roadmap v0.3.1

**Priorité : HAUTE**  
**Contexte : métriques essentielles pour cost_dyn v2 et calibration empirique**  
**Date : 2026-03-20**

---

## Pourquoi c'est critique

`cost_dyn` v1 est un proxy `tokens + latence`. C'est intentionnellement simple.  
Mais pour un modèle mathématique sérieux (EGO, CRÓNOS, calibration `a_secteur/beta_secteur`), il faut les **vrais observables GPU** :

- la consommation mémoire réelle (pas juste les tokens)
- la puissance GPU consommée par inférence
- le temps de prefill vs decode séparément
- l'utilisation GPU en % pendant le run

Sans ça, `cost_dyn` reste une heuristique. Avec ça, on peut construire un **vrai coût physique**.

---

## Ce que vLLM expose déjà — endpoint `/metrics`

vLLM expose un endpoint Prometheus natif sur `/metrics`.

```bash
curl http://51.159.139.27:8000/metrics
```

### Métriques clés disponibles

| Métrique Prometheus | Signification |
|---|---|
| `vllm:gpu_cache_usage_perc` | % du KV cache GPU utilisé |
| `vllm:num_requests_running` | Requêtes en cours |
| `vllm:prompt_tokens_total` | Tokens prompt cumulés |
| `vllm:generation_tokens_total` | Tokens générés cumulés |
| `vllm:time_to_first_token_seconds` | Latence prefill (TTFT) |
| `vllm:time_per_output_token_seconds` | Latence decode par token (TPOT) |
| `vllm:e2e_request_latency_seconds` | Latence totale par requête |
| `vllm:request_prompt_tokens` | Tokens prompt par requête |
| `vllm:request_generation_tokens` | Tokens générés par requête |

### Métriques GPU via nvidia-smi (à scraper séparément)

```bash
nvidia-smi --query-gpu=utilization.gpu,utilization.memory,memory.used,memory.free,power.draw,temperature.gpu --format=csv,noheader,nounits
```

Exemple de sortie :
```
45, 62, 28450, 53109, 187.3, 52
```

Colonnes : `gpu_util%`, `mem_util%`, `mem_used_MB`, `mem_free_MB`, `power_W`, `temp_C`

---

## Ce qu'on veut capturer par run

### Champs à ajouter dans `BackendResult` en v0.3.1

```python
# Temps de prefill (time to first token)
prefill_ms: float | None = None

# Temps de decode total
decode_ms: float | None = None

# Puissance GPU moyenne pendant le run (watts)
gpu_power_w: float | None = None

# Mémoire GPU utilisée au moment du run (MB)
gpu_memory_used_mb: float | None = None

# Utilisation GPU % pendant le run
gpu_util_pct: float | None = None

# Température GPU (°C)
gpu_temp_c: float | None = None
```

### Champs à ajouter dans `RunRecord` en v0.3.1

```python
prefill_ms: float | None = None
decode_ms: float | None = None
gpu_power_w: float | None = None
gpu_memory_used_mb: float | None = None
```

---

## Comment collecter ces métriques

### Option A — Polling `/metrics` avant/après chaque requête

```python
import urllib.request, re

def scrape_vllm_metric(base_url: str, metric_name: str) -> float | None:
    with urllib.request.urlopen(f"{base_url}/metrics") as r:
        for line in r.read().decode().splitlines():
            if line.startswith(metric_name) and not line.startswith("#"):
                return float(line.split()[-1])
    return None

# Avant le run
ttft_before = scrape_vllm_metric(base_url, "vllm:time_to_first_token_seconds_sum")

# Après le run
ttft_after = scrape_vllm_metric(base_url, "vllm:time_to_first_token_seconds_sum")
prefill_ms = (ttft_after - ttft_before) * 1000
```

### Option B — nvidia-smi via SSH pendant le run

```bash
# Sur le serveur, pendant l'inférence :
nvidia-smi --query-gpu=power.draw,memory.used,utilization.gpu,temperature.gpu \
  --format=csv,noheader,nounits -l 1
```

### Option C — Lire les champs `usage` enrichis dans la réponse vLLM

vLLM récent expose parfois `prompt_tokens_details` avec prefill/decode séparés dans le champ `usage`. À vérifier sur la version installée (0.17.1).

```python
usage = data.get("usage", {})
details = usage.get("prompt_tokens_details", {})
prefill_ms = details.get("prefill_time_ms")
```

---

## Plan d'implémentation v0.3.1

### T9 — GPU metrics dans BackendResult et RunRecord

**Fichiers à modifier :**
- `ego_metrology/backends/base.py` — ajouter champs GPU dans `BackendResult`
- `ego_metrology/backends/openai_compat.py` — scraper `/metrics` avant/après chaque call
- `ego_metrology/logging_schema.py` — ajouter `prefill_ms`, `decode_ms`, `gpu_power_w`, `gpu_memory_used_mb` dans `RunRecord`
- `ego_metrology/cost.py` — préparer `cost_dyn` v2 avec `prefill_ms + decode_ms + gpu_power_w`
- `docs/cost_dyn_v2_spec.md` — spec de la formule v2

**Critère de sortie :** chaque `RunRecord` produit sur Qwen contient les métriques GPU réelles.

### Formule `cost_dyn` v2 cible

```
cost_dyn_v2 = w_tokens * total_tokens
            + w_prefill * prefill_ms
            + w_decode * decode_ms
            + w_power * gpu_power_w * latency_total_s
```

Où `w_power * gpu_power_w * latency_total_s` ≈ énergie consommée en joules (proxy).

---

## Commande de test immédiat sur le serveur actif

```bash
# Depuis le Mac, serveur allumé :
curl -s http://51.159.139.27:8000/metrics | grep -E "time_to_first|time_per_output|e2e_request|gpu_cache" | grep -v "^#"

# GPU direct depuis le serveur SSH :
nvidia-smi --query-gpu=power.draw,memory.used,utilization.gpu,temperature.gpu \
  --format=csv,noheader,nounits
```

---

## Rappel — ne pas oublier

- [ ] T9 : ajouter métriques GPU dans `BackendResult` + `RunRecord`
- [ ] Tester `/metrics` endpoint vLLM sur le serveur actif
- [ ] Définir formule `cost_dyn` v2 avec composante énergie
- [ ] Mettre à jour `oracle.py` pour utiliser `cost_dyn_v2` si disponible
- [ ] Bumper version à `0.3.1` quand T9 est fait
