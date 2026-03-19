"""
analyze_extract_then_check.py
==============================
Analyse finale : qwen_single_pass vs qwen_extract_then_check
Corpus : family_a_fixed_v2.json (invariant validé)
Input  : runs/family_a_qwen_extract_then_check_v2.jsonl
Output : reports/calibration_final_summary.json
         reports/calibration_final_summary.md
"""
import json, os, statistics
from collections import defaultdict

INPUT  = "runs/family_a_qwen_extract_then_check_v2.jsonl"
OUT_J  = "reports/calibration_final_summary.json"
OUT_MD = "reports/calibration_final_summary.md"
POLICIES = ["qwen_single_pass", "qwen_extract_then_check"]
LEVELS   = [1,2,3,4,5,6,7]

def load():
    rows = []
    with open(INPUT) as f:
        for line in f: rows.append(json.loads(line))
    return rows

def summarize(runs):
    if not runs: return {}
    n = len(runs)
    correct   = sum(1 for r in runs if r["is_correct"])
    wc        = sum(1 for r in runs if r.get("result")=="wrong_condition")
    missed    = sum(1 for r in runs if r.get("result")=="missed")
    costs     = [r["total_tokens"] for r in runs]
    correct_costs = [r["total_tokens"] for r in runs if r["is_correct"]]
    return {
        "n": n,
        "accuracy":           round(correct/n, 3),
        "wrong_condition_rate": round(wc/n, 3),
        "missed_rate":        round(missed/n, 3),
        "mean_cost_tokens":   round(statistics.mean(costs), 1),
        "mean_cost_correct":  round(statistics.mean(correct_costs), 1) if correct_costs else None,
    }

def run():
    rows = load()
    idx  = defaultdict(lambda: defaultdict(list))
    for r in rows:
        idx[r["policy_id"]][r["level"]].append(r)

    global_s = {pid: summarize([r for r in rows if r["policy_id"]==pid]) for pid in POLICIES}
    per_lv   = {pid: {lv: summarize(idx[pid][lv]) for lv in LEVELS} for pid in POLICIES}

    # Gain absolu
    sp_acc  = global_s["qwen_single_pass"]["accuracy"]
    etc_acc = global_s["qwen_extract_then_check"]["accuracy"]
    gain    = round(etc_acc - sp_acc, 3)
    sp_cost  = global_s["qwen_single_pass"]["mean_cost_tokens"]
    etc_cost = global_s["qwen_extract_then_check"]["mean_cost_tokens"]
    cost_delta = round(etc_cost - sp_cost, 1)

    summary = {"global": global_s, "per_level": per_lv,
               "gain_accuracy": gain, "cost_delta_tokens": cost_delta}

    os.makedirs("reports", exist_ok=True)
    with open(OUT_J,"w") as f: json.dump(summary, f, indent=2)

    # Markdown
    lines = [
        "# EGO Metrology — Rapport final calibration v4",
        "",
        "**Date** : 2026-03-19  ",
        "**Modèle** : Qwen/Qwen2.5-14B-Instruct  ",
        "**Corpus** : `data/family_a_fixed_v2.json` — 210 items, invariant validé  ",
        "**Famille** : A — count+bind (cross-section binding)  ",
        "",
        "## Résultats globaux",
        "",
        "| Politique | Accuracy | Wrong condition | Missed | Coût moyen | Coût/item correct |",
        "|-----------|----------|-----------------|--------|------------|-------------------|",
    ]
    for pid in POLICIES:
        s = global_s[pid]
        lines.append(
            f"| {pid} | {s['accuracy']:.0%} | {s['wrong_condition_rate']:.0%} "
            f"| {s['missed_rate']:.0%} | {s['mean_cost_tokens']} | {s['mean_cost_correct'] or '—'} |"
        )

    lines += [
        "",
        f"**Gain accuracy** : `extract_then_check` vs `single_pass` = **{gain:+.0%}**  ",
        f"**Surcoût moyen** : {cost_delta:+.1f} tokens/item  ",
        "",
        "## Accuracy par niveau",
        "",
        "| Niveau | Bruit | single_pass | extract_then_check |",
        "|--------|-------|-------------|-------------------|",
    ]
    noise_map = {1:0,2:3,3:8,4:18,5:40,6:80,7:140}
    for lv in LEVELS:
        sp  = per_lv["qwen_single_pass"][lv]
        etc = per_lv["qwen_extract_then_check"][lv]
        lines.append(f"| L{lv} | {noise_map[lv]} | {sp.get('accuracy',0):.0%} | {etc.get('accuracy',0):.0%} |")

    lines += [
        "",
        "## Conclusions",
        "",
        "- **Mode d'échec principal** : `wrong_condition` — le modèle choisit un distracteur plausible, pas un problème de format.",
        "- **Politique retenue** : `qwen_extract_then_check` — décomposition structurée + check programmatique.",
        "- **Baseline** : `qwen_single_pass`.",
        "",
        "## Décisions de calibration",
        "",
        "| Élément | Décision |",
        "|---------|----------|",
        "| Contrôle positif | Claude Haiku — 100% L1 toutes familles |",
        "| Modèle intermédiaire | **Qwen2.5-14B-Instruct** |",
        "| Mistral-7B | ❌ trop faible, plancher sur A |",
        "| DeepSeek-coder-6.7B | ❌ bascule mode code, instable |",
        "| Famille retenue | **Family A** — seule famille avec gradient utile |",
        "| Famille B | ⚠ non calibrante — plafond Haiku, instable DeepSeek |",
        "| Famille C | ⚠ non calibrante — plafond Qwen |",
        "| a_secteur / beta_secteur | Non calibrés — signal insuffisant pour fit fiable |",
        "| Corpus | `family_a_fixed_v2.json` — invariant Vega=2 vérifié |",
        "",
        "## Phase suivante",
        "",
        "Intégration de `qwen_extract_then_check` comme politique candidate dans `ego-metrology`.  ",
        "Déploiement FastAPI v0.3 sur Scaleway.  ",
        "ACP comme orchestrateur en phase ultérieure.",
    ]

    with open(OUT_MD,"w") as f: f.write("\n".join(lines))

    # Print
    print("\n" + "="*60)
    print("RÉSULTATS FINAUX")
    print("="*60)
    print(f"{'Politique':<30} {'Accuracy':>8} {'WrongCond':>10} {'Coût':>8}")
    print("-"*60)
    for pid in POLICIES:
        s = global_s[pid]
        print(f"{pid:<30} {s['accuracy']:>8.0%} {s['wrong_condition_rate']:>10.0%} {s['mean_cost_tokens']:>8.1f}")
    print(f"\nGain accuracy  : {gain:+.0%}")
    print(f"Surcoût moyen  : {cost_delta:+.1f} tokens/item")
    print(f"\n→ {OUT_J}")
    print(f"→ {OUT_MD}")

if __name__ == "__main__":
    run()
