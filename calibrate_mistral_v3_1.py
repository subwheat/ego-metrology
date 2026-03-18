"""
Calibration EGO v3.1 — Competitive Retrieval (patch)
=====================================================
Corrections vs v3 :
- 4 faux secrets "blue protocol" (vrais compétiteurs)
- secrets dispersés dans le document (pas groupés)
- fit sans forçage de signe
- prompt_tokens réel mesuré par run
"""

import json, math, os, random, urllib.request

VASTAI_URL  = os.environ.get("OPENAI_BASE_URL", "http://74.48.78.46:24810/v1")
MODEL       = "mistralai/Mistral-7B-Instruct-v0.2"
MAX_TOKENS  = 50
TEMPERATURE = 0.0
RUNS        = 5

# ── Secrets ───────────────────────────────────────────────────────────────────
# 4 faux "blue protocol" + 4 autres protocoles

TRUE_SECRET  = ("blue", "ZETA-7749-BLUE")
DECOYS = [
    ("blue",  "ZETA-7748-BLUE"),    # faux blue 1
    ("blue",  "ZETA-7750-BLUE"),    # faux blue 2
    ("blue",  "THETA-7749-BLUE"),   # faux blue 3
    ("blue",  "ZETA-7749-BLUES"),   # faux blue 4
    ("green", "ZETA-7749-GREEN"),
    ("red",   "ZETA-7749-RED"),
    ("alpha", "ZETA-7749-GLUE"),
    ("omega", "BETA-7749-BLUE"),
]

QUESTION = "What is the activation code for the blue protocol? There is only one correct answer."
EXPECTED = "ZETA-7749-BLUE"

# ── Padding ───────────────────────────────────────────────────────────────────

FILLER = [
    "The committee reviewed the annual report and approved the budget for next year.",
    "Scientists discovered a new species of deep-sea fish near the Pacific trench.",
    "Engineers completed the bridge renovation ahead of schedule and under budget.",
    "The university announced new scholarship programs for international students.",
    "Local authorities issued safety guidelines following the recent incident.",
    "Researchers published findings on renewable energy efficiency improvements.",
    "The stock market showed mixed results after the central bank announcement.",
    "A new transportation line will connect the city center to the airport.",
    "The museum opened an exhibition featuring artifacts from ancient civilizations.",
    "Officials confirmed the infrastructure project will begin next quarter.",
    "The regional council approved funding for three new public hospitals.",
    "A team of geologists identified rare mineral deposits in the eastern mountains.",
]

def make_padding_chunk(target_words: int) -> str:
    sentences, count = [], 0
    while count < target_words:
        s = random.choice(FILLER)
        sentences.append(s)
        count += len(s.split())
    return " ".join(sentences)

def make_secret_line(protocol: str, code: str) -> str:
    return f"Activation code for the {protocol} protocol: {code}."

def make_context(padding_words: int, true_secret_position: str) -> tuple[str, int]:
    """
    Disperse les 9 secrets dans le document.
    Le vrai secret est placé en start/middle/end.
    Retourne (context_str, prompt_tokens_approx).
    """
    all_secrets = DECOYS[:]
    random.shuffle(all_secrets)

    # Segments de padding entre les secrets
    n_secrets    = len(all_secrets) + 1  # +1 pour le vrai
    chunk_words  = max(padding_words // (n_secrets + 1), 10)

    # On construit le document comme une liste de segments
    segments = []
    for s in all_secrets:
        segments.append(("padding", make_padding_chunk(chunk_words)))
        segments.append(("secret",  make_secret_line(*s)))

    # On insère le vrai secret selon la position demandée
    true_line = make_secret_line(*TRUE_SECRET)
    if true_secret_position == "start":
        segments.insert(0, ("secret", true_line))
    elif true_secret_position == "end":
        segments.append(("padding", make_padding_chunk(chunk_words)))
        segments.append(("secret",  true_line))
    else:  # middle
        mid = len(segments) // 2
        segments.insert(mid, ("secret", true_line))

    # Padding final
    segments.append(("padding", make_padding_chunk(chunk_words)))

    context = "\n".join(s[1] for s in segments)
    tokens  = int(len(context.split()) * 1.3)
    return context, tokens

# ── API ───────────────────────────────────────────────────────────────────────

def chat(context: str) -> tuple[str, int]:
    prompt = (
        f"Read the document below carefully.\n\n"
        f"DOCUMENT:\n{context}\n\n"
        f"QUESTION: {QUESTION}\n\n"
        f"Reply with only the exact activation code, nothing else."
    )
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": MAX_TOKENS,
        "temperature": TEMPERATURE,
    }
    req = urllib.request.Request(
        VASTAI_URL + "/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Authorization": "Bearer local"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        data  = json.loads(r.read().decode())
        reply = data["choices"][0]["message"]["content"].strip()
        pt    = int(len(prompt.split()) * 1.3)
        return reply, pt

def classify(answer: str) -> str:
    a = answer.upper()
    if EXPECTED in a:
        return "exact_match"
    for _, code in DECOYS:
        if code.upper() in a:
            return "picked_decoy"
    return "missed"

# ── Niveaux ───────────────────────────────────────────────────────────────────

LEVELS    = [100, 300, 700, 1500, 3000, 5000]
POSITIONS = ["start", "middle", "end"]

def main():
    random.seed(42)
    print("═" * 65)
    print("  EGO METROLOGY — Calibration v3.1 — Competitive Retrieval")
    print(f"  URL    : {VASTAI_URL}")
    print(f"  Target : {EXPECTED}  |  Blue decoys : 4  |  Other : 4")
    print("═" * 65)

    results = []

    for pw in LEVELS:
        level_outcomes = []
        level_tokens   = []

        print(f"\n▶ Padding ~{pw} mots")

        for pos in POSITIONS:
            for run in range(RUNS):
                context, pt = make_context(pw, pos)
                level_tokens.append(pt)
                try:
                    answer  = chat(context)[0]
                    outcome = classify(answer)
                    level_outcomes.append(outcome)
                    icon = "✓" if outcome == "exact_match" else ("⚠" if outcome == "picked_decoy" else "✗")
                    print(f"  [{pos:6}] run {run+1} {icon} {outcome:<15} → {answer[:45]}")
                except Exception as e:
                    print(f"  [{pos:6}] run {run+1} [ERREUR] {e}")
                    level_outcomes.append("error")

        total   = len(level_outcomes)
        exact   = level_outcomes.count("exact_match")
        decoy   = level_outcomes.count("picked_decoy")
        missed  = level_outcomes.count("missed")
        success = exact / max(total, 1)
        avg_pt  = int(sum(level_tokens) / max(len(level_tokens), 1))
        alpha_s = min((avg_pt / 8192) ** 1.5, 1.0)
        c_dyn   = avg_pt * 0.3 * (1 + alpha_s)

        print(f"  → exact={exact}/{total} ({success*100:.0f}%) | decoy={decoy} | missed={missed}")
        print(f"  → avg_prompt_tokens={avg_pt} | C_dyn={c_dyn:.0f}")

        results.append({
            "padding_words":      pw,
            "avg_prompt_tokens":  avg_pt,
            "c_dyn":              round(c_dyn, 1),
            "success_rate":       round(success, 3),
            "exact":              exact,
            "decoy":              decoy,
            "missed":             missed,
            "total":              total,
        })

    # ── Fit ───────────────────────────────────────────────────────────────────
    print("\n" + "═" * 65)
    print("  FIT EGO — log τ = a - β · C_dyn")
    print("═" * 65)

    xs, ys = [], []
    for r in results:
        p_fail  = max(1.0 - r["success_rate"], 0.01)
        log_tau = math.log(1.0 / p_fail)
        xs.append(r["c_dyn"])
        ys.append(log_tau)
        print(f"  C_dyn={r['c_dyn']:>8.0f} | success={r['success_rate']*100:.0f}% | log_tau={log_tau:.3f}")

    n   = len(xs)
    mx, my = sum(xs)/n, sum(ys)/n
    num  = sum((xs[i]-mx)*(ys[i]-my) for i in range(n))
    den  = sum((xs[i]-mx)**2 for i in range(n))
    slope     = num / den if den != 0 else 0
    intercept = my - slope * mx

    print(f"\n  slope     (raw) = {slope:.6f}")
    print(f"  intercept (raw) = {intercept:.4f}")

    if slope < 0:
        print(f"\n  ✓ Décroissance EGO confirmée")
        print(f"  a_secteur    = {intercept:.4f}")
        print(f"  beta_secteur = {-slope:.6f}")
    else:
        print(f"\n  ⚠ Pas de décroissance observée — tâche encore trop facile ou hors régime EGO")
        print(f"  Ne pas utiliser ces constantes pour calibration.")

    out = {
        "model":    MODEL,
        "protocol": "competitive_retrieval_v3_1",
        "slope":    round(slope, 8),
        "intercept": round(intercept, 4),
        "data":     results,
    }
    if slope < 0:
        out["a_secteur"]    = round(intercept, 4)
        out["beta_secteur"] = round(-slope, 6)

    path = os.path.expanduser("~/ego-metrology/calibration_v3_1_results.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\n  Sauvegardé : {path}")

if __name__ == "__main__":
    main()
