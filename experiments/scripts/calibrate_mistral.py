"""
Calibration empirique de tau pour Mistral-7B sur Vast.ai
On génère des textes longs et on mesure la cohérence par bloc de 200 tokens.
"""

import json
import urllib.request
import os

VASTAI_URL = os.environ.get("OPENAI_BASE_URL", "http://74.48.78.46:24810/v1")
MODEL      = "mistralai/Mistral-7B-Instruct-v0.2"

# Prompts de tailles croissantes pour tester différents C_dyn
PROMPTS = [
    (500,   "Explain in great detail the history of mathematics from ancient Greece to the 20th century."),
    (1000,  "Write a very long and detailed essay about the philosophy of science, covering Popper, Kuhn, Lakatos and Feyerabend with examples."),
    (2000,  "Write an extremely long and detailed technical tutorial about building a REST API in Python with FastAPI, covering authentication, database, testing and deployment."),
    (4000,  "Write a very long novel chapter of at least 3000 words about a scientist who discovers a new law of physics. Include dialogue, internal monologue, and detailed descriptions."),
]

def chat(prompt: str, max_tokens: int = 3000) -> str:
    url     = VASTAI_URL + "/chat/completions"
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.3,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Authorization": "Bearer local"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=300) as r:
        data = json.loads(r.read().decode())
        return data["choices"][0]["message"]["content"].strip()

def count_words(text: str) -> int:
    return len(text.split())

def score_coherence_blocks(text: str, block_words: int = 150) -> list[dict]:
    """
    Découpe le texte en blocs de ~150 mots et calcule un score de cohérence
    basique par bloc (répétitions, longueur de phrases, mots rares).
    """
    words  = text.split()
    blocks = []
    for i in range(0, len(words), block_words):
        block     = " ".join(words[i:i+block_words])
        sentences = [s.strip() for s in block.replace("!", ".").replace("?", ".").split(".") if s.strip()]

        # Score 1 : longueur moyenne des phrases (trop court = dérive)
        avg_len = sum(len(s.split()) for s in sentences) / max(len(sentences), 1)
        len_score = min(avg_len / 20.0, 1.0)

        # Score 2 : diversité lexicale
        unique = len(set(w.lower() for w in block.split()))
        total  = len(block.split())
        diversity = unique / max(total, 1)

        # Score 3 : pas de répétition de phrases entières
        repetition = 1.0
        seen = set()
        for s in sentences:
            if s.lower() in seen:
                repetition -= 0.2
            seen.add(s.lower())
        repetition = max(0.0, repetition)

        coherence = round(0.3 * len_score + 0.4 * diversity + 0.3 * repetition, 3)

        blocks.append({
            "block_start_word": i,
            "block_start_token": int(i * 1.3),  # proxy tokens ≈ mots * 1.3
            "coherence": coherence,
            "avg_sentence_len": round(avg_len, 1),
            "lexical_diversity": round(diversity, 3),
            "repetition_score": round(repetition, 3),
        })
    return blocks

def find_tau(blocks: list[dict], threshold: float = 0.45) -> int:
    """Retourne le token index du premier bloc sous le seuil de cohérence."""
    for b in blocks:
        if b["coherence"] < threshold:
            return b["block_start_token"]
    return blocks[-1]["block_start_token"] if blocks else 0

def main():
    print("═" * 60)
    print("  EGO METROLOGY — Calibration Mistral-7B")
    print(f"  URL : {VASTAI_URL}")
    print("═" * 60)

    results = []

    for prompt_tokens, prompt in PROMPTS:
        print(f"\n▶ Prompt ~{prompt_tokens} tokens...")
        print(f"  {prompt[:80]}...")

        try:
            answer = chat(prompt, max_tokens=3000)
        except Exception as e:
            print(f"  [ERREUR] {e}")
            continue

        word_count = count_words(answer)
        token_est  = int(word_count * 1.3)
        blocks     = score_coherence_blocks(answer)
        tau_obs    = find_tau(blocks)

        print(f"  Réponse : ~{word_count} mots / ~{token_est} tokens")
        print(f"  Blocs analysés : {len(blocks)}")
        print(f"  τ observé : ~{tau_obs} tokens avant dérive")
        print("  Cohérence par bloc :")
        for b in blocks:
            bar = "█" * int(b["coherence"] * 20)
            print(f"    token ~{b['block_start_token']:>5} | {bar:<20} {b['coherence']:.3f}")

        results.append({
            "prompt_tokens": prompt_tokens,
            "output_tokens": token_est,
            "tau_observed": tau_obs,
            "blocks": blocks,
        })

    print("\n═" * 60)
    print("  RÉSULTATS CALIBRATION")
    print("═" * 60)
    for r in results:
        print(f"  prompt={r['prompt_tokens']:>5} tokens → τ_obs={r['tau_observed']:>5} tokens")

    # Sauvegarde
    out = os.path.expanduser("~/ego-metrology/calibration_results.json")
    with open(out, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n  Résultats sauvegardés : {out}")

if __name__ == "__main__":
    main()
