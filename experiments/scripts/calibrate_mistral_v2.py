"""
Calibration EGO v2 — Protocole propre
======================================
Principe :
- Tâche FIXE : retrouver une information cachée dans un contexte
- Variable manipulée : taille du padding parasite autour de l'info
- Mesure : succès/échec de récupération (binaire)
- max_tokens élevé pour ne pas censurer
- 5 runs par niveau de contexte pour stabiliser

Loi EGO testée : log τ = a_secteur - β_secteur · C_dyn
"""

import json
import math
import os
import random
import urllib.request

VASTAI_URL = os.environ.get("OPENAI_BASE_URL", "http://74.48.78.46:24810/v1")
MODEL      = "mistralai/Mistral-7B-Instruct-v0.2"
MAX_TOKENS = 200   # réponse courte attendue
TEMPERATURE = 0.0  # déterministe
RUNS_PER_LEVEL = 5

# ── La cible cachée ───────────────────────────────────────────────────────────
# On cache toujours la même info dans le contexte.
# Le modèle doit la retrouver malgré le bruit autour.

SECRET = "The activation code is ZETA-7749-BLUE."
QUESTION = "What is the activation code mentioned in the document?"
EXPECTED = "ZETA-7749-BLUE"

# ── Padding parasite (texte neutre mais long) ─────────────────────────────────

FILLER_SENTENCES = [
    "The committee reviewed the annual report and approved the budget for next year.",
    "Scientists have discovered a new species of deep-sea fish near the Pacific trench.",
    "The weather forecast predicts heavy rainfall across the northern regions this weekend.",
    "Engineers completed the bridge renovation ahead of schedule and under budget.",
    "The university announced new scholarship programs for international students.",
    "Local authorities issued safety guidelines following the recent industrial incident.",
    "Researchers published their findings on renewable energy efficiency improvements.",
    "The stock market showed mixed results following the central bank announcement.",
    "A new public transportation line will connect the city center to the airport.",
    "The museum opened a new exhibition featuring artifacts from ancient civilizations.",
]

def make_padding(target_words: int) -> str:
    """Génère un padding neutre d'environ target_words mots."""
    sentences = []
    word_count = 0
    while word_count < target_words:
        s = random.choice(FILLER_SENTENCES)
        sentences.append(s)
        word_count += len(s.split())
    return " ".join(sentences)

def make_context(padding_words: int, secret_position: str = "middle") -> str:
    """
    Construit le contexte complet :
    [padding_avant] + [SECRET] + [padding_après]
    La moitié du padding est avant, l'autre après.
    """
    half = padding_words // 2
    before = make_padding(half)
    after  = make_padding(half)
    return f"{before}\n\n{SECRET}\n\n{after}"

# ── Niveaux de contexte à tester ──────────────────────────────────────────────
# On augmente le padding parasite progressivement.
# Le secret reste toujours présent — seul le bruit change.

LEVELS = [
    {"padding_words": 100,  "label": "~150 tokens"},
    {"padding_words": 300,  "label": "~450 tokens"},
    {"padding_words": 600,  "label": "~900 tokens"},
    {"padding_words": 1200, "label": "~1800 tokens"},
    {"padding_words": 2400, "label": "~3600 tokens"},
    {"padding_words": 4000, "label": "~6000 tokens"},
]

# ── API call ──────────────────────────────────────────────────────────────────

def chat(context: str, question: str) -> str:
    prompt = f"""Read the following document carefully and answer the question.

DOCUMENT:
{context}

QUESTION: {question}

Answer with only the exact value, nothing else."""

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
        data = json.loads(r.read().decode())
        return data["choices"][0]["message"]["content"].strip()

# ── Scoring ───────────────────────────────────────────────────────────────────

def score(answer: str, expected: str) -> float:
    """1.0 si la réponse contient l'info attendue, 0.0 sinon."""
    return 1.0 if expected.upper() in answer.upper() else 0.0

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    random.seed(42)

    print("═" * 65)
    print("  EGO METROLOGY — Calibration v2 — Protocole retrieval")
    print(f"  URL   : {VASTAI_URL}")
    print(f"  Cible : {EXPECTED}")
    print(f"  Runs  : {RUNS_PER_LEVEL} par niveau")
    print("═" * 65)

    results = []

    for level in LEVELS:
        pw    = level["padding_words"]
        label = level["label"]
        scores = []

        print(f"\n▶ Padding ~{pw} mots ({label})")

        for run in range(RUNS_PER_LEVEL):
            context = make_context(pw)
            prompt_words  = len(context.split()) + len(QUESTION.split())
            prompt_tokens = int(prompt_words * 1.3)

            try:
                answer = chat(context, QUESTION)
                s = score(answer, EXPECTED)
                scores.append(s)
                icon = "✓" if s == 1.0 else "✗"
                print(f"  run {run+1} {icon} → {answer[:60]}")
            except Exception as e:
                print(f"  run {run+1} [ERREUR] {e}")
                scores.append(0.0)

        success_rate = sum(scores) / len(scores)
        alpha_s      = min((prompt_tokens / 8192) ** 1.5, 1.0)
        c_dyn        = prompt_tokens * 0.3 * (1 + alpha_s)

        print(f"  → Succès : {sum(scores):.0f}/{len(scores)} ({success_rate*100:.0f}%)")
        print(f"  → prompt_tokens ≈ {prompt_tokens} | C_dyn = {c_dyn:.1f}")

        results.append({
            "padding_words":  pw,
            "prompt_tokens":  prompt_tokens,
            "c_dyn":          round(c_dyn, 2),
            "success_rate":   round(success_rate, 3),
            "runs":           scores,
        })

    # ── Fit EGO ───────────────────────────────────────────────────────────────
    print("\n" + "═" * 65)
    print("  FIT EGO — log τ = a - β · C_dyn")
    print("═" * 65)

    # On convertit le taux de succès en log_tau
    # τ_logical = 1 / p_failure  (quand succès → 1, τ → ∞ ; quand succès → 0, τ → 1)
    fit_points = []
    for r in results:
        p_fail = 1.0 - r["success_rate"]
        if p_fail <= 0:
            p_fail = 0.01  # évite log(0)
        if p_fail >= 1:
            p_fail = 0.99
        log_tau = math.log(1.0 / p_fail)
        fit_points.append((r["c_dyn"], log_tau))
        print(f"  C_dyn={r['c_dyn']:>8.1f} | success={r['success_rate']*100:.0f}% | log_tau={log_tau:.3f}")

    # Régression linéaire : log_tau = a - beta * c_dyn
    xs = [p[0] for p in fit_points]
    ys = [p[1] for p in fit_points]
    n  = len(xs)
    mx, my = sum(xs)/n, sum(ys)/n
    beta_raw = sum((xs[i]-mx)*(ys[i]-my) for i in range(n)) / sum((xs[i]-mx)**2 for i in range(n))
    a    = my - beta_raw * mx
    beta = -beta_raw  # on force le signe négatif (loi EGO : décroissance)

    print(f"\n  a_secteur    = {a:.4f}")
    print(f"  beta_secteur = {beta:.6f}")

    # ── Sauvegarde ────────────────────────────────────────────────────────────
    output = {
        "model": MODEL,
        "protocol": "retrieval_survival_v2",
        "a_secteur":    round(a, 4),
        "beta_secteur": round(beta, 6),
        "data": results,
    }
    out_path = os.path.expanduser("~/ego-metrology/calibration_v2_results.json")
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\n  Résultats sauvegardés : {out_path}")

if __name__ == "__main__":
    main()
