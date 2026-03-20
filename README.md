<!-- =========================
file: README.md
========================= -->

# 🔍 HYPERFOCUS

Tu es TDAH : donc on fait simple.
Tu laisses `~/Downloads` en chaos, et le système observe + te montre les écarts.

## Deux modes

### Mode SAFE (défaut) — ZERO CONTENT EXFIL
- Aucun contenu ne quitte ton Mac
- Pas d’appel LLM
- Filtrage local uniquement

### Mode ENRICHED (avec `--llm`) — EXFIL CONTRÔLÉE
- Extrait max 2000 chars pour fichiers pertinents uniquement
- Jamais sur PDF
- Jamais sur fichiers ignorés (factures/relevés/etc.)
- Nécessite `DEEPSEEK_API_KEY`

## URLs
- Dashboard: `http://<IP_VM_SCALEWAY>:3000/dashboard`
- Health: `http://<IP_VM_SCALEWAY>:3000/health`

## Commandes (Mac)
- SAFE: `python3 watcher.py start --cloud http://<IP_VM>:3000`
- ENRICHED: `python3 watcher.py start --cloud http://<IP_VM>:3000 --llm`
