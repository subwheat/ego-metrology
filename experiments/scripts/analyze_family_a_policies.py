"""
analyze_family_a_policies.py
=============================
Lit runs/family_a_qwen_policy_eval_v1.jsonl
Produit reports/family_a_qwen_policy_eval_v1_summary.json + .md
"""
import json, os, statistics
from collections import defaultdict

INPUT  = "runs/family_a_qwen_policy_eval_v1.jsonl"
OUT_J  = "reports/family_a_qwen_policy_eval_v1_summary.json"
OUT_MD = "reports/family_a_qwen_policy_eval_v1_summary.md"

POLICIES = ["fixed_cap_4","fixed_cap_8","fixed_cap_16","ego_controller_stub"]
LEVELS   = [1,2,3,4,5,6,7]

def load():
    rows = []
    with open(INPUT) as f:
        for line in f:
            rows.append(json.loads(line))
    return rows

def stats_by_policy_level(rows):
    # index : policy → level → [rows]
    idx = defaultdict(lambda: defaultdict(list))
    for r in rows:
        idx[r["policy_id"]][r["level"]].append(r)
    return idx

def summarize_policy(runs):
    n = len(runs)
    if n == 0: return {}
    correct   = sum(1 for r in runs if r["is_correct"])
    truncated = sum(1 for r in runs if r.get("truncated"))
    costs     = [r["cost_tokens"] for r in runs]
    compl     = [r["completion_tokens"] for r in runs]
    return {
        "n": n,
        "accuracy":          round(correct/n, 3),
        "truncation_rate":   round(truncated/n, 3),
        "mean_cost_tokens":  round(statistics.mean(costs), 1),
        "median_cost_tokens":round(statistics.median(costs), 1),
        "mean_completion_tokens": round(statistics.mean(compl), 2),
    }

def oracle_best_fixed(rows_by_item):
    """
    Pour chaque item, parmi fixed_cap_4/8/16 :
    prendre le moins coûteux qui réussit.
    Retourne le coût moyen de cet oracle.
    """
    fixed_pols = ["fixed_cap_4","fixed_cap_8","fixed_cap_16"]
    oracle_costs = []
    for item_id, pol_runs in rows_by_item.items():
        candidates = []
        for pid in fixed_pols:
            r = pol_runs.get(pid)
            if r and r["is_correct"]:
                candidates.append(r["cost_tokens"])
        if candidates:
            oracle_costs.append(min(candidates))
    if not oracle_costs:
        return None
    return round(statistics.mean(oracle_costs), 1)

def run():
    rows = load()
    idx = stats_by_policy_level(rows)

    # Index par item_id × policy_id
    by_item = defaultdict(dict)
    for r in rows:
        by_item[r["item_id"]][r["policy_id"]] = r

    os.makedirs("reports", exist_ok=True)

    # --- Global summary ---
    global_summary = {}
    for pid in POLICIES:
        all_runs = [r for r in rows if r["policy_id"]==pid]
        global_summary[pid] = summarize_policy(all_runs)

    # --- Per-level summary ---
    per_level = {}
    for pid in POLICIES:
        per_level[pid] = {}
        for lv in LEVELS:
            runs = idx[pid][lv]
            per_level[pid][lv] = summarize_policy(runs)

    # --- Oracle ---
    oracle_cost = oracle_best_fixed(by_item)

    # --- Regret ego vs oracle ---
    ego_runs = [r for r in rows if r["policy_id"]=="ego_controller_stub"]
    ego_correct = [r for r in ego_runs if r["is_correct"]]
    ego_mean_cost = statistics.mean(r["cost_tokens"] for r in ego_runs) if ego_runs else None
    regret = round(ego_mean_cost - oracle_cost, 1) if (ego_mean_cost and oracle_cost) else None

    summary = {
        "global":      global_summary,
        "per_level":   per_level,
        "oracle_best_fixed_cost": oracle_cost,
        "ego_mean_cost":          round(ego_mean_cost,1) if ego_mean_cost else None,
        "ego_regret_vs_oracle":   regret,
    }

    with open(OUT_J,"w") as f:
        json.dump(summary, f, indent=2)

    # --- Markdown report ---
    lines = ["# Family A — Policy Evaluation Report", "",
             f"**Modèle** : Qwen/Qwen2.5-14B-Instruct  ",
             f"**Items** : 210 (30/niveau × 7 niveaux)  ",
             f"**Politiques** : {', '.join(POLICIES)}", "",
             "## Résultats globaux", "",
             "| Politique | Accuracy | Troncature | Coût moyen (tokens) | Completion moyen |",
             "|-----------|----------|------------|---------------------|-----------------|"]
    for pid in POLICIES:
        s = global_summary[pid]
        lines.append(f"| {pid} | {s['accuracy']:.0%} | {s['truncation_rate']:.0%} | {s['mean_cost_tokens']} | {s['mean_completion_tokens']} |")

    lines += ["", "## Accuracy par niveau", ""]
    header = "| Niveau |" + "".join(f" {p} |" for p in POLICIES)
    sep    = "|--------|" + "".join("-----------|" for _ in POLICIES)
    lines += [header, sep]
    for lv in LEVELS:
        row = f"| L{lv}     |"
        for pid in POLICIES:
            s = per_level[pid].get(lv,{})
            acc = f"{s.get('accuracy',0):.0%}" if s else "—"
            row += f" {acc}       |"
        lines.append(row)

    lines += ["", "## Coût moyen par niveau (tokens)", ""]
    lines += [header, sep]
    for lv in LEVELS:
        row = f"| L{lv}     |"
        for pid in POLICIES:
            s = per_level[pid].get(lv,{})
            cost = str(round(s.get('mean_cost_tokens',0))) if s else "—"
            row += f" {cost}         |"
        lines.append(row)

    lines += ["",
              "## Analyse oracle & regret", "",
              f"**Oracle** (meilleur cap fixe réussi, coût min) : {oracle_cost} tokens/item en moyenne",
              f"**Ego controller** coût moyen : {round(ego_mean_cost,1) if ego_mean_cost else '—'} tokens/item",
              f"**Regret ego vs oracle** : {regret:+.1f} tokens/item" if regret is not None else "**Regret** : N/A",
              "",
              "## Interprétation", "",
    ]

    # Auto-interprétation
    ego_acc  = global_summary["ego_controller_stub"]["accuracy"]
    cap16_acc = global_summary["fixed_cap_16"]["accuracy"]
    cap16_cost = global_summary["fixed_cap_16"]["mean_cost_tokens"]
    ego_cost_val = global_summary["ego_controller_stub"]["mean_cost_tokens"]

    if ego_acc >= cap16_acc - 0.05 and ego_cost_val < cap16_cost:
        verdict = "✓ **Le controller ego bat fixed_cap_16** : accuracy comparable, coût inférieur."
    elif ego_acc >= cap16_acc - 0.05:
        verdict = "~ **Le controller ego est équivalent à fixed_cap_16** en accuracy, coût similaire."
    else:
        verdict = "✗ **Le controller ego sous-performe fixed_cap_16** en accuracy."
    lines.append(verdict)

    lines += ["",
              f"- fixed_cap_4  : accuracy={global_summary['fixed_cap_4']['accuracy']:.0%}, troncature={global_summary['fixed_cap_4']['truncation_rate']:.0%}",
              f"- fixed_cap_8  : accuracy={global_summary['fixed_cap_8']['accuracy']:.0%}, troncature={global_summary['fixed_cap_8']['truncation_rate']:.0%}",
              f"- fixed_cap_16 : accuracy={global_summary['fixed_cap_16']['accuracy']:.0%}, troncature={global_summary['fixed_cap_16']['truncation_rate']:.0%}",
              f"- ego_stub     : accuracy={global_summary['ego_controller_stub']['accuracy']:.0%}, troncature={global_summary['ego_controller_stub']['truncation_rate']:.0%}",
    ]

    with open(OUT_MD,"w") as f:
        f.write("\n".join(lines))

    # --- Print ---
    print("\n" + "="*60)
    print("RÉSULTATS GLOBAUX")
    print("="*60)
    print(f"{'Politique':<25} {'Accuracy':>8} {'Troncature':>11} {'Coût moy':>10} {'Compl moy':>10}")
    print("-"*65)
    for pid in POLICIES:
        s = global_summary[pid]
        print(f"{pid:<25} {s['accuracy']:>8.0%} {s['truncation_rate']:>11.0%} {s['mean_cost_tokens']:>10.1f} {s['mean_completion_tokens']:>10.2f}")

    print(f"\nOracle (best fixed cap) : {oracle_cost} tokens/item")
    print(f"Ego controller          : {round(ego_mean_cost,1)} tokens/item")
    print(f"Regret ego vs oracle    : {regret:+.1f} tokens/item" if regret else "Regret : N/A")
    print(f"\n{verdict}")
    print(f"\n→ {OUT_J}")
    print(f"→ {OUT_MD}")

if __name__ == "__main__":
    run()
