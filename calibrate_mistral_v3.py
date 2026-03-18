"""
Calibration EGO v3 — Competitive Retrieval
==========================================
Protocole :
- 1 vrai secret + 8 faux secrets au même format
- 3 positions possibles (début, milieu, fin)
- 5 runs par niveau
- 6 niveaux de longueur de contexte
- Scoring : exact_match / picked_decoy / missed
"""

import json, math, os, random, urllib.request

VASTAI_URL  = os.environ.get("OPENAI_BASE_URL", "http://74.48.78.46:24810/v1")
MODEL       = "mistralai/Mistral-7B-Instruct-v0.2"
MAX_TOKENS  = 50
TEMPERATURE = 0.0
RUNS        = 5

# ── Secrets ───────────────────────────────────────────────────────────────────

TRUE_SECRET = ("blue",   "ZETA-7749-BLUE")
DECOYS = [
    ("green",    "ZETA-7749-GREEN"),
    ("red",      "ZETA-7749-RED"),
    ("alpha",    "ZETA-7748-BLUE"),
    ("omega",    "THETA-7749-BLUE"),
    ("delta",    "ZETA-7749-GLUE"),
    ("gamma",    "ZETA-7750-BLUE"),
    ("epsilon",  "ZETA-7749-BLUES"),
    ("sigma",    "BETA-7749-BLUE"),
]

QUESTION = "What is the activation code for the blue protocol?"
EXPECTED = "ZETA-7749-BLUE"

# ── Padding neutre ────────────────────────────────────────────────────────────

FILLER = [
    "The committee reviewed the annual report and approved the budget.",
    "Scientists discovered a new species of deep-sea fish near the Pacific.",
    "Engineers completed the bridge renovation ahead of schedule.",
    "The university announced new scholarship programs for students.",
    "Local authorities issued safety guidelines following the incident.",
    "Researchers published findings on renewable energy improvements.",
    "The stock market showed mixed results after the central bank meeting.",
    "A new transportation line will connect the city center to the airport.",
    "The museum opened an exhibition featuring artifacts from ancient times.",
    "Officials confirmed the infrastructure project will begin next quarter.",
]

def make_padding(target_words: int) -> str:
    sentences, count = [], 0
    while count < target_words:
        s = random.choice(FILLER)
        sentences.append(s)
        count += len(s.split())
    return " ".join(sentences)

def make_secret_block(protocol: str, code: str) -> str:
    return f"Activation code for the {protocol} protocol: {code}."

def make_context(padding_words: int, position: str) -> str:
    """
    Construit le contexte avec :
    - 1 vrai secret
    - 8 faux secrets mélangés dans le padding
    - position du vrai secret : 'start', 'middle', 'end'
    """
    # Blocs de secrets (vrai + faux, mélangés)
    all_secrets = [TRUE_SECRET] + DECOYS
    random.shuffle(all_secrets)
    secret_blocks = "\n".join(make_secret_block(p, c) for p, c in all_secrets)

    third = padding_words // 3
    pad1 = make_padding(third)
    pad2 = make_padding(third)
    pad3 = make_padding(third)

    if position == "start":
        return f"{secret_blocks}\n\n{pad1}\n\n{pad2}\n\n{pad3}"
    elif position == "end":
        return f"{pad1}\n\n{pad2}\n\n{pad3}\n\n{secret_blocks}"
    else:  # middle
        return f"{pad1}\n\n{secret_blocks}\n\n{pad2}\n\n{pad3}"

# ── API ───────────────────────────────────────────────────────────────────────

def chat(context: str) -> str:
    prompt = f"""Read the document below carefully and answer the question.

DOCUMENT:
{context}

QUESTION: {QUESTION}

Reply with only the exact activation code, nothing else."""

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
        return json.loads(r.read().decode())["choices"][0]["message"]["content"].strip()

# ── Scoring ───────────────────────────────────────────────────────────────────

def classify(answer: str) -> str:
    a = answer.upper()
    if EXPECTED in a:
        return "exact_match"
    for _, code in DECOYS:
        if code in a:
            return "picked_decoy"
    return "missed"

# ── Niveaux ───────────────────────────────────────────────────────────────────

LEVELS = [
    {"padding_words": 100},
    {"padding_words": 300},
    {"padding_words": 700},
    {"padding_words": 1500},
    {"padding_words": 3000},
    {"padding_words": 5000},
]
POSITIONS = ["start", "middle", "end"]

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    random.seed(42)
    print("═" * 65)
    print("  EGO METROLOGY — Calibration v3 — Competitive Retrieval")
    print(f"  URL    : {VASTAI_URL}")
    print(f"  Target : {EXPECTED}  |  Decoys : {len(DECOYS)}")
    print("═" * 65)

    results = []

    for level in LEVELS:
        pw = level["padding_words"]
        level_scores = []

        print(f"\n▶ Padding ~{pw} mots")

        for pos in POSITIONS:
            pos_scores = []
            for run in range(RUNS):
                context = make_context(pw, pos)
                pt = int(len(context.split()) * 1.3)

                try:
                    answer  = chat(context)
                    outcome = classify(answer)
                    pos_scores.append(outcome)
                    icon = "✓" if outcome == "exact_match" else ("⚠" if outcome == "picked_decoy" else "✗")
                    print(f"  [{pos:6}] run {run+1} {icon} {outcome:<15} → {answer[:40]}")
                except Exception as e:
                    print(f"  [{pos:6}] run {run+1} [ERREUR] {e}")
                    pos_scores.append("error")

            level_scores.extend(pos_scores)

        total   = len(level_scores)
        exact   = level_scores.count("exact_match")
        decoy   = level_scores.count("picked_decoy")
        missed  = level_scores.count("missed")
        success = exact / total

        # C_dyn estimé sur prompt moyen
        pt_est  = int((pw + 50) * 1.3)
        alpha_s = min((pt_est / 8192) ** 1.5, 1.0)
        c_dyn   = pt_est * 0.3 * (1 + alpha_s)

        print(f"  → exact={exact}/{total} ({success*100:.0f}%) | decoy={decoy} | missed={missed}")
        print(f"  → C_dyn ≈ {c_dyn:.0f}")

        results.append({
            "padding_words": pw,
            "prompt_tokens": pt_est,
            "c_dyn":         round(c_dyn, 1),
            "success_rate":  round(success, 3),
            "exact":         exact,
            "decoy":         decoy,
            "missed":        missed,
            "total":         total,
        })

    # ── Fit ───────────────────────────────────────────────────────────────────
    print("\n" + "═" * 65)
    print("  FIT EGO")
    print("═" * 65)

    xs, ys = [], []
    for r in results:
        p_fail = max(1.0 - r["success_rate"], 0.01)
        log_tau = math.log(1.0 / p_fail)
        xs.append(r["c_dyn"])
        ys.append(log_tau)
        print(f"  C_dyn={r['c_dyn']:>8.0f} | success={r['success_rate']*100:.0f}% | log_tau={log_tau:.3f}")

    n  = len(xs)
    mx, my = sum(xs)/n, sum(ys)/n
    num  = sum((xs[i]-mx)*(ys[i]-my) for i in range(n))
    den  = sum((xs[i]-mx)**2 for i in range(n))
    beta_raw = num / den if den != 0 else 0
    a    = my - beta_raw * mx
    beta = abs(beta_raw)

    print(f"\n  a_secteur    = {a:.4f}")
    print(f"  beta_secteur = {beta:.6f}")

    out = {
        "model": MODEL, "protocol": "competitive_retrieval_v3",
        "a_secteur": round(a, 4), "beta_secteur": round(beta, 6),
        "data": results,
    }
    path = os.path.expanduser("~/ego-metrology/calibration_v3_results.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\n  Sauvegardé : {path}")

if __name__ == "__main__":
    main()
